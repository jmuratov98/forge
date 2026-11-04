#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""Checks the mechanical rules of forge's standardese specs: python3 check_spec.py [FILE...]

With no FILE, checks every docs/*.md. Cross-references resolve against every spec in docs/, so a
reference from one spec to another is checked too. A bracketed name whose first part is not the
prefix of a forge spec is taken to be an ISO/IEC 14882 stable name and is not checked.

Diagnostics are printed as path:line:column: error: message [rule], like ./x lint. Exits 1 when
there are any.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^(#{1,4}) (.*?) \[([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*)\]\s*$")
PARAGRAPH = re.compile(r"^(\d+) \S")
SUB_ITEM = re.compile(r"^\s*- \((\d+(?:\.\d+)+)\) ")
NOTE_OPEN = re.compile(r"\[(Note|Example) (\d+):")
NOTE_CLOSE = re.compile(r"— end (note|example)\]")
# A stable name in text, but not a Markdown link's text and not [Note 1: or [Example 1:.
REFERENCE = re.compile(r"\[([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+|[a-z][a-z0-9_]*)\](?!\()")
ELEMENT = re.compile(r"^\d+ \*([A-Z][a-z]+(?: [A-Za-z][a-z]+)?)\*:")

# The order of [structure.specifications]; an element may repeat but not go back.
ELEMENT_ORDER = ("Constraints", "Mandates", "Constant When", "Preconditions",
                 "Hardened preconditions", "Effects", "Synchronization", "Postconditions", "Result",
                 "Returns", "Throws", "Complexity", "Remarks", "Error conditions")


@dataclass
class Diagnostic:
    path: Path
    line: int
    column: int
    message: str
    rule: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: error: {self.message} [{self.rule}]"


@dataclass
class Spec:
    path: Path
    lines: list[str]
    prefix: str | None = None
    # Stable name -> line, for the headings of this spec.
    names: dict[str, int] = field(default_factory=dict)


def prose_lines(lines: list[str]):
    """(line number, text, starts a code block) for each line outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(lines, 1):
        if line.startswith("```"):
            fenced = not fenced
            if fenced:
                yield number, "", True
            continue
        if not fenced:
            yield number, line, False


def load(path: Path) -> Spec:
    spec = Spec(path, path.read_text(encoding="utf-8").splitlines())
    for number, line, _ in prose_lines(spec.lines):
        heading = HEADING.match(line)
        if heading:
            name = heading.group(3)
            if len(heading.group(1)) == 1 and spec.prefix is None:
                spec.prefix = name
            spec.names.setdefault(name, number)
    return spec


def check(spec: Spec, all_names: dict[str, tuple[Path, int]], prefixes: set[str]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    def error(number: int, column: int, message: str, rule: str) -> None:
        diagnostics.append(Diagnostic(spec.path, number, column, message, rule))

    if spec.prefix is None:
        error(1, 1, "the first heading must be '# Title [prefix]'", "title")
        return diagnostics
    if not any(line.startswith("Status: ") for line in spec.lines[:10]):
        error(2, 1, "a 'Status: draft, YYYY-MM-DD.' line must follow the title", "status")
    if f"{spec.prefix}.conventions" not in spec.names:
        error(1, 1, f"no conventions clause [{spec.prefix}.conventions]", "conventions")

    paragraph = 0
    sub_items: dict[str, int] = {}
    counters = {"Note": 0, "Example": 0}
    open_notes: list[tuple[str, int]] = []
    element_index = -1
    previous = ""

    for number, line, code in prose_lines(spec.lines):
        # Paragraph numbers start a block; a wrapped line that starts with a number does not.
        starts_block, previous = previous.strip() == "", line
        if code:
            # A new declaration starts a new function specification.
            element_index, previous = -1, ""
            continue

        heading = HEADING.match(line)
        if heading:
            name = heading.group(3)
            if name != spec.prefix and not name.startswith(spec.prefix + "."):
                error(number, line.index("[") + 2, f"[{name}] does not start with the spec's prefix "
                      f"'{spec.prefix}.'", "stable-name")
            first = all_names.get(name)
            if first and (first[0] != spec.path or first[1] != number):
                error(number, line.index("[") + 2, f"[{name}] is already defined at "
                      f"{first[0]}:{first[1]}", "stable-name")
            for kind, opened in open_notes:
                error(opened, 1, f"[{kind} ...: has no '— end {kind.lower()}]'", "note")
            paragraph, sub_items, open_notes, element_index = 0, {}, [], -1
            counters = {"Note": 0, "Example": 0}
            continue
        if line.startswith("#"):
            error(number, 1, "a heading needs a stable name: '## N Title [prefix.name]'", "stable-name")
            continue

        match = PARAGRAPH.match(line) if starts_block else None
        if match:
            value = int(match.group(1))
            if value != paragraph + 1:
                error(number, 1, f"paragraph {value} follows paragraph {paragraph}; expected "
                      f"{paragraph + 1}", "numbering")
            paragraph = value
            sub_items = {}

        match = SUB_ITEM.match(line)
        if match:
            parts = match.group(1).split(".")
            column = line.index("(") + 2
            if int(parts[0]) != paragraph:
                error(number, column, f"item ({match.group(1)}) is in paragraph {paragraph}",
                      "numbering")
            parent = ".".join(parts[:-1])
            expected = sub_items.get(parent, 0) + 1
            if int(parts[-1]) != expected:
                error(number, column, f"item ({match.group(1)}) should be ({parent}.{expected})",
                      "numbering")
            sub_items[parent] = int(parts[-1])

        for note in NOTE_OPEN.finditer(line):
            kind, value = note.group(1), int(note.group(2))
            counters[kind] += 1
            if value != counters[kind]:
                error(number, note.start() + 1, f"{kind} {value} should be {kind} {counters[kind]} "
                      "(numbered within each clause)", "note")
            open_notes.append((kind, number))
        for close in NOTE_CLOSE.finditer(line):
            kind = close.group(1).capitalize()
            if open_notes and open_notes[-1][0] == kind:
                open_notes.pop()
            else:
                error(number, close.start() + 1, f"'— end {close.group(1)}]' closes nothing", "note")

        element = ELEMENT.match(line) if starts_block else None
        if element:
            name = element.group(1)
            if name not in ELEMENT_ORDER:
                error(number, line.index("*") + 1, f"*{name}* is not an element of "
                      "[structure.specifications]", "element")
            else:
                index = ELEMENT_ORDER.index(name)
                if index < element_index:
                    error(number, line.index("*") + 1, f"*{name}* comes after "
                          f"*{ELEMENT_ORDER[element_index]}*; the order is "
                          f"{', '.join(ELEMENT_ORDER)}", "element")
                element_index = max(element_index, index)

        for reference in REFERENCE.finditer(line):
            name = reference.group(1)
            if name.split(".")[0] in prefixes and name not in all_names:
                error(number, reference.start() + 2, f"[{name}] is not a stable name in docs/",
                      "reference")

    for kind, opened in open_notes:
        error(opened, 1, f"[{kind} ...: has no '— end {kind.lower()}]'", "note")
    return diagnostics


def repository_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        if (directory / "x.py").is_file() and (directory / "premake5.lua").is_file():
            return directory
    sys.exit("check_spec.py: cannot find the forge repository above this script")


def main(argv: list[str]) -> int:
    docs = repository_root() / "docs"
    every = sorted(docs.glob("*.md"))
    targets = [Path(arg).resolve() for arg in argv] or every
    specs = {path: load(path) for path in {*every, *targets}}

    all_names: dict[str, tuple[Path, int]] = {}
    for path in sorted(specs):
        for name, number in specs[path].names.items():
            all_names.setdefault(name, (path, number))
    prefixes = {spec.prefix for spec in specs.values() if spec.prefix}

    diagnostics = []
    for path in targets:
        diagnostics += check(specs[path], all_names, prefixes)
    for diagnostic in diagnostics:
        print(diagnostic.format())
    return 1 if diagnostics else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
