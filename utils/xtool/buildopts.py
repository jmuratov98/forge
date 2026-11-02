# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Build options, build directories, and running premake.

The forge options are not listed here: premake's forge-describe action reports the ones in
premake/options.lua, with their values, defaults and allowed values, and x mirrors them as
command-line options. Each set of generation-time options gets its own build directory, since
premake fixes them when it generates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import tools
from .context import Context, read_json, write_if_changed
from .host import WINDOWS, msvc_environment
from .ui import QUIET, VERBOSE, VERY_VERBOSE, UsageError, XError

MARKER = ".forge-build.json"
DEFAULT_CONFIG = "Debug"

# x's names for the compiler families, and premake's.
PREMAKE_TOOLSETS = {"clang": "clang", "gcc": "gcc", "msvc": "msc"}


def premake_inputs(root: Path) -> list[Path]:
    files = [root / "premake5.lua", root / "forge" / "premake5.lua", root / "third_party" / "premake5.lua"]
    files += sorted((root / "premake").glob("*.lua"))
    return [file for file in files if file.is_file()]


def _hash_files(digest, root: Path, files: list[Path]) -> None:
    for file in files:
        digest.update(file.relative_to(root).as_posix().encode() + b"\0")
        digest.update(file.read_bytes() + b"\0")


def describe(ctx: Context) -> dict[str, Any]:
    """forge-describe's JSON, cached until a premake script or premake itself changes."""
    premake = tools.require_tool(ctx, "premake5")
    digest = hashlib.sha256(tools.tool_identity(ctx, "premake5").encode())
    _hash_files(digest, ctx.root, premake_inputs(ctx.root))
    key = digest.hexdigest()

    cache = ctx.cache / "describe.json"
    cached = read_json(cache)
    if isinstance(cached, dict) and cached.get("key") == key:
        return cached["data"]

    completed = ctx.ui.run([premake, f"--file={ctx.root / 'premake5.lua'}", "--no-tests", "forge-describe"],
                           cwd=ctx.root, capture=True, mutates=False, check=False)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    if completed.returncode != 0 or not lines:
        raise XError(f"premake5 forge-describe failed (exit code {completed.returncode}):\n"
                     f"{completed.stdout}")
    data = json.loads(lines[0])
    write_if_changed(cache, json.dumps({"key": key, "data": data}))
    return data


def forge_options(data: dict[str, Any]) -> list[dict[str, Any]]:
    """The premake options x exposes. --to is x's --build-dir."""
    return [option for option in data["options"] if option["trigger"] != "to"]


def dest(option: dict[str, Any]) -> str:
    return "forge_" + option["trigger"].replace("-", "_")


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def add_jobs_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-j", "--jobs", type=positive_int, metavar="N",
                        help="run N jobs at once (default: the tool's own choice, usually one per CPU)")


def add_build_arguments(parser: argparse.ArgumentParser, data: dict[str, Any] | None) -> None:
    group = parser.add_argument_group("build options")
    group.add_argument("-c", "--config", metavar="CONFIG[,...]",
                       help="the configurations to use: Debug (the default), Release, RelDeb, "
                            "Sanitize, or all")
    group.add_argument("--cc", choices=sorted(PREMAKE_TOOLSETS),
                       help="the compiler family (default: premake's choice for the host)")
    group.add_argument("--cxx", metavar="PATH",
                       help="an exact C++ compiler, such as g++-16 (default: $CXX); x finds the "
                            "matching C compiler and archiver next to it")
    group.add_argument("--build-dir", metavar="DIR",
                       help="the build directory (default: named after the options, see "
                            "forge/docs/x.md)")
    add_jobs_argument(group)

    if data is None:
        parser.epilog = ("The forge options (--shared, --std, ...) are listed once ./x setup has "
                         "installed premake.")
        return
    forge = parser.add_argument_group("forge options (from premake/options.lua)")
    for option in forge_options(data):
        flag = "--" + option["trigger"]
        if "value" in option:
            forge.add_argument(flag, dest=dest(option), metavar=option["value"],
                               choices=option["allowed"] or None, help=option["description"])
        else:
            forge.add_argument(flag, dest=dest(option), action="store_true", help=option["description"])


