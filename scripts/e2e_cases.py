"""End-to-end cases: parsing, rendering, compiling and running (docs/testing.md).

A case is one C file that ends with an expectation block:

    // EXPECT-EXIT: 5
    // EXPECT-STDOUT: hello

Shared by the lit test format (lit_e2e_format.py) and update-e2e. Nothing here
imports lit, so update-e2e runs without it.
"""

import difflib
import os
import subprocess
import sys

EXIT_PREFIX = "// EXPECT-EXIT:"
STDOUT_PREFIX = "// EXPECT-STDOUT:"
DEFAULT_TIMEOUT = 60


class CaseError(Exception):
    """A case that can't be run or whose expectation block is malformed."""


class Expectation:
    def __init__(self, exit_code, stdout):
        self.exit_code = exit_code
        self.stdout = stdout


def _split_block(lines):
    """Returns (code_lines, block_lines); the block is the trailing run of
    EXPECT-* lines plus the blank lines before it."""
    end = len(lines)
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    start = end
    while start > 0 and lines[start - 1].startswith("// EXPECT-"):
        start -= 1
    block = lines[start:end]
    while start > 0 and not lines[start - 1].strip():
        start -= 1
    return lines[:start], block


def parse_expectation(text):
    """Reads the trailing block. EXPECT-EXIT is required and comes first; each
    EXPECT-STDOUT line is one line of stdout, and none means empty stdout."""
    _, block = _split_block(text.splitlines())
    if not block or not block[0].startswith(EXIT_PREFIX):
        raise CaseError("the file must end with a '// EXPECT-EXIT: <code>' line "
                        "(then any '// EXPECT-STDOUT:' lines)")
    try:
        exit_code = int(block[0][len(EXIT_PREFIX):].strip())
    except ValueError:
        raise CaseError("EXPECT-EXIT must be an integer: " + block[0]) from None

    stdout = ""
    for line in block[1:]:
        if not line.startswith(STDOUT_PREFIX):
            raise CaseError("only EXPECT-STDOUT lines may follow EXPECT-EXIT: " + line)
        content = line[len(STDOUT_PREFIX):]
        if content.startswith(" "):
            content = content[1:]
        stdout += content + "\n"
    return Expectation(exit_code, stdout)


def render_block(exit_code, stdout):
    if stdout and not stdout.endswith("\n"):
        raise CaseError("stdout must end with a newline to be written as EXPECT-STDOUT lines")
    lines = ["%s %d" % (EXIT_PREFIX, exit_code)]
    for line in stdout.splitlines():
        lines.append((STDOUT_PREFIX + " " + line) if line else STDOUT_PREFIX)
    return "\n".join(lines) + "\n"


def replace_block(text, exit_code, stdout):
    """Returns text with its expectation block (if any) replaced."""
    code, _ = _split_block(text.splitlines())
    return "\n".join(code) + "\n\n" + render_block(exit_code, stdout)


def normalize_newlines(data):
    """Decodes program output; \\r\\n counts as \\n so a case passes on Windows."""
    try:
        return data.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        raise CaseError("the program wrote stdout that is not UTF-8") from None


def expand_command(template, source, output):
    """{src}, {out} and {obj} (an object file beside the output) in a command."""
    values = {"src": source, "out": output, "obj": output + ".obj"}
    return [part.format(**values) for part in template]


class RunResult:
    def __init__(self, exit_code, stdout):
        self.exit_code = exit_code
        self.stdout = stdout


def build_and_run(source, template, workdir, env=None, timeout=DEFAULT_TIMEOUT):
    """Compiles source with the command template, runs the result with no
    stdin and no arguments, and returns its exit code and stdout."""
    os.makedirs(workdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(source))[0]
    output = os.path.join(workdir, stem + (".exe" if sys.platform == "win32" else ""))

    command = expand_command(template, source, output)
    try:
        compiled = subprocess.run(command, cwd=workdir, env=env, timeout=timeout,
                                  stdin=subprocess.DEVNULL, capture_output=True)
    except FileNotFoundError:
        raise CaseError("compiler not found: " + command[0]) from None
    except subprocess.TimeoutExpired:
        raise CaseError("compiling took longer than %d s" % timeout) from None
    if compiled.returncode != 0:
        raise CaseError("compiling failed (%s):\n%s%s" % (
            " ".join(command), compiled.stdout.decode(errors="replace"),
            compiled.stderr.decode(errors="replace")))

    try:
        ran = subprocess.run([output], cwd=workdir, env=env, timeout=timeout,
                             stdin=subprocess.DEVNULL, capture_output=True)
    except subprocess.TimeoutExpired:
        raise CaseError("running the program took longer than %d s" % timeout) from None
    return RunResult(ran.returncode, normalize_newlines(ran.stdout))


def compare(expected, actual):
    """Returns a description of how actual differs from expected, or None."""
    problems = []
    if expected.exit_code != actual.exit_code:
        problems.append("exit code: expected %d, got %d" % (expected.exit_code, actual.exit_code))
    if expected.stdout != actual.stdout:
        diff = difflib.unified_diff(expected.stdout.splitlines(), actual.stdout.splitlines(),
                                    "expected stdout", "actual stdout", lineterm="")
        problems.append("stdout differs:\n" + "\n".join(diff))
    return "\n".join(problems) if problems else None
