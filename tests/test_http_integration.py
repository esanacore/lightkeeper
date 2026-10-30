"""FR-005, NFR-001, NFR-003 over a real HTTP socket.

Runs a tiny fake Nightscout on localhost so the real urllib fetcher, real
JSON decoding, and real error paths are exercised end to end. This partially
closes GAP-003; a test against a real Nightscout deployment is still open.

FR-006: each failure names its kind in plain words, over the same socket; DNS
and certificate failures, which need the outside world, go through an
injected opener in front of the real fetcher.
"""

import gc
import json
import socket
import ssl
import threading
import time
import urllib.error
import warnings
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from lightkeeper.application.monitor import current_status, render_lines
from lightkeeper.domain.status import Level, Thresholds
from lightkeeper.infrastructure import nightscout
from lightkeeper.infrastructure.nightscout import NightscoutClient, NightscoutError

TOKEN = "readable-integration-token"
# Modes in which the fake answers with this HTTP status after the token check.
STATUS_MODES = {"forbidden": 403, "missing": 404, "broken": 500}


class FakeNightscout(BaseHTTPRequestHandler):
    """Serves /api/v1/entries/sgv.json, checks the token header, records requests.

    Like Nightscout with AUTH_DEFAULT_ROLES=denied: no valid token, no data.
    """

    mode = "ok"
    requests = []
    paths = []
    secrets = []
    entries = []

    def do_GET(self):  # noqa: N802 (http.server naming)
        parsed = urlparse(self.path)
        FakeNightscout.requests.append(("GET", parsed.path, parse_qs(parsed.query)))
        FakeNightscout.paths.append(self.path)
        FakeNightscout.secrets.append(self.headers.get("api-secret"))
        if parsed.path != "/api/v1/entries/sgv.json":
            self._send(404, b"not found")
        elif self.headers.get("api-secret") != TOKEN:
            self._send(401, b'{"status": 401, "message": "Unauthorized"}')
        elif FakeNightscout.mode == "slow":
            time.sleep(2)
            self._send(200, b"[]")
        elif FakeNightscout.mode == "redirect":
            # Points at a different scheme/host: must not be followed.
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/api/v1/entries/sgv.json")
            self.end_headers()
        elif FakeNightscout.mode == "redirect-same" and "r=1" not in parsed.query:
            self.send_response(302)
            self.send_header("Location", self.path + "&r=1")
            self.end_headers()
        elif FakeNightscout.mode == "huge":
            self._send(200, b"[" + b"1," * 600_000 + b"1]")
        elif FakeNightscout.mode == "html":
            self._send(200, b"<html>maintenance</html>")
        elif FakeNightscout.mode == "object":
            self._send(200, b'{"status": "ok"}')
        elif FakeNightscout.mode in STATUS_MODES:
            self._send(STATUS_MODES[FakeNightscout.mode], b'{"status": "error"}')
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
    FakeNightscout.paths = []
    FakeNightscout.secrets = []
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
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
    status, error = current_status(client(server), datetime.now(UTC), Thresholds())
    assert error is None
    assert status.level is Level.IN_RANGE
    lines = render_lines(status)
    assert lines[0] == "IN RANGE"
    assert lines[1] == "98 mg/dL \\"


def test_nfr003_only_get_requests_reach_the_server(server):
    client(server).fetch_entries(count=3)
    assert FakeNightscout.requests == [("GET", "/api/v1/entries/sgv.json", {"count": ["3"]})]


def test_nfr001_no_request_line_carries_the_token(server):
    """ADR-0009: a server or proxy logs the request line; the token is not in it."""
    client(server).fetch_entries(count=3)
    assert FakeNightscout.paths == ["/api/v1/entries/sgv.json?count=3"]
    assert FakeNightscout.secrets == [TOKEN]


def test_nfr001_missing_token_is_refused_like_auth_denied(server):
    with pytest.raises(NightscoutError):
        client(server, token=None).fetch_entries()


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
    status, error = current_status(client(dead), datetime.now(UTC), Thresholds())
    assert status.level is Level.NO_DATA
    assert error and TOKEN not in error


