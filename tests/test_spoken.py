"""FR-017: the spoken form says what the screen says, and is never more current.

spec/spoken_vectors.json pins one sentence per display vector. Python must
produce exactly that sentence from the classified status (built here with
the same helpers as tests/test_vectors.py), the Swift package runs the same
file in SpokenVectorTests, and `tools/gen_spoken_vectors.py --check` reports
any drift between the two specs.
"""

import ast
import importlib.util
import json
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from lightkeeper.application.spoken import spoken_age, spoken_name, spoken_text
from lightkeeper.domain.glucose import GlucoseReading, Trend, parse_entries
from lightkeeper.domain.status import Level, Status, classify
from tests.helpers import NOW
from tests.test_vectors import VECTORS, raw_entries, thresholds

ROOT = Path(__file__).resolve().parent.parent
SPOKEN_PATH = ROOT / "spec" / "spoken_vectors.json"
SPOKEN = json.loads(SPOKEN_PATH.read_text(encoding="utf-8"))
SENTENCES = SPOKEN["cases"]

_gen_spec = importlib.util.spec_from_file_location(
    "gen_spoken_vectors", ROOT / "tools" / "gen_spoken_vectors.py"
)
gen = importlib.util.module_from_spec(_gen_spec)
_gen_spec.loader.exec_module(gen)

TREND_WORDS = ("rising", "falling", "steady", "trend unknown")
STALE_START = "Stale, do not trust. "
CONFIRM = "Confirm on the primary device."
NO_DATA = "No data. Check sensor and phone. Confirm on the primary device."
FUTURE = "Stale, do not trust. Reading time is in the future. Confirm on the primary device."


def status_for(case):
    """Classify a display vector exactly as tests/test_vectors.py does."""
    readings = parse_entries(raw_entries(case))
    return classify(readings[0] if readings else None, NOW, thresholds(case))


def reading(mgdl=120, trend=Trend.FLAT):
    return GlucoseReading(mgdl=mgdl, timestamp=NOW, trend=trend)


def stale(mgdl=120, trend=Trend.FLAT, minutes=30):
    return Status(level=Level.STALE, reading=reading(mgdl, trend), age=timedelta(minutes=minutes))


# Forms the vectors do not reach, held to the same rules as the vector sentences.
EDGE_STATUSES = [
    stale(39, Trend.UNKNOWN, 20),
    stale(401, Trend.DOUBLE_UP, 20),
    stale(80, Trend.DOUBLE_DOWN, 1),
    stale(80, Trend.SINGLE_UP, -3),
    Status(level=Level.HIGH, reading=reading(201, Trend.FORTY_FIVE_UP), age=timedelta(0)),
    Status(level=Level.NO_DATA, reading=reading(45), age=timedelta(minutes=3)),
    Status(level=Level.IN_RANGE, reading=reading(), age=None),
    Status(level=Level.IN_RANGE, reading=reading(), age=-timedelta(minutes=3)),
]
EDGE_SENTENCES = [spoken_text(s, e) for s in EDGE_STATUSES for e in (None, "timeout")]


def spoken_screen_age(line):
    """Return the words the screen's age line must be spoken as."""
    if line == "time is in the future":
        return "Reading time is in the future."
    if line == "just now":
        return "just now"
    minutes = re.fullmatch(r"(\d+) min ago", line)
    assert minutes, line
    return spoken_age(int(minutes.group(1)))


def test_fr017_every_display_vector_has_one_spoken_form():
    assert list(SENTENCES) == [case["name"] for case in VECTORS]
    assert len(SENTENCES) == len(VECTORS) >= 39
    assert all(isinstance(text, str) and text for text in SENTENCES.values())
    assert set(SPOKEN) == {"description", "cases"}


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr017_python_matches_spec(case):
    assert spoken_text(status_for(case), case["error"]) == SENTENCES[case["name"]]


def test_fr017_stale_leads_with_do_not_trust_and_has_no_trend_word():
    stale_cases = [case for case in VECTORS if case["level"] == "STALE"]
    assert len(stale_cases) >= 8
    for case in stale_cases:
        text = SENTENCES[case["name"]]
        assert text.startswith(STALE_START), case["name"]
        assert CONFIRM in text, case["name"]
        assert not any(word in text.lower() for word in TREND_WORDS), case["name"]
    # The vectors only cover two arrows on STALE; every arrow is checked here.
    for trend in Trend:
        text = spoken_text(stale(trend=trend))
        assert text.startswith(STALE_START)
        assert not any(word in text.lower() for word in TREND_WORDS), trend
    # Only STALE says it.
    for case in VECTORS:
        assert ("Stale" in SENTENCES[case["name"]]) == (case["level"] == "STALE"), case["name"]


