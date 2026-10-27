"""FR-007 and FR-016: the integer-only panel layout keeps its safety invariants at every size.

"STALE is never weaker than IN RANGE" and "an old value is never the hero" are
measured here at all six panel profiles, not left as comments.
"""

import ast
import dataclasses
import json
import typing
from pathlib import Path

import pytest

from lightkeeper.domain.status import Level
from lightkeeper.infrastructure import epaper_bitmap as eb
from lightkeeper.infrastructure import panel_layout as pl
from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT
from lightkeeper.infrastructure.panel_profiles import (
    ALIASES,
    DEFAULT_PROFILE,
    PROFILES,
    PanelProfile,
    resolve,
)

ROOT = Path(__file__).parent.parent
VECTORS = json.loads((ROOT / "spec" / "display_vectors.json").read_text())["cases"]
PROFILE_IDS = list(PROFILES)


def plans(profile, stamp=None):
    """(vector, plan) for every display vector at `profile`."""
    size = PROFILES[profile]
    return [(c, pl.plan_panel(c["lines"], size.width, size.height, stamp)) for c in VECTORS]


def by_role(plan, role):
    return [line for line in plan.lines if line.role == role]


def walk(value):
    """Every dataclass instance reachable from `value`."""
    if dataclasses.is_dataclass(value):
        yield value
        for f in dataclasses.fields(value):
            yield from walk(getattr(value, f.name))
    elif isinstance(value, tuple):
        for item in value:
            yield from walk(item)


# --- Integer-only ------------------------------------------------------------


@pytest.mark.parametrize("module", ["panel_layout.py", "epaper_bitmap.py"])
def test_fr016_layout_is_integer_only(module):
    source = (ROOT / "src" / "lightkeeper" / "infrastructure" / module).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), (
            f"float literal at line {node.lineno}"
        )
        if isinstance(node, ast.BinOp | ast.AugAssign):
            assert not isinstance(node.op, ast.Div), f"'/' division at line {node.lineno}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"round", "float"}, f"{node.func.id}() at {node.lineno}"
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = {a.name for a in node.names} | {getattr(node, "module", None)}
            assert not names & {"math", "fractions", "decimal"}, f"import at {node.lineno}"


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr016_every_plan_field_is_an_int(profile):
    for stamp in (None, "02:14"):
        for _, plan in plans(profile, stamp):
            for node in walk(plan):
                hints = typing.get_type_hints(type(node))
                for f in dataclasses.fields(node):
                    value = getattr(node, f.name)
                    assert not isinstance(value, float), f.name
                    if hints[f.name] is int:
                        assert type(value) is int, (type(node).__name__, f.name, value)


# --- Treatments --------------------------------------------------------------


def test_fr007_every_vector_headline_has_a_treatment():
    # The vectors reach every level, so every headline the display can show is here.
    assert {c["level"] for c in VECTORS} == {level.value for level in Level}
    for case in VECTORS:
        assert case["lines"][0] in pl.TREATMENTS, case["name"]
    assert pl.TREATMENTS == {
        "IN RANGE": pl.PLAIN,
        "LOW": pl.RULE,
        "HIGH": pl.RULE,
        "URGENT LOW": pl.INVERSE,
        "URGENT HIGH": pl.INVERSE,
        "STALE - DO NOT TRUST": pl.STALE,
        "NO DATA": pl.DASHED,
    }


