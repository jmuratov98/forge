# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Downloads and archive extraction, for setup and pin.

This is the one module that imports from the venv (requests), so only setup's second phase and pin
import it. Integrity comes from the sha256 that tools.json pins, which is checked while the bytes
arrive; extraction refuses anything that could write outside its destination.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .ui import NORMAL, Ui, XError

CHUNK = 1 << 20
TIMEOUT = (10, 60)


def session() -> requests.Session:
    """A session that retries transient failures with backoff. Proxies and REQUESTS_CA_BUNDLE come
    from the environment, as requests always reads them."""
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET"}))
    result = requests.Session()
    result.mount("https://", HTTPAdapter(max_retries=retry))
    result.mount("http://", HTTPAdapter(max_retries=retry))
    result.headers["User-Agent"] = "forge-x"
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_json(http: requests.Session, url: str):
    try:
        response = http.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise XError(f"cannot fetch {url}: {error}") from error


def fetch(ui: Ui, http: requests.Session, url: str, sha256: str | None, downloads: Path,
          label: str) -> tuple[Path, str]:
    """Downloads `url` into `downloads`, named by its sha256, and returns (path, sha256).

    With a pinned `sha256`, a cached copy is reused and a download that does not match is deleted
    and reported. pin passes None to learn the hash.
    """
    downloads.mkdir(parents=True, exist_ok=True)
    if sha256:
        cached = downloads / sha256
        if cached.is_file() and sha256_file(cached) == sha256:
            ui.detail(f"{label}: using {cached}")
            return cached, sha256

    part = downloads / f"download-{os.getpid()}.part"
    digest = hashlib.sha256()
    progress = ui.verbosity == NORMAL and sys.stderr.isatty()
    ui.detail(f"{label}: downloading {url}")
    try:
        with http.get(url, stream=True, timeout=TIMEOUT) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(part, "wb") as out:
                for chunk in response.iter_content(CHUNK):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress:
                        size = f"{done / 1e6:.1f}/{total / 1e6:.1f} MB" if total else f"{done / 1e6:.1f} MB"
                        sys.stderr.write(f"\r    {label}: {size}")
            if progress:
                sys.stderr.write("\n")
    except requests.exceptions.SSLError as error:
        part.unlink(missing_ok=True)
        raise XError(f"cannot download {url}: {error}\nBehind a proxy that re-signs TLS, set "
                     "REQUESTS_CA_BUNDLE to its CA bundle") from error
    except (requests.RequestException, OSError) as error:
        part.unlink(missing_ok=True)
        raise XError(f"cannot download {url}: {error}") from error

    actual = digest.hexdigest()
    if sha256 and actual != sha256:
        part.unlink(missing_ok=True)
        raise XError(f"{url} has sha256 {actual}, but tools.json pins {sha256}: the download is "
                     "corrupt or the file was replaced upstream")
    target = downloads / actual
    os.replace(part, target)
    return target, actual


@dataclass
class Member:
    name: PurePosixPath
    is_dir: bool
    executable: bool
    read: Callable[[], bytes]


def _checked_name(archive: Path, raw: str) -> PurePosixPath | None:
    """The member name as a relative path, or None for the archive's root entry. Absolute names,
    `..` and backslashes are refused: each could put a file outside the destination."""
    if "\\" in raw:
        raise XError(f"{archive}: refusing member '{raw}', whose name has a backslash")
    name = PurePosixPath(raw)
    if name.is_absolute() or ".." in name.parts or (name.parts and ":" in name.parts[0]):
        raise XError(f"{archive}: refusing member '{raw}', which points outside the archive")
    parts = [part for part in name.parts if part != "."]
    return PurePosixPath(*parts) if parts else None


def members(archive: Path) -> Iterator[Member]:
    """The files and directories in a .zip or a .tar.* archive. Links and special files are refused
    rather than extracted, so nothing can be written through them."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zip_file:
            for info in zip_file.infolist():
                name = _checked_name(archive, info.filename)
                if name is None:
                    continue
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise XError(f"{archive}: refusing member '{info.filename}', which is a link")
                yield Member(name, info.is_dir(), bool(mode & 0o111),
                             lambda info=info: zip_file.read(info))
        return

    try:
        tar = tarfile.open(archive, "r:*")
    except tarfile.TarError as error:
        raise XError(f"{archive}: not a zip or tar archive: {error}") from error
    with tar:
        for info in tar:
            name = _checked_name(archive, info.name)
            if name is None:
                continue
            if not (info.isfile() or info.isdir()):
                raise XError(f"{archive}: refusing member '{info.name}', which is not a regular "
                             "file or directory")

            def read(info=info) -> bytes:
                stream = tar.extractfile(info)
                return stream.read() if stream else b""

            yield Member(name, info.isdir(), bool(info.mode & 0o111), read)


def _write(member: Member, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(member.read())
    target.chmod(0o755 if member.executable else 0o644)


def extract_tree(archive: Path, strip: str, destination: Path) -> int:
    """Extracts every member under the top directory `strip` into `destination`, without that
    directory. Returns the number of files."""
    top = PurePosixPath(strip)
    count = 0
    for member in members(archive):
        if member.name == top:
            continue
        if top not in member.name.parents:
            raise XError(f"{archive}: member '{member.name}' is outside its top directory '{strip}'")
        target = destination.joinpath(*member.name.relative_to(top).parts)
        if member.is_dir:
            target.mkdir(parents=True, exist_ok=True)
        else:
            _write(member, target)
            count += 1
    return count


def extract_binary(archive: Path, binary: str, target: Path) -> None:
    """Extracts the one file named `binary`, wherever the archive keeps it, to `target`, executable
    whatever the archive says: zip files made on Windows carry no permissions."""
    # Written while iterating: a member can only be read while its archive is open.
    found = 0
    for member in members(archive):
        if not member.is_dir and member.name.name == binary:
            found += 1
            if found == 1:
                _write(member, target)
    if found != 1:
        target.unlink(missing_ok=True)
        raise XError(f"{archive}: expected one file named {binary}, found {found}")
    target.chmod(0o755)


def install_directory(destination: Path, populate: Callable[[Path], None]) -> None:
    """Fills a new directory with `populate`, then puts it in place of `destination` with renames,
    so that a failure at any point leaves the previous installation as it was."""
    temporary = destination.with_name(f"{destination.name}.tmp-{os.getpid()}")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    try:
        populate(temporary)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    previous = None
    if destination.exists():
        previous = destination.with_name(f"{destination.name}.old-{os.getpid()}")
        os.replace(destination, previous)
    os.replace(temporary, destination)
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)
