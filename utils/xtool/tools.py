# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The tools x runs, where they are, and whether they match tools.json.

`./x setup` installs each one with a stamp that records what it installed. Every other command
compares the stamps with tools.json before it runs anything, and stops with "run ./x setup"
instead of using a missing or outdated tool. No command but setup and pin goes to the network.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .context import Context, read_json
from .host import WINDOWS, exe, host_key, venv_executable
from .ui import SetupRequired, XError

# The downloaded tools, and the environment variable that replaces each one with a binary of the
# user's choosing, for hosts without a pinned binary (premake has none for linux-aarch64).
DOWNLOADED_TOOLS = ("premake5", "ninja", "actionlint", "zizmor")
OVERRIDES = {"premake5": "FORGE_PREMAKE5", "ninja": "FORGE_NINJA", "actionlint": "FORGE_ACTIONLINT",
             "zizmor": "FORGE_ZIZMOR"}

# The tools that live in the venv, as (wheel package, binary).
WHEEL_TOOLS = {
    "clang-format": ("clang_format", "clang-format"),
    "clang-tidy": ("clang_tidy", "clang-tidy"),
    "clang-apply-replacements": ("clang_tidy", "clang-apply-replacements"),
}

STAMP = "stamp.json"
GOOGLETEST_STAMP = ".forge-stamp.json"


def tool_dir(ctx: Context, name: str) -> Path:
    return ctx.tools / name


def tool_binary(ctx: Context, name: str) -> Path:
    return tool_dir(ctx, name) / "bin" / exe(ctx.manifest[name]["binary"])


def host_asset(ctx: Context, name: str) -> dict[str, str] | None:
    return ctx.manifest[name]["hosts"].get(host_key())


def expected_tool_stamp(ctx: Context, name: str) -> dict[str, str] | None:
    asset = host_asset(ctx, name)
    if asset is None:
        return None
    return {"version": ctx.manifest[name]["version"], "sha256": asset.get("sha256", "")}


def tool_status(ctx: Context, name: str) -> tuple[str, Path | None]:
    """("ok" | "override" | "missing" | "stale" | "unsupported", path) for a downloaded tool."""
    override = os.environ.get(OVERRIDES[name])
    if override:
        return "override", Path(override)
    expected = expected_tool_stamp(ctx, name)
    if expected is None:
        return "unsupported", None
    stamp = read_json(tool_dir(ctx, name) / STAMP)
    if stamp is None or not tool_binary(ctx, name).is_file():
        return "missing", None
    return ("ok" if stamp == expected else "stale"), tool_binary(ctx, name)


def require_tool(ctx: Context, name: str) -> Path:
    status, path = tool_status(ctx, name)
    if status in ("ok", "override"):
        return path
    version = ctx.manifest[name]["version"]
    if status == "unsupported":
        raise SetupRequired(f"tools.json pins no {name} for {host_key()}: set {OVERRIDES[name]} to a "
                            f"{name} {version} binary")
    state = "is not set up" if status == "missing" else "is out of date"
    raise SetupRequired(f"{name} {version} {state}: run ./x setup")


def tool_identity(ctx: Context, name: str) -> str:
    """What identifies the binary `require_tool` returns, for cache keys."""
    status, path = tool_status(ctx, name)
    if status == "override":
        return f"override:{path}"
    return json.dumps(expected_tool_stamp(ctx, name), sort_keys=True)


def python_packages_digest(ctx: Context) -> str:
    return hashlib.sha256(json.dumps(ctx.manifest["python"], sort_keys=True).encode()).hexdigest()


def python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def expected_venv_stamp(ctx: Context) -> dict[str, str]:
    return {"python": python_version(), "packages": python_packages_digest(ctx)}


def venv_python(ctx: Context) -> Path:
    return venv_executable(ctx.venv, "python")


def venv_status(ctx: Context) -> str:
    """"ok" | "missing" | "stale". The venv is stale when x runs on another Python minor version
    than the one that made it, or when tools.json pins other packages."""
    stamp = read_json(ctx.venv / STAMP)
    if stamp is None or not venv_python(ctx).is_file():
        return "missing"
    return "ok" if stamp == expected_venv_stamp(ctx) else "stale"


