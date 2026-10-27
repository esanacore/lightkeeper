"""Generate docs/BOM.md from hardware/bom/bom.csv.

The CSV is the single source of truth for what to buy; this script turns it
into a readable bill of materials with per-build totals. tests/test_bom.py
fails if the committed docs/BOM.md differs from what this script produces,
or if a row is malformed.

Usage (from the repo root):
    python tools/gen_bom.py
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "hardware" / "bom" / "bom.csv"
DOC = Path("docs") / "BOM.md"

COLUMNS = [
    "build",
    "item",
    "exact_name",
    "qty",
    "unit_usd_low",
    "unit_usd_high",
    "stock_checked",
    "source",
    "url",
    "notes",
]

BUILDS = {
    "bedside": (
        'Bedside display (Raspberry Pi Zero 2 WH + 2.9" e-paper)',
        "The first display a household can rely on. Runs the Python code as it is, in the "
        "hardened systemd service, inside the printed enclosure from `hardware/enclosure/` "
        "(two parts, no supports, four M2.5 screws).",
    ),
    "pocket": (
        "Pocket display (Xteink X4 Pro)",
        "The ESP32-C3 pocket reader the firmware targets (ADR-0006). No parts beyond the reader.",
    ),
    "bench": (
        "Firmware bench board (Waveshare ESP32-S3-ePaper-1.54)",
        "Develop and test firmware here, not on the device the person with diabetes carries.",
    ),
    "extras": (
        "Optional extras (after the first displays work)",
        "Not needed for a first build.",
    ),
}


def load_rows(path: Path = CSV_PATH) -> list[dict[str, str]]:
    """Read and validate the BOM rows."""
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"bom.csv columns must be exactly {COLUMNS}")
        rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if row["build"] not in BUILDS:
            raise ValueError(f"bom.csv line {number}: unknown build {row['build']!r}")
        if int(row["qty"]) < 1:
            raise ValueError(f"bom.csv line {number}: qty must be at least 1")
        if Decimal(row["unit_usd_low"]) > Decimal(row["unit_usd_high"]):
            raise ValueError(f"bom.csv line {number}: low price above high price")
        if row["url"] and not row["url"].startswith("https://"):
            raise ValueError(f"bom.csv line {number}: links must be https")
    return rows


def money(value: Decimal) -> str:
    """Format dollars with cents."""
    return f"${value:,.2f}"


def price_range(low: Decimal, high: Decimal) -> str:
    """One price, or a low-to-high range."""
    return money(low) if low == high else f"{money(low)} to {money(high)}"


def build_doc(rows: list[dict[str, str]]) -> str:
    """Return the Markdown for docs/BOM.md."""
    out = [
        "# Bill of Materials",
        "",
        "Generated from `hardware/bom/bom.csv` by `tools/gen_bom.py`; edit the CSV, not this "
        "file. Prices are US list prices and move; each row says when its stock was last "
        "checked. Buying advice and alternatives are in `docs/HARDWARE.md`; the enclosure is in "
        "`hardware/enclosure/` and the assembly steps are in `docs/ASSEMBLY.md`.",
        "",
        "Nothing here is a medical device. These are secondary displays; the primary CGM app "
        "and its alarms stay on the phone. See `docs/SAFETY.md`.",
        "",
    ]
    for build, (title, blurb) in BUILDS.items():
        items = [r for r in rows if r["build"] == build]
        if not items:
            continue
        low = sum(Decimal(r["unit_usd_low"]) * int(r["qty"]) for r in items)
        high = sum(Decimal(r["unit_usd_high"]) * int(r["qty"]) for r in items)
        out += [
            f"## {title}",
            "",
            blurb,
            "",
            "| Item | Exact name | Qty | Unit price | Stock | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in items:
            source = f"[{r['source']}]({r['url']})" if r["url"] else r["source"]
            unit = price_range(Decimal(r["unit_usd_low"]), Decimal(r["unit_usd_high"]))
            out.append(
                f"| {r['item']} | {r['exact_name']} | {r['qty']} | {unit} "
                f"| {r['stock_checked']} | {source} |"
            )
        out += ["", f"**Subtotal:** {price_range(low, high)}", ""]
        notes = [r for r in items if r["notes"]]
        if notes:
            out += ["Notes:", ""]
            out += [f"- **{r['item']}:** {r['notes']}" for r in notes]
            out.append("")
    return "\n".join(out)


def build(out_root: Path) -> Path:
    """Write docs/BOM.md under out_root and return its path."""
    target = out_root / DOC
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_doc(load_rows()), encoding="utf-8", newline="\n")
    return target


if __name__ == "__main__":
    print(build(ROOT).relative_to(ROOT))
