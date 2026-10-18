"""FR-001: parsing Nightscout entries into trusted readings."""

import pytest

from glucose_watch.domain.glucose import (
    InvalidReadingError,
    Trend,
    parse_entries,
    parse_entry,
)
from tests.helpers import NOW, entry


def test_fr001_parses_valid_entry():
    reading = parse_entry(entry(mgdl=134, direction="FortyFiveUp"))
    assert reading.mgdl == 134
    assert reading.trend is Trend.FORTY_FIVE_UP
    assert reading.timestamp == NOW
    assert reading.timestamp.tzinfo is not None


@pytest.mark.parametrize("mgdl", [39, 40, 400, 401])
def test_fr001_accepts_sensor_range_and_sentinels(mgdl):
    assert parse_entry(entry(mgdl=mgdl)).mgdl == mgdl


def test_fr001_sentinel_flags():
    assert parse_entry(entry(mgdl=39)).is_sensor_low_sentinel
    assert parse_entry(entry(mgdl=401)).is_sensor_high_sentinel
    middle = parse_entry(entry(mgdl=120))
    assert not middle.is_sensor_low_sentinel and not middle.is_sensor_high_sentinel


@pytest.mark.parametrize(
    "bad",
    [
        "not a dict",
        entry(mgdl=38),
        entry(mgdl=402),
        entry(mgdl=None),
        entry(mgdl="120"),
        entry(mgdl=True),
        entry(mgdl=120.5),
        entry(type="mbg"),
        {"type": "sgv", "sgv": 120},
        entry(date=0),
        entry(date="yesterday"),
        entry(date=False),
    ],
)
def test_fr001_rejects_untrustworthy_entries(bad):
    with pytest.raises(InvalidReadingError):
        parse_entry(bad)


def test_fr001_unknown_direction_keeps_number():
    reading = parse_entry(entry(mgdl=150, direction="SomethingNew"))
    assert reading.mgdl == 150
    assert reading.trend is Trend.UNKNOWN


def test_fr001_missing_direction_is_unknown():
    raw = entry()
    del raw["direction"]
    assert parse_entry(raw).trend is Trend.UNKNOWN


def test_fr001_whole_float_value_is_accepted():
    assert parse_entry(entry(mgdl=120.0)).mgdl == 120


def test_fr001_parse_entries_skips_bad_and_sorts_newest_first():
    readings = parse_entries([entry(100, 10), entry(mgdl=999), entry(110, 0), "junk", entry(105, 5)])
    assert [r.mgdl for r in readings] == [110, 105, 100]


def test_fr001_parse_entries_handles_empty_and_none():
    assert parse_entries([]) == []
    assert parse_entries(None) == []


def test_fr004_every_trend_has_a_plain_ascii_arrow():
    for trend in Trend:
        assert trend.arrow and trend.arrow.isascii()
