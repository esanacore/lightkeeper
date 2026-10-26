"""FR-008 / HAZ-013: Home Assistant over MQTT discovery (ADR-0010), against a fake broker."""

import json
from datetime import timedelta

import pytest

from lightkeeper.application.status_payload import status_payload
from lightkeeper.domain.glucose import parse_entry
from lightkeeper.domain.status import Level, Thresholds, classify
from lightkeeper.infrastructure.home_assistant import (
    HomeAssistantPublisher,
    expire_after_seconds,
    keepalive_seconds,
)
from lightkeeper.infrastructure.mqtt import MqttError, MqttPublisher
from tests.fake_broker import FakeBroker
from tests.helpers import NOW, entry


@pytest.fixture
def broker():
    b = FakeBroker()
    yield b
    b.close()


def publisher(broker, **kwargs):
    mqtt = MqttPublisher("127.0.0.1", broker.port, "lightkeeper-test", tls=False, timeout=3)
    args = {"interval_seconds": 60, "stale_seconds": 900, **kwargs}
    return HomeAssistantPublisher(mqtt, **args)


def payload_for(mgdl=112, minutes_ago=3, error=None):
    status = classify(parse_entry(entry(mgdl, minutes_ago)), NOW, Thresholds())
    return status_payload(status, error, NOW)


# --- the payload -------------------------------------------------------------


def test_fr008_payload_for_a_fresh_reading():
    payload = payload_for()
    assert payload == {
        "version": 1,
        "level": "IN RANGE",
        "mgdl": 112,
        "last_mgdl": 112,
        "trend": "Flat",
        "age_minutes": 3,
        "needs_attention": False,
        "error": None,
        "lines": ["IN RANGE", "112 mg/dL ->", "3 min ago"],
        "generated_at": "2026-10-18T12:00:00+00:00",
    }
    json.dumps(payload)  # JSON-safe


def test_haz013_stale_reading_publishes_no_number():
    payload = payload_for(mgdl=45, minutes_ago=40)
    assert payload["level"] == "STALE"
    assert payload["mgdl"] is None
    assert payload["last_mgdl"] == 45
    assert payload["needs_attention"] is True


@pytest.mark.parametrize("mgdl", [39, 401])
def test_haz013_sensor_sentinels_publish_no_number(mgdl):
    payload = payload_for(mgdl=mgdl, minutes_ago=0)
    assert payload["mgdl"] is None
    assert payload["last_mgdl"] == mgdl


def test_haz013_no_data_and_fetch_errors_are_published_as_such():
    status = classify(None, NOW, Thresholds())
    payload = status_payload(status, "could not reach Nightscout", NOW)
    assert payload["level"] == "NO DATA"
    assert payload["mgdl"] is None and payload["trend"] is None and payload["age_minutes"] is None
    assert payload["error"] == "could not reach Nightscout"
    assert payload["lines"][-1] == "Nightscout unreachable"


# --- timing ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("interval", "stale", "expected"),
    [(60, 900, 180), (30, 900, 180), (120, 900, 360), (600, 900, 900), (60, 120, 120)],
)
def test_haz013_expire_after_is_short_and_never_beyond_the_stale_limit(interval, stale, expected):
    assert expire_after_seconds(interval, stale) == expected


@pytest.mark.parametrize(
    ("interval", "expected"), [(15, 60), (60, 120), (600, 1200), (40_000, 65535)]
)
def test_haz013_keepalive_spans_two_intervals(interval, expected):
    assert keepalive_seconds(interval) == expected


# --- discovery ---------------------------------------------------------------


def test_fr008_three_sensors_share_one_state_topic():
    mqtt = MqttPublisher("127.0.0.1", 1, "x", tls=False)
    ha = HomeAssistantPublisher(mqtt, interval_seconds=60, stale_seconds=900, node_id="bedside")
    configs = dict(ha.discovery_messages())
    assert sorted(configs) == [
        "homeassistant/sensor/bedside/age/config",
        "homeassistant/sensor/bedside/glucose/config",
        "homeassistant/sensor/bedside/level/config",
    ]
    for config in configs.values():
        assert config["state_topic"] == "lightkeeper/bedside/state"
        assert config["json_attributes_topic"] == "lightkeeper/bedside/state"
        assert config["availability_topic"] == "lightkeeper/bedside/availability"
        assert config["expire_after"] == 180
        assert config["device"]["identifiers"] == ["bedside"]
    level = configs["homeassistant/sensor/bedside/level/config"]
    glucose = configs["homeassistant/sensor/bedside/glucose/config"]
    assert level["value_template"] == "{{ value_json.level }}"
    assert level["unique_id"] == "bedside_level"
    assert glucose["unit_of_measurement"] == "mg/dL"
    assert glucose["value_template"] == "{{ value_json.mgdl }}"


