#!/usr/bin/env python3
"""Kontroly stažení jedné epizody z vloženého odkazu, bez sítě mimo místní server."""

from __future__ import annotations

import json
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_audio


class Handler(BaseHTTPRequestHandler):
    pages: dict[str, tuple[int, str, bytes]] = {}

    def do_GET(self) -> None:
        item = self.pages.get(self.path, (404, "text/plain", b"missing"))
        status, mime, body = item[0], item[1], item[2]
        location = item[3] if len(item) > 3 else None
        self.send_response(status)
        self.send_header("Content-Type", mime)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def serve(pages: dict[str, tuple[int, str, bytes]]) -> tuple[ThreadingHTTPServer, str]:
    Handler.pages = pages
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def expect_fail(url: str, directory: Path) -> str:
    try:
        fetch_audio.fetch(url, directory, allow_private=True)
    except SystemExit as exc:
        assert exc.code == 2, exc.code
        return "ok"
    raise AssertionError(f"odkaz měl selhat: {url}")


def test_rejects_private_and_non_http(tmp: Path) -> None:
    try:
        fetch_audio.fetch("http://127.0.0.1/a.mp3", tmp, allow_private=False)
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("místní adresa měla být odmítnutá")
    try:
        fetch_audio.fetch("file:///tmp/a.mp3", tmp, allow_private=True)
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("file odkaz měl být odmítnutý")


def test_direct_audio(base: str, tmp: Path) -> None:
    result = fetch_audio.fetch(f"{base}/epizoda.mp3", tmp, allow_private=True)
    assert result["selection"] == "direct"
    assert Path(result["path"]).read_bytes() == b"ID3fake-audio"
    assert result["bytes"] == len(b"ID3fake-audio")


def test_episode_page(base: str, tmp: Path) -> None:
    result = fetch_audio.fetch(f"{base}/epizoda", tmp, allow_private=True)
    assert result["selection"] == "page"
    assert result["media_url"].endswith("/epizoda.mp3")
    assert result["episode_title"] == "Rozhovor o ligovém kole"
    assert Path(result["path"]).read_bytes().startswith(b"ID3")


def test_feed_latest_and_item(base: str, tmp: Path) -> None:
    latest = fetch_audio.fetch(f"{base}/show.xml", tmp / "latest", allow_private=True)
    assert latest["selection"] == "feed_latest"
    assert latest["episode_title"] == "Nejnovější díl"
    assert latest["media_url"].endswith("/new.mp3")

    chosen = fetch_audio.fetch(f"{base}/starsi", tmp / "item", allow_private=True)
    assert chosen["selection"] == "feed_item"
    assert chosen["episode_title"] == "Starší díl"
    assert chosen["media_url"].endswith("/old.mp3")


def test_player_share_link(base: str, tmp: Path) -> None:
    result = fetch_audio.fetch(f"{base}/+AA4cJ2JWvxg", tmp, allow_private=True)
    assert result["selection"] == "page"
    assert result["media_url"] == f"{base}/media.mp3"
    assert "#" not in result["media_url"]
    assert result["episode_title"] == "TOTW - Omgång #22 — 90MinSvenskan"
    assert Path(result["path"]).read_bytes() == b"ID3player-audio"


def test_recent_feed(base: str, tmp: Path) -> None:
    now = fetch_audio.datetime(2026, 10, 6, 12, 0, tzinfo=fetch_audio.timezone.utc)
    recent = fetch_audio.fetch_recent(f"{base}/tyden.xml", tmp / "recent", 7, allow_private=True, now=now)
    assert len(recent) == 1
    assert recent[0]["selection"] == "feed_recent"
    assert recent[0]["episode_title"] == "Díl z tohoto týdne"
    assert recent[0]["media_url"].endswith("/new.mp3")
    assert Path(recent[0]["path"]).read_bytes() == b"ID3fake-audio"

    none = fetch_audio.fetch_recent(f"{base}/stary.xml", tmp / "old", 7, allow_private=True, now=now)
    assert none == []

    undated = fetch_audio.fetch_recent(f"{base}/show.xml", tmp / "undated", 7, allow_private=True, now=now)
    assert len(undated) == 1
    assert undated[0]["selection"] == "feed_latest"
    assert undated[0]["episode_title"] == "Nejnovější díl"


