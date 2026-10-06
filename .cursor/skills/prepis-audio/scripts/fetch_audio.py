#!/usr/bin/env python3
"""Stáhne jednu epizodu z odkazu, který uživatel sám vložil.

Nepřijímá název pořadu a nic nevyhledává. Přímý audiosoubor uloží tak, jak je.
Ze stránky epizody nebo sdíleného přehrávače vezme jeden vložený zvuk a
sleduje přesměrování až k souboru. Z RSS nebo Atom feedu vezme položku,
na kterou odkaz míří, a když odkaz míří na celý feed, jen nejnovější díl.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES = 500 * 1024 * 1024
SNIFF_BYTES = 2 * 1024 * 1024
USER_AGENT = "prepis-audio/1.0"
AUDIO_EXT = {".mp3", ".m4a", ".m4b", ".mp4", ".aac", ".ogg", ".oga", ".wav", ".opus", ".flac", ".webm"}
OG_AUDIO = {"og:audio", "og:audio:url", "og:audio:secure_url", "twitter:player:stream"}
EXT_BY_TYPE = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/webm": ".webm",
}


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def has_audio_ext(url: str) -> bool:
    path = urllib.parse.urlsplit(url).path.lower()
    return Path(path).suffix in AUDIO_EXT


def content_type(header: str | None) -> str:
    return (header or "").split(";", 1)[0].strip().lower()


def without_fragment(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if not parts.fragment:
        return url
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def is_public_host(hostname: str) -> bool:
    host = hostname.strip("[]").rstrip(".")
    if not host or host.lower() in {"localhost", "metadata.google.internal"}:
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return False
    if not addresses:
        return False
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def check_url(url: str, allow_private: bool) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        fail(2, "Odkaz musí být http nebo https adresa jedné epizody nebo audiosouboru.")
    if parts.username or parts.password:
        fail(2, "Odkaz nesmí obsahovat přihlašovací údaje.")
    if not allow_private and not is_public_host(parts.hostname):
        fail(2, "Odkaz vede na adresu, ze které nahrávku nestahuji.")
    return parts


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private: bool) -> None:
        super().__init__()
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url: str, allow_private: bool):
    check_url(url, allow_private)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="GET",
    )
    opener = urllib.request.build_opener(SafeRedirectHandler(allow_private))
    try:
        return opener.open(request, timeout=60)
    except urllib.error.HTTPError as exc:
        fail(3, f"Odkaz vrátil chybu {exc.code}. Nahrávku z něj nemám a přepis jsem nespustil.")
    except urllib.error.URLError as exc:
        fail(3, f"Odkaz se nepodařilo otevřít: {exc.reason}. Nahrávku z něj nemám a přepis jsem nespustil.")


def read_capped(response, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        block = response.read(64 * 1024)
        if not block:
            break
        total += len(block)
        if total > limit:
            fail(2, "Soubor z odkazu je větší než 500 MB. Přepis jsem nespustil.")
        chunks.append(block)
    return b"".join(chunks)


def safe_filename(name: str, fallback_ext: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")
    if not base:
        base = "epizoda"
    if Path(base).suffix.lower() not in AUDIO_EXT:
        base = f"{base}{fallback_ext or '.audio'}"
    return base[:120]


def filename_from_headers(headers, url: str, mime: str) -> str:
    disposition = headers.get("Content-Disposition") or ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    if not match:
        match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
    raw = urllib.parse.unquote(match.group(1)) if match else Path(urllib.parse.urlsplit(url).path).name
    ext = EXT_BY_TYPE.get(mime, "")
    if not ext and has_audio_ext(url):
        ext = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return safe_filename(raw or "epizoda", ext or ".audio")


def is_audio_response(mime: str, url: str) -> bool:
    if mime.startswith("audio/"):
        return True
    if mime in {"application/ogg", "application/octet-stream"} and has_audio_ext(url):
        return True
    if mime == "video/mp4" and Path(urllib.parse.urlsplit(url).path).suffix.lower() in {".m4a", ".m4b", ".mp4"}:
        return True
    return False


def save_audio(url: str, output_dir: Path, allow_private: bool) -> tuple[Path, int]:
    url = without_fragment(url)
    with open_url(url, allow_private) as response:
        final = response.geturl()
        mime = content_type(response.headers.get("Content-Type"))
        if not is_audio_response(mime, final):
            fail(2, "Odkaz nevede na audiosoubor. Přepis jsem nespustil.")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename_from_headers(response.headers, final, mime)
        if path.exists():
            stem = path.stem
            suffix = path.suffix
            index = 2
            while path.exists():
                path = output_dir / f"{stem}-{index}{suffix}"
                index += 1
        total = 0
        with path.open("wb") as handle:
            while True:
                block = response.read(64 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_BYTES:
                    handle.close()
                    path.unlink(missing_ok=True)
                    fail(2, "Soubor z odkazu je větší než 500 MB. Přepis jsem nespustil.")
                handle.write(block)
        if total == 0:
            path.unlink(missing_ok=True)
            fail(2, "Odkaz vrátil prázdný soubor. Přepis jsem nespustil.")
        return path, total


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.og: list[str] = []
        self.media: list[str] = []
        self.links: list[str] = []
        self.jsonld: list[str] = []
        self.title_parts: list[str] = []
        self.player_title: str | None = None
        self._in_title = False
        self._script_ld = False
        self._script_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag == "script" and "ld+json" in attr.get("type", ""):
            self._script_ld = True
            self._script_buf = []
        if tag == "meta":
            key = (attr.get("property") or attr.get("name") or "").lower()
            if key in OG_AUDIO and attr.get("content"):
                self.og.append(attr["content"])
        if tag == "audio":
            episode = attr.get("data-title", "").strip()
            show = attr.get("data-podcast-title", "").strip()
            if episode and show:
                self.player_title = f"{episode} — {show}"
            elif episode:
                self.player_title = episode
        if tag in {"audio", "source"} and attr.get("src"):
            self.media.append(without_fragment(attr["src"]))
        if tag == "link":
            href = attr.get("href")
            type_ = attr.get("type", "").lower()
            rel = attr.get("rel", "").lower()
            if href and (type_.startswith("audio/") or "enclosure" in rel):
                self.media.append(href)
        if tag == "a" and attr.get("href") and has_audio_ext(attr["href"]):
            self.links.append(attr["href"])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._script_ld:
            self.jsonld.append("".join(self._script_buf))
            self._script_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._script_ld:
            self._script_buf.append(data)


def jsonld_audio_urls(blob: str) -> list[str]:
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        content = node.get("contentUrl")
        if isinstance(content, str) and any(
            name in {"AudioObject", "PodcastEpisode", "RadioEpisode"} for name in kinds if isinstance(name, str)
        ):
            found.append(content)
        for key in ("associatedMedia", "audio", "encoding", "@graph"):
            if key in node:
                walk(node[key])

    walk(data)
    return found


def absolute_unique(page_url: str, urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in urls:
        if not raw or not raw.strip():
            continue
        absolute = without_fragment(urllib.parse.urljoin(page_url, raw.strip()))
        key = normalize_url(absolute)
        if key in seen:
            continue
        seen.add(key)
        result.append(absolute)
    return result


def audio_from_html(page_url: str, html: str) -> tuple[str, str | None]:
    parser = PageParser()
    parser.feed(html)
    ld_urls: list[str] = []
    for blob in parser.jsonld:
        ld_urls.extend(jsonld_audio_urls(blob))
    title = parser.player_title or re.sub(r"\s+", " ", "".join(parser.title_parts)).strip() or None
    for tier in (parser.og, ld_urls, parser.media, parser.links):
        urls = absolute_unique(page_url, tier)
        if len(urls) == 1:
            return urls[0], title
        if len(urls) > 1:
            fail(
                2,
                "Odkaz vede na víc zvukových souborů. Vlož odkaz na jednu epizodu nebo na samotný audiosoubor. Přepis jsem nespustil.",
            )
    fail(
        2,
        "Z odkazu nejde získat audiosoubor. Vlož přímý soubor, stránku epizody se zvukem, nebo RSS položku. Přepis jsem nespustil.",
    )


def child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name.lower() and child.text and child.text.strip():
            return child.text.strip()
    return None


def absolute_ref(base: str, value: str | None) -> str | None:
    if not value:
        return value
    parts = urllib.parse.urlsplit(value)
    if parts.scheme in {"http", "https"}:
        return value
    if parts.scheme:
        return value
    return urllib.parse.urljoin(base, value)


def feed_items(root: ElementTree.Element) -> list[dict]:
    items: list[dict] = []
    for element in root.iter():
        if local_name(element.tag) not in {"item", "entry"}:
            continue
        title = child_text(element, "title")
        link = child_text(element, "link")
        guid = child_text(element, "guid") or child_text(element, "id")
        published_raw = None
        for date_name in ("pubDate", "published", "updated", "date"):
            published_raw = child_text(element, date_name)
            if published_raw:
                break
        enclosure = None
        for child in list(element):
            name = local_name(child.tag)
            type_ = (child.get("type") or "").lower()
            if name == "enclosure" and child.get("url") and (
                not type_ or type_.startswith("audio/") or has_audio_ext(child.get("url") or "")
            ):
                enclosure = child.get("url")
            if name == "content" and child.get("url") and (
                type_.startswith("audio/") or has_audio_ext(child.get("url") or "")
            ):
                enclosure = child.get("url")
            if name == "link":
                href = child.get("href")
                rel = (child.get("rel") or "").lower()
                if href and (rel == "enclosure" or type_.startswith("audio/") or has_audio_ext(href)):
                    enclosure = href
                elif href and rel in {"", "alternate"} and not link:
                    link = href
        if enclosure:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "guid": guid,
                    "enclosure": enclosure,
                    "published": parse_published(published_raw),
                }
            )
    return items


def parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    parsed = None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def recent_feed_items(items: list[dict], days: int, now: datetime) -> tuple[list[dict], str]:
    if not items:
        fail(2, "Feed neobsahuje zvukovou epizodu. Přepis jsem nespustil.")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(days=days)
    dated = [item for item in items if item.get("published")]
    if not dated:
        return [items[0]], "feed_latest"
    chosen = [item for item in dated if item["published"] >= cutoff]
    return chosen, "feed_recent"


def select_feed_item(items: list[dict], requested_url: str) -> tuple[dict, str]:
    if not items:
        fail(2, "Feed neobsahuje zvukovou epizodu. Přepis jsem nespustil.")
    wanted = normalize_url(requested_url)
    for item in items:
        for candidate in (item.get("link"), item.get("guid"), item.get("enclosure")):
            if candidate and normalize_url(candidate) == wanted:
                return item, "feed_item"
    return items[0], "feed_latest"


def looks_like_feed(mime: str, body: bytes) -> bool:
    if any(token in mime for token in ("xml", "rss", "atom")):
        return True
    head = body.lstrip()[:200].lower()
    return head.startswith(b"<?xml") or head.startswith(b"<rss") or head.startswith(b"<feed")


def decode_text(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def result_from_item(url: str, item: dict, selection: str, output_dir: Path, allow_private: bool) -> dict:
    path, size = save_audio(item["enclosure"], output_dir, allow_private)
    published = item.get("published")
    return {
        "source_url": url,
        "media_url": item["enclosure"],
        "path": str(path),
        "episode_title": item.get("title"),
        "selection": selection,
        "bytes": size,
        "published": published.isoformat() if published else None,
    }


def fetch(url: str, output_dir: Path, allow_private: bool = False) -> dict:
    with open_url(url, allow_private) as response:
        final = response.geturl()
        mime = content_type(response.headers.get("Content-Type"))
        if is_audio_response(mime, final):
            response.close()
            path, size = save_audio(final, output_dir, allow_private)
            return {
                "source_url": url,
                "media_url": final,
                "path": str(path),
                "episode_title": None,
                "selection": "direct",
                "bytes": size,
            }
        body = read_capped(response, SNIFF_BYTES)

    if looks_like_feed(mime, body):
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError:
            fail(2, "Odkaz vypadá jako feed, ale nejde ho přečíst. Přepis jsem nespustil.")
        items = feed_items(root)
        for item in items:
            item["link"] = absolute_ref(final, item.get("link"))
            item["guid"] = absolute_ref(final, item.get("guid"))
            item["enclosure"] = absolute_ref(final, item.get("enclosure"))
        item, selection = select_feed_item(items, final)
        return result_from_item(url, item, selection, output_dir, allow_private)

    media_url, title = audio_from_html(final, decode_text(body))
    path, size = save_audio(media_url, output_dir, allow_private)
    return {
        "source_url": url,
        "media_url": media_url,
        "path": str(path),
        "episode_title": title,
        "selection": "page",
        "bytes": size,
    }


def load_feed(url: str, allow_private: bool) -> tuple[str, str, bytes] | None:
    with open_url(url, allow_private) as response:
        final = response.geturl()
        mime = content_type(response.headers.get("Content-Type"))
        if is_audio_response(mime, final):
            return None
        body = read_capped(response, SNIFF_BYTES)
    if not looks_like_feed(mime, body):
        return None
    return final, mime, body


def fetch_recent(
    url: str,
    output_dir: Path,
    days: int,
    allow_private: bool = False,
    now: datetime | None = None,
) -> list[dict]:
    if days < 1:
        fail(2, "Počet dní musí být aspoň 1.")
    loaded = load_feed(url, allow_private)
    if loaded is None:
        one = fetch(url, output_dir, allow_private)
        one.setdefault("published", None)
        return [one]
    final, _mime, body = loaded
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        fail(2, "Odkaz vypadá jako feed, ale nejde ho přečíst. Přepis jsem nespustil.")
    items = feed_items(root)
    for item in items:
        item["link"] = absolute_ref(final, item.get("link"))
        item["guid"] = absolute_ref(final, item.get("guid"))
        item["enclosure"] = absolute_ref(final, item.get("enclosure"))
    chosen, selection = recent_feed_items(items, days, now or datetime.now(timezone.utc))
    return [
        result_from_item(url, item, selection, output_dir, allow_private)
        for item in chosen
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stáhne epizodu z vloženého odkazu.")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default="output/audio")
    parser.add_argument(
        "--recent-days",
        type=int,
        help="Z feedu stáhne epizody z posledních N dní. Bez data ve feedu jen nejnovější.",
    )
    args = parser.parse_args()
    if args.recent_days:
        result = fetch_recent(args.url, Path(args.output_dir), args.recent_days)
    else:
        result = fetch(args.url, Path(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
