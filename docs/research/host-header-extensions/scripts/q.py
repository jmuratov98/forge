#!/usr/bin/env python3
"""Inspect scan hits.  usage: q.py OUTDIR REGEX [GROUP] [MAX]"""
import json
import re
import sys

out = sys.argv[1]
pat = re.compile(sys.argv[2])
grp = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
mx = int(sys.argv[4]) if len(sys.argv) > 4 else 40
scan = json.load(open(out + "/scan.json"))
act = json.load(open(out + "/pp/active.json"))
sets = {c: set(v["union"]) for c, v in act.items()}
n = 0
for h in scan["hits"]:
    if not pat.search(h["name"]) or (grp and h["group"] != grp):
        continue
    n += 1
    if n > mx:
        continue
    flags = "".join(c[0].upper() if h["block"] in sets[c] else "." for c in ("m1", "m1-O0", "m1-fortify", "gcc-eh", "clang", "neither"))
    g = h["guards"][-1] if h["guards"] else None
    gs = ("#%s %s" % (g["kind"], g["text"]))[:90] if g else "-"
    print("%s %s:%d [%s] %s | %s | %s" % (flags, h["file"].replace("/usr/include/", ""), h["line"], h["ctx"][:30], h["name"], h["spelling"][:60], gs))
print("total", n)
