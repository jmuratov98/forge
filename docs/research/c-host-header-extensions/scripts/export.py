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
    sp = os.path.join(work, "probe-sites.json")
    if os.path.exists(sp):
        export_queries(work, out)


def export_queries(work, out):
    sites = json.load(open(os.path.join(work, "probe-sites.json")))["sites"]
    hits = json.load(open(os.path.join(work, "probe-hits.json")))
    flips = json.load(open(os.path.join(work, "probe-flips.json")))
    ev = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for c, pairs in hits["pairs"].items():
        for n, rec in pairs.items():
            for kind, k, cnt in rec["hits"]:
                ev[k][c][kind] += 1
    fl = collections.defaultdict(list)
    for r in flips:
        fl[r["site"]].append(r)
    with open(os.path.join(out, "queries.tsv"), "w") as fh:
        fh.write("site\top\toperand\tin #define\tstatus\tGCC answer per configuration (roots)\t"
                 "flip: runs/changed/max lines\tflip: constructs added\tflip: constructs removed\tflip rc\n")
        for s in sites:
            if s["kind"] != "query":
                continue
            e = ev[s["id"]]
            d = s["directive"]
            evald = any(e[c]["qt"] or e[c]["qf"] for c in CONFIGS)
            dir_ev = d is not None and any(ev[d][c]["dt"] or ev[d][c]["df"] for c in CONFIGS)
            status = "evaluated" if evald else "short-circuited" if dir_ev else "not evaluated"
            ans = " ".join("%s=%s" % (c, "/".join(x for x in (
                ("1:%d" % e[c]["qt"]) if e[c]["qt"] else "", ("0:%d" % e[c]["qf"]) if e[c]["qf"] else "") if x))
                for c in CONFIGS if e[c]["qt"] or e[c]["qf"])
            rs = fl.get(s["id"], [])
            ch = [r for r in rs if r["added"]["n"] or r["removed"]["n"]]
            mx = max([r["added"]["n"] + r["removed"]["n"] for r in rs] or [0])
            add = sorted({n for r in rs for n in r["added"]["names"]})
            rem = sorted({n for r in rs for n in r["removed"]["names"]})
            rcs = sorted({r["rc"] for r in rs})
            fh.write("\t".join([
                "%s:%d" % (short(s["file"]), s["line"]), s["op"], s["text"], s["in_define"] or "",
                status, ans, "%d/%d/%d" % (len(rs), len(ch), mx) if rs else "",
                " ".join(add), " ".join(rem), " ".join(map(str, rcs))]) + "\n")
    with open(os.path.join(out, "probe-summary.txt"), "w") as fh:
        fh.write("instrumented files %d\nconditional sites %d (uninstrumented: %d)\nquery sites %d\n"
                 "pairs whose emitted code equals the uninstrumented run: %d of %d\n" % (
                     len(json.load(open(os.path.join(work, "probe-sites.json")))["files"]),
                     sum(1 for s in sites if s["kind"] == "cond"),
                     sum(1 for s in sites if s.get("unsafe")),
                     sum(1 for s in sites if s["kind"] == "query"),
                     hits["code_identical"], hits["code_identical"] + len(hits["code_differs"])))
        for s in sites:
            if s.get("unsafe"):
                fh.write("uninstrumented: %s:%d #%s %s\n" % (short(s["file"]), s["line"], s["directive"], s["text"]))


if __name__ == "__main__":
    main()
