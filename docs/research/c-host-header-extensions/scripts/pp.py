#!/usr/bin/env python3
"""Preprocess every accepted (root, configuration) pair with gcc-15 -E -dD.

usage: python3 -I pp.py [TREE_TAG [EXTRA_FLAGS...]]

Writes WORK/pp/<cfg>/<n>.i.gz, where n is the root's index in roots.tsv's
kept list, and WORK/pp/index.json. With TREE_TAG, writes WORK/pp-<TAG>/
instead and passes EXTRA_FLAGS (used for side experiments).
"""
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import accept  # noqa: E402


def one(job):
    cfg, n, root, outdir, extra = job
    rc, out, err = common.run_gcc(cfg, ["-E", "-dD"] + extra, common.tu_for(root))
    with gzip.open(os.path.join(outdir, cfg, "%d.i.gz" % n), "wt") as fh:
        fh.write(out)
    return cfg, n, rc, len(out)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else ""
    extra = sys.argv[2:]
    outdir = os.path.join(common.WORK, "pp-" + tag if tag else "pp")
    rs = accept.roots()
    acc = json.load(open(os.path.join(common.WORK, "accept.json")))
    jobs = []
    for c in common.CONFIG_NAMES:
        os.makedirs(os.path.join(outdir, c), exist_ok=True)
        for n, r in enumerate(rs):
            if acc[c][r]["ok"]:
                jobs.append((c, n, r, outdir, extra))
    idx = {"roots": rs, "pairs": {c: [] for c in common.CONFIG_NAMES}, "extra": extra}
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for cfg, n, rc, size in ex.map(one, jobs):
            if rc != 0:
                print("unexpected -E failure", cfg, rs[n], file=sys.stderr)
            idx["pairs"][cfg].append(n)
    for c in idx["pairs"]:
        idx["pairs"][c].sort()
    json.dump(idx, open(os.path.join(outdir, "index.json"), "w"))
    print({c: len(v) for c, v in idx["pairs"].items()})


if __name__ == "__main__":
    main()
