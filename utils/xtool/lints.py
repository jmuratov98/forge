# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The lints that need no compiler: file hygiene and component layering. Pure functions over file
contents, so that utils/xtool/test can check each rule without a repository."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SPDX = "SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception"

# The comment that the SPDX line starts with, by suffix; `x` is a shell script.
COMMENT_MARKERS = {
    ".hpp": "//", ".cpp": "//", ".h": "//", ".c": "//",
    ".lua": "--", ".py": "#", ".cfg": "#", ".cmd": "@rem", "x": "#",
}
# Checked for whitespace only: these formats have no comments to put an SPDX line in.
WHITESPACE_ONLY = {".json"}

# What the files lint covers, from the repository root.
SCOPE_DIRS = ("forge", "premake", "utils")
SCOPE_FILES = ("x", "x.cmd", "x.py", "premake5.lua", "third_party/premake5.lua")
# Test inputs are not code: they are exempt from formatting and the SPDX line, and may need tabs or
# odd line endings. The lit configurations next to them are code.
TEST_DIRS = ("forge/test", "utils/xtool/test")
TEST_CODE = re.compile(r"(^|/)(lit\.cfg\.py|lit\.local\.cfg|[a-z_]+_test\.py)$")


@dataclass(frozen=True)
class Diagnostic:
    path: Path
    line: int
    column: int
    message: str
    rule: str

    def format(self, rel: Callable[[Path], str]) -> str:
        return f"{rel(self.path)}:{self.line}:{self.column}: error: {self.message} [{self.rule}]"


def _relative(root: Path, file: Path) -> str:
    return file.relative_to(root).as_posix()


def _under(relative: str, *prefixes: str) -> bool:
    return any(relative.startswith(prefix + "/") for prefix in prefixes)


def comment_marker(root: Path, file: Path) -> str | None:
    """The SPDX comment marker for a file the files lint checks fully, "" for one it checks for
    whitespace only, and None for one it skips."""
    relative = _relative(root, file)
    if not (_under(relative, *SCOPE_DIRS) or relative in SCOPE_FILES):
        return None
    if _under(relative, *TEST_DIRS) and not TEST_CODE.search(relative):
        return None
    key = file.suffix or file.name
    if key in COMMENT_MARKERS:
        return COMMENT_MARKERS[key]
    return "" if key in WHITESPACE_ONLY else None


