"""FR-009: the Python implementation passes every shared golden vector.

The same vectors run against the ESP32 firmware rules (firmware/xteink),
so both implementations must agree, line for line.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from lightkeeper.application.monitor import render_lines
from lightkeeper.domain.glucose import InvalidReadingError, parse_entry
from lightkeeper.domain.status import Thresholds, classify
from tests.helpers import NOW

SPEC = json.loads((Path(__file__).parent.parent / "spec" / "display_vectors.json").read_text())
VECTORS = SPEC["cases"]

# Bump this (and the firmware and Swift copies) when an existing vector changes.
EXPECTED_SPEC_VERSION = 1


def run_case(case):
    reading = None
    if case["entry"] is not None:
        raw = dict(case["entry"])
        raw["date"] = int((NOW - timedelta(minutes=case["minutes_ago"])).timestamp() * 1000)
        try:
            reading = parse_entry(raw)
        except InvalidReadingError:
            reading = None
    status = classify(reading, NOW, Thresholds())
    return status.level.value, render_lines(status, case["error"])


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr009_python_matches_shared_vectors(case):
    level, lines = run_case(case)
    assert level == case["level"]
    assert lines == case["lines"]


def test_fr009_vector_names_are_unique():
    names = [c["name"] for c in VECTORS]
    assert len(names) == len(set(names))


def test_fr009_spec_version_is_the_one_this_suite_was_written_for():
    """Every implementation asserts the spec version it was built against.

    A changed vector is then a deliberate, visible event in all three suites.
    """
    assert SPEC["spec_version"] == EXPECTED_SPEC_VERSION