def forge_arguments(options: list[dict[str, Any]], values: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The premake arguments for the options set to non-default values, and the parts of the build
    directory name they give: a flag gives its name, a valued option `<trigger>-<value>`."""
    arguments, parts = [], []
    for option in options:
        trigger = option["trigger"]
        value = values.get(dest(option))
        if "value" in option:
            if value is None or value == option.get("default"):
                continue
            arguments.append(f"--{trigger}={value}")
            parts.append(f"{trigger}-{value.replace(',', '+')}")
        elif value:
            arguments.append(f"--{trigger}")
            parts.append(trigger)
    return arguments, parts


def build_dir_name(parts: list[str]) -> str:
    return "-".join(["build", *parts])


def parse_configs(text: str | None, known: list[str]) -> list[str]:
    if not text:
        return [DEFAULT_CONFIG]
    if text.lower() == "all":
        return list(known)
    by_name = {name.lower(): name for name in known}
    result = []
    for part in text.split(","):
        name = by_name.get(part.strip().lower())
        if name is None:
            raise UsageError(f"unknown configuration '{part}': choose from {', '.join(known)} or all")
        if name not in result:
            result.append(name)
    return result


@dataclass
class Compiler:
    family: str  # clang or gcc
    name: str  # the build directory part: clang23, appleclang17, gcc16
    cxx: str
    cc: str | None
    ar: str


def compiler_siblings(cxx: str, family: str, exists=os.path.exists) -> tuple[str | None, str]:
    """The C compiler and archiver that go with a C++ compiler: g++-16 has gcc-16 and gcc-ar-16,
    clang++-23 has clang-23 and llvm-ar-23. gcc-ar and llvm-ar understand LTO objects, which plain
    ar does not; plain ar is the fallback."""
    directory, name = os.path.split(cxx)
    if family == "clang":
        match = re.fullmatch(r"(.*)clang\+\+(.*)", name)
        c_name, archivers = "clang", ["llvm-ar"]
    else:
        match = re.fullmatch(r"(.*)g\+\+(.*)", name)
        c_name, archivers = "gcc", ["gcc-ar"]
    if not match:
        return None, "ar"
    prefix, suffix = match.groups()
    cc = os.path.join(directory, prefix + c_name + suffix)
    for archiver in archivers:
        for candidate in (prefix + archiver + suffix, archiver + suffix):
            path = os.path.join(directory, candidate)
            if exists(path):
                return (cc if exists(cc) else None), path
    return (cc if exists(cc) else None), "ar"


def parse_compiler_version(version_output: str, dump_version: str) -> tuple[str, str]:
    """(family, build directory part) from `--version` and `-dumpversion` output."""
    first = version_output.splitlines()[0] if version_output else ""
    major = dump_version.strip().split(".")[0]
    if "clang" in first.lower():
        return "clang", ("appleclang" if first.startswith("Apple") else "clang") + major
    if "Free Software Foundation" in version_output or "(GCC)" in first or "g++" in first:
        return "gcc", "gcc" + major
    raise XError(f"cannot tell which compiler this is from its --version: {first!r}")


def detect_compiler(ctx: Context, cxx: str) -> Compiler:
    path = shutil.which(cxx)
    if path is None:
        raise UsageError(f"--cxx {cxx}: not found")
    version = ctx.ui.run([path, "--version"], capture=True, mutates=False, check=False).stdout
    if "Microsoft" in version:
        raise UsageError("--cxx takes a GCC or Clang compiler; use --cc msvc for MSVC")
    dumped = ctx.ui.run([path, "-dumpversion"], capture=True, mutates=False).stdout
    family, name = parse_compiler_version(version, dumped)
    cc, ar = compiler_siblings(path, family)
    return Compiler(family, name, path, cc, ar)


@dataclass
class Build:
    dir: Path
    configs: list[str]
    family: str | None  # x's family name, when one was chosen
    compiler: Compiler | None
    forge_args: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)

    @property
    def no_tests(self) -> bool:
        return "--no-tests" in self.forge_args


def require_describe(ctx: Context) -> dict[str, Any]:
    if ctx.describe_data is None:
        raise ctx.describe_error or XError("premake was not queried")
    return ctx.describe_data


def resolve(ctx: Context, args: argparse.Namespace) -> Build:
    data = require_describe(ctx)
    configs = parse_configs(args.config, data["configurations"])

    cxx = args.cxx or os.environ.get("CXX")
    compiler = detect_compiler(ctx, cxx) if cxx else None
    if compiler and args.cc and args.cc != compiler.family:
        raise UsageError(f"--cc {args.cc} disagrees with {compiler.cxx}, which is {compiler.family}")
    family = compiler.family if compiler else args.cc

    forge_args, parts = forge_arguments(forge_options(data), vars(args))
    name_parts = ([compiler.name] if compiler else [family] if family else []) + parts
    directory = Path(args.build_dir).resolve() if args.build_dir else ctx.root / build_dir_name(name_parts)
    return Build(directory, configs, family, compiler, forge_args, name_parts)


def premake_argv(ctx: Context, build: Build) -> list[str]:
    argv = [str(tools.require_tool(ctx, "premake5")), f"--file={ctx.root / 'premake5.lua'}",
            f"--to={build.dir}"]
    if build.family:
        argv.append(f"--cc={PREMAKE_TOOLSETS[build.family]}")
    if build.compiler:
        argv.append(f"--cxx-path={build.compiler.cxx}")
        if build.compiler.cc:
            argv.append(f"--cc-path={build.compiler.cc}")
        argv.append(f"--ar-path={build.compiler.ar}")
    return argv + build.forge_args + ["ninja"]


def configure_stamp(ctx: Context, argv: list[str]) -> str:
    """Changes whenever premake's output could: its command line or binary, a premake script, the
    googletest it builds, or the set of source files (premake's globs are expanded when it runs, so a
    new .cpp needs a new generation, the problem CMake's GLOB has)."""
    digest = hashlib.sha256(json.dumps(argv).encode())
    digest.update(tools.tool_identity(ctx, "premake5").encode())
    _hash_files(digest, ctx.root, premake_inputs(ctx.root))
    for top in ("include", "source", "unittests"):
        base = ctx.root / "forge" / top
        for directory, _, names in sorted(os.walk(base)):
            for name in sorted(names):
                digest.update(Path(directory, name).relative_to(ctx.root).as_posix().encode() + b"\0")
    digest.update(json.dumps(read_json(tools.googletest_dir(ctx) / tools.GOOGLETEST_STAMP)).encode())
    return digest.hexdigest()


def build_environment(ctx: Context, build: Build) -> dict[str, str] | None:
    """The environment ninja and the compilers need: the MSVC one on Windows, else x's own."""
    if WINDOWS and build.family in (None, "msvc"):
        return msvc_environment(ctx.ui, build.dir / ".forge-msvc-env.json")
    return None


def configure(ctx: Context, build: Build, *, force: bool = False) -> None:
    """Runs premake when the configure stamp changed, then refreshes the compile databases."""
    argv = premake_argv(ctx, build)
    stamp = configure_stamp(ctx, argv)
    marker = read_json(build.dir / MARKER)
    current = isinstance(marker, dict) and marker.get("stamp") == stamp
    if force or not current or not (build.dir / "build.ninja").is_file():
        if not build.no_tests and tools.googletest_status(ctx) not in ("ok", "foreign"):
            raise tools.SetupRequired("googletest is not set up: run ./x setup, or pass --no-tests")
        ctx.ui.step(f"configuring {ctx.rel(build.dir)}")
        ctx.ui.run(argv, cwd=ctx.root, replay=True)
        if not ctx.ui.dry_run:
            write_if_changed(build.dir / MARKER, json.dumps(
                {"options": build.parts, "argv": argv, "stamp": stamp}, indent=2) + "\n")
    else:
        ctx.ui.detail(f"{ctx.rel(build.dir)} is up to date")
    if not ctx.ui.dry_run:
        write_compile_databases(ctx, build)


def compile_rules(build: Build) -> list[str]:
    rules = set()
    for ninja_file in build.dir.glob("*.ninja"):
        rules.update(re.findall(r"^rule ((?:cc|cxx)_\S+)$", ninja_file.read_text(), re.MULTILINE))
    return sorted(rules)


def compile_database(ctx: Context, build: Build, config: str) -> list[dict[str, Any]]:
    """The compile commands of one configuration. ninja's database covers every configuration, since
    premake puts them all in one ninja file; outputs under <config>/obj/ pick one out."""
    rules = compile_rules(build)
    if not rules:
        return []
    ninja = tools.require_tool(ctx, "ninja")
    output = ctx.ui.run([ninja, "-C", build.dir, "-t", "compdb", *rules], capture=True, mutates=False,
                        base_env=build_environment(ctx, build)).stdout
    prefix = f"{config}/obj/"
    return [entry for entry in json.loads(output)
            if entry.get("output", "").replace("\\", "/").startswith(prefix)]


def write_compile_databases(ctx: Context, build: Build) -> None:
    """<build>/<config>/compile_commands.json for each configuration, and a copy of the first one at
    the repository root, where clangd looks."""
    for index, config in enumerate(build.configs):
        text = json.dumps(compile_database(ctx, build, config), indent=2) + "\n"
        write_if_changed(build.dir / config / "compile_commands.json", text)
        if index == 0 and write_if_changed(ctx.root / "compile_commands.json", text):
            ctx.ui.detail(f"compile_commands.json now describes {ctx.rel(build.dir)} ({config})")


def ninja_verbosity(verbosity: int) -> list[str]:
    if verbosity <= QUIET:
        return ["--quiet"]
    if verbosity >= VERY_VERBOSE:
        return ["-v", "-d", "explain"]
    if verbosity >= VERBOSE:
        return ["-v"]
    return []


def ninja_targets(ctx: Context, build: Build) -> set[str]:
    if not (build.dir / "build.ninja").is_file():
        return set()
    ninja = tools.require_tool(ctx, "ninja")
    output = ctx.ui.run([ninja, "-C", build.dir, "-t", "targets", "all"], capture=True, mutates=False,
                        base_env=build_environment(ctx, build)).stdout
    return {line.rsplit(": ", 1)[0] for line in output.splitlines() if ": " in line}


def map_targets(names: list[str], configs: list[str], available: set[str]) -> list[str]:
    """Short names for premake's targets: `core` is forge_core_<config>, `core_unittests`
    forge_core_unittests_<config>. Any other name is ninja's own."""
    result = []
    for name in names:
        found = False
        for config in configs:
            for candidate in (f"forge_{name}_{config}", f"{name}_{config}"):
                if candidate in available:
                    result.append(candidate)
                    found = True
                    break
        if not found:
            result.append(name)
    return result


def run_ninja(ctx: Context, build: Build, targets: list[str], jobs: int | None,
              extra: list[str] | None = None) -> int:
    ninja = tools.require_tool(ctx, "ninja")
    argv = [ninja, "-C", build.dir, *ninja_verbosity(ctx.ui.verbosity)]
    if jobs:
        argv += ["-j", str(jobs)]
    completed = ctx.ui.run([*argv, *targets, *(extra or [])], check=False,
                           base_env=build_environment(ctx, build))
    return 1 if completed.returncode else 0
