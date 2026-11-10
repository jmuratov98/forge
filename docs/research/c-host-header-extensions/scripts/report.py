#!/usr/bin/env python3
"""Build the inventory, the appendix and the report's tables.

usage: python3 -I report.py WORK_COPY HX9_INVENTORY DOC_DIR

WORK_COPY: copies of the VM's accept.json, pedantic-noext.json, gccnames.json,
extract.json, extract-pp-fob.json, probe-sites.json, probe-hits.json,
probe-flips.json, vmscan.json. HX9_INVENTORY: issue #9's generated appendix
(`git show origin/research/host-header-extensions:docs/research/host-header-extensions/inventory.md`).
DOC_DIR: docs/research. Writes
  DOC_DIR/c-host-header-extensions/data/{inventory,asm-labels,opened-headers,predefined-macros}.tsv
  DOC_DIR/c-host-header-extensions/inventory.md          (generated appendix)
  DOC_DIR/c-host-header-extensions.md                     (main.md with tables filled in)
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classes  # noqa: E402

C = ["gnu89", "gnu89+gs", "gnu99", "gnu99+gs", "gnu17", "gnu17+gs", "gnu23", "gnu23+gs"]
DIALECTS = ["gnu89", "gnu99", "gnu17", "gnu23"]
GCC_INC = "/usr/lib/gcc/aarch64-linux-gnu/15/include/"


def short(p):
    for pre, rep in ((GCC_INC, "gcc/"), ("/usr/include/aarch64-linux-gnu/", "aarch64/"), ("/usr/include/", "")):
        if p.startswith(pre):
            return rep + p[len(pre):]
    return p


def cfgset(cs):
    """Compact description of a set of configurations."""
    cs = set(cs)
    if not cs:
        return "none"
    if cs == set(C):
        return "all 8"
    if cs == {d + "+gs" for d in DIALECTS}:
        return "+gs only (all dialects)"
    if cs == set(DIALECTS):
        return "without _GNU_SOURCE only"
    parts = []
    for d in DIALECTS:
        a, b = d in cs, d + "+gs" in cs
        if a and b:
            parts.append(d)
        elif a:
            parts.append(d + " (no gs)")
        elif b:
            parts.append(d + "+gs")
    return ", ".join(parts)


# ------------------------------------------------------------------ #9 data

def parse_hx9(path):
    t = open(path).read()
    out = {}
    for sec in re.split(r"(?m)^### ", t):
        if not sec.startswith("F.") or sec.startswith("F.17"):
            continue
        rows = [l for l in sec.split("\n") if l.startswith("|")]
        hdr = [c.strip() for c in rows[0].strip("|").split("|")]
        ci, ri, ki = hdr.index("Class"), hdr.index("Reached"), hdr.index("Kind")
        for l in rows[2:]:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", l.strip()[1:-1])]
            m = re.match(r"^`([^`]+)`$", cells[0])
            if not m:
                continue
            name = m.group(1)
            bm = re.match(r"^(.*)\{([^}]*)\}$", name)
            names = [bm.group(1) + s for s in bm.group(2).split(",")] if bm else [name]
            for nm in names:
                out[nm] = {"class": cells[ci], "reached": cells[ri].replace("&lt;", "<").replace("&gt;", ">"),
                           "kind": cells[ki], "section": sec.split("\n")[0]}
    return out


def hx9_reached_m1(rec):
    r = rec["reached"]
    return r.startswith("M1 (") or r.startswith("M1 (via") or r == "M1 macro only" or r.startswith("M1 macro")


# ------------------------------------------------------------------ names

def display(nm, gk):
    kind, _, rest = nm.partition(":")
    if kind == "id":
        return rest
    if kind == "attr":
        return rest
    if kind == "pragma":
        return "#pragma " + rest if not rest.startswith("(") else "_Pragma " + rest
    if kind == "asm":
        return {"label": "asm label (symbol rename)"}.get(rest, "inline asm " + rest)
    if kind == "syntax":
        return {"statement expression": "statement expression ({ ... })",
                "imaginary constant": "imaginary constant suffix"}.get(rest, rest)
    if kind == "directive":
        return rest
    return nm


def main():
    W, hx9p, doc = sys.argv[1], sys.argv[2], sys.argv[3]
    out_dir = os.path.join(doc, "c-host-header-extensions")
    data_dir = os.path.join(out_dir, "data")
    hx9 = parse_hx9(hx9p)
    # #9 rows outside its F tables (F.17 lists asm per occurrence; G.1 classes them M)
    hx9.setdefault("asm label (symbol rename)", {"class": "M", "reached": "M1 (G.1)", "kind": "asm", "section": "G.1"})
    hx9.setdefault("inline asm (basic)", {"class": "M", "reached": "M1 (G.1)", "kind": "asm", "section": "G.1"})
    ex = json.load(open(os.path.join(W, "extract.json")))
    gn = json.load(open(os.path.join(W, "gccnames.json")))
    vs = json.load(open(os.path.join(W, "vmscan.json")))
    owners = vs["owners"]
    roots = ex["roots"]
    reswords = {r["name"]: r for r in gn["reswords"]}

    def owner(f):
        if f in ("?", "<built-in>"):
            return "?"
        return owners.get(os.path.realpath(f) if f.startswith("/") else f, owners.get(f, "?"))

    # ---- aggregate occurrences
    names = {}
    for c, nm, md, site, rs in ex["occ"]:
        if nm.startswith("predef:"):
            continue
        r = names.setdefault(nm, {"modes": collections.defaultdict(lambda: collections.defaultdict(set)),
                                  "sites": collections.defaultdict(lambda: collections.defaultdict(set))})
        r["modes"][md][c].update(rs)
        r["sites"][md][tuple(site)].update(rs)
    # directives from the scan: #warning
    for d in vs["directives"]:
        if d["directive"] == "warning" and d["entered"]:
            r = names.setdefault("directive:#warning", {"modes": collections.defaultdict(lambda: collections.defaultdict(set)),
                                                        "sites": collections.defaultdict(lambda: collections.defaultdict(set))})
            for c, k in d["entered"].items():
                r["modes"]["code"][c].update({-1 - i for i in range(k)})
            r["sites"]["code"][(d["file"], d["line"])].update({-1})
    forms = collections.defaultdict(collections.Counter)
    for nm, fm, cnt in ex["forms"]:
        forms[nm][fm] += cnt

    pc = gn["per_config"]
    rows = []
    for nm, r in names.items():
        kind, _, base = nm.partition(":")
        disp = display(nm, None)
        # drop plain identifiers that are not extensions
        if kind == "id":
            if base in classes.DROP_IDS:
                continue
            g = pc["gnu23"].get(base) or pc["gnu17"].get(base) or {}
            if g.get("macro") or base in ("__FILE__", "__LINE__"):
                continue
        reached = {c: set() for c in C}
        code = {c: set() for c in C}
        via = {c: set() for c in C}
        macro = {c: set() for c in C}
        for md, per in r["modes"].items():
            for c, rs in per.items():
                if md == "code" or md == "define":
                    code[c] |= rs
                elif md == "via":
                    via[c] |= rs
                elif md == "macro":
                    macro[c] |= rs
        for c in C:
            reached[c] = code[c] | via[c]
        status = {}
        for c in C:
            if code[c]:
                status[c] = "code"
            elif via[c]:
                status[c] = "via"
            elif macro[c]:
                status[c] = "macro"
        # origins
        orig_reached, orig_macro = set(), set()
        for md, sites in r["sites"].items():
            for site in sites:
                if md in ("code", "define"):
                    orig_reached.add(owner(site[0]))
                elif md == "via":
                    orig_reached.add(owner(site[3]) if len(site) > 3 else "?")
                elif md == "macro":
                    orig_macro.add(owner(site[0]))
        # representative site
        rep = ""
        for md in ("code", "define", "via", "macro"):
            if md in r["sites"] and r["sites"][md]:
                site, rs = max(r["sites"][md].items(), key=lambda kv: (len(kv[1]), kv[0][0] != "?"))
                if md in ("code", "define"):
                    rep = "%s:%d" % (short(site[0]), site[1])
                elif md == "via":
                    rep = "%s:%d via `%s` (%s:%d)" % (short(site[0]), site[1], site[2], short(site[3]), site[4]) if len(site) > 3 else ""
                else:
                    rep = "%s:%d in `#define %s`" % (short(site[0]), site[1], site[2])
                break
        # GCC kind
        gkind = ""
        if kind == "id":
            g = pc["gnu23"].get(base) or {}
            if base in reswords:
                gkind = "keyword (c_common_reswords %s)" % (reswords[base]["flags"] or "0")
            elif g.get("hb"):
                gkind = "builtin (__has_builtin = 1)"
            elif g.get("typedef_ok"):
                gkind = "predeclared type"
            else:
                gkind = "preprocessor"
        h = hx9.get(classes.ALIAS.get(disp, disp))
        cls, why, group = classes.classify(nm, disp, h)
        rows.append({
            "name": nm, "display": disp, "group": group, "gkind": gkind,
            "status": status, "code": code, "via": via, "macro": macro, "reached": reached,
            "orig_reached": sorted(orig_reached - {"?"}) or sorted(orig_reached),
            "orig_macro": sorted(orig_macro), "rep": rep,
            "forms": [f for f, _ in forms[nm].most_common(3)],
            "class": cls, "why": why,
            "hx9_class": h["class"] if h else "", "hx9_reached": h["reached"] if h else "",
        })
    rows.extend(pedantic_rows(W, owner))
    missing = [r["display"] for r in rows if r["class"] is None]
    if missing:
        print("UNCLASSIFIED:", missing, file=sys.stderr)
    json.dump([{k: (v if not isinstance(v, dict) or k in ("status",) else {c: sorted(s) for c, s in v.items()})
                for k, v in r.items()} for r in rows],
              open(os.path.join(W, "inventory-rows.json"), "w"))
    print("names", len(rows))
    T = tables(W, rows, hx9, ex, gn, vs)
    os.makedirs(data_dir, exist_ok=True)
    write_tsvs(W, rows, ex, vs, data_dir)
    tmpl_dir = os.path.dirname(os.path.abspath(__file__))
    for src, dst in (("main.md", os.path.join(doc, "c-host-header-extensions.md")),
                     ("appendix.md", os.path.join(out_dir, "inventory.md"))):
        text = open(os.path.join(tmpl_dir, src)).read()
        for k, v in T.items():
            text = text.replace("{{%s}}" % k, v)
        left = re.findall(r"\{\{(\w+)\}\}", text)
        if left:
            print("unfilled in", src, left, file=sys.stderr)
        open(dst, "w").write(text)


# constructs the token scanner does not see, taken from GCC's own pedantic
# diagnostics (the -D__extension__= run): message regex -> inventory name
PEDANTIC_ONLY = [
    (r"does not support .static. or type qualifiers in parameter array declarators",
     "qualifier in parameter array declarator ([__restrict])"),
    (r"forbids variable length array", "variable-length array parameter"),
    (r"restricts enumerator values to range of .int.", "enumerator value outside int"),
]


def pedantic_rows(W, owner):
    ped = json.load(open(os.path.join(W, "pedantic-noext.json")))
    out = []
    for rx, name in PEDANTIC_ONLY:
        code = {c: set() for c in C}
        sites = collections.defaultdict(set)
        for c in C:
            for root, v in ped[c].items():
                for f, line, kind, msg, opt in v["diags"]:
                    if kind != "note" and re.search(rx, msg):
                        code[c].add(root)
                        sites[(f, line)].add(root)
        if not sites:
            continue
        site = max(sites.items(), key=lambda kv: len(kv[1]))[0]
        cls, why, _ = classes.classify("syntax:" + name, name, None)
        empty = {c: set() for c in C}
        out.append({"name": "syntax:" + name, "display": name, "group": "syntax", "gkind": "(GCC pedantic diagnostic)",
                    "status": {c: "code" for c in C if code[c]}, "code": code, "via": empty, "macro": empty,
                    "reached": code, "orig_reached": sorted({owner(f) for f, _l in sites}), "orig_macro": [],
                    "rep": "%s:%d" % (short(site[0]), site[1]), "forms": [], "class": cls, "why": why,
                    "hx9_class": "", "hx9_reached": ""})
    return out


# ------------------------------------------------------------------ output

def md(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in body:
        out.append("| " + " | ".join(str(x).replace("|", "\\|") for x in r) + " |")
    return "\n".join(out)


def rstatus(r):
    """Overall status: reached (code/via) in some configuration, else macro only."""
    if any(r["reached"][c] for c in C):
        return "reached"
    return "macro only"


def origin_label(r):
    o = r["orig_reached"] if rstatus(r) == "reached" else r["orig_macro"]
    o = [x for x in o if x in ("glibc", "kernel", "gcc")]
    return "+".join(o) if o else "?"


def hs(r):
    """Header-side origin, ignoring GCC's own headers."""
    o = r["orig_reached"] if rstatus(r) == "reached" else r["orig_macro"]
    return [x for x in o if x in ("glibc", "kernel")]


