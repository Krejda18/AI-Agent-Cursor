#!/usr/bin/env python3
"""Namluvení textového shrnutí do mp3 přes Edge TTS."""

import argparse
import asyncio
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts

DEFAULT_VOICE = "cs-CZ-VlastaNeural"
MALE_VOICE = "cs-CZ-AntoninNeural"
CHUNK_LIMIT = 2500


def clean(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\w)[*_~](?!\w)", "", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunks(text: str, limit: int = CHUNK_LIMIT):
    blocks = re.split(r"\n\s*\n", text)
    buf = ""
    for block in blocks:
        pieces = [block.strip()]
        if len(block) > limit:
            pieces = re.split(r"(?<=[.!?])\s+", block.strip())
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if buf and len(buf) + len(piece) + 2 > limit:
                yield buf.strip()
                buf = piece
            else:
                buf = f"{buf}\n\n{piece}".strip() if buf else piece
    if buf.strip():
        yield buf.strip()


async def synthesize(text: str, voice: str, path: Path) -> None:
    await edge_tts.Communicate(text, voice).save(str(path))


def concat(parts: list[Path], output: Path) -> None:
    if len(parts) == 1:
        output.write_bytes(parts[0].read_bytes())
        return
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "list.txt"
        listing.write_text(
            "".join(f"file '{part}'\n" for part in parts),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c",
                "copy",
                str(output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def duration_seconds(path: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Shrnutí textu do mp3")
    parser.add_argument("input", nargs="?", help="textový soubor; bez něj se čte stdin")
    parser.add_argument("-o", "--output", default="summary.mp3")
    parser.add_argument("--voice", help="Edge TTS hlas, například cs-CZ-AntoninNeural")
    parser.add_argument("--male", action="store_true", help="český mužský hlas")
    args = parser.parse_args()

    raw = (
        Path(args.input).read_text(encoding="utf-8")
        if args.input
        else sys.stdin.read()
    )
    text = clean(raw)
    if not text:
        print("prázdný text", file=sys.stderr)
        return 1

    voice = args.voice or (MALE_VOICE if args.male else DEFAULT_VOICE)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        parts = []
        for index, piece in enumerate(chunks(text)):
            part = folder / f"part{index:03d}.mp3"
            asyncio.run(synthesize(piece, voice, part))
            parts.append(part)
        concat(parts, output)

    print(f"{output.resolve()}\t{voice}\t{duration_seconds(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
