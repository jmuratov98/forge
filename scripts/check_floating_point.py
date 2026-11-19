#!/usr/bin/env python3
"""Rejects `float` and `double` outside core.

    check_floating_point.py [--root REPO]

ADR 0005: Forge's output is byte-identical across hosts, so target floating
point is folded in software and float literals are parsed by core. Host
floating point is for core's software floating point and its timing utilities
only. Exits 1 and prints file:line for each use.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpp_scan  # noqa: E402

CORE_DIRECTORY = "forge/core/"
KEYWORD = re.compile(r"\b(float|double)\b")
# Lines whose text is not code: <float.h> is a header name, not the type.
NOT_CODE = re.compile(r"^[ \t]*#[ \t]*(include|error|warning|pragma)\b")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=os.path.join(os.path.dirname(__file__), ".."),
                        help="the repository root (default: this one)")
    args = parser.parse_args()

    failures = 0
    checked = 0
    for path, relative in cpp_scan.source_files(args.root):
        if relative.startswith(CORE_DIRECTORY):
            continue
        checked += 1
        with open(path, encoding="utf-8", errors="replace") as source:
            lines = cpp_scan.blank_comments_and_strings(source.read()).split("\n")
        for number, line in enumerate(lines, 1):
            if NOT_CODE.match(line):
                continue
            for match in KEYWORD.finditer(line):
                print("%s:%d: error: '%s' outside core; target floating point is "
                      "software (ADR 0005)" % (relative, number, match.group(1)),
                      file=sys.stderr)
                failures += 1
    if failures:
        return 1
    print("check_floating_point: %d files ok" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
