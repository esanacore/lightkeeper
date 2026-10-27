"""The bill of materials: the CSV is valid and docs/BOM.md matches what it generates."""

import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("gen_bom", ROOT / "tools" / "gen_bom.py")
gen_bom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_bom)


def test_bom_rows_are_valid():
    rows = gen_bom.load_rows()
    assert {r["build"] for r in rows} >= {"bedside", "pocket", "bench"}


def test_committed_bom_doc_is_up_to_date(tmp_path):
    generated = gen_bom.build(tmp_path).read_text(encoding="utf-8")
    committed = (ROOT / "docs" / "BOM.md").read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == generated, "run python tools/gen_bom.py"


def test_bedside_subtotal_is_in_the_doc():
    doc = gen_bom.build_doc(gen_bom.load_rows())
    assert "Bedside display" in doc and "**Subtotal:**" in doc


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"build": "garage"}, "unknown build"),
        ({"qty": "0"}, "qty"),
        ({"unit_usd_low": "9", "unit_usd_high": "1"}, "low price"),
        ({"url": "http://example.com"}, "https"),
    ],
)
def test_bad_rows_are_rejected(tmp_path, change, message):
    rows = list(csv.DictReader((ROOT / "hardware" / "bom" / "bom.csv").open(encoding="utf-8")))
    rows[0].update(change)
    bad = tmp_path / "bom.csv"
    with bad.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=gen_bom.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match=message):
        gen_bom.load_rows(bad)


def test_wrong_columns_are_rejected(tmp_path):
    bad = tmp_path / "bom.csv"
    bad.write_text("build,item\nbedside,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        gen_bom.load_rows(bad)


def test_single_price_and_range_formats():
    from decimal import Decimal

    assert gen_bom.price_range(Decimal("5"), Decimal("5")) == "$5.00"
    assert gen_bom.price_range(Decimal("5"), Decimal("7.5")) == "$5.00 to $7.50"
