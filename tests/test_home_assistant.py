"""FR-008 / HAZ-013: Home Assistant over MQTT discovery (ADR-0010), against a fake broker."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from lightkeeper.application.status_payload import PAYLOAD_VERSION, status_payload
from lightkeeper.domain.glucose import GlucoseReading, Trend, parse_entries, parse_entry
from lightkeeper.domain.status import Level, Status, Thresholds, classify
from lightkeeper.infrastructure.home_assistant import (
    AGE_TEMPLATE,
    HomeAssistantPublisher,
    device_name,
    expire_after_seconds,
    keepalive_seconds,
)
from lightkeeper.infrastructure.mqtt import MqttError, MqttPublisher
from tests.fake_broker import FakeBroker
from tests.helpers import NOW, entry
from tests.test_vectors import VECTORS, raw_entries, thresholds

SENSORS = ["level", "glucose", "age", "last_reading"]
# CONNECT, one retained config per sensor, then the retained availability flag.
SETUP_PACKETS = 1 + len(SENSORS) + 1
PAYLOAD_KEYS = {
    "version",
    "level",
    "mgdl",
    "last_mgdl",
    "trend",
    "age_minutes",
    "reading_at",
    "needs_attention",
    "error",
    "lines",
    "generated_at",
}


@pytest.fixture
def broker():
    b = FakeBroker()
    yield b
    b.close()


def publisher(broker, **kwargs):
    mqtt = MqttPublisher("127.0.0.1", broker.port, "lightkeeper-test", tls=False, timeout=3)
    args = {"interval_seconds": 60, "stale_seconds": 900, **kwargs}
    return HomeAssistantPublisher(mqtt, **args)


def offline_publisher(**kwargs):
    """Return a publisher that is never connected, for reading its discovery configs."""
    mqtt = MqttPublisher("127.0.0.1", 1, "x", tls=False)
    return HomeAssistantPublisher(mqtt, interval_seconds=60, stale_seconds=900, **kwargs)


def configs_by_key(ha):
    """{sensor key: discovery config}, keyed by the topic's sensor segment."""
    return {topic.split("/")[-2]: config for topic, config in ha.discovery_messages()}


def payload_for(mgdl=112, minutes_ago=3, error=None):
    status = classify(parse_entry(entry(mgdl, minutes_ago)), NOW, Thresholds())
    return status_payload(status, error, NOW)


def vector_payload(case):
    """Return (status, payload) for a vector, classified as tests/test_vectors.py does."""
    readings = parse_entries(raw_entries(case))
    status = classify(readings[0] if readings else None, NOW, thresholds(case))
    return status, status_payload(status, case["error"], NOW)


# --- the payload -------------------------------------------------------------


def test_fr008_payload_for_a_fresh_reading():
    payload = payload_for()
    assert payload == {
        "version": 2,
        "level": "IN RANGE",
        "mgdl": 112,
        "last_mgdl": 112,
        "trend": "Flat",
        "age_minutes": 3,
        "reading_at": "2026-10-18T11:57:00+00:00",
        "needs_attention": False,
        "error": None,
        "lines": ["IN RANGE", "112 mg/dL ->", "3 min ago"],
        "generated_at": "2026-10-18T12:00:00+00:00",
    }
    json.dumps(payload)  # JSON-safe


def test_fr008_payload_version_is_2():
    """D14: `age_minutes` changed meaning (None, not negative, for a future date)."""
    assert PAYLOAD_VERSION == 2
    assert payload_for()["version"] == 2
    assert status_payload(classify(None, NOW, Thresholds()), None, NOW)["version"] == 2


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_haz013_future_dated_age_is_none_never_negative(case):
    status, payload = vector_payload(case)
    assert payload["lines"] == case["lines"]
    assert payload["level"] == case["level"]
    age = payload["age_minutes"]
    assert age is None or (isinstance(age, int) and age >= 0)
    if status.age is not None and status.age < timedelta(0):
        assert age is None  # dated in the future: no age to count
    elif status.age is not None:
        assert age == status.age_minutes
    # The number only for a fresh, measured reading.
    sentinel = status.reading is not None and (
        status.reading.is_sensor_low_sentinel or status.reading.is_sensor_high_sentinel
    )
    if case["level"] in ("STALE", "NO DATA") or sentinel:
        assert payload["mgdl"] is None
    else:
        assert payload["mgdl"] == status.reading.mgdl
    # The reading's time exactly when there is a reading, in UTC.
    assert (payload["reading_at"] is None) == (status.reading is None)
    if status.reading is not None:
        when = datetime.fromisoformat(payload["reading_at"])
        assert when.utcoffset() == timedelta(0)
        assert when == status.reading.timestamp.replace(microsecond=0)
    # Exactly these fields: no spoken sentence, so no audio path is invited.
    assert set(payload) == PAYLOAD_KEYS
    json.dumps(payload)