def test_nfr001_https_to_http_redirect_is_refused(server):
    """A downgrade redirect would leak the token in the clear, so it is refused."""
    FakeNightscout.mode = "redirect"
    with pytest.raises(NightscoutError) as caught:
        client(server).fetch_entries()
    assert "redirect" in str(caught.value)
    assert TOKEN not in str(caught.value)
    # Only the first request reached the server; nothing followed the redirect.
    assert [r[1] for r in FakeNightscout.requests] == ["/api/v1/entries/sgv.json"]


def test_nfr001_same_site_redirect_is_followed(server):
    FakeNightscout.mode = "redirect-same"
    assert client(server).fetch_entries()[0]["sgv"] == 98
    # The header survived the same-site redirect, and neither URL carried the token.
    assert FakeNightscout.secrets == [TOKEN, TOKEN]
    assert all(TOKEN not in p for p in FakeNightscout.paths)


def test_fr005_oversized_response_is_an_error(server):
    FakeNightscout.mode = "huge"
    with pytest.raises(NightscoutError):
        client(server).fetch_entries()


@pytest.mark.parametrize(
    ("mode", "token"),
    [("broken", TOKEN), ("forbidden", TOKEN), ("redirect", TOKEN), ("ok", "readable-wrong")],
    ids=["500", "403", "redirect", "401"],
)
def test_fr005_a_failed_answer_leaves_no_connection_open(server, mode, token):
    """An error answer's response is closed at once, not left for the garbage collector."""
    FakeNightscout.mode = mode
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always", ResourceWarning)
        with pytest.raises(NightscoutError) as caught:
            client(server, token=token).fetch_entries()
        assert caught.value.__context__ is None  # nothing chained holds the response
        del caught
        gc.collect()
    assert [str(w.message) for w in seen if issubclass(w.category, ResourceWarning)] == []


# --- what failed, in plain words, over the socket (FR-006) ---------------------------

NOT_ENTRIES = (
    "Nightscout answered, but not with a list of readings. Check NIGHTSCOUT_URL points at "
    "Nightscout itself, not a login or maintenance page"
)


def failure(url, token=TOKEN, timeout=5):
    with pytest.raises(NightscoutError) as caught:
        client(url, token=token, timeout=timeout).fetch_entries()
    err = caught.value
    for text in (str(err), err.hint):
        assert TOKEN not in text  # redaction holds for every kind
    return err


@pytest.mark.parametrize(
    ("mode", "token", "kind", "message", "hint"),
    [
        (
            "ok",
            "readable-wrong",
            nightscout.AUTH_REJECTED,
            "Nightscout answered HTTP 401",
            "Nightscout refused the token (HTTP 401). Check NIGHTSCOUT_TOKEN is a readable "
            "token, never the API secret",
        ),
        (
            "ok",
            None,
            nightscout.AUTH_REJECTED,
            "Nightscout answered HTTP 401",
            "Nightscout needs a token (HTTP 401). Set NIGHTSCOUT_TOKEN to a readable token, "
            "never the API secret",
        ),
        (
            "forbidden",
            TOKEN,
            nightscout.AUTH_REJECTED,
            "Nightscout answered HTTP 403",
            "Nightscout refused the token (HTTP 403). Check NIGHTSCOUT_TOKEN is a readable "
            "token, never the API secret",
        ),
        (
            "missing",
            TOKEN,
            nightscout.HTTP_STATUS,
            "Nightscout answered HTTP 404",
            "Nightscout answered HTTP 404 (not found). Check NIGHTSCOUT_URL is the address you "
            "open Nightscout at in a browser",
        ),
        (
            "broken",
            TOKEN,
            nightscout.HTTP_STATUS,
            "Nightscout answered HTTP 500",
            "Nightscout answered HTTP 500, a problem on the site. Open the site in a browser to "
            "check it is running",
        ),
        (
            "html",
            TOKEN,
            nightscout.BAD_RESPONSE,
            "Nightscout returned a response that is not JSON",
            NOT_ENTRIES,
        ),
        (
            "object",
            TOKEN,
            nightscout.BAD_RESPONSE,
            "Nightscout returned JSON that is not a list of entries",
            NOT_ENTRIES,
        ),
        (
            "huge",
            TOKEN,
            nightscout.BAD_RESPONSE,
            "Nightscout returned a response too large to be entries",
            NOT_ENTRIES,
        ),
        (
            "redirect",
            TOKEN,
            nightscout.REDIRECT_REFUSED,
            "refused redirect to a different scheme or host (http://example.invalid)",
            "Nightscout redirected to a different address, which is refused so the token "
            "never leaves the site. Set NIGHTSCOUT_URL to the final https address",
        ),
    ],
)
def test_fr006_each_answer_names_its_kind_in_plain_words(server, mode, token, kind, message, hint):
    FakeNightscout.mode = mode
    err = failure(server, token=token)
    assert (err.kind, str(err), err.hint) == (kind, message, hint)
    assert "could not reach" not in str(err)  # Nightscout answered: it was reached


