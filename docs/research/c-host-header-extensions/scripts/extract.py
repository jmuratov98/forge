#!/usr/bin/env python3
"""Reached constructs, from gcc-15 -E -dD output of every accepted pair.

usage: python3 -I extract.py [PP_DIR_NAME]     (after gccnames.py)

For each (configuration, root) the -E output is split into emitted lines,
#define lines and #pragma lines, each attributed to (header, line) by the
linemarkers. A construct found in an emitted line is
  - "code" when the same token pattern occurs in the header's own text for
    that line (the source span runs to the next emitted line or directive);
  - "via"  when it does not: it came from a macro that header code expanded.
    The defining macro is found among the macros the span's identifiers reach.
A construct found only in #define bodies of the TU, and never emitted, is
"macro" (macro only: live only if user code expands the macro). The syntax of
a #define line itself (variadic parameters) is "define".
Identifiers are tracked when gccnames.json says GCC knows them (builtin,
keyword, predeclared type, or predefined macro) and they are not C89 keywords.
Writes WORK/extract[-TAG].json.
"""
import collections
import gzip
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

C89_KEYWORDS = set("""auto break case char const continue default do double else enum extern
float for goto if int long register return short signed sizeof static struct switch typedef
union unsigned void volatile while""".split())
DIRECTIVE_RE = re.compile(r"^\s*#")
PRAGMA_SRC_RE = re.compile(r"^\s*#\s*pragma\b")
INCLUDE_RE = re.compile(r"^\s*#\s*(include_next|include|import)\b\s*(.*)$")

TRACK = None


def load_track():
    g = json.load(open(os.path.join(common.WORK, "gccnames.json")))
    t = set()
    for cfg, res in g["per_config"].items():
        for x, r in res.items():
            if x in C89_KEYWORDS:
                continue
            if r.get("hb") or r.get("screen") or r.get("macro"):
                t.add(x)
    return t


def count_pattern(toks, pat):
    if len(pat) == 1:
        return sum(1 for t in toks if t[1] == pat[0])
    n, c = len(pat), 0
    for i in range(len(toks) - n + 1):
        if all(toks[i + j][1] == pat[j] for j in range(n)):
            c += 1
    return c


