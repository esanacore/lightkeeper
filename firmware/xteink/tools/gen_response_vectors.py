"""Turn spec/response_vectors.json into a C++ include for the host tests.

Run by the Makefile. Bodies are written as C string literals with every
non-printable or non-ASCII byte as a three-digit octal escape (a hex escape
could swallow the next character), and with an explicit byte length.
Usage: python gen_response_vectors.py <response_vectors.json> <out.inc>
"""

import json
import sys


def c_bytes(data):
    """Return `data` (bytes) as a C string literal."""
    out = []
    for byte in data:
        char = chr(byte)
        if char in '"\\':
            out.append("\\" + char)
        elif 0x20 <= byte < 0x7F and char != "?":  # "?" avoids trigraphs
            out.append(char)
        else:
            out.append(f"\\{byte:03o}")
    return '"' + "".join(out) + '"'


def main(src, dst):
    """Write one ResponseVector initializer per case in `src` to `dst`."""
    with open(src, encoding="utf-8") as fh:
        spec = json.load(fh)
    out = [
        "// Generated from spec/response_vectors.json by tools/gen_response_vectors.py."
        " Do not edit.",
        f"// spec_version {int(spec['spec_version'])}",
    ]
    for case in spec["cases"]:
        body = case["body"].encode("utf-8")
        expect = case["expect"]
        if expect == "error":
            kind, mgdl, date, trend = 0, 0, 0, '""'
        elif expect is None:
            kind, mgdl, date, trend = 1, 0, 0, '""'
        else:
            kind, mgdl, date = 2, int(expect["mgdl"]), int(expect["date"])
            trend = c_bytes(expect["trend"].encode("ascii"))
        fields = [f'"{case["name"]}"', c_bytes(body), f"{len(body)}u", str(kind), str(mgdl)]
        out.append("{" + ", ".join([*fields, f"{date}LL", trend]) + "},")
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    version_path = dst.rsplit(".", 1)[0] + "_version.inc"
    with open(version_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{int(spec['spec_version'])}\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
