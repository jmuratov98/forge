#!/usr/bin/env python3
"""Steering surface: identifiers tested by conditionals in the closure that
no header in the closure #defines (so they come from the compiler, the
command line, or the user), plus preprocessor queries.

usage: steer.py OUTDIR CLANG_PREDEF_TXT OUT_JSON
"""
import collections
import json
import re
import sys


def main():
    out = sys.argv[1]
    scan = json.load(open(out + "/scan.json"))
    act = json.load(open(out + "/pp/active.json"))
    m1 = set(act["m1"]["union"])
    clang_pre = {}
    for line in open(sys.argv[2]):
        m = re.match(r"#define (\w+)(?:\(.*?\))? ?(.*)$", line.rstrip("\n"))
        if m:
            clang_pre[m.group(1)] = m.group(2)
    defined_in_headers = collections.defaultdict(list)
    for d in scan["defines"]:
        defined_in_headers[d["name"]].append("%s:%d" % (d["file"], d["line"]))
    ids = collections.defaultdict(lambda: {"tests": 0, "files": set(), "sites": [], "m1_sites": 0})
    for c in scan["conds"]:
        for x in c["ids"]:
            r = ids[x]
            r["tests"] += 1
            r["files"].add(c["file"])
            live = c["block"] in m1
            if live:
                r["m1_sites"] += 1
            if len(r["sites"]) < 400:
                r["sites"].append({"file": c["file"], "line": c["line"], "kind": c["kind"],
                                   "text": c["text"], "live": live})
    res = []
    for x, r in ids.items():
        res.append({
            "name": x, "tests": r["tests"], "files": len(r["files"]), "m1_sites": r["m1_sites"],
            "defined_in_headers": defined_in_headers.get(x, [])[:5],
            "n_defined_in_headers": len(defined_in_headers.get(x, [])),
            "clang_predef": clang_pre.get(x),
            "sites": r["sites"],
        })
    res.sort(key=lambda r: -r["tests"])
    queries = collections.defaultdict(lambda: {"n": 0, "live": 0, "sites": []})
    for c in scan["conds"]:
        for q in c["queries"]:
            k = "%s(%s)" % (q[0], q[1])
            queries[k]["n"] += 1
            if c["block"] in m1:
                queries[k]["live"] += 1
            queries[k]["sites"].append("%s:%d" % (c["file"], c["line"]))
    with open(sys.argv[3], "w") as f:
        json.dump({"ids": res, "queries": queries}, f, indent=0)
    ext = [r for r in res if r["n_defined_in_headers"] == 0]
    print(len(res), "conditional identifiers;", len(ext), "never defined in headers;",
          len(queries), "distinct queries", file=sys.stderr)


if __name__ == "__main__":
    main()
