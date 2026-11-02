# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x lint: five stages, cheapest first, all of which run so that one run reports everything.

files       hygiene that needs no compiler: SPDX line, #pragma once, whitespace, line endings
layering    includes follow the component graph in forge/premake5.lua
workflows   the pinned actionlint and zizmor over the GitHub Actions files in .github
headers     each header compiles on its own, included twice
clang-tidy  the pinned clang-tidy over the compile database, with results cached by content
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import buildopts, lints, repo, tools
from .context import Context, read_json, write_if_changed
from .host import WINDOWS
from .ui import XError

STAGES = ("files", "layering", "workflows", "headers", "clang-tidy")

# A diagnostic's location, which clang-tidy gives relative to the compile command's directory.
LOCATION = re.compile(r"^([^\s:][^:]*):(\d+):(\d+): ")

# Lines clang-tidy prints about itself rather than about the code.
TIDY_NOISE = re.compile(r"^(\d+ (warnings?|errors?)( and \d+ errors?)? generated\.|Suppressed \d+ warnings"
                        r"|Use -header-filter=|Error while processing |Found compiler error)")


def stage_list(text: str) -> list[str]:
    names = [name.strip() for name in text.split(",") if name.strip()]
    if not names or any(name not in STAGES for name in names):
        raise argparse.ArgumentTypeError(f"choose from {', '.join(STAGES)}")
    return names