def reach_desc(r):
    rc = {c for c in C if r["reached"][c]}
    mc = {c for c in C if r["macro"][c] and not r["reached"][c]}
    mx = max(len(r["reached"][c]) for c in C)
    parts = []
    if rc:
        how = "code" if any(r["code"][c] for c in C) else "via macro"
        if any(r["code"][c] for c in C) and any(r["via"][c] for c in C):
            how = "code, via macro"
        parts.append("%s: %s (max %d roots)" % (how, cfgset(rc), mx))
    if mc:
        parts.append("macro only: %s" % cfgset(mc))
    return "; ".join(parts)


def tables(W, rows, hx9, ex, gn, vs):
    T = {}
    acc = json.load(open(os.path.join(W, "accept.json")))
    # accepted set
    body = []
    for c in C:
        ok = sum(1 for v in acc[c].values() if v["ok"])
        fails = sorted(r for r, v in acc[c].items() if not v["ok"])
        body.append([c, len(acc[c]), ok, ", ".join("`<%s>`" % f for f in fails)])
    T["accept_table"] = md(["Configuration", "Roots", "Accepted", "Rejected"], body)
    fe = {}
    for c in C:
        for r, v in acc[c].items():
            if not v["ok"]:
                f = v["first_error"]
                fe[r] = "%s:%d: %s" % (short(f[0]), f[1], f[3])
    T["reject_list"] = "\n".join("- `<%s>`: %s" % (r, e) for r, e in sorted(fe.items()))
    # opened headers
    opened = collections.defaultdict(lambda: collections.defaultdict(set))
    for c, f, rs in ex["opened"]:
        if f.startswith("/"):
            opened[vs["owners"].get(os.path.realpath(f), "?")][c].add(os.path.realpath(f))
    body = []
    for o in ("glibc", "kernel", "gcc"):
        allf = set().union(*opened[o].values()) if opened[o] else set()
        body.append([o, len(allf)] + [len(opened[o][c]) for c in C])
    T["opened_table"] = md(["Package", "Opened (any configuration)"] + C, body)

    # counts per group and class
    groups = ["builtin", "attribute", "keyword", "pragma", "asm", "syntax"]
    gname = {"builtin": "Builtins", "attribute": "Attributes", "keyword": "Keywords and types",
             "pragma": "Pragmas", "asm": "asm labels", "syntax": "Syntax and directives"}
    body = []
    tot = collections.Counter()
    for g in groups:
        rs = [r for r in rows if r["group"] == g]
        reached = [r for r in rs if rstatus(r) == "reached"]
        mo = [r for r in rs if rstatus(r) == "macro only"]
        cl = collections.Counter(r["class"] for r in rs)
        gonly = [r for r in rs if not hs(r)]
        row = [gname[g], len(rs), len(reached), len(mo), cl["M"], cl["L"], cl["A"],
               sum(1 for r in rs if "glibc" in hs(r)), sum(1 for r in rs if "kernel" in hs(r)), len(gonly)]
        for i, k in enumerate(["n", "reached", "mo", "M", "L", "A", "glibc", "kernel", "gcc"]):
            tot[k] += row[i + 1]
        body.append(row)
    body.append(["**Total**"] + ["**%d**" % tot[k] for k in ["n", "reached", "mo", "M", "L", "A", "glibc", "kernel", "gcc"]])
    T["counts_table"] = md(["Group", "Names", "Reached by header code", "Macro only", "M", "L", "A",
                            "glibc", "kernel UAPI", "only GCC's own headers"], body)
    T["n_names"] = str(tot["n"])
    T["n_M"], T["n_L"], T["n_A"] = str(tot["M"]), str(tot["L"]), str(tot["A"])
    T["n_reached"], T["n_macro"] = str(tot["reached"]), str(tot["mo"])
    T["n_gcconly"] = str(tot["gcc"])
    # class x reach for header-side names only
    hrows = [r for r in rows if hs(r)]
    body = []
    for st in ("reached", "macro only"):
        rs = [r for r in hrows if rstatus(r) == st]
        cl = collections.Counter(r["class"] for r in rs)
        body.append([st, len(rs), cl["M"], cl["L"], cl["A"]])
    T["hs_table"] = md(["Status (glibc or kernel origin)", "Names", "M", "L", "A"], body)
    # per configuration
    body = []
    for c in C:
        rr = [r for r in rows if r["reached"][c]]
        mo = [r for r in rows if r["macro"][c] and not r["reached"][c]]
        cl = collections.Counter(r["class"] for r in rr)
        body.append([c, len(rr), "%d / %d / %d" % (cl["M"], cl["L"], cl["A"]), len(mo)])
    T["per_config_table"] = md(["Configuration", "Names reached by header code", "of which M / L / A",
                                "Macro only"], body)
    # names whose reach depends on the configuration
    body = []
    for r in sorted(rows, key=lambda r: (r["group"], r["display"])):
        rc = {c for c in C if r["reached"][c]}
        mc = {c for c in C if r["macro"][c]}
        if (rc and rc != set(C)) or (not rc and mc != set(C)):
            body.append(["`%s`" % r["display"], r["class"], cfgset(rc) if rc else "-",
                         cfgset(mc - rc) if (mc - rc) else "-", origin_label(r)])
    T["config_dep_table"] = md(["Name", "Class", "Reached by header code in", "Macro only in", "Origin"], body)
    # every-configuration list
    allc = [r for r in rows if {c for c in C if r["reached"][c]} == set(C)]
    T["all_config_list"] = ", ".join("`%s`" % r["display"] for r in sorted(allc, key=lambda r: (r["group"], r["display"])))
    T["n_all_config"] = str(len(allc))

    # delta against #9
    new, dropped, changes = [], [], []
    disp_set = {classes.ALIAS.get(r["display"], r["display"]) for r in rows}
    for r in sorted(rows, key=lambda r: (r["group"], r["display"])):
        h = hx9.get(classes.ALIAS.get(r["display"], r["display"]))
        if not h:
            new.append([r, "not in #9"])
        elif not hx9_reached_m1(h):
            new.append([r, "#9: %s" % h["reached"]])
        if h and h["class"] in "MLA" and h["class"] != r["class"]:
            changes.append(["`%s`" % r["display"], h["class"], r["class"], r["why"]])
    T["delta_new_table"] = md(["Name", "Class", "C mode", "Origin", "#9 status"],
                              [["`%s`" % r["display"], r["class"], reach_desc(r), origin_label(r), w] for r, w in new])
    T["n_new"] = str(len(new))
    T["n_new_M"] = str(sum(1 for r, w in new if r["class"] == "M"))
    T["new_M_list"] = ", ".join("`%s`" % r["display"] for r, w in new if r["class"] == "M")
    T["class_change_table"] = md(["Name", "#9 class", "C-mode class", "Reason"], changes)
    for nm, h in sorted(hx9.items()):
        if hx9_reached_m1(h) and nm not in disp_set:
            dropped.append((h["section"].split(" ", 1)[1] if " " in h["section"] else h["section"], nm, h["class"]))
    by = collections.defaultdict(list)
    for sec, nm, cl in dropped:
        by[sec].append("`%s` (%s)" % (nm, cl))
    T["delta_dropped_full"] = "\n".join("- **%s** (%d): %s" % (sec, len(v), ", ".join(v)) for sec, v in sorted(by.items()))
    T["delta_dropped_list"] = "\n".join("- **%s** (%d): %s%s" % (sec, len(v), ", ".join(v[:8]),
                                                                 ", ... (appendix C)" if len(v) > 8 else "")
                                        for sec, v in sorted(by.items()))
    T["n_dropped"] = str(len(dropped))

    # asm labels
    asm = collections.defaultdict(lambda: collections.defaultdict(set))
    sites = collections.defaultdict(set)
    for c, decl, label, mode, f, line, macro, rs in ex["asm"]:
        asm[c][(decl, label)].update(rs)
        sites[(decl, label)].add("%s:%d" % (short(f), line))
    fob = json.load(open(os.path.join(W, "extract-pp-fob.json")))
    asm_fob = collections.defaultdict(set)
    for c, decl, label, mode, f, line, macro, rs in fob["asm"]:
        asm_fob[c].add((decl, label))

    def fam(decl, label):
        if label.startswith("__isoc23_"):
            return "`__isoc23_*` (C23 strto*/wcsto*/scanf)"
        if label.startswith("__isoc99_"):
            return "`__isoc99_*` (C99 scanf family)"
        if label.endswith("64") or "64_" in label or "64v2" in label:
            return "LFS `*64`"
        return "other"
    body = []
    for c in C:
        cnt = collections.Counter(fam(*k) for k in asm[c])
        body.append([c, len(asm[c]), cnt["`__isoc23_*` (C23 strto*/wcsto*/scanf)"],
                     cnt["`__isoc99_*` (C99 scanf family)"], cnt["other"],
                     len(asm_fob[c] - set(asm[c]))])
    T["asm_table"] = md(["Configuration", "Distinct renames", "`__isoc23_*`", "`__isoc99_*`", "Other",
                         "Added by `-D_FILE_OFFSET_BITS=64 -D_TIME_BITS=64`"], body)
    other = sorted({k for c in C for k in asm[c] if fam(*k) == "other"})
    T["asm_other_table"] = md(["Declared name", "asm label", "Configurations", "Site"],
                              [["`%s`" % d, "`%s`" % l, cfgset({c for c in C if (d, l) in asm[c]}),
                                ", ".join(sorted(sites[(d, l)]))] for d, l in other])
    iso = sorted({k for c in C for k in asm[c] if fam(*k) != "other"}, key=lambda k: (k[1], k[0]))
    T["asm_iso_table"] = md(["Declared name", "asm label", "Configurations", "Site"],
                            [["`%s`" % d, "`%s`" % l, cfgset({c for c in C if (d, l) in asm[c]}),
                              ", ".join(sorted(sites[(d, l)]))] for d, l in iso])
    lfs = sorted({k for c in C for k in asm_fob[c]} - {k for c in C for k in asm[c]})
    T["n_lfs"] = str(len(lfs))
    T["lfs_list"] = ", ".join("`%s`→`%s`" % k for k in lfs)

    # queries
    qrows, prereq = query_tables(W)
    T["query_table"] = qrows
    T["prereq_table"] = prereq
    # pedantic
    T["pedantic_table"] = pedantic_table(W)
    # predefined macros expanded
    pm = collections.defaultdict(set)
    for c, nm, md_, site, rs in ex["occ"]:
        if nm.startswith("predef:"):
            pm[nm[7:]].add(c)
    T["predef_list"] = ", ".join("`%s`%s" % (m, "" if cs == set(C) else " (%s)" % cfgset(cs)) for m, cs in sorted(pm.items()))
    T["n_predef"] = str(len(pm))
    # appendix
    T["appendix_tables"] = appendix(rows)
    return T


