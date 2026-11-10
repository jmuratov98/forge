#!/usr/bin/env python3
"""Reduce the VM's raw results to the small files kept in git (data/).

usage: python3 -I export.py WORK_COPY OUT_DIR

WORK_COPY holds copies of the VM's accept.json, pedantic.json,
pedantic-noext.json (and, when present, gccnames.json, probe-*.json).
Writes:
  accept.tsv      root, then per configuration ok / first error
  pedantic.tsv    every pedantic diagnostic site: run, file:line, option,
                  message, configurations (roots per configuration)
"""
import collections
import json
import os
import sys

CONFIGS = ["gnu89", "gnu89+gs", "gnu99", "gnu99+gs", "gnu17", "gnu17+gs", "gnu23", "gnu23+gs"]


def short(p):
    for pre, rep in (("/usr/lib/gcc/aarch64-linux-gnu/15/include/", "gcc/"),
                     ("/usr/include/aarch64-linux-gnu/", "aarch64/"), ("/usr/include/", "")):
        if p.startswith(pre):
            return rep + p[len(pre):]
    return p


def main():
    work, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    acc = json.load(open(os.path.join(work, "accept.json")))
    roots = sorted(acc[CONFIGS[0]])
    with open(os.path.join(out, "accept.tsv"), "w") as fh:
        fh.write("root\t" + "\t".join(CONFIGS) + "\n")
        for r in roots:
            cells = []
            for c in CONFIGS:
                v = acc[c][r]
                if v["ok"]:
                    cells.append("ok" + (" (%d warning)" % v["n_warning"] if v["n_warning"] else ""))
                else:
                    fe = v["first_error"]
                    cells.append("FAIL %s:%d %s" % (short(fe[0]), fe[1], fe[3]) if fe else "FAIL rc=%d" % v["rc"])
            fh.write(r + "\t" + "\t".join(cells) + "\n")
    rows = []
    for run in ("pedantic", "pedantic-noext"):
        p = os.path.join(work, run + ".json")
        if not os.path.exists(p):
            continue
        ped = json.load(open(p))
        agg = collections.defaultdict(lambda: collections.defaultdict(set))
        for c in CONFIGS:
            for r, v in ped[c].items():
                for f, line, kind, msg, opt in v["diags"]:
                    if kind == "note":
                        continue
                    agg[(short(f), line, opt, msg)][c].add(r)
        for (f, line, opt, msg), cs in sorted(agg.items()):
            rows.append([run, "%s:%d" % (f, line), opt, msg,
                         " ".join("%s=%d" % (c, len(cs[c])) for c in CONFIGS if c in cs)])
    with open(os.path.join(out, "pedantic.tsv"), "w") as fh:
        fh.write("run\tsite\toption\tmessage\tconfigurations (roots)\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")
    print("accept rows", len(roots), "pedantic rows", len(rows))


if __name__ == "__main__":
    main()