def require_venv(ctx: Context) -> Path:
    status = venv_status(ctx)
    if status != "ok":
        state = "is not set up" if status == "missing" else "is out of date"
        raise SetupRequired(f"the Python environment in {ctx.rel(ctx.venv)} {state}: run ./x setup")
    return venv_python(ctx)


def wheel_tool(ctx: Context, name: str) -> Path:
    """The binary that a clang wheel ships. Running it directly, rather than through the wheel's
    Python entry point, saves starting Python for each of the many files format and lint check."""
    require_venv(ctx)
    package, binary = WHEEL_TOOLS[name]
    site = "Lib/site-packages" if WINDOWS else "lib/python*/site-packages"
    matches = glob.glob(str(ctx.venv / site / package / "data" / "bin" / exe(binary)))
    if not matches:
        raise SetupRequired(f"{binary} is missing from {ctx.rel(ctx.venv)}: run ./x setup")
    return Path(matches[0])


def googletest_dir(ctx: Context) -> Path:
    return ctx.root / ctx.manifest["googletest"]["into"]


def expected_googletest_stamp(ctx: Context) -> dict[str, str]:
    spec = ctx.manifest["googletest"]
    return {"version": spec["version"], "sha256": spec.get("sha256", "")}


def googletest_status(ctx: Context) -> str:
    """"ok" | "missing" | "stale" | "foreign", the last for a tree that ./x setup did not install."""
    directory = googletest_dir(ctx)
    stamp = read_json(directory / GOOGLETEST_STAMP)
    if stamp is None:
        return "foreign" if directory.exists() else "missing"
    return "ok" if stamp == expected_googletest_stamp(ctx) else "stale"


def find_llvm_tool(name: str, variable: str) -> Path | None:
    """An LLVM tool that is not downloaded: the one `variable` names, else the first on PATH, in
    Homebrew's llvm, or in /usr/lib/llvm-<N> (Debian's apt.llvm.org packages), newest first."""
    configured = os.environ.get(variable)
    if configured:
        return Path(configured)
    found = shutil.which(name)
    if found:
        return Path(found)

    candidates = []
    prefixes = [os.environ.get("HOMEBREW_PREFIX", ""), "/opt/homebrew", "/usr/local"]
    for prefix in filter(None, prefixes):
        candidates.append(Path(prefix) / "opt" / "llvm" / "bin" / name)

    def llvm_version(path: str) -> int:
        match = re.search(r"llvm-(\d+)", path)
        return int(match.group(1)) if match else 0

    candidates += [Path(path) for path in sorted(glob.glob(f"/usr/lib/llvm-*/bin/{name}"),
                                                 key=llvm_version, reverse=True)]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def find_filecheck() -> Path | None:
    """FileCheck is not downloaded: LLVM's release archives leave it out (their builds keep
    LLVM_INSTALL_UTILS off), and the FileCheck on PyPI is a reimplementation without features the
    tests use. CI installs conda-forge's llvmdev (.github/ci/install-llvm-tools.sh). The in-tree
    FileCheck that testing.md plans will replace this search."""
    return find_llvm_tool("FileCheck", "FORGE_FILECHECK")


def find_symbolizer() -> Path | None:
    """llvm-symbolizer, which forge runs to put names and lines in stack traces
    (docs/stacktrace.md). It is not downloaded: x does not fetch a package manager's LLVM for one
    binary (CI gets it with FileCheck). Without it traces show addresses only, and the tests that
    need names skip."""
    found = find_llvm_tool(exe("llvm-symbolizer"), "FORGE_SYMBOLIZER_PATH")
    return found if found is not None and found.is_file() else None


def symbolizer_environment() -> dict[str, str]:
    """What ./x test and ./x run add to the environment of the programs they run, so that forge's
    stack traces find llvm-symbolizer wherever x found it."""
    symbolizer = find_symbolizer()
    return {"FORGE_SYMBOLIZER_PATH": str(symbolizer)} if symbolizer else {}


def require_filecheck() -> Path:
    filecheck = find_filecheck()
    if filecheck is None:
        raise SetupRequired("FileCheck not found: install LLVM (brew install llvm, or apt install "
                            "llvm-<N>-tools) or set FORGE_FILECHECK to a FileCheck binary")
    if not filecheck.is_file():
        raise XError(f"FORGE_FILECHECK is {filecheck}, which does not exist")
    return filecheck


def requests_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("requests") is not None
