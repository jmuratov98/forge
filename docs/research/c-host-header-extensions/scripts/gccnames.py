#!/usr/bin/env python3
"""Ask gcc-15 itself what each reserved identifier in the headers is.

usage: python3 -I gccnames.py      (after pp.py and gccsrc.sh)

1. Scans every WORK/pp/<cfg>/*.i.gz and collects (a) identifiers that start
   with '_' or are spelled like a GCC reserved word, from emitted code and
   from #define bodies, and (b) every attribute name used inside
   __attribute__((...)) or [[...]].
2. Parses c_common_reswords (gcc/c-family/c-common.cc) and applies the C
   parser's keyword mask (gcc/c/c-parser.cc c_parse_init) per dialect.
3. For each configuration, in a translation unit with no headers:
   - `#if __has_builtin (X)` for every identifier;
   - `int X;` for every identifier (any diagnostic means GCC predeclares or
     reserves X); flagged ones are re-run one per TU, with
     `typedef X t;` to tell types from functions and keywords;
   - `#if __has_attribute (X)` / `__has_c_attribute (X)` for attribute names.
   Predefined macros of the configuration are excluded from the identifier
   tests and listed as such.
Writes WORK/gccnames.json.
"""
import gzip
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SRC = os.path.join(common.WORK, "gccsrc", "src")


def reswords():
    text = open(os.path.join(SRC, "gcc/c-family/c-common.cc")).read()
    start = text.index("const struct c_common_resword c_common_reswords[] =")
    end = text.index("};", start)
    flags_h = open(os.path.join(SRC, "gcc/c-family/c-common.h")).read()
    fl = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"#define (D_\w+)\s+0x([0-9a-fA-F]+)", flags_h)}
    rows = []
    base_line = text[:start].count("\n") + 1
    for m in re.finditer(r'\{\s*"([^"]+)",\s*(RID_\w+),\s*([^}]*?)\s*\}', text[start:end]):
        f = m.group(3).strip()
        val = 0
        for part in re.split(r"\s*\|\s*", f):
            part = part.strip()
            if part in ("0", ""):
                continue
            val |= fl.get(part, 0)
        line = base_line + text[start:start + m.start()].count("\n")
        rows.append({"name": m.group(1), "rid": m.group(2), "flags": f, "mask": val, "line": line})
    return rows, fl


def keyword_mask(fl, isoc99, isoc23, no_asm=False):
    # gcc/c/c-parser.cc c_parse_init
    mask = fl["D_CXXONLY"]
    if not isoc99:
        mask |= fl["D_C99"]
    if not isoc23:
        mask |= fl["D_C23"]
    if no_asm:
        mask |= fl["D_ASM"] | fl["D_EXT"]
        if not isoc99:
            mask |= fl["D_EXT89"]
        if not isoc23:
            mask |= fl["D_EXT11"]
    mask |= fl["D_OBJC"] | fl["D_CXX_OBJC"]
    return mask


DIALECT = {"gnu89": (False, False), "gnu99": (True, False), "gnu17": (True, False), "gnu23": (True, True)}


def scan_one(job):
    path, kwnames = job
    text = gzip.open(path, "rt").read()
    ids, attrs, stdattrs = set(), set(), set()
    toks = []
    for kind, f, line, payload in common.parse_i(text):
        if kind == "code":
            toks.extend(common.tokenize(payload))
        elif kind == "define" and f not in ("<built-in>", "<command-line>"):
            name, params, body = common.split_define(payload)
            bt = common.tokenize(body)
            for k, v in bt:
                if k == "id" and (v.startswith("_") or v in kwnames):
                    ids.add(v)
            for _, nm, key, _form in common.detect(bt):
                if nm.startswith("attr:"):
                    attrs.add(key[0])
                elif nm.startswith("stdattr:"):
                    stdattrs.add(nm[8:])
    for k, v in toks:
        if k == "id" and (v.startswith("_") or v in kwnames):
            ids.add(v)
    for _, nm, key, _form in common.detect(toks):
        if nm.startswith("attr:"):
            attrs.add(key[0])
        elif nm.startswith("stdattr:"):
            stdattrs.add(nm[8:])
    return ids, attrs, stdattrs


def predefined(cfg):
    rc, out, _ = common.run_gcc(cfg, ["-E", "-dM"], "")
    return {m.group(1) for m in re.finditer(r"^#define (\w+)", out, re.M)}


DIAG_LINE = re.compile(r"^<stdin>:(\d+):\d+: (warning|error|pedwarn): (.*)$")


