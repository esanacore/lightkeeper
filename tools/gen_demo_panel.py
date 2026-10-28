"""Inline the browser panel port and the data it draws with into demo.html.

demo.html is one file with no network loads, so everything its panel needs
is copied into the page script between `// BEGIN GENERATED PANEL` and
`// END GENERATED PANEL`:

- web/panel/panel.js, byte for byte (the integer-only port of the panel
  rasterizer that spec/panel_vectors.json pins);
- spec/font5x8.json, the Keeper 5x8 font;
- the spoken sentence of every vector, from spec/spoken_vectors.json;
- the three pixel lamps from assets/brand/pixel-icons.json, for the status chip;
- the panel profiles, from lightkeeper.infrastructure.panel_profiles;
- the page's own size in bytes, for the colophon, worked out last.

The states block above it stays tools/gen_display_gallery.py's. Because the
page's size covers that block too, run this script after the gallery script
whenever a vector changes. tests/test_demo_panel.py fails if the committed
block differs from what this script produces.

Usage (from the repo root):
    python tools/gen_demo_panel.py           # rewrite the block in demo.html
    python tools/gen_demo_panel.py --check   # exit 1 if the block is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lightkeeper.infrastructure.panel_profiles import DEFAULT_PROFILE, PROFILES  # noqa: E402

DEMO = Path("demo.html")
PANEL_JS = Path("web") / "panel" / "panel.js"
FONT = Path("spec") / "font5x8.json"
SPOKEN = Path("spec") / "spoken_vectors.json"
ICONS = Path("assets") / "brand" / "pixel-icons.json"
LAMPS = ("lamp-lit", "lamp-hatched", "lamp-empty")
BEGIN = "      // BEGIN GENERATED PANEL"
END = "      // END GENERATED PANEL"
INDENT = "      "
PAGE_BUDGET = 512 * 1024  # bytes: the small-web budget for the one-file demo
SOURCES = ", ".join(path.as_posix() for path in (PANEL_JS, FONT, SPOKEN, ICONS))


def read(relative: Path) -> str:
    """Read a repository file's text, whatever line endings the checkout gave it."""
    return (ROOT / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


def dump(value: object) -> str:
    """JSON for a value inside the page script, indented to match it."""
    return json.dumps(value, indent=2).replace("\n", "\n" + INDENT)


def dump_font(font: dict[str, object]) -> str:
    """The font as JSON with one glyph per line, as spec/font5x8.json writes it."""
    glyphs = font["glyphs"]
    assert isinstance(glyphs, dict)
    head = [f"  {json.dumps(key)}: {json.dumps(value)}," for key, value in font.items()]
    rows = [f"    {json.dumps(char)}: {json.dumps(cells)}" for char, cells in glyphs.items()]
    keep = [line for line, key in zip(head, font, strict=True) if key != "glyphs"]
    lines = ["{", *keep, '  "glyphs": {', ",\n".join(rows), "  }", "}"]
    return "\n".join(lines).replace("\n", "\n" + INDENT)


def check_inline(name: str, text: str) -> None:
    """Refuse text that would end the page's script element early or start a comment in it."""
    lowered = text.lower()
    for marker in ("</script", "<!--", "<script"):
        if marker in lowered:
            raise SystemExit(f"{name} contains {marker!r}, which cannot sit inside an inline script")


def block(page_bytes: int) -> str:
    """The generated block, from its BEGIN line up to (not including) the END line."""
    script = read(PANEL_JS)
    if not script.endswith("\n"):
        raise SystemExit(f"{PANEL_JS.as_posix()} must end with a newline")
    font = json.loads(read(FONT))
    spoken = json.loads(read(SPOKEN))["cases"]
    lamps = {
        entry["name"]: entry["rows"]
        for entry in json.loads(read(ICONS))["icons"]
        if entry["name"] in LAMPS
    }
    if set(lamps) != set(LAMPS):
        raise SystemExit(f"{ICONS.as_posix()} is missing a lamp: {sorted(set(LAMPS) - set(lamps))}")
    profiles = {
        profile.name: {
            "width": profile.width,
            "height": profile.height,
            "description": profile.description,
        }
        for profile in PROFILES.values()
    }
    text = "".join(
        [
            f"{BEGIN} (tools/gen_demo_panel.py from {SOURCES} and the panel profiles)\n",
            script,
            f"{INDENT}const font = {dump_font(font)};\n",
            f"{INDENT}const spoken = {dump(spoken)};\n",
            f"{INDENT}const lampIcons = {dump({name: lamps[name] for name in LAMPS})};\n",
            f"{INDENT}const profiles = {dump(profiles)};\n",
            f"{INDENT}const defaultProfile = {json.dumps(DEFAULT_PROFILE)};\n",
            f"{INDENT}const pageBytes = {page_bytes};\n",
        ]
    )
    check_inline("the generated panel block", text)
    return text


def render(page: str) -> str:
    """Return the page with a fresh generated block, its size stated in bytes.

    The stated size is part of the page, so it is found by repeating until
    it no longer changes (at most a couple of times, when the digit count grows).
    """
    if page.count(BEGIN) != 1 or page.count(END) != 1:
        raise SystemExit(f"{DEMO} needs exactly one {BEGIN.strip()!r} and one {END.strip()!r}")
    start = page.index(BEGIN)
    end = page.index(END, start)
    size = 0
    for _ in range(5):
        out = page[:start] + block(size) + page[end:]
        actual = len(out.encode("utf-8"))
        if actual == size:
            if size > PAGE_BUDGET:
                raise SystemExit(f"{DEMO} is {size} bytes, over the {PAGE_BUDGET} byte budget")
            return out
        size = actual
    raise SystemExit("the page size did not settle")


def build() -> dict[Path, str]:
    """Return the text of each generated file, by path relative to the repo root."""
    return {DEMO: render(read(DEMO))}


def main(argv: list[str] | None = None) -> int:
    """Rewrite the block, or with --check report whether it is current."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the block is out of date")
    args = parser.parse_args(argv)
    stale = []
    for relative, text in build().items():
        if read(relative) == text:
            continue
        stale.append(relative.as_posix())
        if not args.check:
            (ROOT / relative).write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {relative.as_posix()}")
    if args.check and stale:
        print(f"out of date: {', '.join(stale)}; run python tools/gen_demo_panel.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
