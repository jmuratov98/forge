#!/usr/bin/env python3
"""Show conditional blocks entered in config A but not B.
usage: blockdiff.py OUTDIR MANIFEST CFG_A CFG_B [MAX]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx  # noqa: E402

out, man_p, a, b = sys.argv[1:5]
mx = int(sys.argv[5]) if len(sys.argv) > 5 else 200
act = json.load(open(out + "/pp/active.json"))
marks = json.load(open(out + "/markers.json"))
manifest = hx.load_manifest(man_p)
A, B = set(act[a]["union"]), set(act[b]["union"])
cache = {}


def directive_text(f, line):
    if f not in cache:
        cache[f] = {ll.start: ll for ll in hx.logical_lines(hx.read_text(manifest, f))}
    ll = cache[f].get(line)
    return " ".join(ll.code.split())[:110] if ll else "(file entry)"


rows = []
for k in A - B:
    f, line = marks[k]
    rows.append((f, line, directive_text(f, line) if line else "(file entry)"))
rows.sort()
print("%d blocks in %s not in %s" % (len(rows), a, b))
for r in rows[:mx]:
    print("%s:%d  %s" % (r[0].replace("/usr/include/", ""), r[1], r[2]))
