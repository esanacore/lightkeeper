"""FR-011: the SVG panel image matches the rendered lines and is safe to embed.

The image draws each status with the same 1-bit shape as the panel, from the
same table, in the brand's colors; the hierarchy rules the panel holds (the
status word never smaller than the number, an old value never the hero) are
measured here at the six panel profiles and at a sweep of other sizes.
"""

import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lightkeeper import cli
from lightkeeper.infrastructure import panel_layout as pl
from lightkeeper.infrastructure import svg_display as sd
from lightkeeper.infrastructure.epaper_bitmap import Bitmap, _draw_frame
from lightkeeper.infrastructure.panel_profiles import PROFILES
from lightkeeper.infrastructure.svg_display import render_svg

NS = {"svg": "http://www.w3.org/2000/svg"}
ROOT = Path(__file__).resolve().parent.parent
TOKENS = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))
VECTORS = json.loads((ROOT / "spec" / "display_vectors.json").read_text(encoding="utf-8"))["cases"]
VECTOR_IDS = [c["name"] for c in VECTORS]
FRESH_VECTORS = [c for c in VECTORS if pl.treatment(c["lines"][0]) in pl.FRESH]
PROFILE_SIZES = [(p.width, p.height) for p in PROFILES.values()]
# The smallest accepted panel, heights where the margin and the font sizes
# round differently, tall and narrow, short and wide, and a few large ones.
SWEEP_SIZES = sorted(
    {(w, h) for w in (100, 101, 160, 296) for h in (60, 61, 62, 63, 64, 70, 99, 128, 300, 800)}
    | {(801, 60), (1600, 61), (100, 1200), (4096, 4096)}
)
ALL_SIZES = [*PROFILE_SIZES, *SWEEP_SIZES]
STALE_LINES = VECTORS[VECTOR_IDS.index("stale_at_16_minutes")]["lines"]
WRITTEN = datetime(2026, 10, 18, 23, 59, tzinfo=UTC)
HATCH = f"url(#{sd.ID_PREFIX}-hatch)"
STRETCH = re.compile(r"matrix\(1 0 0 ([0-9.]+) 0 (-?[0-9.]+)\)")


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


# --- reading the drawing back ---------------------------------------------------


@dataclass(frozen=True)
class Box:
    """A rectangle in image pixels: left, top, right and bottom edges."""

    left: int
    top: int
    right: int
    bottom: int

    def inside(self, other):
        across = other.left <= self.left and self.right <= other.right
        return across and other.top <= self.top and self.bottom <= other.bottom

    def meets(self, other):  # the two share at least one pixel
        across = self.left < other.right and other.left < self.right
        return across and self.top < other.bottom and other.top < self.bottom


@dataclass(frozen=True)
class Text:
    """One drawn line: its words, font size, fill and the box it covers."""

    text: str
    size: int
    fill: str
    box: Box
    baseline: int
    element: ET.Element


@dataclass(frozen=True)
class Drawing:
    """Everything an SVG draws, sorted by kind."""

    lines: list[Text]  # every <text>, in document order
    ink: list[Box]  # Ink rectangles: the band, the rule, the strike
    hatch: list[Box]  # the hatched frame's four sides
    dashes: list[ET.Element]  # the dashed frame's four sides
    patterns: list[ET.Element]


