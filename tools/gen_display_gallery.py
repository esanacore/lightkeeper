"""Generate the display-state gallery from the shared vectors.

Writes one SVG per case in spec/display_vectors.json to
docs/img/display-states/, plus docs/DISPLAY_STATES.md showing them all.
Because the images come from the same vectors the tests use, the gallery
can't quietly drift from real behavior: tests/test_gallery.py fails if the
committed files differ from what this script produces.

Usage (from the repo root):
    python tools/gen_display_gallery.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lightkeeper.infrastructure.epaper_bitmap import Bitmap, render_bitmap  # noqa: E402
from lightkeeper.infrastructure.svg_display import render_svg  # noqa: E402

VECTORS = ROOT / "spec" / "display_vectors.json"
IMG_DIR = Path("docs") / "img" / "display-states"
PANEL_DIR = Path("docs") / "img" / "epaper"
PANEL_SCALE = 2  # PNGs are drawn at 2x so the 1-bit pixels stay visible on a high-DPI screen
DOC = Path("docs") / "DISPLAY_STATES.md"
DEMO = Path("demo.html")
BEGIN = "      // BEGIN GENERATED STATES"
END = "      // END GENERATED STATES"

# Short, plain-English captions for each vector, in the order shown.
GROUPS = [
    (
        "Fresh readings",
        [
            "in_range_flat",
            "in_range_just_now",
            "boundary_low_70_in_range",
            "low_69",
            "urgent_low_55",
            "sensor_low_sentinel",
            "boundary_high_180_in_range",
            "high_181",
            "urgent_high_250",
            "sensor_high_sentinel",
            "unknown_direction",
        ],
    ),
    (
        "Old or untrustworthy time",
        [
            "fresh_at_15_minutes",
            "stale_at_16_minutes",
            "stale_beats_urgent_low",
            "future_dated",
            "small_clock_skew_ok",
            "fresh_at_14_minutes_59_seconds",
            "stale_at_15_minutes_1_second",
            "future_skew_exactly_2_minutes_ok",
            "future_skew_2_minutes_1_second_stale",
        ],
    ),
    (
        "Several entries at once",
        [
            "same_timestamp_lower_value_wins",
            "newest_entry_wins_in_any_order",
            "poisoned_entries_skipped",
            "rejected_newest_does_not_freshen_older",
            "all_entries_rejected_is_no_data",
        ],
    ),
    (
        "Custom thresholds (60 / 80 / 160 / 220 mg/dL, stale after 10 minutes)",
        [
            "custom_urgent_low_60",
            "custom_low_79",
            "custom_in_range_160",
            "custom_high_161",
            "custom_urgent_high_220",
            "custom_fresh_at_10_minutes",
            "custom_stale_after_10_minutes",
        ],
    ),
    (
        "Missing data and outages",
        [
            "no_data",
            "no_data_unreachable",
            "last_good_while_unreachable",
            "stale_while_unreachable_stays_four_lines",
            "invalid_value_rejected",
            "huge_value_rejected",
            "non_sgv_rejected",
        ],
    ),
]


def describe_age(item: dict) -> str:
    """How old an entry is, in the unit the vector gives it."""
    if "seconds_ago" in item:
        ago, unit = item["seconds_ago"], "s"
    else:
        ago, unit = item["minutes_ago"], " min"
    return f"{abs(ago)}{unit} in the future" if ago < 0 else f"{ago}{unit} old"


def describe_entry(item: dict) -> str:
    """One entry as `type value mg/dL, direction, age`."""
    entry = item["entry"]
    kind = entry.get("type", "sgv")
    return f"{kind} {entry.get('sgv')} mg/dL, {entry.get('direction')}, {describe_age(item)}"


def describe(case: dict) -> str:
    """One-line plain-English description of a vector's situation."""
    if "entries" in case:
        situation = "; ".join(describe_entry(item) for item in case["entries"])
    elif case["entry"] is None:
        situation = "No reading in Nightscout"
    else:
        situation = describe_entry(case)
    if case["error"]:
        situation += ", Nightscout unreachable"
    return situation


