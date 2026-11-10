#!/usr/bin/env python3
"""Observe GCC's own conditional evaluation and __has_* answers.

usage: python3 -I probe.py instrument   (normal user; after extract.py)
       sudo env C13_WORK=... unshare -m sh probe-mount.sh INST python3 -I probe.py run
       sudo env C13_WORK=... unshare -m sh probe-mount.sh INST python3 -I probe.py flips

instrument: copies /usr/include and GCC's include directory to WORK/inst/ and
rewrites, in every header some accepted pair opened, without changing any
line number:
  * every conditional directive into an equivalent #if/#elif whose value is
        ((EXPR) ? (__forge_dt_K + 1) : (__forge_df_K + 0))
    (#ifdef X -> defined X, #ifndef X -> !defined X, #else -> #elif 1);
  * every query operand Q inside those expressions, and inside #define bodies
    (other than the wrapper macros' own definitions), into
        ((__forge_flip_K) ? !(Q) : ((Q) ? (__forge_qt_K + (Q)) : (__forge_qf_K + (Q))))
    Query operands are calls of __has_builtin, __has_attribute,
    __has_c_attribute, __has_cpp_attribute, __has_include, __has_include_next,
    __has_feature, __has_extension, __has_embed, __has_warning,
    __is_identifier, glibc's __glibc_has_attribute, __glibc_has_builtin,
    __glibc_has_extension, __GNUC_PREREQ, __glibc_clang_prereq, and
    `defined OP` for any of the operators.
  Writes WORK/probe-sites.json.
run: runs every accepted pair with -E -Wundef -Wsystem-headers against the
  instrumented tree (bind-mounted over the real paths by probe-mount.sh).
  libcpp's -Wundef warning fires only for identifiers it actually evaluates
  (not for operands skipped by && / || / ?:), so each __forge_* warning says
  that GCC evaluated that directive or operand, and the t/f name says what it
  found. Writes WORK/probe-hits.json.
flips: for each query operand GCC evaluated, re-runs up to 3 roots that
  evaluate it per configuration with -D__forge_flip_K=1 (the opposite answer)
  and records which emitted lines change. Writes WORK/probe-flips.json.
"""
import collections
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

OPS = ["__has_builtin", "__has_attribute", "__has_c_attribute", "__has_cpp_attribute",
       "__has_include_next", "__has_include", "__has_feature", "__has_extension", "__has_embed",
       "__has_warning", "__is_identifier"]
WRAPPERS = ["__glibc_has_attribute", "__glibc_has_builtin", "__glibc_has_extension",
            "__GNUC_PREREQ", "__glibc_clang_prereq"]
CALL_RE = re.compile(r"\b(%s)\s*\(" % "|".join(OPS + WRAPPERS))
DEFINED_RE = re.compile(r"\bdefined\s*(\(\s*(%s)\s*\)|(%s)\b)" % ("|".join(OPS + WRAPPERS), "|".join(OPS + WRAPPERS)))
DIR_RE = re.compile(r"^\s*#\s*(\w+)\b(.*)$", re.S)
COND_OPEN = {"if", "ifdef", "ifndef"}
COND_MID = {"elif", "else", "elifdef", "elifndef"}
INST = os.path.join(common.WORK, "inst")
TREES = [("/usr/include", "usr-include"), (common.GCC_INC, "gcc-include")]
PROBE_RE = re.compile(r'"__forge_(dt|df|qt|qf|flip)_(\d+)" is not defined')


def comment_state(text):
    """Per physical line (1-based): does the line end inside a /* comment?"""
    res = [False]
    inc = False
    i, n = 0, len(text)
    line_end_flags = []
    while i < n:
        c = text[i]
        if inc:
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                inc = False
                i += 2
                continue
        else:
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                inc = True
                i += 2
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "/":
                j = text.find("\n", i)
                i = n if j < 0 else j
                continue
            if c in "\"'":
                j = i + 1
                while j < n and text[j] != c and text[j] != "\n":
                    j += 2 if text[j] == "\\" else 1
                i = j + 1
                continue
        if c == "\n":
            line_end_flags.append(inc)
        i += 1
    line_end_flags.append(inc)
    return res + line_end_flags


