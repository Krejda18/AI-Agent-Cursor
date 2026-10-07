#!/usr/bin/env python3
"""Stáhne přepis nejnovějšího dílu přes PodscriptAPI. Audio nestahuje.

Z feedu vezme jen nejnovější díl. Když už je jeho adresa ve zpracovaných,
API se nevolá. Rozdělané job_id se jen dotáhne přes GET a druhý přepis
se nespouští. Klíč se nikam nezapisuje a text přepisu se tiskne jen do souboru.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

SCRIPTS = Path(__file__).resolve().parents[2] / "prepis-audio" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_audio  # noqa: E402

PODSCRIPT_BASE = "https://podscriptapi.com/api"
TEXT_LIMIT = 20 * 1024 * 1024
POLL_INTERVAL_SEC = 5
POLL_MAX_SEC = 480
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def stamp_from_ms(value: int) -> str:
    total = value // 1000
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def segments_to_text(segments: list) -> str:
    rows: list[tuple[str | None, str]] = []
    any_time = False
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = re.sub(r"\s+", " ", str(segment.get("text") or "")).strip()
        if not text:
            continue
        try:
            start_ms = int(segment.get("start") or 0)
            end_ms = int(segment.get("end") or 0)
        except (TypeError, ValueError):
            start_ms = 0
            end_ms = 0
        mark = stamp_from_ms(start_ms) if start_ms > 0 or end_ms > 0 else None
        if mark:
            any_time = True
        speaker = str(segment.get("speaker") or "").strip()
        if speaker:
            text = f"{speaker}: {text}"
        rows.append((mark, text))
    if not rows:
        return ""
    if not any_time:
        return "\n".join(text for _mark, text in rows) + "\n"
    lines = [f"[{mark}] {text}" if mark else text for mark, text in rows]
    return "\n".join(lines) + "\n"


def transcript_body(payload: dict) -> str:
    segments = payload.get("segments")
    if isinstance(segments, list):
        text = segments_to_text(segments)
        if text.strip():
            return text
    raw = payload.get("text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip() + "\n"
    return ""


def file_for(item: dict, output_dir: Path) -> Path:
    identity = item.get("guid") or item.get("enclosure") or item.get("title") or "dil"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{digest}.txt"


def load_processed(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        found.add(html.unescape(clean))
    return found


def load_jobs(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        job_id, sep, media = clean.partition(" ")
        media = html.unescape(media.strip())
        if sep and JOB_ID_RE.fullmatch(job_id) and media:
            found[media] = job_id
    return found


def save_jobs(path: Path | None, jobs: dict[str, str]) -> None:
    if path is None:
        return
    lines = ["# Rozdělané přepisy PodscriptAPI. job_id a media_url. Tento soubor necommituj."]
    for media, job_id in jobs.items():
        if JOB_ID_RE.fullmatch(job_id):
            lines.append(f"{job_id} {media}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def episode_result(item: dict, **extra: object) -> dict:
    published = item.get("published")
    result = {
        "title": item.get("title"),
        "guid": item.get("guid"),
        "media_url": item.get("enclosure"),
        "published": published.isoformat() if isinstance(published, datetime) else None,
        "source": "podscript",
        "podscript_source": None,
        "language": None,
        "job_id": None,
        "path": None,
        "status": "missing",
        "reason": None,
    }
    result.update(extra)
    return result


def newest_item(items: list[dict]) -> dict:
    dated = [item for item in items if item.get("published")]
    if dated:
        return max(dated, key=lambda item: item["published"])
    return items[0]


def parse_feed(url: str, allow_private: bool) -> tuple[str, list[dict]]:
    loaded = fetch_audio.load_feed(url, allow_private)
    if loaded is None:
        fail(2, "Odkaz není RSS feed. Přepis přes PodscriptAPI z něj neberu a audio nestahuji.")
    final, _mime, body = loaded
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        fail(2, "Feed nejde přečíst. Přepis jsem nestáhl.")
    items: list[dict] = []
    for item in fetch_audio.feed_items(root):
        item["link"] = fetch_audio.absolute_ref(final, item.get("link"))
        item["enclosure"] = fetch_audio.absolute_ref(final, item.get("enclosure"))
        if item.get("guid"):
            item["guid"] = html.unescape(str(item["guid"])).strip()
        if item.get("enclosure"):
            item["enclosure"] = html.unescape(str(item["enclosure"])).strip()
        items.append(item)
    if not items:
        fail(2, "Feed neobsahuje díl. Přepis jsem nestáhl.")
    return final, items


def reason_for_status(status: int) -> str:
    if status == 401:
        return "PodscriptAPI klíč odmítl. Přepis jsem nestáhl."
    if status == 402:
        return "Na PodscriptAPI není dost kreditů. Přepis jsem nestáhl."
    if status == 404:
        return "PodscriptAPI díl nenašlo. Přepis jsem nestáhl."
    if status == 422:
        return "Díl nemá veřejné audio nebo je delší než osm hodin. Přepis jsem nestáhl."
    if status == 429:
        return "PodscriptAPI omezilo počet dotazů. Přepis jsem znovu nespouštěl."
    if status == 503:
        return "PodscriptAPI je dočasně nedostupné. Přepis jsem nestáhl."
    if status == 0:
        return "PodscriptAPI se nepodařilo otevřít. Přepis jsem nestáhl."
    return f"PodscriptAPI vrátilo chybu {status}. Přepis jsem nestáhl."


def decode_json(body: bytes) -> dict | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def request_json(
    method: str,
    url: str,
    api_key: str,
    allow_private: bool,
    payload: dict | None,
    sleep,
) -> tuple[int, dict | None]:
    fetch_audio.check_url(url, allow_private)
    data = None
    headers = {
        "User-Agent": fetch_audio.USER_AGENT,
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    opener = urllib.request.build_opener(fetch_audio.SafeRedirectHandler(allow_private))
    for attempt in range(2):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with opener.open(request, timeout=60) as response:
                status = getattr(response, "status", response.code)
                body = fetch_audio.read_capped(response, TEXT_LIMIT)
            return status, decode_json(body)
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                exc.read(TEXT_LIMIT)
            except OSError:
                pass
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            short_wait = retry_after.isdigit() and int(retry_after) <= 5 if retry_after else False
            if status in {429, 503} and attempt == 0 and short_wait:
                sleep(int(retry_after) if retry_after and retry_after.isdigit() else 2)
                continue
            return status, None
        except urllib.error.URLError:
            return 0, None
    return 0, None


def start_payload(feed_url: str, item: dict) -> dict:
    payload: dict = {"url": feed_url}
    if item.get("guid"):
        payload["episode"] = {"guid": item["guid"]}
    elif item.get("title"):
        payload["episode"] = {"title": item["title"]}
    return payload


def await_transcript(
    base: str,
    api_key: str,
    allow_private: bool,
    initial: dict,
    sleep,
    monotonic,
    max_wait: float,
) -> tuple[dict | None, str | None]:
    payload = initial
    started = monotonic()
    while payload.get("status") == "processing":
        job_id = str(payload.get("id") or "")
        if not JOB_ID_RE.fullmatch(job_id):
            return None, "PodscriptAPI nevrátilo použitelné job_id. Druhý přepis jsem nespustil."
        if monotonic() - started >= max_wait:
            return payload, None
        sleep(POLL_INTERVAL_SEC)
        status, refreshed = request_json(
            "GET",
            f"{base.rstrip('/')}/v1/transcripts/{urllib.parse.quote(job_id)}?format=json",
            api_key,
            allow_private,
            None,
            sleep,
        )
        if refreshed is None:
            if status == 200:
                return None, "PodscriptAPI nevrátilo JSON. Přepis jsem nestáhl."
            return None, reason_for_status(status)
        payload = refreshed
    return payload, None


def save_completed(item: dict, payload: dict, output_dir: Path) -> dict:
    text = transcript_body(payload)
    job_id = str(payload.get("id") or "") or None
    if not text.strip():
        return episode_result(
            item,
            job_id=job_id,
            podscript_source=payload.get("source"),
            language=payload.get("language"),
            status="missing",
            reason="Přepis z PodscriptAPI je prázdný. Shrnutí z něj nedělej.",
        )
    path = file_for(item, output_dir)
    path.write_text(text, encoding="utf-8")
    return episode_result(
        item,
        podscript_source=payload.get("source"),
        language=payload.get("language"),
        job_id=job_id,
        path=str(path),
        status="saved",
        reason=None,
    )


def fetch_show_transcript(
    url: str,
    output_dir: Path,
    allow_private: bool = False,
    api_key: str | None = None,
    podscript_base: str = PODSCRIPT_BASE,
    processed_urls: set[str] | None = None,
    jobs_file: Path | None = None,
    sleep=time.sleep,
    monotonic=time.monotonic,
    max_wait: float = POLL_MAX_SEC,
) -> dict:
    key = api_key if api_key is not None else os.environ.get("PODSCRIPT_API_KEY") or ""
    if not key:
        fail(3, "PODSCRIPT_API_KEY chybí. Přepis jsem nestáhl a audio jsem nestahoval.")
    final, items = parse_feed(url, allow_private)
    item = newest_item(items)
    enclosure = item.get("enclosure") or ""
    done = processed_urls or set()
    if enclosure and enclosure in done:
        return episode_result(
            item,
            status="processed",
            reason="Nejnovější díl už je ve zpracovane.txt. Přepis jsem znovu nestahoval.",
        )

    jobs = load_jobs(jobs_file)
    existing = jobs.get(enclosure) if enclosure else None
    base = podscript_base.rstrip("/")
    if existing:
        status, payload = request_json(
            "GET",
            f"{base}/v1/transcripts/{urllib.parse.quote(existing)}?format=json",
            key,
            allow_private,
            None,
            sleep,
        )
        if status == 404 or payload is None and status == 404:
            jobs.pop(enclosure, None)
            save_jobs(jobs_file, jobs)
            existing = None
            payload = None
        elif status != 200 or payload is None:
            return episode_result(item, job_id=existing, status="missing", reason=reason_for_status(status))
        elif payload.get("status") == "failed":
            jobs.pop(enclosure, None)
            save_jobs(jobs_file, jobs)
            return episode_result(
                item,
                job_id=existing,
                status="missing",
                reason="Přepis na PodscriptAPI selhal. Shrnutí z něj nedělej a díl nezapisuj.",
            )
        else:
            payload, error = await_transcript(base, key, allow_private, payload, sleep, monotonic, max_wait)
            if error or payload is None:
                return episode_result(item, job_id=existing, status="missing", reason=error)
            if payload.get("status") == "processing":
                return episode_result(
                    item,
                    job_id=str(payload.get("id") or existing),
                    status="processing",
                    reason="Přepis na PodscriptAPI ještě běží. Shrnutí z něj nedělej a díl nezapisuj.",
                )
            if payload.get("status") == "failed":
                jobs.pop(enclosure, None)
                save_jobs(jobs_file, jobs)
                return episode_result(
                    item,
                    job_id=existing,
                    status="missing",
                    reason="Přepis na PodscriptAPI selhal. Shrnutí z něj nedělej a díl nezapisuj.",
                )
            saved = save_completed(item, payload, output_dir)
            if saved["status"] == "saved":
                jobs.pop(enclosure, None)
                save_jobs(jobs_file, jobs)
            return saved

    status, payload = request_json(
        "POST",
        f"{base}/v1/transcripts",
        key,
        allow_private,
        start_payload(final, item),
        sleep,
    )
    if status not in {200, 202} or payload is None:
        if payload is None and status in {200, 202}:
            reason = "PodscriptAPI nevrátilo JSON. Přepis jsem nestáhl."
        else:
            reason = reason_for_status(status)
        return episode_result(item, status="missing", reason=reason)
    if payload.get("status") == "failed":
        return episode_result(
            item,
            job_id=str(payload.get("id") or "") or None,
            status="missing",
            reason="Přepis na PodscriptAPI selhal. Shrnutí z něj nedělej a díl nezapisuj.",
        )
    job_id = str(payload.get("id") or "")
    if payload.get("status") == "processing" and enclosure and JOB_ID_RE.fullmatch(job_id):
        jobs[enclosure] = job_id
        save_jobs(jobs_file, jobs)
    payload, error = await_transcript(base, key, allow_private, payload, sleep, monotonic, max_wait)
    if error or payload is None:
        return episode_result(item, job_id=job_id or None, status="missing", reason=error)
    if payload.get("status") == "processing":
        return episode_result(
            item,
            job_id=str(payload.get("id") or job_id or "") or None,
            status="processing",
            reason="Přepis na PodscriptAPI ještě běží. Shrnutí z něj nedělej a díl nezapisuj.",
        )
    if payload.get("status") != "completed":
        return episode_result(
            item,
            job_id=str(payload.get("id") or "") or None,
            status="missing",
            reason="PodscriptAPI přepis nedokončilo. Shrnutí z něj nedělej a díl nezapisuj.",
        )
    saved = save_completed(item, payload, output_dir)
    if saved["status"] == "saved" and enclosure:
        jobs.pop(enclosure, None)
        save_jobs(jobs_file, jobs)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Stáhne přepis nejnovějšího dílu přes PodscriptAPI. Audio nestahuje.")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default="output/transcripts")
    parser.add_argument("--processed-file", default="")
    parser.add_argument("--jobs-file", default="")
    args = parser.parse_args()
    processed = load_processed(Path(args.processed_file)) if args.processed_file else set()
    jobs_file = Path(args.jobs_file) if args.jobs_file else None
    result = fetch_show_transcript(
        args.url,
        Path(args.output_dir),
        processed_urls=processed,
        jobs_file=jobs_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
