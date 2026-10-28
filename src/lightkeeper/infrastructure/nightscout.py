"""Read-only Nightscout client.

Only GET requests, only the entries endpoint. Uses the standard library so
there is no third-party HTTP code in the data path.

Authentication: pass a Nightscout *read-only* access token (role "readable"),
never the full API_SECRET. The token travels in the `api-secret` request
header, which Nightscout's v1 API checks against its stored access tokens, so
it never appears in a URL, a proxy log, or a hosting log (ADR-0009). It is
still sensitive: it is never logged or printed, and errors redact it.

Failures: every error is a NightscoutError whose `kind` names the failing link
(one of KINDS) and whose `hint` says in plain words what to check, naming the
setting (NIGHTSCOUT_URL, NIGHTSCOUT_TOKEN). Neither ever holds the token. The
display shows "Nightscout unreachable" for every kind; the kind and the hint
are advice for the person reading stderr, never screen text (FR-006).
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
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

# What failed, from the network up. Every kind shows the same screen text.
UNREACHABLE = "unreachable"  # DNS, a refused or dropped connection
TIMEOUT = "timeout"
TLS = "tls"  # the certificate or the TLS handshake
AUTH_REJECTED = "auth_rejected"  # HTTP 401 or 403: the token
HTTP_STATUS = "http_status"  # any other HTTP error status
BAD_RESPONSE = "bad_response"  # not JSON, not a list, too large, or cut off
REDIRECT_REFUSED = "redirect_refused"  # to another scheme or host
KINDS = (UNREACHABLE, TIMEOUT, TLS, AUTH_REJECTED, HTTP_STATUS, BAD_RESPONSE, REDIRECT_REFUSED)


class NightscoutError(RuntimeError):
    """Raised when Nightscout can't be reached or returns something unusable.

    `kind` is one of KINDS. `hint` is one plain-language sentence for a
    person: what went wrong and which setting to check. It defaults to the
    message.
    """

    def __init__(self, message: str, kind: str = UNREACHABLE, hint: str = "") -> None:
        """Keep the message (for logs and --json), the kind, and the hint."""
        super().__init__(message)
        self.kind = kind
        self.hint = hint or message


class _RedirectRefused(urllib.error.URLError):
    """A redirect to another scheme or host, refused before it is followed."""


class _ResponseTooLarge(urllib.error.URLError):
    """A body larger than any entries query returns."""


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
            # Named without any user:password the Location may carry.
            where = new.netloc.rpartition("@")[2]
            raise _RedirectRefused(
                f"refused redirect to a different scheme or host ({new.scheme}://{where})"
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
            raise _ResponseTooLarge("response larger than expected for an entries query")
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
        setting_name: str = "NIGHTSCOUT_URL",
        token_setting_name: str = "NIGHTSCOUT_TOKEN",  # noqa: S107 (a variable's name)
    ) -> None:
        """Configure a read-only client for one Nightscout site.

        `token` must have the readable role only. `fetcher` is injectable for
        tests, and `allow_http` exists only for localhost testing. Every
        message names `setting_name` and `token_setting_name`, the settings a
        person can change, and never echoes the address or the token.
        """
        self._url_name = setting_name
        self._token_name = token_setting_name
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname:
            raise ValueError(
                f"{setting_name} must be a full address like https://my-nightscout.example"
            )
        if parsed.scheme == "http" and not allow_http:
            # Glucose data is health data; plain HTTP is only for local testing.
            raise ValueError(
                f"{setting_name} must use https: http would send the glucose readings "
                "and the token unencrypted"
            )
        if any(char.isspace() or not char.isprintable() for char in base_url):
            # http.client refuses these only at the first request.
            raise ValueError(f"{setting_name} must be one address, with no spaces")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError(
                f"{setting_name} must be just the site, with no query, fragment, or login"
            )
        try:
            _ = parsed.port  # urlparse checks the port only when it is read
        except ValueError:
            raise ValueError(
                f"{setting_name} has a port that is not a number up to 65535"
            ) from None
        if token is not None and not (token.isascii() and token.isprintable()):
            # A line break or other control character would make the HTTP
            # library reject the header, with the token's value in its message.
            raise ValueError(
                f"{token_setting_name} must be printable ASCII on one line, "
                "like readable-0123456789abcdef"
            )
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
            for form in (
                self._token,
                urllib.parse.quote(self._token, safe=""),
                repr(self._token)[1:-1],
            ):
                text = text.replace(form, "***")
        return text

    def fetch_entries(self, count: int = 12) -> list[Any]:
        """Return the newest `count` raw entries as a list of dicts."""
        if not 1 <= count <= 288:
            raise ValueError("count must be between 1 and 288 (24 hours of 5-minute readings)")
        url = self._entries_url(count)
        try:
            body = self._fetcher(url, self._auth_headers(), self._timeout)
        # urllib raises URLError (HTTPError among them), OSError (timeouts and
        # TLS among them) and ValueError (a header or URL it refuses); a body
        # cut off mid-read is an HTTPException.
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as exc:
            raise self._failure(exc) from None

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            raise self._bad_response("Nightscout returned a response that is not JSON") from None

        if not isinstance(data, list):
            raise self._bad_response("Nightscout returned JSON that is not a list of entries")
        return data

    def _failure(self, exc: Exception) -> NightscoutError:
        """Name the failing link for an exception from the fetcher, token redacted."""
        url = self._url_name
        # HTTPError is a URLError, so it is checked first: Nightscout answered.
        if isinstance(exc, urllib.error.HTTPError):
            return self._http_failure(exc.code)
        if isinstance(exc, _RedirectRefused):
            return NightscoutError(
                self._redact(str(exc.reason)),
                REDIRECT_REFUSED,
                "Nightscout redirected to a different address, which is refused so the token "
                f"never leaves the site. Set {url} to the final https address",
            )
        if isinstance(exc, _ResponseTooLarge):
            return self._bad_response("Nightscout returned a response too large to be entries")
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        message = self._redact(f"could not reach Nightscout: {exc}")
        if isinstance(reason, TimeoutError):
            return NightscoutError(
                f"Nightscout did not answer within {self._timeout:g} seconds",
                TIMEOUT,
                f"Nightscout did not answer within {self._timeout:g} seconds. Check the site "
                "is up and that this device is online",
            )
        # Before the generic OSError: an SSLError is one.
        if isinstance(reason, ssl.SSLError):
            return NightscoutError(
                message,
                TLS,
                "The secure (TLS) connection to Nightscout failed. Check "
                f"{url} is the site's real https address and that this device's clock is right",
            )
        if isinstance(reason, socket.gaierror):
            return NightscoutError(
                message,
                UNREACHABLE,
                "Could not find Nightscout's address (the DNS lookup failed). Check "
                f"{url} is spelled right and that this device is online",
            )
        # RemoteDisconnected is an OSError too, and InvalidURL fails before sending.
        answered = not isinstance(reason, (OSError, http.client.InvalidURL))
        if isinstance(reason, http.client.HTTPException) and answered:
            return self._bad_response(
                self._redact(f"Nightscout's response was cut off or garbled: {exc}")
            )
        return NightscoutError(
            message,
            UNREACHABLE,
            f"Could not connect to Nightscout. Check {url}, that the site is up, "
            "and that this device is online",
        )

    def _http_failure(self, code: int) -> NightscoutError:
        """Nightscout answered with an error status: the token, the address, or the site."""
        message = f"Nightscout answered HTTP {code}"
        if code in (401, 403):
            if self._token:
                hint = (
                    f"Nightscout refused the token (HTTP {code}). Check {self._token_name} "
                    "is a readable token, never the API secret"
                )
            else:
                hint = (
                    f"Nightscout needs a token (HTTP {code}). Set {self._token_name} "
                    "to a readable token, never the API secret"
                )
            return NightscoutError(message, AUTH_REJECTED, hint)
        if code == 404:
            hint = (
                f"Nightscout answered HTTP 404 (not found). Check {self._url_name} is the "
                "address you open Nightscout at in a browser"
            )
        elif code >= 500:
            hint = (
                f"Nightscout answered HTTP {code}, a problem on the site. Open the site "
                "in a browser to check it is running"
            )
        else:
            hint = (
                f"Nightscout answered HTTP {code}. Check {self._url_name} is the address "
                "you open Nightscout at in a browser"
            )
        return NightscoutError(message, HTTP_STATUS, hint)

    def _bad_response(self, message: str) -> NightscoutError:
        return NightscoutError(
            message,
            BAD_RESPONSE,
            "Nightscout answered, but not with a list of readings. Check "
            f"{self._url_name} points at Nightscout itself, not a login or maintenance page",
        )
