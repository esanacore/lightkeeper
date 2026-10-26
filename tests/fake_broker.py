"""A tiny fake MQTT broker on localhost for tests (GAP-002).

Accepts connections, answers CONNECT with a CONNACK whose return code the
test chooses, and records every packet as a decoded dict. It understands just
enough MQTT 3.1.1 to check what the publisher sends.
"""

from __future__ import annotations

import socket
import struct
import threading


def _read_exactly(conn, count):
    data = b""
    while len(data) < count:
        chunk = conn.recv(count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def read_packet(conn):
    """Return (first_byte, body) for one packet, or None at end of stream."""
    head = _read_exactly(conn, 1)
    if head is None:
        return None
    multiplier, length = 1, 0
    while True:
        byte = _read_exactly(conn, 1)
        if byte is None:
            return None
        length += (byte[0] & 0x7F) * multiplier
        if not byte[0] & 0x80:
            break
        multiplier *= 128
    body = _read_exactly(conn, length) if length else b""
    return head[0], body


def _take_string(data, offset):
    (size,) = struct.unpack(">H", data[offset : offset + 2])
    return data[offset + 2 : offset + 2 + size], offset + 2 + size


def decode(first, body):
    """Decode the packets the publisher may send into plain dicts."""
    kind = first >> 4
    if kind == 1:  # CONNECT
        protocol, offset = _take_string(body, 0)
        level, flags = body[offset], body[offset + 1]
        (keepalive,) = struct.unpack(">H", body[offset + 2 : offset + 4])
        offset += 4
        client_id, offset = _take_string(body, offset)
        packet = {
            "type": "CONNECT",
            "protocol": protocol.decode(),
            "level": level,
            "clean": bool(flags & 0x02),
            "keepalive": keepalive,
            "client_id": client_id.decode(),
        }
        if flags & 0x04:
            topic, offset = _take_string(body, offset)
            payload, offset = _take_string(body, offset)
            packet["will"] = (topic.decode(), payload, bool(flags & 0x20))
        if flags & 0x80:
            user, offset = _take_string(body, offset)
            packet["username"] = user.decode()
        if flags & 0x40:
            password, offset = _take_string(body, offset)
            packet["password"] = password.decode()
        return packet
    if kind == 3:  # PUBLISH, QoS 0
        topic, offset = _take_string(body, 0)
        return {
            "type": "PUBLISH",
            "topic": topic.decode(),
            "payload": body[offset:],
            "retain": bool(first & 0x01),
            "qos": (first >> 1) & 0x03,
        }
    if kind == 14:
        return {"type": "DISCONNECT"}
    return {"type": f"UNKNOWN-{kind}"}


class FakeBroker:
    """Serves on 127.0.0.1; `packets` collects decoded packets from all sessions."""

    def __init__(self, return_code=0, connack=None):
        self.return_code = return_code
        self.connack = connack  # raw bytes to send instead, if set
        self.packets = []
        self.sessions = 0
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen()
        self.port = self._server.getsockname()[1]
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            self.sessions += 1
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        with conn:
            while True:
                packet = read_packet(conn)
                if packet is None:
                    return
                decoded = decode(*packet)
                self.packets.append(decoded)
                if decoded["type"] == "CONNECT":
                    if self.connack is not None:
                        conn.sendall(self.connack)
                        return
                    conn.sendall(bytes([0x20, 2, 0, self.return_code]))
                    if self.return_code:
                        return
                if decoded["type"] == "DISCONNECT":
                    return

    def wait_for(self, count, timeout=5.0):
        """Block until at least `count` packets arrived (or time out)."""
        import time

        deadline = time.monotonic() + timeout
        while len(self.packets) < count and time.monotonic() < deadline:
            time.sleep(0.01)
        return self.packets

    def close(self):
        self._stop = True
        self._server.close()
