# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The ./x command line: global options, the commands, and turning failures into exit codes.

Exit codes: 0 success; 1 a build, test, lint or check failed; 2 a usage error; 3 something ./x
setup provides is missing; 130 interrupted; 141 the output pipe closed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import buildopts, cmd_build, cmd_format, cmd_lint, cmd_misc, cmd_pin, cmd_setup, cmd_test, host
from .context import Context
from .ui import NORMAL, QUIET, Ui, XError

# The commands whose options include the build options, which need premake's forge-describe.
BUILD_COMMANDS = {"configure", "build", "test", "lint", "check", "clean"}

DESCRIPTION = """\
forge's developer entry point. Start with ./x setup, then ./x build or ./x test.
Global options go before or after the command; arguments after -- go to the
wrapped tool (ninja for build, lit for test). forge/docs/x.md has the details."""


def common_parser() -> argparse.ArgumentParser:
    """The global options, given to the top-level parser and to every command's, so that they work
    on either side of the command. SUPPRESS keeps a command's parser from resetting an option that
    was given before the command."""
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_argument_group("global options")
    group.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS,
                       help="print each command x runs; -vv also the tools' own detail")
    group.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS,
                       help="print only errors, warnings and results such as failures")
    group.add_argument("-n", "--dry-run", action="store_true", default=argparse.SUPPRESS,
                       help="print the commands that would change anything, and run none of them")
    group.add_argument("--color", choices=("auto", "always", "never"), default=argparse.SUPPRESS,
                       help="color the output (default: auto, which honors NO_COLOR)")
    # x's own tests point x at a fixture repository.
    group.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser


def build_parser(describe_data: dict | None) -> argparse.ArgumentParser:
    common = common_parser()
    parser = argparse.ArgumentParser(prog="./x", parents=[common], description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(title="commands", metavar="COMMAND")
    cmd_setup.register(subparsers, common)
    cmd_build.register(subparsers, common, describe_data)
    cmd_test.register(subparsers, common, describe_data)
    cmd_format.register(subparsers, common)
    cmd_lint.register(subparsers, common, describe_data)
    cmd_misc.register(subparsers, common, describe_data)
    cmd_pin.register(subparsers, common)
    return parser


def split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """x's own arguments, and those after the first `--`, which go to the wrapped tool."""
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1:]
    return argv, []


def prescan(argv: list[str]) -> tuple[argparse.Namespace, str | None]:
    """The global options and the command name, before the full parser exists: which options the
    build commands take depends on premake, which needs --root and the verbosity first."""
    known, rest = common_parser().parse_known_args(argv)
    command = next((word for word in rest if not word.startswith("-")), None)
    return known, command


def make_ui(options: argparse.Namespace) -> Ui:
    verbosity = QUIET if getattr(options, "quiet", False) else getattr(options, "verbose", NORMAL)
    return Ui(verbosity, getattr(options, "color", "auto"), getattr(options, "dry_run", False))


def main(code_root: str, argv: list[str]) -> int:
    own, passthrough = split_passthrough(argv)
    early, command = prescan(own)
    code = Path(code_root).resolve()
    root = Path(getattr(early, "root", code)).resolve()
    ctx = Context(root, code, make_ui(early))

    try:
        # Every command, --help included: on MSYS2's Python, host_key, the venv and every path x
        # passes on would be wrong.
        host.require_native_python()
        if command in BUILD_COMMANDS:
            try:
                ctx.describe_data = buildopts.describe(ctx)
            except XError as error:
                # Raised by the commands that need the forge options, and only then: --help and
                # clean --all work before setup.
                ctx.describe_error = error

        parser = build_parser(ctx.describe_data)
        args = parser.parse_args(own)
        if getattr(args, "quiet", False) and getattr(args, "verbose", 0):
            parser.error("-q/--quiet and -v/--verbose cannot be combined")
        ctx.ui = make_ui(args)
        args.passthrough = passthrough
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help()
            return 0
        if passthrough and not getattr(args, "takes_passthrough", False):
            parser.error(f"{command} takes no arguments after --")
        return handler(ctx, args)
    except XError as error:
        ctx.ui.error(str(error))
        return error.code
    except KeyboardInterrupt:
        # The child got the same SIGINT; subprocess.run has already waited for it or killed it.
        print(file=sys.stderr)
        return 130
    except BrokenPipeError:
        # The reader went away, as `./x doctor | head` does; exit the way a SIGPIPE would, without
        # Python complaining again when it flushes stdout at exit.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