def check_content(path: Path, data: bytes, marker: str, header: bool) -> list[Diagnostic]:
    """The hygiene rules over one file. `marker` is the SPDX comment marker, or "" to skip the SPDX
    rule; `header` asks for #pragma once."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        return [Diagnostic(path, 1, 1, f"not UTF-8 ({error.reason} at byte {error.start})", "encoding")]

    diagnostics = []
    lines = text.split("\n")
    if text and not text.endswith("\n"):
        diagnostics.append(Diagnostic(path, len(lines), len(lines[-1]) + 1,
                                      "no newline at the end of the file", "final-newline"))
    if text.endswith("\n"):
        lines.pop()

    reported_crlf = False
    for number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
            if not reported_crlf:
                diagnostics.append(Diagnostic(path, number, len(line) + 1,
                                              "CRLF line ending; forge uses LF only", "crlf"))
                reported_crlf = True
        if "\t" in line:
            diagnostics.append(Diagnostic(path, number, line.index("\t") + 1,
                                          "tab character; indent with spaces", "tab"))
        stripped = line.rstrip(" \t")
        if stripped != line:
            diagnostics.append(Diagnostic(path, number, len(stripped) + 1, "trailing whitespace",
                                          "trailing-whitespace"))

    if marker:
        expected = f"{marker} {SPDX}"
        index = 1 if lines and lines[0].startswith("#!") else 0
        actual = lines[index].rstrip("\r") if index < len(lines) else ""
        if actual != expected:
            diagnostics.append(Diagnostic(path, index + 1, 1, f"line {index + 1} must be '{expected}'",
                                          "spdx"))
    if header and not any(line.strip() == "#pragma once" for line in lines):
        diagnostics.append(Diagnostic(path, 1, 1, "header has no #pragma once", "pragma-once"))
    return sorted(diagnostics, key=lambda diagnostic: (diagnostic.line, diagnostic.column))


def fix_content(data: bytes, marker: str) -> bytes:
    """What --fix repairs: line endings, trailing whitespace, the final newline and a missing SPDX
    line. Tabs and #pragma once need a person."""
    text = data.decode("utf-8")
    lines = [line.rstrip("\r").rstrip(" \t") for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    if marker and not any("SPDX-License-Identifier" in line for line in lines[:2]):
        index = 1 if lines and lines[0].startswith("#!") else 0
        spdx = [f"{marker} {SPDX}"]
        if index < len(lines) and lines[index] != "":
            spdx.append("")
        lines[index:index] = spdx
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def check_kind(root: Path, file: Path) -> list[Diagnostic]:
    """forge/include and forge/source hold C++ headers and sources only."""
    relative = _relative(root, file)
    if _under(relative, "forge/include", "forge/source") and file.suffix not in (".hpp", ".cpp"):
        return [Diagnostic(file, 1, 1, "forge/include and forge/source hold only .hpp and .cpp files",
                           "file-kind")]
    return []


def check_file(root: Path, file: Path) -> list[Diagnostic]:
    diagnostics = check_kind(root, file)
    marker = comment_marker(root, file)
    if marker is not None:
        diagnostics += check_content(file, file.read_bytes(), marker, file.suffix == ".hpp")
    return diagnostics


INCLUDE = re.compile(r'^\s*#\s*include\s*[<"](forge/([a-z0-9_]+)/[^">]+)[">]')
OWNER = re.compile(r"^forge/(?:(include|source)/forge|(unittests))/([^/]+)/")


def closure(graph: dict[str, list[str]], names: list[str]) -> set[str]:
    """`names` and everything they depend on, directly or not."""
    result: set[str] = set()
    pending = list(names)
    while pending:
        name = pending.pop()
        if name not in result:
            result.add(name)
            pending += graph.get(name, [])
    return result


def check_layering(root: Path, files: list[Path], components: dict[str, list[str]],
                   tests: dict[str, list[str]], read: Callable[[Path], str] | None = None) -> list[Diagnostic]:
    """A component's files include forge/<d>/ only for d itself or one of its dependencies, a unit
    test's only for its own dependencies, and a public header never includes a header that only
    forge/source has. The graph is forge/premake5.lua's, as premake's forge-describe reports it."""
    read = read or (lambda file: file.read_text(encoding="utf-8", errors="replace"))
    diagnostics = []
    for file in files:
        if file.suffix not in (".hpp", ".cpp"):
            continue
        match = OWNER.match(_relative(root, file))
        if not match:
            continue
        top, unittests, name = match.groups()
        if unittests:
            if name not in tests:
                diagnostics.append(Diagnostic(file, 1, 1, f"forge/unittests/{name}/ belongs to no "
                                              "forge.test in forge/premake5.lua", "layering"))
                continue
            owner, allowed, public = f"test '{name}'", closure(components, tests[name]), False
        else:
            if name not in components:
                diagnostics.append(Diagnostic(file, 1, 1, f"forge/{top}/forge/{name}/ belongs to no "
                                              "forge.component in forge/premake5.lua", "layering"))
                continue
            owner, allowed, public = f"component '{name}'", closure(components, [name]), top == "include"

        for number, line in enumerate(read(file).splitlines(), 1):
            include = INCLUDE.match(line)
            if not include:
                continue
            path, dependency = include.groups()
            column = line.index(path) + 1
            if dependency not in components:
                diagnostics.append(Diagnostic(file, number, column, f"'{path}' is in no declared "
                                              f"component: forge/premake5.lua has no '{dependency}'",
                                              "layering"))
            elif dependency not in allowed:
                diagnostics.append(Diagnostic(file, number, column, f"{owner} cannot include '{path}': "
                                              f"'{dependency}' is not among its dependencies in "
                                              "forge/premake5.lua", "layering"))
            elif (public and not (root / "forge" / "include" / path).exists()
                  and (root / "forge" / "source" / path).exists()):
                diagnostics.append(Diagnostic(file, number, column, f"a public header cannot include "
                                              f"the private header '{path}' (forge/source/{path})",
                                              "layering"))
    return diagnostics