def query_tables(W):
    sites = json.load(open(os.path.join(W, "probe-sites.json")))["sites"]
    hits = json.load(open(os.path.join(W, "probe-hits.json")))["pairs"]
    flips = json.load(open(os.path.join(W, "probe-flips.json")))
    ev = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for c, pairs in hits.items():
        for n, rec in pairs.items():
            for kind, k, cnt in rec["hits"]:
                ev[k][c][kind] += 1
    fl = collections.defaultdict(list)
    for r in flips:
        fl[r["site"]].append(r)
    body, pre = [], collections.defaultdict(lambda: [0, 0, 0, set()])
    for s in sites:
        if s["kind"] != "query":
            continue
        e = ev[s["id"]]
        evc = {c for c in C if e[c]["qt"] or e[c]["qf"]}
        d = s["directive"]
        status = "evaluated" if evc else ("short-circuited" if d is not None and any(
            ev[d][c]["dt"] or ev[d][c]["df"] for c in C) else "not evaluated")
        rs = fl.get(s["id"], [])
        ch = [r for r in rs if r["added"]["n"] or r["removed"]["n"]]
        rem = sorted({n for r in rs for n in r["removed"]["names"]})
        add = sorted({n for r in rs for n in r["added"]["names"]})
        if s["op"] in ("__GNUC_PREREQ", "__glibc_clang_prereq"):
            key = (s["op"], s["text"].split("(", 1)[1].replace(" ", "").rstrip(")"))
            p = pre[key]
            p[0] += 1
            p[1] += status == "evaluated"
            p[2] += bool(ch)
            p[3].update(rem)
            continue
        if status != "evaluated":
            continue
        vals = set()
        for c in evc:
            vals |= {"1"} if e[c]["qt"] else set()
            vals |= {"0"} if e[c]["qf"] else set()
        maxroots = max(e[c]["qt"] + e[c]["qf"] for c in evc)
        eff = "no change" if not ch else "%s%s" % (
            ("loses " + ", ".join("`%s`" % display(x, None) for x in rem)) if rem else "no listed construct lost",
            ("; gains " + ", ".join("`%s`" % display(x, None) for x in add)) if add else "")
        mx = max([r["added"]["n"] + r["removed"]["n"] for r in rs] or [0])
        body.append(["%s:%d" % (short(s["file"]), s["line"]), "`%s`" % s["text"], "/".join(sorted(vals)),
                     cfgset(evc), maxroots, "%d lines; %s" % (mx, eff.strip()) if ch else "no change"])
    qt = md(["Site", "Query", "GCC 15.2 answer", "Evaluated in", "Roots (max)",
             "If answered the other way (flip run)"], body)
    pb = []
    for (op, th), (n, ne, nc, rem) in sorted(pre.items(), key=lambda kv: (kv[0][0], [int(x) for x in kv[0][1].split(",")])):
        pb.append(["`%s (%s)`" % (op, th), n, ne, nc, ", ".join(sorted("`%s`" % display(x, None) for x in rem)) or "-"])
    pt = md(["Test", "Sites in opened headers", "Evaluated", "Flip changes output", "Constructs lost when flipped"], pb)
    return qt, pt


