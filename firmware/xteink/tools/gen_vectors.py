"""Turn spec/display_vectors.json into a C++ include for the host tests.

The include defines one VectorEntry array per case that has entries, then
the kVectors table that points at them.

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


def seconds_ago(item):
    """Return an entry's age in seconds, from `seconds_ago` or `minutes_ago`."""
    if "seconds_ago" in item:
        return int(item["seconds_ago"])
    return int(item["minutes_ago"]) * 60


def entry_init(item):
    """One C++ VectorEntry initializer for an `entry` plus its age."""
    entry = item["entry"]
    sgv = entry.get("sgv")
    has_sgv = isinstance(sgv, (int, float)) and not isinstance(sgv, bool)
    return (
        "{"
        f"{c_str(entry.get('type'))}, {'true' if has_sgv else 'false'}, "
        f"{float(sgv) if has_sgv else 0.0}, {c_str(entry.get('direction'))}, "
        f"{seconds_ago(item)}LL"
        "}"
    )


def main(src, dst):
    """Write the entry arrays and the kVectors table for every case in `src` to `dst`."""
    with open(src, encoding="utf-8") as fh:
        spec = json.load(fh)
    cases = spec["cases"]
    out = [
        "// Generated from spec/display_vectors.json by tools/gen_vectors.py. Do not edit.",
        f"// spec_version {int(spec['spec_version'])}",
    ]
    rows = []
    for index, case in enumerate(cases):
        items = case["entries"] if "entries" in case else [case]
        items = [item for item in items if item["entry"] is not None]
        if items:
            out.append(
                f"const VectorEntry kEntries{index}[] = {{"
                + ", ".join(entry_init(item) for item in items)
                + "};"
            )
        entries = f"kEntries{index}" if items else "nullptr"
        custom = case.get("thresholds")
        if custom is None:
            limits = "false, 0, 0, 0, 0, 0"
        else:
            limits = (
                f"true, {int(custom['urgent_low'])}, {int(custom['low'])}, "
                f"{int(custom['high'])}, {int(custom['urgent_high'])}, "
                f"{int(custom['stale_after_minutes'])}"
            )
        lines = case["lines"] + [None] * (4 - len(case["lines"]))
        rows.append(
            "    {"
            f"{c_str(case['name'])}, {len(items)}, {entries}, "
            f"{'true' if case['error'] else 'false'}, {limits}, {c_str(case['level'])}, "
            f"{len(case['lines'])}, {{{', '.join(c_str(x) for x in lines)}}}"
            "},"
        )
    out += ["const Vector kVectors[] = {", *rows, "};"]
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    version_path = dst.rsplit(".", 1)[0] + "_version.inc"
    with open(version_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{int(spec['spec_version'])}\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
