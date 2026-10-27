"""The hazard log and the traceability matrix cite only tests that exist.

docs/SAFETY.md names the test behind each hazard's mitigation, and
docs/REQUIREMENTS_TRACEABILITY.md the tests behind each requirement. A renamed
or deleted test would leave either one advertising a check that no longer
runs, so every test either document cites is looked up here:

- `test_x` is a Python test function under tests/, a tests/ module, or a C++
  host test `void test_x(` under firmware/. A citation ending in `_` (such as
  `test_fr003_`) is a prefix that at least one test function must start with.
- `testX` is a Swift `func testX` under apps/, and `XTests` a Swift test class.
- A cited test file or folder (`tests/test_cli.py`, `VectorTests.swift`,
  `apps/ios/Lightkeeper/Tests/`) exists, by its path from the repository root
  or, for a bare file name, anywhere under tests/, apps/ or firmware/.
- `-k word` selects at least one Python test by name.

A hazard whose test is not written yet says so in words, as HAZ-010 does,
rather than naming a test that does not exist.
"""

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["docs/SAFETY.md", "docs/REQUIREMENTS_TRACEABILITY.md"]
SKIP_DIRS = {"__pycache__", "node_modules", "build"}

TOKEN = re.compile(r"[A-Za-z0-9_./-]+")
KEYWORD = re.compile(r"(?<![\w-])-k\s+([A-Za-z0-9_]+)")
PYTHON_TEST = re.compile(r"test_[a-z0-9_]+")
SWIFT_TEST = re.compile(r"test[A-Z][A-Za-z0-9_]*")
SWIFT_CLASS = re.compile(r"[A-Z][A-Za-z0-9]*Tests")
TEST_FILE_SUFFIXES = (".py", ".swift", ".cpp")


@dataclass
class Citations:
    """Every test identifier one document cites, by kind."""

    python: set[str] = field(default_factory=set)
    swift: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)


@dataclass
class Index:
    """Every test that exists in the repository, by kind."""

    python: set[str] = field(default_factory=set)
    modules: set[str] = field(default_factory=set)
    cpp: set[str] = field(default_factory=set)
    swift: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    file_names: set[str] = field(default_factory=set)


def is_test_file(name):
    stem = name.rsplit(".", 1)[0]
    return stem.startswith("test_") or stem.endswith("Tests")


def cited(text):
    """Pick the test identifiers out of a document's text."""
    found = Citations(keywords=set(KEYWORD.findall(text)))
    for raw in TOKEN.findall(text):
        # Drop sentence full stops, the "..." of `test_fr003_...`, and a leading "../".
        token = raw.strip(".-").lstrip("/")
        name = token.rstrip("/").rsplit("/", 1)[-1]
        if token.endswith("/"):
            if "test" in token.lower():
                found.files.add(token)
        elif name.endswith(TEST_FILE_SUFFIXES):
            if is_test_file(name):
                found.files.add(token)
        elif PYTHON_TEST.fullmatch(token):
            found.python.add(token)
        elif SWIFT_TEST.fullmatch(token):
            found.swift.add(token)
        elif SWIFT_CLASS.fullmatch(token):
            found.classes.add(token)
    return found


def source_files(top, suffixes):
    """Files under ROOT/top with one of `suffixes`, skipping hidden and build folders."""
    for folder, subfolders, names in os.walk(ROOT / top):
        subfolders[:] = [d for d in subfolders if not d.startswith(".") and d not in SKIP_DIRS]
        for name in names:
            if name.endswith(suffixes):
                yield Path(folder) / name


def build_index():
    index = Index()
    for path in source_files("tests", (".py",)):
        index.file_names.add(path.name)
        if path.name.startswith("test_"):
            index.modules.add(path.stem)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name.startswith("test"):
                    index.python.add(node.name)
    for path in source_files("apps", (".swift",)):
        index.file_names.add(path.name)
        text = path.read_text(encoding="utf-8")
        index.swift.update(re.findall(r"\bfunc\s+(test\w+)\s*\(", text))
        index.classes.update(re.findall(r"\bclass\s+(\w+Tests)\b", text))
    for path in source_files("firmware", (".cpp", ".h")):
        index.file_names.add(path.name)
        index.cpp.update(re.findall(r"\bvoid\s+(test_\w+)\s*\(", path.read_text(encoding="utf-8")))
    return index


INDEX = build_index()