@pytest.mark.parametrize(
    "kwargs", [{"node_id": "bed side"}, {"node_id": "a/b"}, {"discovery_prefix": "home#"}]
)
def test_fr008_unsafe_ids_are_rejected(kwargs):
    mqtt = MqttPublisher("127.0.0.1", 1, "x", tls=False)
    with pytest.raises(ValueError):
        HomeAssistantPublisher(mqtt, interval_seconds=60, stale_seconds=900, **kwargs)


# --- against the fake broker -------------------------------------------------


def test_haz013_first_publish_sets_will_discovery_availability_then_unretained_state(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    packets = broker.wait_for(6)
    connect, *publishes = packets
    assert connect["type"] == "CONNECT"
    assert connect["will"] == ("lightkeeper/lightkeeper/availability", b"offline", True)
    assert connect["keepalive"] == 120
    topics = [(p["topic"], p["retain"]) for p in publishes]
    assert topics == [
        ("homeassistant/sensor/lightkeeper/level/config", True),
        ("homeassistant/sensor/lightkeeper/glucose/config", True),
        ("homeassistant/sensor/lightkeeper/age/config", True),
        ("lightkeeper/lightkeeper/availability", True),
        ("lightkeeper/lightkeeper/state", False),
    ]
    assert publishes[3]["payload"] == b"online"
    assert json.loads(publishes[4]["payload"])["level"] == "IN RANGE"


def test_haz013_later_publishes_send_only_state_never_retained(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    ha.publish(payload_for(mgdl=68, minutes_ago=1))
    packets = broker.wait_for(7)
    assert broker.sessions == 1
    last = packets[-1]
    assert last["topic"] == "lightkeeper/lightkeeper/state" and last["retain"] is False
    assert json.loads(last["payload"])["level"] == "LOW"
    assert all(
        not p["retain"] for p in packets if p.get("topic") == "lightkeeper/lightkeeper/state"
    )


def test_haz013_watch_shutdown_marks_offline_then_disconnects(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    ha.finish(offline=True)
    packets = broker.wait_for(8)
    assert packets[-2] == {
        "type": "PUBLISH",
        "topic": "lightkeeper/lightkeeper/availability",
        "payload": b"offline",
        "retain": True,
        "qos": 0,
    }
    assert packets[-1] == {"type": "DISCONNECT"}


def test_haz013_one_shot_run_disconnects_without_marking_offline(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    ha.finish(offline=False)
    packets = broker.wait_for(7)
    assert packets[-1] == {"type": "DISCONNECT"}
    assert not any(p.get("payload") == b"offline" for p in packets if p["type"] == "PUBLISH")


def test_fr008_finish_without_a_connection_does_nothing(broker):
    publisher(broker).finish(offline=True)
    assert broker.packets == []


def test_haz013_reconnects_after_a_failure_and_repeats_discovery(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    ha._mqtt.close()  # the connection dies (the broker would send the will)
    ha.publish(payload_for())
    broker.wait_for(12)
    assert broker.sessions == 2
    connects = [p for p in broker.packets if p["type"] == "CONNECT"]
    assert len(connects) == 2


def test_haz013_refused_broker_raises_for_the_caller_to_log(broker):
    broker.return_code = 4
    with pytest.raises(MqttError, match="bad user name"):
        publisher(broker).publish(payload_for())


def test_haz013_failed_offline_publish_at_shutdown_just_closes():
    class DeadMqtt:
        connected = True
        closed = False

        def publish(self, *args, **kwargs):
            raise MqttError("publish failed")

        def close(self):
            self.closed = True

        def disconnect(self):
            raise AssertionError("must not try DISCONNECT on a dead connection")

    dead = DeadMqtt()
    ha = HomeAssistantPublisher(dead, interval_seconds=60, stale_seconds=900)
    ha.finish(offline=True)
    assert dead.closed


def test_fr008_level_changes_reach_home_assistant(broker):
    """FR-008 acceptance: an automation can trigger on URGENT LOW and on STALE."""
    ha = publisher(broker)
    for mgdl, minutes in [(112, 1), (54, 1), (54, 30)]:
        ha.publish(payload_for(mgdl=mgdl, minutes_ago=minutes))
    states = [
        json.loads(p["payload"])["level"]
        for p in broker.wait_for(8)
        if p.get("topic") == "lightkeeper/lightkeeper/state"
    ]
    assert states == [Level.IN_RANGE.value, Level.URGENT_LOW.value, Level.STALE.value]
    assert timedelta(minutes=30) > Thresholds().stale_after