def test_fr006_a_wrong_path_in_the_url_is_a_404_not_unreachable(server):
    err = failure(server + "/not-nightscout")
    assert err.kind == nightscout.HTTP_STATUS
    assert err.hint.startswith("Nightscout answered HTTP 404 (not found). Check NIGHTSCOUT_URL")


def test_fr006_slow_site_is_a_timeout(server):
    FakeNightscout.mode = "slow"
    err = failure(server, timeout=0.3)
    assert (err.kind, str(err)) == (
        nightscout.TIMEOUT,
        "Nightscout did not answer within 0.3 seconds",
    )


def test_fr006_nothing_listening_is_unreachable(server):
    err = failure(server.rsplit(":", 1)[0] + ":1")
    assert err.kind == nightscout.UNREACHABLE
    assert err.hint == (
        "Could not connect to Nightscout. Check NIGHTSCOUT_URL, that the site is up, and that "
        "this device is online"
    )


@pytest.fixture
def not_tls():
    """Serve plain HTTP to a TLS hello, as a misconfigured proxy might."""
    listener = socket.create_server(("127.0.0.1", 0))

    def serve():
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            conn.recv(4096)  # the client's hello, so it is sent before the answer
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield f"https://127.0.0.1:{listener.getsockname()[1]}"
    listener.close()
    thread.join(timeout=5)


def test_fr006_a_failed_tls_handshake_names_tls(not_tls):
    err = failure(not_tls)
    assert err.kind == nightscout.TLS
    assert err.hint.startswith(
        "The secure (TLS) connection to Nightscout failed. Check NIGHTSCOUT_URL"
    )


# DNS, certificates and timeouts need the outside world, so an opener stands
# in front of the real fetcher and raises what urllib raises for each.


class FailingOpener:
    def __init__(self, error):
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, dict(request.header_items()), timeout))
        raise self.error


@pytest.mark.parametrize(
    ("error", "kind", "hint"),
    [
        (
            urllib.error.URLError(socket.gaierror(-2, f"Name or service not known {TOKEN}")),
            nightscout.UNREACHABLE,
            "Could not find Nightscout's address (the DNS lookup failed). Check NIGHTSCOUT_URL "
            "is spelled right and that this device is online",
        ),
        (
            urllib.error.URLError(
                ssl.SSLCertVerificationError(1, "certificate verify failed: self-signed")
            ),
            nightscout.TLS,
            "The secure (TLS) connection to Nightscout failed. Check NIGHTSCOUT_URL is the "
            "site's real https address and that this device's clock is right",
        ),
        (
            urllib.error.URLError(TimeoutError("_ssl.c:989: The handshake operation timed out")),
            nightscout.TIMEOUT,
            "Nightscout did not answer within 5 seconds. Check the site is up and that this "
            "device is online",
        ),
        (
            TimeoutError("The read operation timed out"),
            nightscout.TIMEOUT,
            "Nightscout did not answer within 5 seconds. Check the site is up and that this "
            "device is online",
        ),
    ],
    ids=["dns", "certificate", "handshake-timeout", "read-timeout"],
)
def test_fr006_dns_tls_and_timeouts_through_the_real_fetcher(monkeypatch, error, kind, hint):
    opener = FailingOpener(error)
    monkeypatch.setattr(nightscout, "_opener", opener)
    err = failure("https://ns.example.com", timeout=5)
    assert (err.kind, err.hint) == (kind, hint)
    # The real fetcher still sent the token in the header only.
    ((url, headers, timeout),) = opener.requests
    assert url == "https://ns.example.com/api/v1/entries/sgv.json?count=12"
    assert headers["Api-secret"] == TOKEN and timeout == 5
