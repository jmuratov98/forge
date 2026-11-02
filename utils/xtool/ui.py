# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Messages and subprocesses. Every message x prints and every command it runs goes through Ui, so
that -q, -v, -vv, --dry-run and --color mean the same thing in every command."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

QUIET = -1
NORMAL = 0
VERBOSE = 1
VERY_VERBOSE = 2


class XError(Exception):
    """A failure that x reports as `x: error: <message>` and exits with `code`."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


class SetupRequired(XError):
    """A tool or directory that `./x setup` provides is missing or out of date."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 3)


class UsageError(XError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 2)


def command_line(argv: Sequence[str | os.PathLike[str]]) -> str:
    """`argv` as a line that the platform's shell runs unchanged."""
    words = [os.fspath(word) for word in argv]
    if os.name == "nt":
        return subprocess.list2cmdline(words)
    return shlex.join(words)


def _wants_color(choice: str, stream) -> bool:
    if choice != "auto":
        return choice == "always"
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb" or not stream.isatty():
        return False
    # Older Windows consoles print escape sequences literally; Windows Terminal sets WT_SESSION.
    return os.name != "nt" or "WT_SESSION" in os.environ or "TERM" in os.environ


class Ui:
    def __init__(self, verbosity: int = NORMAL, color: str = "auto", dry_run: bool = False) -> None:
        self.verbosity = verbosity
        self.dry_run = dry_run
        self.color = color
        self._out_color = _wants_color(color, sys.stdout)
        self._err_color = _wants_color(color, sys.stderr)

    @property
    def quiet(self) -> bool:
        return self.verbosity <= QUIET

    def _paint(self, code: str, text: str, enabled: bool) -> str:
        return f"\033[{code}m{text}\033[0m" if enabled else text

    def step(self, message: str) -> None:
        """A heading for one part of a command, such as one tool being installed."""
        if self.verbosity >= NORMAL:
            print(self._paint("1;34", "==> ", self._out_color) + message, flush=True)

    def info(self, message: str) -> None:
        if self.verbosity >= NORMAL:
            print(message, flush=True)

    def detail(self, message: str) -> None:
        if self.verbosity >= VERBOSE:
            print(message, flush=True)

    def result(self, message: str) -> None:
        """Output that is the point of the command, such as a diff or a lint report: shown even
        with -q."""
        print(message, flush=True)

    def warn(self, message: str) -> None:
        label = self._paint("1;33", "warning", self._err_color)
        print(f"x: {label}: {message}", file=sys.stderr, flush=True)

    def error(self, message: str) -> None:
        label = self._paint("1;31", "error", self._err_color)
        print(f"x: {label}: {message}", file=sys.stderr, flush=True)

    def echo(self, argv: Sequence[str | os.PathLike[str]], cwd: Path | None = None,
             env: Mapping[str, str] | None = None) -> None:
        """Prints a command so that pasting it into a shell runs it the way x does."""
        line = command_line(argv)
        if env:
            line = " ".join(f"{name}={command_line([value])}" for name, value in env.items()) + " " + line
        if cwd is not None and Path(cwd).resolve() != Path.cwd().resolve():
            line = f"cd {command_line([cwd])} && {line}"
        print(self._paint("2", "$ " + line, self._out_color), flush=True)

    def run(
        self,
        argv: Sequence[str | os.PathLike[str]],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        base_env: Mapping[str, str] | None = None,
        mutates: bool = True,
        capture: bool = False,
        merge_stderr: bool = False,
        replay: bool = False,
        check: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Runs a command.

        `env` adds variables to `base_env` (default: x's own environment); only the additions are
        echoed. A command that `mutates` is printed instead of run under --dry-run; queries run
        either way. `capture` returns stdout as text, and with `merge_stderr` stderr in it too, for
        commands that run in parallel. `replay` hides the command's output under -q and prints it
        only if the command fails. `check` turns a failure into an XError.
        """
        words = [os.fspath(word) for word in argv]
        if self.dry_run and mutates:
            self.echo(words, cwd, env)
            return subprocess.CompletedProcess(words, 0, "", "")
        if self.verbosity >= VERBOSE:
            self.echo(words, cwd, env)

        environment = dict(base_env if base_env is not None else os.environ)
        environment.update(env or {})
        hide = replay and self.quiet and not capture
        try:
            completed = subprocess.run(
                words,
                cwd=cwd,
                env=environment,
                input=input,
                text=True,
                stdout=subprocess.PIPE if capture or hide else None,
                stderr=subprocess.STDOUT if hide or (capture and merge_stderr) else None,
            )
        except FileNotFoundError as error:
            raise XError(f"cannot run {words[0]}: {error.strerror}") from error
        if completed.returncode != 0:
            if hide and completed.stdout:
                sys.stderr.write(completed.stdout)
            if check:
                raise XError(f"{Path(words[0]).name} failed with exit code {completed.returncode}")
        return completed
