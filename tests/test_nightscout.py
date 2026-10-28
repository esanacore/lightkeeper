"""NFR-001, NFR-003: the Nightscout client is HTTPS-only, read-only, and never leaks the token.

FR-006: every failure names its kind and gives a plain-language hint.
"""

import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse

import pytest

from lightkeeper.infrastructure import nightscout
from lightkeeper.infrastructure.nightscout import NightscoutClient, NightscoutError
from tests.helpers import entry

TOKEN = "readable-abc123secret"


class RecordingFetcher:
    def __init__(self, body=b"[]", error=None):
        self.body = body
        self.error = error
        self.urls = []
        self.headers = []

    def __call__(self, url, headers, timeout):
        self.urls.append((url, timeout))
        self.headers.append(headers)
        if self.error:
            raise self.error
        return self.body


def make_client(fetcher, token=TOKEN):
    return NightscoutClient("https://ns.example.com/", token=token, fetcher=fetcher)


def test_nfr003_only_reads_the_sgv_entries_endpoint():
    fetcher = RecordingFetcher(json.dumps([entry()]).encode())
    data = make_client(fetcher).fetch_entries(count=5)
    assert data[0]["sgv"] == 120
    url, timeout = fetcher.urls[0]
    parsed = urllib.parse.urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.path == "/api/v1/entries/sgv.json"
    query = urllib.parse.parse_qs(parsed.query)
    assert query == {"count": ["5"]}
    assert timeout == nightscout.DEFAULT_TIMEOUT_SECONDS


def test_nfr001_token_travels_in_a_header_never_the_url():
    """ADR-0009: the token stays out of URLs, so it stays out of access logs."""
    fetcher = RecordingFetcher()
    make_client(fetcher).fetch_entries()
    url = fetcher.urls[0][0]
    assert TOKEN not in url
    assert urllib.parse.quote(TOKEN, safe="") not in url
    assert "token" not in urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert fetcher.headers[0] == {"api-secret": TOKEN}


def test_nfr003_no_token_means_no_auth_header():
    fetcher = RecordingFetcher()
    make_client(fetcher, token=None).fetch_entries()
    assert "token=" not in fetcher.urls[0][0]
    assert fetcher.headers[0] == {}


@pytest.mark.parametrize(
    "url", ["http://ns.example.com", "ftp://ns.example.com", "ns.example.com", ""]
)
def test_nfr001_rejects_non_https_urls(url):
    with pytest.raises(ValueError):
        NightscoutClient(url)


def test_nfr001_http_allowed_only_when_explicit():
    client = NightscoutClient("http://localhost:1337", fetcher=RecordingFetcher(), allow_http=True)
    assert client.fetch_entries() == []


@pytest.mark.parametrize("count", [0, 289])
def test_nfr003_count_is_bounded(count):
    with pytest.raises(ValueError):
        make_client(RecordingFetcher()).fetch_entries(count=count)


def test_nfr001_network_errors_redact_the_token():
    error = urllib.error.URLError(f"failed for https://ns.example.com/?token={TOKEN}")
    with pytest.raises(NightscoutError) as caught:
        make_client(RecordingFetcher(error=error)).fetch_entries()
    assert TOKEN not in str(caught.value)
    assert "***" in str(caught.value)


def test_nfr001_redacts_url_encoded_token():
    odd_token = "read able/+"
    encoded = urllib.parse.quote(odd_token, safe="")
    error = OSError(f"boom {encoded}")
    client = make_client(RecordingFetcher(error=error), token=odd_token)
    with pytest.raises(NightscoutError) as caught:
        client.fetch_entries()
    assert encoded not in str(caught.value)


def test_fr005_error_without_token_keeps_message():
    client = make_client(RecordingFetcher(error=OSError("refused")), token=None)
    with pytest.raises(NightscoutError, match="refused"):
        client.fetch_entries()


def test_fr005_timeout_becomes_nightscout_error():
    with pytest.raises(NightscoutError):
        make_client(RecordingFetcher(error=TimeoutError("slow"))).fetch_entries()


@pytest.mark.parametrize("body", [b"<html>login</html>", b"\xff\xfe", b'{"status": "ok"}'])
def test_fr005_bad_responses_become_nightscout_error(body):
    with pytest.raises(NightscoutError):
        make_client(RecordingFetcher(body)).fetch_entries()


