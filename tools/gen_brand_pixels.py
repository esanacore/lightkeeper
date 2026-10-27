"""Render the brand pixel icons and marks to PNG.

Reads the '#'/'.' grids in assets/brand/pixel-icons.json and writes each one
to assets/brand/png/ twice: pixel-<name>.png at 1x and pixel-<name>@4x.png at
4x. They are drawn with the e-paper panel's own 1-bit Bitmap and enlarged by
whole numbers without smoothing, so an icon on a page is the same pixels a
panel would show. tests/test_brand_tokens.py fails if the committed PNGs
differ from what this script produces.

Usage (from the repo root):
    python tools/gen_brand_pixels.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lightkeeper.infrastructure.epaper_bitmap import Bitmap  # noqa: E402

ICONS = ROOT / "assets" / "brand" / "pixel-icons.json"
PNG_DIR = Path("assets") / "brand" / "png"
SCALES = (1, 4)
INK, PAPER = "#", "."
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def is_grid(size: object, rows: object) -> bool:
    """Check that rows is a square grid of '#' and '.', `size` cells on a side, size >= 1."""
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        return False
    if not isinstance(rows, list) or len(rows) != size:
        return False
    return all(
        isinstance(row, str) and len(row) == size and set(row) <= {INK, PAPER} for row in rows
    )


def load_icons(path: Path = ICONS) -> list[dict[str, Any]]:
    """Every icon entry, after checking that its grid can be drawn as declared."""
    icons: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["icons"]
    seen: set[str] = set()
    for icon in icons:
        name, size, rows = icon.get("name"), icon.get("size"), icon.get("rows")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in seen:
            raise SystemExit(f"{path.name}: icon name {name!r} is malformed or repeated")
        seen.add(name)
        if not is_grid(size, rows):
            raise SystemExit(
                f"{path.name}: {name} needs a whole-number size of at least 1"
                f" and that many rows of that many '#' or '.' (size {size!r})"
            )
    return icons


def draw(rows: list[str], scale: int) -> Bitmap:
    """Draw a grid as a 1-bit bitmap, each cell a scale x scale block."""
    bitmap = Bitmap(len(rows[0]) * scale, len(rows) * scale)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == INK:
                bitmap.fill(x * scale, y * scale, scale, scale)
    return bitmap


def png_name(name: str, scale: int) -> str:
    """File name for an icon at a scale: no suffix at 1x, @<n>x otherwise."""
    return f"pixel-{name}.png" if scale == 1 else f"pixel-{name}@{scale}x.png"


def build(out_root: Path) -> list[Path]:
    """Write every icon at every scale under out_root and return the files written."""
    png_dir = out_root / PNG_DIR
    png_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for icon in load_icons():
        for scale in SCALES:
            path = png_dir / png_name(icon["name"], scale)
            path.write_bytes(draw(icon["rows"], scale).to_png())
            written.append(path)
    return written


if __name__ == "__main__":
    for path in build(ROOT):
        print(path.relative_to(ROOT).as_posix())
