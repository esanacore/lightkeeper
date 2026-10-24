"""FR-009: the Python implementation passes every shared golden vector.

The same vectors run against the ESP32 firmware rules (firmware/xteink),
so both implementations must agree, line for line.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from lightkeeper.application.monitor import render_lines
from lightkeeper.domain.glucose import parse_entries
from lightkeeper.domain.status import Thresholds, classify
from tests.helpers import NOW

SPEC = json.loads((Path(__file__).parent.parent / "spec" / "display_vectors.json").read_text())
VECTORS = SPEC["cases"]

# Bump this (and the firmware and Swift copies) when an existing vector changes.
EXPECTED_SPEC_VERSION = 1


def age(item):
    """Return an entry's age from `minutes_ago` or `seconds_ago` (exactly one is given)."""
    if "seconds_ago" in item:
        return timedelta(seconds=item["seconds_ago"])
    return timedelta(minutes=item["minutes_ago"])


def raw_entries(case):
    """Every raw entry in the case, dated relative to NOW."""
    items = case["entries"] if "entries" in case else [case]
    raws = []
    for item in items:
        if item["entry"] is not None:
            raw = dict(item["entry"])
            raw["date"] = int((NOW - age(item)).timestamp() * 1000)
            raws.append(raw)
    return raws


def thresholds(case):
    custom = case.get("thresholds")
    if custom is None:
        return Thresholds()
    return Thresholds(
        urgent_low=custom["urgent_low"],
        low=custom["low"],
        high=custom["high"],
        urgent_high=custom["urgent_high"],
        stale_after=timedelta(minutes=custom["stale_after_minutes"]),
    )


def run_case(case):
    readings = parse_entries(raw_entries(case))
    status = classify(readings[0] if readings else None, NOW, thresholds(case))
    return status.level.value, render_lines(status, case["error"])


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr009_python_matches_shared_vectors(case):
    level, lines = run_case(case)
    assert level == case["level"]
    assert lines == case["lines"]


def test_fr009_vector_names_are_unique():
    names = [c["name"] for c in VECTORS]
    assert len(names) == len(set(names))


def test_fr009_every_case_has_one_entry_form_and_one_age():
    """A malformed case would otherwise run with a silent default."""
    for case in VECTORS:
        assert ("entry" in case) != ("entries" in case), case["name"]
        items = case["entries"] if "entries" in case else [case]
        for item in items:
            assert ("minutes_ago" in item) != ("seconds_ago" in item), case["name"]
        if "thresholds" in case:
            assert set(case["thresholds"]) == {
                "urgent_low",
                "low",
                "high",
                "urgent_high",
                "stale_after_minutes",
            }, case["name"]


def test_fr009_spec_version_is_the_one_this_suite_was_written_for():
    """Every implementation asserts the spec version it was built against.

    A changed vector is then a deliberate, visible event in all three suites.
    """
    assert SPEC["spec_version"] == EXPECTED_SPEC_VERSION