def test_haz013_future_dated_vectors_publish_stale_with_no_age():
    """The vectors that are dated past the clock-skew allowance, by name."""
    for name in ("future_dated", "future_skew_2_minutes_1_second_stale"):
        (case,) = [c for c in VECTORS if c["name"] == name]
        status, payload = vector_payload(case)
        assert status.age_minutes is not None and status.age_minutes < 0
        assert payload["level"] == "STALE"
        assert payload["age_minutes"] is None
        assert payload["mgdl"] is None
        assert payload["last_mgdl"] == status.reading.mgdl
        assert payload["reading_at"] > payload["generated_at"]  # the future, said honestly


def test_haz013_negative_age_is_never_published_even_from_a_hand_built_status():
    reading = GlucoseReading(mgdl=120, timestamp=NOW + timedelta(seconds=1), trend=Trend.FLAT)
    status = Status(level=Level.STALE, reading=reading, age=timedelta(seconds=-1))
    assert status.age_minutes == -1
    assert status_payload(status, None, NOW)["age_minutes"] is None


def test_fr008_reading_at_drops_a_fraction_so_it_never_looks_newer():
    when = datetime(2026, 10, 18, 11, 57, 30, 999_000, tzinfo=UTC)
    reading = GlucoseReading(mgdl=120, timestamp=when, trend=Trend.FLAT)
    status = Status(level=Level.IN_RANGE, reading=reading, age=NOW - when)
    assert status_payload(status, None, NOW)["reading_at"] == "2026-10-18T11:57:30+00:00"


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


def test_fr008_four_sensors_share_one_state_topic():
    ha = offline_publisher(node_id="bedside")
    configs = dict(ha.discovery_messages())
    assert sorted(configs) == [
        "homeassistant/sensor/bedside/age/config",
        "homeassistant/sensor/bedside/glucose/config",
        "homeassistant/sensor/bedside/last_reading/config",
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
    ("node_id", "name"),
    [
        ("lightkeeper", "Lightkeeper"),
        ("bedside", "Lightkeeper (bedside)"),
        ("Lightkeeper", "Lightkeeper (Lightkeeper)"),
        ("kitchen-2", "Lightkeeper (kitchen-2)"),
    ],
)
def test_fr008_device_name_includes_node_id_and_unique_ids_unchanged(node_id, name):
    assert device_name(node_id) == name
    ha = offline_publisher(node_id=node_id)
    assert ha.node_id == node_id
    for key, config in configs_by_key(ha).items():
        assert config["device"]["name"] == name
        # Keyed by the node id alone, exactly as before the device was renamed,
        # so Home Assistant keeps every existing entity id.
        assert config["device"]["identifiers"] == [node_id]
        assert config["unique_id"] == f"{node_id}_{key}"
    assert sorted(configs_by_key(ha)) == sorted(SENSORS)


def test_fr008_default_publisher_keeps_the_plain_device_name():
    configs = configs_by_key(offline_publisher())
    assert {c["device"]["name"] for c in configs.values()} == {"Lightkeeper"}
    assert {c["unique_id"] for c in configs.values()} == {
        "lightkeeper_level",
        "lightkeeper_glucose",
        "lightkeeper_age",
        "lightkeeper_last_reading",
    }


def test_fr008_level_sensor_is_enum_with_seven_options():
    level = configs_by_key(offline_publisher())["level"]
    assert level["device_class"] == "enum"
    assert level["options"] == [
        "NO DATA",
        "STALE",
        "URGENT LOW",
        "LOW",
        "IN RANGE",
        "HIGH",
        "URGENT HIGH",
    ]
    # Exactly the levels the displays can publish: none missing, none extra.
    assert sorted(level["options"]) == sorted(lv.value for lv in Level)
    assert len(set(level["options"])) == 7
    # Home Assistant refuses a unit or state class on an enum sensor.
    assert "unit_of_measurement" not in level and "state_class" not in level
    # Every level a vector publishes is one of the options.
    assert {vector_payload(c)[1]["level"] for c in VECTORS} <= set(level["options"])