@pytest.mark.parametrize("headline", ["IN RANGE ", "in range", "STALE", "", "HIGH!", "OK"])
def test_fr007_unknown_headline_gets_the_cautious_dashed_frame(headline):
    plan = pl.plan_panel([headline, "120 mg/dL ->", "3 min ago"], 296, 128)
    assert pl.treatment(headline) == pl.DASHED
    assert plan.treatment == pl.DASHED
    assert plan.frame is not None and plan.frame.kind == pl.DASHED
    assert (plan.ink_band, plan.rule, plan.strike) == (None, None, None)
    # No hero: a number under an unknown headline is drawn as plain context.
    assert [line.role for line in plan.lines] == [pl.CONTEXT, pl.CONTEXT]
    assert len({line.scale for line in plan.lines}) == 1


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_each_treatment_draws_only_its_own_marks(profile):
    for case, plan in plans(profile):
        kind = pl.treatment(case["lines"][0])
        assert plan.treatment == kind
        assert (plan.rule is not None) == (kind == pl.RULE)
        assert (plan.ink_band is not None) == (kind in (pl.INVERSE, pl.STALE))
        assert (plan.strike is not None) == (kind == pl.STALE)
        assert (plan.frame is not None) == (kind in (pl.STALE, pl.DASHED))
        if plan.frame is not None:
            assert plan.frame.kind == kind
        if plan.rule is not None:
            # Full content width, right under the headline, inside the band.
            assert (plan.rule.x, plan.rule.w) == (plan.content.x, plan.content.w)
            assert plan.rule.y + plan.rule.h == plan.band.y + plan.band.h
            assert plan.rule.y >= plan.headline.y + plan.headline.height


# --- Sizes and hierarchy -----------------------------------------------------


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_headline_band_same_height_for_every_level(profile):
    bands = set()
    for stamp in (None, "02:14"):
        for _, plan in plans(profile, stamp):
            assert plan.headline.tall == plan.band_scale
            assert plan.band.h == 2 * pl.BAND_PAD + GLYPH_HEIGHT * plan.band_scale
            assert plan.headline.height == GLYPH_HEIGHT * plan.band_scale
            bands.add((plan.band, plan.headline.y))
    assert len(bands) == 1, bands


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_stale_never_weaker_across_panel_sizes(profile):
    size = PROFILES[profile]
    in_range = eb.render_bitmap(["IN RANGE", "112 mg/dL ->", "3 min ago"], size.width, size.height)
    in_range_plan = pl.plan_panel(["IN RANGE"], size.width, size.height)
    band = in_range_plan.band
    in_range_rows = [
        y
        for y in range(band.y, band.y + band.h)
        if any(in_range.is_ink(x, y) for x in range(band.x, band.x + band.w))
    ]
    in_range_height = in_range_rows[-1] - in_range_rows[0] + 1
    stale_cases = [(c, p) for c, p in plans(profile) if c["level"] == "STALE"]
    assert stale_cases
    for case, plan in stale_cases:
        bitmap = eb.draw_plan(plan)
        assert plan.ink_band == plan.band
        # The inverse band, measured in pixels down its padded left edge.
        x, top = plan.band.x, plan.band.y
        assert not bitmap.is_ink(x, top - 1)
        run = 0
        while bitmap.is_ink(x, top + run):
            run += 1
        assert run == plan.band.h
        assert run >= in_range_height, case["name"]
        inked = sum(
            bitmap.is_ink(bx, by)
            for by in range(plan.band.y, plan.band.y + plan.band.h)
            for bx in range(plan.band.x, plan.band.x + plan.band.w)
        )
        assert inked * 100 >= 40 * plan.band.w * plan.band.h, case["name"]
        # The STALE word is never shorter than IN RANGE's.
        assert plan.headline.height == in_range_plan.headline.height


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_value_line_is_hero_but_never_above_headline(profile):
    fresh = [(c, p) for c, p in plans(profile) if p.treatment in pl.FRESH]
    assert len(fresh) == len([c for c in VECTORS if c["level"] not in ("STALE", "NO DATA")])
    for case, plan in fresh:
        (value,) = by_role(plan, pl.VALUE)
        (age,) = by_role(plan, pl.AGE)
        assert value.text == case["lines"][1]
        assert age.scale <= value.scale <= plan.headline.scale, case["name"]
        assert all(line.scale <= value.scale for line in plan.lines), case["name"]


def test_fr007_value_line_takes_the_headline_scale_at_296x128():
    plan = pl.plan_panel(["IN RANGE", "112 mg/dL ->", "3 min ago"], 296, 128)
    assert (plan.headline.scale, plan.lines[0].text, plan.lines[0].scale) == (
        4,
        "112 mg/dL ->",
        4,
    )
    assert plan.lines[1].scale == 3


