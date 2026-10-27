"""Every Mermaid diagram has a rendered SVG made from its current source.

CI has no Mermaid CLI, so tools/render_diagrams.py records the SHA-256 of each
source in assets/diagrams/manifest.json; a source edited without a re-render
fails here.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "assets" / "diagrams"
spec = importlib.util.spec_from_file_location(
    "render_diagrams", ROOT / "tools" / "render_diagrams.py"
)
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def test_diagram_svgs_were_rendered_from_the_current_sources():
    manifest = json.loads((DIAGRAMS / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == render.manifest(), "a diagram changed: run python tools/render_diagrams.py"
    for entry in manifest["diagrams"].values():
        svg = (DIAGRAMS / entry["svg"]).read_text(encoding="utf-8")
        assert svg.lstrip().startswith("<svg") and len(svg) > 2000
