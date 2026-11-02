# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Runs lit inside .forge/venv: python lit_runner.py CONFIG_MAP_JSON [lit arguments...]

The config map is the mechanism llvm-lit uses: it sends lit, when it finds a source tree's
lit.cfg.py, to a build directory's lit.site.cfg.py instead, so that `./x test forge/test/host`
works on source paths.
"""

import json
import os
import sys

# This directory holds x's own modules; none of them may shadow what lit imports.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

import lit.main  # noqa: E402


def main() -> None:
    config_map = json.loads(sys.argv[1])
    sys.argv = ["lit", *sys.argv[2:]]
    lit.main.main({"config_map": config_map})


if __name__ == "__main__":
    main()
