"""Turn spec/display_vectors.json into a C++ include for the host tests.

Run by the Makefile, so the firmware tests always use the same vectors as
the Python suite. Usage: python gen_vectors.py <vectors.json> <out.inc>
"""

import json
import sys


def c_str(value):
    """Return `value` as a C++ string literal, or nullptr for None."""
    if value is None:
        return "nullptr"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main(src, dst):
    """Write one C++ Vector initializer per case in `src` to `dst`."""
    with open(src, encoding="utf-8") as fh:
        spec = json.load(fh)
    cases = spec["cases"]
    out = [
        "// Generated from spec/display_vectors.json by tools/gen_vectors.py. Do not edit.",
        f"// spec_version {int(spec['spec_version'])}",
    ]
    for case in cases:
        entry = case["entry"]
        has_entry = "true" if entry is not None else "false"
        entry = entry or {}
        sgv = entry.get("sgv")
        has_sgv = isinstance(sgv, (int, float)) and not isinstance(sgv, bool)
        lines = case["lines"] + [None] * (4 - len(case["lines"]))
        out.append(
            "{"
            f"{c_str(case['name'])}, {has_entry}, {c_str(entry.get('type'))}, "
            f"{'true' if has_sgv else 'false'}, {float(sgv) if has_sgv else 0.0}, "
            f"{c_str(entry.get('direction'))}, {case['minutes_ago']}, "
            f"{'true' if case['error'] else 'false'}, {c_str(case['level'])}, "
            f"{len(case['lines'])}, {{{', '.join(c_str(x) for x in lines)}}}"
            "},"
        )
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    version_path = dst.rsplit(".", 1)[0] + "_version.inc"
    with open(version_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{int(spec['spec_version'])}\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
