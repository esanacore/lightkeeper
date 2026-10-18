"""FR-004, FR-005: rendering and graceful degradation when Nightscout fails."""

from datetime import timedelta

from glucose_watch.application.monitor import current_status, render_lines
from glucose_watch.domain.status import Level, Thresholds
from tests.helpers import NOW, FakeSource, entry

T = Thresholds()


def test_fr004_normal_reading_renders_value_arrow_and_age():
    status, error = current_status(FakeSource([entry(112, 3, "SingleUp")]), NOW, T)
    assert error is None
    assert render_lines(status) == ["IN RANGE", "112 mg/dL ^", "3 min ago"]


def test_fr004_just_now_wording():
    status, _ = current_status(FakeSource([entry(150)]), NOW, T)
    assert render_lines(status)[2] == "just now"


def test_fr004_uses_newest_reading():
    status, _ = current_status(FakeSource([entry(100, 10), entry(65, 0)]), NOW, T)
    assert status.level is Level.LOW
    assert status.reading.mgdl == 65


def test_fr004_sentinels_render_as_words_not_numbers():
    low, _ = current_status(FakeSource([entry(39)]), NOW, T)
    high, _ = current_status(FakeSource([entry(401)]), NOW, T)
    assert render_lines(low)[:2] == ["URGENT LOW", "LOW (<40)"]
    assert render_lines(high)[:2] == ["URGENT HIGH", "HIGH (>400)"]


def test_fr003_stale_reading_renders_warning_first():
    status, _ = current_status(FakeSource([entry(120, 30)]), NOW, T)
    lines = render_lines(status)
    assert lines[0] == "STALE - DO NOT TRUST"
    assert lines[1] == "last: 120 mg/dL ->"
    assert lines[2] == "30 min ago"
    assert "Confirm on primary device" in lines


def test_fr003_future_reading_renders_clock_warning():
    status, _ = current_status(FakeSource([entry(120, -10)]), NOW, T)
    assert render_lines(status)[2] == "time is in the future"


def test_fr004_no_data_renders_guidance():
    status, error = current_status(FakeSource([]), NOW, T)
    assert error is None
    assert render_lines(status)[0] == "NO DATA"


def test_fr005_fetch_error_with_no_history_is_no_data():
    status, error = current_status(FakeSource(error=RuntimeError("down")), NOW, T)
    assert status.level is Level.NO_DATA
    assert error == "down"
    assert render_lines(status, error)[-1] == "Nightscout unreachable"


def test_fr005_fetch_error_reuses_last_good_and_ages_it_into_stale():
    good, _ = current_status(FakeSource([entry(120, 2)]), NOW, T)
    failing = FakeSource(error=RuntimeError("down"))

    soon, _ = current_status(failing, NOW + timedelta(minutes=5), T, last_good=good)
    assert soon.level is Level.IN_RANGE
    assert soon.age_minutes == 7

    later, error = current_status(failing, NOW + timedelta(minutes=20), T, last_good=good)
    assert later.level is Level.STALE
    assert render_lines(later, error)[0] == "STALE - DO NOT TRUST"


def test_fr004_stale_while_unreachable_stays_four_lines():
    good, _ = current_status(FakeSource([entry(120, 2)]), NOW, T)
    later, error = current_status(FakeSource(error=RuntimeError("down")), NOW + timedelta(minutes=30), T, good)
    lines = render_lines(later, error)
    assert lines == ["STALE - DO NOT TRUST", "last: 120 mg/dL ->", "32 min ago", "Nightscout unreachable"]


def test_fr004_render_output_is_ascii_and_short():
    for mgdl, ago in [(39, 0), (120, 3), (300, 1), (120, 60)]:
        status, _ = current_status(FakeSource([entry(mgdl, ago)]), NOW, T)
        rendered = render_lines(status, "x")
        assert len(rendered) <= 4
        for line in rendered:
            assert line.isascii()
            assert len(line) <= 26  # fits a small e-ink panel at a readable size
