"""Check that this machine can build and test Lightkeeper.

Fails fast and names exactly what's missing. Run from the repo root:
    python tools/doctor.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 11)


def checks() -> list[tuple[str, bool, str]]:
    """Return (name, ok, how to fix) for every prerequisite."""
    results = [
        (
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+",
            sys.version_info[:2] >= MIN_PYTHON,
            f"you have {sys.version.split()[0]}; install 3.11 or newer (see docs/SETUP.md)",
        ),
        (
            "constitution submodule",
            (ROOT / "constitution" / "CONSTITUTION.md").exists(),
            "run: git submodule update --init --recursive",
        ),
    ]
    for module, fix in [
        ("pytest", 'pip install -e ".[dev]"'),
        ("ruff", 'pip install -e ".[dev]"'),
        ("mypy", 'pip install -e ".[dev]"'),
    ]:
        results.append((module, _importable(module), fix))
    for tool, fix in [
        ("g++", "install a C++17 compiler (needed for the firmware host tests)"),
        ("make", "install make (needed for the firmware host tests)"),
    ]:
        results.append((tool, shutil.which(tool) is not None, fix))
    return results


def _importable(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def main() -> int:
    """Print each check and return 1 if anything required is missing."""
    failed = 0
    for name, ok, fix in checks():
        print(f"  {'OK     ' if ok else 'MISSING'}  {name}" + ("" if ok else f"  ->  {fix}"))
        failed += not ok
    optional_ok = shutil.which("clang-format") is not None
    print(f"  {'OK     ' if optional_ok else 'OPTIONAL'}  clang-format (C++ format check)")
    print("Ready." if not failed else f"{failed} prerequisite(s) missing.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
