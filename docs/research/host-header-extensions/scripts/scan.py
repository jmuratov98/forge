#!/usr/bin/env python3
"""Scan every header in the static include closure for compiler extensions.

usage: scan.py MANIFEST CLOSURE_JSON CP_TRAIT_DEF MANINDEX_JSON OUT_JSON

Outputs a JSON object:
  hits:    one record per extension occurrence
  defines: every #define in the closure (name, file, line, guards, body)
  conds:   every conditional directive (file, line, kind, text, identifiers, queries)
Block ids ("fid.n") match those written by `hx.py instrument`.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx  # noqa: E402

TOKEN_RE = re.compile(r"""
    (?P<str>(?:u8|u|U|L)?"(?:\\.|[^"\\])*"?)
  | (?P<chr>(?:u8|u|U|L)?'(?:\\.|[^'\\])*'?)
  | (?P<num>\.?\d(?:[eEpP][+-]|[A-Za-z0-9_.']|)*)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<punct>\#\#|::|\.\.\.|->|[^\sA-Za-z0-9_])
""", re.X)


def tokenize(code):
    toks = []
    for m in TOKEN_RE.finditer(code):
        kind = m.lastgroup
        toks.append((kind, m.group(kind), m.start()))
    return toks


def balanced(toks, i):
    """toks[i] is '(' or '['; return index of matching closer (or len-1)."""
    opener = toks[i][1]
    closer = {"(": ")", "[": "]", "{": "}"}[opener]
    depth = 0
    for j in range(i, len(toks)):
        t = toks[j][1]
        if toks[j][0] != "punct":
            continue
        if t in "([{":
            depth += 1
        elif t in ")]}":
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def split_top(toks, a, b):
    """Split toks[a:b] at top-level commas; return list of (start, end)."""
    parts = []
    depth = 0
    s = a
    for j in range(a, b):
        t = toks[j][1]
        if toks[j][0] == "punct":
            if t in "([{":
                depth += 1
            elif t in ")]}":
                depth -= 1
            elif t == "," and depth == 0:
                parts.append((s, j))
                s = j + 1
    parts.append((s, b))
    return parts


def norm_attr(name):
    if name.startswith("__") and name.endswith("__") and len(name) > 4:
        return name[2:-2]
    return name


KEYWORD_EXT = {
    # GNU alternate keywords and extension keywords (GCC c_common_reswords)
    "__extension__": "keyword", "__typeof__": "keyword", "__typeof": "keyword",
    "typeof": "keyword", "__typeof_unqual__": "keyword", "__typeof_unqual": "keyword",
    "__decltype": "keyword", "__alignof__": "keyword", "__alignof": "keyword",
    "__restrict": "keyword", "__restrict__": "keyword", "__inline": "keyword",
    "__inline__": "keyword", "__const": "keyword", "__volatile": "keyword",
    "__signed": "keyword", "__signed__": "keyword", "__complex": "keyword",
    "__complex__": "keyword", "__real": "keyword", "__real__": "keyword",
    "__imag": "keyword", "__imag__": "keyword", "__label__": "keyword",
    "__thread": "keyword", "__null": "keyword", "__FUNCTION__": "keyword",
    "__PRETTY_FUNCTION__": "keyword", "__auto_type": "keyword", "__constinit": "keyword",
    "__transaction_atomic": "keyword", "__transaction_relaxed": "keyword",
    "__transaction_cancel": "keyword",
    # C keywords appearing in C++ translation units
    "_Alignas": "c-keyword", "_Alignof": "c-keyword", "_Atomic": "c-keyword",
    "_BitInt": "c-keyword", "_Bool": "c-keyword", "_Complex": "c-keyword",
    "_Imaginary": "c-keyword", "_Static_assert": "c-keyword", "_Noreturn": "c-keyword",
    "_Generic": "c-keyword", "_Thread_local": "c-keyword",
    # extended types
    "__int128": "type", "__int128_t": "type", "__uint128_t": "type",
    "__float128": "type", "__float80": "type", "__ibm128": "type", "__bf16": "type",
    "__fp16": "type", "__mfp8": "type",
    "_Float16": "type", "_Float32": "type", "_Float64": "type", "_Float128": "type",
    "_Float32x": "type", "_Float64x": "type", "_Float128x": "type",
    "_Decimal32": "type", "_Decimal64": "type", "_Decimal128": "type", "_Decimal64x": "type",
    # preprocessor extension macros/operators
    "__COUNTER__": "pp", "__INCLUDE_LEVEL__": "pp", "__BASE_FILE__": "pp",
    "__FILE_NAME__": "pp", "__TIMESTAMP__": "pp",
}
PP_OPERATORS = {"__has_include", "__has_include_next", "__has_builtin", "__has_attribute",
                "__has_cpp_attribute", "__has_c_attribute", "__has_feature", "__has_extension",
                "__has_embed", "__has_warning", "__is_identifier", "__building_module",
                "__is_target_arch", "__is_target_os", "__is_target_vendor",
                "__is_target_environment", "__has_declspec_attribute"}
QUERY_WRAPPERS = {"_GLIBCXX_HAS_BUILTIN": "__has_builtin",
                  "_GLIBCXX_USE_BUILTIN_TRAIT": "__has_builtin",
                  "__glibc_has_builtin": "__has_builtin",
                  "__glibc_has_attribute": "__has_attribute",
                  "__glibc_has_extension": "__has_extension",
                  "__GNUC_PREREQ": "__GNUC_PREREQ",
                  "__glibc_clang_prereq": "__glibc_clang_prereq",
                  "_GLIBCXX_HAS_ATTRIBUTE": "__has_attribute"}
ASM_WORDS = {"__asm__", "__asm", "asm"}
STD_CXX_ATTRS = {"nodiscard", "likely", "unlikely", "no_unique_address", "deprecated",
                 "maybe_unused", "noreturn", "fallthrough", "carries_dependency", "assume",
                 "indeterminate"}
DECL_ARRAY_RE = re.compile(
    r"^(?:(?:struct|union|enum|const|volatile|unsigned|signed|long|short|__extension__)\s+)*"
    r"[A-Za-z_]\w*(?:\s*<[^;]*>)?[\s*&]+[A-Za-z_]\w*\s*\[\s*(0?)\s*\]\s*;\s*$")
NEON_TYPE_RE = re.compile(r"^__(?:Int|Uint|Float|Poly|Bfloat|Mfloat)\d+x\d+_t$|^__SV[A-Za-z0-9]+_t$")


def load_traits(path):
    names = set()
    for m in re.finditer(r'^DEFTRAIT_\w+\s*\(\s*\w+\s*,\s*"([^"]+)"', open(path).read(), re.M):
        names.add(m.group(1))
    return names


def guard_view(stack):
    """Non-include-guard frames, outer to inner, as plain dicts."""
    out = []
    for fr in stack:
        if fr["guard"]:
            continue
        out.append({"kind": fr["kind"], "text": fr["text"], "line": fr["line"],
                    "chain": fr["chain"]})
    return out


def main():
    manifest_p, closure_p, trait_p, manidx_p, out_p = sys.argv[1:6]
    manifest = hx.load_manifest(manifest_p)
    closure = json.load(open(closure_p))
    traits = load_traits(trait_p)
    manidx = json.load(open(manidx_p))
    atomic_names = {n for n, es in manidx["builtin"].items()
                    if any("atomic-Builtins" in e["page"] for e in es)}
    sync_names = {n for n, es in manidx["builtin"].items()
                  if any("sync-Builtins" in e["page"] for e in es)}
    attr_names = set(manidx["attribute"])
    fid_of = {p: i for i, p in enumerate(sorted(manifest))}
    files = sorted(closure["files"])

    hits = []
    defines = []
    conds = []
    uses = {}

    for logical in files:
        fid = fid_of[logical]
        text = hx.read_text(manifest, logical)
        lls = hx.logical_lines(text)
        stack = []
        counter = 0
        first_cond_seen = False
        prev_tail = (";", "punct")
        tail_stack = []
        for k, ll in enumerate(lls):
            d, rest = hx.directive(ll)
            stack_before = [dict(fr) for fr in stack]
            # the token before a branch is the one before its #if group
            if d in hx.COND_OPEN:
                tail_stack.append(prev_tail)
            elif d in hx.COND_MID and tail_stack:
                prev_tail = tail_stack[-1]
            elif d == "endif" and tail_stack:
                tail_stack.pop()
            if d in hx.COND_OPEN:
                counter += 1
                frame = {"kind": d, "text": rest, "line": ll.start, "block": "%d.%d" % (fid, counter),
                         "chain": [], "guard": False}
                if not first_cond_seen:
                    first_cond_seen = True
                    gm = re.match(r"^(?:ifndef\s+(\w+)|if\s+!\s*defined\s*\(?\s*(\w+)\s*\)?\s*)$", d + " " + rest)
                    if gm:
                        gname = gm.group(1) or gm.group(2)
                        for ll2 in lls[k + 1:k + 4]:
                            d2, r2 = hx.directive(ll2)
                            if d2 == "define" and r2.split()[:1] == [gname]:
                                frame["guard"] = True
                                break
                            if d2 is not None:
                                break
                stack.append(frame)
            elif d in hx.COND_MID:
                if stack:
                    prev = stack.pop()
                    counter += 1
                    chain = prev["chain"] + [[prev["kind"], prev["text"], prev["line"]]]
                    stack.append({"kind": d, "text": rest, "line": ll.start,
                                  "block": "%d.%d" % (fid, counter), "chain": chain, "guard": False})
            elif d == "endif":
                if stack:
                    stack.pop()

            # the block a line belongs to: for conditional directives, the parent
            if d in hx.COND_OPEN or d in hx.COND_MID or d == "endif":
                ctx_stack = stack_before if d != "endif" else stack
                if d in hx.COND_MID and ctx_stack:
                    ctx_stack = ctx_stack[:-1]
            else:
                ctx_stack = stack
            block = ctx_stack[-1]["block"] if ctx_stack else "%d.0" % fid
            guards = guard_view(ctx_stack)

            def emit(name, group, spelling, ctx, extra=None):
                rec = {"name": name, "group": group, "spelling": spelling, "file": logical,
                       "line": ll.start, "ctx": ctx, "block": block, "guards": guards}
                if extra:
                    rec.update(extra)
                hits.append(rec)

            code = ll.code
            if d is None:
                ctx = "code"
                body = code
            elif d == "define":
                m = re.match(r"\s*(\w+)(\([^)]*\))?(.*)$", rest, re.S)
                if not m:
                    continue
                mname, params, body = m.group(1), m.group(2), m.group(3)
                ctx = "define:" + mname
                defines.append({"name": mname, "file": logical, "line": ll.start, "block": block,
                                "params": params, "body": body.strip(), "guards": guards})
                # macro *named* like an extension keyword = non-GNU fallback
                if mname in KEYWORD_EXT or mname in ("__attribute__", "__attribute", "__asm__", "__asm"):
                    emit(mname, "fallback-define", mname, ctx, {"body": body.strip()})
                if params:
                    pm = re.search(r"(\w+)\s*\.\.\.\s*\)", params)
                    if pm:
                        emit("named variadic macro parameter", "syntax", pm.group(0), ctx)
            elif d in ("if", "elif", "ifdef", "ifndef", "elifdef", "elifndef"):
                ctx = "cond"
                body = rest
                ids = set()
                toks = tokenize(rest)
                queries = []
                for i, (kind, val, _) in enumerate(toks):
                    if kind != "id" or val == "defined":
                        continue
                    if (val in PP_OPERATORS or val in QUERY_WRAPPERS) and i + 1 < len(toks) and toks[i + 1][1] == "(":
                        j = hx_bal = balanced(toks, i + 1)
                        arg = " ".join(t[1] for t in toks[i + 2:j])
                        queries.append([val, arg])
                        continue
                    ids.add(val)
                # remove identifiers that are only query arguments
                qargs = set()
                for q in queries:
                    for t in tokenize(q[1]):
                        if t[0] == "id":
                            qargs.add(t[1])
                ids2 = set()
                for i, (kind, val, _) in enumerate(toks):
                    if kind == "id" and val != "defined":
                        ids2.add(val)
                inside = set()
                for i, (kind, val, _) in enumerate(toks):
                    if kind == "id" and (val in PP_OPERATORS or val in QUERY_WRAPPERS) and i + 1 < len(toks) and toks[i + 1][1] == "(":
                        j = balanced(toks, i + 1)
                        for t in toks[i + 2:j]:
                            if t[0] == "id":
                                inside.add(t[1])
                plain = {x for x in ids2 if x not in inside and x not in PP_OPERATORS and x not in QUERY_WRAPPERS}
                conds.append({"file": logical, "line": ll.start, "kind": d, "text": rest,
                              "ids": sorted(plain), "queries": queries,
                              "block": block, "guards": guards,
                              "own_block": stack[-1]["block"] if stack else None})
                for q in queries:
                    emit("query:%s(%s)" % (q[0], q[1]), "query", q[0], ctx)
                for x in plain:
                    if x in PP_OPERATORS:
                        emit(x, "preprocessor", x, ctx)
                continue
            elif d == "pragma":
                txt = re.sub(r"\s+", " ", rest).strip()
                words = txt.split(" ")
                key = " ".join(words[:2]) if words and words[0] in ("GCC", "clang", "STDC", "omp") else words[0]
                key = re.sub(r"\(.*$", "", key)
                emit("#pragma " + key, "pragma", txt, "pragma")
                continue
            elif d in ("include_next", "warning", "ident", "sccs", "assert", "unassert", "import"):
                emit("#" + d, "directive", ("#" + d + " " + rest)[:80], "directive")
                continue
            else:
                continue

            toks = tokenize(body)
            n = len(toks)
            i = 0
            while i < n:
                kind, val, pos = toks[i]
                nxt = toks[i + 1][1] if i + 1 < n else ""
                if kind == "num":
                    if re.search(r"(?:[fFlL]?[iIjJ]|[iIjJ][fFlL]?)$", val) and not val.lower().startswith("0x") and re.match(r"^[\d.]", val):
                        emit("imaginary constant suffix", "syntax", val, ctx)
                    elif re.search(r"(?:[fF](?:16|32|64|128)x?|[bB][fF]16|[qQwW])$", val) and not val.lower().startswith("0x"):
                        emit("pp-number suffix " + re.search(r"(?:[fF](?:16|32|64|128)x?|[bB][fF]16|[qQwW])$", val).group(0), "syntax", val, ctx)
                    i += 1
                    continue
                if kind == "str" and i > 0 and toks[i - 1][1] == "(" and i > 1 and toks[i - 2][1] == "_Pragma":
                    i += 1
                    continue
                if kind != "id":
                    if kind == "punct" and val == "?" and nxt == ":" :
                        emit("conditional with omitted operand (?:)", "syntax", "?:", ctx)
                    if kind == "punct" and val == "##" and nxt == "__VA_ARGS__" and i > 0 and toks[i - 1][1] == ",":
                        emit("GNU comma paste (, ## __VA_ARGS__)", "syntax", ", ## __VA_ARGS__", ctx)
                    if kind == "punct" and val == "(" and nxt == "{" and (ctx.startswith("define:") or (i > 0 and toks[i - 1][1] == "__extension__")):
                        emit("statement expression ({ ... })", "syntax", "({", ctx)
                    if kind == "punct" and val == "[" and nxt == "[" and i + 2 < n:
                        # C++11 attribute-specifier
                        j = balanced(toks, i)
                        if j > i + 2 and toks[j - 1][1] == "]":
                            inner_a, inner_b = i + 2, j - 1
                            ns_using = None
                            if toks[inner_a][1] == "using":
                                ns_using = toks[inner_a + 1][1]
                                inner_a += 3
                            for (a, b) in split_top(toks, inner_a, inner_b):
                                if a >= b:
                                    continue
                                if b - a >= 3 and toks[a + 1][1] == "::":
                                    ns, an = toks[a][1], toks[a + 2][1]
                                else:
                                    ns, an = ns_using, toks[a][1]
                                if toks[a][0] != "id":
                                    continue
                                if ns is None:
                                    base = norm_attr(an)
                                    if base in STD_CXX_ATTRS:
                                        grp = "attribute-std"
                                        nm = "[[%s]]" % base
                                    else:
                                        grp = "attribute-cxx11-other"
                                        nm = "[[%s]]" % an
                                else:
                                    grp = "attribute"
                                    nm = norm_attr(an)
                                emit(nm, grp, "[[%s%s]]" % (ns + "::" if ns else "", an), ctx,
                                     {"syntax": "[[%s::]]" % ns if ns else "[[]]"})
                            i = j + 1
                            continue
                    i += 1
                    continue

                # identifiers
                if val in ("__attribute__", "__attribute") and nxt == "(" and i + 2 < n and toks[i + 2][1] == "(":
                    j = balanced(toks, i + 1)
                    inner = balanced(toks, i + 2)
                    for (a, b) in split_top(toks, i + 3, inner):
                        if a >= b or toks[a][0] != "id":
                            continue
                        an = toks[a][1]
                        emit(norm_attr(an), "attribute", an, ctx, {"syntax": val + "(())"})
                        # identifiers following the name at top level (e.g. __LEAF)
                        depth = 0
                        for t in toks[a + 1:b]:
                            if t[0] == "punct" and t[1] in "([":
                                depth += 1
                            elif t[0] == "punct" and t[1] in ")]":
                                depth -= 1
                            elif t[0] == "id" and depth == 0:
                                emit("attribute-list macro " + t[1], "attribute-macro", t[1], ctx)
                    emit(val, "keyword", val, ctx)
                    i = j + 1
                    continue
                if val in ASM_WORDS:
                    # qualifiers
                    j = i + 1
                    quals = []
                    while j < n and toks[j][1] in ("volatile", "__volatile__", "__volatile", "goto", "inline", "__inline", "__inline__"):
                        quals.append(toks[j][1])
                        j += 1
                    if j < n and toks[j][1] == "(":
                        k2 = balanced(toks, j)
                        inner = toks[j + 1:k2]
                        depth = 0
                        has_colon = False
                        for t in inner:
                            if t[0] == "punct" and t[1] in "([{":
                                depth += 1
                            elif t[0] == "punct" and t[1] in ")]}":
                                depth -= 1
                            elif t[0] == "punct" and t[1] in (":", "::") and depth == 0:
                                has_colon = True
                        pj = i - 1
                        while pj >= 0 and toks[pj][1] == "__extension__":
                            pj -= 1
                        if pj >= 0:
                            prev, prev_kind = toks[pj][1], toks[pj][0]
                        elif ctx == "code":
                            prev, prev_kind = prev_tail
                        else:
                            prev, prev_kind = "", ""
                        if not quals and not has_colon and (prev in (")", "]") or prev_kind == "id") and prev not in ("return", "else", "do"):
                            emit("asm label (symbol rename)", "asm", val, ctx,
                                 {"asm": " ".join(t[1] for t in inner)[:80]})
                        else:
                            emit("inline asm" + (" (extended)" if has_colon else " (basic)"), "asm", val, ctx,
                                 {"asm": (" ".join(quals) + " " + " ".join(t[1] for t in inner))[:100]})
                        i = k2 + 1
                        continue
                    emit("asm keyword (other)", "asm", val, ctx)
                    i += 1
                    continue
                if val == "_Pragma" and nxt == "(":
                    j = balanced(toks, i + 1)
                    arg = " ".join(t[1] for t in toks[i + 2:j])
                    s = arg
                    if arg.startswith('"'):
                        s = arg.strip('"').replace('\\"', '"')
                    words = re.sub(r"\s+", " ", s).strip().split(" ")
                    key = " ".join(words[:2]) if words and words[0] in ("GCC", "clang", "STDC", "omp") else words[0]
                    key = re.sub(r"\(.*$", "", key)
                    emit("#pragma " + key, "pragma", "_Pragma(" + arg + ")", ctx, {"via": "_Pragma"})
                    i = j + 1
                    continue
                if val.startswith("__builtin_"):
                    emit(val, "builtin", val, ctx)
                elif val in traits and (nxt in ("(", "<")):
                    emit(val, "trait", val, ctx)
                elif val in atomic_names and nxt == "(":
                    emit(val, "atomic", val, ctx)
                elif val in sync_names and nxt == "(":
                    emit(val, "sync", val, ctx)
                elif val in KEYWORD_EXT:
                    # skip keyword used as macro name in its own #define (handled above)
                    if not (ctx == "define:" + val):
                        emit(val, KEYWORD_EXT[val], val, ctx)
                elif NEON_TYPE_RE.match(val):
                    emit(val, "aarch64-type", val, ctx)
                elif val in PP_OPERATORS:
                    emit(val, "preprocessor", val, ctx)
                elif val in QUERY_WRAPPERS and nxt == "(":
                    j = balanced(toks, i + 1)
                    arg = " ".join(t[1] for t in toks[i + 2:j])
                    emit("query:%s(%s)" % (val, arg), "query", val, ctx)
                elif val.startswith("__") and val.endswith("__") and norm_attr(val) in attr_names and len(val) > 4:
                    # bare attribute token outside an __attribute__ list (e.g. "#define __LEAF , __leaf__")
                    prevtok = toks[i - 1][1] if i > 0 else ""
                    if prevtok == ",":
                        emit(norm_attr(val), "attribute", val, ctx, {"syntax": "via macro"})
                elif "$" in val:
                    emit("$ in identifier", "syntax", val, ctx)
                if val == "long" and nxt == "double":
                    emit("long double", "type-std", "long double", ctx)
                if val == "case" and "..." in body:
                    emit("case range", "syntax", "case ...", ctx)
                if val == "goto" and nxt == "*":
                    emit("computed goto", "syntax", "goto *", ctx)
                i += 1

            # zero-length / flexible array members (C++ has neither)
            if ctx == "code":
                one = " ".join(body.split())
                if DECL_ARRAY_RE.match(one) and not re.search(r"\b(extern|static|typedef|return|operator)\b|::|=|\(", one):
                    m = DECL_ARRAY_RE.match(one)
                    kind_ = "zero-length array member" if m.group(1).strip() == "0" else "flexible array member"
                    emit(kind_, "syntax", one[:80], ctx)
                if re.search(r"\b__flexarr\b", body):
                    emit("flexible array member (__flexarr)", "syntax", "__flexarr", ctx)
            elif ctx.startswith("define:"):
                one = " ".join(body.split())
                if re.search(r"\[\s*0\s*\]\s*$", one) or re.search(r"\w\s*\[\s*0\s*\]\s*;", one):
                    emit("zero-length array member", "syntax", one[:80], ctx)
                if re.search(r"\b\w+\s*\[\s*\]\s*;", one) or re.fullmatch(r"\[\s*\]", one):
                    emit("flexible array member", "syntax", one[:80], ctx)

            # identifier uses, for macro-expansion reachability
            if ctx == "code":
                ids_here = {t[1] for t in toks if t[0] == "id"}
                uses.setdefault(block, set()).update(ids_here)
                if toks:
                    prev_tail = (toks[-1][1], toks[-1][0])

    with open(out_p, "w") as f:
        json.dump({"hits": hits, "defines": defines, "conds": conds,
                   "uses": {k: sorted(v) for k, v in uses.items()}}, f)
    print(len(hits), "hits;", len(defines), "defines;", len(conds), "conditionals", file=sys.stderr)


if __name__ == "__main__":
    main()
