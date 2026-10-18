"""FR-002, FR-003, NFR-002: status classification and the staleness rule."""

from datetime import timedelta

import pytest

from lightkeeper.domain.glucose import parse_entry
from lightkeeper.domain.status import Level, Thresholds, classify
from tests.helpers import NOW, entry

DEFAULTS = Thresholds()


def status_for(mgdl, minutes_ago=0, thresholds=DEFAULTS):
    return classify(parse_entry(entry(mgdl=mgdl, minutes_ago=minutes_ago)), NOW, thresholds)


@pytest.mark.parametrize(
    "mgdl, expected",
    [
        (39, Level.URGENT_LOW),
        (55, Level.URGENT_LOW),
        (56, Level.LOW),
        (69, Level.LOW),
        (70, Level.IN_RANGE),
        (120, Level.IN_RANGE),
        (180, Level.IN_RANGE),
        (181, Level.HIGH),
        (249, Level.HIGH),
        (250, Level.URGENT_HIGH),
        (401, Level.URGENT_HIGH),
    ],
)
def test_fr002_threshold_boundaries(mgdl, expected):
    assert status_for(mgdl).level is expected


def test_fr002_custom_thresholds_apply():
    custom = Thresholds(urgent_low=60, low=80, high=160, urgent_high=220)
    assert status_for(75, thresholds=custom).level is Level.LOW
    assert status_for(165, thresholds=custom).level is Level.HIGH


def test_fr002_only_in_range_is_quiet():
    assert not Level.IN_RANGE.needs_attention
    for level in Level:
        if level is not Level.IN_RANGE:
            assert level.needs_attention


def test_fr003_no_reading_is_no_data():
    status = classify(None, NOW, DEFAULTS)
    assert status.level is Level.NO_DATA
    assert status.age_minutes is None


def test_fr003_fresh_reading_is_trusted_at_limit():
    assert status_for(120, minutes_ago=15).level is Level.IN_RANGE


def test_fr003_old_in_range_reading_is_stale_not_in_range():
    status = status_for(120, minutes_ago=16)
    assert status.level is Level.STALE
    assert status.age_minutes == 16


def test_fr003_staleness_beats_urgent_low():
    # Even an alarming number must not be shown as current when it is old.
    assert status_for(45, minutes_ago=40).level is Level.STALE


def test_fr003_future_dated_reading_is_stale():
    status = status_for(120, minutes_ago=-10)
    assert status.level is Level.STALE
    assert status.age_minutes < 0


def test_fr003_small_clock_skew_is_tolerated():
    status = status_for(120, minutes_ago=-1)
    assert status.level is Level.IN_RANGE
    assert status.age_minutes == 0


def test_fr003_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        classify(None, NOW.replace(tzinfo=None), DEFAULTS)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"urgent_low": 70, "low": 70},
        {"low": 200, "high": 180},
        {"high": 260, "urgent_high": 250},
        {"urgent_low": 30},
        {"urgent_high": 450},
        {"stale_after": timedelta(0)},
    ],
)
def test_nfr002_invalid_thresholds_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Thresholds(**kwargs)