def pedantic_table(W):
    ped = json.load(open(os.path.join(W, "pedantic-noext.json")))
    agg = collections.defaultdict(lambda: [collections.defaultdict(set), set()])
    for c in C:
        for r, v in ped[c].items():
            for f, line, kind, msg, opt in v["diags"]:
                if kind == "note":
                    continue
                m = re.sub(r"‘[^’]*’", "‘X’", msg) if re.search(r"zero-size|redefined|variable length", msg) else msg
                a = agg[(m, opt)]
                a[0][c].add(r)
                a[1].add("%s:%d" % (short(f), line))
    body = []
    for (m, opt), (cs, ss) in sorted(agg.items(), key=lambda kv: -len(kv[1][1])):
        body.append([m, opt or "-", cfgset(set(cs)), max(len(x) for x in cs.values()), len(ss),
                     ", ".join(sorted(ss)[:3]) + (" ..." if len(ss) > 3 else "")])
    return md(["GCC diagnostic", "Option", "Configurations", "Roots (max)", "Sites", "Example sites"], body)


def appendix(rows):
    out = []
    gname = {"builtin": "Builtins", "attribute": "Attributes", "keyword": "Keywords and types",
             "pragma": "Pragmas", "asm": "asm", "syntax": "Syntax and directives"}
    for i, g in enumerate(["builtin", "attribute", "keyword", "pragma", "asm", "syntax"]):
        rs = sorted([r for r in rows if r["group"] == g], key=lambda r: r["display"])
        out.append("### A.%d %s (%d)\n" % (i + 1, gname[g], len(rs)))
        body = []
        for r in rs:
            per = " ".join("%s:%s" % (c.replace("gnu", "").replace("+gs", "g"),
                                      len(r["reached"][c]) if r["reached"][c] else ("m" if r["macro"][c] else "-"))
                           for c in C)
            body.append(["`%s`" % r["display"], r["class"], r["hx9_class"] or "-", origin_label(r),
                         reach_desc(r), per, r["rep"], "; ".join("`%s`" % f for f in r["forms"][:2]) or "-",
                         r["gkind"] or "-", r["why"]])
        out.append(md(["Name", "Class", "#9 class", "Origin", "Reach", "Roots per configuration",
                       "Representative site", "Forms", "GCC kind", "Class reason"], body))
        out.append("")
    return "\n".join(out)