def test_default_fetcher_sends_json_accept_header(monkeypatch):
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit=None):
            seen["limit"] = limit
            return b"[]"

    def fake_open(request, timeout):
        seen["accept"] = request.get_header("Accept")
        seen["secret"] = request.get_header("Api-secret")
        seen["timeout"] = timeout
        seen["method"] = request.get_method()
        return FakeResponse()

    monkeypatch.setattr(nightscout._opener, "open", fake_open)
    headers = {"api-secret": "t"}
    assert nightscout._default_fetcher("https://ns.example.com/x", headers, 3) == b"[]"
    assert seen == {
        "accept": "application/json",
        "secret": "t",
        "timeout": 3,
        "method": "GET",
        "limit": nightscout.MAX_RESPONSE_BYTES + 1,
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://ns.example.com/?token=abc",
        "https://ns.example.com/#x",
        "https://user:pw@ns.example.com",
    ],
)
def test_nfr001_rejects_urls_with_query_fragment_or_login(url):
    with pytest.raises(ValueError):
        NightscoutClient(url)


# --- What failed, in plain words (FR-006) ------------------------------------------


def http_error(code):
    return urllib.error.HTTPError(
        "https://ns.example.com/api/v1/entries/sgv.json?count=12", code, "x", {}, None
    )


def failure(error, token=TOKEN, **kwargs):
    """The NightscoutError a fetch raises when the fetcher raises `error`."""
    client = NightscoutClient(
        "https://ns.example.com", token=token, fetcher=RecordingFetcher(error=error), **kwargs
    )
    with pytest.raises(NightscoutError) as caught:
        client.fetch_entries()
    return caught.value


@pytest.mark.parametrize("code", [401, 403])
def test_fr006_refused_token_is_named_not_could_not_reach(code):
    err = failure(http_error(code))
    assert (err.kind, str(err)) == (nightscout.AUTH_REJECTED, f"Nightscout answered HTTP {code}")
    assert err.hint == (
        f"Nightscout refused the token (HTTP {code}). Check NIGHTSCOUT_TOKEN is a readable "
        "token, never the API secret"
    )


def test_fr006_missing_token_says_one_is_needed():
    err = failure(http_error(401), token=None)
    assert err.kind == nightscout.AUTH_REJECTED
    assert err.hint.startswith("Nightscout needs a token (HTTP 401). Set NIGHTSCOUT_TOKEN to")


@pytest.mark.parametrize(
    ("code", "hint"),
    [
        (404, "Nightscout answered HTTP 404 (not found). Check NIGHTSCOUT_URL is the address"),
        (500, "Nightscout answered HTTP 500, a problem on the site."),
        (503, "Nightscout answered HTTP 503, a problem on the site."),
        (429, "Nightscout answered HTTP 429. Check NIGHTSCOUT_URL is the address"),
        (302, "Nightscout answered HTTP 302. Check NIGHTSCOUT_URL is the address"),
    ],
)
def test_fr006_other_http_statuses_say_what_nightscout_answered(code, hint):
    err = failure(http_error(code))
    assert (err.kind, str(err)) == (nightscout.HTTP_STATUS, f"Nightscout answered HTTP {code}")
    assert err.hint.startswith(hint)
    assert "could not reach" not in str(err)


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed")),
        socket.gaierror(-2, "Name or service not known"),
    ],
)
def test_fr006_dns_failure_names_dns(error):
    err = failure(error)
    assert err.kind == nightscout.UNREACHABLE
    assert str(err).startswith("could not reach Nightscout: ")
    assert err.hint == (
        "Could not find Nightscout's address (the DNS lookup failed). Check NIGHTSCOUT_URL "
        "is spelled right and that this device is online"
    )


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
        ConnectionResetError(104, "reset"),
        http.client.RemoteDisconnected("Remote end closed connection without response"),
        urllib.error.URLError("unknown url type"),
        http.client.InvalidURL("nonnumeric port"),
    ],
)
def test_fr006_connection_failures_name_the_connection(error):
    err = failure(error)
    assert err.kind == nightscout.UNREACHABLE
    assert err.hint.startswith("Could not connect to Nightscout. Check NIGHTSCOUT_URL")


@pytest.mark.parametrize(
    "error", [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))]
)
def test_fr006_timeout_says_how_long_it_waited(error):
    err = failure(error, timeout=2.5)
    assert (err.kind, str(err)) == (
        nightscout.TIMEOUT,
        "Nightscout did not answer within 2.5 seconds",
    )
    assert err.hint.startswith("Nightscout did not answer within 2.5 seconds. Check the site")


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")),
        ssl.SSLError(1, "wrong version number"),
    ],
)
def test_fr006_tls_failure_names_tls(error):
    err = failure(error)
    assert err.kind == nightscout.TLS
    assert err.hint.startswith("The secure (TLS) connection to Nightscout failed. Check")
    assert "clock" in err.hint


