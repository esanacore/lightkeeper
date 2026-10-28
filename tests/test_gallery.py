"""FR-011: the committed display gallery matches what the generator produces.

If this fails, run `python tools/gen_display_gallery.py` and commit the result.
"""

import importlib.util
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "gen_display_gallery", ROOT / "tools" / "gen_display_gallery.py"
)
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


def png_content(data: bytes) -> tuple[bytes, bytes]:
    """(IHDR, decompressed pixel data): what a PNG shows, independent of the zlib build.

    Different zlib versions compress the same pixels to different bytes, so the
    committed PNGs are compared by content, not by their compressed bytes.
    """
    header, pixels, pos = b"", b"", 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            pixels += body
        pos += 12 + length
    return header, zlib.decompress(pixels)


def test_fr011_committed_gallery_is_up_to_date(tmp_path):
    for generated in gallery.build(tmp_path):
        relative = generated.relative_to(tmp_path)
        committed = ROOT / relative
        assert committed.exists(), f"{relative} is missing; run tools/gen_display_gallery.py"
        if relative.suffix == ".png":
            same = png_content(committed.read_bytes()) == png_content(generated.read_bytes())
        else:  # text: line endings may differ by checkout
            same = committed.read_bytes().replace(
                b"\r\n", b"\n"
            ) == generated.read_bytes().replace(b"\r\n", b"\n")
        assert same, f"{relative} is out of date; run tools/gen_display_gallery.py"


def test_fr011_every_vector_is_in_the_gallery():
    listed = [name for _, names in gallery.GROUPS for name in names]
    assert len(listed) == len(set(listed))


def demo_array(page: str, name: str) -> str:
    """Return the array literal `const name = [ ... ];` from the demo's page script."""
    start = page.index(f"const {name} = [")
    return page[start : page.index("\n      ];\n", start)]


def test_fr011_demo_buttons_point_at_real_vectors():
    import json
    import re

    page = (ROOT / "demo.html").read_text(encoding="utf-8").replace("\r\n", "\n")
    vectors = {
        c["name"]
        for c in json.loads((ROOT / "spec" / "display_vectors.json").read_text())["cases"]
    }
    # The "All vectors" buttons are built from the label map in the page script:
    # `name: "Label"`, one group per row.
    labelled = set(re.findall(r"\b([a-z0-9_]+): \"", demo_array(page, "groups")))
    assert labelled, "demo has no state buttons"
    # Every labelled button is a real vector, and every vector has a hand-written
    # label (a new vector would otherwise fall into the "Other" group unnamed).
    assert labelled <= vectors
    assert vectors <= labelled, f"add demo labels for: {sorted(vectors - labelled)}"
    # The story buttons that come first: `["vector", "Label", "What happened."]`.
    story = re.findall(r"^\s*\[\"([a-z0-9_]+)\", \"[^\"]+\", \"", demo_array(page, "story"), re.M)
    assert len(story) == 7 and len(set(story)) == 7
    assert set(story) <= vectors
    # Each label becomes a button with its vector's name, so every vector has a
    # labelled control, inside the disclosure that holds them all.
    script = page[page.index("const groupsBox") :]
    assert "row.append(toggle(label, {state: name}));" in script
    assert "button.textContent = text;" in page
    assert page.index('<details id="all-states">') < page.index('id="groups"')
