# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""What every command is given: the repository, where x keeps its state, and the Ui."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ui import Ui, XError


@dataclass
class Context:
    # The repository x works on. It is where x.py is, unless x's own tests pass --root.
    root: Path
    # Where x.py and utils/xtool are.
    code_root: Path
    ui: Ui
    # premake's forge-describe output, for the commands that take build options. When premake is
    # not set up yet, describe_error says so, and only the commands that need the data fail.
    describe_data: dict[str, Any] | None = None
    describe_error: XError | None = None
    _manifest: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def state(self) -> Path:
        return self.root / ".forge"

    @property
    def tools(self) -> Path:
        return self.state / "tools"

    @property
    def venv(self) -> Path:
        return self.state / "venv"

    @property
    def cache(self) -> Path:
        return self.state / "cache"

    @property
    def manifest_path(self) -> Path:
        return self.root / "utils" / "xtool" / "tools.json"

    @property
    def manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            try:
                self._manifest = json.loads(self.manifest_path.read_text())
            except (OSError, ValueError) as error:
                raise XError(f"cannot read {self.manifest_path}: {error}") from error
        return self._manifest

    def rel(self, path: Path | str) -> str:
        """`path` relative to the current directory when it is inside it, for messages."""
        path = Path(path)
        try:
            return os.path.relpath(path) if path.resolve().is_relative_to(Path.cwd().resolve()) else str(path)
        except ValueError:
            # Another drive on Windows.
            return str(path)


def read_json(path: Path) -> Any:
    """The JSON in `path`, or None when it is missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_if_changed(path: Path, text: str) -> bool:
    """Writes `text` to `path` unless it already holds it, so that tools watching the file do not
    see a change. Returns whether it wrote."""
    try:
        if path.read_text() == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True
