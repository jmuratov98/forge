#!/usr/bin/env python3
"""Checks the CMake target graph against docs/layout.md's dependency rules.

    check_target_graph.py --source-dir . --cmake-arg=-DFORGE_BUILD_TESTS=OFF
    check_target_graph.py --build-dir build/debug

forge_add_library already refuses a disallowed edge, but a raw
target_link_libraries bypasses it. This reads the direct dependencies CMake
generated (through `cmake --graphviz`) and rejects any dependency cycle, any
edge between libraries outside cmake/library_edges.json, and any forge_* static
library that file doesn't list. Exits 1 and prints each problem.

With --source-dir the project is configured in a fresh temporary build
directory; with --build-dir an existing one is reconfigured.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

EDGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cmake", "library_edges.json")
PREFIX = "forge_"
# graphviz draws a static library as an octagon.
NODE = re.compile(r'^\s*"(node\d+)" \[ label = "([^"]*)", shape = (\w+) \]')
EDGE = re.compile(r'^\s*"(node\d+)" -> "(node\d+)"')


def load_edges(path):
    with open(path, encoding="utf-8") as handle:
        edges = json.load(handle)
    return {name: deps for name, deps in edges.items() if not name.startswith("_")}


def run_cmake(cmake, arguments):
    result = subprocess.run([cmake] + arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        sys.exit("cmake failed:\n" + result.stdout.decode(errors="replace"))


def read_libraries(dot_file):
    """Returns {library name: [library names it links directly]} for the
    forge_* static libraries in a graphviz file."""
    names = {}
    links = []
    with open(dot_file, encoding="utf-8") as handle:
        for line in handle:
            node = NODE.match(line)
            if node:
                label = node.group(2).split("\\n")[0]
                if node.group(3) == "octagon" and label.startswith(PREFIX):
                    names[node.group(1)] = label[len(PREFIX):]
                continue
            edge = EDGE.match(line)
            if edge:
                links.append(edge.groups())

    libraries = {name: set() for name in names.values()}
    for source, target in links:
        if source in names and target in names:
            libraries[names[source]].add(names[target])
    return {name: sorted(deps) for name, deps in libraries.items()}


def find_cycle(graph):
    """Returns one dependency cycle as a list of names, or None."""
    done, path = set(), []

    def visit(node):
        if node in path:
            return path[path.index(node):] + [node]
        if node in done:
            return None
        path.append(node)
        for other in graph.get(node, []):
            cycle = visit(other)
            if cycle:
                return cycle
        path.pop()
        done.add(node)
        return None

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def check(libraries, edges):
    problems = []
    for name in sorted(libraries):
        if name not in edges:
            problems.append("forge_%s is not a library in docs/layout.md; add it to "
                            "cmake/library_edges.json and the layout first" % name)
            continue
        allowed = edges[name]
        for dependency in libraries[name]:
            if "*" not in allowed and dependency not in allowed:
                problems.append("forge_%s links forge_%s, which docs/layout.md does not allow "
                                "(%s may depend on: %s)" % (name, dependency, name,
                                                            ", ".join(allowed) or "nothing"))
    cycle = find_cycle(libraries)
    if cycle:
        problems.append("dependency cycle: " + " -> ".join(PREFIX + name for name in cycle))
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--source-dir", help="configure this project in a temporary build directory")
    where.add_argument("--build-dir", help="reconfigure this existing build directory")
    parser.add_argument("--cmake", default="cmake", help="the cmake executable")
    parser.add_argument("--cmake-arg", action="append", default=[],
                        help="an extra cmake argument for --source-dir; repeatable")
    parser.add_argument("--edges", default=EDGES, help="the allowed-edge table")
    args = parser.parse_args()

    edges = load_edges(args.edges)
    with tempfile.TemporaryDirectory(prefix="forge-graph-") as scratch:
        dot_file = os.path.join(scratch, "graph.dot")
        if args.build_dir:
            run_cmake(args.cmake, ["--graphviz=" + dot_file, args.build_dir])
        else:
            build_dir = os.path.join(scratch, "build")
            run_cmake(args.cmake, ["-S", args.source_dir, "-B", build_dir] + args.cmake_arg)
            run_cmake(args.cmake, ["--graphviz=" + dot_file, build_dir])
        libraries = read_libraries(dot_file)

    problems = check(libraries, edges)
    for problem in problems:
        print("error: " + problem, file=sys.stderr)
    if problems:
        return 1
    print("check_target_graph: %d libraries, %d edges ok"
          % (len(libraries), sum(len(deps) for deps in libraries.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
