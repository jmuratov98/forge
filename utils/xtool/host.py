# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The machine x runs on: its key in tools.json, the Python x needs on it, executable names, venv
layouts, and the MSVC environment."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from .ui import SetupRequired, Ui

WINDOWS = os.name == "nt"


def host_key() -> str:
    """`<os>-<arch>`, as tools.json names hosts: darwin-arm64, linux-aarch64, windows-x86_64, ..."""
    system = {"darwin": "darwin", "linux": "linux", "win32": "windows"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        # Each OS's own name for 64-bit ARM, as their release assets use it.
        arch = "aarch64" if system == "linux" else "arm64"
    else:
        arch = machine
    return f"{system}-{arch}"


def foreign_python(platform_name: str, version: str, system: str) -> str | None:
    """What kind of Python `sys.platform`, `sys.version` and `platform.system()` describe, when it
    is a Windows Python that cannot run x: MSYS2's or Cygwin's, POSIX builds that see a Cygwin host,
    for which tools.json pins no tools, or a MinGW build, such as MSYS2's ucrt64, mingw64 and
    clang64 Pythons. All of them make venvs with the POSIX layout (bin/, not Scripts\\), and none
    installs the Windows wheels that tools.json pins for clang-format and clang-tidy. None for any
    other Python: CPython as python.org builds it for Windows, with MSVC, and every Python on other
    hosts."""
    if platform_name in ("cygwin", "msys"):
        # MSYS2's runtime calls itself MINGW64_NT and the like in its MinGW shells; Cygwin's is
        # always CYGWIN_NT.
        return "Cygwin's Python" if system.upper().startswith("CYGWIN") else "MSYS2's Python"
    if platform_name == "win32" and "MSC v." not in version:
        return "a MinGW build of Python"
    return None


def require_native_python() -> None:
    """Stops x on a Python that foreign_python names. The ./x script looks for a native one first,
    but `python3 x.py`, x.cmd without the py launcher, or a PATH without a native Python still
    reach one."""
    kind = foreign_python(sys.platform, sys.version, platform.system())
    if kind is not None:
        raise SetupRequired(
            "x needs a native Windows Python 3.10 or newer, python.org's or the Python install "
            f"manager's, and {sys.executable} is {kind}, which cannot make the venv x needs. "
            "Install a native Python: ./x finds it as python, python3 or py on PATH (an MSYS2 shell "
            "keeps Windows' PATH only with MSYS2_PATH_TYPE=inherit), and x.cmd through py")


def exe(name: str) -> str:
    return name + ".exe" if WINDOWS else name


def venv_executable(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if WINDOWS else "bin") / exe(name)


# The Pythons that make venvs with the other layout, which this Python cannot use. Elsewhere it is
# a Windows Python, in a checkout that WSL shares with Windows.
FOREIGN_VENV_MAKERS = "MSYS2's, Cygwin's or a MinGW Python" if WINDOWS else "a Windows Python"


def is_foreign_venv(venv: Path) -> bool:
    """Whether one of FOREIGN_VENV_MAKERS made `venv`: it has the other layout's directory and not
    this one's Python."""
    return (not venv_executable(venv, "python").is_file()
            and (venv / ("bin" if WINDOWS else "Scripts")).is_dir())


def msvc_environment(ui: Ui, cache: Path) -> dict[str, str]:
    """The environment vcvarsall.bat sets up for the newest Visual Studio with the x64 C++ tools.

    Running vcvarsall takes seconds, so the result is cached in `cache`, keyed by the installation
    it came from.
    """
    program_files = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        raise SetupRequired("Visual Studio not found (no vswhere.exe): install Visual Studio 2022 or "
                            "newer with the C++ workload")
    query = ui.run([vswhere, "-latest", "-products", "*", "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property",
                    "installationPath"], capture=True, mutates=False)
    installation = query.stdout.strip()
    if not installation:
        raise SetupRequired("no Visual Studio installation has the x64 C++ tools")

    try:
        cached = json.loads(cache.read_text())
        if cached.get("installation") == installation:
            return cached["environment"]
    except (OSError, ValueError, KeyError):
        pass

    arch = "arm64" if platform.machine().lower() == "arm64" else "x64"
    vcvarsall = Path(installation) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
    ui.detail(f"reading the MSVC environment from {vcvarsall}")
    output = subprocess.run(f'cmd /s /c ""{vcvarsall}" {arch} >nul && set"', capture_output=True,
                            text=True, shell=False)
    if output.returncode != 0:
        raise SetupRequired(f"{vcvarsall} failed:\n{output.stdout}{output.stderr}")
    environment = dict(line.split("=", 1) for line in output.stdout.splitlines() if "=" in line)
    if not ui.dry_run:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"installation": installation, "environment": environment}))
    return environment
