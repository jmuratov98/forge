"""Grep-level feature scan of the C programs found by enumerate.py.

Usage: python3 -I scan.py LTS_ROOT PROGRAMS_JSON OUT_JSON

For each C program: follows quoted #includes (including file's directory,
then the program's -I directories, then the program directory) to collect
the program's own files; counts physical lines; strips comments; blanks
string and character literal contents (kept separately so printf formats
can be scanned); then counts regex hits per feature. Occurrences inside
#if 0 or any other conditional are counted: this is grep-level, not
preprocessed. Never executes anything from LTS_ROOT.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

INC_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*([<"])([^>"]+)[>"]', re.M)

MATHL = ("acos asin atan atan2 cos sin tan acosh asinh atanh cosh sinh tanh exp exp2 expm1 "
         "frexp ilogb ldexp log log10 log1p log2 logb modf scalbn scalbln cbrt fabs hypot pow "
         "sqrt erf erfc lgamma tgamma ceil floor nearbyint rint lrint llrint round lround "
         "llround trunc fmod remainder remquo copysign nan nextafter nexttoward fdim fmax fmin "
         "fma").split()

FEATURES = {
    "long_double": r"\blong\s+double\b|\bdouble\s+long\b",
    "long_double_cast": r"\(\s*long\s+double\s*\)",
    "math_l_funcs": r"\b(?:" + "|".join(f + "l" for f in MATHL) + r"|strtold|wcstold)\s*\(",
    "LONGDOUBLE_TYPE": r"\bLONGDOUBLE_TYPE\b",
    "int128": r"\b__int128(?:_t)?\b|\b__uint128_t\b|\bmode\s*\(\s*_*TI_*\s*\)",
    "BitInt": r"\b_BitInt\s*\(",
    "Complex": r"\b_Complex\b|\b__complex__\b|\b_Complex_I\b|\bcomplex\s+(?:float|double|long)\b|\b(?:float|double)\s+complex\b",
    "Generic": r"\b_Generic\s*\(",
    "Atomic_kw": r"\b_Atomic\b",
    "atomic_builtins": r"\b__(?:atomic|sync)_[a-z_]+\s*\(",
    "Thread_local": r"\b(?:_Thread_local|__thread|thread_local)\b",
    "pthread_calls": r"\bpthread_[a-z_]+\s*\(",
    "Alignas_Alignof": r"\b(?:_Alignas|_Alignof|alignas|alignof)\b",
    "gnu_alignof": r"\b__alignof(?:__)?\b",
    "Static_assert": r"\b(?:_Static_assert|static_assert)\b",
    "Noreturn": r"\b(?:_Noreturn|noreturn)\b",
    "restrict": r"\b(?:restrict|__restrict__|__restrict)\b",
    "inline_static": r"\bstatic\s+(?:__inline__|__inline|inline)\b|\b(?:__inline__|__inline|inline)\s+static\b",
    "inline_extern": r"\bextern\s+(?:__inline__|__inline|inline)\b|\b(?:__inline__|__inline|inline)\s+extern\b",
    "inline_any": r"\b(?:__inline__|__inline|inline)\b",
    "gnu_inline_attr": r"\bgnu_inline\b",
    "hex_float": r"\b0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)[pP][+-]?[0-9]+",
    "variadic_macro": r"#[ \t]*define[ \t]+\w+\([^)]*\.\.\.[ \t]*\)",
    "nullptr": r"\bnullptr\b",
    "constexpr": r"\bconstexpr\b",
    "typeof_plain": r"\btypeof(?:_unqual)?\b",
    "typeof_gnu": r"\b__typeof(?:__)?\b",
    "c23_attr": r"\[\[\s*(?:__)?[A-Za-z_]\w*",
    "embed": r"#[ \t]*embed\b",
    "auto_kw": r"\bauto\b",
    "bool_ident": r"\btypedef\b[^;]*\bbool\s*;|#[ \t]*define[ \t]+(?:bool|true|false)\b|\benum\b[^;{]*\{[^}]*\b(?:false|true)\b",
    "stmt_expr": r"\(\s*\{",
    "computed_goto": r"\bgoto\s*\*",
    "case_range": r"\bcase\b[^:;]*\.\.\.",
    "zero_len_array": r"^[ \t]*(?:[A-Za-z_]\w*[ \t*]+)+[A-Za-z_]\w*[ \t]*\[[ \t]*0[ \t]*\][ \t]*;",
    "vector_size": r"\bvector_size\b",
    "alloca": r"\b(?:__builtin_)?alloca\s*\(",
    "inline_asm": r"\b(?:__asm__|__asm|asm)\b\s*(?:volatile|__volatile__)?\s*(?:goto\s*)?\(",
    "asm_label": r"\)\s*(?:__asm__|__asm|asm)\s*\(\s*\"",
    "setjmp": r"\b(?:setjmp|longjmp|sigsetjmp|siglongjmp|_setjmp|_longjmp)\s*\(",
    "signal": r"\b(?:signal|sigaction)\s*\(",
    "va_start": r"\bva_start\s*\(",
    "bitfield": r"^[ \t]*(?:(?:unsigned|signed|const|volatile)\s+)*(?:int|unsigned|signed|char|short|long|_Bool|bool|u?int(?:8|16|32|64)_t|[A-Za-z_]\w*_t|[A-Z][A-Za-z0-9_]*)\s+(?:[A-Za-z_]\w*\s*)?:\s*[0-9]+\s*[;,]",
    "fenv_calls": r"\bfe(?:getround|setround|clearexcept|raiseexcept|testexcept|getenv|setenv|holdexcept|updateenv|getexceptflag|setexceptflag|enableexcept|disableexcept)\s*\(",
    "Pragma_op": r"\b_Pragma\s*\(",
}
FEATURES = {k: re.compile(v, re.M) for k, v in FEATURES.items()}
FMT_L = re.compile(r"%[-+ #0'0-9.*$]*L[fFeEgGaA]")
BUILTIN = re.compile(r"\b(__builtin_\w+)")
ATTR = re.compile(r"\b__attribute(?:__)?\s*\(\(")
PRAGMA = re.compile(r"^[ \t]*#[ \t]*pragma[ \t]+(\w+)(?:[ \t]+(\w+))?", re.M)


def strip(text):
    """Return (code, strings): comments removed, literal contents blanked."""
    out, strs, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j])); i = j; continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            i = j; continue
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            lit = text[i + 1:j]
            if c == '"':
                strs.append(lit)
            out.append(c + re.sub(r"[^\n]", "x", lit) + c); i = j + 1; continue
        # keep #include targets intact by skipping <...> handling: includes are parsed from raw text
        out.append(c); i += 1
    return "".join(out), strs


def attr_names(code):
    names = Counter()
    for m in ATTR.finditer(code):
        i, depth, buf = m.end(), 2, ""
        while i < len(code) and depth:
            ch = code[i]
            if ch == "(":
                depth += 1
                if depth == 3:
                    buf += " "
            elif ch == ")":
                depth -= 1
            elif depth == 2:
                buf += ch
            i += 1
        for part in buf.split(","):
            w = re.match(r"\s*([A-Za-z_]\w*)", part)
            if w:
                names[w.group(1).strip("_")] += 1
    return names


def inc_dirs(p, root):
    dirs = []
    flags = (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) + (p["CXXFLAGS"] or [])
    for k, f in enumerate(flags):
        d = None
        if f == "-I" and k + 1 < len(flags):
            d = flags[k + 1]
        elif f.startswith("-I") and len(f) > 2:
            d = f[2:]
        if d:
            dirs.append(d if os.path.isabs(d) else os.path.join(root, p["dir"], d))
    for e in p["extra"]:
        if e[0] == "target_include_directories":
            dirs += [x for x in e[1:] if os.path.isabs(x)]
    return dirs


def closure(p, root):
    pdir = os.path.join(root, p["dir"])
    idirs = inc_dirs(p, root)
    todo = [os.path.normpath(os.path.join(pdir, s)) for s in p["sources"]]
    seen, sys_inc, unresolved = [], set(), set()
    while todo:
        f = todo.pop()
        if f in seen or not os.path.isfile(f):
            continue
        seen.append(f)
        raw = open(f, encoding="latin-1").read()
        for kind, name in INC_RE.findall(raw):
            cands = ([os.path.dirname(f)] if kind == '"' else []) + idirs + ([pdir] if kind == '"' else [])
            hit = None
            for d in cands:
                c = os.path.normpath(os.path.join(d, name))
                if os.path.isfile(c):
                    hit = c; break
            if hit:
                todo.append(hit)
            elif kind == "<":
                sys_inc.add(name)
            else:
                unresolved.add(name)
    return seen, sys_inc, unresolved


def main():
    root, pj, out = sys.argv[1], sys.argv[2], sys.argv[3]
    progs = [p for p in json.load(open(pj))["programs"] if p["lang"] == "C"]
    res = []
    for p in progs:
        files, sys_inc, unresolved = closure(p, root)
        loc_c = loc_h = 0
        feats = Counter()
        builtins, attrs, pragmas, fmt = Counter(), Counter(), Counter(), 0
        for f in files:
            raw = open(f, encoding="latin-1").read()
            nl = raw.count("\n")
            if f.endswith(".c"):
                loc_c += nl
            else:
                loc_h += nl
            code, strs = strip(raw)
            for k, rx in FEATURES.items():
                n = len(rx.findall(code))
                if n:
                    feats[k] += n
            builtins.update(BUILTIN.findall(code))
            attrs.update(attr_names(code))
            for a, b in PRAGMA.findall(code):
                pragmas[(a + " " + b).strip()] += 1
            fmt += sum(len(FMT_L.findall(s.replace("%%", ""))) for s in strs)
        if fmt:
            feats["printf_L"] = fmt
        rel = [os.path.relpath(f, root) for f in files]
        res.append(dict(name=p["name"], dir=p["dir"], n_c=sum(f.endswith(".c") for f in files),
                        n_h=sum(not f.endswith(".c") for f in files), loc_c=loc_c, loc_h=loc_h,
                        files=rel, sys_includes=sorted(sys_inc), unresolved_quoted=sorted(unresolved),
                        features=dict(feats), builtins=dict(builtins), attributes=dict(attrs),
                        pragmas=dict(pragmas)))
    json.dump(res, open(out, "w"), indent=1)
    print(f"programs={len(res)} c_files={sum(r['n_c'] for r in res)} loc_c={sum(r['loc_c'] for r in res)} "
          f"loc_h={sum(r['loc_h'] for r in res)}")


if __name__ == "__main__":
    main()