def test_fr017_no_data_has_no_digits():
    no_data = [case for case in VECTORS if case["level"] == "NO DATA"]
    assert len(no_data) >= 5
    for case in no_data:
        assert not re.search(r"\d", SENTENCES[case["name"]]), case["name"]
        assert SENTENCES[case["name"]].startswith(NO_DATA), case["name"]
    # A NO DATA level never speaks the reading it may still carry, whatever its age.
    for minutes in (0, 40, -5):
        status = Status(level=Level.NO_DATA, reading=reading(45), age=timedelta(minutes=minutes))
        assert spoken_text(status) == NO_DATA, minutes


def test_fr017_reading_forms_always_carry_the_age():
    """Every screen with a reading speaks the same age the screen shows."""
    for case in VECTORS:
        if case["level"] == "NO DATA":
            continue
        expected = spoken_screen_age(case["lines"][2])
        text = SENTENCES[case["name"]]
        assert re.search(rf"(?<!\d){re.escape(expected)}", text, re.IGNORECASE), case["name"]


def test_fr017_no_ascii_arrow_tokens_or_unit_abbreviation():
    """A screen reader would say "v" or "slash"; the sentences say words instead."""
    arrows = {trend.arrow for trend in Trend}
    assert {"->", "^", "v", "vv", "\\"} <= arrows
    for text in [*SENTENCES.values(), *EDGE_SENTENCES]:
        tokens = {token.strip(".,") for token in text.split()}
        assert not tokens & arrows, text
        for banned in ("->", "^", "\\", "/", "?"):
            assert banned not in text, text
        assert not re.search(r"mg/dL|\bmg\b", text, re.IGNORECASE), text
        assert text.isascii(), text


@pytest.mark.parametrize(
    ("tamper", "reported"),
    [
        (lambda spec: spec["cases"].update(in_range_flat="In range."), "in_range_flat:"),
        (lambda spec: spec["cases"].pop("no_data"), "no_data: missing"),
        (lambda spec: spec["cases"].update(made_up="No data."), "made_up: not a display vector"),
        (lambda spec: spec.update(description="edited"), "description differs"),
        (lambda spec: spec.update(spec_version=2), "top-level keys"),
        (
            lambda spec: spec.update(cases=dict(reversed(list(spec["cases"].items())))),
            "not in spec/display_vectors.json order",
        ),
    ],
)
def test_fr017_generator_check_reports_drift(tmp_path, capsys, tamper, reported):
    assert gen.main(["--check"]) == 0, "spec/spoken_vectors.json is out of date"
    capsys.readouterr()
    spec = json.loads(SPOKEN_PATH.read_text(encoding="utf-8"))
    tamper(spec)
    drifted = tmp_path / "spoken_vectors.json"
    drifted.write_text(gen.render(spec), encoding="utf-8")
    assert gen.main(["--check", "--spoken", str(drifted)]) == 1
    err = capsys.readouterr().err
    assert reported in err
    assert "run: python tools/gen_spoken_vectors.py" in err


@pytest.mark.parametrize(
    ("content", "reported"),
    [
        (None, "is missing"),
        ("{not json", "is not valid JSON"),
        ('{"cases": []}\n', "has no 'cases' object"),
        ("[]\n", "has no 'cases' object"),
    ],
)
def test_fr017_generator_check_reports_a_broken_file(tmp_path, capsys, content, reported):
    path = tmp_path / "spoken_vectors.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert gen.main(["--check", "--spoken", str(path)]) == 1
    assert reported in capsys.readouterr().err


def test_fr017_generator_check_reports_formatting_drift(tmp_path, capsys):
    path = tmp_path / "spoken_vectors.json"
    path.write_text(json.dumps(SPOKEN, indent=4), encoding="utf-8")
    assert gen.main(["--check", "--spoken", str(path)]) == 1
    assert "formatting differs" in capsys.readouterr().err


def test_fr017_generator_writes_the_committed_file(tmp_path):
    path = tmp_path / "spoken_vectors.json"
    assert gen.main(["--spoken", str(path)]) == 0
    committed = SPOKEN_PATH.read_bytes().replace(b"\r\n", b"\n")
    assert path.read_bytes() == committed
    assert gen.main(["--check", "--spoken", str(path)]) == 0


def test_fr017_generator_follows_the_display_vectors(tmp_path, capsys):
    """A new display vector without a spoken form is drift, named by its case."""
    display = json.loads((ROOT / "spec" / "display_vectors.json").read_text(encoding="utf-8"))
    extra = dict(display["cases"][0], name="brand_new_case")
    display["cases"].append(extra)
    display_path = tmp_path / "display_vectors.json"
    display_path.write_text(json.dumps(display), encoding="utf-8")
    assert gen.main(["--check", "--display", str(display_path)]) == 1
    assert "brand_new_case: missing" in capsys.readouterr().err


