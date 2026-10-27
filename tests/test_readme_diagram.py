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


def test_every_local_readme_link_and_image_exists():
    """A renamed render or doc must not leave the README pointing at nothing."""
    import re

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)\s]+)\)", readme)
    local = [t.split("#", 1)[0] for t in targets if not re.match(r"^(https?:|mailto:|#)", t)]
    assert "hardware/enclosure/renders/hero.png" in local
    missing = sorted({t for t in local if t and not (ROOT / t).exists()})
    assert missing == [], f"README links to missing files: {missing}"