def missing(found, index=INDEX):
    """One line for every citation that names no existing test."""
    problems = []
    for name in sorted(found.python):
        if name.endswith("_"):
            ok = any(test.startswith(name) for test in index.python | index.cpp)
        else:
            ok = name in index.python | index.modules | index.cpp
        if not ok:
            problems.append(f"{name}: no Python test, tests/ module, or C++ test by that name")
    problems += [f"{n}: no Swift func {n}" for n in sorted(found.swift - index.swift)]
    problems += [f"{n}: no Swift class {n}" for n in sorted(found.classes - index.classes)]
    for path in sorted(found.files):
        if "/" in path.rstrip("/"):
            ok = (ROOT / path).exists()
        else:
            ok = path in index.file_names
        if not ok:
            problems.append(f"{path}: no such test file or folder")
    # Matched as a whole `_`-separated part of a name, so `-k fr001` is not
    # satisfied by `test_nfr001_...` alone (pytest itself would select those).
    names = {f"_{name.lower()}_" for name in index.python | index.modules}
    for word in sorted(found.keywords):
        if not any(f"_{word.lower()}_" in name for name in names):
            problems.append(f"-k {word}: selects no Python test")
    return problems


def doc_text(doc):
    return (ROOT / doc).read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", DOCS)
def test_every_test_the_document_cites_exists(doc):
    assert missing(cited(doc_text(doc))) == []


def test_the_guard_sees_every_kind_of_citation_in_the_real_documents():
    """A guard that extracts nothing would pass any document."""
    found = cited("\n".join(doc_text(doc) for doc in DOCS))
    assert len(found.python) >= 10
    assert len(found.swift) >= 5
    assert found.classes
    assert len(found.files) >= 10
    assert len(found.keywords) >= 10
    assert "test_fr003_" in found.python, "the Conventions prefix is read as a prefix"
    assert any(path.endswith("/") for path in found.files), "folders are checked too"
    assert len(INDEX.python) > 150 and INDEX.swift and INDEX.cpp and INDEX.classes


def test_every_kind_of_missing_citation_is_reported():
    text = (
        "| HAZ-999 | ... | `test_fr999_never_written`, `test_zz9_`, Swift `testNothingLikeThis` "
        "and `NoSuchTests`, `tests/test_gone.py` (`-k zz999`), `GoneTests.swift`, "
        "`apps/ios/Nowhere/Tests/`, `test_fr003_staleness_beats_urgent_lo` |"
    )
    problems = missing(cited(text))
    reported = [
        "test_fr003_staleness_beats_urgent_lo:",
        "test_fr999_never_written:",
        "test_zz9_:",
        "testNothingLikeThis:",
        "NoSuchTests:",
        "tests/test_gone.py:",
        "GoneTests.swift:",
        "apps/ios/Nowhere/Tests/:",
        "-k zz999:",
    ]
    for start in reported:
        assert any(problem.startswith(start) for problem in problems), (start, problems)
    assert len(problems) == len(reported), problems


def test_a_requirement_id_inside_another_never_satisfies_a_citation():
    """FR-001's tests are not NFR-001's: IDs are matched whole (constitution TESTING.md)."""
    index = Index(python={"test_nfr001_token_is_redacted"}, modules={"test_nightscout"})
    found = cited("`-k fr001`, `test_fr001_`, `-k nfr001`, `-k nightscout`")
    assert missing(found, index) == [
        "test_fr001_: no Python test, tests/ module, or C++ test by that name",
        "-k fr001: selects no Python test",
    ]


def test_real_tests_of_every_kind_are_found():
    text = (
        "`test_fr003_` and `test_fr003_staleness_beats_urgent_low` (`-k fr003`), the module "
        "`test_deploy`, C++ `test_parse_edges` in `test_glucose_rules.cpp`, Swift "
        "`testTokenTravelsInAHeaderNeverTheURL` in `NightscoutClientTests`, "
        "`VectorTests.swift`, `apps/ios/Lightkeeper/Tests/`, `../tests/test_cli.py`."
    )
    found = cited(text)
    assert found.python == {
        "test_fr003_",
        "test_fr003_staleness_beats_urgent_low",
        "test_deploy",
        "test_parse_edges",
    }
    assert found.swift == {"testTokenTravelsInAHeaderNeverTheURL"}
    assert found.classes == {"NightscoutClientTests"}
    assert found.files == {
        "test_glucose_rules.cpp",
        "VectorTests.swift",
        "apps/ios/Lightkeeper/Tests/",
        "tests/test_cli.py",
    }
    assert found.keywords == {"fr003"}
    assert missing(found) == []


def test_prose_about_tests_is_not_read_as_a_citation():
    found = cited(
        "Tests assert this; tests against a fake Trio (not yet written), testing, TestFlight, "
        "`make -C firmware/xteink test`, `pytest --cov`, docs/TEST_PLAN.md, `apps/ios/`."
    )
    assert found == Citations()