def panel_png(lines: list[str]) -> bytes:
    """Return the exact 1-bit bitmap the Pi panel will show, enlarged without smoothing."""
    native = render_bitmap(lines)
    big = Bitmap(native.width * PANEL_SCALE, native.height * PANEL_SCALE)
    for y in range(native.height):
        for x in range(native.width):
            if native.is_ink(x, y):
                big.fill(x * PANEL_SCALE, y * PANEL_SCALE, PANEL_SCALE, PANEL_SCALE)
    return big.to_png()


def build(out_root: Path) -> list[Path]:
    """Write the gallery under out_root and return the files written."""
    cases = {c["name"]: c for c in json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]}
    listed = [name for _, names in GROUPS for name in names]
    missing = sorted(set(cases) - set(listed))
    if missing:
        raise SystemExit(
            f"add these vectors to GROUPS in {Path(__file__).name}: {', '.join(missing)}"
        )

    img_dir = out_root / IMG_DIR
    img_dir.mkdir(parents=True, exist_ok=True)
    panel_dir = out_root / PANEL_DIR
    panel_dir.mkdir(parents=True, exist_ok=True)
    written = []
    doc = [
        "# Display States",
        "",
        'Every screen Lightkeeper can show, drawn at the size of a 2.9" e-paper panel. '
        "These images are generated from `spec/display_vectors.json` by "
        "`tools/gen_display_gallery.py`, the same cases the Python, firmware, and Swift "
        "tests run, so they always match real behavior. Regenerate them after changing a vector.",
        "",
        "Rules worth noticing: anything older than 15 minutes, or more than 2 minutes in the "
        "future, shows STALE, even when the number would be alarming; sensor out-of-range "
        "values show as words, not numbers; and the screen never uses more than four lines.",
        "",
        "![How a reading becomes a word: NO DATA, then STALE before any range check, then the "
        "thresholds](../assets/diagrams/classification.svg)",
        "",
        "The **Screen** column is the SVG preview (also written by `--svg`). The **Panel pixels** "
        "column is the exact 1-bit bitmap the Raspberry Pi e-paper panel will show, drawn by "
        "`lightkeeper.infrastructure.epaper_bitmap` with the project's own font and shown at 2x.",
        "",
    ]
    for heading, names in GROUPS:
        doc += [
            f"## {heading}",
            "",
            "| Situation | Screen | Panel pixels |",
            "| --- | --- | --- |",
        ]
        for name in names:
            case = cases[name]
            svg_path = img_dir / f"{name}.svg"
            svg_path.write_text(
                render_svg(case["lines"], title=f"{case['level']}: {name}"), encoding="utf-8"
            )
            written.append(svg_path)
            png_path = panel_dir / f"{name}.png"
            png_path.write_bytes(panel_png(case["lines"]))
            written.append(png_path)
            doc.append(
                f"| {describe(case)} | ![{case['level']}](img/display-states/{name}.svg) "
                f"| ![{case['level']}, panel pixels](img/epaper/{name}.png) |"
            )
        doc.append("")
    doc_path = out_root / DOC
    doc_path.write_text("\n".join(doc), encoding="utf-8")
    written.append(doc_path)
    written.append(write_demo(cases, out_root))
    return written


def write_demo(cases: dict, out_root: Path) -> Path:
    """Replace the generated states block in demo.html with the vectors."""
    page = (ROOT / DEMO).read_text(encoding="utf-8")
    start = page.index(BEGIN)
    end = page.index(END, start)
    states = {name: {"level": c["level"], "lines": c["lines"]} for name, c in cases.items()}
    body = json.dumps(states, indent=2).replace("\n", "\n      ")
    block = (
        f"{BEGIN} (tools/gen_display_gallery.py from spec/display_vectors.json)\n"
        f"      const states = {body};\n"
    )
    out = out_root / DEMO
    out.write_text(page[:start] + block + page[end:], encoding="utf-8")
    return out


if __name__ == "__main__":
    for path in build(ROOT):
        print(path.relative_to(ROOT))