def classify(cfg, names, attrs, stdattrs):
    pre = predefined(cfg)
    test = [x for x in names if x not in pre]
    res = {x: {"macro": True} for x in names if x in pre}
    # __has_builtin
    src = "".join("#if __has_builtin (%s)\nforge_hb_%d\n#endif\n" % (x, i) for i, x in enumerate(test))
    _, out, err = common.run_gcc(cfg, ["-E", "-P"], src)
    hb = {int(m.group(1)) for m in re.finditer(r"forge_hb_(\d+)", out)}
    # int X; screen
    src = "".join("int %s;\n" % x for x in test)
    _, _, err = common.run_gcc(cfg, ["-fsyntax-only", "-fmax-errors=0", "-fno-diagnostics-show-caret",
                                     "-fdiagnostics-color=never", "-w" if False else "-Wall"], src)
    flagged = set()
    for ln in err.splitlines():
        m = DIAG_LINE.match(ln)
        if m:
            flagged.add(int(m.group(1)) - 1)
    for i, x in enumerate(test):
        res[x] = {"macro": False, "hb": i in hb, "screen": i in flagged}

    def single(x):
        _, _, e1 = common.run_gcc(cfg, ["-fsyntax-only", "-fno-diagnostics-show-caret",
                                        "-fdiagnostics-color=never"], "int %s;\n" % x)
        _, _, e2 = common.run_gcc(cfg, ["-fsyntax-only", "-fno-diagnostics-show-caret",
                                        "-fdiagnostics-color=never"], "typedef %s forge_t;\n" % x)
        d1 = [DIAG_LINE.match(ln).group(3) for ln in e1.splitlines() if DIAG_LINE.match(ln)]
        d2 = [DIAG_LINE.match(ln) for ln in e2.splitlines() if DIAG_LINE.match(ln)]
        return x, d1, not any(m.group(2) == "error" for m in d2), [m.group(3) for m in d2]

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for x, d1, tok, d2 in ex.map(single, [x for i, x in enumerate(test) if i in flagged or i in hb]):
            res[x].update({"int_diag": d1, "typedef_ok": tok, "typedef_diag": d2})
    # attributes
    av = {}
    for op, group in (("__has_attribute", sorted(attrs)), ("__has_c_attribute", sorted(stdattrs))):
        for x in group:
            vals = []
            for probe in ("(%s(%s)) == 0", "(%s(%s)) == 1", "(%s(%s)) > 1"):
                src = "#if %s\nforge_yes\n#endif\n" % (probe % (op, x))
                _, out, err = common.run_gcc(cfg, ["-E", "-P"], src)
                vals.append("forge_yes" in out)
            val = 0 if vals[0] else 1 if vals[1] else ">1" if vals[2] else "?"
            if val == ">1":
                lo, hi = 2, 1 << 31
                while lo < hi:
                    mid = (lo + hi) // 2
                    src = "#if (%s(%s)) > %d\nforge_yes\n#endif\n" % (op, x, mid)
                    _, out, _ = common.run_gcc(cfg, ["-E", "-P"], src)
                    if "forge_yes" in out:
                        lo = mid + 1
                    else:
                        hi = mid
                val = lo
            av["%s(%s)" % (op, x)] = val
    return cfg, res, av, sorted(pre)


def main():
    rows, fl = reswords()
    kwnames = {r["name"] for r in rows}
    idx = json.load(open(os.path.join(common.WORK, "pp", "index.json")))
    jobs = []
    for c in common.CONFIG_NAMES:
        for n in idx["pairs"][c]:
            jobs.append((os.path.join(common.WORK, "pp", c, "%d.i.gz" % n), kwnames))
    ids, attrs, stdattrs = set(), set(), set()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for a, b, s in ex.map(scan_one, jobs, chunksize=8):
            ids |= a
            attrs |= b
            stdattrs |= s
    print("identifiers", len(ids), "attribute spellings", len(attrs), "std attrs", len(stdattrs))
    names = sorted(ids)
    out = {"reswords": rows, "flags": fl, "identifiers": names, "attribute_spellings": sorted(attrs),
           "std_attributes": sorted(stdattrs), "keywords": {}, "per_config": {}, "attr_values": {},
           "predefined": {}}
    for d, (c99, c23) in DIALECT.items():
        mask = keyword_mask(fl, c99, c23)
        out["keywords"][d] = sorted(r["name"] for r in rows if not (r["mask"] & mask))
    for c in common.CONFIG_NAMES:
        cfg, res, av, pre = classify(c, names, attrs, stdattrs)
        out["per_config"][cfg] = res
        out["attr_values"][cfg] = av
        out["predefined"][cfg] = pre
        print(cfg, "hb", sum(1 for r in res.values() if r.get("hb")),
              "screened", sum(1 for r in res.values() if r.get("screen")))
    json.dump(out, open(os.path.join(common.WORK, "gccnames.json"), "w"), indent=0, sort_keys=True)


if __name__ == "__main__":
    main()
