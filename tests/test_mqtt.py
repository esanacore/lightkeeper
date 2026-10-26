"""FR-008 / HAZ-013: the standard-library MQTT 3.1.1 publisher (ADR-0010)."""

import socket
import ssl

import pytest

from lightkeeper.infrastructure import mqtt
from lightkeeper.infrastructure.mqtt import MqttError, MqttPublisher, Will
from tests.fake_broker import FakeBroker, decode


@pytest.fixture
def broker():
    b = FakeBroker()
    yield b
    b.close()


def local(broker, **kwargs):
    return MqttPublisher("127.0.0.1", broker.port, "test-client", tls=False, timeout=3, **kwargs)


@pytest.mark.parametrize(
    ("length", "encoded"),
    [
        (0, b"\x00"),
        (127, b"\x7f"),
        (128, b"\x80\x01"),
        (16_383, b"\xff\x7f"),
        (16_384, b"\x80\x80\x01"),
        (2_097_151, b"\xff\xff\x7f"),
        (268_435_455, b"\xff\xff\xff\x7f"),
    ],
)
def test_fr008_remaining_length_matches_the_spec_examples(length, encoded):
    assert mqtt.encode_remaining_length(length) == encoded


@pytest.mark.parametrize("length", [-1, 268_435_456])
def test_fr008_remaining_length_out_of_range_is_rejected(length):
    with pytest.raises(ValueError):
        mqtt.encode_remaining_length(length)


def test_fr008_connect_packet_carries_will_and_credentials():
    packet = mqtt.connect_packet(
        "lk", 120, Will("lightkeeper/lk/availability", b"offline"), "user", "pw"
    )
    first, body = packet[0], packet[2:]
    decoded = decode(first, body)
    assert decoded == {
        "type": "CONNECT",
        "protocol": "MQTT",
        "level": 4,
        "clean": True,
        "keepalive": 120,
        "client_id": "lk",
        "will": ("lightkeeper/lk/availability", b"offline", True),
        "username": "user",
        "password": "pw",
    }


def test_fr008_connect_packet_minimal():
    packet = mqtt.connect_packet("lk", 60)
    assert decode(packet[0], packet[2:]) == {
        "type": "CONNECT",
        "protocol": "MQTT",
        "level": 4,
        "clean": True,
        "keepalive": 60,
        "client_id": "lk",
    }


def test_fr008_unretained_will_clears_the_retain_flag():
    packet = mqtt.connect_packet("lk", 60, Will("t", b"x", retain=False))
    assert decode(packet[0], packet[2:])["will"] == ("t", b"x", False)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"keepalive": 0},
        {"keepalive": 70_000},
        {"keepalive": 60, "password": "pw"},
        {"keepalive": 60, "client_id": "x" * 70_000},
        {"keepalive": 60, "will": Will("t", b"x" * 70_000)},
    ],
)
def test_fr008_connect_packet_rejects_invalid_fields(kwargs):
    args = {"client_id": "lk", **kwargs}
    with pytest.raises(ValueError):
        mqtt.connect_packet(**args)


def test_fr008_publish_packet_qos0_with_and_without_retain():
    plain = mqtt.publish_packet("a/b", b"hello")
    kept = mqtt.publish_packet("a/b", b"hello", retain=True)
    assert decode(plain[0], plain[2:]) == {
        "type": "PUBLISH",
        "topic": "a/b",
        "payload": b"hello",
        "retain": False,
        "qos": 0,
    }
    assert decode(kept[0], kept[2:])["retain"] is True


@pytest.mark.parametrize("topic", ["", "a/+", "a/#", "a\x00b"])
def test_fr008_publish_refuses_wildcards_and_empty_topics(topic):
    with pytest.raises(ValueError):
        mqtt.publish_packet(topic, b"x")


def test_fr008_disconnect_packet():
    assert mqtt.disconnect_packet() == b"\xe0\x00"


@pytest.mark.parametrize(
    ("packet", "message"),
    [
        (b"\x20\x02\x00\x00", None),
        (b"\x20\x02\x00\x05", "not authorized"),
        (b"\x20\x02\x00\x04", "bad user name or password"),
        (b"\x20\x02\x00\x09", "code 9"),
        (b"\x30\x02\x00\x00", "CONNACK"),
        (b"\x20\x02\x00", "CONNACK"),
    ],
)
def test_fr008_connack_is_checked(packet, message):
    if message is None:
        mqtt.check_connack(packet)
    else:
        with pytest.raises(MqttError, match=message):
            mqtt.check_connack(packet)