def test_fr017_generator_check_runs_as_a_script():
    result = subprocess.run(  # noqa: S603 - fixed arguments, this interpreter
        [sys.executable, str(ROOT / "tools" / "gen_spoken_vectors.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "up to date" in result.stdout


def test_fr017_every_trend_has_its_own_words():
    assert {trend: spoken_name(trend) for trend in Trend} == {
        Trend.DOUBLE_UP: "rising quickly",
        Trend.SINGLE_UP: "rising",
        Trend.FORTY_FIVE_UP: "rising slowly",
        Trend.FLAT: "steady",
        Trend.FORTY_FIVE_DOWN: "falling slowly",
        Trend.SINGLE_DOWN: "falling",
        Trend.DOUBLE_DOWN: "falling quickly",
        Trend.UNKNOWN: "trend unknown",
    }


def test_fr017_ages_are_spoken_in_whole_minutes():
    assert spoken_age(0) == "just now"
    assert spoken_age(1) == "1 minute ago"
    assert spoken_age(2) == "2 minutes ago"
    assert spoken_age(15) == "15 minutes ago"


@pytest.mark.parametrize(
    ("level", "headline"),
    [
        (Level.URGENT_LOW, "Urgent low."),
        (Level.LOW, "Low."),
        (Level.IN_RANGE, "In range."),
        (Level.HIGH, "High."),
        (Level.URGENT_HIGH, "Urgent high."),
    ],
)
def test_fr017_fresh_levels_lead_with_their_word(level, headline):
    status = Status(level=level, reading=reading(150, Trend.SINGLE_UP), age=timedelta(minutes=1))
    expected = f"{headline} 150 milligrams per deciliter, rising. 1 minute ago."
    assert spoken_text(status) == expected


def test_fr017_stale_sentinels_say_the_sensor_limit_not_a_number():
    assert spoken_text(stale(39, minutes=20)) == (
        "Stale, do not trust. Last reading below 40, 20 minutes ago. "
        "Confirm on the primary device."
    )
    assert spoken_text(stale(401, minutes=61)) == (
        "Stale, do not trust. Last reading above 400, 61 minutes ago. "
        "Confirm on the primary device."
    )


def test_fr017_without_a_reading_or_an_age_it_is_spoken_as_no_data():
    for status in [
        Status(level=Level.IN_RANGE, reading=None, age=None),
        Status(level=Level.STALE, reading=None, age=timedelta(minutes=20)),
        Status(level=Level.STALE, reading=reading(), age=None),
        Status(level=Level.IN_RANGE, reading=reading(), age=None),
    ]:
        assert spoken_text(status) == NO_DATA, status


def test_fr017_a_negative_age_is_never_spoken_as_current():
    """Fresh ages from classify are never negative; a Status whose age is, is not trusted."""
    for level in (Level.IN_RANGE, Level.URGENT_LOW, Level.STALE):
        status = Status(level=level, reading=reading(), age=-timedelta(minutes=3))
        assert spoken_text(status) == FUTURE, level


def test_fr017_an_unknown_level_gets_the_most_cautious_form():
    status = Status(level=object(), reading=reading(250), age=timedelta(minutes=2))
    assert spoken_text(status) == NO_DATA


def test_fr017_unreachable_is_added_last_to_every_form():
    for status in [*EDGE_STATUSES, *(status_for(case) for case in VECTORS)]:
        plain = spoken_text(status)
        assert spoken_text(status, "connection refused") == plain + " Nightscout unreachable."
        # Same truthiness as render_lines: an empty error string is no error.
        assert spoken_text(status, "") == plain


def test_fr017_spoken_form_imports_only_the_domain_layer():
    """Built from the Status, never by parsing render_lines' output."""
    source = (ROOT / "src" / "lightkeeper" / "application" / "spoken.py").read_text("utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    ours = {name for name in imported if name.split(".")[0] == "lightkeeper"}
    assert ours and all(name.startswith("lightkeeper.domain.") for name in ours), ours
    assert imported - ours <= {"__future__"}, imported


def names_and_keys(tree):
    """Every imported or referenced name, and every literal dict or subscript key."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or ""
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, ast.Dict):
            yield from (key.value for key in node.keys if isinstance(key, ast.Constant))
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            yield node.slice.value


def test_fr017_spoken_form_is_not_published_to_home_assistant():
    """No audio-alert path is invited: the HA payload never carries the sentence (HAZ-013)."""
    modules = [
        "application/status_payload.py",
        "infrastructure/home_assistant.py",
        "infrastructure/mqtt.py",
    ]
    for module in modules:
        tree = ast.parse((ROOT / "src" / "lightkeeper" / module).read_text("utf-8"))
        found = {name for name in names_and_keys(tree) if "spoken" in str(name).lower()}
        assert not found, (module, found)
    # The guard itself sees a payload key and an import.
    planted = ast.parse(
        "from lightkeeper.application.spoken import spoken_text\nx = {'spoken': 1}\n"
    )
    assert {"lightkeeper.application.spoken", "spoken_text", "spoken"} <= set(
        names_and_keys(planted)
    )
