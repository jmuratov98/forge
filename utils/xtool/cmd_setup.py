# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x setup: installs the pinned tools, the venv and googletest.

It works in two phases, because requests, which does the downloading, cannot download itself:
phase A makes .forge/venv with pip, which installs the pinned wheels and requests among them, and
phase B downloads premake5, ninja, actionlint, zizmor and googletest. When requests imports in the Python running x,
phase B runs there; otherwise x runs itself again under the venv's Python for it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import tools
from .context import Context
from .host import exe, host_key
from .ui import QUIET, VERBOSE, VERY_VERBOSE, XError

DOWNLOADED = (*tools.DOWNLOADED_TOOLS, "googletest")
COMPONENTS = ("venv", *DOWNLOADED)


def component_list(text: str) -> list[str]:
    names = [name.strip() for name in text.split(",") if name.strip()]
    unknown = [name for name in names if name not in COMPONENTS]
    if unknown or not names:
        raise argparse.ArgumentTypeError(f"choose from {', '.join(COMPONENTS)}")
    return names


def register(subparsers, common) -> None:
    parser = subparsers.add_parser(
        "setup", parents=[common], help="install the pinned tools, the venv and googletest",
        description="Installs what tools.json pins: premake5, ninja, actionlint and zizmor into "
                    ".forge/tools, lit and the clang tools into .forge/venv, googletest into "
                    "third_party/googletest. "
                    "A second run changes nothing unless tools.json did.")
    parser.add_argument("--only", type=component_list, metavar="LIST",
                        help=f"install only these, comma-separated: {', '.join(COMPONENTS)}")
    parser.add_argument("--force", action="store_true",
                        help="replace a third_party/googletest that ./x setup did not install")
    parser.add_argument("--phase-b", action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(handler=run)


def global_flags(ctx: Context) -> list[str]:
    """The global options of this run, for running x again in another Python."""
    flags = ["--root", str(ctx.root), "--color", ctx.ui.color]
    if ctx.ui.verbosity <= QUIET:
        flags.append("-q")
    elif ctx.ui.verbosity >= VERBOSE:
        flags.append("-" + "v" * ctx.ui.verbosity)
    if ctx.ui.dry_run:
        flags.append("-n")
    return flags


def run(ctx: Context, args: argparse.Namespace) -> int:
    selected = args.only or list(COMPONENTS)
    downloads = [name for name in DOWNLOADED if name in selected]
    if args.phase_b:
        return phase_b(ctx, downloads, args.force)

    if "venv" in selected:
        setup_venv(ctx)
    if downloads:
        if tools.requests_available():
            phase_b(ctx, downloads, args.force)
        else:
            if tools.venv_status(ctx) != "ok":
                setup_venv(ctx)
            argv = [tools.venv_python(ctx), ctx.code_root / "x.py", *global_flags(ctx), "setup",
                    "--phase-b", "--only", ",".join(downloads)]
            if args.force:
                argv.append("--force")
            completed = ctx.ui.run(argv, mutates=False, check=False)
            if completed.returncode:
                return completed.returncode
    report_filecheck(ctx)
    report_symbolizer(ctx)
    return 0


def setup_venv(ctx: Context) -> None:
    status = tools.venv_status(ctx)
    if status == "ok":
        ctx.ui.info(f"venv: up to date ({ctx.rel(ctx.venv)})")
        return
    packages = ctx.manifest["python"]
    unpinned = [name for name, spec in packages.items() if not spec.get("sha256")]
    if unpinned:
        raise XError(f"tools.json has no hashes for {', '.join(unpinned)}: run ./x pin python")

    ctx.ui.step(f"{'creating' if status == 'missing' else 'recreating'} {ctx.rel(ctx.venv)}")
    if ctx.venv.exists() and not ctx.ui.dry_run:
        shutil.rmtree(ctx.venv)
    completed = ctx.ui.run([sys.executable, "-m", "venv", ctx.venv], replay=True, check=False)
    if completed.returncode:
        raise XError(f"python -m venv failed; on Debian and Ubuntu, apt install python3-venv "
                     f"(for {sys.executable}) provides it")

    # Every package is pinned, dependencies included, so pip needs no resolving (--no-deps), only
    # wheels (--only-binary) and only the pinned files (--require-hashes).
    lines = []
    for name, spec in packages.items():
        hashes = " ".join(f"--hash=sha256:{digest}" for digest in spec["sha256"])
        lines.append(f"{name}=={spec['version']} {hashes}")
    requirements = ctx.cache / "requirements.txt"
    if not ctx.ui.dry_run:
        requirements.parent.mkdir(parents=True, exist_ok=True)
        requirements.write_text("\n".join(lines) + "\n")

    pip = [tools.venv_python(ctx), "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", "--require-hashes", "--no-deps", "--only-binary=:all:", "-r", requirements]
    if ctx.ui.verbosity >= VERY_VERBOSE:
        pip.append("-v")
    elif ctx.ui.verbosity < VERBOSE:
        pip.append("-q")
    ctx.ui.run(pip, replay=True)
    if not ctx.ui.dry_run:
        (ctx.venv / tools.STAMP).write_text(json.dumps(tools.expected_venv_stamp(ctx)) + "\n")
    installed = ", ".join(f"{name} {spec['version']}" for name, spec in packages.items())
    ctx.ui.info(f"venv: installed {installed}")


def phase_b(ctx: Context, names: list[str], force: bool) -> int:
    from . import download

    http = download.session()
    for name in names:
        if name == "googletest":
            install_googletest(ctx, http, force)
        else:
            install_tool(ctx, http, name)
    return 0


def check_override(ctx: Context, name: str, path: Path) -> None:
    version = ctx.manifest[name]["version"]
    completed = ctx.ui.run([path, "--version"], cwd=ctx.state if ctx.state.is_dir() else None,
                           capture=True, mutates=False, check=False)
    if version not in completed.stdout:
        ctx.ui.warn(f"{tools.OVERRIDES[name]}={path} does not report version {version}, which "
                    "tools.json pins")
    ctx.ui.info(f"{name}: using {path} ({tools.OVERRIDES[name]})")


def install_tool(ctx: Context, http, name: str) -> None:
    from . import download

    status, path = tools.tool_status(ctx, name)
    spec = ctx.manifest[name]
    if status == "override":
        check_override(ctx, name, path)
        return
    if status == "unsupported":
        raise XError(f"tools.json pins no {name} for {host_key()}: set {tools.OVERRIDES[name]} to a "
                     f"{name} {spec['version']} binary")
    if status == "ok":
        ctx.ui.info(f"{name}: {spec['version']} is up to date")
        return

    asset = tools.host_asset(ctx, name)
    if not asset.get("sha256"):
        raise XError(f"tools.json has no hash for {name} on {host_key()}: run ./x pin {name}")
    url = spec["url"].format(version=spec["version"], asset=asset["asset"])
    ctx.ui.step(f"installing {name} {spec['version']}")
    if ctx.ui.dry_run:
        ctx.ui.info(f"would download {url} into {ctx.rel(tools.tool_dir(ctx, name))}")
        return
    archive, _ = download.fetch(ctx.ui, http, url, asset["sha256"], ctx.cache / "downloads", name)
    binary = exe(spec["binary"])

    def populate(directory: Path) -> None:
        download.extract_binary(archive, binary, directory / "bin" / binary)
        (directory / tools.STAMP).write_text(json.dumps(tools.expected_tool_stamp(ctx, name)) + "\n")

    download.install_directory(tools.tool_dir(ctx, name), populate)
    # From the tool's own directory, which has no premake5.lua for premake to load.
    version = ctx.ui.run([tools.tool_binary(ctx, name), "--version"], cwd=tools.tool_dir(ctx, name),
                         capture=True, mutates=False, check=False)
    ctx.ui.detail(version.stdout.strip())
    ctx.ui.info(f"{name}: installed {spec['version']} in {ctx.rel(tools.tool_binary(ctx, name))}")


def install_googletest(ctx: Context, http, force: bool) -> None:
    from . import download

    spec = ctx.manifest["googletest"]
    destination = tools.googletest_dir(ctx)
    status = tools.googletest_status(ctx)
    if status == "ok":
        ctx.ui.info(f"googletest: {spec['version']} is up to date")
        return
    if status == "foreign" and not force:
        raise XError(f"{ctx.rel(destination)} exists, but ./x setup did not install it (it has no "
                     f"{tools.GOOGLETEST_STAMP}): move it away, or pass --force to replace it")
    if not spec.get("sha256"):
        raise XError("tools.json has no hash for googletest: run ./x pin googletest")

    url = spec["url"].format(version=spec["version"])
    ctx.ui.step(f"installing googletest {spec['version']}")
    if ctx.ui.dry_run:
        ctx.ui.info(f"would download {url} into {ctx.rel(destination)}")
        return
    archive, _ = download.fetch(ctx.ui, http, url, spec["sha256"], ctx.cache / "downloads", "googletest")

    def populate(directory: Path) -> None:
        count = download.extract_tree(archive, spec["strip"].format(version=spec["version"]), directory)
        (directory / tools.GOOGLETEST_STAMP).write_text(
            json.dumps(tools.expected_googletest_stamp(ctx)) + "\n")
        ctx.ui.detail(f"googletest: extracted {count} files")

    destination.parent.mkdir(parents=True, exist_ok=True)
    download.install_directory(destination, populate)
    ctx.ui.info(f"googletest: installed {spec['version']} in {ctx.rel(destination)}")


def report_filecheck(ctx: Context) -> None:
    filecheck = tools.find_filecheck()
    if filecheck is None:
        ctx.ui.warn("FileCheck not found, and ./x test needs it: install LLVM (brew install llvm, "
                    "or apt install llvm-<N>-tools), or set FORGE_FILECHECK to a FileCheck binary")
    else:
        ctx.ui.info(f"FileCheck: {filecheck}")


def report_symbolizer(ctx: Context) -> None:
    symbolizer = tools.find_symbolizer()
    if symbolizer is None:
        ctx.ui.warn("llvm-symbolizer not found, so forge's stack traces will show addresses without "
                    "names: install LLVM (brew install llvm, or apt install llvm-<N>), or set "
                    "FORGE_SYMBOLIZER_PATH to an llvm-symbolizer")
    else:
        ctx.ui.info(f"llvm-symbolizer: {symbolizer}")
