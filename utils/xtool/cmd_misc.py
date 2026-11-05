# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x check, ./x run and ./x doctor."""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path

from . import buildopts, cmd_build, cmd_format, cmd_lint, cmd_test, tools
from .buildopts import MARKER
from .context import Context, read_json
from .host import FOREIGN_VENV_MAKERS, WINDOWS, exe, host_key, venv_executable
from .ui import SetupRequired, XError

RUNNABLE = (*tools.DOWNLOADED_TOOLS, "lit", "clang-format", "clang-tidy", "clang-apply-replacements",
            "FileCheck", "llvm-symbolizer", "python")


def register(subparsers, common, describe_data) -> None:
    parser = subparsers.add_parser(
        "check", parents=[common], help="format --check, lint, build and test: ready to push?",
        description="Runs format --check, lint, build and test with the same build options, goes on "
                    "past format and lint failures, skips test when build fails, and ends with a "
                    "summary.")
    buildopts.add_build_arguments(parser, describe_data)
    parser.set_defaults(handler=run_check)

    parser = subparsers.add_parser(
        "run", parents=[common], help="run one of the pinned tools",
        description=f"Runs a tool the way x does, with any arguments: {', '.join(RUNNABLE)}. For "
                    "example, IDE projects: ./x run premake5 vs2022 --to=build-vs")
    parser.add_argument("tool", choices=RUNNABLE, metavar="TOOL")
    parser.add_argument("arguments", nargs=argparse.REMAINDER, metavar="ARGUMENT")
    parser.set_defaults(handler=run_tool, takes_passthrough=True)

    parser = subparsers.add_parser(
        "doctor", parents=[common], help="report the tools, compilers and build directories",
        description="Reports what ./x setup installed and whether it is current, which compilers "
                    "forge/core/config.hpp accepts, and the build directories ./x made. Exits 3 "
                    "when something ./x setup provides is missing.")
    parser.set_defaults(handler=run_doctor)


def run_check(ctx: Context, args: argparse.Namespace) -> int:
    defaults = {"paths": [], "passthrough": [], "targets": [], "only": None, "skip": None,
                "fix": False, "filter": None, "no_build": True}
    stage_args = argparse.Namespace(**{**defaults, **{key: value for key, value in vars(args).items()
                                                      if key not in defaults}})

    def attempt(name: str, action) -> str:
        try:
            return "ok" if action() == 0 else "failed"
        except SetupRequired:
            raise
        except XError as error:
            ctx.ui.error(str(error))
            return "failed"

    results = {
        "format": attempt("format", lambda: cmd_format.format_command(ctx, [], True, args.jobs)),
        "lint": attempt("lint", lambda: cmd_lint.run(ctx, stage_args)),
        "build": attempt("build", lambda: cmd_build.run_build(ctx, stage_args)),
    }
    results["test"] = (attempt("test", lambda: cmd_test.run(ctx, stage_args))
                       if results["build"] == "ok" else "skipped")

    ctx.ui.result("")
    for name, outcome in results.items():
        ctx.ui.result(f"  {name:<8} {outcome}")
    return 0 if all(outcome == "ok" for outcome in results.values()) else 1


def tool_path(ctx: Context, name: str) -> Path:
    if name in tools.DOWNLOADED_TOOLS:
        return tools.require_tool(ctx, name)
    if name in tools.WHEEL_TOOLS:
        return tools.wheel_tool(ctx, name)
    if name == "FileCheck":
        return tools.require_filecheck()
    if name == "llvm-symbolizer":
        symbolizer = tools.find_symbolizer()
        if symbolizer is None:
            raise SetupRequired("llvm-symbolizer not found: install LLVM (brew install llvm, or apt "
                                "install llvm-<N>), or set FORGE_SYMBOLIZER_PATH to an llvm-symbolizer")
        return symbolizer
    tools.require_venv(ctx)
    return venv_executable(ctx.venv, name)


def run_tool(ctx: Context, args: argparse.Namespace) -> int:
    argv = [tool_path(ctx, args.tool), *args.arguments, *args.passthrough]
    # A forge program that lit or python starts writes its stack traces with names.
    return ctx.ui.run(argv, env=tools.symbolizer_environment(), check=False).returncode


def compiler_candidates() -> list[str]:
    """The GCC and Clang C++ compilers on PATH, versioned names included, once each."""
    seen, result = set(), []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        for pattern in ("clang++", "clang++-[0-9]*", "g++", "g++-[0-9]*"):
            for path in sorted(glob.glob(os.path.join(directory, exe(pattern)))):
                real = os.path.realpath(path)
                if os.access(path, os.X_OK) and real not in seen:
                    seen.add(real)
                    result.append(path)
    return result