def test_fr008_last_reading_timestamp_sensor_shares_availability_and_expiry():
    configs = configs_by_key(offline_publisher(node_id="bedside"))
    last = configs["last_reading"]
    assert last["name"] == "Last reading"
    assert last["device_class"] == "timestamp"
    assert last["value_template"] == "{{ value_json.reading_at }}"
    assert last["unique_id"] == "bedside_last_reading"
    assert "unit_of_measurement" not in last and "state_class" not in last
    shared = [
        "state_topic",
        "json_attributes_topic",
        "availability_topic",
        "payload_available",
        "payload_not_available",
        "expire_after",
        "device",
    ]
    for key in shared:
        assert last[key] == configs["level"][key], key
    assert last["availability_topic"] == "lightkeeper/bedside/availability"
    assert last["expire_after"] == 180


def test_haz013_age_template_publishes_unknown_never_a_negative_age():
    """The guard behind the payload's own: a negative or missing age renders `none`.

    Home Assistant renders the template with Jinja, which the stdlib-only
    runtime does not have, so its exact text is pinned here; Home Assistant
    shows a sensor whose template renders None as unknown. Checking it in a
    real Home Assistant stays with GAP-002.
    """
    age = configs_by_key(offline_publisher())["age"]
    assert age["value_template"] == AGE_TEMPLATE
    assert AGE_TEMPLATE == (
        "{{ value_json.age_minutes if value_json.age_minutes is number"
        " and value_json.age_minutes >= 0 else none }}"
    )
    assert age["unit_of_measurement"] == "min"


def test_fr008_no_sensor_carries_spoken_text():
    """The spoken sentences are for screen readers; Home Assistant gets none."""
    configs = configs_by_key(offline_publisher())
    assert sorted(configs) == sorted(SENSORS)
    assert "spoken" not in json.dumps(configs)
    assert "spoken" not in json.dumps(payload_for())


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
    packets = broker.wait_for(SETUP_PACKETS + 1)
    connect, *publishes = packets
    assert connect["type"] == "CONNECT"
    assert connect["will"] == ("lightkeeper/lightkeeper/availability", b"offline", True)
    assert connect["keepalive"] == 120
    topics = [(p["topic"], p["retain"]) for p in publishes]
    assert topics == [
        ("homeassistant/sensor/lightkeeper/level/config", True),
        ("homeassistant/sensor/lightkeeper/glucose/config", True),
        ("homeassistant/sensor/lightkeeper/age/config", True),
        ("homeassistant/sensor/lightkeeper/last_reading/config", True),
        ("lightkeeper/lightkeeper/availability", True),
        ("lightkeeper/lightkeeper/state", False),
    ]
    assert publishes[4]["payload"] == b"online"
    state = json.loads(publishes[5]["payload"])
    assert state["level"] == "IN RANGE"
    assert state["reading_at"] == "2026-10-18T11:57:00+00:00"


def test_fr008_discovery_over_the_wire_names_the_device_and_types_the_sensors(broker):
    """FR-008 acceptance with the fake broker: device name, enum level, timestamp sensor."""
    ha = publisher(broker, node_id="bedside")
    ha.publish(payload_for())
    packets = broker.wait_for(SETUP_PACKETS + 1)
    configs = {
        p["topic"].split("/")[-2]: json.loads(p["payload"])
        for p in packets
        if p["type"] == "PUBLISH" and p["topic"].endswith("/config")
    }
    assert sorted(configs) == sorted(SENSORS)
    assert {c["device"]["name"] for c in configs.values()} == {"Lightkeeper (bedside)"}
    assert {c["device"]["identifiers"][0] for c in configs.values()} == {"bedside"}
    assert configs["level"]["device_class"] == "enum"
    assert configs["level"]["options"] == [lv.value for lv in Level]
    assert configs["last_reading"]["device_class"] == "timestamp"
    assert configs["last_reading"]["expire_after"] == configs["level"]["expire_after"] == 180


def test_haz013_later_publishes_send_only_state_never_retained(broker):
    ha = publisher(broker)
    ha.publish(payload_for())
    ha.publish(payload_for(mgdl=68, minutes_ago=1))
    packets = broker.wait_for(SETUP_PACKETS + 2)
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
    packets = broker.wait_for(SETUP_PACKETS + 3)
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
    packets = broker.wait_for(SETUP_PACKETS + 2)
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
    broker.wait_for(2 * (SETUP_PACKETS + 1))
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
        for p in broker.wait_for(SETUP_PACKETS + 3)
        if p.get("topic") == "lightkeeper/lightkeeper/state"
    ]
    assert states == [Level.IN_RANGE.value, Level.URGENT_LOW.value, Level.STALE.value]
    assert timedelta(minutes=30) > Thresholds().stale_after