def read(svg):
    """Parse an SVG drawn by render_svg into its texts and marks."""
    root = ET.fromstring(svg)
    lines = []
    for t in root.findall("svg:text", NS):
        size, baseline, x = int(t.get("font-size")), int(t.get("y")), int(t.get("x"))
        top = baseline - round(size * sd.BASELINE_RATIO)
        span = int(t.get("textLength", "0"))
        left = x - span if t.get("text-anchor") == "end" else x
        # A headline stretched to the band's height carries matrix(1 0 0 tall 0 shift).
        matrix = STRETCH.fullmatch(t.get("transform", "matrix(1 0 0 1 0 0)"))
        tall, shift = float(matrix[1]), float(matrix[2])
        box = Box(left, round(top * tall + shift), left + span, round((top + size) * tall + shift))
        lines.append(Text(t.text or "", size, t.get("fill"), box, baseline, t))
    ink, hatch = [], []
    for r in root.findall("svg:rect", NS):
        if r.get("fill") in (sd.INK, HATCH):
            x, y = int(r.get("x")), int(r.get("y"))
            box = Box(x, y, x + int(r.get("width")), y + int(r.get("height")))
            (ink if r.get("fill") == sd.INK else hatch).append(box)
    dashes, patterns = root.findall("svg:line", NS), root.findall(".//svg:pattern", NS)
    return Drawing(lines, ink, hatch, dashes, patterns)


def margin_of(width, height):
    return round(min(width, height) * sd.MARGIN_RATIO)


def content_box(width, height):
    edge = margin_of(width, height)
    return Box(edge, edge, width - edge, height - edge)


def sizes_by_role(drawing, lines):
    """{role: [font sizes]} for the screen's lines, roles as the panel assigns them."""
    out = {}
    roles = [pl.HEADLINE, *pl.roles_for(pl.treatment(lines[0]), len(lines) - 1)]
    for text, role in zip(drawing.lines, roles, strict=False):  # the stamp is left out
        out.setdefault(role, []).append(text.size)
    return out


def marks(drawing, width, height):
    """(bands, rules, strikes): the Ink rectangles, told apart by where they sit.

    The band starts at the top of the content box; a strike crosses a line of
    text under the headline; anything else is a rule.
    """
    top = content_box(width, height).top
    bands = [box for box in drawing.ink if box.top == top]
    strikes = [
        box
        for box in drawing.ink
        if box not in bands and any(line.box.meets(box) for line in drawing.lines[1:])
    ]
    rules = [box for box in drawing.ink if box not in bands and box not in strikes]
    return bands, rules, strikes


# --- shape before hue: the panel's treatment table ------------------------------


def test_fr011_shapes_come_from_the_panel_layout_table(monkeypatch):
    assert sd.treatment is pl.treatment and sd.REFERENCE_HEADLINE == pl.REFERENCE_HEADLINE
    plain = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    assert read(render_svg(plain)).dashes == []
    # Change the table and the SVG follows: there is no second copy of it.
    monkeypatch.setitem(pl.TREATMENTS, "IN RANGE", pl.DASHED)
    assert len(read(render_svg(plain)).dashes) == 4


@pytest.mark.parametrize("case", VECTORS, ids=VECTOR_IDS)
def test_fr011_each_status_draws_its_panel_shape_and_nothing_else(case):
    lines = case["lines"]
    kind = pl.treatment(lines[0])
    assert kind == TOKENS["status"][case["level"]]["treatment"]
    for width, height in PROFILE_SIZES:
        d = read(render_svg(lines, width, height))
        content = content_box(width, height)
        headline = d.lines[0]
        banded = kind in (pl.INVERSE, pl.STALE)
        # Paper words on the Ink band; Ink words everywhere else.
        assert headline.fill == (sd.PAPER if banded else sd.INK)
        assert headline.element.get("font-weight") == "700"
        assert all(line.fill == sd.INK for line in d.lines[1:])
        bands, rules, strikes = marks(d, width, height)
        assert len(bands) == (1 if banded else 0)
        assert len(rules) == (1 if kind == pl.RULE else 0)
        assert len(strikes) == (1 if kind == pl.STALE else 0)
        assert len(d.hatch) == (4 if kind == pl.STALE else 0)
        assert len(d.patterns) == (1 if kind == pl.STALE else 0)
        assert len(d.dashes) == (4 if kind == pl.DASHED else 0)
        for band in bands:  # the band spans the content width, the headline inside it
            assert (band.left, band.right) == (content.left, content.right)
            assert headline.box.inside(band)
        for rule in rules:  # under the headline, full content width
            assert (rule.left, rule.right) == (content.left, content.right)
            assert rule.bottom - rule.top == pl.RULE_THICKNESS
            assert headline.box.bottom <= rule.top
            assert all(rule.bottom <= line.box.top for line in d.lines[1:])


