"""Draw rendered display lines as an SVG image of an e-ink panel.

Used for three things: the docs gallery of every display state, the
`--svg` CLI option (handy for Home Assistant or a web dashboard), and
previewing layouts before real e-paper hardware exists.

The image is the 1-bit panel in brand colors (docs/BRAND.md): Paper and Ink,
with Muted only for the stamp and the panel's edge. Each status gets the same
shape it gets on the panel, from the same table (`panel_layout.TREATMENTS`),
drawn with plain rect, line and pattern elements, so the shape looks the same
whatever fonts the viewer has:

- plain: IN RANGE.
- rule: LOW and HIGH get a 2 px rule under the headline, full content width.
- inverse: URGENT LOW and URGENT HIGH get Paper words on an Ink band.
- stale: the Ink band, a 4 px hatched frame in the margin, and a strike
  through the `last:` line.
- dashed: NO DATA, and any headline not in the table, get a 2 px dashed
  frame in the margin: the most cautious shape.

Texture (hatch, dashes) stays in the margin, never under text. Sizes follow
the panel's rules: the headline band is one height for every level at a
given panel size; on fresh screens the value line (the number and its arrow)
is larger than the lines under it but never larger than the headline, so the
status word is never smaller than the number; the age is never smaller than
the context lines; and on STALE the `last:` line is never larger than the
age, so an old value is never the hero.

Pure standard library. The output is static SVG with no scripts or links,
and every line of text is XML-escaped, so it is safe to embed anywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from xml.sax.saxutils import escape

from lightkeeper.infrastructure.panel_layout import (
    AGE,
    BAND_PAD,
    DASH_OFF,
    DASH_ON,
    DASH_WIDTH,
    DASHED,
    HATCH_PITCH,
    HATCH_WIDTH,
    INVERSE,
    LAST,
    REFERENCE_HEADLINE,
    RULE,
    RULE_THICKNESS,
    STALE,
    VALUE,
    roles_for,
    treatment,
)

# A common small e-paper panel size (Waveshare 2.9"), in pixels.
DEFAULT_WIDTH = 296
DEFAULT_HEIGHT = 128

# Brand tokens, light theme (assets/brand/tokens.json, held there by the tests).
PAPER = "#E6E5DF"  # Paper
INK = "#15171C"  # Ink
STAMP = "#5B6068"  # Muted, 5.01:1 on Paper: the stamp and the panel's edge

# IBM Plex Mono is the brand's data face; the others are where it is missing.
FONT = "IBM Plex Mono, DejaVu Sans Mono, Consolas, monospace"
HATCH_ID = "lk-hatch"

# Monospace glyphs are about 0.6 of the font size wide, in every font in FONT.
CHAR_WIDTH_RATIO = 0.6
# A line's box is one font size tall: the baseline sits 0.8 of the way down,
# leaving the rest for descenders, and capitals are about 0.72 tall.
BASELINE_RATIO = 0.8
CAP_RATIO = 0.72

# Target font sizes and the margin, as a share of the panel height.
HEADLINE_RATIO = 0.19
VALUE_RATIO = 0.16
BODY_RATIO = 0.12
STAMP_RATIO = 0.07
MARGIN_RATIO = 0.09
STAMP_GAP = 2  # least space between the lines and the stamp under them
THICK_STRIKE_SIZE = 24  # the strike is 2 px through text this large, 1 px below

# hatch-45: one ink pixel every HATCH_PITCH along each row, where x + y is a
# multiple of the pitch, counted from the image's top-left pixel.
HATCH_CELLS = tuple(((-y) % HATCH_PITCH, y) for y in range(HATCH_PITCH))


def _fit(size: int, lines: list[str], usable_width: int) -> int:
    """Largest font size (up to `size`) that fits the longest line."""
    longest = max((len(line) for line in lines), default=0)
    if longest == 0:
        return size
    return max(8, min(size, int(usable_width / (longest * CHAR_WIDTH_RATIO))))


def text_width(text: str, size: int) -> int:
    """Estimated width in pixels of `text` at font `size`."""
    return round(len(text) * size * CHAR_WIDTH_RATIO)


def _text(text: str, x: int, top: int, size: int, fill: str, extra: str = "") -> str:
    """One line of text whose box (one font size tall) starts at `top`.

    `textLength` holds the line to the width the layout planned, so it covers
    the same span (and the strike the same letters) in whichever font of FONT
    the viewer has.
    """
    baseline = top + round(size * BASELINE_RATIO)
    span = f' textLength="{text_width(text, size)}"' if text else ""
    return (
        f'<text x="{x}" y="{baseline}" fill="{fill}" font-family="{FONT}" '
        f'font-size="{size}"{span}{extra}>{escape(text)}</text>'
    )


def _rect(x: int, y: int, w: int, h: int, fill: str = INK) -> str:
    """A filled rectangle, in Ink unless told otherwise."""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def _num(value: float) -> str:
    """A coordinate as SVG wants it: `4`, not `4.0`; `5.5` stays."""
    return str(int(value)) if value == int(value) else str(value)


def _hatch_frame(inset: int, width: int, height: int) -> list[str]:
    """A ring HATCH_WIDTH wide, `inset` from the edge, filled with the hatch."""
    fill = f"url(#{HATCH_ID})"
    side = height - 2 * inset - 2 * HATCH_WIDTH
    ring_w = width - 2 * inset
    return [
        _rect(inset, inset, ring_w, HATCH_WIDTH, fill),
        _rect(inset, height - inset - HATCH_WIDTH, ring_w, HATCH_WIDTH, fill),
        _rect(inset, inset + HATCH_WIDTH, HATCH_WIDTH, side, fill),
        _rect(width - inset - HATCH_WIDTH, inset + HATCH_WIDTH, HATCH_WIDTH, side, fill),
    ]


def _dashed_frame(inset: int, width: int, height: int) -> list[str]:
    """A ring DASH_WIDTH wide, `inset` from the edge: DASH_ON on, DASH_OFF off.

    As on the panel, the dashes are counted from the ring's top-left corner
    along each side, and the top and bottom rows span the corners.
    """
    half = DASH_WIDTH / 2
    left, right = inset, width - inset
    top, bottom = inset, height - inset
    dash = (
        f'stroke="{INK}" stroke-width="{DASH_WIDTH}" stroke-dasharray="{DASH_ON} {DASH_OFF}"'
    )

    def line(x1: float, y1: float, x2: float, y2: float, offset: int = 0) -> str:
        shift = f' stroke-dashoffset="{offset}"' if offset else ""
        ends = f'x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" y2="{_num(y2)}"'
        return f"<line {ends} {dash}{shift}/>"

    return [
        line(left, top + half, right, top + half),
        line(left, bottom - half, right, bottom - half),
        line(left + half, top + DASH_WIDTH, left + half, bottom - DASH_WIDTH, DASH_WIDTH),
        line(right - half, top + DASH_WIDTH, right - half, bottom - DASH_WIDTH, DASH_WIDTH),
    ]


def render_svg(
    lines: list[str],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    title: str | None = None,
    written_at: datetime | None = None,
) -> str:
    """Return an SVG document showing `lines` the way the panel would.

    The first line is the status headline, so it is drawn larger and bold,
    with its status shape. `title` names the image for screen readers; by
    default it is the lines themselves, joined with " / ", and `<desc>`
    carries them one per line. When `written_at` is given, a small "written
    HH:MM UTC" stamp is drawn at the bottom right, in a strip of its own, so
    a dashboard viewer can tell a live writer from one that died and left
    its last image behind.

    Text is never drawn below 8 px, so on a panel much narrower than it is
    tall the longest lines can run into the margin; at the default size every
    line fits inside it.
    """
    if width < 100 or height < 60:
        raise ValueError("panel must be at least 100x60 pixels")
    if not lines:
        raise ValueError("nothing to draw: lines is empty")

    kind = treatment(lines[0])
    margin = round(height * MARGIN_RATIO)
    usable_width = width - 2 * margin

    # The band: one height per panel size, sized from IN RANGE. A longer
    # headline is drawn smaller inside the same band, centred in it.
    inner = usable_width - 2 * BAND_PAD
    band_size = _fit(round(height * HEADLINE_RATIO), [REFERENCE_HEADLINE], inner)
    band_height = band_size + 2 * BAND_PAD
    headline_size = _fit(band_size, lines[:1], inner)
    headline_top = margin + BAND_PAD + (band_size - headline_size) // 2

    # Under the band, in glance order: the value line is the hero (never
    # above the headline), the age is never above the hero, and the `last:`
    # and context lines are never above the age (or the headline).
    body = lines[1:]
    roles = roles_for(kind, len(body))
    value_lines = [text for text, role in zip(body, roles, strict=True) if role == VALUE]
    age_lines = [text for text, role in zip(body, roles, strict=True) if role == AGE]
    small_lines = [  # the `last:` line and the context lines
        text for text, role in zip(body, roles, strict=True) if role not in (VALUE, AGE)
    ]
    body_target = round(height * BODY_RATIO)
    value_size = min(headline_size, _fit(round(height * VALUE_RATIO), value_lines, usable_width))
    age_cap = value_size if value_lines else headline_size
    age_size = min(age_cap, _fit(body_target, age_lines, usable_width))
    small_cap = age_size if age_lines else headline_size
    small_size = min(small_cap, _fit(body_target, small_lines, usable_width))
    sizes = [
        value_size if role == VALUE else age_size if role == AGE else small_size
        for role in roles
    ]

    # The stamp is chrome: never larger than any line of the screen.
    stamp_size = min(max(7, round(height * STAMP_RATIO)), min(sizes, default=headline_size))
    strip = stamp_size + STAMP_GAP if written_at is not None else 0
    top = margin + band_height
    bottom = height - margin - strip
    gap = max(0, bottom - top - sum(sizes)) // (len(body) + 1)

    label = title if title is not None else " / ".join(lines)
    label_attribute = escape(label, {'"': "&quot;"})
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label_attribute}">',
        f"<title>{escape(label)}</title>",
        "<desc>" + "\n".join(escape(line) for line in lines) + "</desc>",
    ]
    if kind == STALE:
        cells = "".join(
            f'<rect x="{x}" y="{y}" width="1" height="1" fill="{INK}"/>' for x, y in HATCH_CELLS
        )
        parts.append(
            f'<defs><pattern id="{HATCH_ID}" width="{HATCH_PITCH}" height="{HATCH_PITCH}" '
            f'patternUnits="userSpaceOnUse">{cells}</pattern></defs>'
        )
    parts.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'fill="{PAPER}" stroke="{STAMP}"/>'
    )
    # The frame sits in the margin, centred, clear of every line of text.
    if kind == STALE:
        parts += _hatch_frame((margin - HATCH_WIDTH) // 2, width, height)
    elif kind == DASHED:
        parts += _dashed_frame((margin - DASH_WIDTH) // 2, width, height)
    banded = kind in (INVERSE, STALE)
    if banded:
        parts.append(_rect(margin, margin, usable_width, band_height))
    parts.append(
        _text(
            lines[0],
            margin + BAND_PAD,
            headline_top,
            headline_size,
            PAPER if banded else INK,
            ' font-weight="700"',
        )
    )
    if kind == RULE:
        parts.append(
            _rect(margin, margin + band_height - RULE_THICKNESS, usable_width, RULE_THICKNESS)
        )

    y = top + gap
    for text, role, size in zip(body, roles, sizes, strict=True):
        parts.append(_text(text, margin, y, size, INK))
        if role == LAST:  # only STALE has one: the old value, struck through
            # Through the middle of the capitals, across the whole line.
            thickness = 2 if size >= THICK_STRIKE_SIZE else 1
            middle = y + round(size * BASELINE_RATIO) - round(size * CAP_RATIO / 2)
            parts.append(_rect(margin, middle - thickness // 2, text_width(text, size), thickness))
        y += size + gap

    if written_at is not None:
        stamp = "written " + written_at.astimezone(UTC).strftime("%H:%M UTC")
        parts.append(
            _text(
                stamp,
                width - margin,
                height - margin - stamp_size,
                stamp_size,
                STAMP,
                ' text-anchor="end"',
            )
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
