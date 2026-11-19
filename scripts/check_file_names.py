#!/usr/bin/env python3
"""Checks that C++ source file names are snake_case (docs/style.md).

    check_file_names.py [--root REPO]

clang-tidy can't check file names, so this is the one naming rule it doesn't
cover. A name is lowercase letters, digits and underscores, with an optional
.inc before the extension (version.inc.hpp). Exits 1 and prints each offender.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpp_scan  # noqa: E402

NAME = re.compile(r"^[a-z0-9_]+(\.inc)?\.(c|cc|cpp|cxx|h|hh|hpp|hxx|inl|ipp|tpp)$")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=os.path.join(os.path.dirname(__file__), ".."),
                        help="the repository root (default: this one)")
    args = parser.parse_args()

    failures = 0
    checked = 0
    for subdirectory in ("forge", "test"):
        for _, relative in cpp_scan.source_files(args.root, subdirectory, skip_directories=("Inputs",)):
            checked += 1
            if not NAME.match(os.path.basename(relative)):
                print("%s: error: file names are snake_case (docs/style.md)" % relative,
                      file=sys.stderr)
                failures += 1
    if failures:
        return 1
    print("check_file_names: %d files ok" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
