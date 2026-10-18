"""Draw rendered display lines as an SVG image of an e-ink panel.

Used for three things: the docs gallery of every display state, the
`--svg` CLI option (handy for Home Assistant or a web dashboard), and
previewing layouts before real e-paper hardware exists.

Pure standard library. The output is static SVG with no scripts or links,
and every line of text is XML-escaped, so it is safe to embed anywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from xml.sax.saxutils import escape

# A common small e-paper panel size (Waveshare 2.9"), in pixels.
DEFAULT_WIDTH = 296
DEFAULT_HEIGHT = 128

PAPER = "#e8e8e3"
INK = "#111111"
EDGE = "#b9b9b3"
STAMP = "#5b5b57"


# Monospace glyphs are about 0.6 of the font size wide.
CHAR_WIDTH_RATIO = 0.6


def _fit(size: int, lines: list[str], usable_width: int) -> int:
    """Largest font size (up to `size`) that fits the longest line."""
    longest = max((len(line) for line in lines), default=0)
    if longest == 0:
        return size
    return max(8, min(size, int(usable_width / (longest * CHAR_WIDTH_RATIO))))


def render_svg(
    lines: list[str],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    title: str = "Lightkeeper display",
    written_at: datetime | None = None,
) -> str:
    """Return an SVG document showing `lines` the way the panel would.

    The first line is the status headline, so it is drawn larger and bold.
    When `written_at` is given, a small "written HH:MM UTC" stamp is drawn
    in the bottom-right corner so a dashboard viewer can tell a live writer
    from one that died and left its last image behind.
    """
    if width < 100 or height < 60:
        raise ValueError("panel must be at least 100x60 pixels")
    if not lines:
        raise ValueError("nothing to draw: lines is empty")

    margin = round(height * 0.09)
    usable_width = width - 2 * margin
    # Shrink text when the longest line would run off the panel edge.
    headline_size = _fit(round(height * 0.19), lines[:1], usable_width)
    body_size = _fit(round(height * 0.12), lines[1:], usable_width)
    # Spread the lines evenly over the space below the headline.
    body_lines = lines[1:]
    first_baseline = margin + headline_size
    remaining = height - first_baseline - margin
    step = remaining / max(len(body_lines), 1)

    label = escape(title, {'"': "&quot;"})
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">',
        f"<title>{escape(title)}</title>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="4" '
        f'fill="{PAPER}" stroke="{EDGE}"/>',
        f'<text x="{margin}" y="{first_baseline}" fill="{INK}" '
        f'font-family="DejaVu Sans Mono, Consolas, monospace" font-size="{headline_size}" '
        f'font-weight="700">{escape(lines[0])}</text>',
    ]
    for index, line in enumerate(body_lines, start=1):
        baseline = round(first_baseline + step * index - (step - body_size) / 2)
        parts.append(
            f'<text x="{margin}" y="{baseline}" fill="{INK}" '
            f'font-family="DejaVu Sans Mono, Consolas, monospace" font-size="{body_size}">'
            f"{escape(line)}</text>"
        )
    if written_at is not None:
        stamp = "written " + written_at.astimezone(UTC).strftime("%H:%M UTC")
        stamp_size = max(7, round(height * 0.07))
        parts.append(
            f'<text x="{width - margin}" y="{height - round(margin * 0.4)}" fill="{STAMP}" '
            f'font-family="DejaVu Sans Mono, Consolas, monospace" font-size="{stamp_size}" '
            f'text-anchor="end">{escape(stamp)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
