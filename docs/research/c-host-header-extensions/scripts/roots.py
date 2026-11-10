#!/usr/bin/env python3
"""Enumerate the root set: one TU per header libc6-dev ships under /usr/include.

usage: python3 -I roots.py OUT_TSV

Rule (issue #10's header sweep): every regular file in `dpkg -L libc6-dev`
under /usr/include, named relative to /usr/include/aarch64-linux-gnu when it
lives there and relative to /usr/include otherwise; skip any name with a
`bits` path component, and kernel `linux/` and `asm/` names. Writes
`name<TAB>physical path<TAB>kept|skip:<reason>` for every file.
"""
import os
import subprocess
import sys

MULTI = "/usr/include/aarch64-linux-gnu/"


def main():
    out = sys.argv[1]
    files = subprocess.run(["dpkg", "-L", "libc6-dev"], capture_output=True,
                           text=True, check=True).stdout.splitlines()
    rows = []
    for f in files:
        if not f.startswith("/usr/include/") or not os.path.isfile(f) or os.path.islink(f):
            continue
        name = f[len(MULTI):] if f.startswith(MULTI) else f[len("/usr/include/"):]
        parts = name.split("/")
        if "bits" in parts[:-1]:
            why = "skip:bits"
        elif parts[0] in ("linux", "asm"):
            why = "skip:kernel"
        elif not name.endswith(".h"):
            why = "skip:not-.h"
        else:
            why = "kept"
        rows.append((name, f, why))
    rows.sort()
    with open(out, "w") as fh:
        for r in rows:
            fh.write("\t".join(r) + "\n")
    kept = sum(1 for r in rows if r[2] == "kept")
    print("files", len(rows), "kept", kept,
          {w: sum(1 for r in rows if r[2] == w) for w in sorted({r[2] for r in rows})})


if __name__ == "__main__":
    main()