def test_haz013_plain_mqtt_is_refused_off_localhost():
    with pytest.raises(ValueError, match="localhost"):
        MqttPublisher("broker.example.com", 1883, "lk", tls=False)
    for host in ("localhost", "127.0.0.1", "::1"):
        MqttPublisher(host, 1883, "lk", tls=False)
    with pytest.raises(ValueError):
        MqttPublisher("", 8883, "lk")


def test_fr008_connect_publish_disconnect_against_a_broker(broker):
    client = local(broker, username="u", password="p")
    client.connect(60, Will("lk/availability", b"offline"))
    assert client.connected
    client.publish("lk/state", b'{"level": "IN RANGE"}')
    client.disconnect()
    assert not client.connected
    packets = broker.wait_for(3)
    assert [p["type"] for p in packets] == ["CONNECT", "PUBLISH", "DISCONNECT"]
    assert packets[0]["username"] == "u"
    assert packets[1]["payload"] == b'{"level": "IN RANGE"}'


def test_fr008_refused_connection_raises_and_closes(broker):
    broker.return_code = 5
    client = local(broker)
    with pytest.raises(MqttError, match="not authorized"):
        client.connect(60)
    assert not client.connected


def test_fr008_broker_hanging_up_before_connack_is_an_error(broker):
    broker.connack = b""  # send nothing, then hang up
    client = local(broker)
    with pytest.raises(MqttError, match="closed"):
        client.connect(60)


def test_haz013_unreachable_broker_error_never_contains_the_password():
    def refuse(host, port, timeout):
        raise OSError("connection refused (password was hunter2)")

    client = MqttPublisher(
        "127.0.0.1", 1, "lk", password="hunter2", username="u", tls=False, opener=refuse
    )
    with pytest.raises(MqttError) as caught:
        client.connect(60)
    assert "hunter2" not in str(caught.value)
    assert "***" in str(caught.value)


def test_fr008_publish_without_connection_is_an_error():
    with pytest.raises(MqttError, match="not connected"):
        MqttPublisher("127.0.0.1", 1, "lk", tls=False).publish("t", b"x")


class BrokenSocket:
    def __init__(self, fail_on_send=False, fail_on_close=False):
        self.fail_on_send = fail_on_send
        self.fail_on_close = fail_on_close
        self.sent = b""

    def settimeout(self, timeout):
        pass

    def sendall(self, data):
        if self.fail_on_send and self.sent:
            raise OSError("broken pipe")
        self.sent += data

    def recv(self, count):
        return b"\x20\x02\x00\x00"[:count]

    def close(self):
        if self.fail_on_close:
            raise OSError("already closed")


def test_fr008_failed_publish_closes_so_the_next_cycle_reconnects():
    sock = BrokenSocket(fail_on_send=True)
    client = MqttPublisher("127.0.0.1", 1, "lk", tls=False, opener=lambda h, p, t: sock)
    client.connect(60)
    with pytest.raises(MqttError, match="publish failed"):
        client.publish("t", b"x")
    assert not client.connected


def test_fr008_disconnect_and_close_tolerate_a_dead_socket():
    sock = BrokenSocket(fail_on_send=True, fail_on_close=True)
    client = MqttPublisher("127.0.0.1", 1, "lk", tls=False, opener=lambda h, p, t: sock)
    client.connect(60)
    client.disconnect()  # DISCONNECT send fails, close fails: both swallowed
    assert not client.connected
    client.disconnect()  # already closed: nothing to do


def test_haz013_tls_wraps_the_socket_and_verifies_the_host(monkeypatch):
    seen = {}

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            seen["hostname"] = server_hostname
            return sock

    def fake_default_context():
        seen["verified"] = True
        return FakeContext()

    monkeypatch.setattr(ssl, "create_default_context", fake_default_context)
    client = MqttPublisher("broker.example.com", 8883, "lk", opener=lambda h, p, t: BrokenSocket())
    client.connect(60)
    assert seen == {"verified": True, "hostname": "broker.example.com"}


def test_fr008_default_opener_connects_over_tcp(broker):
    sock = mqtt._tcp("127.0.0.1", broker.port, 3)
    assert isinstance(sock, socket.socket)
    sock.close()
