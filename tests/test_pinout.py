"""The pinout diagram matches its generator and the HAT's documented pins."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gen_pinout", ROOT / "tools" / "gen_pinout.py")
gen_pinout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_pinout)


def test_committed_pinout_is_up_to_date(tmp_path):
    generated = gen_pinout.build(tmp_path).read_text(encoding="utf-8")
    committed = (ROOT / gen_pinout.OUT).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == generated, "run python tools/gen_pinout.py"


def test_epaper_signals_sit_on_the_standard_spi_pins():
    expected = {19: "GPIO10", 23: "GPIO11", 24: "GPIO8"}  # MOSI, SCLK, CE0
    for pin, name in expected.items():
        assert gen_pinout.HEADER[pin] == name
        assert gen_pinout.role(pin)[1] == "epaper"


def test_every_header_pin_is_drawn():
    svg = gen_pinout.build_svg()
    assert len(gen_pinout.HEADER) == 40
    for pin in range(1, 41):
        assert f">{pin}</text>" in svg
    assert gen_pinout.role(6) == ("GND", "ground")
    assert gen_pinout.role(7) == ("", "unused")