def test_ambiguous_and_empty_page(base: str, tmp: Path) -> None:
    expect_fail(f"{base}/seznam", tmp)
    expect_fail(f"{base}/spotify", tmp)


def main() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Nejnovější díl</title>
        <link>http://example.test/novy</link>
        <enclosure url="NEW" type="audio/mpeg"/>
      </item>
      <item>
        <title>Starší díl</title>
        <link>OLD_PAGE</link>
        <enclosure url="OLD" type="audio/mpeg"/>
      </item>
    </channel></rss>
    """
    page = """<!doctype html><html><head>
      <title>Rozhovor o ligovém kole</title>
      <meta property="og:audio" content="AUDIO">
      </head><body><a href="/reklama.mp3">reklama</a></body></html>
    """
    listing = """<html><body>
      <a href="/a.mp3">a</a><a href="/b.mp3">b</a>
      </body></html>
    """
    empty = "<html><head><title>Poslouchejte v aplikaci</title></head><body></body></html>"
    week_feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Díl z tohoto týdne</title>
        <pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate>
        <enclosure url="NEW" type="audio/mpeg"/>
      </item>
      <item>
        <title>Starý díl</title>
        <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate>
        <enclosure url="OLD" type="audio/mpeg"/>
      </item>
    </channel></rss>
    """
    old_feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Jen starý díl</title>
        <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate>
        <enclosure url="OLD" type="audio/mpeg"/>
      </item>
    </channel></rss>
    """
    player = """<!doctype html><html><head><title>TOTW — Overcast</title></head><body>
      <audio data-title="TOTW - Omgång #22" data-podcast-title="90MinSvenskan">
        <source src="MEDIA#t=0" type="audio/mpeg"/>
      </audio>
      <script>if (file_ext != '.mp3' && file_ext != '.m4a') {}</script>
      </body></html>
    """
    audio = b"ID3fake-audio"
    tmp = Path("/tmp/prepis-audia-fetch-test")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    server, base = serve(
        {
            "/epizoda.mp3": (200, "audio/mpeg", audio),
            "/new.mp3": (200, "audio/mpeg", audio),
            "/old.mp3": (200, "audio/mpeg", audio),
            "/reklama.mp3": (200, "audio/mpeg", b"ad"),
            "/file.mp3": (200, "audio/mpeg", b"ID3player-audio"),
        }
    )
    try:
        server.RequestHandlerClass.pages["/epizoda"] = (
            200,
            "text/html",
            page.replace("AUDIO", f"{base}/epizoda.mp3").encode(),
        )
        server.RequestHandlerClass.pages["/show.xml"] = (
            200,
            "application/rss+xml",
            feed.replace("NEW", f"{base}/new.mp3").replace("OLD_PAGE", f"{base}/starsi").replace("OLD", f"{base}/old.mp3").encode(),
        )
        server.RequestHandlerClass.pages["/starsi"] = server.RequestHandlerClass.pages["/show.xml"]
        server.RequestHandlerClass.pages["/seznam"] = (200, "text/html", listing.encode())
        server.RequestHandlerClass.pages["/spotify"] = (200, "text/html", empty.encode())
        server.RequestHandlerClass.pages["/media.mp3"] = (
            302,
            "text/html",
            b"",
            f"{base}/file.mp3",
        )
        server.RequestHandlerClass.pages["/+AA4cJ2JWvxg"] = (
            200,
            "text/html",
            player.replace("MEDIA", f"{base}/media.mp3").encode(),
        )
        server.RequestHandlerClass.pages["/tyden.xml"] = (
            200,
            "application/rss+xml",
            week_feed.replace("NEW", f"{base}/new.mp3").replace("OLD", f"{base}/old.mp3").encode(),
        )
        server.RequestHandlerClass.pages["/stary.xml"] = (
            200,
            "application/rss+xml",
            old_feed.replace("OLD", f"{base}/old.mp3").encode(),
        )
        test_rejects_private_and_non_http(tmp / "blocked")
        test_direct_audio(base, tmp / "direct")
        test_episode_page(base, tmp / "page")
        test_player_share_link(base, tmp / "player")
        test_feed_latest_and_item(base, tmp)
        test_recent_feed(base, tmp)
        test_ambiguous_and_empty_page(base, tmp / "bad")
    finally:
        server.shutdown()
    print("test_fetch: v pořádku")
    print(json.dumps({"base": base}, ensure_ascii=False))


if __name__ == "__main__":
    main()
