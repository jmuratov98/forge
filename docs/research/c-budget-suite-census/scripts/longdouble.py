"""Count long double expression nodes in program code with clang's AST dump.

Usage: python3 -I longdouble.py LTS_ROOT PROGRAMS_JSON DEB_ROOT OUT_JSON NAME...

For each named C program, runs clang -Xclang -ast-dump -fsyntax-only with
diag.py's clang-gnu17 sysroot and flags (aarch64-unknown-linux-gnu, glibc
2.43 headers). Tracks the current file from the dump's <file:line:col>
locations and counts, in files under LTS_ROOT only, nodes whose type is
'long double': arithmetic and comparison operators, casts by kind, calls,
and declarations. Text-dump based, so attribution follows clang's
"file changes only when printed" convention.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("diag", os.path.join(HERE, "diag.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

LOC = re.compile(r"<(/[^:>]+|[^<>:\s]+\.[chy]):(\d+)")
NODE = re.compile(r"^[\s|`-]*(\w+) 0x[0-9a-f]+")


def main():
    root, pj, deb, out = sys.argv[1:5]
    names = set(sys.argv[5:])
    rootn = os.path.realpath(root) + "/"
    base = diag.sysroot_args("clang", deb) + ["-std=gnu17", "-Xclang", "-ast-dump", "-w"]
    res = {}
    for p in json.load(open(pj))["programs"]:
        if p["name"] not in names or p["lang"] != "C":
            continue
        c = Counter()
        sites = Counter()
        pdir = os.path.join(root, p["dir"])
        for s in p["sources"]:
            r = subprocess.run(base + diag.prog_flags(p, False) + [s], cwd=pdir,
                               capture_output=True, text=True, errors="replace")
            cur, line_no = None, 0
            for line in r.stdout.splitlines():
                m = LOC.search(line)
                if m:
                    cur = os.path.realpath(os.path.join(pdir, m.group(1)))
                    line_no = int(m.group(2))
                else:
                    m2 = re.search(r"<line:(\d+)", line)
                    if m2:
                        line_no = int(m2.group(1))
                if not cur or not cur.startswith(rootn) or "'long double'" not in line:
                    continue
                n = NODE.match(line)
                if not n:
                    continue
                kind = n.group(1)
                if kind in ("BinaryOperator", "CompoundAssignOperator", "UnaryOperator"):
                    q = re.findall(r"'([^']*)'", line)  # type, then operator
                    op = q[1] if len(q) > 1 else "?"
                    kind = f"{kind} {op}"
                elif kind in ("ImplicitCastExpr", "CStyleCastExpr"):
                    ck = re.search(r"<(\w+)>", line[line.find("'long double'"):])
                    kind = f"{kind} <{ck.group(1) if ck else '?'}>"
                c[kind] += 1
                sites[f"{os.path.relpath(cur, rootn)}:{line_no}"] += 1
        res[p["name"]] = {"nodes": dict(c), "sites": len(sites),
                          "files": sorted({k.rsplit(':', 1)[0] for k in sites})}
    json.dump(res, open(out, "w"), indent=1)
    for k, v in res.items():
        print(k, v["sites"], sorted(v["nodes"].items(), key=lambda x: -x[1])[:25])


if __name__ == "__main__":
    main()
