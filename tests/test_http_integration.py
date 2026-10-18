"""FR-005, NFR-001, NFR-003 over a real HTTP socket.

Runs a tiny fake Nightscout on localhost so the real urllib fetcher, real
JSON decoding, and real error paths are exercised end to end. This partially
closes GAP-003; a test against a real Nightscout deployment is still open.
"""

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from glucose_watch.application.monitor import current_status, render_lines
from glucose_watch.domain.status import Level, Thresholds
from glucose_watch.infrastructure.nightscout import NightscoutClient, NightscoutError

TOKEN = "readable-integration-token"


class FakeNightscout(BaseHTTPRequestHandler):
    """Serves /api/v1/entries/sgv.json, checks the token, records requests."""

    mode = "ok"
    requests = []
    entries = []

    def do_GET(self):  # noqa: N802 (http.server naming)
        parsed = urlparse(self.path)
        FakeNightscout.requests.append(("GET", parsed.path, parse_qs(parsed.query)))
        if parsed.path != "/api/v1/entries/sgv.json":
            self._send(404, b"not found")
        elif parse_qs(parsed.query).get("token") != [TOKEN]:
            self._send(401, b'{"status": 401, "message": "Unauthorized"}')
        elif FakeNightscout.mode == "slow":
            time.sleep(2)
            self._send(200, b"[]")
        elif FakeNightscout.mode == "html":
            self._send(200, b"<html>maintenance</html>")
        else:
            self._send(200, json.dumps(FakeNightscout.entries).encode())

    def do_POST(self):  # noqa: N802
        FakeNightscout.requests.append(("POST", self.path, {}))
        self._send(405, b"")

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet (and token-free)
        pass


@pytest.fixture
def server():
    FakeNightscout.mode = "ok"
    FakeNightscout.requests = []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    FakeNightscout.entries = [
        {"type": "sgv", "sgv": 98, "date": now_ms - 60_000, "direction": "FortyFiveDown"},
        {"type": "sgv", "sgv": 104, "date": now_ms - 360_000, "direction": "Flat"},
    ]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeNightscout)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def client(url, token=TOKEN, timeout=5):
    return NightscoutClient(url, token=token, allow_http=True, timeout=timeout)


def test_fr005_end_to_end_reading_over_http(server):
    status, error = current_status(client(server), datetime.now(timezone.utc), Thresholds())
    assert error is None
    assert status.level is Level.IN_RANGE
    lines = render_lines(status)
    assert lines[0] == "IN RANGE"
    assert lines[1] == "98 mg/dL \\"


def test_nfr003_only_get_requests_reach_the_server(server):
    client(server).fetch_entries(count=3)
    assert FakeNightscout.requests == [("GET", "/api/v1/entries/sgv.json", {"count": ["3"], "token": [TOKEN]})]


def test_nfr001_wrong_token_is_an_error_and_not_echoed(server):
    with pytest.raises(NightscoutError) as caught:
        client(server, token="readable-wrong").fetch_entries()
    assert "readable-wrong" not in str(caught.value)


def test_fr005_timeout_is_an_error(server):
    FakeNightscout.mode = "slow"
    with pytest.raises(NightscoutError):
        client(server, timeout=0.3).fetch_entries()


def test_fr005_html_maintenance_page_is_an_error(server):
    FakeNightscout.mode = "html"
    with pytest.raises(NightscoutError):
        client(server).fetch_entries()


def test_fr005_server_gone_degrades_to_no_data(server):
    url = server
    # Point at a port nothing listens on.
    dead = url.rsplit(":", 1)[0] + ":1"
    status, error = current_status(client(dead), datetime.now(timezone.utc), Thresholds())
    assert status.level is Level.NO_DATA
    assert error and TOKEN not in error
