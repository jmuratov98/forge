#!/usr/bin/env python3
"""Configures, builds and tests one preset the way a CI job does.

    ci_build.py --preset ci-debug --cxx g++-11 --cc gcc-11 \\
        --timestamp 20261118153000 --sha 7643163

Runs cmake --preset, builds everything, runs the `check` target, and when a
timestamp is given checks that the configured version has the ADR 0001 CI form.
CI and contributors run the same commands. Needs lit installed (see
docs/building.md).
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--preset", required=True, help="a preset in CMakePresets.json")
    parser.add_argument("--cxx", help="the C++ compiler")
    parser.add_argument("--cc", help="the C compiler (the end-to-end self-test uses it)")
    parser.add_argument("--timestamp", help="FORGE_BUILD_TIMESTAMP, YYYYMMDDHHMMSS in UTC")
    parser.add_argument("--sha", help="FORGE_BUILD_SHA, the first 7 hex characters of the commit")
    args = parser.parse_args()

    configure = ["cmake", "--preset", args.preset]
    if args.cxx:
        configure.append("-DCMAKE_CXX_COMPILER=" + args.cxx)
    if args.cc:
        configure.append("-DCMAKE_C_COMPILER=" + args.cc)
    if args.timestamp:
        configure.append("-DFORGE_BUILD_TIMESTAMP=" + args.timestamp)
        configure.append("-DFORGE_BUILD_SHA=" + (args.sha or ""))

    try:
        run(configure)
        run(["cmake", "--build", "--preset", args.preset])
        run(["cmake", "--build", "--preset", args.preset, "--target", "check"])
        if args.timestamp:
            header = os.path.join(ROOT, "build", args.preset, "generated", "version.inc.hpp")
            run([sys.executable, os.path.join(ROOT, "scripts", "check_dev_version.py"),
                 "--require-ci-form", "--header", header])
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
