# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The repository's own files, for format and lint: git's list in a git checkout, otherwise a walk
that skips what x, the build and the tools generate."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

# Generated or downloaded, never linted: build directories, x's state, the googletest checkout.
SKIPPED_DIRS = {".git", ".forge", ".cache", "__pycache__", "Output"}


def _skipped(root: Path, directory: Path) -> bool:
    relative = directory.relative_to(root).as_posix()
    return (directory.name in SKIPPED_DIRS or relative == "build" or relative.startswith("build-")
            or relative == "third_party/googletest")


def all_files(root: Path) -> list[Path]:
    if (root / ".git").exists():
        listed = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others",
                                 "--exclude-standard"], capture_output=True, text=True)
        if listed.returncode == 0:
            return sorted(root / name for name in listed.stdout.split("\0") if name)
    result = []
    for directory, dirs, names in os.walk(root):
        here = Path(directory)
        dirs[:] = sorted(name for name in dirs if not _skipped(root, here / name))
        result += [here / name for name in names]
    return sorted(result)


def select(files: Iterable[Path], paths: list[Path]) -> list[Path]:
    """The files that are, or are under, one of `paths`; all of them when `paths` is empty."""
    if not paths:
        return list(files)
    resolved = [path.resolve() for path in paths]
    return [file for file in files
            if any(file == path or path in file.parents for path in resolved)]


def under(root: Path, file: Path, *prefixes: str) -> bool:
    relative = file.relative_to(root).as_posix()
    return any(relative == prefix or relative.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)
