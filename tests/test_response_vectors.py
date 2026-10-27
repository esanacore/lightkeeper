"""FR-001 / FR-005: raw Nightscout responses lead to the same conclusion everywhere.

spec/response_vectors.json holds response bodies as sent over the wire. Python
must reach exactly the expected conclusion with the client's own parsing path
(json.loads, then parse_entries); the firmware's heap-free parser and the
Swift package run the same file.
"""

import json
from pathlib import Path

import pytest

from lightkeeper.domain.glucose import parse_entries

SPEC = json.loads(
    (Path(__file__).parent.parent / "spec" / "response_vectors.json").read_text(encoding="utf-8")
)
CASES = SPEC["cases"]

# Bump this (and the firmware and Swift copies) when an existing case changes.
EXPECTED_SPEC_VERSION = 1


def conclude(body: str):
    """Return what the Python client concludes from one response body."""
    try:
        data = json.loads(body)
    except ValueError:
        return "error"
    if not isinstance(data, list):
        return "error"
    readings = parse_entries(data)
    if not readings:
        return None
    newest = readings[0]
    return {
        "mgdl": newest.mgdl,
        "date": int(newest.timestamp.timestamp() * 1000),
        "trend": newest.trend.value,
    }


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fr001_python_concludes_what_the_response_vectors_expect(case):
    assert conclude(case["body"]) == case["expect"]


def test_fr001_response_vector_names_are_unique():
    names = [c["name"] for c in CASES]
    assert len(names) == len(set(names))


def test_fr001_response_spec_version_is_the_one_this_suite_was_written_for():
    assert SPEC["spec_version"] == EXPECTED_SPEC_VERSION


def test_fr001_swift_allowances_are_noted_and_safe():
    """Where Foundation's JSON parser may differ, only safe outcomes are allowed.

    Safe means a whole-response error (the display ages its last good reading)
    or a reading that parse_entries itself accepted from the body.
    """
    for case in CASES:
        allowed = case.get("swift_also_accepts")
        if allowed is None:
            continue
        assert case.get("swift_note"), case["name"]
        for outcome in allowed:
            if outcome == "error":
                continue
            assert set(outcome) == {"mgdl", "date", "trend"}, case["name"]
            assert str(outcome["mgdl"]) in case["body"], case["name"]
