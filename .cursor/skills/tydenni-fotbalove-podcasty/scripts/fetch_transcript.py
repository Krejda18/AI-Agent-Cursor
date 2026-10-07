#!/usr/bin/env python3
"""Najde celý textový přepis dílu. Audio nestahuje.

Pořadí: odkaz podcast:transcript ve feedu, odkaz na přepis v popisu,
odkaz na stránce dílu, a když je v prostředí PODSCAN_API_KEY, celý
přepis z Podscanu podle RSS a guid. Bez textu díl zůstane missing.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

SCRIPTS = Path(__file__).resolve().parents[2] / "prepis-audio" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_audio  # noqa: E402

PODSCAN_BASE = "https://podscan.fm/api/v1"
TEXT_LIMIT = 20 * 1024 * 1024
TRANSCRIPT_EXT = {".vtt", ".srt", ".ttml"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
TIME_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?:[.,](?P<ms>\d{1,3}))?"
)


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def unescape_url(value: str) -> str:
    return html.unescape(value).rstrip(").,]}>\"'")


def is_audio_url(url: str) -> bool:
    return fetch_audio.has_audio_ext(url)


def is_transcript_url(url: str) -> bool:
    if is_audio_url(url):
        return False
    path = urllib.parse.urlsplit(url).path.lower()
    suffix = Path(path).suffix
    if suffix in TRANSCRIPT_EXT:
        return True
    return "transcript" in path


def stamp_from_clock(value: str) -> str | None:
    match = TIME_RE.search(value.strip())
    if not match:
        return None
    minutes = int(match.group("h")) * 60 + int(match.group("m"))
    seconds = int(match.group("s"))
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def cues_to_text(cues: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for start, text in cues:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"</?[^>]+>", "", cleaned).strip()
        if cleaned:
            lines.append(f"[{start}] {cleaned}")
    return "\n".join(lines) + ("\n" if lines else "")


def vtt_or_srt_to_text(body: str) -> str:
    cues: list[tuple[str, str]] = []
    current_time: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_time, buffer
        if current_time and buffer:
            cues.append((current_time, " ".join(buffer)))
        current_time = None
        buffer = []

    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.upper() == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
            flush()
            continue
        if "-->" in line:
            flush()
            current_time = stamp_from_clock(line.split("-->", 1)[0])
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if current_time:
            spoken = re.sub(r"^<v(?:\.[^ >]+)?(?:\s+[^>]+)?>", "", line)
            spoken = spoken.replace("</v>", "")
            buffer.append(spoken)
    flush()
    if cues:
        return cues_to_text(cues)
    plain = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    return plain + ("\n" if plain else "")


def html_to_text(body: str) -> str:
    without = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", body)
    without = re.sub(r"(?i)<br\s*/?>", "\n", without)
    without = re.sub(r"(?i)</p>", "\n", without)
    without = re.sub(r"<[^>]+>", " ", without)
    text = html.unescape(without)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    kept = [line for line in lines if line]
    return "\n".join(kept) + ("\n" if kept else "")


def to_text(body: bytes, mime: str, url: str) -> str:
    raw = body.decode("utf-8", errors="replace")
    path = urllib.parse.urlsplit(url).path.lower()
    kind = mime.split(";", 1)[0].strip().lower()
    if path.endswith((".vtt", ".srt")) or kind in {"text/vtt", "application/x-subrip"}:
        return vtt_or_srt_to_text(raw)
    if "html" in kind or path.endswith((".html", ".htm")):
        return html_to_text(raw)
    if path.endswith(".json") or kind == "application/json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw if raw.strip() else ""
        segments = payload.get("segments") if isinstance(payload, dict) else None
        if isinstance(segments, list):
            cues: list[tuple[str, str]] = []
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                start = segment.get("startTime") or segment.get("start")
                body_text = segment.get("body") or segment.get("text") or ""
                if start is None or not str(body_text).strip():
                    continue
                mark = stamp_from_clock(str(start)) or str(start)
                cues.append((mark, str(body_text)))
            if cues:
                return cues_to_text(cues)
        return raw if raw.strip() else ""
    if path.endswith(".ttml") or "ttml" in kind or "<tt" in raw[:200]:
        pieces = re.findall(r"<p\b([^>]*)>(.*?)</p>", raw, flags=re.I | re.S)
        cues = []
        for attrs, inner in pieces:
            begin = re.search(r'begin="([^"]+)"', attrs)
            text = re.sub(r"<[^>]+>", " ", inner)
            mark = stamp_from_clock(begin.group(1)) if begin else None
            if mark and text.strip():
                cues.append((mark, text))
        if cues:
            return cues_to_text(cues)
    return vtt_or_srt_to_text(raw) if "-->" in raw else (raw if raw.strip() else "")


def read_text_url(url: str, allow_private: bool) -> tuple[bytes, str]:
    with fetch_audio.open_url(url, allow_private) as response:
        final = response.geturl()
        mime = fetch_audio.content_type(response.headers.get("Content-Type"))
        body = fetch_audio.read_capped(response, TEXT_LIMIT)
    return body, mime or final


def item_transcript_urls(element: ElementTree.Element) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for child in element.iter():
        if fetch_audio.local_name(child.tag) != "transcript":
            continue
        url = child.get("url")
        if url:
            clean = html.unescape(url.strip())
            if clean not in seen and is_transcript_url(clean):
                found.append((clean, "rss"))
                seen.add(clean)
    blob = html.unescape(ElementTree.tostring(element, encoding="unicode"))
    for match in URL_RE.findall(blob):
        url = unescape_url(match)
        if is_transcript_url(url) and url not in seen:
            found.append((url, "popis"))
            seen.add(url)
    return found


def page_transcript_urls(page_url: str, page: str) -> list[str]:
    found: list[str] = []
    text = html.unescape(page)
    for match in re.findall(r"""<(?:track|a)\b[^>]*\b(?:src|href)=["']([^"']+)["']""", text, re.I):
        absolute = fetch_audio.absolute_ref(page_url, html.unescape(match).strip())
        if absolute and is_transcript_url(absolute):
            found.append(absolute)
    for match in URL_RE.findall(text):
        url = unescape_url(match)
        absolute = fetch_audio.absolute_ref(page_url, url)
        if absolute and is_transcript_url(absolute) and absolute not in found:
            found.append(absolute)
    return found


def parse_items(root: ElementTree.Element, base: str) -> list[dict]:
    items: list[dict] = []
    for element in root.iter():
        if fetch_audio.local_name(element.tag) not in {"item", "entry"}:
            continue
        title = fetch_audio.child_text(element, "title")
        link = fetch_audio.child_text(element, "link")
        guid = fetch_audio.child_text(element, "guid") or fetch_audio.child_text(element, "id")
        published_raw = None
        for date_name in ("pubDate", "published", "updated", "date"):
            published_raw = fetch_audio.child_text(element, date_name)
            if published_raw:
                break
        enclosure = None
        for child in list(element):
            name = fetch_audio.local_name(child.tag)
            type_ = (child.get("type") or "").lower()
            if name == "enclosure" and child.get("url"):
                enclosure = child.get("url")
            if name == "link":
                href = child.get("href")
                rel = (child.get("rel") or "").lower()
                if href and (rel == "enclosure" or type_.startswith("audio/")):
                    enclosure = href
                elif href and rel in {"", "alternate"} and not link:
                    link = href
        transcripts = item_transcript_urls(element)
        if not any((title, guid, enclosure, transcripts)):
            continue
        items.append(
            {
                "title": title,
                "link": fetch_audio.absolute_ref(base, link),
                "guid": guid,
                "enclosure": fetch_audio.absolute_ref(base, enclosure),
                "published": fetch_audio.parse_published(published_raw),
                "transcripts": [
                    (fetch_audio.absolute_ref(base, url) or url, source) for url, source in transcripts
                ],
            }
        )
    return items


def file_for(item: dict, output_dir: Path) -> Path:
    identity = item.get("guid") or item.get("enclosure") or item.get("title") or "dil"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{digest}.txt"


def save_transcript(item: dict, url: str, source: str, output_dir: Path, allow_private: bool) -> dict:
    body, mime = read_text_url(url, allow_private)
    text = to_text(body, mime, url)
    if not text.strip():
        raise ValueError("prázdný přepis")
    path = file_for(item, output_dir)
    path.write_text(text, encoding="utf-8")
    published = item.get("published")
    return {
        "title": item.get("title"),
        "guid": item.get("guid"),
        "media_url": item.get("enclosure"),
        "published": published.isoformat() if published else None,
        "transcript_url": url,
        "source": source,
        "path": str(path),
        "status": "saved",
    }


def podscan_episode_id(
    rss: str,
    guid: str | None,
    enclosure: str | None,
    api_key: str,
    base: str,
    allow_private: bool,
) -> str | None:
    if guid:
        query = urllib.parse.urlencode({"rss_feed": rss, "guid": guid, "exclude_transcript": "true"})
        url = f"{base.rstrip('/')}/episodes/search/by/feed-and-guid?{query}"
        payload = get_json(url, api_key, allow_private)
        episodes = payload.get("episodes") if isinstance(payload, dict) else None
        if isinstance(episodes, list) and episodes:
            episode_id = episodes[0].get("episode_id")
            if episode_id:
                return str(episode_id)
    if enclosure:
        query = urllib.parse.urlencode({"enclosure_url": enclosure})
        url = f"{base.rstrip('/')}/episodes/search/by/enclosure-url?{query}"
        payload = get_json(url, api_key, allow_private)
        episodes = payload.get("episodes") if isinstance(payload, dict) else None
        if isinstance(episodes, list) and episodes:
            episode_id = episodes[0].get("episode_id")
            if episode_id:
                return str(episode_id)
    return None


def get_json(url: str, api_key: str, allow_private: bool) -> dict:
    fetch_audio.check_url(url, allow_private)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": fetch_audio.USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(fetch_audio.SafeRedirectHandler(allow_private))
    try:
        with opener.open(request, timeout=60) as response:
            body = fetch_audio.read_capped(response, TEXT_LIMIT)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            fail(3, "Podscan klíč odmítl. Přepis jsem nestáhl.")
        if exc.code == 404:
            return {}
        fail(3, f"Podscan vrátil chybu {exc.code}. Přepis jsem nestáhl.")
    except urllib.error.URLError as exc:
        fail(3, f"Podscan se nepodařilo otevřít: {exc.reason}. Přepis jsem nestáhl.")
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        fail(3, "Podscan nevrátil JSON. Přepis jsem nestáhl.")
    if not isinstance(payload, dict):
        fail(3, "Podscan nevrátil JSON. Přepis jsem nestáhl.")
    return payload


def podscan_vtt(episode_id: str, api_key: str, base: str, allow_private: bool) -> bytes:
    url = f"{base.rstrip('/')}/episodes/{urllib.parse.quote(episode_id)}/transcript/download?format=vtt"
    fetch_audio.check_url(url, allow_private)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": fetch_audio.USER_AGENT,
            "Accept": "text/vtt, text/plain",
            "Authorization": f"Bearer {api_key}",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(fetch_audio.SafeRedirectHandler(allow_private))
    try:
        with opener.open(request, timeout=60) as response:
            return fetch_audio.read_capped(response, TEXT_LIMIT)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            fail(3, "Podscan klíč odmítl. Přepis jsem nestáhl.")
        if exc.code == 404:
            return b""
        raise


def missing(item: dict, reason: str) -> dict:
    published = item.get("published")
    return {
        "title": item.get("title"),
        "guid": item.get("guid"),
        "media_url": item.get("enclosure"),
        "published": published.isoformat() if published else None,
        "transcript_url": None,
        "source": None,
        "path": None,
        "status": "missing",
        "reason": reason,
    }


def fetch_recent_transcripts(
    url: str,
    output_dir: Path,
    days: int,
    allow_private: bool = False,
    now: datetime | None = None,
    api_key: str | None = None,
    podscan_base: str = PODSCAN_BASE,
) -> list[dict]:
    if days < 1:
        fail(2, "Počet dní musí být aspoň 1.")
    loaded = fetch_audio.load_feed(url, allow_private)
    if loaded is None:
        fail(2, "Odkaz není RSS feed. Textový přepis z něj neberu a audio nestahuji.")
    final, _mime, body = loaded
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        fail(2, "Feed nejde přečíst. Textový přepis jsem nestáhl.")
    items = parse_items(root, final)
    if not items:
        fail(2, "Feed neobsahuje díl. Textový přepis jsem nestáhl.")
    chosen, _selection = fetch_audio.recent_feed_items(items, days, now or datetime.now(timezone.utc))
    key = api_key if api_key is not None else os.environ.get("PODSCAN_API_KEY") or ""
    results: list[dict] = []
    for item in chosen:
        saved = None
        for transcript_url, source in item.get("transcripts") or []:
            if not transcript_url or is_audio_url(transcript_url):
                continue
            try:
                saved = save_transcript(item, transcript_url, source, output_dir, allow_private)
                break
            except (SystemExit, ValueError, urllib.error.URLError, OSError):
                saved = None
        link = item.get("link")
        if saved is None and link and not is_audio_url(link) and link != item.get("enclosure"):
            try:
                page_body, _mime = read_text_url(link, allow_private)
                page = page_body.decode("utf-8", errors="replace")
            except (SystemExit, urllib.error.URLError, OSError):
                page = ""
            for transcript_url in page_transcript_urls(link, page):
                try:
                    saved = save_transcript(item, transcript_url, "stranka", output_dir, allow_private)
                    break
                except (SystemExit, ValueError, urllib.error.URLError, OSError):
                    saved = None
        if saved is None and key:
            try:
                episode_id = podscan_episode_id(
                    final,
                    item.get("guid"),
                    item.get("enclosure"),
                    key,
                    podscan_base,
                    allow_private,
                )
                if episode_id:
                    vtt = podscan_vtt(episode_id, key, podscan_base, allow_private)
                    text = to_text(vtt, "text/vtt", "transcript.vtt")
                    if text.strip():
                        path = file_for(item, output_dir)
                        path.write_text(text, encoding="utf-8")
                        published = item.get("published")
                        saved = {
                            "title": item.get("title"),
                            "guid": item.get("guid"),
                            "media_url": item.get("enclosure"),
                            "published": published.isoformat() if published else None,
                            "transcript_url": f"{podscan_base.rstrip('/')}/episodes/{episode_id}/transcript/download?format=vtt",
                            "source": "podscan",
                            "path": str(path),
                            "status": "saved",
                        }
            except SystemExit:
                raise
            except (urllib.error.URLError, OSError, ValueError):
                saved = None
        if saved is None:
            if key:
                reason = "Celý textový přepis se nepodařilo získat. Audio jsem nestahoval."
            else:
                reason = "U dílu není veřejný textový přepis a PODSCAN_API_KEY chybí. Audio jsem nestahoval."
            saved = missing(item, reason)
        results.append(saved)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Stáhne textový přepis dílů z feedu. Audio nestahuje.")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default="output/transcripts")
    parser.add_argument("--recent-days", type=int, default=7)
    args = parser.parse_args()
    result = fetch_recent_transcripts(args.url, Path(args.output_dir), args.recent_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
