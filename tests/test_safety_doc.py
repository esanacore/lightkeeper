"""The hazard log and the traceability matrix cite only tests that exist.

docs/SAFETY.md names the test behind each hazard's mitigation, and
docs/REQUIREMENTS_TRACEABILITY.md the tests behind each requirement. A renamed
or deleted test would leave either one advertising a check that no longer
runs, so every test either document cites is looked up here:

- `test_x` is a Python test function under tests/, a tests/ module, or a C++
  host test `void test_x(` under firmware/. A citation ending in `_` (such as
  `test_fr003_`) is a prefix that at least one test function must start with.
- `testX` is a Swift `func testX` or a Kotlin `fun testX` under apps/, and
  `XTests` (or Kotlin's `XTest`) a test class, a test target declared in a
  Package.swift or project.yml, or a folder of that name.
- A cited test file or folder (`tests/test_cli.py`, `VectorTests.swift`,
  `panel.test.mjs`, `tests/`, `apps/ios/Lightkeeper/Tests/`) exists, by its
  path from the repository root or, for a bare name, anywhere under tests/,
  apps/, firmware/ or web/. A test file of any suffix is looked up, so one in
  a new language is never passed unread.
- `-k word`, and every word of a quoted `-k "fr001 or fr002"`, selects at
  least one Python test by name. When the table cell (or line) cites Python
  test files before it, it must select a test in one of them: in
  `tests/test_deploy.py` (`-k haz002`) the haz002 tests must live in
  test_deploy.py. A `-k` with no new file since the previous one shares that
  one's files, as in `tests/test_cli.py` (`-k fr008`, `-k haz013`).
- A shared vector, named straight after the word "vector" (`vector
  huge_value_rejected` in backticks), is a case in a spec/*_vectors.json file.

A hazard whose test is not written yet says so in words, as HAZ-010 does,
rather than naming a test that does not exist.
"""

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["docs/SAFETY.md", "docs/REQUIREMENTS_TRACEABILITY.md"]
TEST_ROOTS = ("tests", "apps", "firmware", "web")
SKIP_DIRS = {"__pycache__", "node_modules", "build"}

# A `-k` selector (bare, or a quoted expression) or else one token of text.
SCAN = re.compile(
    r"(?<![\w-])-k\s+(?:\"[^\"]*\"|'[^']*'|[A-Za-z0-9_]+)|(?P<token>[A-Za-z0-9_./-]+)"
)
WORD = re.compile(r"[A-Za-z0-9_]+")
OPERATORS = {"and", "or", "not"}
VECTOR = re.compile(r"\bvectors?\s+((?:`\w+`(?:,\s*|\s+(?:and|or)\s+)?)+)", re.IGNORECASE)
EXTENSION = re.compile(r"[A-Za-z][A-Za-z0-9]{0,5}")
PYTHON_TEST = re.compile(r"test_[A-Za-z0-9_]+")
SWIFT_TEST = re.compile(r"test[A-Z][A-Za-z0-9_]*")
SWIFT_CLASS = re.compile(r"[A-Z][A-Za-z0-9]*Tests?")


@dataclass
class Citations:
    """Every test identifier one document cites, by kind."""

    python: set[str] = field(default_factory=set)
    swift: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    # (word, the Python test files it must select a test in; empty means any).
    keywords: set[tuple[str, tuple[str, ...]]] = field(default_factory=set)
    vectors: set[str] = field(default_factory=set)


@dataclass
class Index:
    """Every test that exists in the repository, by kind."""

    python: set[str] = field(default_factory=set)
    modules: set[str] = field(default_factory=set)
    by_file: dict[str, set[str]] = field(default_factory=dict)
    cpp: set[str] = field(default_factory=set)
    swift: set[str] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    file_names: set[str] = field(default_factory=set)
    dir_names: set[str] = field(default_factory=set)
    vectors: set[str] = field(default_factory=set)


def is_test_file(name):
    """`test_x.py`, `XTests.swift`, `XTest.kt`, `x_test.cpp`, `x.test.mjs` or `x.spec.js`."""
    parts = name.split(".")
    return (
        parts[0].startswith("test_")
        or parts[0].endswith(("Test", "Tests", "_test"))
        or any(part in ("test", "spec") for part in parts[1:-1])
    )


def has_extension(name):
    return "." in name and EXTENSION.fullmatch(name.rsplit(".", 1)[1]) is not None


def cited(text):
    """Pick the test identifiers out of a document's text."""
    found = Citations()
    for line in text.splitlines():
        for cell in line.split("|"):
            cite_cell(cell, found)
    for match in VECTOR.finditer(text):
        found.vectors.update(re.findall(r"`(\w+)`", match.group(1)))
    return found


