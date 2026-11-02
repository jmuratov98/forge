# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x configure, ./x build and ./x clean."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from . import buildopts
from .buildopts import MARKER
from .context import Context
from .ui import XError


def register(subparsers, common, describe_data) -> None:
    parser = subparsers.add_parser(
        "configure", parents=[common], help="generate a build directory and its compile_commands.json",
        description="Runs premake when the options, a premake script or the list of source files "
                    "changed, and writes compile_commands.json for each configuration and at the "
                    "repository root. build, test and lint do this themselves.")
    buildopts.add_build_arguments(parser, describe_data)
    parser.add_argument("--force", action="store_true", help="run premake even when nothing changed")
    parser.set_defaults(handler=run_configure)

    parser = subparsers.add_parser(
        "build", parents=[common], help="build forge (and the unit tests)",
        description="Configures when needed, then runs ninja. A TARGET is a component (core), a "
                    "unit test (core_unittests) or any ninja target; the default is everything in "
                    "the chosen configurations. Arguments after -- go to ninja.")
    parser.add_argument("targets", nargs="*", metavar="TARGET")
    buildopts.add_build_arguments(parser, describe_data)
    parser.set_defaults(handler=run_build, takes_passthrough=True)

    parser = subparsers.add_parser(
        "clean", parents=[common], help="remove build directories that ./x made",
        description="Removes the build directory of the given options, or only the given "
                    "configurations in it with -c. Only directories that ./x made (they hold "
                    f"{MARKER}) are removed.")
    buildopts.add_build_arguments(parser, describe_data)
    parser.add_argument("--all", action="store_true", help="remove every build directory ./x made")
    parser.set_defaults(handler=run_clean)


def run_configure(ctx: Context, args: argparse.Namespace) -> int:
    build = buildopts.resolve(ctx, args)
    buildopts.configure(ctx, build, force=args.force)
    ctx.ui.info(f"{ctx.rel(build.dir)}: configured ({', '.join(build.configs)})")
    return 0


def run_build(ctx: Context, args: argparse.Namespace) -> int:
    build = buildopts.resolve(ctx, args)
    buildopts.configure(ctx, build)
    if args.targets:
        targets = buildopts.map_targets(args.targets, build.configs, buildopts.ninja_targets(ctx, build))
    else:
        targets = build.configs
    ctx.ui.step(f"building {ctx.rel(build.dir)} ({', '.join(build.configs)})")
    return buildopts.run_ninja(ctx, build, targets, args.jobs, args.passthrough)


def remove(ctx: Context, directory: Path) -> None:
    ctx.ui.step(f"removing {ctx.rel(directory)}")
    if ctx.ui.dry_run:
        ctx.ui.echo(["rm", "-rf", directory])
    else:
        shutil.rmtree(directory)


def run_clean(ctx: Context, args: argparse.Namespace) -> int:
    if args.all:
        found = False
        for directory in sorted(ctx.root.glob("build*")):
            if not directory.is_dir():
                continue
            if (directory / MARKER).is_file():
                remove(ctx, directory)
                found = True
            else:
                ctx.ui.warn(f"leaving {ctx.rel(directory)}: ./x did not make it (no {MARKER})")
        if not found:
            ctx.ui.info("no build directories to remove")
        return 0

    build = buildopts.resolve(ctx, args)
    if not build.dir.exists():
        ctx.ui.info(f"{ctx.rel(build.dir)} does not exist")
        return 0
    if not (build.dir / MARKER).is_file():
        raise XError(f"{ctx.rel(build.dir)} was not made by ./x (it has no {MARKER}); remove it yourself")
    if args.config:
        for config in build.configs:
            if (build.dir / config).exists():
                remove(ctx, build.dir / config)
    else:
        remove(ctx, build.dir)
    return 0
