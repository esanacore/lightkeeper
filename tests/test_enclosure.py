"""The bedside enclosure: renders and STLs match the model they were made from.

CI has no OpenSCAD, so instead of re-rendering, tools/render_enclosure.py
records the SHA-256 of every input in manifest.json; this test fails when the
model or the screen content changed without a re-render.
"""

import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENCLOSURE = ROOT / "hardware" / "enclosure"

spec = importlib.util.spec_from_file_location(
    "render_enclosure", ROOT / "tools" / "render_enclosure.py"
)
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def test_screen_include_matches_the_rasterizer():
    committed = (ENCLOSURE / "screen_in_range.scad").read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == render.screen_include(), (
        "run python tools/render_enclosure.py"
    )


def test_renders_and_stls_were_made_from_the_current_model():
    manifest = json.loads((ENCLOSURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == render.manifest(), "model changed: run python tools/render_enclosure.py"
    for path in [*manifest["renders"].values(), *manifest["stls"].values()]:
        assert (ENCLOSURE / path).stat().st_size > 1000, path


def test_stls_are_non_empty_meshes():
    for name in render.STLS.values():
        data = (ENCLOSURE / "stl" / name).read_bytes()
        if data[:5] == b"solid":
            assert data.count(b"facet normal") > 100, name
        else:
            (triangles,) = struct.unpack("<I", data[80:84])
            assert triangles > 100 and len(data) == 84 + 50 * triangles, name


def test_screen_runs_cover_the_ink():
    lines = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    runs = render.screen_runs(lines)
    ink = sum(n for _, _, n in runs)
    bitmap = render.render_bitmap(lines)
    assert ink == sum(bitmap.ink)
