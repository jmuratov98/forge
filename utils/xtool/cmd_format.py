# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x format: clang-format, the version tools.json pins, over forge's C and C++ files."""

from __future__ import annotations

import argparse
import difflib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import buildopts, repo, tools
from .context import Context

SUFFIXES = (".hpp", ".cpp", ".h", ".c")


def register(subparsers, common) -> None:
    parser = subparsers.add_parser(
        "format", aliases=["fmt"], parents=[common], help="format the C++ code with clang-format",
        description="Formats the C and C++ files under forge/ with the pinned clang-format. "
                    "forge/test/ is left alone: its inputs are not code. PATHs limit the run to "
                    "those files and directories.")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    parser.add_argument("--check", action="store_true",
                        help="change nothing; print a diff of what would change and exit 1 if any would")
    buildopts.add_jobs_argument(parser)
    parser.set_defaults(handler=run)


def format_files(ctx: Context, paths: list[str]) -> list[Path]:
    files = [file for file in repo.all_files(ctx.root)
             if file.suffix in SUFFIXES and repo.under(ctx.root, file, "forge")
             and not repo.under(ctx.root, file, "forge/test")]
    return repo.select(files, [Path(path) for path in paths])


def run(ctx: Context, args: argparse.Namespace) -> int:
    return format_command(ctx, args.paths, args.check, args.jobs)


def format_command(ctx: Context, paths: list[str], check: bool, jobs: int | None) -> int:
    clang_format = tools.wheel_tool(ctx, "clang-format")
    files = format_files(ctx, paths)
    workers = jobs or os.cpu_count() or 1

    if check:
        def diff(file: Path) -> str:
            original = file.read_text(encoding="utf-8")
            formatted = ctx.ui.run([clang_format, "--style=file", file], capture=True, mutates=False).stdout
            name = file.relative_to(ctx.root).as_posix()
            return "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                                formatted.splitlines(keepends=True),
                                                f"a/{name}", f"b/{name}"))

        with ThreadPoolExecutor(workers) as pool:
            diffs = [text for text in pool.map(diff, files) if text]
        for text in diffs:
            ctx.ui.result(text.rstrip("\n"))
        if diffs:
            ctx.ui.error(f"{len(diffs)} of {len(files)} files need formatting: run ./x format")
            return 1
        ctx.ui.info(f"format: {len(files)} files are formatted")
        return 0

    before = {file: file.read_bytes() for file in files}
    batches = [files[index::workers] for index in range(workers)]
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda batch: ctx.ui.run([clang_format, "--style=file", "-i", *batch]),
                      [batch for batch in batches if batch]))
    if ctx.ui.dry_run:
        return 0
    changed = [file for file in files if file.read_bytes() != before[file]]
    for file in changed:
        ctx.ui.info(f"formatted {ctx.rel(file)}")
    ctx.ui.info(f"format: {len(changed)} of {len(files)} files changed")
    return 0