def check_compiler(ctx: Context, cxx: str, unit: Path) -> str:
    """"ok", or the first error the compiler gives for forge/core/config.hpp. The compiler floor is
    the one config.hpp enforces, not a copy of it."""
    macros = {"FORGE_ASSERTIONS_ENABLED": 0, "FORGE_EXCEPTIONS_ENABLED": 0, "FORGE_SHARED": 0,
              "FORGE_BUILDING_SHARED": 0, "FORGE_DEBUG": 1, "FORGE_RELEASE": 0, "FORGE_RELDEB": 0,
              "FORGE_SANITIZE": 0}
    argv = [cxx, "-std=c++20", "-fsyntax-only", "-fno-exceptions", "-I", str(ctx.root / "forge" / "include"),
            *(f"-D{name}={value}" for name, value in macros.items()), str(unit)]
    completed = ctx.ui.run(argv, capture=True, merge_stderr=True, mutates=False, check=False)
    if completed.returncode == 0:
        return "ok"
    errors = [line for line in completed.stdout.splitlines() if "error" in line]
    message = errors[0] if errors else completed.stdout.strip()
    match = re.search(r'#\s*error\s+"?([^"]*)', message)
    return "rejected: " + (match.group(1) if match else message.split("error:", 1)[-1].strip())


def run_doctor(ctx: Context, args: argparse.Namespace) -> int:
    rows: list[tuple[str, str, str]] = []
    missing = False

    def add(name: str, status: str, detail: str, *, required: bool = True) -> None:
        nonlocal missing
        rows.append((name, status, detail))
        missing = missing or (required and status not in ("ok", "override", "found"))

    rows.append(("host", host_key(), f"Python {sys.version.split()[0]} ({sys.executable})"))
    for name in tools.DOWNLOADED_TOOLS:
        status, path = tools.tool_status(ctx, name)
        version = ctx.manifest[name]["version"]
        add(name, status, f"{version} {ctx.rel(path)}" if path else f"{version}: run ./x setup")
    venv = tools.venv_status(ctx)
    packages = ", ".join(f"{name} {spec['version']}" for name, spec in ctx.manifest["python"].items()
                         if name in ("lit", "clang-format", "clang-tidy"))
    maker = tools.venv_maker(ctx)
    if venv == "ok":
        detail = f"{ctx.rel(ctx.venv)} ({packages}) on {maker}"
    elif venv == "foreign":
        detail = f"made by {maker}, {FOREIGN_VENV_MAKERS}: run ./x setup to replace it"
    else:
        detail = f"made by {maker}: run ./x setup" if maker else "run ./x setup"
    add("venv", venv, detail)
    googletest = tools.googletest_status(ctx)
    add("googletest", "ok" if googletest == "foreign" else googletest,
        f"{ctx.manifest['googletest']['version']} {ctx.rel(tools.googletest_dir(ctx))}"
        + (" (not installed by ./x setup)" if googletest == "foreign" else ""))
    filecheck = tools.find_filecheck()
    add("FileCheck", "found" if filecheck else "missing",
        str(filecheck) if filecheck else "install LLVM, or set FORGE_FILECHECK")
    # Optional: without it, stack traces show addresses only and the tests that need names skip.
    symbolizer = tools.find_symbolizer()
    add("llvm-symbolizer", "found" if symbolizer else "not found",
        str(symbolizer) if symbolizer else "stack traces will have no names: install LLVM, or set "
        "FORGE_SYMBOLIZER_PATH", required=False)

    width = max(len(name) for name, _, _ in rows)
    for name, status, detail in rows:
        ctx.ui.result(f"{name:<{width}}  {status:<11} {detail}")

    builds = [directory for directory in sorted(ctx.root.glob("build*")) if (directory / MARKER).is_file()]
    ctx.ui.result("")
    ctx.ui.result("build directories:" if builds else "build directories: none yet (./x build makes one)")
    for directory in builds:
        marker = read_json(directory / MARKER) or {}
        options = " ".join(marker.get("options", [])) or "defaults"
        ctx.ui.result(f"  {ctx.rel(directory):<{width + 12}} {options}")

    ctx.ui.result("")
    ctx.ui.result("compilers on PATH, checked against forge/core/config.hpp:")
    unit = ctx.cache / "doctor" / "config.cpp"
    if not ctx.ui.dry_run:
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text('#include "forge/core/config.hpp"\n')
    candidates = [] if WINDOWS else compiler_candidates()
    for cxx in candidates:
        version = ctx.ui.run([cxx, "--version"], capture=True, mutates=False, check=False).stdout
        first = version.splitlines()[0] if version else "?"
        verdict = check_compiler(ctx, cxx, unit) if unit.exists() else "not checked"
        ctx.ui.result(f"  {cxx}: {first}\n    {verdict}")
    if WINDOWS:
        ctx.ui.result("  MSVC: ./x build --cc msvc finds it through vswhere")
    elif not candidates:
        ctx.ui.result("  none found")
    return 3 if missing else 0
