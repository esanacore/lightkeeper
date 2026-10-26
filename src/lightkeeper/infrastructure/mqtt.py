"""A minimal, publish-only MQTT 3.1.1 client (ADR-0010).

Only what Lightkeeper needs: CONNECT (with a Last Will, username, and
password), PUBLISH at QoS 0 with an optional retain flag, and DISCONNECT. It
never subscribes, and the only packet it reads is the CONNACK. Standard
library only (ADR-0005), so there is no third-party network code on the
display device.

Safety and security:
- TLS with certificate verification is the default. Plain MQTT is refused
  unless the broker is on localhost (mirrors `allow_http` in the Nightscout
  client), because the password and health data would cross the network in
  the clear.
- The password never appears in an exception message.
"""

from __future__ import annotations

import socket
import ssl
import struct
from collections.abc import Callable
from dataclasses import dataclass

PROTOCOL_LEVEL = 4  # MQTT 3.1.1
MAX_REMAINING_LENGTH = 268_435_455  # the largest length the 4-byte encoding allows
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_CONNECT = 0x10
_CONNACK = 0x20
_PUBLISH = 0x30
_DISCONNECT = 0xE0

# CONNACK return codes (MQTT 3.1.1, section 3.2.2.3).
_REFUSALS = {
    1: "unacceptable protocol version",
    2: "client identifier rejected",
    3: "server unavailable",
    4: "bad user name or password",
    5: "not authorized",
}


class MqttError(RuntimeError):
    """Raised when the broker can't be reached or refuses the connection."""


@dataclass(frozen=True)
class Will:
    """The message the broker publishes if this client disappears."""

    topic: str
    payload: bytes
    retain: bool = True


def encode_remaining_length(length: int) -> bytes:
    """Encode a packet's remaining length as MQTT's variable-length integer."""
    if not 0 <= length <= MAX_REMAINING_LENGTH:
        raise ValueError(f"remaining length out of range: {length}")
    out = bytearray()
    while True:
        byte, length = length % 128, length // 128
        out.append(byte | (0x80 if length else 0))
        if not length:
            return bytes(out)


def _string(text: str) -> bytes:
    """Encode `text` as UTF-8 with MQTT's two-byte length prefix."""
    data = text.encode("utf-8")
    if len(data) > 0xFFFF:
        raise ValueError("MQTT strings are limited to 65535 bytes")
    return struct.pack(">H", len(data)) + data


def _binary(data: bytes) -> bytes:
    if len(data) > 0xFFFF:
        raise ValueError("MQTT binary fields are limited to 65535 bytes")
    return struct.pack(">H", len(data)) + data


def connect_packet(
    client_id: str,
    keepalive: int,
    will: Will | None = None,
    username: str | None = None,
    password: str | None = None,
) -> bytes:
    """Build a CONNECT packet with a clean session."""
    if not 0 < keepalive <= 0xFFFF:
        raise ValueError("keepalive must be between 1 and 65535 seconds")
    if password is not None and username is None:
        raise ValueError("MQTT 3.1.1 needs a user name to send a password")
    flags = 0x02  # clean session
    payload = _string(client_id)
    if will is not None:
        flags |= 0x04 | (0x20 if will.retain else 0)  # will flag, QoS 0, retain
        payload += _string(will.topic) + _binary(will.payload)
    if username is not None:
        flags |= 0x80
        payload += _string(username)
    if password is not None:
        flags |= 0x40
        payload += _binary(password.encode("utf-8"))
    variable = _string("MQTT") + bytes([PROTOCOL_LEVEL, flags]) + struct.pack(">H", keepalive)
    body = variable + payload
    return bytes([_CONNECT]) + encode_remaining_length(len(body)) + body


def publish_packet(topic: str, payload: bytes, retain: bool = False) -> bytes:
    """Build a QoS 0 PUBLISH packet."""
    if not topic or any(c in topic for c in "+#\x00"):
        raise ValueError("publish topics must be non-empty with no wildcards")
    body = _string(topic) + payload
    header = _PUBLISH | (0x01 if retain else 0)
    return bytes([header]) + encode_remaining_length(len(body)) + body


def disconnect_packet() -> bytes:
    """Build a DISCONNECT packet; the broker then discards the will."""
    return bytes([_DISCONNECT, 0])


def check_connack(packet: bytes) -> None:
    """Raise MqttError unless `packet` is a CONNACK that accepts the connection."""
    if len(packet) != 4 or packet[0] != _CONNACK or packet[1] != 2:
        raise MqttError("broker did not answer with a CONNACK")
    code = packet[3]
    if code:
        raise MqttError(f"broker refused the connection: {_REFUSALS.get(code, f'code {code}')}")


# Opens a connected socket-like object; injectable for tests.
Opener = Callable[[str, int, float], socket.socket]


def _tcp(host: str, port: int, timeout: float) -> socket.socket:
    return socket.create_connection((host, port), timeout=timeout)


class MqttPublisher:
    """One connection to one broker, for publishing only."""

    def __init__(
        self,
        host: str,
        port: int,
        client_id: str,
        username: str | None = None,
        password: str | None = None,
        tls: bool = True,
        timeout: float = 10,
        opener: Opener | None = None,
    ) -> None:
        """Configure, without connecting yet. Plain MQTT only to localhost."""
        if not host:
            raise ValueError("an MQTT broker host is required")
        if not tls and host.lower() not in LOCAL_HOSTS:
            raise ValueError(
                "plain MQTT is only allowed to a broker on localhost; enable TLS for "
                f"{host!r} (the password and glucose data would cross the network unencrypted)"
            )
        self.host = host
        self.port = port
        self.client_id = client_id
        self._username = username
        self._password = password
        self._tls = tls
        self._timeout = timeout
        self._opener = opener or _tcp
        self._sock: socket.socket | None = None

    @property
    def connected(self) -> bool:
        """True while a connection is open."""
        return self._sock is not None

    def _redact(self, text: str) -> str:
        return text.replace(self._password, "***") if self._password else text

    def connect(self, keepalive: int, will: Will | None = None) -> None:
        """Open the connection and wait for the broker to accept it."""
        self.close()
        packet = connect_packet(self.client_id, keepalive, will, self._username, self._password)
        try:
            sock = self._opener(self.host, self.port, self._timeout)
            if self._tls:
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=self.host)
            sock.settimeout(self._timeout)
            self._sock = sock
            sock.sendall(packet)
            check_connack(self._read_exactly(sock, 4))
        except MqttError:
            self.close()
            raise
        except (OSError, ssl.SSLError) as exc:
            self.close()
            raise MqttError(self._redact(f"could not reach MQTT broker: {exc}")) from None

    def _read_exactly(self, sock: socket.socket, count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            if not chunk:
                raise MqttError("broker closed the connection")
            data += chunk
        return data

    def publish(self, topic: str, payload: bytes, retain: bool = False) -> None:
        """Send one QoS 0 message. Raises MqttError, and closes, on failure."""
        if self._sock is None:
            raise MqttError("not connected")
        packet = publish_packet(topic, payload, retain)
        try:
            self._sock.sendall(packet)
        except OSError as exc:
            self.close()
            raise MqttError(self._redact(f"publish failed: {exc}")) from None

    def disconnect(self) -> None:
        """Say goodbye cleanly (the broker drops the will), then close."""
        if self._sock is not None:
            try:
                self._sock.sendall(disconnect_packet())
            except OSError:
                pass
        self.close()

    def close(self) -> None:
        """Drop the connection without DISCONNECT (the broker sends the will)."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
