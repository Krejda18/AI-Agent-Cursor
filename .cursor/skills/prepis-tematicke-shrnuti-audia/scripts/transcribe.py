#!/usr/bin/env python3
"""Lokální přepis řeči modelem faster-whisper, s volitelnou zálohou OpenAI.

Nahrávka se při lokálním běhu nikam neodesílá. Externí větev vyžaduje
--confirm-external-upload a klíč OPENAI_API_KEY v prostředí.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

CHUNK_SECONDS = 600.0
OVERLAP_SECONDS = 3.0
LOW_LOGPROB = -1.0
HIGH_COMPRESSION = 2.4
NO_SPEECH = 0.6
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MAX_BYTES = 25 * 1024 * 1024


@dataclass
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    compression_ratio: float = 0.0
    unintelligible: bool = False
    uncertain: bool = False
    # Časy slov jsou vůči dílu. Do výstupního JSON se neukládají.
    words: list[tuple[float, float, str]] | None = None

    def display_text(self) -> str:
        body = self.text.strip()
        if self.unintelligible or not body:
            return "[nesrozumitelné]"
        if self.uncertain:
            return f"[nejisté] {body}"
        return body


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, text=True, capture_output=True)


def probe(path: Path) -> dict:
    if not path.is_file():
        fail(2, f"Audiosoubor neexistuje: {path}")
    if shutil.which("ffprobe") is None:
        fail(3, "V prostředí chybí ffprobe. Nainstaluj balíček ffmpeg a spusť přepis znovu.")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name,size:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        fail(3, f"ffprobe nedokáže přečíst soubor {path}. {detail}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(3, f"ffprobe vrátil nečitelný popis souboru: {exc}")
    duration = data.get("format", {}).get("duration")
    try:
        duration_s = float(duration)
    except (TypeError, ValueError):
        fail(3, "U nahrávky nelze zjistit délku. Soubor může být poškozený nebo nejde o audio.")
    if duration_s <= 0:
        fail(3, "Nahrávka má nulovou délku. Potřebuji soubor, ve kterém je řeč.")
    streams = data.get("streams") or []
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {
        "format": data.get("format", {}).get("format_name"),
        "duration_seconds": round(duration_s, 3),
        "size_bytes": int(data.get("format", {}).get("size") or path.stat().st_size),
        "codec": audio.get("codec_name"),
        "sample_rate": int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        "channels": audio.get("channels"),
    }


def convert_wav(source: Path, destination: Path) -> None:
    if shutil.which("ffmpeg") is None:
        fail(3, "V prostředí chybí ffmpeg. Bez něj nelze nahrávku převést na WAV 16 kHz.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )
    if result.returncode != 0 or not destination.is_file():
        detail = (result.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg nevrátil popis chyby"
        fail(3, f"Převod do WAV selhal: {tail}")


def chunk_bounds(duration: float, chunk_seconds: float, overlap: float) -> list[tuple[float, float]]:
    if chunk_seconds <= overlap:
        fail(3, "Délka dílu musí být větší než překryv.")
    if duration <= chunk_seconds:
        return [(0.0, duration)]
    bounds: list[tuple[float, float]] = []
    origin = 0.0
    step = chunk_seconds - overlap
    while origin < duration - 0.05:
        end = min(duration, origin + chunk_seconds)
        bounds.append((origin, end))
        if end >= duration - 0.05:
            break
        origin += step
    return bounds


def cut_wav(source: Path, destination: Path, start: float, end: float) -> None:
    result = run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(source),
            "-c",
            "copy",
            str(destination),
        ]
    )
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg nevrátil popis chyby"
        fail(3, f"Rozdělení nahrávky selhalo u času {start:.1f}s: {tail}")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def is_duplicate(previous: str, current: str) -> bool:
    old = normalize(previous)
    new = normalize(current)
    if not old or not new:
        return False
    if old == new or old.endswith(new) or new.endswith(old):
        return True
    window = old[-40:]
    return len(window) >= 12 and (new.startswith(window) or window in new[:80])


def mark_segment(segment: Segment) -> Segment:
    text = segment.text.strip()
    no_speech = segment.no_speech_prob >= NO_SPEECH and len(text) < 8
    repetitive = segment.compression_ratio >= HIGH_COMPRESSION
    if no_speech or repetitive or not text:
        segment.text = ""
        segment.words = None
        segment.unintelligible = True
        segment.uncertain = False
        return segment
    if segment.avg_logprob < LOW_LOGPROB:
        segment.uncertain = True
    return segment


def take_new_audio(segment: Segment, origin: float, keep_from: float) -> Segment | None:
    """Zahodí část segmentu, která už byla v předchozím dílu (před keep_from)."""
    if segment.words:
        kept = [
            word
            for word in segment.words
            if origin + (word[0] + word[1]) / 2 >= keep_from - 0.05
        ]
        if not kept:
            return None
        text = "".join(word[2] for word in kept).strip()
        start = origin + kept[0][0]
        end = origin + kept[-1][1]
    else:
        start = origin + segment.start
        end = origin + segment.end
        midpoint = (start + end) / 2
        if end <= keep_from + 0.05 or midpoint < keep_from - 0.05:
            return None
        text = segment.text.strip()
    if end <= start:
        return None
    return Segment(
        start=round(start, 3),
        end=round(end, 3),
        text=text,
        avg_logprob=segment.avg_logprob,
        no_speech_prob=segment.no_speech_prob,
        compression_ratio=segment.compression_ratio,
        unintelligible=segment.unintelligible or not text,
        uncertain=segment.uncertain,
    )


def merge_chunks(chunks: list[tuple[float, list[Segment]]], overlap: float) -> list[Segment]:
    """Spojí díly. Překryv slouží modelu jako kontext; do výstupu jde jen řeč,
    která začíná až po konci už zařazeného textu.
    """
    del overlap  # Délka překryvu je vlastnost řezu, ne hranice mazání.
    merged: list[Segment] = []
    covered_until = 0.0
    for origin, segments in chunks:
        for segment in segments:
            fresh = take_new_audio(segment, origin, covered_until)
            if fresh is None:
                continue
            if merged and fresh.text and is_duplicate(merged[-1].text, fresh.text):
                if fresh.start <= merged[-1].end + 0.4:
                    continue
            merged.append(fresh)
            covered_until = max(covered_until, fresh.end)
    return merged


def format_timestamp(seconds: float) -> str:
    total_tenths = int(round(max(0.0, seconds) * 10))
    hours, rem = divmod(total_tenths, 36000)
    minutes, rem = divmod(rem, 600)
    secs, tenths = divmod(rem, 10)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}.{tenths}"
    return f"{minutes:02d}:{secs:02d}.{tenths}"


def render_text(segments: list[Segment]) -> str:
    lines = []
    for segment in segments:
        lines.append(
            f"[{format_timestamp(segment.start)}–{format_timestamp(segment.end)}] {segment.display_text()}"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def load_local_model(model_name: str):
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fail(
            4,
            "Chybí balíček faster-whisper. Nainstaluj ho do .venv příkazem "
            "pip install -r .cursor/skills/prepis-tematicke-shrnuti-audia/requirements.txt "
            "a spusť přepis znovu. Nahrávka se nikam neodesílala.",
        )
    try:
        return WhisperModel(model_name, device="cpu", compute_type="int8"), model_name
    except Exception as exc:
        if model_name == "small":
            fail(4, f"Lokální model '{model_name}' se nepodařilo načíst: {exc}")
        print(
            f"Model '{model_name}' se nepodařilo načíst ({exc}). Zkouším menší model 'small'.",
            file=sys.stderr,
        )
        try:
            return WhisperModel("small", device="cpu", compute_type="int8"), "small"
        except Exception as second:
            fail(4, f"Lokální modely '{model_name}' ani 'small' se nepodařilo načíst: {second}")


def transcribe_local(wav_path: Path, language: str | None, model) -> tuple[list[Segment], str, float]:
    kwargs = {
        "beam_size": 5,
        "vad_filter": True,
        "condition_on_previous_text": True,
        "temperature": 0.0,
        "word_timestamps": True,
    }
    if language:
        kwargs["language"] = language
    try:
        segments_iter, info = model.transcribe(str(wav_path), **kwargs)
        segments = []
        for raw in segments_iter:
            words = [
                (float(word.start), float(word.end), word.word)
                for word in (getattr(raw, "words", None) or [])
            ]
            segments.append(
                mark_segment(
                    Segment(
                        start=float(raw.start),
                        end=float(raw.end),
                        text=(raw.text or "").strip(),
                        avg_logprob=float(raw.avg_logprob),
                        no_speech_prob=float(raw.no_speech_prob),
                        compression_ratio=float(getattr(raw, "compression_ratio", 0.0) or 0.0),
                        words=words or None,
                    )
                )
            )
    except Exception as exc:
        fail(4, f"Lokální přepis selhal: {exc}")
    detected = language or getattr(info, "language", None) or ""
    probability = float(getattr(info, "language_probability", 0.0) or 0.0)
    return segments, detected, probability


def transcribe_openai(wav_path: Path, language: str | None) -> tuple[list[Segment], str]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        fail(
            4,
            "Chybí OPENAI_API_KEY v prostředí procesu. Klíč nepatří do textu skillu ani do výstupních souborů.",
        )
    print(
        f"EXTERNÍ PŘENOS: nahrávka se odesílá na {OPENAI_URL} (OpenAI).",
        file=sys.stderr,
    )
    try:
        import urllib.request
    except ImportError as exc:
        fail(4, f"Standardní knihovna pro HTTP chybí: {exc}")

    size = wav_path.stat().st_size
    if size > OPENAI_MAX_BYTES:
        fail(
            4,
            f"Díl nahrávky má {size} B, limit OpenAI je {OPENAI_MAX_BYTES} B. "
            "Zkrať díly parametrem --chunk-seconds.",
        )
    boundary = "----AudioSkillBoundary7f3a"
    filename = wav_path.name
    file_bytes = wav_path.read_bytes()
    fields: list[tuple[str, str]] = [("model", "whisper-1"), ("response_format", "verbose_json"), ("timestamp_granularities[]", "segment")]
    if language:
        fields.append(("language", language))
    body = bytearray()
    for name, value in fields:
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    body.extend(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
    )
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        OPENAI_URL,
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # Nepřidávej tělo odpovědi, může obsahovat ozvěnu požadavku.
        fail(4, f"OpenAI přepis selhal ({type(exc).__name__}). Nahrávka šla na {OPENAI_URL}.")
    detected = str(payload.get("language") or language or "")
    segments = []
    for raw in payload.get("segments") or []:
        segments.append(
            mark_segment(
                Segment(
                    start=float(raw.get("start") or 0.0),
                    end=float(raw.get("end") or 0.0),
                    text=str(raw.get("text") or "").strip(),
                    avg_logprob=float(raw.get("avg_logprob") or 0.0),
                    no_speech_prob=float(raw.get("no_speech_prob") or 0.0),
                    compression_ratio=float(raw.get("compression_ratio") or 0.0),
                )
            )
        )
    return segments, detected


def write_outputs(output_dir: Path, stem: str, payload: dict, text: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    text_path = output_dir / f"{stem}.txt"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(text, encoding="utf-8")
    return json_path, text_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Přepis audia v původním jazyce s časovými značkami.")
    parser.add_argument("audio", type=Path, help="Cesta k audiosouboru dodanému uživatelem")
    parser.add_argument("--output-dir", type=Path, default=Path("output/transcripts"))
    parser.add_argument("--model", default="medium")
    parser.add_argument("--language", default="auto", help="auto, nebo kód jazyka (cs, uk, en, ...)")
    parser.add_argument("--chunk-seconds", type=float, default=CHUNK_SECONDS)
    parser.add_argument("--overlap-seconds", type=float, default=OVERLAP_SECONDS)
    parser.add_argument("--provider", choices=("local", "openai"), default="local")
    parser.add_argument(
        "--confirm-external-upload",
        action="store_true",
        help="Povolí odeslání nahrávky na OpenAI. Bez tohoto příznaku se externí přepis nespustí.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    audio = args.audio.expanduser().resolve()
    media = probe(audio)
    language = None if args.language == "auto" else args.language
    print(
        f"Soubor {audio.name}: formát {media['format']}, kodek {media['codec']}, "
        f"délka {media['duration_seconds']:.1f}s, {media['size_bytes']} B.",
        file=sys.stderr,
    )

    if args.provider == "openai" and not args.confirm_external_upload:
        fail(
            4,
            "Externí přepis je zastavený. Nahrávka by šla na "
            f"{OPENAI_URL} (OpenAI). Nejdřív to napiš uživateli a pak předej "
            "--confirm-external-upload. Klíč OPENAI_API_KEY musí být jen v prostředí.",
        )

    model = None
    model_name = args.model
    provider = f"local:faster-whisper:{model_name}"
    if args.provider == "local":
        model, model_name = load_local_model(args.model)
        provider = f"local:faster-whisper:{model_name}"
    else:
        provider = "openai:whisper-1"

    bounds = chunk_bounds(media["duration_seconds"], args.chunk_seconds, args.overlap_seconds)
    chunks: list[tuple[float, list[Segment]]] = []
    detected_language = language or ""
    language_probability = 0.0

    with tempfile.TemporaryDirectory(prefix="prepis-audia-") as tmp:
        temp = Path(tmp)
        wav = temp / "source.wav"
        convert_wav(audio, wav)
        for index, (start, end) in enumerate(bounds, start=1):
            piece = temp / f"chunk-{index:03d}.wav"
            cut_wav(wav, piece, start, end)
            print(
                f"Díl {index}/{len(bounds)}: {start:.1f}s–{end:.1f}s, nástroj {provider}.",
                file=sys.stderr,
            )
            if args.provider == "local":
                segments, chunk_language, chunk_probability = transcribe_local(
                    piece, language or None, model
                )
            else:
                segments, chunk_language = transcribe_openai(piece, language or None)
                chunk_probability = 0.0
            if chunk_language and not language:
                language = chunk_language
                detected_language = chunk_language
                language_probability = chunk_probability
            chunks.append((start, segments))

    merged = merge_chunks(chunks, args.overlap_seconds if len(bounds) > 1 else 0.0)
    spoken = [segment for segment in merged if segment.display_text() != "[nesrozumitelné]"]
    if not spoken:
        fail(
            4,
            "Přepis nevrátil žádnou řeč. Zkontroluj, zda nahrávka obsahuje srozumitelnou řeč "
            f"a zda formát {media['format']} odpovídá zvuku. Soubor {audio} zpracovaný není.",
        )

    payload = {
        "source": str(audio),
        "provider": provider,
        "model": model_name if args.provider == "local" else "whisper-1",
        "language": detected_language,
        "language_probability": round(language_probability, 4),
        "media": {
            **media,
            "converted_to": "wav/pcm_s16le/16000Hz/mono",
            "chunks": [
                {"start": round(start, 3), "end": round(end, 3)} for start, end in bounds
            ],
            "overlap_seconds": args.overlap_seconds if len(bounds) > 1 else 0.0,
        },
        "segments": [
            {
                **{key: value for key, value in asdict(segment).items() if key != "words"},
                "display_text": segment.display_text(),
            }
            for segment in merged
        ],
    }
    text = render_text(merged)
    stem = audio.stem
    json_path, text_path = write_outputs(args.output_dir, stem, payload, text)
    print(f"Přepis: {text_path}", file=sys.stderr)
    print(f"JSON: {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
