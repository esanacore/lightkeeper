"""NFR-004: CI runs the whole suite, fails fast, and keeps its pinned dependencies current.

Read as text, like the Android workflow check in tests/test_android.py: the
suite has no YAML parser, and these are the lines a reviewer reads.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def steps(workflow):
    """Each step's name (or, unnamed, its action) and its block of lines, in order."""
    blocks = re.split(r"^      - (?=name: |uses: )", workflow, flags=re.M)[1:]
    return {re.match(r"(?:name|uses): (.+)", block)[1]: block for block in blocks}


def jobs(workflow):
    """Each job's id and its block of lines."""
    body = workflow.split("\njobs:\n", 1)[1]
    blocks = re.split(r"^  (?=[\w-]+:$)", body, flags=re.M)[1:]
    return {block.split(":", 1)[0]: block for block in blocks}


def test_nfr004_the_test_runner_gives_the_real_tk_tests_a_display():
    # The real-Tk tests, evidence for HAZ-002 and HAZ-016, fail on CI with no display.
    workflow = (WORKFLOWS / "constitution-tests.yml").read_text(encoding="utf-8")
    named = steps(workflow)
    order = list(named)
    display, run = "Make sure a virtual display is available", "Run declared test command"
    assert order.index("Set up Python") < order.index(display)
    assert order.index(display) + 1 == order.index(run), order
    screen = "xvfb-run -a --server-args='-screen 0 1280x1024x24'"
    declared = "bash constitution/scripts/run_declared_tests.sh --strict ."
    assert f"run: {screen} {declared}\n" in named[run]
    guard = named[display]
    assert "command -v xvfb-run" in guard and 'python -c "import tkinter"' in guard
    assert "xvfb xauth" in guard and "libtk8.6" in guard  # what to install if either is missing
    assert screen in guard and "tkinter.Tk().destroy()" in guard  # one real window, here
    # The three tests the display is for, each behind run_real_tk.
    calls = sum(
        len(re.findall(r"^    run_real_tk\(", path.read_text(encoding="utf-8"), re.M))
        for path in (ROOT / "tests").glob("test_*.py")
    )
    assert calls == 3


def test_nfr004_dependabot_watches_the_android_gradle_build():
    config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    entries = re.findall(
        r'^  - package-ecosystem: "([\w-]+)"\n    directory: "([^"]+)"\n'
        r'    schedule:\n      interval: "(\w+)"\n',
        config,
        re.M,
    )
    assert (ROOT / "apps" / "android" / "settings.gradle.kts").is_file()
    assert ("gradle", "/apps/android", "weekly") in entries
    assert ("pip", "/", "weekly") in entries
    assert ("github-actions", "/", "weekly") in entries


def test_nfr004_the_firmware_build_fails_fast_on_a_stalled_download():
    workflow = (WORKFLOWS / "firmware-device.yml").read_text(encoding="utf-8")
    found = jobs(workflow)
    assert set(found) == {"build"}
    for job, block in found.items():
        (minutes,) = re.findall(r"^    timeout-minutes: (\d+)$", block, re.M)
        assert 0 < int(minutes) <= 30, job
