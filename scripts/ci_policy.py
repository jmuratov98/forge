#!/usr/bin/env python3
"""Runs the policy checks that need clang-tidy, the way the CI `policy` job does.

    ci_policy.py [--clang-tidy clang-tidy-18]

The source-tree checks (includes, floating point, file names) run in every
host's `check`. This adds what only one host needs to run: the target graph
against docs/layout.md, and clang-tidy's naming check (.clang-tidy), both over
the real tree (using the compile commands of a Debug build) and over the
fixtures that show the rules can fail.
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "build", "policy")


def run(command):
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clang-tidy", default="clang-tidy", help="the clang-tidy executable")
    parser.add_argument("--extra-arg", action="append", default=[],
                        help="an extra compiler argument for clang-tidy; repeatable")
    args = parser.parse_args()

    tidy_path = shutil.which(args.clang_tidy)
    if not tidy_path:
        sys.exit("clang-tidy not found: " + args.clang_tidy)
    scripts = os.path.join(ROOT, "scripts")
    python = sys.executable
    try:
        run([python, os.path.join(scripts, "check_target_graph.py"), "--source-dir", ROOT,
             "--cmake-arg=-GNinja", "--cmake-arg=-DFORGE_BUILD_TESTS=OFF"])

        run(["cmake", "-S", ROOT, "-B", BUILD, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug",
             "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DFORGE_CLANG_TIDY=" + tidy_path])
        run(["cmake", "--build", BUILD])
        sources = []
        for directory in ("forge", "test"):
            for path, _, names in os.walk(os.path.join(ROOT, directory)):
                if "Inputs" in path.split(os.sep):
                    continue
                sources += [os.path.join(path, n) for n in sorted(names) if n.endswith((".cpp", ".cc"))]
        tidy = [tidy_path, "-p", BUILD, "--quiet"]
        tidy += ["--extra-arg=" + extra for extra in args.extra_arg]
        run(tidy + sorted(sources))

        run([python, "-c", "from lit.main import main; main()", "-sv",
             os.path.join(BUILD, "test", "tidy")])
    except subprocess.CalledProcessError as error:
        return error.returncode
    print("ci_policy: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
