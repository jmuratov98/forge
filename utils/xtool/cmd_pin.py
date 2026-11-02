# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""./x pin: writes the sha256s of the versions in tools.json back into it. For maintainers.

To move to a new version: edit its `version` in tools.json, run ./x pin, and review the diff.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import tools
from .cmd_setup import global_flags
from .context import Context
from .host import venv_executable

NAMES = ("premake5", "ninja", "googletest", "python")


def pin_name(text: str) -> str:
    # Not argparse's choices: with nargs="*", older Pythons check the empty default against them.
    if text not in NAMES:
        raise argparse.ArgumentTypeError(f"choose from {', '.join(NAMES)}")
    return text


def register(subparsers, common) -> None:
    parser = subparsers.add_parser(
        "pin", parents=[common], help="record the sha256s of the versions in tools.json (maintainers)",
        description="Downloads every host's asset of each tool to hash it, and reads the wheels' "
                    "hashes from PyPI, then rewrites tools.json.")
    parser.add_argument("names", nargs="*", type=pin_name, metavar="NAME",
                        help=f"what to pin: {', '.join(NAMES)} (default: all)")
    parser.set_defaults(handler=run)


def run(ctx: Context, args: argparse.Namespace) -> int:
    if not tools.requests_available():
        return run_in_pin_venv(ctx, args)
    from . import download

    names = args.names or list(NAMES)
    manifest = ctx.manifest
    http = download.session()
    downloads = ctx.cache / "downloads"

    for name in ("premake5", "ninja"):
        if name not in names:
            continue
        spec = manifest[name]
        hashes: dict[str, str] = {}
        for host, asset in sorted(spec["hosts"].items()):
            url = spec["url"].format(version=spec["version"], asset=asset["asset"])
            if url not in hashes:
                ctx.ui.step(f"{name} {spec['version']}: {url}")
                _, hashes[url] = download.fetch(ctx.ui, http, url, None, downloads, f"{name} {host}")
            asset["sha256"] = hashes[url]

    if "googletest" in names:
        spec = manifest["googletest"]
        url = spec["url"].format(version=spec["version"])
        ctx.ui.step(f"googletest {spec['version']}: {url}")
        _, spec["sha256"] = download.fetch(ctx.ui, http, url, None, downloads, "googletest")

    if "python" in names:
        for package, spec in manifest["python"].items():
            spec["sha256"] = wheel_hashes(ctx, http, package, spec["version"])

    if ctx.ui.dry_run:
        ctx.ui.result(json.dumps(manifest, indent=2))
    else:
        ctx.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        ctx.ui.info(f"wrote {ctx.rel(ctx.manifest_path)}")
    return 0


def wheel_hashes(ctx: Context, http, package: str, version: str) -> list[str]:
    """The hashes pip may install for `package`: its pure-Python wheel when there is one, since pip
    then needs nothing else, and otherwise every platform's wheel. Read from PyPI's JSON API, so
    nothing is downloaded."""
    from . import download

    ctx.ui.step(f"{package} {version}: hashes from PyPI")
    data = download.get_json(http, f"https://pypi.org/pypi/{package}/{version}/json")
    wheels = [file for file in data["urls"] if file["packagetype"] == "bdist_wheel"]
    if not wheels:
        raise tools.XError(f"PyPI has no wheels for {package} {version}")
    pure = [file for file in wheels if file["filename"].endswith("-py3-none-any.whl")]
    chosen = pure[:1] or wheels
    return sorted(file["digests"]["sha256"] for file in chosen)


def run_in_pin_venv(ctx: Context, args: argparse.Namespace) -> int:
    """The first pin has no hashes to install requests with, so it runs in a throwaway venv where
    requests comes from PyPI without one. This is the one place x trusts PyPI's TLS alone, and only
    maintainers run pin."""
    venv = ctx.cache / "pin-venv"
    python = venv_executable(venv, "python")
    if not python.is_file():
        version = ctx.manifest["python"]["requests"]["version"]
        ctx.ui.step(f"creating {ctx.rel(venv)} with requests {version}")
        ctx.ui.run([sys.executable, "-m", "venv", venv], replay=True)
        ctx.ui.run([python, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                    f"requests=={version}"], replay=True)
    argv = [python, ctx.code_root / "x.py", *global_flags(ctx), "pin", *args.names]
    return ctx.ui.run(argv, mutates=False, check=False).returncode