def test_fr007_in_range_headline_fills_half_the_width_at_800x480():
    plan = pl.plan_panel(["IN RANGE", "112 mg/dL ->", "3 min ago"], 800, 480)
    assert plan.headline.width * 2 >= plan.content.w


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_stale_last_line_never_the_hero(profile):
    for case, plan in plans(profile):
        if case["level"] != "STALE":
            assert not by_role(plan, pl.LAST)
            continue
        (last,) = by_role(plan, pl.LAST)
        (age,) = by_role(plan, pl.AGE)
        assert last.text == case["lines"][1] and last.text.startswith("last: ")
        assert last.scale <= age.scale, case["name"]
        assert last.scale <= plan.headline.scale, case["name"]
        # At body scale: the same size as the context lines, never larger.
        assert all(line.scale == last.scale for line in by_role(plan, pl.CONTEXT))
        assert last.scale == min(line.scale for line in plan.lines)


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_age_line_never_below_body(profile):
    for case, plan in plans(profile):
        ages = by_role(plan, pl.AGE)
        if case["level"] == "NO DATA":
            assert not ages
            continue
        (age,) = ages
        body = by_role(plan, pl.CONTEXT) + by_role(plan, pl.LAST)
        assert all(age.scale >= line.scale for line in body), case["name"]


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_strike_crosses_last_line_only(profile):
    for case, plan in plans(profile):
        if plan.treatment != pl.STALE:
            assert plan.strike is None
            continue
        (last,) = by_role(plan, pl.LAST)
        strike = plan.strike
        assert (strike.x, strike.w) == (last.x, last.width)
        assert strike.h == (1 if last.scale <= 2 else 2)
        # Through the capitals, never into the descender row or another line.
        assert last.y <= strike.y and strike.y + strike.h <= last.y + pl.CAP_ROWS * last.scale
        # The strike adds ink only inside its own box.
        struck = eb.draw_plan(plan)
        clean = eb.draw_plan(dataclasses.replace(plan, strike=None))
        changed = {
            (i % plan.width, i // plan.width)
            for i, (a, b) in enumerate(zip(struck.ink, clean.ink, strict=True))
            if a != b
        }
        assert changed, case["name"]
        assert all(
            strike.x <= x < strike.x + strike.w and strike.y <= y < strike.y + strike.h
            for x, y in changed
        )
        assert all(struck.ink[i] >= clean.ink[i] for i in range(len(clean.ink)))


def test_fr007_digits_stay_distinct_under_strike():
    scales = {
        line.scale
        for profile in PROFILE_IDS
        for stamp in (None, "02:14")
        for _, plan in plans(profile, stamp)
        for line in by_role(plan, pl.LAST)
    }
    assert 1 in scales and 2 in scales and max(scales) >= 3
    for scale in sorted(scales):
        drawn = set()
        for digit in "0123456789":
            line = pl.PlacedText(
                digit, pl.LAST, 0, 0, scale, scale, pl.text_width(digit, scale), 8 * scale
            )
            bitmap = eb.Bitmap(line.width, line.height)
            eb.draw_text(bitmap, digit, 0, 0, scale)
            strike = pl.strike_box(line)
            bitmap.fill(strike.x, strike.y, strike.w, strike.h)
            drawn.add(bytes(bitmap.ink))
        assert len(drawn) == 10, f"two digits look the same under the strike at scale {scale}"


@pytest.mark.parametrize("profile", PROFILE_IDS)
def test_fr007_lines_keep_their_order_and_never_overlap(profile):
    for stamp in (None, "02:14"):
        for case, plan in plans(profile, stamp):
            assert [plan.headline.text] + [line.text for line in plan.lines] == case["lines"]
            boxes = [plan.band] + [line.box for line in plan.lines]
            for upper, lower in zip(boxes, boxes[1:], strict=False):
                assert upper.y + upper.h + pl.MIN_GAP <= lower.y, case["name"]
            assert boxes[-1].y + boxes[-1].h <= plan.content.y + plan.content.h


@pytest.mark.parametrize(
    ("profile", "margin", "band_scale"),
    [
        ("waveshare_2in9", 8, 4),
        ("waveshare_1in54", 12, 3),
        ("waveshare_2in13", 7, 4),
        ("waveshare_4in2", 18, 8),
        ("waveshare_7in5", 29, 15),
        ("kindle", 48, 11),
    ],
)
def test_fr016_profile_margins_and_band_scales_are_pinned(profile, margin, band_scale):
    size = PROFILES[profile]
    plan = pl.plan_panel(["IN RANGE"], size.width, size.height)
    assert pl.margin(size.height) == plan.margin == margin
    assert plan.band_scale == band_scale <= pl.headline_cap(size.height)
    assert plan.content == pl.Box(
        margin, margin, size.width - 2 * margin, size.height - 2 * margin
    )


def test_fr016_margin_is_six_percent_rounded_half_up():
    assert [pl.margin(h) for h in (60, 74, 75, 128, 125, 141, 142)] == [4, 4, 5, 8, 8, 8, 9]
    assert [pl.headline_cap(h) for h in (60, 128, 159, 160, 480, 800)] == [4, 4, 4, 5, 15, 25]
    assert [pl.body_cap(s) for s in (1, 2, 3, 4, 8, 15)] == [1, 2, 3, 3, 4, 7]
    sizes = [(157, 70), (296, 128), (800, 479), (800, 480), (600, 800), (4096, 4096)]
    assert [pl.stamp_scale(w, h) for w, h in sizes] == [2, 2, 2, 2, 3, 17]


def test_haz014_stamp_scale_never_outgrows_a_narrow_content_box():
    # 2000 // 240 asks for 8, which is 216 px wide; the content box is 154.
    content = 394 - 2 * pl.margin(2000)
    assert pl.text_width(pl.STAMP_SAMPLE, 2000 // 240) > content
    assert pl.stamp_scale(394, 2000) == 5
    assert pl.text_width(pl.STAMP_SAMPLE, 5) <= content < pl.text_width(pl.STAMP_SAMPLE, 6)
    stamp = pl.plan_panel(["NO DATA", "Check sensor and phone"], 394, 2000, "23:59").stamp
    assert stamp.x >= pl.margin(2000) and stamp.scale == 5


# --- Fitting the height on panels far smaller than the profiles ---------------

FOUR = ["IN RANGE", "101 mg/dL ->", "7 min ago", "Nightscout unreachable"]


def scales(plan):
    return [(line.role, line.scale) for line in plan.lines]


def test_fr007_context_shrinks_before_the_hero():
    # At 296x128 the context is already at 2, so the hero gives up one step,
    # never below the age, and the age keeps its size.
    plan = pl.plan_panel(FOUR, 296, 128)
    assert scales(plan) == [(pl.VALUE, 3), (pl.AGE, 3), (pl.CONTEXT, 2)]
    # Without the context line, the hero keeps the headline scale.
    assert scales(pl.plan_panel(FOUR[:3], 296, 128)) == [(pl.VALUE, 4), (pl.AGE, 3)]


@pytest.mark.parametrize(
    ("width", "height", "stamp", "band_scale"),
    [(400, 70, None, 3), (157, 70, None, 3), (296, 70, None, 3), (157, 70, "02:14", 1)],
)
def test_fr007_tiny_panels_shrink_everything_but_the_status(width, height, stamp, band_scale):
    plan = pl.plan_panel(FOUR, width, height, stamp)
    assert plan.band_scale == band_scale
    assert scales(plan) == [(pl.VALUE, 1), (pl.AGE, 1), (pl.CONTEXT, 1)]
    boxes = [plan.band] + [line.box for line in plan.lines]
    for upper, lower in zip(boxes, boxes[1:], strict=False):
        assert upper.y + upper.h <= lower.y
    assert boxes[-1].y + boxes[-1].h <= plan.content.y + plan.content.h


def test_fr007_a_two_line_fresh_screen_has_a_hero_and_no_age():
    plan = pl.plan_panel(["IN RANGE", "112 mg/dL ->"], 296, 128)
    assert scales(plan) == [(pl.VALUE, 4)]
    tiny = pl.plan_panel(["IN RANGE", "112 mg/dL ->"], 157, 70, "02:14")
    assert scales(tiny) == [(pl.VALUE, 1)]


def test_fr007_too_many_lines_for_a_tiny_panel_are_clipped_not_refused():
    # Six lines under the headline: more than any screen has, so the size check
    # does not cover them, and the bottom ones are clipped rather than refused.
    lines = ["NO DATA", "a", "b", "c", "d", "e", "f"]
    plan = pl.plan_panel(lines, 157, 70)
    assert [line.scale for line in plan.lines] == [1] * 6
    assert plan.lines[-1].y + plan.lines[-1].height > plan.content.y + plan.content.h
    bitmap = eb.render_bitmap(lines, 157, 70)
    assert bitmap.width == 157


def test_fr007_stale_with_no_lines_under_it_has_no_strike():
    plan = pl.plan_panel(["STALE - DO NOT TRUST"], 296, 128)
    assert plan.lines == () and plan.strike is None and plan.ink_band == plan.band


# --- Input checks --------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "reason"),
    [
        (99, 128, "too narrow"),
        (164, 128, "too narrow"),
        (128, 296, "too narrow"),  # the 2.9" panel mounted in portrait
        (100, 600, "too narrow"),
        (100, 4096, "too narrow"),
        (120, 80, "too narrow"),
        (296, 59, "too short"),
        (296, 69, "too short"),
        (4097, 128, "1 to 4096 pixels on a side"),
        (296, 4097, "1 to 4096 pixels on a side"),
        (0, 128, "1 to 4096 pixels on a side"),
        (296, -128, "1 to 4096 pixels on a side"),
    ],
)
def test_fr007_plan_refuses_impossible_panels(width, height, reason):
    with pytest.raises(ValueError, match=f"panel {width}x{height} (is|must be) {reason}"):
        pl.plan_panel(["NO DATA"], width, height)


@pytest.mark.parametrize("stamp", ["2:14", "24:00", "12:60", "ab:cd", "12:345", " 2:14", ""])
def test_haz014_stamp_must_be_24_hour_hh_mm(stamp):
    with pytest.raises(ValueError, match="HH:MM"):
        pl.plan_panel(["NO DATA"], 296, 128, stamp)


# --- Panel profiles ----------------------------------------------------------


def test_fr016_profiles_resolve_by_name_alias_or_size():
    assert DEFAULT_PROFILE == "waveshare_2in9"
    assert resolve(DEFAULT_PROFILE) == PanelProfile(
        "waveshare_2in9",
        eb.DEFAULT_WIDTH,
        eb.DEFAULT_HEIGHT,
        PROFILES[DEFAULT_PROFILE].description,
    )
    assert {name: (p.width, p.height) for name, p in PROFILES.items()} == {
        "waveshare_2in9": (296, 128),
        "waveshare_1in54": (200, 200),
        "waveshare_2in13": (250, 122),
        "waveshare_4in2": (400, 300),
        "waveshare_7in5": (800, 480),
        "kindle": (600, 800),
    }
    assert ALIASES == {"trmnl": "waveshare_7in5"}
    assert resolve(" TRMNL ") is PROFILES["waveshare_7in5"]
    assert resolve("Kindle") is PROFILES["kindle"]
    custom = resolve("320x240")
    assert (custom.name, custom.width, custom.height) == ("320x240", 320, 240)
    assert resolve("157x70").width == 157  # the smallest panel accepted at all


@pytest.mark.parametrize("spec", ["", "waveshare", "296", "296x", "x128", "29.6x128", "-296x128"])
def test_fr016_unknown_profile_names_the_choices(spec):
    with pytest.raises(ValueError, match="waveshare_2in9.*trmnl.*296x128"):
        resolve(spec)


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        (
            "99x128",
            "is too narrow: at 128 px tall the margins take 16 px, and 'Confirm on "
            "primary device' needs 149 px between them, 165 px in all",
        ),
        ("128x296", "is too narrow: at 296 px tall the margins take 36 px"),
        ("100x600", "is too narrow"),
        ("100x4096", "is too narrow: .* 641 px in all"),
        ("120x80", "is too narrow"),
        ("100x60", "is too narrow"),
        (
            "296x59",
            "is too short: the margins take 8 px, and the headline band and a "
            "four-line screen with its stamp need 62 px between them",
        ),
        ("296x69", "is too short"),
        ("4097x480", "must be 1 to 4096 pixels on a side"),
        ("800x99999", "must be 1 to 4096 pixels on a side"),
        ("0x0", "must be 1 to 4096 pixels on a side"),
    ],
)
def test_fr016_custom_size_must_be_drawable(spec, reason):
    with pytest.raises(ValueError, match=f"^panel {spec} {reason}"):
        resolve(spec)


