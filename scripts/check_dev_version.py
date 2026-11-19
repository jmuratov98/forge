#!/usr/bin/env python3
"""Checks that a Forge version is valid SemVer 2.0.0 and an ADR 0001 dev version.

    check_dev_version.py --header build/generated/version.inc.hpp
    check_dev_version.py --require-ci-form --header build/generated/version.inc.hpp
    echo 0.1.0-alpha+dev.local | check_dev_version.py --stdin

A dev version is X.Y.Z[-{alpha|beta|rc}[.N]]+dev.local or
X.Y.Z[-{alpha|beta|rc}[.N]]+dev.{YYYYMMDDHHMMSS}.g{shortsha}; --require-ci-form
accepts only the second. Prints the version when it is valid.
"""

import argparse
import re
import sys

# The regular expression from semver.org.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
STAGE = r"(?:-(?:alpha|beta|rc)(?:\.[1-9][0-9]*)?)?"
LOCAL = re.compile(r"^\d+\.\d+\.\d+" + STAGE + r"\+dev\.local$")
CI = re.compile(r"^\d+\.\d+\.\d+" + STAGE + r"\+dev\.\d{14}\.g[0-9a-f]{7}$")
HEADER = re.compile(r'^#define FORGE_VERSION_STRING "([^"]*)"$', re.MULTILINE)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--header", help="the generated version.inc.hpp")
    source.add_argument("--version", help="the version string")
    source.add_argument("--stdin", action="store_true", help="read the version from stdin")
    parser.add_argument("--require-ci-form", action="store_true",
                        help="reject +dev.local: the build must carry a timestamp and commit")
    args = parser.parse_args()

    if args.header:
        with open(args.header, encoding="utf-8") as header:
            match = HEADER.search(header.read())
        if not match:
            sys.exit("%s: no FORGE_VERSION_STRING definition" % args.header)
        version = match.group(1)
    elif args.stdin:
        version = sys.stdin.read().strip()
    else:
        version = args.version

    if not SEMVER.match(version):
        sys.exit("%r is not valid SemVer 2.0.0" % version)
    if not (CI.match(version) or (LOCAL.match(version) and not args.require_ci_form)):
        wanted = "+dev.{timestamp}.g{sha}" if args.require_ci_form else "+dev.local or +dev.{timestamp}.g{sha}"
        sys.exit("%r is not an ADR 0001 dev version (expected %s)" % (version, wanted))
    print(version)


if __name__ == "__main__":
    main()