def write_tsvs(W, rows, ex, vs, data_dir):
    with open(os.path.join(data_dir, "inventory.tsv"), "w") as fh:
        fh.write("name\tgroup\tclass\thx9_class\torigin\t" + "\t".join(C) + "\trepresentative site\tclass reason\n")
        for r in sorted(rows, key=lambda r: (r["group"], r["display"])):
            per = []
            for c in C:
                st = r["status"].get(c, "-")
                n = len(r["reached"][c]) or len(r["macro"][c])
                per.append("%s:%d" % (st, n) if st != "-" else "-")
            fh.write("\t".join([r["display"], r["group"], r["class"] or "?", r["hx9_class"], origin_label(r)] + per
                               + [r["rep"], r["why"]]) + "\n")
    with open(os.path.join(data_dir, "asm-labels.tsv"), "w") as fh:
        fh.write("configuration\tdeclared\tlabel\tmode\tsite\tmacro\troots\n")
        for c, decl, label, mode, f, line, macro, rs in sorted(ex["asm"], key=lambda x: (x[0], x[2], x[1] or "")):
            fh.write("\t".join([c, decl or "?", label, mode, "%s:%d" % (short(f), line), macro, str(len(rs))]) + "\n")
    with open(os.path.join(data_dir, "opened-headers.tsv"), "w") as fh:
        per = collections.defaultdict(dict)
        for c, f, rs in ex["opened"]:
            per[f][c] = len(rs)
        fh.write("header\tpackage\t" + "\t".join(C) + "\n")
        for f in sorted(per):
            fh.write("\t".join([short(f), vs["owners"].get(os.path.realpath(f), vs["owners"].get(f, "?"))]
                               + [str(per[f].get(c, 0)) for c in C]) + "\n")


if __name__ == "__main__":
    main()