def test_fr011_an_unknown_headline_gets_the_cautious_dashed_frame():
    d = read(render_svg(["SOMETHING NEW", "120 mg/dL ->", "3 min ago"]))
    assert len(d.dashes) == 4 and d.ink == [] and d.hatch == [] and d.patterns == []


@pytest.mark.parametrize(("width", "height"), PROFILE_SIZES)
def test_fr011_headline_band_is_one_height_for_every_level(width, height):
    bottoms, headlines = set(), set()
    for case in [*VECTORS, {"lines": ["SOMETHING NEW", "x"]}]:
        d = read(render_svg(case["lines"], width, height))
        bands, rules, _ = marks(d, width, height)
        bottoms.update(box.bottom for box in bands + rules)  # the band's lower edge
        # STALE - DO NOT TRUST is drawn narrower but never shorter than IN RANGE.
        headlines.add((d.lines[0].box.top, d.lines[0].box.bottom))
    assert len(bottoms) == 1 and len(headlines) == 1
    ((top, bottom),) = headlines  # the band's full height, inside its padding
    assert (top, bottom) == (margin_of(width, height) + pl.BAND_PAD, min(bottoms) - pl.BAND_PAD)
    (band_bottom,) = bottoms
    for case in VECTORS:  # every line under the headline starts below the band
        d = read(render_svg(case["lines"], width, height))
        assert all(line.box.top >= band_bottom for line in d.lines[1:])


def test_fr011_strike_crosses_the_last_line_only_1_px_on_small_text_2_px_on_large():
    thicknesses = set()
    for (width, height), case in ((size, c) for size in PROFILE_SIZES for c in VECTORS):
        if pl.treatment(case["lines"][0]) != pl.STALE:
            continue
        d = read(render_svg(case["lines"], width, height))
        last = d.lines[1]
        assert last.text.startswith("last: ")
        (strike,) = [box for box in d.ink if box.top != margin_of(width, height)]
        # Across the whole line, through its capitals.
        assert (strike.left, strike.right) == (last.box.left, last.box.right)
        cap_top = last.baseline - round(last.size * sd.CAP_RATIO)
        assert cap_top < strike.top and strike.bottom < last.baseline
        thickness = strike.bottom - strike.top
        assert thickness == (2 if last.size >= sd.THICK_STRIKE_SIZE else 1)
        thicknesses.add(thickness)
        assert [line for line in d.lines if line.box.meets(strike)] == [last]
    assert thicknesses == {1, 2}  # the 2.9" panel has the thin one, the 7.5" the thick


def ring_pixels(drawing):
    """Return the pixels the hatch and the dashes ink, sampled at pixel centres."""
    inked = set()
    cells = {
        (int(r.get("x")), int(r.get("y")))
        for pattern in drawing.patterns
        for r in pattern.findall("svg:rect", NS)
    }
    for box in drawing.hatch:
        for y in range(box.top, box.bottom):
            for x in range(box.left, box.right):
                if (x % sd.HATCH_PITCH, y % sd.HATCH_PITCH) in cells:
                    inked.add((x, y))
    for line in drawing.dashes:
        x1, y1, x2, y2 = (int(line.get(k)) for k in ("x1", "y1", "x2", "y2"))
        half = int(line.get("stroke-width")) // 2
        on, off = (int(n) for n in line.get("stroke-dasharray").split())
        offset = int(line.get("stroke-dashoffset", "0"))
        if y1 == y2:  # across
            for x in range(x1, x2):
                if (x - x1 + offset) % (on + off) < on:
                    inked.update((x, y) for y in range(y1 - half, y1 + half))
        else:  # down
            for y in range(y1, y2):
                if (y - y1 + offset) % (on + off) < on:
                    inked.update((x, y) for x in range(x1 - half, x1 + half))
    return inked


