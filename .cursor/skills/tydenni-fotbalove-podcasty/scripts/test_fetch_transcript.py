#!/usr/bin/env python3
"""Kontroly stažení přepisu přes PodscriptAPI. Audio se z feedu nestahuje."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_transcript


class Handler(BaseHTTPRequestHandler):
    pages: dict[str, tuple[int, str, bytes]] = {}
    routes: dict[tuple[str, str], object] = {}
    seen: list[tuple[str, str]] = []
    posts: list[bytes] = []
    auth = "Bearer test-token"

    def do_GET(self) -> None:
        self.seen.append(("GET", self.path))
        path = self.path.split("?", 1)[0]
        if path in self.pages:
            status, mime, body = self.pages[path]
            self._send(status, mime, body)
            return
        self._api("GET", path)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        self.seen.append(("POST", self.path))
        self.posts.append(raw)
        path = self.path.split("?", 1)[0]
        self._api("POST", path)

    def _api(self, method: str, path: str) -> None:
        auth = self.headers.get("Authorization") or ""
        if auth != self.auth:
            self._send(401, "application/json", b'{"message":"unauthorized"}')
            return
        item = self.routes.get((method, path))
        if item is None:
            self._send(404, "application/json", b'{"message":"missing"}')
            return
        if callable(item):
            item = item()
        status, body, headers = item
        self._send(status, "application/json", body, headers)

    def _send(self, status: int, mime: str, body: bytes, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def serve() -> tuple[ThreadingHTTPServer, str]:
    Handler.pages = {}
    Handler.routes = {}
    Handler.seen = []
    Handler.posts = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def feed(base: str) -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
<item>
  <title>Stary</title>
  <guid>g-old</guid>
  <enclosure url="{base}/stary.mp3" type="audio/mpeg"/>
  <pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate>
</item>
<item>
  <title>Novy</title>
  <guid>g-new</guid>
  <enclosure url="{base}/novy.mp3" type="audio/mpeg"/>
  <pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
""".encode()


def title_feed(base: str) -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
<item>
  <title>Jen nazev</title>
  <enclosure url="{base}/nazev.mp3" type="audio/mpeg"/>
  <pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>
