"""Generate docs/img/pinout-2.9-touch-hat.svg: which Pi header pins the HAT uses.

The pin assignments come from Waveshare's 2.9inch Touch e-Paper HAT wiki
(signal to physical pin); the BCM numbers are the standard Raspberry Pi
mapping for those pins. tests/test_pinout.py fails if the committed SVG
differs from what this script produces.

Usage (from the repo root):
    python tools/gen_pinout.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = Path("docs") / "img" / "pinout-2.9-touch-hat.svg"

# Standard Raspberry Pi 40-pin header: physical pin -> name.
HEADER = {
    1: "3V3", 2: "5V", 3: "GPIO2", 4: "5V", 5: "GPIO3", 6: "GND", 7: "GPIO4", 8: "GPIO14",
    9: "GND", 10: "GPIO15", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
    16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25",
    23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
    30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16",
    37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21",
}  # fmt: skip

# What the 2.9inch Touch e-Paper HAT connects (Waveshare wiki), by physical pin.
HAT = {
    1: ("VCC", "power"),
    17: ("VCC", "power"),
    19: ("DIN (MOSI)", "epaper"),
    23: ("CLK (SCLK)", "epaper"),
    24: ("CS (CE0)", "epaper"),
    22: ("DC", "epaper"),
    11: ("RST", "epaper"),
    18: ("BUSY", "epaper"),
    3: ("SDA (touch)", "touch"),
    5: ("SCL (touch)", "touch"),
    13: ("INT (touch)", "touch"),
    15: ("TRST (touch)", "touch"),
}

COLORS = {
    "epaper": ("#2B5BA8", "#FFFFFF"),
    "touch": ("#7A4FA0", "#FFFFFF"),
    "power": ("#B3261E", "#FFFFFF"),
    "ground": ("#15171C", "#FFFFFF"),
    "unused": ("#E6E5DF", "#5B6068"),
}

INK = "#15171C"
MUTED = "#5B6068"
FONT = "DejaVu Sans, Segoe UI, Helvetica, Arial, sans-serif"


def role(pin: int) -> tuple[str, str]:
    """(label, colour role) for one physical pin."""
    if pin in HAT:
        return HAT[pin]
    if HEADER[pin] == "GND":
        return ("GND", "ground")
    return ("", "unused")


def build_svg() -> str:
    """Return the pinout diagram as an SVG document."""
    width, height = 940, 900
    top, row_h = 120, 34
    left_x, right_x = 410, 470  # pin centres for odd (left) and even (right) columns
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Raspberry Pi header pins used by the Waveshare 2.9 inch Touch e-Paper HAT">',
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
        f'<text x="40" y="48" font-family="{FONT}" font-size="24" font-weight="700" '
        f'fill="{INK}">Pi header pins used by the 2.9" Touch e-Paper HAT</text>',
        f'<text x="40" y="78" font-family="{FONT}" font-size="15" fill="{MUTED}">The HAT plugs '
        "straight onto the 40-pin header; no wiring. This is for writing or debugging a driver. "
        "Source: Waveshare wiki.</text>",
        f'<rect x="{left_x - 26}" y="{top - 26}" width="{right_x - left_x + 52}" '
        f'height="{20 * row_h + 18}" rx="8" fill="#262B33"/>',
    ]
    for row in range(20):
        y = top + row * row_h
        for pin, x, anchor, text_x in (
            (2 * row + 1, left_x, "end", left_x - 40),
            (2 * row + 2, right_x, "start", right_x + 40),
        ):
            label, kind = role(pin)
            fill, text_fill = COLORS[kind]
            shape = (
                f'<rect x="{x - 12}" y="{y - 12}" width="24" height="24" rx="3" fill="{fill}" '
                'stroke="#FFFFFF" stroke-width="1.5"/>'
                if pin == 1
                else f'<circle cx="{x}" cy="{y}" r="12" fill="{fill}" stroke="#FFFFFF" '
                'stroke-width="1.5"/>'
            )
            out.append(shape)
            out.append(
                f'<text x="{x}" y="{y + 4}" font-family="{FONT}" font-size="11" '
                f'font-weight="700" text-anchor="middle" fill="{text_fill}">{pin}</text>'
            )
            name = HEADER[pin]
            if label and label != name:
                text = (
                    f"{escape(label)}  ·  {name}"
                    if anchor == "start"
                    else (f"{name}  ·  {escape(label)}")
                )
            else:
                text = name
            weight = "700" if kind != "unused" else "400"
            colour = INK if kind != "unused" else MUTED
            out.append(
                f'<text x="{text_x}" y="{y + 5}" font-family="{FONT}" font-size="14" '
                f'font-weight="{weight}" text-anchor="{anchor}" fill="{colour}">{text}</text>'
            )
    legend_y = top + 20 * row_h + 40
    for i, (kind, label) in enumerate(
        [
            ("epaper", "E-paper panel (SPI)"),
            ("touch", "Touch controller (I2C), optional"),
            ("power", "3.3 V power"),
            ("ground", "Ground"),
        ]
    ):
        x = (60, 285, 600, 780)[i]
        fill, _ = COLORS[kind]
        out.append(f'<circle cx="{x}" cy="{legend_y}" r="9" fill="{fill}"/>')
        out.append(
            f'<text x="{x + 18}" y="{legend_y + 5}" font-family="{FONT}" font-size="14" '
            f'fill="{INK}">{label}</text>'
        )
    out.append(
        f'<text x="60" y="{legend_y + 34}" font-family="{FONT}" font-size="13" fill="{MUTED}">'
        "Pin 1 is the square pad. Enable SPI with raspi-config before driving the panel.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def build(out_root: Path) -> Path:
    """Write the SVG under out_root and return its path."""
    target = out_root / OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_svg(), encoding="utf-8", newline="\n")
    return target


if __name__ == "__main__":
    print(build(ROOT).relative_to(ROOT))
