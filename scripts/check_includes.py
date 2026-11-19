#!/usr/bin/env python3
"""Checks every #include in Forge's source against ADR 0004's allowlist.

    check_includes.py [--root REPO]

Forge's own source includes only the allowlisted standard headers, its own
headers (forge/...), and, inside core only, C library and OS headers.
Everything else the C++ standard library provides comes from core. Tests are
exempt; build-time code generators are not. Exits 1 and prints file:line for
each violation.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpp_scan  # noqa: E402

ALLOWED = frozenset("""
    cstddef cstdint climits cfloat cstdarg limits version new initializer_list
    compare concepts type_traits utility bit atomic source_location cstring
""".split())

# The C library's C++ wrappers: C library headers, so they belong to core.
C_LIBRARY = frozenset("""
    cassert cctype cerrno cfenv cinttypes ciso646 clocale cmath csetjmp csignal
    cstdalign cstdbool cstdio cstdlib ctime cuchar cwchar cwctype
""".split())

# C++ standard library headers other than the allowlisted ones. core provides
# these; no file includes them, core included.
CXX_STANDARD = frozenset("""
    algorithm any array barrier bitset charconv chrono codecvt complex
    condition_variable coroutine deque exception execution expected filesystem
    flat_map flat_set format forward_list fstream functional future generator
    hazard_pointer hive inplace_vector iomanip ios iosfwd iostream istream
    iterator latch linalg list locale map mdspan memory memory_resource mutex
    numbers numeric optional ostream print queue random ranges ratio rcu regex
    scoped_allocator semaphore set shared_mutex simd span spanstream sstream
    stack stacktrace stdexcept stdfloat stop_token streambuf string string_view
    strstream syncstream system_error text_encoding thread tuple typeindex
    typeinfo unordered_map unordered_set valarray variant vector
""".split())

CORE_DIRECTORY = "forge/core/"
TEST_DIRECTORIES = ("test", "tests")
INCLUDE = re.compile(r"^[ \t]*#[ \t]*include[ \t]*<([^>\n]+)>", re.MULTILINE)


def violation(header, in_core):
    """Why including <header> is not allowed here, or None."""
    if header in ALLOWED or header.startswith("forge/"):
        return None
    if header in CXX_STANDARD:
        return ("<%s> is a C++ standard library header; core provides it "
                "(ADR 0004)" % header)
    if in_core:
        return None
    if header in C_LIBRARY:
        return "<%s> is a C library header; only core includes those (ADR 0004)" % header
    return "<%s> is a C library, OS or third-party header; only core includes those (ADR 0004)" % header


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=os.path.join(os.path.dirname(__file__), ".."),
                        help="the repository root (default: this one)")
    args = parser.parse_args()

    failures = 0
    checked = 0
    for path, relative in cpp_scan.source_files(args.root):
        if any(part in TEST_DIRECTORIES for part in relative.split("/")[:-1]):
            continue
        checked += 1
        with open(path, encoding="utf-8", errors="replace") as source:
            text = cpp_scan.blank_comments_and_strings(source.read())
        in_core = relative.startswith(CORE_DIRECTORY)
        for match in INCLUDE.finditer(text):
            problem = violation(match.group(1).strip(), in_core)
            if problem:
                line = text.count("\n", 0, match.start()) + 1
                print("%s:%d: error: %s" % (relative, line, problem), file=sys.stderr)
                failures += 1
    if failures:
        return 1
    print("check_includes: %d files ok" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