def cite_cell(cell, found):
    """Add one table cell's citations (or one line's, outside a table) to `found`."""
    scope: tuple[str, ...] = ()
    since: set[str] = set()  # Python test files cited since the previous -k
    for match in SCAN.finditer(cell):
        raw = match.group("token")
        if raw is None:
            if since:
                scope, since = tuple(sorted(since)), set()
            words = WORD.findall(match.group(0).split(None, 1)[1])
            found.keywords.update((w, scope) for w in words if w.lower() not in OPERATORS)
            continue
        # Drop sentence full stops, the "..." of `test_fr003_...`, and a leading "../".
        token = raw.strip(".-").lstrip("/")
        name = token.rstrip("/").rsplit("/", 1)[-1]
        if token.endswith("/"):
            if "test" in token.lower():
                found.files.add(token)
        elif has_extension(name):
            if is_test_file(name):
                found.files.add(token)
                if name.endswith(".py"):
                    since.add(name)
        elif PYTHON_TEST.fullmatch(token):
            found.python.add(token)
        elif SWIFT_TEST.fullmatch(token):
            found.swift.add(token)
        elif SWIFT_CLASS.fullmatch(token):
            found.classes.add(token)


def walk(top):
    """os.walk under ROOT/top, skipping hidden and build folders."""
    for folder, subfolders, names in os.walk(ROOT / top):
        subfolders[:] = [d for d in subfolders if not d.startswith(".") and d not in SKIP_DIRS]
        yield Path(folder), subfolders, names


def files_under(top, *endings):
    for folder, _, names in walk(top):
        yield from (folder / name for name in names if name.endswith(endings))


def read(path):
    return path.read_text(encoding="utf-8")


def vector_names():
    """Every case name in the shared vector files under spec/.

    Display and response cases carry a `name`; panel cases name their display
    vector in `vector`; the spoken file is a map keyed by vector name.
    """
    names = set()
    for path in (ROOT / "spec").glob("*_vectors.json"):
        spec = json.loads(read(path))
        cases = spec.get("cases", []) if isinstance(spec, dict) else []
        if isinstance(cases, dict):
            names.update(cases)
        else:
            for case in cases:
                if isinstance(case, dict):
                    names.update(case[key] for key in ("name", "vector") if key in case)
    return names


def build_index():
    index = Index(vectors=vector_names())
    for top in TEST_ROOTS:
        for _, subfolders, names in walk(top):
            index.dir_names.update(subfolders)
            index.classes.update(d for d in subfolders if SWIFT_CLASS.fullmatch(d))
            index.file_names.update(names)
    for path in files_under("tests", ".py"):
        functions = {
            node.name
            for node in ast.walk(ast.parse(read(path)))
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test")
        }
        index.python |= functions
        index.by_file.setdefault(path.name, set()).update(functions)
        if path.name.startswith("test_"):
            index.modules.add(path.stem)
    for path in files_under("apps", ".swift", ".kt"):
        text = read(path)
        index.swift.update(re.findall(r"\bfunc?\s+(test\w+)\s*\(", text))
        index.classes.update(re.findall(r"\bclass\s+(\w+Tests?)\b", text))
        index.classes.update(re.findall(r"\.testTarget\(\s*name:\s*\"(\w+)\"", text))
    for path in files_under("apps", "project.yml"):
        for listed in re.findall(r"\btestTargets:\s*\[([^\]]*)\]", read(path)):
            index.classes.update(WORD.findall(listed))
    for path in files_under("firmware", ".cpp", ".h"):
        index.cpp.update(re.findall(r"\bvoid\s+(test_\w+)\s*\(", read(path)))
    return index


INDEX = build_index()


def selects(word, names):
    """Whether `-k word` picks one of `names`, matching it as a whole `_`-separated part.

    So `-k fr001` is not satisfied by `test_nfr001_...` alone (pytest itself
    would select those).
    """
    return any(f"_{word.lower()}_" in f"_{name.lower()}_" for name in names)


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
    problems += [f"{n}: no Swift or Kotlin func {n}" for n in sorted(found.swift - index.swift)]
    for name in sorted(found.classes - index.classes):
        problems.append(f"{name}: no test class, test target, or folder {name}")
    for path in sorted(found.files):
        bare = "/" not in path.rstrip("/")
        if path.endswith("/"):
            ok = (ROOT / path).is_dir() or (bare and path.rstrip("/") in index.dir_names)
        elif bare:
            ok = path in index.file_names
        else:
            ok = (ROOT / path).is_file()
        if not ok:
            problems.append(f"{path}: no such test file or folder")
    for word, scope in sorted(found.keywords):
        if scope:
            names = {Path(file).stem for file in scope}
            names.update(*(index.by_file.get(file, set()) for file in scope))
            where = " in " + ", ".join(scope)
        else:
            names, where = index.python | index.modules, ""
        if not selects(word, names):
            problems.append(f"-k {word}: selects no Python test{where}")
    for name in sorted(found.vectors - index.vectors):
        problems.append(f"{name}: no case {name} in spec/*_vectors.json")
    return problems


def doc_text(doc):
    return read(ROOT / doc)


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
    assert ("haz002", ("test_deploy.py",)) in found.keywords, "a -k is held to its file"
    assert "huge_value_rejected" in found.vectors, "HAZ-011's shared vector is checked"
    assert len(INDEX.python) > 150 and INDEX.swift and INDEX.cpp and INDEX.classes
    assert {"LightkeeperCoreTests", "LightkeeperTests"} <= INDEX.classes, "test targets"
    assert {"no_data", "huge_value_rejected"} <= INDEX.vectors
    assert "test_haz002_" in "".join(INDEX.by_file["test_deploy.py"])


