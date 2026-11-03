#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Adds a forge component: python3 new_component.py NAME [--deps A,B] [--header-only] [-n]

Creates forge/include/forge/NAME/NAME.hpp, forge/source/forge/NAME/NAME.cpp (unless
--header-only) and forge/unittests/NAME/NAME_test.cpp, and appends a forge.component and a
forge.test entry to forge/premake5.lua. With -n, prints what it would do and changes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SPDX = "SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
# The entries of forge/premake5.lua, as premake/forge.lua's forge.component and forge.test read them.
ENTRY = re.compile(r'forge\.(component|test)\s*\{\s*"([a-z][a-z0-9_]*)"')
DEPENDENCIES = re.compile(r'forge\.component\s*\{\s*"([a-z][a-z0-9_]*)"\s*,\s*dependencies\s*=\s*\{([^}]*)\}')


def repository_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        if (directory / "x.py").is_file() and (directory / "forge" / "premake5.lua").is_file():
            return directory
    sys.exit("new_component.py: cannot find the forge repository above this script")


def snake_name(text: str) -> str:
    if not NAME.match(text):
        raise argparse.ArgumentTypeError(f"'{text}' is not a snake_case name")
    return text


def name_list(text: str) -> list[str]:
    return [snake_name(name.strip()) for name in text.split(",") if name.strip()]


def lua_list(names: list[str]) -> str:
    return "{ " + ", ".join(f'"{name}"' for name in names) + " }" if names else "{}"


def files(name: str, header_only: bool) -> dict[str, str]:
    header = f"forge/{name}/{name}.hpp"
    result = {
        f"forge/include/{header}": f"""// {SPDX}

#pragma once

#include "forge/core/config.hpp"
""",
        f"forge/unittests/{name}/{name}_test.cpp": f"""// {SPDX}

#include "{header}"

#include <gtest/gtest.h>
""",
    }
    if not header_only:
        result[f"forge/source/forge/{name}/{name}.cpp"] = f"""// {SPDX}

#include "{header}"
"""
    return result


def premake_entries(name: str, dependencies: list[str]) -> str:
    return (f"    forge.component {{ \"{name}\",\n"
            f"        dependencies = {lua_list(dependencies)}\n"
            f"    }},\n"
            f"    forge.test {{ \"{name}\",\n"
            f"        dependencies = {lua_list([name])}\n"
            f"    }},\n")


def closure(graph: dict[str, list[str]], names: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(names)
    while stack:
        name = stack.pop()
        if name not in seen:
            seen.add(name)
            stack += graph.get(name, [])
    return seen


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="new_component.py", description=__doc__.split("\n\n")[1])
    parser.add_argument("name", type=snake_name)
    parser.add_argument("--deps", type=name_list, default=[], metavar="A,B",
                        help="the components it depends on (core is not implied)")
    parser.add_argument("--header-only", action="store_true", help="no .cpp: the component is never linked")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = repository_root()
    premake = root / "forge" / "premake5.lua"
    text = premake.read_text(encoding="utf-8")
    declared = {(kind, name) for kind, name in ENTRY.findall(text)}
    components = {name for kind, name in declared if kind == "component"}
    graph = {name: re.findall(r'"([a-z][a-z0-9_]*)"', deps) for name, deps in DEPENDENCIES.findall(text)}

    problems = []
    if args.name in components or ("test", args.name) in declared:
        problems.append(f"forge/premake5.lua already declares '{args.name}'")
    problems += [f"'{dep}' is not a component in forge/premake5.lua" for dep in args.deps
                 if dep not in components]
    if args.name in closure(graph, args.deps):
        problems.append(f"depending on {', '.join(args.deps)} would make a cycle through '{args.name}'")
    new_files = files(args.name, args.header_only)
    problems += [f"{path} exists" for path in new_files if (root / path).exists()]

    # The entries go before the list's closing brace, after an entry that ends with a comma.
    lines = text.splitlines(keepends=True)
    close = max((i for i, line in enumerate(lines) if line.rstrip() == "}"), default=None)
    if close is None or not lines[close - 1].rstrip().endswith(","):
        problems.append("forge/premake5.lua does not end with `<entry>,` then `}`; add the entries by hand")
    if problems:
        for problem in problems:
            print(f"new_component.py: error: {problem}", file=sys.stderr)
        return 1

    entries = premake_entries(args.name, args.deps)
    updated = "".join(lines[:close]) + entries + "".join(lines[close:])
    for path, content in new_files.items():
        print(f"create {path}")
        if not args.dry_run:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(content, encoding="utf-8", newline="\n")
    print(f"update forge/premake5.lua:\n{entries}", end="")
    if not args.dry_run:
        premake.write_text(updated, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
