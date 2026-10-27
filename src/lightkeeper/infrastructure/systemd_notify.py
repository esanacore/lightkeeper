"""Tell systemd how the service is doing (sd_notify), using only the standard library.

Under `Type=notify` with `WatchdogSec=` (see `deploy/lightkeeper.service`),
the `--watch` loop sends `WATCHDOG=1` once per cycle. If a cycle ever hangs,
the pings stop and systemd restarts the service instead of leaving a frozen
screen up (HAZ-002). `STATUS=` puts the current level in `systemctl status`.

Outside systemd (`NOTIFY_SOCKET` unset) every call is a no-op. A failed send
is ignored: telling systemd must never break the display, and if pings keep
failing the watchdog restarts the service, which is the safe outcome.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable

# Sends one datagram to an address; injectable so tests run on any OS.
Sender = Callable[[bytes, str], None]


def _unix_datagram(message: bytes, address: str) -> None:  # pragma: no cover - Linux only
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:  # type: ignore[attr-defined,unused-ignore]
        sock.sendto(message, address)


def notify_address(raw: str | None) -> str | None:
    """Translate `NOTIFY_SOCKET` into a socket address (a leading @ is abstract)."""
    if not raw:
        return None
    if raw.startswith("@"):
        return "\0" + raw[1:]
    if raw.startswith("/"):
        return raw
    return None  # vsock and other forms are not used for this service


class SystemdNotifier:
    """Sends sd_notify messages when running under systemd."""

    def __init__(self, raw_address: str | None = None, sender: Sender | None = None) -> None:
        """Read `NOTIFY_SOCKET` unless an address is given."""
        if raw_address is None:
            raw_address = os.environ.get("NOTIFY_SOCKET")
        self._address = notify_address(raw_address)
        self._send = sender or _unix_datagram

    @property
    def enabled(self) -> bool:
        """Whether a systemd notify socket is available."""
        return self._address is not None

    def notify(self, **fields: str) -> None:
        """Send one `KEY=value` line per field, such as READY="1"."""
        if self._address is None or not fields:
            return
        # One line per field; newlines inside a value would start a new field.
        message = "\n".join(
            f"{key}={str(value).replace(chr(10), ' ')}" for key, value in fields.items()
        )
        try:
            self._send(message.encode("utf-8"), self._address)
        except OSError:
            pass

    def ready(self, status: str) -> None:
        """Report that the service has started."""
        self.notify(READY="1", STATUS=status)

    def alive(self, status: str) -> None:
        """Report a finished cycle: pet the watchdog and update the status line."""
        self.notify(WATCHDOG="1", STATUS=status)

    def stopping(self) -> None:
        """Report a deliberate shutdown."""
        self.notify(STOPPING="1", STATUS="stopping")
