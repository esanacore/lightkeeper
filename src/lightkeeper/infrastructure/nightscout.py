"""Read-only Nightscout client.

Only GET requests, only the entries endpoint. Uses the standard library so
there is no third-party HTTP code in the data path.

Authentication: pass a Nightscout *read-only* access token (role "readable"),
never the full API_SECRET. Nightscout's v1 API takes the token as a `token`
query parameter, so the token must be treated as sensitive: it is never
logged or printed, and errors redact it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 10

# A fetcher takes (url, timeout) and returns the response body as bytes.
# Injecting it keeps the client testable without a real server.
Fetcher = Callable[[str, float], bytes]


class NightscoutError(RuntimeError):
    """Raised when Nightscout can't be reached or returns something unusable."""


def _default_fetcher(url: str, timeout: float) -> bytes:
    """GET `url` and return the raw body.

    NightscoutClient.__init__ only accepts https (or explicitly allowed http
    for localhost tests), so file:// and custom schemes never reach urlopen.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body: bytes = response.read()
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
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._fetcher = fetcher or _default_fetcher
        self._timeout = timeout

    def _entries_url(self, count: int) -> str:
        params = {"count": str(count)}
        if self._token:
            params["token"] = self._token
        return f"{self._base_url}/api/v1/entries/sgv.json?{urllib.parse.urlencode(params)}"

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
            body = self._fetcher(url, self._timeout)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise NightscoutError(self._redact(f"could not reach Nightscout: {exc}")) from None

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise NightscoutError("Nightscout returned a response that is not JSON") from None

        if not isinstance(data, list):
            raise NightscoutError("Nightscout returned JSON that is not a list of entries")
        return data
