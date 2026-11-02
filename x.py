#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""forge's developer entry point; ./x --help lists the commands. The code is in utils/xtool."""

import os
import sys

# Before anything else, and in syntax every Python 3 parses, so that an old Python gets this message
# rather than a SyntaxError from utils/xtool.
if sys.version_info < (3, 10):
    sys.exit("x.py needs Python 3.10 or newer, and %s is %s" % (sys.executable, sys.version.split()[0]))

ROOT = os.path.dirname(os.path.abspath(__file__))
# Keeps __pycache__ directories out of the source tree.
sys.pycache_prefix = os.path.join(ROOT, ".forge", "cache", "pycache")
sys.path.insert(0, os.path.join(ROOT, "utils"))

from xtool.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(ROOT, sys.argv[1:]))