def test_every_kind_of_missing_citation_is_reported():
    text = (
        "| HAZ-999 | ... | `test_fr999_never_written`, `test_zz9_`, `test_ZZ9_capitals`, Swift "
        "`testNothingLikeThis` and `NoSuchTests`, Kotlin `NoSuchTest`, `GoneTests.swift`, "
        "`gone.test.mjs`, `GoneRulesTest.kt`, `apps/ios/Nowhere/Tests/`, `NowhereTests/`, "
        "`tests/test_spoken.py/`, `test_fr003_staleness_beats_urgent_lo`, "
        "shared vector `no_such_case` |\n"
        '| HAZ-998 | `tests/test_gone.py` (`-k zz999`) | `pytest -k "zz1 or not zz2"` '
        "| `tests/test_status.py` (`-k haz002`) |"
    )
    problems = missing(cited(text))
    reported = [
        "test_fr003_staleness_beats_urgent_lo:",
        "test_fr999_never_written:",
        "test_zz9_:",
        "test_ZZ9_capitals:",
        "testNothingLikeThis:",
        "NoSuchTest:",
        "NoSuchTests:",
        "tests/test_gone.py:",
        "GoneTests.swift:",
        "gone.test.mjs:",
        "GoneRulesTest.kt:",
        "apps/ios/Nowhere/Tests/:",
        "NowhereTests/:",
        "tests/test_spoken.py/:",
        "-k zz999: selects no Python test in test_gone.py",
        "-k zz1: selects no Python test",
        "-k zz2: selects no Python test",
        "-k haz002: selects no Python test in test_status.py",
        "no_such_case:",
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


def test_a_keyword_must_select_a_test_in_the_files_cited_before_it():
    """`tests/test_deploy.py` (`-k haz002`) goes stale if the haz002 tests move elsewhere."""
    index = Index(
        python={"test_haz002_watchdog", "test_haz011_survives"},
        modules={"test_deploy", "test_cli"},
        by_file={
            "test_deploy.py": {"test_haz002_watchdog"},
            "test_cli.py": {"test_haz011_survives"},
        },
    )
    found = cited(
        "| `tests/test_deploy.py` (`-k haz002`) | `tests/test_cli.py` (`-k haz002`) |\n"
        "| `tests/test_cli.py`, `tests/test_deploy.py` (`-k haz011`, `-k haz002`) |\n"
        "| `tests/test_cli.py` (`-k haz011`); later `tests/test_deploy.py` (`-k haz011`) |\n"
        "On a line with no file of its own, `-k haz002` may select a test anywhere.\n"
        "`tests/test_cli.py` (`-k cli`) selects by the module's name, as pytest does."
    )
    assert missing(found, index) == [
        "-k haz002: selects no Python test in test_cli.py",
        "-k haz011: selects no Python test in test_deploy.py",
    ]


def test_real_tests_of_every_kind_are_found():
    text = (
        "`test_fr003_` and `test_fr003_staleness_beats_urgent_low` (`-k fr003`), the module "
        "`test_deploy`, C++ `test_parse_edges` in `test_glucose_rules.cpp`, Swift "
        "`testTokenTravelsInAHeaderNeverTheURL` in `NightscoutClientTests`, the test targets "
        "`LightkeeperCoreTests` and `LightkeeperTests`, `VectorTests.swift`, "
        "`apps/ios/Lightkeeper/Tests/`, `Tests/`, `tests/`, `../tests/test_cli.py`, and the "
        "shared vectors `huge_value_rejected` and `no_data`.\n"
        '| HAZ-002 | `tests/test_deploy.py` (`-k haz002`) | `pytest -k "fr003 and not fr002"` |'
    )
    found = cited(text)
    assert found.python == {
        "test_fr003_",
        "test_fr003_staleness_beats_urgent_low",
        "test_deploy",
        "test_parse_edges",
    }
    assert found.swift == {"testTokenTravelsInAHeaderNeverTheURL"}
    assert found.classes == {"NightscoutClientTests", "LightkeeperCoreTests", "LightkeeperTests"}
    assert found.files == {
        "test_glucose_rules.cpp",
        "VectorTests.swift",
        "apps/ios/Lightkeeper/Tests/",
        "Tests/",
        "tests/",
        "tests/test_cli.py",
        "tests/test_deploy.py",
    }
    assert found.keywords == {("fr003", ()), ("fr002", ()), ("haz002", ("test_deploy.py",))}
    assert found.vectors == {"huge_value_rejected", "no_data"}
    assert missing(found) == []


def test_prose_about_tests_is_not_read_as_a_citation():
    found = cited(
        "Tests assert this; tests against a fake Trio (not yet written), testing, TestFlight, "
        "`make -C firmware/xteink test`, `pytest --cov`, docs/TEST_PLAN.md, `apps/ios/`, "
        "the vectors above, shared vectors keep every port in step, `-k` alone, e.g. a test."
    )
    assert found == Citations()