def register(subparsers, common, describe_data) -> None:
    parser = subparsers.add_parser(
        "lint", parents=[common], help="run the lints and clang-tidy",
        description=__doc__.split("\n\n", 1)[1] if __doc__ else None,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", metavar="PATH", help="lint only these files and directories")
    buildopts.add_build_arguments(parser, describe_data)
    parser.add_argument("--only", type=stage_list, metavar="STAGES", help="run only these stages")
    parser.add_argument("--skip", type=stage_list, metavar="STAGES", help="skip these stages")
    parser.add_argument("--fix", action="store_true",
                        help="repair what can be repaired: whitespace, line endings, SPDX lines, "
                             "clang-tidy's fixes")
    parser.set_defaults(handler=run)


def report(ctx: Context, diagnostics: list[lints.Diagnostic]) -> int:
    for diagnostic in diagnostics:
        ctx.ui.result(diagnostic.format(ctx.rel))
    return len(diagnostics)


def run(ctx: Context, args: argparse.Namespace) -> int:
    stages = [stage for stage in STAGES
              if (not args.only or stage in args.only) and stage not in (args.skip or [])]
    files = repo.select(repo.all_files(ctx.root), [Path(path) for path in args.paths])
    build = None
    problems = 0
    for stage in stages:
        ctx.ui.step(f"lint: {stage}")
        if stage == "files":
            problems += lint_files(ctx, files, args.fix)
        elif stage == "layering":
            problems += lint_layering(ctx, files)
        elif stage == "workflows":
            problems += lint_workflows(ctx, files)
        else:
            if build is None:
                build = buildopts.resolve(ctx, args)
                buildopts.configure(ctx, build)
            if stage == "headers":
                problems += lint_headers(ctx, build, files, args.jobs)
            else:
                problems += lint_tidy(ctx, build, files, args.fix, args.jobs)
    if problems:
        ctx.ui.error(f"lint: {problems} problem{'s' if problems != 1 else ''}")
        return 1
    ctx.ui.info("lint: no problems")
    return 0


def lint_files(ctx: Context, files: list[Path], fix: bool) -> int:
    diagnostics = []
    for file in files:
        marker = lints.comment_marker(ctx.root, file)
        if fix and marker is not None:
            data = file.read_bytes()
            try:
                fixed = lints.fix_content(data, marker)
            except UnicodeDecodeError:
                fixed = data
            if fixed != data:
                if not ctx.ui.dry_run:
                    file.write_bytes(fixed)
                ctx.ui.info(f"fixed {ctx.rel(file)}")
        diagnostics += lints.check_file(ctx.root, file)
    return report(ctx, diagnostics)


def lint_layering(ctx: Context, files: list[Path]) -> int:
    data = buildopts.require_describe(ctx)
    components = {component["name"]: component["dependencies"] for component in data["components"]}
    tests = {test["name"]: test["dependencies"] for test in data["tests"]}
    return report(ctx, lints.check_layering(ctx.root, files, components, tests))


def lint_workflows(ctx: Context, files: list[Path]) -> int:
    """actionlint checks workflows; zizmor audits workflows, composite actions and dependabot.yml for
    security problems, offline. Both run from the root, where actionlint finds the local actions a
    workflow uses. actionlint would also run shellcheck and pyflakes if they happen to be on PATH,
    which would make the result depend on the machine, so they are turned off."""
    kinds = {file: lints.workflow_kind(ctx.root, file) for file in files}
    audited = [file.relative_to(ctx.root).as_posix() for file, kind in kinds.items() if kind]
    workflows = [file.relative_to(ctx.root).as_posix() for file, kind in kinds.items() if kind == "workflow"]
    if not audited:
        ctx.ui.detail("lint: no GitHub Actions files to check")
        return 0

    diagnostics = []
    if workflows:
        completed = ctx.ui.run([tools.require_tool(ctx, "actionlint"), "-no-color", "-shellcheck=", "-pyflakes=",
                                "-format", "{{json .}}", *workflows],
                               cwd=ctx.root, capture=True, mutates=False, check=False)
        # 1 means it found problems; 2 and 3 that it could not run.
        if completed.returncode not in (0, 1):
            raise XError(f"actionlint failed with exit code {completed.returncode}")
        diagnostics += lints.actionlint_diagnostics(ctx.root, json.loads(completed.stdout or "[]"))
    problems = report(ctx, diagnostics)

    completed = ctx.ui.run([tools.require_tool(ctx, "zizmor"), "--quiet", "--offline", "--no-exit-codes",
                            "--strict-collection", "--format", "json-v1", *audited],
                           cwd=ctx.root, capture=True, mutates=False, check=False)
    # A file zizmor cannot parse fails the run; actionlint has reported why above.
    if completed.returncode != 0:
        raise XError(f"zizmor failed with exit code {completed.returncode}")
    return problems + report(ctx, lints.zizmor_diagnostics(ctx.root, json.loads(completed.stdout or "[]")))


def site_value(site_config: Path, name: str) -> Any:
    """A value premake wrote into a lit site config, which has one `config.<name> = <literal>` line
    per value."""
    try:
        for line in site_config.read_text().splitlines():
            if line.startswith(f"config.{name} = "):
                return ast.literal_eval(line.split(" = ", 1)[1])
    except OSError:
        pass
    raise XError(f"{site_config} has no config.{name}: run ./x configure --force")


def entry_source(entry: dict[str, Any]) -> Path:
    return (Path(entry["directory"]) / entry["file"]).resolve()


def compile_arguments(entry: dict[str, Any]) -> list[str]:
    """A compile command without its source file, its output and its dependency file, so that it
    can compile something else or only list the includes."""
    words = entry.get("arguments") or shlex.split(entry["command"], posix=not WINDOWS)
    result, skip = [], False
    for word in words:
        if skip:
            skip = False
        elif word in ("-o", "-MF"):
            skip = True
        elif word in ("-c", "/c", "-MD", "-MMD", "/showIncludes") or word.startswith("/Fo") \
                or word == entry["file"]:
            continue
        else:
            result.append(word)
    return result


def digest_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path).encode() + b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def lint_headers(ctx: Context, build: buildopts.Build, files: list[Path], jobs: int | None) -> int:
    """Each header compiles on its own, and twice in one file, which also proves #pragma once.
    Public headers are compiled the way code outside libforge compiles them, with the site config's
    host compiler command; private headers with a compile command from their own component."""
    config = build.configs[0]
    site = build.dir / config / "test" / "lit.site.cfg.py"
    if ctx.ui.dry_run and not site.exists():
        ctx.ui.info("headers: skipped; the build directory is not configured")
        return 0
    host_cxx = site_value(site, "forge_host_cxx")
    syntax_only = "/Zs" if site_value(site, "forge_host_cxx_family") == "msvc" else "-fsyntax-only"

    private_commands: dict[str, dict[str, Any]] = {}
    for entry in buildopts.compile_database(ctx, build, config):
        match = re.match(r"forge/source/forge/([^/]+)/", entry_source(entry).relative_to(ctx.root).as_posix())
        if match:
            private_commands.setdefault(match.group(1), entry)

    every_header = [file for file in repo.all_files(ctx.root) if file.suffix == ".hpp"
                    and repo.under(ctx.root, file, "forge/include", "forge/source")]
    known = set(every_header)
    headers = [file for file in files if file in known]
    # A header's includes are other forge headers, so any change to one re-checks them all.
    headers_digest = digest_files(every_header)
    translation_units = build.dir / config / "headers"

    def check(header: Path) -> tuple[Path, Path, str] | None:
        relative = header.relative_to(ctx.root).as_posix()
        include = relative.split("/", 2)[2]
        unit = translation_units / f"{include}.cpp"
        entry = None if relative.startswith("forge/include/") else private_commands.get(include.split("/")[1])
        if entry is None:
            argv, cwd = [*host_cxx, syntax_only, str(unit)], None
        else:
            argv, cwd = [*compile_arguments(entry), syntax_only, str(unit)], Path(entry["directory"])
        key = hashlib.sha256(json.dumps([argv, headers_digest, relative]).encode()).hexdigest()
        cached = ctx.cache / "headers" / key
        if cached.exists():
            return None
        write_if_changed(unit, f'#include "{include}"\n#include "{include}"\n')
        completed = ctx.ui.run(argv, cwd=cwd, capture=True, merge_stderr=True, mutates=False,
                               check=False, base_env=buildopts.build_environment(ctx, build))
        if completed.returncode == 0:
            write_if_changed(cached, "")
            return None
        return header, unit, completed.stdout

    with ThreadPoolExecutor(jobs or os.cpu_count() or 1) as pool:
        failures = [failure for failure in pool.map(check, headers) if failure]
    for header, unit, output in failures:
        ctx.ui.result(output.rstrip("\n"))
        ctx.ui.result(lints.Diagnostic(header, 1, 1, f"does not compile on its own ({ctx.rel(unit)} "
                                       "includes it twice)", "self-contained").format(ctx.rel))
    ctx.ui.info(f"headers: {len(headers)} checked, {len(headers) - len(failures)} self-contained")
    return len(failures)


