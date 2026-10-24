"""The README's diagram image, its source, and the collapsed copy stay in step.

If this fails, re-render the image as described in assets/diagrams/README.md
and paste the .mmd source into the README's collapsed block.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "assets" / "diagrams"


def test_readme_embeds_the_rendered_diagram():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "](assets/diagrams/how-it-fits-together.svg)" in readme
    assert (DIAGRAMS / "how-it-fits-together.svg").stat().st_size > 0


def test_readme_collapsed_source_matches_the_mmd_file():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    source = (DIAGRAMS / "how-it-fits-together.mmd").read_text(encoding="utf-8")
    assert f"```mermaid\n{source}```" in readme
