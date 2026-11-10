#!/usr/bin/env python3
"""Package owners and directive lines of the opened headers.

usage: python3 -I vmscan.py      (after extract.py and probe.py run)

For every header an accepted pair opened: its package (dpkg), and every
directive line other than conditionals and #define/#undef, with the
configurations (and root counts) in which GCC entered it. A line is entered
in a pair when the pair opened the file and the innermost enclosing
conditional branch was taken (its __forge_dt_K probe fired). Branch nesting
is recomputed with the same walk as probe.py's instrumenter, so site ids
match. Also records every `_Pragma` in those headers.
Writes WORK/vmscan.json.
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import probe  # noqa: E402

SKIP = {"if", "ifdef", "ifndef", "elif", "else", "elifdef", "elifndef", "endif", "define", "undef"}


def main():
    ex = json.load(open(os.path.join(common.WORK, "extract.json")))
    sites = json.load(open(os.path.join(common.WORK, "probe-sites.json")))["sites"]
    hits = json.load(open(os.path.join(common.WORK, "probe-hits.json")))["pairs"]
    opened = collections.defaultdict(lambda: collections.defaultdict(set))  # file -> cfg -> roots
    for c, f, rs in ex["opened"]:
        opened[os.path.realpath(f) if f.startswith("/") else f][c].update(rs)
    dt = collections.defaultdict(lambda: collections.defaultdict(set))      # site -> cfg -> roots
    for c, pairs in hits.items():
        for n, rec in pairs.items():
            for kind, k, cnt in rec["hits"]:
                if kind == "dt":
                    dt[k][c].add(int(n))
    cond_at = {(s["file"], s["line"]): s["id"] for s in sites if s["kind"] == "cond"}
    owners = {}
    lines_out = []
    for f in sorted(opened):
        if not f.startswith("/"):
            continue
        owners[f] = common.owner(f)
        raw = open(f, encoding="utf-8", errors="replace").read()
        stripped = [""] + common.strip_comments(raw).split("\n")
        stack = []
        i = 1
        n = len(stripped) - 1
        while i <= n:
            start = i
            text = stripped[i]
            while text.endswith("\\") and i < n:
                text = text[:-1] + " " + stripped[i + 1]
                i += 1
            i += 1
            m = probe.DIR_RE.match(text)
            pragma_ops = re.findall(r"\b_Pragma\s*\(([^)]*)\)", text)
            if m:
                d = m.group(1)
                if d in probe.COND_OPEN:
                    stack.append(cond_at.get((f, start)))
                    continue
                if d in probe.COND_MID:
                    if stack:
                        stack.pop()
                    stack.append(cond_at.get((f, start)))
                    continue
                if d == "endif":
                    if stack:
                        stack.pop()
                    continue
                if d in SKIP and not pragma_ops:
                    continue
            if not m and not pragma_ops:
                continue
            inner = stack[-1] if stack else None
            entered = {}
            for c in common.CONFIG_NAMES:
                rs = opened[f].get(c, set())
                if inner is not None:
                    rs = rs & dt[inner].get(c, set()) if inner in dt else set()
                if rs:
                    entered[c] = len(rs)
            if m and m.group(1) not in SKIP:
                lines_out.append({"file": f, "line": start, "directive": m.group(1),
                                  "text": " ".join(m.group(2).split())[:160], "entered": entered,
                                  "unknown": inner is None and bool(stack)})
            for arg in pragma_ops:
                lines_out.append({"file": f, "line": start, "directive": "_Pragma",
                                  "text": " ".join(arg.split())[:160], "entered": entered,
                                  "in_define": bool(m and m.group(1) == "define")})
    json.dump({"owners": owners, "directives": lines_out}, open(os.path.join(common.WORK, "vmscan.json"), "w"))
    print("files", len(owners), collections.Counter(owners.values()),
          "directive lines", len(lines_out), collections.Counter(x["directive"] for x in lines_out))


if __name__ == "__main__":
    main()
