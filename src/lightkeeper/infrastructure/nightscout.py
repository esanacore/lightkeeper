"""Read-only Nightscout client.

Only GET requests, only the entries endpoint. Uses the standard library so
there is no third-party HTTP code in the data path.

Authentication: pass a Nightscout *read-only* access token (role "readable"),
never the full API_SECRET. The token travels in the `api-secret` request
header, which Nightscout's v1 API checks against its stored access tokens, so
it never appears in a URL, a proxy log, or a hosting log (ADR-0009). It is
still sensitive: it is never logged or printed, and errors redact it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 10

# 288 entries of ~200 bytes is ~60 KB; anything near a megabyte is not Nightscout.
MAX_RESPONSE_BYTES = 1_000_000

# A fetcher takes (url, headers, timeout) and returns the response body as
# bytes. Injecting it keeps the client testable without a real server.
Fetcher = Callable[[str, dict[str, str], float], bytes]

# Nightscout reads an access token from this header as well as from `?token=`
# (lib/authorization/index.js, v15.0.9). A plaintext API_SECRET here does not
# match: Nightscout compares this header against the secret's hash.
TOKEN_HEADER = "api-secret"  # noqa: S105 (a header name, not a secret)


class NightscoutError(RuntimeError):
    """Raised when Nightscout can't be reached or returns something unusable."""


class _SameSchemeRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse redirects that would downgrade https to http.

    urllib follows redirects by default and copies request headers onto the
    new request, so a redirect to http:// would send the token in the clear.
    Cross-site redirects are refused too: the token belongs to one site.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old = urllib.parse.urlparse(req.full_url)
        new = urllib.parse.urlparse(newurl)
        if new.scheme != old.scheme or new.netloc != old.netloc:
            raise urllib.error.URLError(
                f"refused redirect to a different scheme or host ({new.scheme}://{new.netloc})"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameSchemeRedirects)


def _default_fetcher(url: str, headers: dict[str, str], timeout: float) -> bytes:
    """GET `url` with `headers` and return the raw body, capped at MAX_RESPONSE_BYTES.

    NightscoutClient.__init__ only accepts https (or explicitly allowed http
    for localhost tests), so file:// and custom schemes never reach urlopen.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json", **headers})  # noqa: S310
    with _opener.open(request, timeout=timeout) as response:
        body: bytes = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise urllib.error.URLError("response larger than expected for an entries query")
        return body


class NightscoutClient:
    """Fetches recent sensor glucose entries from one Nightscout site."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        fetcher: Fetcher | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        allow_http: bool = False,
    ) -> None:
        """Configure a read-only client for one Nightscout site.

        `token` must have the readable role only. `fetcher` is injectable for
        tests, and `allow_http` exists only for localhost testing.
        """
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("base_url must be a full URL like https://my-nightscout.example")
        if parsed.scheme == "http" and not allow_http:
            # Glucose data is health data; plain HTTP is only for local testing.
            raise ValueError(
                "base_url must use https (pass allow_http=True for local testing only)"
            )
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("base_url must be just the site, with no query, fragment, or login")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._fetcher = fetcher or _default_fetcher
        self._timeout = timeout

    def _entries_url(self, count: int) -> str:
        """Build the entries URL. It never carries the token (ADR-0009)."""
        query = urllib.parse.urlencode({"count": count})
        return f"{self._base_url}/api/v1/entries/sgv.json?{query}"

    def _auth_headers(self) -> dict[str, str]:
        return {TOKEN_HEADER: self._token} if self._token else {}

    def _redact(self, text: str) -> str:
        if self._token:
            text = text.replace(self._token, "***")
            text = text.replace(urllib.parse.quote(self._token, safe=""), "***")
        return text

    def fetch_entries(self, count: int = 12) -> list[Any]:
        """Return the newest `count` raw entries as a list of dicts."""
        if not 1 <= count <= 288:
            raise ValueError("count must be between 1 and 288 (24 hours of 5-minute readings)")
        url = self._entries_url(count)
        try:
            body = self._fetcher(url, self._auth_headers(), self._timeout)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise NightscoutError(self._redact(f"could not reach Nightscout: {exc}")) from None

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise NightscoutError("Nightscout returned a response that is not JSON") from None

        if not isinstance(data, list):
            raise NightscoutError("Nightscout returned JSON that is not a list of entries")
        return data
