# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The machine x runs on: its key in tools.json, executable names, and the MSVC environment."""

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


def exe(name: str) -> str:
    return name + ".exe" if WINDOWS else name


def venv_executable(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if WINDOWS else "bin") / exe(name)


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
