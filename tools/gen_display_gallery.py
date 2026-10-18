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

from lightkeeper.infrastructure.svg_display import render_svg  # noqa: E402

VECTORS = ROOT / "spec" / "display_vectors.json"
IMG_DIR = Path("docs") / "img" / "display-states"
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


def describe(case: dict) -> str:
    """One-line plain-English description of a vector's situation."""
    entry = case["entry"]
    if entry is None:
        situation = "No reading in Nightscout"
    else:
        ago = case["minutes_ago"]
        when = f"{abs(ago)} min in the future" if ago < 0 else f"{ago} min old"
        kind = entry.get("type", "sgv")
        situation = f"{kind} {entry.get('sgv')} mg/dL, {entry.get('direction')}, {when}"
    if case["error"]:
        situation += ", Nightscout unreachable"
    return situation


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
    ]
    for heading, names in GROUPS:
        doc += [f"## {heading}", "", "| Situation | Screen |", "| --- | --- |"]
        for name in names:
            case = cases[name]
            svg_path = img_dir / f"{name}.svg"
            svg_path.write_text(
                render_svg(case["lines"], title=f"{case['level']}: {name}"), encoding="utf-8"
            )
            written.append(svg_path)
            doc.append(f"| {describe(case)} | ![{case['level']}](img/display-states/{name}.svg) |")
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
