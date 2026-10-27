"""Named e-paper panel sizes the reference rasterizer is tested at.

Each profile is a width and height in pixels, in the orientation the lines
read (landscape for the Waveshare panels, portrait for the Kindle). The six
named here are pinned by `spec/panel_vectors.json`, so every port draws the
same pixels at the same sizes. `resolve` also accepts any `WxH`, for panels
that have no name yet.

Pure standard library (ADR-0005).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The rasterizer's limits: smaller panels cannot hold four lines, and larger
# ones would only be a typo that allocates a huge image.
MIN_WIDTH = 100
MIN_HEIGHT = 60
MAX_SIDE = 4096


@dataclass(frozen=True)
class PanelProfile:
    """A panel size: `name` is a profile name or `WxH` for a custom size."""

    name: str
    width: int
    height: int
    description: str


PROFILES: dict[str, PanelProfile] = {
    profile.name: profile
    for profile in (
        PanelProfile("waveshare_2in9", 296, 128, 'Waveshare 2.9", the bedside Pi panel'),
        PanelProfile("waveshare_1in54", 200, 200, 'Waveshare 1.54", square'),
        PanelProfile("waveshare_2in13", 250, 122, 'Waveshare 2.13"'),
        PanelProfile("waveshare_4in2", 400, 300, 'Waveshare 4.2"'),
        PanelProfile("waveshare_7in5", 800, 480, 'Waveshare 7.5", the panel in a TRMNL'),
        PanelProfile("kindle", 600, 800, "Kindle, portrait"),
    )
}
ALIASES = {"trmnl": "waveshare_7in5"}
DEFAULT_PROFILE = "waveshare_2in9"

_SIZE = re.compile(r"([0-9]{1,5})x([0-9]{1,5})")


def resolve(spec: str) -> PanelProfile:
    """Return the profile for a name (or alias), or for a size written `WxH`.

    Raises ValueError, naming the known profiles, for anything else.
    """
    key = spec.strip().lower()
    key = ALIASES.get(key, key)
    if key in PROFILES:
        return PROFILES[key]
    match = _SIZE.fullmatch(key)
    if match is None:
        names = ", ".join([*PROFILES, *ALIASES])
        raise ValueError(f"unknown panel {spec!r}: use one of {names}, or a size like 296x128")
    width, height = int(match.group(1)), int(match.group(2))
    if not (MIN_WIDTH <= width <= MAX_SIDE and MIN_HEIGHT <= height <= MAX_SIDE):
        raise ValueError(
            f"panel {width}x{height} is outside {MIN_WIDTH}x{MIN_HEIGHT} to {MAX_SIDE}x{MAX_SIDE}"
        )
    return PanelProfile(f"{width}x{height}", width, height, "custom size")