def dependencies(ctx: Context, build: buildopts.Build, entry: dict[str, Any]) -> list[Path] | None:
    """The files a translation unit reads, from the compiler's own -MM, or None when they cannot be
    listed (MSVC), which turns the cache off for it."""
    arguments = compile_arguments(entry)
    if not arguments or Path(arguments[0]).stem.lower() in ("cl", "clang-cl"):
        return None
    directory = Path(entry["directory"])
    completed = ctx.ui.run([*arguments, "-MM", str(entry_source(entry))], cwd=directory, capture=True,
                           mutates=False, check=False, base_env=buildopts.build_environment(ctx, build))
    if completed.returncode != 0:
        return None
    rule = completed.stdout.replace("\\\n", " ")
    return [(directory / word).resolve() for word in rule.split(":", 1)[-1].split()]


def lint_tidy(ctx: Context, build: buildopts.Build, files: list[Path], fix: bool, jobs: int | None) -> int:
    config = build.configs[0]
    clang_tidy = tools.wheel_tool(ctx, "clang-tidy")
    selected = set(files)
    entries = [entry for entry in buildopts.compile_database(ctx, build, config)
               if entry_source(entry) in selected and repo.under(ctx.root, entry_source(entry), "forge")]

    version = ctx.ui.run([clang_tidy, "--version"], capture=True, mutates=False).stdout
    # The wheel's clang-tidy has no default SDK, and it meets GCC-only warning flags in a GCC build.
    extra = ["--extra-arg=-Wno-unknown-warning-option"]
    if sys.platform == "darwin":
        sdk = ctx.ui.run(["xcrun", "--show-sdk-path"], capture=True, mutates=False).stdout.strip()
        extra.append(f"--extra-arg=-isysroot{sdk}")
    settings = digest_files([file for file in repo.all_files(ctx.root) if file.name == ".clang-tidy"])
    database = build.dir / config
    fixes = Path(tempfile.mkdtemp(prefix="tidy-fixes-", dir=ctx.cache)) if fix and not ctx.ui.dry_run else None

    def check(item: tuple[int, dict[str, Any]]) -> tuple[Path, int, str]:
        index, entry = item
        source = entry_source(entry)
        cached = None
        if not fix:
            inputs = dependencies(ctx, build, entry)
            if inputs is not None:
                key = hashlib.sha256(json.dumps([version, settings, compile_arguments(entry), extra,
                                                 digest_files(inputs)]).encode()).hexdigest()
                cached = ctx.cache / "tidy" / f"{key}.json"
                result = read_json(cached)
                if isinstance(result, dict):
                    return source, result["returncode"], result["output"]

        argv = [clang_tidy, "-p", str(database), "--quiet", *extra, str(source)]
        if fixes is not None:
            argv.append(f"--export-fixes={fixes / f'{index}.yaml'}")
        completed = ctx.ui.run(argv, capture=True, merge_stderr=True, mutates=False, check=False)
        directory = Path(entry["directory"])

        def relocate(line: str) -> str:
            # Relative to the current directory, like x's other diagnostics, so that they are
            # clickable from where x ran.
            match = LOCATION.match(line)
            if not match or Path(match.group(1)).is_absolute():
                return line
            return ctx.rel((directory / match.group(1)).resolve()) + line[len(match.group(1)):]

        output = "\n".join(relocate(line) for line in completed.stdout.splitlines()
                           if not TIDY_NOISE.match(line))
        if cached is not None:
            write_if_changed(cached, json.dumps({"returncode": completed.returncode, "output": output}))
        return source, completed.returncode, output

    with ThreadPoolExecutor(jobs or os.cpu_count() or 1) as pool:
        results = list(pool.map(check, enumerate(entries)))
    problems = 0
    for _, returncode, output in results:
        if output.strip():
            ctx.ui.result(output.rstrip("\n"))
        problems += max(len(re.findall(r": error: ", output)), 1 if returncode else 0)

    if fixes is not None:
        if any(fixes.iterdir()):
            ctx.ui.step("clang-tidy: applying fixes")
            ctx.ui.run([tools.wheel_tool(ctx, "clang-apply-replacements"), "--format", "--style=file",
                        fixes])
        for file in fixes.iterdir():
            file.unlink()
        fixes.rmdir()
    ctx.ui.info(f"clang-tidy: {len(entries)} files checked")
    return problems