# --- Every size resolve accepts ------------------------------------------------

# The widest line any display vector shows, at scale 1: what the size check
# must leave room for between the margins.
WIDEST = max(pl.text_width(line, 1) for case in VECTORS for line in case["lines"])


def narrowest(height):
    """Return the narrowest panel this tall whose content box holds the widest line at 1."""
    return 2 * pl.margin(height) + WIDEST


def test_fr016_size_limits_come_from_the_widest_screen_line():
    assert any(pl.WIDEST_LINE in case["lines"] for case in VECTORS)
    assert WIDEST == pl.text_width(pl.WIDEST_LINE, 1) == pl.min_content_width() == 149
    # Every headline fits inside the band's padding at that width.
    assert all(pl.text_width(h, 1) + 2 * pl.BAND_PAD <= WIDEST for h in pl.TREATMENTS)
    # At every height, one pixel narrower than the widest line needs is refused.
    for height in range(70, pl.MAX_SIDE + 1):
        width = narrowest(height)
        assert resolve(f"{width}x{height}").width == width
        with pytest.raises(ValueError, match="too narrow"):
            resolve(f"{width - 1}x{height}")
    # The shortest panel holds the band and a four-line screen with its stamp.
    for width in (narrowest(69), 296, pl.MAX_SIDE):
        assert resolve(f"{width}x70").height == 70
        with pytest.raises(ValueError, match="too short"):
            resolve(f"{width}x69")
    assert 70 - 2 * pl.margin(70) == pl.min_content_height(296, 70) == 62