@pytest.mark.parametrize(
    "error",
    [
        http.client.IncompleteRead(b"[{", 1000),
        urllib.error.URLError(http.client.BadStatusLine("garbage")),
        nightscout._ResponseTooLarge("response larger than expected for an entries query"),
    ],
)
def test_fr006_cut_off_or_oversized_answer_is_a_bad_response(error):
    err = failure(error)
    assert err.kind == nightscout.BAD_RESPONSE
    assert err.hint.startswith("Nightscout answered, but not with a list of readings")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<html>login</html>", "Nightscout returned a response that is not JSON"),
        (b"\xff\xfe\xff", "Nightscout returned a response that is not JSON"),
        (b"[" * 100_000 + b"]" * 100_000, "Nightscout returned a response that is not JSON"),
        (b'{"status": "ok"}', "Nightscout returned JSON that is not a list of entries"),
    ],
    ids=["html", "not-utf", "nested-too-deep", "object"],
)
def test_fr006_answers_that_are_not_entries_are_bad_responses(body, message):
    with pytest.raises(NightscoutError) as caught:
        make_client(RecordingFetcher(body)).fetch_entries()
    assert (caught.value.kind, str(caught.value)) == (nightscout.BAD_RESPONSE, message)
    assert "not a login or maintenance page" in caught.value.hint


def test_fr006_refused_redirect_is_its_own_kind():
    err = failure(nightscout._RedirectRefused("refused redirect to a different scheme or host"))
    assert err.kind == nightscout.REDIRECT_REFUSED
    assert "redirect" in str(err)
    assert err.hint.endswith("Set NIGHTSCOUT_URL to the final https address")


def test_fr006_redirect_handler_never_names_a_login_in_the_location():
    class Request:
        full_url = "https://ns.example.com/api/v1/entries/sgv.json"

    handler = nightscout._SameSchemeRedirects()
    with pytest.raises(nightscout._RedirectRefused) as caught:
        handler.redirect_request(Request(), None, 302, "Found", {}, "http://u:pw@evil.example/x")
    assert str(caught.value.reason) == (
        "refused redirect to a different scheme or host (http://evil.example)"
    )


def test_fr006_every_kind_is_listed_once():
    assert len(set(nightscout.KINDS)) == len(nightscout.KINDS) == 7


def test_fr006_an_error_without_a_hint_uses_its_message():
    err = NightscoutError("plain")
    assert (err.kind, err.hint) == (nightscout.UNREACHABLE, "plain")


def test_fr006_messages_name_the_settings_a_caller_chose():
    err = failure(
        http_error(401), setting_name="the Nightscout address", token_setting_name="the token"
    )
    assert "Check the token is a readable token" in err.hint
    err = failure(OSError("refused"), setting_name="the Nightscout address")
    assert "Check the Nightscout address, that the site is up" in err.hint
    with pytest.raises(ValueError, match="^the Nightscout address must use https"):
        NightscoutClient("http://ns.example.com", setting_name="the Nightscout address")


@pytest.mark.parametrize(
    "url",
    [
        "http://ns.example.com",
        "ns.example.com",
        "https://",
        "https://:443",
        "https://ns.example.com/?x=1",
        "https://ns.example.com:abc",
        "https://ns.example.com:70000",
        "https://ns.example.com/night scout",
        "https://ns.example.com/\x7f",
    ],
)
def test_fr006_url_messages_name_the_variable_not_the_parameters(url):
    with pytest.raises(ValueError) as caught:
        NightscoutClient(url)
    message = str(caught.value)
    assert message.startswith("NIGHTSCOUT_URL ")
    assert "allow_http" not in message and "base_url" not in message


@pytest.mark.parametrize("token", ["readable-abc\n", "readable-\rabc", "\x00", "café-token"])
def test_nfr001_a_token_no_header_can_carry_is_refused_unechoed(token):
    """http.client would refuse the header with the token's value in its message."""
    with pytest.raises(ValueError) as caught:
        NightscoutClient("https://ns.example.com", token=token)
    assert str(caught.value).startswith("NIGHTSCOUT_TOKEN must be printable ASCII")
    assert token.strip() not in str(caught.value)


@pytest.mark.parametrize(
    "error",
    [
        http_error(401),
        urllib.error.URLError(f"failed for {TOKEN}"),
        urllib.error.URLError(socket.gaierror(-2, f"no {TOKEN}")),
        urllib.error.URLError(ssl.SSLError(1, f"bad {TOKEN}")),
        TimeoutError(f"slow {TOKEN}"),
        OSError(f"boom {urllib.parse.quote(TOKEN, safe='')}"),
        ValueError(f"Invalid header value {TOKEN!r}"),
        http.client.IncompleteRead(TOKEN.encode()),
        nightscout._RedirectRefused(f"refused redirect to x?{TOKEN}"),
    ],
)
def test_nfr001_redaction_holds_for_every_kind(error):
    err = failure(error)
    assert err.kind in nightscout.KINDS
    for text in (str(err), err.hint):
        assert TOKEN not in text
        assert urllib.parse.quote(TOKEN, safe="") not in text