@pytest.mark.parametrize(("width", "height"), [*PROFILE_SIZES, (100, 60), (101, 63)])
@pytest.mark.parametrize("kind", [pl.STALE, pl.DASHED])
def test_fr011_frames_ink_the_same_pixels_as_the_panel_frame(kind, width, height):
    headline = "STALE - DO NOT TRUST" if kind == pl.STALE else "NO DATA"
    drawing = read(render_svg([headline, "x"], width, height))
    thickness = pl.HATCH_WIDTH if kind == pl.STALE else pl.DASH_WIDTH
    inset = (margin_of(width, height) - thickness) // 2
    panel = Bitmap(width, height)
    _draw_frame(
        panel, kind, pl.Box(inset, inset, width - 2 * inset, height - 2 * inset), thickness
    )
    expected = {(i % width, i // width) for i, ink in enumerate(panel.ink) if ink}
    assert ring_pixels(drawing) == expected


def test_fr011_hatch_is_the_brand_hatch_counted_from_the_top_left_pixel():
    (pattern,) = read(render_svg(STALE_LINES)).patterns
    assert pattern.get("patternUnits") == "userSpaceOnUse"
    assert (pattern.get("width"), pattern.get("height")) == (str(pl.HATCH_PITCH),) * 2
    grid = [["."] * pl.HATCH_PITCH for _ in range(pl.HATCH_PITCH)]
    for r in pattern.findall("svg:rect", NS):
        assert (r.get("width"), r.get("height"), r.get("fill")) == ("1", "1", sd.INK)
        grid[int(r.get("y"))][int(r.get("x"))] = "#"
    assert ["".join(row) for row in grid] == TOKENS["texture"]["hatch-45"]["cells"]


def test_fr011_an_id_prefix_keeps_the_hatch_of_each_inlined_image_its_own():
    # Ids are page-wide: inlined side by side, each STALE image needs its own,
    # or hiding the first one can take the visible one's hatch with it.
    assert render_svg(STALE_LINES, id_prefix=sd.ID_PREFIX) == render_svg(STALE_LINES)
    for prefix in ("lk", "bedside", "Kitchen_2-b"):
        root = ET.fromstring(render_svg(STALE_LINES, id_prefix=prefix))
        assert [p.get("id") for p in root.iter(f"{{{NS['svg']}}}pattern")] == [f"{prefix}-hatch"]
        fills = {e.get("fill") for e in root.iter() if "url(" in e.get("fill", "")}
        assert fills == {f"url(#{prefix}-hatch)"}
    for bad in ("", "1st", "a b", 'x" onload="y', "a)", "a\n"):  # never escapes the attribute
        with pytest.raises(ValueError, match="id_prefix"):
            render_svg(STALE_LINES, id_prefix=bad)


@pytest.mark.parametrize(("width", "height"), ALL_SIZES)
def test_fr011_texture_stays_in_the_margin_never_under_text(width, height):
    content = content_box(width, height)
    for headline in ("STALE - DO NOT TRUST", "NO DATA"):
        lines = [headline, *STALE_LINES[1:]]
        d = read(render_svg(lines, width, height, written_at=WRITTEN))
        texture = d.hatch + [Box(x, y, x + 1, y + 1) for x, y in ring_pixels(d)]
        assert texture
        assert not any(box.meets(content) for box in texture)
        assert not any(line.box.meets(box) for line in d.lines for box in texture)


# --- hierarchy: the status word is never smaller than the number ----------------


@pytest.mark.parametrize("case", FRESH_VECTORS, ids=[c["name"] for c in FRESH_VECTORS])
def test_fr011_value_line_is_larger_than_body_text_and_no_larger_than_the_headline(case):
    lines = case["lines"]
    d = read(render_svg(lines))
    headline, value, *rest = (line.size for line in d.lines)
    assert all(value > size for size in rest)
    assert value <= headline
    assert value == round(sd.DEFAULT_HEIGHT * sd.VALUE_RATIO)  # the hero at full size


@pytest.mark.parametrize(("width", "height"), ALL_SIZES)
def test_fr011_glance_order_holds_at_every_size(width, height):
    for case in VECTORS:
        for written_at in (None, WRITTEN):
            d = read(render_svg(case["lines"], width, height, written_at=written_at))
            by_role = sizes_by_role(d, case["lines"])
            (headline,) = by_role[pl.HEADLINE]  # the size it is set at
            tall = d.lines[0].box.bottom - d.lines[0].box.top  # stretched to the band
            where = (width, height, case["name"], written_at)
            # Nothing on the screen is taller than the status word, and the
            # number (fresh or old) is never set larger than it.
            assert all(line.size <= tall for line in d.lines), where
            for role in (pl.VALUE, pl.LAST):
                assert all(size <= headline for size in by_role.get(role, [])), where
            # The hero, then the age, then everything else (on STALE, the
            # old value is never above the age: it is never the hero).
            for value in by_role.get(pl.VALUE, []):
                assert all(age <= value for age in by_role.get(pl.AGE, [])), where
            for age in by_role.get(pl.AGE, []):
                for role in (pl.LAST, pl.CONTEXT):
                    assert all(size <= age for size in by_role.get(role, [])), where
            if written_at is not None:  # the stamp is chrome
                assert d.lines[-1].text == "written 23:59 UTC"
                assert all(d.lines[-1].size <= line.size for line in d.lines[:-1]), where
                assert d.lines[-1].size >= sd.STAMP_MIN_SIZE, where
            assert all(line.size >= sd.MIN_SIZE for line in d.lines[: len(case["lines"])])


def test_fr011_an_old_value_is_never_larger_than_its_age_even_when_the_age_line_is_long():
    # A long age line is fitted smaller; the `last:` line (and context) follow it down.
    lines = ["STALE - DO NOT TRUST", "last: 1 ->", "time is in the future, by a long way", "x"]
    headline, last, age, context = (line.size for line in read(render_svg(lines)).lines)
    assert age < round(sd.DEFAULT_HEIGHT * sd.BODY_RATIO)
    assert last == context == age < headline
    # On a square panel the narrowed STALE headline is set small and stretched;
    # the age keeps its size, and the short old value stays at the headline's.
    d = read(render_svg(["STALE - DO NOT TRUST", "last: 1 ->", "16 min ago"], 200, 200))
    headline, last, age = (line.size for line in d.lines)
    tall = d.lines[0].box.bottom - d.lines[0].box.top
    assert last == headline < age == round(200 * sd.BODY_RATIO) < tall


@pytest.mark.parametrize(("width", "height"), ALL_SIZES)
def test_fr011_every_line_stays_inside_the_content_box_at_every_size(width, height):
    content = content_box(width, height)
    for case in VECTORS:
        for written_at in (None, WRITTEN):
            d = read(render_svg(case["lines"], width, height, written_at=written_at))
            where = (width, height, case["name"], written_at)
            assert [line.text for line in d.lines][: len(case["lines"])] == case["lines"]
            for line in d.lines:
                assert line.box.inside(content), (*where, line.text, line.box)
            # In order down the panel, never touching; the stamp under them all.
            for upper, lower in zip(d.lines, d.lines[1:], strict=False):
                assert upper.box.bottom <= lower.box.top, (*where, upper.text, lower.text)


def test_fr011_a_line_too_long_for_a_tiny_panel_is_drawn_narrower_not_past_the_margin():
    lines = VECTORS[VECTOR_IDS.index("no_data")]["lines"]
    d = read(render_svg(lines, 100, 60))
    confirm = d.lines[2]
    assert confirm.text == "Confirm on primary device" and confirm.size == sd.MIN_SIZE
    assert confirm.element.get("lengthAdjust") == "spacingAndGlyphs"
    assert confirm.box == Box(5, confirm.box.top, 95, confirm.box.bottom)
    # At the default size nothing needs squeezing.
    assert all(t.element.get("lengthAdjust") is None for t in read(render_svg(lines)).lines)


def test_fr011_out_of_room_context_shrinks_first_then_the_hero_never_status_or_age():
    value, body = (
        round(sd.DEFAULT_HEIGHT * sd.VALUE_RATIO),
        round(sd.DEFAULT_HEIGHT * sd.BODY_RATIO),
    )
    # More lines than a screen has: the context gives way, the hero and age do not.
    fresh = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    d = read(render_svg([*fresh, "one", "two", "three"]))
    sizes = [line.size for line in d.lines]
    assert sizes[1:3] == [value, body] and all(sd.MIN_SIZE < s < body for s in sizes[3:])
    assert all(line.box.inside(content_box(296, 128)) for line in d.lines)
    # Context already at its smallest on a short panel: the hero gives way toward the age.
    lines = VECTORS[VECTOR_IDS.index("last_good_while_unreachable")]["lines"]
    d = read(render_svg(lines, 296, 62, written_at=WRITTEN))
    headline, hero, age, context, stamp = (line.size for line in d.lines)
    assert stamp <= context == age == sd.MIN_SIZE < hero < round(62 * sd.VALUE_RATIO) <= headline
    assert all(line.box.inside(content_box(296, 62)) for line in d.lines)
    # Far too many lines: the hero stops at the age; the status and the age keep their size.
    lines = [*fresh, *(f"line {n}" for n in range(12))]
    sizes = [line.size for line in read(render_svg(lines)).lines]
    assert sizes[0] == read(render_svg(fresh)).lines[0].size
    assert sizes[1] == sizes[2] == body and set(sizes[3:]) == {sd.MIN_SIZE}
    assert texts(render_svg(lines)) == lines  # still every line, in order


def test_fr011_an_empty_line_is_drawn_without_a_width():
    root = ET.fromstring(render_svg(["IN RANGE", ""]))
    empty = root.findall("svg:text", NS)[1]
    assert empty.text is None and empty.get("textLength") is None


# --- brand: colors and type -----------------------------------------------------


def test_fr011_colors_are_the_brand_tokens():
    color = TOKENS["color"]
    assert sd.PAPER == color["paper"]["light"]
    assert sd.INK == color["ink"]["light"]
    assert sd.STAMP == color["muted"]["light"]
    assert sd.LINE_STRONG == color["line-strong"]["light"]  # bezels, as on the demo page
    for case in VECTORS:
        root = ET.fromstring(render_svg(case["lines"], written_at=WRITTEN))
        used = {
            element.get(name)
            for element in root.iter()
            for name in ("fill", "stroke")
            if element.get(name) is not None
        }
        assert used <= {sd.PAPER, sd.INK, sd.STAMP, sd.LINE_STRONG, HATCH}, case["name"]
        # Chrome only: Muted for the stamp, Line strong for the panel's edge.
        muted = [e for e in root.iter() if sd.STAMP in (e.get("fill"), e.get("stroke"))]
        assert [(e.tag.split("}")[1], e.text) for e in muted] == [("text", "written 23:59 UTC")]
        edge = [e for e in root.iter() if sd.LINE_STRONG in (e.get("fill"), e.get("stroke"))]
        assert [(e.tag.split("}")[1], e.get("stroke")) for e in edge] == [("rect", sd.LINE_STRONG)]


def test_fr011_every_line_names_the_brand_font_stack_and_holds_its_width():
    assert sd.FONT == "IBM Plex Mono, DejaVu Sans Mono, Consolas, monospace"
    for case in VECTORS:
        for line in read(render_svg(case["lines"], written_at=WRITTEN)).lines:
            # The same span in whichever of these fonts the viewer has, so the
            # layout (and the strike) does not depend on DejaVu being there.
            assert line.element.get("font-family") == sd.FONT
            assert int(line.element.get("textLength")) == sd.text_width(line.text, line.size)


# --- names for a screen reader ---------------------------------------------------


@pytest.mark.parametrize("case", VECTORS, ids=VECTOR_IDS)
def test_fr011_title_is_the_joined_lines(case):
    lines = case["lines"]
    root = ET.fromstring(render_svg(lines))
    assert root.get("role") == "img"
    assert root.find("svg:title", NS).text == " / ".join(lines)
    assert root.get("aria-label") == " / ".join(lines) == sd.default_title(lines)
    assert root.find("svg:desc", NS).text.split("\n") == lines
    assert list(root)[0].tag.endswith("title")  # read first


def test_fr011_title_and_desc_are_escaped_and_a_given_title_still_wins():
    lines = ['IN RANGE <b> & "x"', "a < b"]
    root = ET.fromstring(render_svg(lines))
    assert root.find("svg:title", NS).text == 'IN RANGE <b> & "x" / a < b'
    assert root.get("aria-label") == 'IN RANGE <b> & "x" / a < b'
    assert root.find("svg:desc", NS).text.split("\n") == lines
    named = ET.fromstring(render_svg(lines, title="Bedside panel"))
    assert named.find("svg:title", NS).text == named.get("aria-label") == "Bedside panel"


def test_fr011_no_scripts_and_no_links():
    hostile = ['<a href="javascript:x">', "javascript:alert(1)", "<script>x</script>"]
    screens = [case["lines"] for case in VECTORS] + [hostile]
    allowed = {"svg", "title", "desc", "defs", "pattern", "rect", "line", "text"}
    for lines in screens:
        for written_at in (None, WRITTEN):
            svg = render_svg(lines, written_at=written_at, title=hostile[0])
            root = ET.fromstring(svg)
            for element in root.iter():
                assert element.tag.split("}")[1] in allowed
                for name, value in element.attrib.items():
                    assert "href" not in name.lower()
                    assert not name.lower().startswith("on")
                    assert "url(" not in value or value == HATCH
            assert "<script" not in svg and "<a " not in svg


# --- the docs gallery ------------------------------------------------------------


_spec = importlib.util.spec_from_file_location(
    "gallery", ROOT / "tools" / "gen_display_gallery.py"
)
gallery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gallery)


def test_fr011_gallery_alt_text_reads_the_real_lines():
    doc = (ROOT / "docs" / "DISPLAY_STATES.md").read_text(encoding="utf-8")
    heard = {}
    for case in VECTORS:
        name, lines = case["name"], case["lines"]
        found = re.findall(rf"!\[((?:\\.|[^\]\\])*)\]\(img/display-states/{name}\.svg\)", doc)
        assert len(found) == 1, name
        (alt,) = found
        assert alt == gallery.markdown_alt(sd.default_title(lines))
        heard[name] = re.sub(r"\\(.)", r"\1", alt)  # what a reader hears
        assert heard[name] == " / ".join(lines)
        svg = (ROOT / "docs" / "img" / "display-states" / f"{name}.svg").read_text("utf-8")
        assert ET.fromstring(svg).find("svg:title", NS).text == heard[name]
    # The IN RANGE rows no longer all read "IN RANGE": each says its own number and age.
    in_range = {heard[c["name"]] for c in VECTORS if c["level"] == "IN RANGE"}
    assert len(in_range) > 1 and "IN RANGE" not in in_range


def test_fr011_gallery_alt_text_escapes_markdown_and_table_syntax():
    raw = "a|b *c* _d_ [e] <f> `g` \\h & ~i~"
    escaped = gallery.markdown_alt(raw)
    assert re.sub(r"\\(.)", r"\1", escaped) == raw
    assert re.search(r"(?<!\\)[|*_\[\]<`&~]", escaped) is None
