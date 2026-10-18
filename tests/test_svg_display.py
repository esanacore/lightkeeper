"""FR-011: the SVG panel image matches the rendered lines and is safe to embed."""

import xml.etree.ElementTree as ET

import pytest

from lightkeeper import cli
from lightkeeper.infrastructure.svg_display import render_svg

NS = {"svg": "http://www.w3.org/2000/svg"}


def texts(svg):
    root = ET.fromstring(svg)
    return [t.text for t in root.findall("svg:text", NS)]


def test_fr011_every_line_is_drawn_in_order():
    lines = ["STALE - DO NOT TRUST", "last: 120 mg/dL ->", "32 min ago", "Nightscout unreachable"]
    assert texts(render_svg(lines)) == lines


def test_fr011_headline_is_bold_and_larger():
    root = ET.fromstring(render_svg(["IN RANGE", "112 mg/dL ->", "3 min ago"]))
    first, second = root.findall("svg:text", NS)[:2]
    assert first.get("font-weight") == "700"
    assert int(first.get("font-size")) > int(second.get("font-size"))


def test_fr011_text_stays_inside_the_panel():
    for height in (60, 128, 480):
        root = ET.fromstring(render_svg(["A", "B", "C", "D"], width=300, height=height))
        for t in root.findall("svg:text", NS):
            assert 0 < int(t.get("y")) < height


def test_fr011_markup_in_text_is_escaped():
    svg = render_svg(['<script>alert("x")</script>', "a & b"], title='x" onload="y')
    root = ET.fromstring(svg)  # parses, so nothing broke out of the markup
    assert root.find(".//svg:script", NS) is None
    assert texts(svg) == ['<script>alert("x")</script>', "a & b"]
    assert root.get("aria-label") == 'x" onload="y'


@pytest.mark.parametrize(
    "kwargs", [{"lines": []}, {"lines": ["x"], "width": 50}, {"lines": ["x"], "height": 20}]
)
def test_fr011_rejects_bad_input(kwargs):
    with pytest.raises(ValueError):
        render_svg(**kwargs)


def test_fr011_cli_writes_svg_atomically(tmp_path, monkeypatch, capsys):
    for name in ["NIGHTSCOUT_URL", "NIGHTSCOUT_TOKEN"]:
        monkeypatch.delenv(name, raising=False)
    target = tmp_path / "screen.svg"
    assert cli.main(["--demo", "--demo-mgdl", "64", "--svg", str(target)]) == 1
    drawn = texts(target.read_text(encoding="utf-8"))
    assert drawn[:2] == ["LOW", "64 mg/dL ->"]
    # HAZ-011: the file says when it was written, so a dashboard can tell a
    # live writer from one that died and left its last image behind.
    assert drawn[-1].startswith("written ") and drawn[-1].endswith(" UTC")
    assert not (tmp_path / "screen.svg.tmp").exists()


def test_haz011_written_stamp_is_optional_and_utc():
    from datetime import UTC, datetime, timedelta, timezone

    plain = render_svg(["IN RANGE", "120 mg/dL ->"])
    assert "written" not in plain
    local = datetime(2026, 10, 18, 7, 5, tzinfo=timezone(timedelta(hours=-5)))
    assert "written 12:05 UTC" in render_svg(["IN RANGE"], written_at=local)
    assert "written 12:05 UTC" in render_svg(["IN RANGE"], written_at=local.astimezone(UTC))


def test_fr011_longest_lines_fit_the_panel_width():
    from lightkeeper.infrastructure.svg_display import CHAR_WIDTH_RATIO

    lines = ["STALE - DO NOT TRUST", "Confirm on primary device"]
    for width in (296, 400):
        root = ET.fromstring(render_svg(lines, width=width, height=128))
        for t in root.findall("svg:text", NS):
            right_edge = int(t.get("x")) + len(t.text) * int(t.get("font-size")) * CHAR_WIDTH_RATIO
            assert right_edge <= width - int(t.get("x"))


def test_fr011_headline_only_screen():
    assert texts(render_svg(["NO DATA"])) == ["NO DATA"]
