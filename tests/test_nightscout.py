"""NFR-001, NFR-003: the Nightscout client is HTTPS-only, read-only, and never leaks the token."""

import json
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
