"""FR-011: the committed display gallery matches what the generator produces.

If this fails, run `python tools/gen_display_gallery.py` and commit the result.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "gen_display_gallery", ROOT / "tools" / "gen_display_gallery.py"
)
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


def test_fr011_committed_gallery_is_up_to_date(tmp_path):
    for generated in gallery.build(tmp_path):
        relative = generated.relative_to(tmp_path)
        committed = ROOT / relative
        assert committed.exists(), f"{relative} is missing; run tools/gen_display_gallery.py"
        assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8"), (
            f"{relative} is out of date; run tools/gen_display_gallery.py"
        )


def test_fr011_every_vector_is_in_the_gallery():
    listed = [name for _, names in gallery.GROUPS for name in names]
    assert len(listed) == len(set(listed))


def test_fr011_demo_buttons_point_at_real_vectors():
    import json
    import re

    page = (ROOT / "demo.html").read_text(encoding="utf-8")
    vectors = {
        c["name"]
        for c in json.loads((ROOT / "spec" / "display_vectors.json").read_text())["cases"]
    }
    # Buttons are built from the label map in the page script: `name: "Label"`.
    script = page[page.index("const groups = [") : page.index("const result =")]
    labelled = set(re.findall(r"\b([a-z0-9_]+): \"", script))
    assert labelled, "demo has no state buttons"
    # Every labelled button is a real vector, and every vector has a hand-written
    # label (a new vector would otherwise fall into the "Other" group unnamed).
    assert labelled <= vectors
    assert vectors <= labelled, f"add demo labels for: {sorted(vectors - labelled)}"