def process(job):
    cfg, n, path, track = job
    text = gzip.open(path, "rt").read()
    recs = common.parse_i(text)
    macros = collections.defaultdict(list)    # name -> [(file, line, params, body_toks)]
    builtin_macros = set()
    lines_of = collections.defaultdict(list)  # file -> lines with any record
    opened = []
    includes = []                              # (includer, line) of each #include
    stack = []
    for kind, f, line, payload in recs:
        if kind == "define":
            name, params, body = common.split_define(payload)
            if f in ("<built-in>", "<command-line>"):
                builtin_macros.add(name)
            macros[name].append((f, line, params, common.tokenize(body)))
        if kind in ("code", "define", "undef", "pragma"):
            lines_of[f].append(line)
        if kind == "enter":
            opened.append(f)
        if kind == "return":
            includes.append((f, line - 1))
            lines_of[f].append(line - 1)
    for f in lines_of:
        lines_of[f] = sorted(set(lines_of[f]))

    # reach closure over macro bodies
    reach_memo = {}

    def reach(m):
        if m in reach_memo:
            return reach_memo[m]
        seen, todo = set(), [m]
        while todo:
            x = todo.pop()
            if x in seen or x not in macros:
                continue
            seen.add(x)
            for (_f, _l, _p, bt) in macros[x]:
                for k, v in bt:
                    if k == "id" and v in macros and v not in seen:
                        todo.append(v)
        reach_memo[m] = seen
        return seen

    import bisect
    tokset = {}

    def holds(m, pat):
        if m not in tokset:
            tokset[m] = (set(t[1] for d in macros[m] for t in d[3]), [d[3] for d in macros[m]])
        vals, bodies = tokset[m]
        if pat[0] not in vals:
            return False
        return len(pat) == 1 or any(count_pattern(bt, pat) for bt in bodies)

    def span(f, line):
        src = common.source_lines(f)
        ls = lines_of.get(f, [])
        k = bisect.bisect_right(ls, line)
        end = ls[k] - 1 if k < len(ls) else line + 40
        end = min(end, line + 40, len(src) - 1)
        out = [src[line]] if line < len(src) else []
        for L in range(line + 1, end + 1):
            if DIRECTIVE_RE.match(src[L]):
                break
            out.append(src[L])
        return common.tokenize(" ".join(out))

    occ = collections.Counter()      # (name, mode, site) -> count
    forms = collections.Counter()    # (name, form) -> count
    asm_labels = collections.Counter()  # (declared, label, mode, file, line, macro) -> count
    expanded = set()

    # ---- emitted code: one token stream
    stream, rec_of = [], []
    code_recs = [r for r in recs if r[0] == "code"]
    for ri, (_k, f, line, payload) in enumerate(code_recs):
        for t in common.tokenize(payload):
            stream.append(t)
            rec_of.append(ri)
    found = collections.defaultdict(list)  # ri -> [(name, key, form, idx)]
    for idx, name, key, form in common.detect(stream):
        found[rec_of[idx]].append((name, key, form, idx))
    for idx, (k, v) in enumerate(stream):
        if k == "id" and v in track:
            found[rec_of[idx]].append(("id:" + v, (v,), "", idx))
    span_cache = {}
    for ri, items in found.items():
        _k, f, line, payload = code_recs[ri]
        sp = span(f, line)
        span_ids = {v for k, v in sp if k == "id" and v in macros}
        clos = set()
        for m in span_ids:
            clos |= reach(m)
        expanded |= clos
        bykey = collections.defaultdict(list)
        for it in items:
            bykey[(it[0], it[1])].append(it)
        for (name, key), its in bykey.items():
            if len(key) > 1:
                # a multi-token pattern may span source lines: test each token
                # against the source span of its own emitted line
                direct = []
                for (_nm, ky, _fm, idx) in its:
                    ok = True
                    for off in range(len(ky)):
                        p = idx + off
                        if p >= len(stream):
                            ok = False
                            break
                        rr = rec_of[p]
                        if rr not in span_cache:
                            span_cache[rr] = {v for _k2, v in span(code_recs[rr][1], code_recs[rr][2])}
                        if stream[p][1] not in span_cache[rr]:
                            ok = False
                            break
                    direct.append(ok)
            else:
                src_n = count_pattern(sp, key)
                direct = [j < src_n for j in range(len(its))]
            via_site = None
            for j, (nm, ky, form, idx) in enumerate(its):
                if direct[j]:
                    mode, site = "code", (f, line)
                else:
                    if via_site is None:
                        cand = sorted(m for m in clos if holds(m, ky))
                        if cand:
                            m = cand[0]
                            df, dl = macros[m][0][0], macros[m][0][1]
                        else:
                            m, df, dl = "?", "?", 0
                        via_site = (f, line, m, df, dl)
                    mode, site = "via", via_site
                occ[(nm, mode, site)] += 1
                if form:
                    forms[(nm, form)] += 1
                if nm == "asm:label":
                    # declared name: first identifier followed by '(' at depth 0 in this declaration
                    s = idx
                    while s > 0 and stream[s - 1][1] not in (";", "}", "{"):
                        s -= 1
                    decl = None
                    depth = 0
                    for q in range(s, idx):
                        tk, tv = stream[q][0], stream[q][1]
                        if tv == "(":
                            depth += 1
                        elif tv == ")":
                            depth -= 1
                        elif tk == "id" and depth == 0 and q + 1 < idx and stream[q + 1][1] == "(" and tv not in common.ATTR_WORDS and tv not in ("__typeof__", "__typeof", "typeof", "__extension__"):
                            decl = tv
                            break
                    if decl is None:
                        for q in range(idx - 1, s - 1, -1):
                            if stream[q][0] == "id" and stream[q][1] not in common.ATTR_WORDS:
                                decl = stream[q][1]
                                break
                    asm_labels[(decl, form, mode, f, line, site[2] if mode == "via" else "")] += 1

    # ---- pragmas
    for kind, f, line, payload in recs:
        if kind != "pragma":
            continue
        name = "pragma:" + common.pragma_key(payload)
        src = common.source_lines(f)
        if line < len(src) and PRAGMA_SRC_RE.match(src[line]):
            occ[(name, "code", (f, line))] += 1
        else:
            sp = span(f, line)
            clos = set()
            for k, v in sp:
                if k == "id" and v in macros:
                    clos |= reach(v)
            expanded |= clos
            cand = sorted(m for m in clos if holds(m, ("_Pragma",)))
            m = cand[0] if cand else "?"
            df, dl = (macros[m][0][0], macros[m][0][1]) if cand else ("?", 0)
            occ[(name, "via", (f, line, m, df, dl))] += 1
        forms[(name, payload.strip()[:120])] += 1

    # ---- #define bodies (macro-only candidates) and #define syntax
    for name, defs in macros.items():
        for (f, line, params, bt) in defs:
            if f in ("<built-in>", "<command-line>"):
                continue
            seen = set()
            for idx, nm, key, form in common.detect(bt):
                seen.add(nm)
                occ[(nm, "macro", (f, line, name))] += 1
                if form:
                    forms[(nm, form)] += 1
            for k, v in bt:
                if k == "id" and v in track:
                    occ[("id:" + v, "macro", (f, line, name))] += 1
            for nm in common.define_syntax(params, bt):
                mode = "define" if nm.startswith("syntax:named") or nm.startswith("syntax:variadic") else ("via" if name in expanded else "macro")
                occ[(nm, mode, (f, line, name))] += 1

    # ---- includes: #include_next and computed includes
    inc = collections.Counter()
    for (f, line) in includes:
        src = common.source_lines(f)
        if 0 < line < len(src):
            m = INCLUDE_RE.match(src[line])
            if m:
                if m.group(1) == "include_next":
                    occ[("directive:#include_next", "code", (f, line))] += 1
                if not m.group(2).lstrip().startswith(("<", '"')):
                    occ[("directive:computed #include", "code", (f, line))] += 1

    # predefined macros that header code expands
    for m in expanded & builtin_macros:
        occ[("predef:" + m, "via", ("<built-in>", 0))] += 1
    return cfg, n, list(occ.items()), list(forms.items()), list(asm_labels.items()), sorted(set(opened))


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "pp"
    track = load_track()
    idx = json.load(open(os.path.join(common.WORK, tag, "index.json")))
    roots = idx["roots"]
    jobs = [(c, n, os.path.join(common.WORK, tag, c, "%d.i.gz" % n), track)
            for c in common.CONFIG_NAMES for n in idx["pairs"][c]]
    occ = collections.defaultdict(set)        # (cfg, name, mode, site) -> roots
    forms = collections.Counter()             # (name, form) -> count
    asm = collections.defaultdict(set)        # (cfg, decl, label, mode, file, line, macro) -> roots
    opened = collections.defaultdict(set)     # (cfg, file) -> roots
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for cfg, n, o, fm, al, op in ex.map(process, jobs, chunksize=4):
            for (name, mode, site), c in o:
                occ[(cfg, name, mode, tuple(site))].add(n)
            for k, c in fm:
                forms[k] += c
            for k, c in al:
                asm[(cfg,) + tuple(k)].add(n)
            for f in op:
                opened[(cfg, f)].add(n)
    out = {
        "roots": roots,
        "occ": [[c, nm, md, list(site), sorted(rs)] for (c, nm, md, site), rs in occ.items()],
        "forms": [[nm, fm, c] for (nm, fm), c in forms.items()],
        "asm": [list(k) + [sorted(rs)] for k, rs in asm.items()],
        "opened": [[c, f, sorted(rs)] for (c, f), rs in opened.items()],
    }
    name = "extract.json" if tag == "pp" else "extract-%s.json" % tag
    json.dump(out, open(os.path.join(common.WORK, name), "w"))
    print("occ keys", len(out["occ"]), "asm keys", len(out["asm"]), "opened", len(out["opened"]))


if __name__ == "__main__":
    main()
