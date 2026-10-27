"""Build spec/response_vectors.json, the shared raw-response corpus.

Edit the cases here and rerun from the repository root:
    python tools/gen_response_corpus.py
Python, the firmware, and Swift all run the file it writes.
"""

# A data table of raw JSON bodies: long lines are the bodies themselves, and %
# formatting keeps their braces literal where f-strings would double every one.
# ruff: noqa: E501, UP031

import json

T0 = 1792324800000  # 2026-10-18T12:00:00Z
M = 60_000


def e(sgv=120, minutes=0, direction="Flat", **extra):
    """Build one Nightscout entry `minutes` before T0, with any extra fields."""
    d = {"type": "sgv", "sgv": sgv, "date": T0 - minutes * M, "direction": direction}
    d.update(extra)
    return d


def body(obj):
    """Serialize `obj` the way a server would."""
    return json.dumps(obj)


def reading(mgdl, minutes, trend="Flat"):
    """Expect this reading to be the newest trustworthy one."""
    return {"mgdl": mgdl, "date": T0 - minutes * M, "trend": trend}


cases = [
    # Shapes Nightscout really sends.
    (
        "typical_newest_first",
        body(
            [
                {
                    "_id": "6510a1",
                    "device": "Trio",
                    "date": T0,
                    "dateString": "2026-10-18T12:00:00.000Z",
                    "sgv": 112,
                    "delta": -1.5,
                    "direction": "Flat",
                    "type": "sgv",
                    "filtered": 0,
                    "unfiltered": 0,
                    "rssi": 100,
                    "noise": 1,
                    "sysTime": "2026-10-18T12:00:00.000Z",
                    "utcOffset": 0,
                },
                e(114, 5),
            ]
        ),
        reading(112, 0),
    ),
    (
        "oldest_first",
        body([e(100, 10), e(105, 5), e(110, 0, "FortyFiveUp")]),
        reading(110, 0, "FortyFiveUp"),
    ),
    ("empty_list", "[]", None),
    (
        "whitespace_everywhere",
        '\n[\n\t{ "sgv" : 98 ,\r\n "date" : %d , "direction" : "SingleDown" , "type" : "sgv" }\n]\n'
        % T0,
        reading(98, 0, "SingleDown"),
    ),
    (
        "unknown_nested_fields",
        body(
            [
                e(
                    121,
                    1,
                    meta={
                        "a": [1, {"b": [2, 3.5e1, None, True, False]}],
                        "c": None,
                        "q": 'x"y\\z',
                    },
                    tags=[],
                    empty={},
                )
            ]
        ),
        reading(121, 1),
    ),
    (
        "unicode_in_unknown_field",
        '[{"device": "xDrip-\\u00e9 café", "sgv": 130, "date": %d, "direction": "Flat", "type": "sgv"}]'
        % T0,
        reading(130, 0),
    ),
    (
        "escaped_direction",
        '[{"sgv": 125, "date": %d, "direction": "Fla\\u0074", "type": "sgv"}]' % T0,
        reading(125, 0),
    ),
    (
        "escaped_slash_and_controls_in_unknown",
        '[{"note": "a\\/b\\n\\t\\r\\b\\f", "sgv": 101, "date": %d, "type": "sgv", "direction": "Flat"}]'
        % T0,
        reading(101, 0),
    ),
    # Field-level rejection, mirroring parse_entry.
    (
        "type_missing_is_sgv",
        body([{"sgv": 140, "date": T0, "direction": "Flat"}]),
        reading(140, 0),
    ),
    ("type_mbg_skipped", body([e(80, 0, type="mbg"), e(115, 5)]), reading(115, 5)),
    ("type_not_a_string_skipped", body([e(80, 0, type=5), e(116, 5)]), reading(116, 5)),
    ("sgv_true_skipped", body([e(True, 0), e(117, 5)]), reading(117, 5)),
    ("sgv_null_skipped", body([e(None, 0), e(118, 5)]), reading(118, 5)),
    ("sgv_string_skipped", body([e("120", 0), e(119, 5)]), reading(119, 5)),
    (
        "sgv_whole_float_accepted",
        '[{"sgv": 120.0, "date": %d, "direction": "Flat", "type": "sgv"}]' % T0,
        reading(120, 0),
    ),
    (
        "sgv_exponent_accepted",
        '[{"sgv": 1.2e2, "date": %d, "direction": "Flat", "type": "sgv"}]' % T0,
        reading(120, 0),
    ),
    (
        "sgv_fraction_skipped",
        '[{"sgv": 120.5, "date": %d, "type": "sgv"}, {"sgv": 99, "date": %d, "type": "sgv", "direction": "Flat"}]'
        % (T0, T0 - 5 * M),
        reading(99, 5),
    ),
    (
        "sgv_overflow_skipped",
        '[{"sgv": 1e400, "date": %d, "type": "sgv"}, {"sgv": 97, "date": %d, "type": "sgv", "direction": "Flat"}]'
        % (T0, T0 - 5 * M),
        reading(97, 5),
    ),
    ("sgv_negative_skipped", body([e(-5, 0), e(96, 5)]), reading(96, 5)),
    ("date_string_skipped", body([e(80, 0, date=str(T0)), e(95, 5)]), reading(95, 5)),
    ("date_in_seconds_skipped", body([e(80, 0, date=T0 // 1000), e(94, 5)]), reading(94, 5)),
    (
        "direction_not_a_string_is_unknown",
        body([e(131, 0, direction=5)]),
        reading(131, 0, "Unknown"),
    ),
    (
        "direction_missing_is_unknown",
        body([{"sgv": 132, "date": T0, "type": "sgv"}]),
        reading(132, 0, "Unknown"),
    ),
    (
        "non_object_elements_skipped",
        '[1, "x", null, true, [], [{"sgv": 50}], {"sgv": 133, "date": %d, "type": "sgv", "direction": "Flat"}]'
        % T0,
        reading(133, 0),
    ),
    ("all_entries_invalid", body([e(402, 0), e(None, 5), e(80, 0, type="cal")]), None),
    # Selection, mirroring parse_entries.
    (
        "same_timestamp_lower_value_wins",
        body([e(130, 0), e(68, 0, "SingleDown"), e(110, 5)]),
        reading(68, 0, "SingleDown"),
    ),
    (
        "duplicate_key_last_wins",
        '[{"sgv": 300, "sgv": 109, "date": %d, "type": "sgv", "direction": "Flat"}]' % T0,
        reading(109, 0),
    ),
    # Whole-response errors: the client reports a fetch error, never a reading.
    ("object_not_a_list", '{"status": 401, "message": "Unauthorized"}', "error"),
    ("html_maintenance_page", "<html><body>Maintenance</body></html>", "error"),
    ("truncated_body", '[{"sgv": 120, "date": ', "error"),
    ("trailing_garbage", body([e(120, 0)]) + " x", "error"),
    ("trailing_comma", '[{"sgv": 120, "date": %d, "type": "sgv"},]' % T0, "error"),
    ("single_quotes", "[{'sgv': 120}]", "error"),
    (
        "raw_newline_inside_string",
        '[{"sgv": 120, "date": %d, "type": "sgv", "note": "a\nb"}]' % T0,
        "error",
    ),
    ("leading_zero_number", '[{"sgv": 0120, "date": %d, "type": "sgv"}]' % T0, "error"),
    ("bare_word", '[{"sgv": undefined}]', "error"),
    ("empty_body", "", "error"),
    ("unterminated_string", '[{"type": "sgv', "error"),
    ("bad_escape", '[{"note": "\\x41", "sgv": 120, "date": %d, "type": "sgv"}]' % T0, "error"),
]

spec = {
    "spec_version": 1,
    "description": (
        "Raw Nightscout /api/v1/entries responses and what every implementation must conclude "
        "from each: the newest trustworthy reading (`mgdl`, `date` in Unix ms, `trend`), `null` "
        'when the response parses but holds no usable reading, or `"error"` when the response '
        "is not a JSON list. Python (json.loads and parse_entries), the firmware's heap-free "
        "parser, and Swift (JSONSerialization and parseEntries) all run every case. Times are "
        "relative to 2026-10-18T12:00:00Z. spec_version increments whenever an existing case "
        "changes; adding a case does not bump it. `swift_also_accepts` lists outcomes the Swift suite may also see where Foundation's JSON parser differs from Python's on syntax Nightscout never sends; each is safe (an error, or the same reading)."
    ),
    "cases": [{"name": n, "body": b, "expect": x} for n, b, x in cases],
}
# Foundation's JSONSerialization is stricter or looser than Python's json on
# syntax no Nightscout server produces. Each allowance is a safe outcome only:
# a whole-response error (the display then ages its last good reading) or the
# very reading Python finds.
SWIFT = {
    "sgv_overflow_skipped": (
        ["error"],
        "JSONSerialization rejects a number it cannot represent; Nightscout writes non-finite numbers as null, so this never comes from a real server.",
    ),
    "duplicate_key_last_wins": (
        [reading(300, 0)],
        "Apple's JSONSerialization keeps the first of two duplicate keys where Python keeps the last. Nightscout cannot send duplicates: MongoDB documents and JSON.stringify both rule them out.",
    ),
    "trailing_comma": (
        [reading(120, 0, "Unknown")],
        "Some Foundation versions accept a trailing comma; the entries are still validated by parseEntries.",
    ),
}
for case in spec["cases"]:
    if case["name"] in SWIFT:
        case["swift_also_accepts"], case["swift_note"] = SWIFT[case["name"]]
names = [c["name"] for c in spec["cases"]]
assert len(names) == len(set(names))
with open("spec/response_vectors.json", "w", encoding="utf-8", newline="\n") as fh:
    fh.write(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
print(len(names), "cases")