def find_close(s, i):
    """s[i] == '('; index of the matching ')'."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def wrap_queries(expr, new_site):
    """Wrap every query operand in expr; new_site(op, text) returns an id."""
    spans = []
    for m in CALL_RE.finditer(expr):
        op = m.group(1)
        o = expr.index("(", m.end() - 1)
        c = find_close(expr, o)
        if c < 0:
            continue
        spans.append((m.start(), c + 1, op, "call"))
    for m in DEFINED_RE.finditer(expr):
        op = m.group(2) or m.group(3)
        spans.append((m.start(), m.end(), op, "defined"))
    spans.sort()
    # drop overlaps (keep the outer / first)
    keep, last = [], -1
    for s in spans:
        if s[0] >= last:
            keep.append(s)
            last = s[1]
    out = expr
    for a, b, op, kind in reversed(keep):
        q = expr[a:b]
        k = new_site(op, kind, " ".join(q.split()))
        rep = ("((__forge_flip_%d) ? !(%s) : ((%s) ? (__forge_qt_%d + (%s)) : (__forge_qf_%d + (%s))))"
               % (k, q, q, k, q, k, q))
        out = out[:a] + rep + out[b:]
    return out


def instrument_file(path, dest, fid, sites):
    raw = open(path, encoding="utf-8", errors="replace").read()
    ends_in_c = comment_state(raw)
    stripped = common.strip_comments(raw).split("\n")
    phys = raw.split("\n")
    lines = [""] + stripped
    out = [""] + list(phys)
    stack = []
    i = 1
    nlines = len(lines) - 1
    while i <= nlines:
        start = i
        text = lines[i]
        while text.endswith("\\") and i < nlines:
            text = text[:-1] + " " + lines[i + 1]
            i += 1
        end = i
        i += 1
        m = DIR_RE.match(text)
        if not m:
            continue
        d, rest = m.group(1), m.group(2).strip()
        unsafe = ends_in_c[end] if end < len(ends_in_c) else False

        def new_site(op, kind, q, _st=start):
            k = len(sites)
            sites.append({"id": k, "file": path, "line": _st, "kind": "query", "op": op, "form": kind,
                          "text": q, "directive": None, "in_define": None})
            return k

        if d in COND_OPEN or d in COND_MID:
            k = len(sites)
            parent = None
            prev = None
            if d in COND_MID:
                if stack:
                    prev = stack.pop()
                    parent = sites[prev]["parent"]
            else:
                parent = stack[-1] if stack else None
            site = {"id": k, "file": path, "line": start, "kind": "cond", "directive": d, "text": rest,
                    "parent": parent, "prev": prev, "unsafe": unsafe, "queries": []}
            sites.append(site)
            stack.append(k)
            if unsafe:
                continue
            if d == "ifdef":
                expr = "defined " + rest
            elif d == "ifndef":
                expr = "!defined " + rest
            elif d == "elifdef":
                expr = "defined " + rest
            elif d == "elifndef":
                expr = "!defined " + rest
            elif d == "else":
                expr = "1"
            else:
                expr = rest
            before = len(sites)
            expr2 = wrap_queries(expr, new_site)
            for q in range(before, len(sites)):
                sites[q]["directive"] = k
            site["queries"] = list(range(before, len(sites)))
            kw = "#if" if d in COND_OPEN else "#elif"
            new = "%s ((%s) ? (__forge_dt_%d + 1) : (__forge_df_%d + 0))" % (kw, expr2, k, k)
            out[start] = new
            for L in range(start + 1, end + 1):
                out[L] = ""
        elif d == "endif":
            if stack:
                stack.pop()
        elif d == "define" and not unsafe:
            dm = re.match(r"(\w+)(\([^)]*\))?(.*)$", rest, re.S)
            if not dm or dm.group(1) in WRAPPERS:
                continue
            body = dm.group(3)
            if not CALL_RE.search(body) and not DEFINED_RE.search(body):
                continue
            before = len(sites)
            body2 = wrap_queries(body, new_site)
            for q in range(before, len(sites)):
                sites[q]["in_define"] = dm.group(1)
                sites[q]["parent_block"] = stack[-1] if stack else None
            out[start] = "#define %s%s %s" % (dm.group(1), dm.group(2) or "", body2.strip())
            for L in range(start + 1, end + 1):
                out[L] = ""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out[1:]))


def instrument():
    ex = json.load(open(os.path.join(common.WORK, "extract.json")))
    opened = sorted({f for _c, f, _rs in ex["opened"] if f.startswith("/")})
    if os.path.exists(INST):
        shutil.rmtree(INST)
    for src, name in TREES:
        shutil.copytree(src, os.path.join(INST, name), symlinks=True)
    sites = []
    files = []
    for fid, path in enumerate(opened):
        real = os.path.realpath(path)
        for src, name in TREES:
            if real.startswith(src + "/"):
                dest = os.path.join(INST, name, real[len(src) + 1:])
                break
        else:
            continue
        if os.path.islink(dest):
            os.unlink(dest)
        instrument_file(real, dest, fid, sites)
        files.append(path)
    json.dump({"files": files, "sites": sites}, open(os.path.join(common.WORK, "probe-sites.json"), "w"))
    print("files", len(files), "sites", len(sites),
          "cond", sum(1 for s in sites if s["kind"] == "cond"),
          "query", sum(1 for s in sites if s["kind"] == "query"),
          "unsafe", sum(1 for s in sites if s.get("unsafe")))


def one_run(job):
    cfg, n, root, extra = job
    rc, out, err = common.run_gcc(cfg, ["-E", "-dD", "-Wundef", "-Wsystem-headers"] + extra, common.tu_for(root))
    hits = collections.Counter()
    for m in PROBE_RE.finditer(err):
        hits[(m.group(1), int(m.group(2)))] += 1
    return cfg, n, rc, hits, out


def run():
    idx = json.load(open(os.path.join(common.WORK, "pp", "index.json")))
    roots = idx["roots"]
    jobs = [(c, n, roots[n], []) for c in common.CONFIG_NAMES for n in idx["pairs"][c]]
    res = {c: {} for c in common.CONFIG_NAMES}
    same = 0
    diff = []
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for cfg, n, rc, hits, out in ex.map(one_run, jobs):
            res[cfg][n] = {"rc": rc, "hits": [[k, i, c] for (k, i), c in hits.items()]}
            # check: the emitted code equals the uninstrumented run's
            orig = gzip.open(os.path.join(common.WORK, "pp", cfg, "%d.i.gz" % n), "rt").read()
            a = [r for r in common.parse_i(orig) if r[0] in ("code", "pragma")]
            b = [r for r in common.parse_i(out) if r[0] in ("code", "pragma")]
            if a == b:
                same += 1
            else:
                diff.append([cfg, n])
    json.dump({"pairs": res, "code_identical": same, "code_differs": diff},
              open(os.path.join(common.WORK, "probe-hits.json"), "w"))
    print("runs", len(jobs), "emitted code identical to uninstrumented", same, "differs", len(diff))


def records(out):
    return collections.Counter((r[0], common.short(r[1]), r[2], r[3]) for r in common.parse_i(out)
                               if r[0] in ("code", "define", "undef", "pragma") and r[1] not in ("<built-in>", "<command-line>"))


def flips():
    sites = json.load(open(os.path.join(common.WORK, "probe-sites.json")))["sites"]
    hits = json.load(open(os.path.join(common.WORK, "probe-hits.json")))["pairs"]
    idx = json.load(open(os.path.join(common.WORK, "pp", "index.json")))
    roots = idx["roots"]
    size = {}
    evaluated = collections.defaultdict(list)  # (k, cfg) -> roots
    for cfg, pairs in hits.items():
        for n, rec in pairs.items():
            for kind, k, c in rec["hits"]:
                if kind in ("qt", "qf"):
                    evaluated[(k, cfg)].append(int(n))
    for cfg in common.CONFIG_NAMES:
        for n in idx["pairs"][cfg]:
            size[(cfg, n)] = os.path.getsize(os.path.join(common.WORK, "pp", cfg, "%d.i.gz" % n))
    jobs = []
    for (k, cfg), rs in evaluated.items():
        rs = sorted(set(rs), key=lambda n: size[(cfg, n)])[:3]
        for n in rs:
            jobs.append((k, cfg, n))
    base = {}
    need = sorted({(cfg, n) for _k, cfg, n in jobs})

    def do_base(p):
        cfg, n = p
        _, _, rc, _, out = one_run((cfg, n, roots[n], []))
        return p, records(out)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for p, rec in ex.map(do_base, need):
            base[p] = rec

    def do_flip(job):
        k, cfg, n = job
        _, _, rc, _, out = one_run((cfg, n, roots[n], ["-D__forge_flip_%d=1" % k]))
        rec = records(out)
        b = base[(cfg, n)]
        added = rec - b
        removed = b - rec
        return k, cfg, n, rc, added, removed

    res = []
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for k, cfg, n, rc, added, removed in ex.map(do_flip, jobs):
            def summ(cnt):
                toks = []
                lines = []
                for (kind, f, line, text), c in cnt.items():
                    lines.append([kind, f, line, text[:160]])
                    if kind == "define":
                        _nm, _p, body = common.split_define(text)
                        toks.extend(common.tokenize(body))
                    else:
                        toks.extend(common.tokenize(text))
                names = sorted({nm for _i, nm, _k, _f in common.detect(toks)} |
                               {"id:" + v for kk, v in toks if kk == "id" and v.startswith("__builtin")})
                lines.sort()
                return {"n": sum(cnt.values()), "names": names, "sample": lines[:12]}
            res.append({"site": k, "cfg": cfg, "root": roots[n], "rc": rc,
                        "added": summ(added), "removed": summ(removed)})
    json.dump(res, open(os.path.join(common.WORK, "probe-flips.json"), "w"))
    print("flip runs", len(res), "changed", sum(1 for r in res if r["added"]["n"] or r["removed"]["n"]))


if __name__ == "__main__":
    {"instrument": instrument, "run": run, "flips": flips}[sys.argv[1]]()
