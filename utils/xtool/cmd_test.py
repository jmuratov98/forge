# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x test: builds, then runs lit over forge's lit suite, its unit tests and x's own tests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import buildopts, tools
from .context import Context
from .ui import NORMAL, QUIET, VERBOSE, UsageError


def register(subparsers, common, describe_data) -> None:
    parser = subparsers.add_parser(
        "test", parents=[common], help="build, then run the tests",
        description="Builds, then runs lit on the lit suite (forge/test), the unit tests and x's own "
                    "tests (utils/xtool/test), once per configuration. A PATH may be a source "
                    "file or directory: forge/test/host, forge/unittests/core. Arguments after -- "
                    "go to lit.")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    buildopts.add_build_arguments(parser, describe_data)
    parser.add_argument("--filter", metavar="REGEX",
                        help="run only the lit tests whose names match REGEX; for GoogleTest cases, "
                             "set GTEST_FILTER")
    parser.add_argument("--no-build", action="store_true", help="test what is built already")
    parser.set_defaults(handler=run, takes_passthrough=True)


def lit_verbosity(verbosity: int) -> list[str]:
    if verbosity <= QUIET:
        return ["-q"]
    if verbosity == NORMAL:
        return ["-s"]
    if verbosity == VERBOSE:
        return ["-sv"]
    return ["-a"]


def config_key(path: Path) -> str:
    """A config map key, normalized the way lit's discovery normalizes the paths it looks up."""
    return os.path.normcase(os.path.realpath(path))


class Selection:
    """Which tests the PATH arguments ask for, by suite."""

    def __init__(self, ctx: Context, paths: list[str]) -> None:
        self.lit: list[Path] = []
        self.xtool: list[Path] = []
        # forge_<component>_unittests binaries, "" for every one; None when no unit test was named.
        self.unittests: list[str] | None = None
        unittests_root = ctx.root / "forge" / "unittests"
        xtool_root = ctx.code_root / "utils" / "xtool" / "test"
        for raw in paths:
            path = Path(raw).resolve()
            if not path.exists():
                raise UsageError(f"{raw}: no such file or directory")
            if path == unittests_root or unittests_root in path.parents:
                parts = path.relative_to(unittests_root).parts
                self.unittests = (self.unittests or []) + [f"forge_{parts[0]}_unittests" if parts else ""]
            elif path == xtool_root or xtool_root in path.parents:
                self.xtool.append(path)
            else:
                self.lit.append(path)

    @property
    def only_xtool(self) -> bool:
        return bool(self.xtool) and not self.lit and self.unittests is None

    def unit_filter(self) -> str | None:
        """lit runs each GoogleTest binary in shards named <binary>/<shard>/<count>, so a filter on
        lit's test names can pick binaries but not test cases; GTEST_FILTER picks those."""
        names = [name for name in self.unittests or [] if name]
        if "" in (self.unittests or []) or not names:
            return None
        return "/(" + "|".join(names) + ")/"


def run(ctx: Context, args: argparse.Namespace) -> int:
    selection = Selection(ctx, args.paths)
    build = buildopts.resolve(ctx, args)
    # x's own tests need no forge build.
    if not selection.only_xtool:
        buildopts.configure(ctx, build)
        if not args.no_build:
            ctx.ui.step(f"building {ctx.rel(build.dir)} ({', '.join(build.configs)})")
            if buildopts.run_ninja(ctx, build, build.configs, args.jobs):
                return 1

    python = tools.require_venv(ctx)
    env = {
        "FORGE_FILECHECK": str(tools.require_filecheck()),
        # x's own tests run x's build commands with the same tools.
        "FORGE_PREMAKE5": str(tools.require_tool(ctx, "premake5")),
        "FORGE_NINJA": str(tools.require_tool(ctx, "ninja")),
        **tools.symbolizer_environment(),
    }
    xtool_suite = ctx.code_root / "utils" / "xtool" / "test"

    failed = False
    for index, config in enumerate(build.configs):
        site = build.dir / config
        unittests = site / "unittests" / "lit.site.cfg.py"
        config_map = {config_key(ctx.root / "forge" / "test" / "lit.cfg.py"):
                      str(site / "test" / "lit.site.cfg.py")}
        if unittests.is_file():
            config_map[config_key(ctx.root / "forge" / "unittests" / "lit.cfg.py")] = str(unittests)

        # x's own tests do not depend on the configuration, so they run with the first one only.
        runs: list[tuple[list[Path], str | None]] = []
        if not args.paths:
            paths = [site / "test", *([site / "unittests"] if unittests.is_file() else []),
                     *([xtool_suite] if index == 0 else [])]
            runs.append((paths, args.filter))
        else:
            paths = selection.lit + (selection.xtool if index == 0 else [])
            if paths:
                runs.append((paths, args.filter))
            if selection.unittests is not None:
                if unittests.is_file():
                    runs.append(([site / "unittests"], selection.unit_filter()))
                else:
                    ctx.ui.warn(f"{ctx.rel(build.dir)} has no unit tests (generated with --no-tests?)")

        if not runs:
            continue
        ctx.ui.step("testing x" if selection.only_xtool else f"testing {ctx.rel(build.dir)} ({config})")
        for paths, test_filter in runs:
            argv = [python, ctx.code_root / "utils" / "xtool" / "lit_runner.py", json.dumps(config_map),
                    *lit_verbosity(ctx.ui.verbosity)]
            if args.jobs:
                argv += ["-j", str(args.jobs)]
            if test_filter:
                argv += ["--filter", test_filter]
            # With -q, lit's summary is shown only when a test fails.
            completed = ctx.ui.run([*argv, *paths, *args.passthrough], env=env, check=False, replay=True,
                                   base_env=buildopts.build_environment(ctx, build))
            failed = failed or completed.returncode != 0
    return 1 if failed else 0
