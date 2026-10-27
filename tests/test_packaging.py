"""The wheel ships every module and the console script, with no runtime dependencies.

Builds the real wheel with the project's own backend (offline, no build
isolation), so a packaging change that drops a module, breaks the console
script, or adds a runtime dependency fails here instead of on a Raspberry Pi.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "lightkeeper"


def test_wheel_contains_every_module_and_the_entry_point(tmp_path):
    subprocess.run(  # noqa: S603 (fixed arguments, the test's own interpreter)
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(ROOT),
            "--no-deps",
            "--no-build-isolation",
            "--quiet",
            "--wheel-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=tmp_path,
    )
    (wheel,) = tmp_path.glob("lightkeeper-*.whl")
    names = set(zipfile.ZipFile(wheel).namelist())

    expected = {
        "lightkeeper/" + p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    assert expected <= names, f"missing from the wheel: {sorted(expected - names)}"

    dist_info = next(n.split("/")[0] for n in names if n.endswith(".dist-info/METADATA"))
    metadata = zipfile.ZipFile(wheel).read(f"{dist_info}/METADATA").decode()
    entry_points = zipfile.ZipFile(wheel).read(f"{dist_info}/entry_points.txt").decode()
    assert "lightkeeper = lightkeeper.cli:main" in entry_points
    runtime = [
        line
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist:") and "extra ==" not in line
    ]
    assert runtime == [], "runtime must stay stdlib-only (ADR-0005)"
    assert "License: Apache-2.0" in metadata
