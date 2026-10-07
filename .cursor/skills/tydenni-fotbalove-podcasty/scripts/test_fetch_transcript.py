#!/usr/bin/env python3
"""Kontroly textového přepisu. Audio se z feedu nestahuje."""

from __future__ import annotations

import json
import shutil
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_transcript


class Handler(BaseHTTPRequestHandler):
    pages: dict[str, tuple[int, str, bytes]] = {}
    seen: list[str] = []

    def do_GET(self) -> None:
        self.seen.append(self.path)
        path = self.path.split("?", 1)[0]
        if path == "/episodes/search/by/feed-and-guid":
            auth = self.headers.get("Authorization") or ""
            if auth != "Bearer test-token":
                body = b'{"message":"unauthorized"}'
                self._send(401, "application/json", body)
                return
            body = json.dumps(
                {"podcast": None, "suggested_feed": False, "episodes": [{"episode_id": "ep_1"}]}
            ).encode()
            self._send(200, "application/json", body)
            return
        if path == "/episodes/ep_1/transcript/download":
            body = b"WEBVTT\n\n00:10:00.000 --> 00:10:04.000\nViking ma penize\n"
            self._send(200, "text/vtt", body)
            return
        item = self.pages.get(path, (404, "text/plain", b"missing"))
        self._send(item[0], item[1], item[2])

    def _send(self, status: int, mime: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def serve(pages: dict[str, tuple[int, str, bytes]]) -> tuple[ThreadingHTTPServer, str]:
    Handler.pages = pages
    Handler.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def feed(base: str) -> bytes:
    return f"""<?xml version="1.0"?>
<rss xmlns:podcast="https://podcastindex.org/namespace/1.0" version="2.0">
<channel>
<item>
  <title>Novy</title>
  <guid>g-new</guid>
  <link>{base}/novy-clanek</link>
  <enclosure url="{base}/novy.mp3" type="audio/mpeg"/>
  <pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate>
  <podcast:transcript url="{base}/novy.vtt" type="text/vtt"/>
</item>
<item>
  <title>Z popisu</title>
  <guid>g-popis</guid>
  <enclosure url="{base}/popis.mp3" type="audio/mpeg"/>
  <pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate>
  <description>Přepis je na {base}/z-popisu.srt a zvuk nech být.</description>
</item>
<item>
  <title>Ze stranky</title>
  <guid>g-page</guid>
  <link>{base}/stranka</link>
  <enclosure url="{base}/stranka.mp3" type="audio/mpeg"/>
  <pubDate>Sun, 04 Oct 2026 12:00:00 GMT</pubDate>
</item>
<item>
  <title>Bez textu</title>
  <guid>g-none</guid>
  <enclosure url="{base}/bez.mp3" type="audio/mpeg"/>
  <pubDate>Sat, 03 Oct 2026 12:00:00 GMT</pubDate>
</item>
<item>
  <title>Stary</title>
  <guid>g-old</guid>
  <enclosure url="{base}/stary.mp3" type="audio/mpeg"/>
  <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate>
  <podcast:transcript url="{base}/stary.vtt" type="text/vtt"/>
</item>
<item>
  <title>Podscan</title>
  <guid>g-pod</guid>
  <enclosure url="{base}/pod.mp3" type="audio/mpeg"/>
  <pubDate>Fri, 02 Oct 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
""".encode()


def test_text_marks() -> None:
    text = fetch_transcript.vtt_or_srt_to_text(
        "WEBVTT\n\n01:09:02.000 --> 01:09:08.000\n<v Host>Malmö má sto milionů\n"
    )
    assert "[1:09:02] Malmö má sto milionů" in text, text
    srt = fetch_transcript.vtt_or_srt_to_text(
        "1\n00:02:00,000 --> 00:02:03,000\nBrann má dluh\n"
    )
    assert "[02:00] Brann má dluh" in srt, srt


def test_feed(base: str, tmp: Path) -> None:
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    rows = fetch_transcript.fetch_recent_transcripts(
        f"{base}/feed.xml",
        tmp,
        7,
        allow_private=True,
        now=now,
        api_key="",
    )
    by_title = {row["title"]: row for row in rows}
    assert set(by_title) == {"Novy", "Z popisu", "Ze stranky", "Bez textu", "Podscan"}, set(by_title)
    assert by_title["Novy"]["status"] == "saved"
    assert by_title["Novy"]["source"] == "rss"
    assert "[01:05] Malmö má peníze" in Path(by_title["Novy"]["path"]).read_text(encoding="utf-8")
    assert by_title["Z popisu"]["source"] == "popis"
    assert "[02:00] Brann má dluh" in Path(by_title["Z popisu"]["path"]).read_text(encoding="utf-8")
    assert by_title["Ze stranky"]["source"] == "stranka"
    assert "[03:00] mladý hráč" in Path(by_title["Ze stranky"]["path"]).read_text(encoding="utf-8")
    assert by_title["Bez textu"]["status"] == "missing"
    assert by_title["Podscan"]["status"] == "missing"
    assert "PODSCAN_API_KEY" in by_title["Podscan"]["reason"]
    assert not any(path.split("?", 1)[0].endswith(".mp3") for path in Handler.seen), Handler.seen
    assert not any(path.endswith("stary.vtt") for path in Handler.seen)


def test_podscan(base: str, tmp: Path) -> None:
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    rows = fetch_transcript.fetch_recent_transcripts(
        f"{base}/feed.xml",
        tmp,
        7,
        allow_private=True,
        now=now,
        api_key="test-token",
        podscan_base=base,
    )
    pod = next(row for row in rows if row["title"] == "Podscan")
    assert pod["status"] == "saved", pod
    assert pod["source"] == "podscan"
    assert "[10:00] Viking ma penize" in Path(pod["path"]).read_text(encoding="utf-8")
    assert not any(path.split("?", 1)[0].endswith(".mp3") for path in Handler.seen), Handler.seen


def main() -> None:
    test_text_marks()
    tmp = Path("/tmp/tydenni-transcript-test")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    pages = {
        "/novy.vtt": (200, "text/vtt", b"WEBVTT\n\n00:01:05.000 --> 00:01:08.000\nMalm\xc3\xb6 m\xc3\xa1 pen\xc3\xadze\n"),
        "/z-popisu.srt": (200, "application/x-subrip", "1\n00:02:00,000 --> 00:02:03,000\nBrann má dluh\n".encode()),
        "/stranka": (
            200,
            "text/html",
            b'<html><a href="/ze-stranky.vtt">transcript</a></html>',
        ),
        "/ze-stranky.vtt": (200, "text/vtt", "WEBVTT\n\n00:03:00.000 --> 00:03:02.000\nmladý hráč\n".encode()),
        "/stary.vtt": (200, "text/vtt", "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nstarý\n".encode()),
    }
    server, base = serve(pages)
    pages["/feed.xml"] = (200, "application/rss+xml", feed(base))
    try:
        test_feed(base, tmp / "a")
        Handler.seen = []
        test_podscan(base, tmp / "b")
    finally:
        server.shutdown()
    print("test_fetch_transcript: v pořádku")


if __name__ == "__main__":
    main()