""".encode()


def clock():
    state = {"t": 0.0}
    sleeps: list[float] = []

    def monotonic() -> float:
        return state["t"]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        state["t"] += seconds

    return monotonic, sleep, sleeps


def completed(text: str = "Castellón vede.") -> dict:
    return {
        "id": "job-12345678",
        "status": "completed",
        "source": "asr",
        "language": "es",
        "text": text,
        "segments": [{"start": 65000, "end": 69000, "text": text}],
    }


def test_segments() -> None:
    text = fetch_transcript.segments_to_text(
        [{"start": 4142000, "end": 4148000, "speaker": "Host", "text": "Malmö má sto milionů"}]
    )
    assert "[1:09:02] Host: Malmö má sto milionů" in text, text
    plain = fetch_transcript.segments_to_text([{"start": 0, "end": 0, "text": "bez času"}])
    assert plain.strip() == "bez času", plain
    assert "[" not in plain


def test_latest(base: str, tmp: Path) -> None:
    Handler.routes[("POST", "/v1/transcripts")] = (202, b'{"id":"job-12345678","status":"processing"}', {})
    Handler.routes[("GET", "/v1/transcripts/job-12345678")] = (
        200,
        json.dumps(completed()).encode(),
        {},
    )
    monotonic, sleep, sleeps = clock()
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp,
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        jobs_file=tmp / "probihajici.txt",
        sleep=sleep,
        monotonic=monotonic,
        max_wait=30,
    )
    assert row["status"] == "saved", row
    assert row["title"] == "Novy", row
    assert row["source"] == "podscript"
    assert row["podscript_source"] == "asr"
    assert row["language"] == "es"
    assert "[01:05] Castellón vede." in Path(row["path"]).read_text(encoding="utf-8")
    assert len(Handler.posts) == 1, Handler.posts
    sent = json.loads(Handler.posts[0].decode())
    assert sent["url"] == f"{base}/feed.xml"
    assert sent["episode"] == {"guid": "g-new"}
    assert "webhook_url" not in sent
    dumped = json.dumps(row)
    assert "test-token" not in dumped
    assert "Castellón vede." not in dumped
    assert not any(path.endswith(".mp3") for _method, path in Handler.seen), Handler.seen
    assert sleeps == [5], sleeps
    assert not (tmp / "probihajici.txt").read_text(encoding="utf-8").strip().endswith("novy.mp3")


def test_processed_skips_api(base: str, tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    processed = tmp / "zpracovane.txt"
    processed.write_text(f"# hotovo\n{base}/novy.mp3\n", encoding="utf-8")
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp / "out",
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        processed_urls=fetch_transcript.load_processed(processed),
    )
    assert row["status"] == "processed", row
    assert row["title"] == "Novy"
    assert row["path"] is None
    assert Handler.posts == []
    assert not any(method == "POST" for method, _path in Handler.seen), Handler.seen


def test_resume_job(base: str, tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    jobs = tmp / "probihajici.txt"
    jobs.write_text(f"job-12345678 {base}/novy.mp3\n", encoding="utf-8")
    Handler.routes[("GET", "/v1/transcripts/job-12345678")] = (
        200,
        json.dumps(completed("už hotovo")).encode(),
        {},
    )
    monotonic, sleep, sleeps = clock()
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp / "out",
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        jobs_file=jobs,
        sleep=sleep,
        monotonic=monotonic,
    )
    assert row["status"] == "saved", row
    assert "už hotovo" in Path(row["path"]).read_text(encoding="utf-8")
    assert Handler.posts == []
    assert sleeps == []
    assert "job-12345678" not in jobs.read_text(encoding="utf-8")


def test_processing_keeps_job(base: str, tmp: Path) -> None:
    Handler.routes[("POST", "/v1/transcripts")] = (202, b'{"id":"job-12345678","status":"processing"}', {})
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp,
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        jobs_file=tmp / "probihajici.txt",
        sleep=lambda _seconds: None,
        monotonic=lambda: 0.0,
        max_wait=0,
    )
    assert row["status"] == "processing", row
    assert row["job_id"] == "job-12345678"
    assert row["path"] is None
    stored = (tmp / "probihajici.txt").read_text(encoding="utf-8")
    assert f"job-12345678 {base}/novy.mp3" in stored
    assert len(Handler.posts) == 1


def test_title_when_guid_missing(base: str, tmp: Path) -> None:
    Handler.routes[("POST", "/v1/transcripts")] = (200, json.dumps(completed("podle názvu")).encode(), {})
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/nazev.xml",
        tmp,
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        sleep=lambda _seconds: None,
        monotonic=lambda: 0.0,
    )
    assert row["status"] == "saved", row
    sent = json.loads(Handler.posts[0].decode())
    assert sent["episode"] == {"title": "Jen nazev"}


def test_rate_limit_does_not_wait(base: str, tmp: Path) -> None:
    Handler.routes[("POST", "/v1/transcripts")] = (429, b'{"message":"slow"}', {"Retry-After": "36000"})
    sleeps: list[float] = []
    started = time.monotonic()
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp,
        allow_private=True,
        api_key="test-token",
        podscript_base=base,
        sleep=lambda seconds: sleeps.append(seconds),
        monotonic=time.monotonic,
    )
    assert row["status"] == "missing", row
    assert "36000" not in (row["reason"] or "")
    assert "test-token" not in json.dumps(row)
    assert sleeps == []
    assert time.monotonic() - started < 3


def test_unauthorized(base: str, tmp: Path) -> None:
    row = fetch_transcript.fetch_show_transcript(
        f"{base}/feed.xml",
        tmp,
        allow_private=True,
        api_key="psk_live_tajny",
        podscript_base=base,
    )
    assert row["status"] == "missing", row
    assert "psk_live_tajny" not in json.dumps(row)
    assert "klíč odmítl" in row["reason"]


def test_missing_key() -> None:
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            fetch_transcript.fetch_show_transcript(
                "https://example.com/feed.xml",
                Path("/tmp/unused"),
                api_key="",
            )
        except SystemExit as exc:
            assert exc.code == 3
            assert "PODSCRIPT_API_KEY chybí" in err.getvalue()
            assert "psk_" not in err.getvalue()
            return
    raise AssertionError("chybějící klíč měl běh zastavit")


def main() -> None:
    test_segments()
    test_missing_key()
    tmp = Path("/tmp/tydenni-transcript-test")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    server, base = serve()
    Handler.pages["/feed.xml"] = (200, "application/rss+xml", feed(base))
    Handler.pages["/nazev.xml"] = (200, "application/rss+xml", title_feed(base))
    try:
        test_latest(base, tmp / "a")
        Handler.seen = []
        Handler.posts = []
        test_processed_skips_api(base, tmp / "b")
        Handler.seen = []
        Handler.posts = []
        test_resume_job(base, tmp / "c")
        Handler.seen = []
        Handler.posts = []
        test_processing_keeps_job(base, tmp / "d")
        Handler.seen = []
        Handler.posts = []
        test_title_when_guid_missing(base, tmp / "e")
        Handler.seen = []
        Handler.posts = []
        test_rate_limit_does_not_wait(base, tmp / "f")
        Handler.seen = []
        Handler.posts = []
        test_unauthorized(base, tmp / "g")
    finally:
        server.shutdown()
    print("test_fetch_transcript: v pořádku")


if __name__ == "__main__":
    main()
