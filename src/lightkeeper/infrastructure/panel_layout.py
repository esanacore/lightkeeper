"""Plan where every line, band and frame goes on a 1-bit e-paper panel.

The plan is whole-number arithmetic only: no floats, no `/` division and no
rounding, and every division is of a number that cannot be negative. Python,
JavaScript and C++ disagree about rounding halves (and C++ may fuse a
multiply and an add), so a float layout would move a line by a pixel on one
port and not another (proposed HAZ-016). With integers, the ports draw the
pixels `spec/panel_vectors.json` pins, exactly.

The status shape comes from the headline (`lines[0]`) alone, through
`TREATMENTS`, so classification (STALE before any range check) is never
redone here. Each status gets its word plus a 1-bit shape (docs/BRAND.md,
Keeper's Logbook):

- plain: IN RANGE.
- rule: LOW and HIGH get a 2 px rule under the headline, full content width.
- inverse: URGENT LOW and URGENT HIGH get paper glyphs on an ink band.
- stale: the inverse band, a 4 px hatched frame in the margin, and a strike
  through the `last:` line.
- dashed: NO DATA, and any headline not in the table, get a 2 px dashed
  frame in the margin: the most cautious shape.

Texture (hatch, dashes) lives only in the margin; glyphs, the band, the rule
and the strike stay inside the content box. Nothing here moves or blinks:
the plan is one still image.

Sizes, all measured invariants (tests/test_panel_layout.py):

- The headline band is one height for every level at a given panel size,
  sized from the IN RANGE headline. A longer headline is drawn narrower and
  stretched vertically to fill the same band, so STALE - DO NOT TRUST is never
  smaller than IN RANGE.
- On fresh screens the value line (`lines[1]`, the number and its arrow in
  one string) is the hero: as large as fits, but never above the headline's
  scale, so the status word is never smaller than the number.
- The age line is never below body scale; on STALE, the `last:` line is at
  body scale and never above the age line or the headline, so an old value
  is never the hero.
- When the lines do not fit the height, context shrinks first (not below
  scale 2), then the hero (not below the age), and only then the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lightkeeper.infrastructure.font5x7 import GLYPH_HEIGHT, GLYPH_WIDTH
from lightkeeper.infrastructure.panel_profiles import MAX_SIDE, MIN_HEIGHT, MIN_WIDTH

PLAIN = "plain"
RULE = "rule"
INVERSE = "inverse"
STALE = "stale"
DASHED = "dashed"

# Keyed by the exact headline text; anything else gets UNKNOWN_TREATMENT.
TREATMENTS: dict[str, str] = {
    "IN RANGE": PLAIN,
    "LOW": RULE,
    "HIGH": RULE,
    "URGENT LOW": INVERSE,
    "URGENT HIGH": INVERSE,
    "STALE - DO NOT TRUST": STALE,
    "NO DATA": DASHED,
}
UNKNOWN_TREATMENT = DASHED
FRESH = frozenset({PLAIN, RULE, INVERSE})

# The band height is sized from this headline, the same for every level.
REFERENCE_HEADLINE = "IN RANGE"

# Line roles, in glance order: status, value, age, context, then the stamp.
HEADLINE = "headline"
VALUE = "value"
LAST = "last"
AGE = "age"
CONTEXT = "context"
STAMP = "stamp"

BAND_PAD = 2  # around the headline glyphs, inside the band
RULE_THICKNESS = 2
HATCH_WIDTH = 4
HATCH_PITCH = 4  # one inked diagonal every 4 px
DASH_WIDTH = 2
DASH_ON = 4
DASH_OFF = 4
MIN_GAP = 2  # least space above, between and below the lines under the band
READABLE_SCALE = 2  # context shrinks to this before the hero shrinks at all
RESERVED_BODY_LINES = 3  # a four-line screen has three lines under the band
CAP_ROWS = GLYPH_HEIGHT - 1  # glyph rows above the baseline; the last is for descenders
STAMP_MIN_SCALE = 2

_STAMP_TEXT = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


@dataclass(frozen=True)
class Box:
    """A rectangle in panel pixels: top-left corner, width and height."""

    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class PlacedText:
    """One line of text where it is drawn.

    `scale` is the width of a glyph cell in pixels and `tall` its height;
    they differ only for a headline narrowed to fit the band.
    """

    text: str
    role: str
    x: int
    y: int
    scale: int
    tall: int
    width: int
    height: int

    @property
    def box(self) -> Box:
        """The glyph cells this line covers, descender row included."""
        return Box(self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class Frame:
    """A texture ring in the margin: `box` is its outer edge."""

    kind: str  # STALE draws a hatch, DASHED a dashed line
    box: Box
    thickness: int


@dataclass(frozen=True)
class PanelPlan:
    """Everything the drawer needs, in whole pixels."""

    width: int
    height: int
    margin: int
    treatment: str
    content: Box
    band: Box
    band_scale: int
    headline: PlacedText
    lines: tuple[PlacedText, ...]
    stamp: PlacedText | None
    ink_band: Box | None  # filled with ink, with the headline drawn in paper on it
    rule: Box | None
    strike: Box | None
    frame: Frame | None


@dataclass
class _Sizes:
    """Scales of the lines under the band while they are fitted to the height."""

    value: int
    age: int
    small: int  # the `last:` line and the context lines

    def of(self, role: str) -> int:
        """Return the scale a line with `role` is drawn at."""
        if role == VALUE:
            return self.value
        if role == AGE:
            return self.age
        return self.small


def treatment(headline: str) -> str:
    """Return the shape for a headline; an unknown one gets the cautious dashed frame."""
    return TREATMENTS.get(headline, UNKNOWN_TREATMENT)


def glyph_gap(scale: int) -> int:
    """Space between characters: at least one pixel, wider at large sizes."""
    return max(1, scale // 2)


def text_width(text: str, scale: int) -> int:
    """Width in pixels of `text` drawn at `scale`."""
    if not text:
        return 0
    return len(text) * GLYPH_WIDTH * scale + (len(text) - 1) * glyph_gap(scale)


def fit_scale(lines: list[str], usable_width: int, max_scale: int) -> int:
    """Largest whole-number scale (up to `max_scale`) at which every line fits."""
    for scale in range(max_scale, 1, -1):
        if all(text_width(line, scale) <= usable_width for line in lines):
            return scale
    return 1


def margin(height: int) -> int:
    """Clear space on every side: 6% of the height, rounded half up, at least 4 px."""
    return max(4, (height * 6 + 50) // 100)


def headline_cap(height: int) -> int:
    """Return the largest headline scale for a panel this tall."""
    return max(4, height // 32)


def body_cap(band_scale: int) -> int:
    """Return the largest age and context scale: about half the headline, at least 3."""
    return min(band_scale, max(3, band_scale // 2))


def stamp_scale(height: int) -> int:
    """Return the stamp's scale: 2, or more on tall panels."""
    return max(STAMP_MIN_SCALE, height // 240)


def check_stamp(stamp: str) -> None:
    """Refuse anything but a 24-hour `HH:MM`."""
    if not _STAMP_TEXT.fullmatch(stamp):
        raise ValueError(f"stamp must be a 24-hour HH:MM, got {stamp!r}")


def roles_for(kind: str, count: int) -> list[str]:
    """Return the role of each of the `count` lines under the headline."""
    if kind in FRESH:
        first = [VALUE, AGE]
    elif kind == STALE:
        first = [LAST, AGE]
    else:
        first = []
    return [first[i] if i < len(first) else CONTEXT for i in range(count)]


def plan_panel(lines: list[str], width: int, height: int, stamp: str | None = None) -> PanelPlan:
    """Lay out `lines` on a `width` x `height` panel.

    `stamp`, when given, is an `HH:MM` drawn right-aligned on the age row, or
    along the bottom of the content box when the age row has no room for it.
    Either way its space is reserved, so it never touches another line.
    """
    if not (MIN_WIDTH <= width <= MAX_SIDE and MIN_HEIGHT <= height <= MAX_SIDE):
        raise ValueError(
            f"panel must be at least {MIN_WIDTH}x{MIN_HEIGHT} pixels "
            f"and at most {MAX_SIDE} on a side"
        )
    if not lines:
        raise ValueError("nothing to draw: lines is empty")
    if stamp is not None:
        check_stamp(stamp)

    edge = margin(height)
    content = Box(edge, edge, width - 2 * edge, height - 2 * edge)
    kind = treatment(lines[0])
    stamp_size = stamp_scale(height)
    strip = GLYPH_HEIGHT * stamp_size + MIN_GAP if stamp is not None else 0

    # The band: one height per panel, sized from IN RANGE. It leaves room for
    # a four-line screen at scale 1 (and the stamp), so even a tiny panel
    # never overlaps its lines.
    inner = content.w - 2 * BAND_PAD
    reserve = RESERVED_BODY_LINES * GLYPH_HEIGHT + (RESERVED_BODY_LINES + 1) * MIN_GAP + strip
    tallest = max(0, content.h - 2 * BAND_PAD - reserve) // GLYPH_HEIGHT
    band_scale = fit_scale([REFERENCE_HEADLINE], inner, max(1, min(headline_cap(height), tallest)))
    band = Box(content.x, content.y, content.w, 2 * BAND_PAD + GLYPH_HEIGHT * band_scale)
    head_scale = fit_scale([lines[0]], inner, band_scale)
    headline = PlacedText(
        text=lines[0],
        role=HEADLINE,
        x=band.x + BAND_PAD,
        y=band.y + BAND_PAD,
        scale=head_scale,
        tall=band_scale,
        width=text_width(lines[0], head_scale),
        height=GLYPH_HEIGHT * band_scale,
    )

    body = lines[1:]
    roles = roles_for(kind, len(body))
    by_role = {role: [t for t, r in zip(body, roles, strict=True) if r == role] for role in roles}
    value_lines = by_role.get(VALUE, [])
    age_lines = by_role.get(AGE, [])
    small_lines = by_role.get(LAST, []) + by_role.get(CONTEXT, [])

    # Widest that fits: the hero up to the headline, the age up to the hero,
    # the rest up to the age (and, on STALE, up to the headline as well).
    cap = body_cap(band_scale)
    value = fit_scale(value_lines, content.w, head_scale)
    age = fit_scale(age_lines, content.w, min(cap, value) if value_lines else cap)
    small_cap = min(cap, age) if age_lines else cap
    if kind == STALE:
        small_cap = min(small_cap, head_scale)
    sizes = _Sizes(value, age, fit_scale(small_lines, content.w, small_cap))

    # The stamp sits at the right of the age row when it fits there beside
    # the age and a one-character gap; otherwise it gets the bottom strip.
    stamp_chars = "" if stamp is None else stamp
    on_age_row = bool(stamp_chars and age_lines) and (
        text_width(age_lines[0], age) + GLYPH_WIDTH * age + text_width(stamp_chars, stamp_size)
        <= content.w
    )
    top = band.y + band.h
    bottom = content.y + content.h - (strip if stamp_chars and not on_age_row else 0)

    def row_scales() -> list[int]:
        """Each line's row height in glyph cells: the age row is as tall as its stamp."""
        return [
            max(sizes.of(role), stamp_size) if role == AGE and on_age_row else sizes.of(role)
            for role in roles
        ]

    # Shrink in glance order until the lines and their gaps fit the height:
    # context to a readable 2, the hero down to the age, then context to 1,
    # then the age. Only panels far smaller than the profiles reach the end.
    gaps = len(body) + 1
    while GLYPH_HEIGHT * sum(row_scales()) + gaps * MIN_GAP > bottom - top:
        if small_lines and sizes.small > READABLE_SCALE:
            sizes.small -= 1
        elif value_lines and sizes.value > (sizes.age if age_lines else 1):
            sizes.value -= 1
        elif small_lines and sizes.small > 1:
            sizes.small -= 1
        elif age_lines and sizes.age > 1:
            sizes.age -= 1
        else:
            break  # still too tall: the panel edge clips the bottom

    rows = row_scales()
    gap = max(0, bottom - top - GLYPH_HEIGHT * sum(rows)) // gaps
    placed = []
    stamp_line = None
    y = top + gap
    for text, role, row in zip(body, roles, rows, strict=True):
        scale = sizes.of(role)
        # Text sharing a row shares its baseline.
        placed.append(_place(text, role, content.x, y + CAP_ROWS * (row - scale), scale))
        if role == AGE and on_age_row:
            stamp_y = y + CAP_ROWS * (row - stamp_size)
            stamp_line = _place_right(stamp_chars, content.x + content.w, stamp_y, stamp_size)
        y += GLYPH_HEIGHT * row + gap
    if stamp_chars and not on_age_row:
        stamp_y = content.y + content.h - GLYPH_HEIGHT * stamp_size
        stamp_line = _place_right(stamp_chars, content.x + content.w, stamp_y, stamp_size)

    return PanelPlan(
        width=width,
        height=height,
        margin=edge,
        treatment=kind,
        content=content,
        band=band,
        band_scale=band_scale,
        headline=headline,
        lines=tuple(placed),
        stamp=stamp_line,
        ink_band=band if kind in (INVERSE, STALE) else None,
        rule=(
            Box(content.x, band.y + band.h - RULE_THICKNESS, content.w, RULE_THICKNESS)
            if kind == RULE
            else None
        ),
        # Under a STALE headline the first line is always the `last:` line.
        strike=strike_box(placed[0]) if kind == STALE and placed else None,
        frame=_frame(kind, edge, width, height),
    )


def _place(text: str, role: str, x: int, y: int, scale: int) -> PlacedText:
    """Place a line of text at `scale`, its top-left corner at (x, y)."""
    return PlacedText(
        text, role, x, y, scale, scale, text_width(text, scale), GLYPH_HEIGHT * scale
    )


def _place_right(text: str, right: int, y: int, scale: int) -> PlacedText:
    """Place the stamp with its right edge at `right`."""
    return _place(text, STAMP, right - text_width(text, scale), y, scale)


def strike_box(line: PlacedText) -> Box:
    """Return a rule through the middle of the line's capitals, across its full width.

    1 px thick at scale 2 or less, 2 px from scale 3.
    """
    thickness = 1 if line.scale <= 2 else 2
    middle = line.y + (CAP_ROWS * line.scale) // 2 - thickness // 2
    return Box(line.x, middle, line.width, thickness)


def _frame(kind: str, edge: int, width: int, height: int) -> Frame | None:
    """Return the texture ring for STALE or DASHED, centred in the margin."""
    if kind not in (STALE, DASHED):
        return None
    thickness = HATCH_WIDTH if kind == STALE else DASH_WIDTH
    inset = (edge - thickness) // 2  # the margin is at least 4, so never negative
    return Frame(kind, Box(inset, inset, width - 2 * inset, height - 2 * inset), thickness)
