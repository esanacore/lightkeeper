"""The wiki in `wiki/` stays complete, linked, and consistent with the repository.

CI publishes `wiki/` to the GitHub wiki on merge, so a page that is unlisted,
a link that dangles, a scaffold placeholder, or a stale version line ships to
readers. These checks fail the build first.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
DOCS = ROOT / "docs"
SIDEBAR = WIKI / "_Sidebar.md"

# Internal, agent, or contract documents that the wiki need not cite by path.
DOCS_NOT_REQUIRED_IN_WIKI = {
    "AGENT_HANDOFF.md",
    "AGENT_PROMPTS.md",
    "SESSION_PLAN.md",
    "MEMORY.md",
    "HELP.md",
    "COMMAND_REFERENCE.md",
    "ENV_VARS.md",
    "OTS_SOFTWARE.md",
    "REQUIREMENTS_TRACEABILITY.md",
    "PRODUCT_REQUIREMENTS.md",
    "TEST_PLAN.md",
    "OPERATIONS.md",
}

SCAFFOLD_PHRASES = ("Replace this scaffold", "Describe the project")

WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
FENCE = re.compile(r"^\s*```", re.MULTILINE)


def wiki_pages() -> list[Path]:
    return sorted(p for p in WIKI.glob("*.md") if p.name != SIDEBAR.name)


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline code, where [[...]] is not a link."""
    parts = FENCE.split(text)
    prose = "".join(part for index, part in enumerate(parts) if index % 2 == 0)
    return re.sub(r"`[^`]*`", "", prose)


def page_stem(link_target: str) -> str:
    """GitHub maps [[Display|Target]] and [[A Page#anchor]] to A-Page.md."""
    target = link_target.split("|")[-1].split("#")[0].strip()
    return target.replace(" ", "-").lower()


def test_every_page_is_listed_in_the_sidebar():
    sidebar_stems = {page_stem(link) for link in WIKI_LINK.findall(SIDEBAR.read_text())}
    missing = [p.name for p in wiki_pages() if p.stem.lower() not in sidebar_stems]
    assert not missing, f"pages missing from _Sidebar.md: {missing}"


def test_every_wiki_link_resolves_to_a_page():
    existing = {p.stem.lower() for p in WIKI.glob("*.md")}
    dangling = []
    for page in WIKI.glob("*.md"):
        for link in WIKI_LINK.findall(strip_code(page.read_text(encoding="utf-8"))):
            if "://" in link:
                continue
            if page_stem(link) not in existing:
                dangling.append(f"{page.name} -> [[{link}]]")
    assert not dangling, f"dangling wiki links: {dangling}"


def test_every_public_doc_is_cited_by_path_in_the_wiki():
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in wiki_pages())
    expected = sorted(p.name for p in DOCS.glob("*.md") if p.name not in DOCS_NOT_REQUIRED_IN_WIKI)
    assert expected, "no docs found to check; is the docs/ layout unchanged?"
    uncited = [name for name in expected if f"docs/{name}" not in corpus]
    assert not uncited, f"docs never cited by path in any wiki page: {uncited}"


def test_no_scaffold_placeholders_survive():
    leftovers = []
    for page in WIKI.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        leftovers.extend(f"{page.name}: {phrase}" for phrase in SCAFFOLD_PHRASES if phrase in text)
    assert not leftovers, f"scaffold text left in the wiki: {leftovers}"


def test_home_states_the_current_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    home = (WIKI / "Home.md").read_text(encoding="utf-8")
    assert f"Current version: {version}" in home
