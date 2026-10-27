"""Render every Mermaid diagram in assets/diagrams/ to SVG with the brand config.

Writes assets/diagrams/manifest.json with the SHA-256 of each source and of the
config, so tests/test_diagrams.py fails when a diagram changes without a
re-render (CI has no Mermaid CLI).

Usage (from the repo root), with the Mermaid CLI installed:
    npm install --no-save @mermaid-js/mermaid-cli
    python tools/render_diagrams.py [--mmdc PATH] [--puppeteer-config PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "assets" / "diagrams"
CONFIG = DIAGRAMS / "mermaid-config.json"
MANIFEST = DIAGRAMS / "manifest.json"


def sha256(path: Path) -> str:
    """Hex digest of a file, ignoring line-ending differences."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sources() -> list[Path]:
    """Every diagram source, in a stable order."""
    return sorted(DIAGRAMS.glob("*.mmd"))


def manifest() -> dict[str, object]:
    """Hashes of what the committed SVGs were rendered from."""
    return {
        "config": sha256(CONFIG),
        "diagrams": {p.stem: {"source": sha256(p), "svg": f"{p.stem}.svg"} for p in sources()},
    }


def main(argv: list[str] | None = None) -> int:
    """Render each source and write the manifest."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--mmdc", default=shutil.which("mmdc"), help="path to the mmdc binary")
    parser.add_argument("--puppeteer-config", help="puppeteer config (to use a local browser)")
    args = parser.parse_args(argv)
    if not args.mmdc:
        print("mmdc not found: install @mermaid-js/mermaid-cli", file=sys.stderr)
        return 1
    for source in sources():
        command = [args.mmdc, "-i", str(source), "-o", str(source.with_suffix(".svg"))]
        command += ["-b", "white", "-c", str(CONFIG)]
        if args.puppeteer_config:
            command += ["-p", args.puppeteer_config]
        subprocess.run(command, check=True)  # noqa: S603 (arguments built here)
        print(f"rendered {source.with_suffix('.svg').relative_to(ROOT)}")
    MANIFEST.write_text(json.dumps(manifest(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