def apart(a, b):
    """Report whether two boxes share no pixel."""
    return a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y


def within(outer, box):
    """Report whether `box` lies wholly inside `outer`."""
    return (
        outer.x <= box.x
        and box.x + box.w <= outer.x + outer.w
        and outer.y <= box.y
        and box.y + box.h <= outer.y + outer.h
    )


SWEEP_HEIGHTS = [70, 71, 74, 75, 99, 122, 128, 141, 142, 200, 239, 240, 296, 300, 479, 480]
SWEEP_HEIGHTS += [600, 800, 1000, 1500, 2000, 2500, 3000, 3500, 4095, 4096]


@pytest.mark.parametrize("height", SWEEP_HEIGHTS)
def test_fr007_every_accepted_size_keeps_every_line_inside_the_content_box(height):
    # Narrow and tall included: the narrowest width resolve accepts at this
    # height, a few just above it, and some wide ones.
    least = narrowest(height)
    widths = sorted({least, least + 1, least + 9, 2 * least, 296, 801, pl.MAX_SIDE})
    for width in (w for w in widths if least <= w <= pl.MAX_SIDE):
        assert resolve(f"{width}x{height}").width == width
        for case in VECTORS:
            for stamp in (None, "23:59"):
                plan = pl.plan_panel(case["lines"], width, height, stamp)
                where = (width, height, case["name"], stamp)
                for line in [plan.headline, *plan.lines, *([plan.stamp] if stamp else [])]:
                    assert within(plan.content, line.box), (*where, line.text)
                head = plan.headline
                assert head.x + head.width <= plan.band.x + plan.band.w - pl.BAND_PAD, where
                boxes = [plan.band] + [line.box for line in plan.lines]
                for upper, lower in zip(boxes, boxes[1:], strict=False):
                    assert upper.y + upper.h + pl.MIN_GAP <= lower.y, where
                if stamp:
                    assert plan.stamp.scale >= pl.STAMP_MIN_SCALE, where
                    assert all(apart(plan.stamp.box, box) for box in boxes), where
