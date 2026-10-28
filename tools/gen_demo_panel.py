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
    """Format a value as JSON for the page script, indented to match it."""
    return json.dumps(value, indent=2).replace("\n", "\n" + INDENT)


def dump_font(font: dict[str, object]) -> str:
    """Format the font as JSON with one glyph per line, as spec/font5x8.json has it."""
    glyphs = font["glyphs"]
    assert isinstance(glyphs, dict)
    head = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in font.items() if k != "glyphs"]
    rows = [f"    {json.dumps(char)}: {json.dumps(cells)}" for char, cells in glyphs.items()]
    lines = ["{", *head, '  "glyphs": {', ",\n".join(rows), "  }", "}"]
    return "\n".join(lines).replace("\n", "\n" + INDENT)


def check_inline(name: str, text: str) -> None:
    """Refuse text that would break the page script it is copied into.

    `</script` would end the script element early, and `<!--` or `<script`
    switch the HTML parser into a state where it might. A block marker would
    make this script, or tools/gen_display_gallery.py, cut the page in the
    wrong place.
    """
    lowered = text.lower()
    for marker in ("</script", "<!--", "<script"):
        if marker in lowered:
            raise SystemExit(
                f"{name} contains {marker!r}, which cannot sit inside an inline script"
            )
    for marker in ("BEGIN GENERATED", "END GENERATED"):
        if marker in text:
            raise SystemExit(f"{name} contains {marker!r}, which marks where the page is cut")


def block(page_bytes: int) -> str:
    """Return the generated block, from its BEGIN line up to (not including) the END line."""
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
        raise SystemExit(
            f"{ICONS.as_posix()} is missing a lamp: {sorted(set(LAMPS) - set(lamps))}"
        )
    profiles = {
        profile.name: {
            "width": profile.width,
            "height": profile.height,
            "description": profile.description,
        }
        for profile in PROFILES.values()
    }
    check_inline(PANEL_JS.as_posix(), script)
    data = "".join(
        [
            f"{INDENT}const font = {dump_font(font)};\n",
            f"{INDENT}const spoken = {dump(spoken)};\n",
            f"{INDENT}const lampIcons = {dump({name: lamps[name] for name in LAMPS})};\n",
            f"{INDENT}const profiles = {dump(profiles)};\n",
            f"{INDENT}const defaultProfile = {json.dumps(DEFAULT_PROFILE)};\n",
            f"{INDENT}const pageBytes = {page_bytes};\n",
        ]
    )
    check_inline(f"the data from {SOURCES}", data)
    header = f"{BEGIN} (tools/gen_demo_panel.py from {SOURCES} and the panel profiles)\n"
    return header + script + data


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
