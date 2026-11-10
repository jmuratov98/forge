"""Render docs/research/c-budget-suite-census.md from main.md and the data.

Usage: python3 -I report.py WORK_DIR TEMPLATE OUT_MD LTS_ROOT

WORK_DIR holds programs.json (enumerate.py), scan.json (scan.py), the
diag-*.json files (diag.py), ld.json (longdouble.py) and torture.json /
glibc.json when present. Each {{NAME}} in the template is replaced by the
output of the function table_NAME below; a missing input yields a note.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

W = sys.argv[1]
CTMARK = {"sqlite3": "sqlite3", "clamscan": "ClamAV", "consumer-typeset": "consumer-typeset",
          "lencod": "lencod", "pairlocalalign": "mafft", "SPASS": "SPASS"}


def load(name):
    p = os.path.join(W, name)
    return json.load(open(p)) if os.path.exists(p) else None


PROGS = [p for p in load("programs.json")["programs"] if p["lang"] == "C"]
ALLP = load("programs.json")["programs"]
SCAN = {(r["dir"], r["name"]): r for r in (load("scan.json") or [])}
DIAG = {}
for f in sorted(os.listdir(W)):
    m = re.match(r"diag-(.+)\.json$", f)
    if m:
        DIAG[m.group(1)] = {(e["dir"], e["name"]): e for e in json.load(open(os.path.join(W, f)))["programs"]}


def short(d):
    return (d.replace("SingleSource/Benchmarks", "SS").replace("MultiSource/Benchmarks", "MS")
            .replace("MultiSource/Applications", "MA"))


def pname(p):
    n = p["name"]
    return f"**{n}** (CTMark {CTMARK[n]})" if n in CTMARK else n


def key(p):
    return (p["dir"], p["name"])


def std_of(p):
    own = [f for f in (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) if f.startswith("-std=")]
    if own:
        return own[-1][5:] + " (CFLAGS)"
    if p["c_standard"]:
        return "gnu" + p["c_standard"].replace("90", "89") + " (C_STANDARD " + p["c_standard"] + ")"
    return "—"


def flags_of(p, pred):
    out = []
    for f in (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) + (p["CXXFLAGS"] or []) + (p["__DEFS"] or []):
        if pred(f) and f not in out:
            out.append(f)
    return out


def esc(s):
    return s.replace("|", "\\|")


def table_COUNTS():
    c = Counter(p["lang"] for p in ALLP)
    by = Counter()
    for p in PROGS:
        parts = p["dir"].split("/")
        by[short("/".join(parts[:3]))] += 1
    loc_c = sum(SCAN[key(p)]["loc_c"] for p in PROGS if key(p) in SCAN)
    files = {}
    for p in PROGS:
        for f in SCAN.get(key(p), {}).get("files", []):
            files[f] = 1
    lines = ["| Measure | Value |", "|---|---|",
             f"| Test programs the fixed configuration defines under the scanned trees | {len(ALLP)} |",
             f"| C programs (every source `.c`) | **{c['C']}** |",
             f"| C++ programs | {c['C++']} |",
             f"| Mixed C and C++ (not counted as C) | {c['mixed']}: " +
             ", ".join(p["name"] for p in ALLP if p["lang"] == "mixed") + " |"]
    uc = uh = 0
    for f in files:
        n = UNIQ_LINES.get(f, 0)
        if f.endswith(".c"):
            uc += n
        else:
            uh += n
    lines += [f"| Distinct program files reached (`.c` sources, `#include`d `.c`, local headers) | {len(files)} |",
              f"| Lines in those distinct `.c` files | **{uc:,}** |",
              f"| Lines in those distinct local headers | {uh:,} |",
              f"| Total lines of C (distinct `.c` + `.h`) | **{uc + uh:,}** |"]
    lines += ["", "| Suite directory | C programs |", "|---|---|"]
    for k, v in sorted(by.items()):
        lines.append(f"| `{k}` | {v} |")
    return "\n".join(lines)


def table_CTMARK():
    lines = ["| CTMark entry | Symlink target | Test target | `.c` files | Lines (.c + local .h) | std the suite passes |",
             "|---|---|---|---|---|---|"]
    tgt = {"sqlite3": "MultiSource/Applications/sqlite3", "ClamAV": "MultiSource/Applications/ClamAV",
           "consumer-typeset": "MultiSource/Benchmarks/MiBench/consumer-typeset",
           "lencod": "MultiSource/Applications/JM/lencod", "mafft": "MultiSource/Benchmarks/mafft",
           "SPASS": "MultiSource/Applications/SPASS"}
    for p in PROGS:
        if p["name"] in CTMARK:
            s = SCAN[key(p)]
            lines.append(f"| `CTMark/{CTMARK[p['name']]}` | `../{tgt[CTMARK[p['name']]]}` | `{p['name']}` | "
                         f"{s['n_c']} | {s['loc_c'] + s['loc_h']:,} | {std_of(p)} |")
    return "\n".join(lines)


def tol(p):
    t = []
    if p["FP_TOLERANCE"]:
        t.append("r " + p["FP_TOLERANCE"][0])
    if p["FP_ABSTOLERANCE"]:
        t.append("a " + p["FP_ABSTOLERANCE"][0])
    if p["HASH_PROGRAM_OUTPUT"]:
        t.append("hash")
    defs = [f for f in (p["__DEFS"] or []) if "FP_ABSTOLERANCE" in f]
    if defs:
        t.append("in-program " + defs[0][2:])
    return ", ".join(t) or "exact"


def table_FLAGS():
    lines = ["| # | Program | Directory | `.c` | Lines | std | `-D`/`-U`/`-I` | `-W`/`-f`/other | Link | Reference output; fpcmp |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(sorted(PROGS, key=lambda p: (p["dir"], p["name"])), 1):
        s = SCAN.get(key(p), {})
        d = flags_of(p, lambda f: f.startswith(("-D", "-U")) and "FP_ABSTOLERANCE" not in f and f != "-DNDEBUG")
        inc = flags_of(p, lambda f: f.startswith("-I"))
        o = flags_of(p, lambda f: f.startswith(("-W", "-f", "-pthread")) and not f.startswith("-Werror=date"))
        o += ["target_link_libraries(${Intl_LIBRARIES}) after find_package(Intl): empty on glibc, whose libc holds libintl"
              for e in p["extra"] if e[0] == "target_link_libraries"]
        ld = " ".join(p["LDFLAGS"] or []) or "—"
        dtxt = " ".join(f"`{esc(x)}`" for x in d) if d else "—"
        if inc:
            dtxt += f" + {len(inc)} `-I`"
        lines.append(f"| {i} | {pname(p)} | `{short(p['dir'])}` | {s.get('n_c', '?')} | "
                     f"{s.get('loc_c', 0) + s.get('loc_h', 0):,} | {std_of(p)} | {dtxt} | "
                     f"{' '.join('`' + esc(x) + '`' for x in o) or '—'} | {ld} | "
                     f"{'yes' if p['reference_output'] else 'no'}; {tol(p)} |")
    return "\n".join(lines)


def table_FLAGSUMMARY():
    c = Counter()
    who = defaultdict(list)
    for p in PROGS:
        for f in flags_of(p, lambda f: f.startswith(("-W", "-f", "-pthread"))):
            if f.startswith("-Werror=date"):
                continue
            c[f] += 1
            who[f].append(p["name"])
        for f in p["LDFLAGS"] or []:
            c["link " + f] += 1
        st = std_of(p)
        lab = "std " + (st.split(" ")[0] + (" via -std= in CFLAGS" if "CFLAGS" in st else " via C_STANDARD")
                        if st != "—" else "not pinned (compiler default)")
        c[lab] += 1
        who[lab].append(p["name"])
    lines = ["| Flag | Programs | Which (up to 12) |", "|---|---|---|"]
    for f, n in sorted(c.items(), key=lambda x: (-x[1], x[0])):
        names = who.get(f, [])
        lst = ", ".join(names[:12]) + (" …" if len(names) > 12 else "") if names and n < len(PROGS) else ""
        lines.append(f"| `{f}` | {n} | {lst} |")
    return "\n".join(lines)



PP = {(r["dir"], r["name"]): r for r in (load("pp.json") or [])}
LD = load("ld.json") or {}
C99_HDR = {"stdint.h", "stdbool.h", "inttypes.h", "complex.h", "fenv.h", "tgmath.h"}
C11_HDR = {"stdalign.h", "stdatomic.h", "stdnoreturn.h", "threads.h", "uchar.h"}
C23_HDR = {"stdbit.h", "stdckdint.h"}
VA_MACRO_BUILTINS = {"__builtin_va_start", "__builtin_va_end", "__builtin_va_arg", "__builtin_va_copy",
                     "__builtin_va_list", "__builtin_c23_va_start"}


def dg(cfg, p, flag=None, sub=None, sev=None):
    e = DIAG.get(cfg, {}).get(key(p))
    if not e:
        return []
    out = []
    for x in e["diags"]:
        if flag and x[3] != flag:
            continue
        if sub and sub not in x[4]:
            continue
        if sev == "error" and x[2] == "warning":
            continue
        out.append(x)
    return out


def gcc_err_class(msg):
    if re.search(r"\b(bool|true|false)\b", msg) or "two or more data types" in msg:
        return "bool/true/false keywords"
    if "_Generic" in msg:
        return "glibc C23 _Generic macro"
    if re.search(r"too (many|few) arguments|number of arguments|prototype declaration|conflicting types|incompatible pointer type", msg):
        return "() now means (void)"
    if "defaults to 'int'" in msg:
        return "implicit int"
    if "restrict" in msg or "controlling expression" in msg or "expected identifier or '('" in msg or "expected expression" in msg:
        return "restrict is a keyword"
    if "No such file" in msg:
        return "missing header"
    return "other"


def derive(p):
    s, pp = SCAN.get(key(p), {"features": {}, "sys_includes": [], "builtins": {}, "attributes": {}}), PP.get(key(p), {"features": {}, "builtins": {}, "attributes": {}, "pragmas": {}})
    f, g = s["features"], pp["features"]
    inc = set(s["sys_includes"]) | {u for u in s.get("unresolved_quoted", []) if u in C99_HDR | C11_HDR}
    d = {}
    nodes = LD.get(p["name"], {}).get("nodes", {})
    arith = sum(v for k, v in nodes.items() if k.startswith(("BinaryOperator", "CompoundAssign", "UnaryOperator")))
    d["ld"] = ("arith" if arith else "decl") if g.get("long_double") else ("inactive" if f.get("long_double") else "")
    d["ld_printf"] = g.get("printf_L", 0)
    d["ld_mathl"] = g.get("math_l_funcs", 0)
    d["int128"] = g.get("int128", 0)
    d["cx"] = g.get("Complex", 0)
    d["cx_h"] = "complex.h" in inc
    d["vla"] = len(dg("clang-gnu17", p, "-Wvla"))
    thr = []
    if g.get("pthread_calls"):
        thr.append("pthread")
    if g.get("Thread_local"):
        thr.append("TLS")
    if g.get("Atomic_kw") or g.get("atomic_builtins"):
        thr.append("atomics")
    d["thr"] = thr
    d["thr_inactive"] = bool(f.get("pthread_calls") or f.get("Thread_local") or f.get("Atomic_kw")) and not thr
    c11 = []
    if g.get("c11_keyword") and f.get("c11_keyword"):  # spelled by the program, not only by glibc macros
        c11.append("C11 keyword")
    if inc & C11_HDR:
        c11.append(", ".join(sorted(inc & C11_HDR)))
    for x in dg("clang-gnu99", p, "-Wc11-extensions"):
        w = re.search(r"'(_\w+)'", x[4])
        if w and not f.get("c11_keyword"):
            continue  # spelled by a system-header macro (glibc's strchr), not the program
        c11.append(x[4])
    d["c11"] = sorted(set(c11))
    c99 = Counter()
    for x in dg("clang-gnu89", p):
        if x[3] in ("-Wdeclaration-after-statement",):
            c99["mixed decls"] += 1
        elif x[3] == "-Wlong-long":
            c99["long long"] += 1
        elif x[3] == "-Wvla-extension":
            c99["VLA"] += 1
        elif x[3] == "-Wc99-extensions":
            m = x[4]
            k = ("for-init decl" if "for loop" in m else "_Bool" if "_Bool" in m else "flexible array" if "flexible" in m
                 else "compound literal" if "compound literal" in m else "hex float" if "hexadecimal" in m
                 else "non-constant aggregate init" if "aggregate" in m else "_Complex" if "_Complex" in m else m[:40])
            c99[k] += 1
        elif x[2] != "warning" and "restrict" in x[4]:
            c99["restrict"] += 1
    if f.get("line_comment"):
        c99["// comments"] += f["line_comment"]
    if g.get("inline_kw"):
        c99["inline"] += g["inline_kw"]
    restrict_ident = bool(dg("clang-gnu17", p, sub="restrict", sev="error"))  # pre-C99 code using it as a name
    if restrict_ident:
        c99.pop("restrict", None)
    elif g.get("restrict_kw"):
        c99["restrict"] += g["restrict_kw"]
    if f.get("variadic_macro"):
        c99["variadic macro"] += f["variadic_macro"]
    for h in sorted(inc & C99_HDR):
        c99["<" + h + ">"] += 1
    d["c99"] = c99
    c23 = [x[4] for x in dg("clang-gnu17", p, "-Wc23-extensions")] + [x[4] for x in dg("clang-gnu17", p, sub="is a C23 extension") if x[3] != "-Wc23-extensions"]
    for k in ("nullptr", "constexpr", "c23_attr", "embed", "BitInt", "typeof_plain"):
        if g.get(k):
            c23.append(k)
    if inc & C23_HDR:
        c23.append(", ".join(sorted(inc & C23_HDR)))
    d["c23"] = sorted(set(c23))
    d["knr_def"] = len(dg("clang-gnu17", p, "-Wdeprecated-non-prototype", "a function definition without a prototype"))
    d["noproto_call"] = len(dg("clang-gnu17", p, "-Wdeprecated-non-prototype", "passing arguments to"))
    d["noproto_conflict"] = len(dg("clang-gnu17", p, "-Wdeprecated-non-prototype", "zero-parameter prototype"))
    d["impl_int"] = len(dg("clang-gnu17", p, "-Wimplicit-int"))
    d["impl_decl"] = len(dg("clang-gnu17", p, "-Wimplicit-function-declaration"))
    for cfg in ("gcc-default", "gcc-gnu17", "gcc-gnu11", "gcc-gnu99", "gcc-gnu89", "gcc-pinned"):
        errs = dg(cfg, p, sev="error")
        d[cfg] = (len(errs), Counter(gcc_err_class(x[4]) for x in errs))
    gnu = []
    for fl, lab in (("-Wgnu-label-as-value", "computed goto"), ("-Wgnu-imaginary-constant", "imaginary constant"),
                    ("-Wgnu-zero-variadic-macro-arguments", ", ##__VA_ARGS__"), ("-Wvariadic-macros", "named variadic macro"),
                    ("-Wgnu-statement-expression", "statement expression"), ("-Wgnu-case-range", "case range"),
                    ("-Wzero-length-array", "zero-length array"), ("-Wgnu-empty-struct", "empty struct"),
                    ("-Wgnu-conditional-omitted-operand", "?: omitted operand"), ("-Wgnu-pointer-arith", "void* arithmetic"),
                    ("-Wpointer-arith", "void* arithmetic"), ("-Wgnu-folding-constant", "folded VLA bound")):
        if dg("clang-gnu17", p, fl):
            gnu.append(lab)
    if g.get("vector_size"):
        gnu.append("vector_size")
    if g.get("alloca") or pp["builtins"].get("__builtin_alloca"):
        gnu.append("alloca")
    if g.get("inline_asm"):
        gnu.append("inline asm")
    if g.get("typeof_gnu"):
        gnu.append("__typeof__")
    if g.get("Complex") and re.search(r"__complex__", open(os.path.join(sys.argv[4], s["files"][0]), encoding="latin-1").read() if s.get("files") else ""):
        gnu.append("__complex__")
    if dg("clang-gnu17", p, sub="function definition is not allowed here"):
        gnu.append("nested function")
    d["gnu"] = sorted(set(gnu))
    d["attrs"] = dict(pp["attributes"])
    d["builtins"] = {k: v for k, v in pp["builtins"].items() if k not in VA_MACRO_BUILTINS}
    d["builtins_spelled"] = dict(s.get("builtins", {}))
    d["attrs_spelled"] = dict(s.get("attributes", {}))
    d["pragmas"] = dict(pp.get("pragmas", {}))
    d["setjmp"] = g.get("setjmp", 0)
    d["signal"] = g.get("signal", 0)
    d["va_start"] = f.get("va_start", 0) if pp["builtins"].get("__builtin_va_start") else 0
    d["bitfield"] = g.get("bitfield", 0)
    d["hexfloat"] = g.get("hex_float", 0)
    d["inc"] = sorted(inc)
    rev = "C89"
    if c99:
        rev = "C99"
    if d["c11"]:
        rev = "C11"
    if d["c23"]:
        rev = "C23/GNU"
    d["needs"] = rev
    # newest and oldest GNU dialect GCC 16 accepts with the program's own flags
    ok = [std for std, cfg in (("gnu89", "gcc-gnu89"), ("gnu99", "gcc-gnu99"), ("gnu11", "gcc-gnu11"),
                               ("gnu17", "gcc-gnu17"), ("gnu23", "gcc-default")) if d[cfg][0] == 0]
    d["ok"] = ok
    return d


DER = {}


def der(p):
    if key(p) not in DER:
        DER[key(p)] = derive(p)
    return DER[key(p)]


def span(ok):
    if not ok:
        return "none"
    order = ["gnu89", "gnu99", "gnu11", "gnu17", "gnu23"]
    idx = [order.index(o) for o in ok]
    if idx == list(range(min(idx), max(idx) + 1)):
        return ok[0] if len(ok) == 1 else f"{ok[0]}–{ok[-1]}"
    return ", ".join(ok)


def table_FEATURES():
    hdr = ("| # | Program | Needs | GCC 16 accepts | `long double` | `_Complex` | VLA | K&R defs | `f()` called with args | "
           "`f()` decl conflicts | implicit int | implicit decl | gnu23 errors (class) | GNU extensions reached |")
    lines = [hdr, "|" + "---|" * 14]
    for i, p in enumerate(sorted(PROGS, key=lambda p: (p["dir"], p["name"])), 1):
        d = der(p)
        n23, c23 = d["gcc-default"]
        cls = "; ".join(f"{k} {v}" for k, v in c23.most_common()) if n23 else "0"
        ld = d["ld"] or "—"
        cx = (f"yes{' (complex.h)' if d['cx_h'] else ''}" if d["cx"] else "—")
        def z(v):
            return str(v) if v else "—"
        lines.append(f"| {i} | {pname(p)} | {d['needs']} | {span(d['ok'])} | {ld} | {cx} | {z(d['vla'])} | {z(d['knr_def'])} | "
                     f"{z(d['noproto_call'])} | {z(d['noproto_conflict'])} | {z(d['impl_int'])} | {z(d['impl_decl'])} | "
                     f"{n23 and f'{n23}: {cls}' or '0'} | {', '.join(d['gnu']) or '—'} |")
    return "\n".join(lines)


def names(ps, limit=None):
    out = []
    for p in ps:
        out.append(pname(p))
    if limit and len(out) > limit:
        return ", ".join(out[:limit]) + f" … ({len(out) - limit} more)"
    return ", ".join(out)


def table_FEATURE_COUNTS():
    rows = []

    def add(label, pred, how, limit=40):
        ps = [p for p in PROGS if pred(der(p))]
        ct = [p for p in ps if p["name"] in CTMARK]
        rows.append(f"| {label} | {len(ps)} | {len(ct)} | {names(ps, limit) or '—'} | {how} |")
    add("`long double` arithmetic", lambda d: d["ld"] == "arith", "gcc -E reached + clang AST")
    add("`long double` only in inactive `#if` branches", lambda d: d["ld"] == "inactive", "grep hit, absent after gcc -E")
    add("`%Lf`/`%Le`/`%Lg`/`%La` formats", lambda d: d["ld_printf"], "string literals after gcc -E")
    add("`<math.h>` `*l` functions, `strtold`", lambda d: d["ld_mathl"], "gcc -E")
    add("`__int128`, `__uint128_t`, `mode(TI)`", lambda d: d["int128"], "grep and gcc -E")
    add("`_BitInt`", lambda d: "BitInt" in d["c23"], "gcc -E")
    add("`_Complex`/`__complex__`/`complex`", lambda d: d["cx"], "gcc -E")
    add("`<tgmath.h>`", lambda d: "tgmath.h" in d["inc"], "includes (grep)")
    add("`<fenv.h>`", lambda d: "fenv.h" in d["inc"], "includes (grep)")
    add("VLA", lambda d: d["vla"], "clang -Wvla")
    add("`_Atomic`, `<stdatomic.h>`, `__atomic_*`/`__sync_*`", lambda d: "atomics" in d["thr"], "gcc -E")
    add("`_Thread_local`/`__thread`", lambda d: "TLS" in d["thr"], "gcc -E")
    add("pthread calls reached", lambda d: "pthread" in d["thr"], "gcc -E")
    add("pthread/TLS/atomics only in inactive branches", lambda d: d["thr_inactive"], "grep hit, absent after gcc -E")
    add("any C11 construct or C11 header spelled by the program", lambda d: d["c11"], "gcc -E keywords, includes, clang -std=gnu99 -Wc11-extensions")
    add("any C99 construct (see 4.2)", lambda d: d["c99"], "clang -std=gnu89 -pedantic, grep", 20)
    add("C23 construct or extension (`{}` initializer, `#warning`, …)", lambda d: d["c23"], "clang -Wc23-extensions, grep")
    add("K&R function definitions", lambda d: d["knr_def"], "clang -Wdeprecated-non-prototype", 60)
    add("calls with arguments to a `()` declaration", lambda d: d["noproto_call"], "clang -Wdeprecated-non-prototype", 60)
    add("`()` declaration that conflicts once `()` means `(void)`", lambda d: d["noproto_conflict"], "clang -Wdeprecated-non-prototype", 60)
    add("implicit int", lambda d: d["impl_int"], "clang -Wimplicit-int", 60)
    add("implicit function declarations", lambda d: d["impl_decl"], "clang -Wimplicit-function-declaration")
    add("hex float literals", lambda d: d["hexfloat"], "gcc -E + clang gnu89")
    add("`restrict` keyword", lambda d: d["c99"].get("restrict"), "gcc -E", 12)
    add("`inline` keyword", lambda d: d["c99"].get("inline"), "gcc -E", 12)
    add("flexible array members", lambda d: d["c99"].get("flexible array"), "clang -std=gnu89 -pedantic")
    add("compound literals", lambda d: d["c99"].get("compound literal"), "clang -std=gnu89 -pedantic")
    add("variadic macros (`__VA_ARGS__` or named)", lambda d: d["c99"].get("variadic macro") or "named variadic macro" in d["gnu"], "grep `#define f(...)`, clang")
    add("setjmp/longjmp", lambda d: d["setjmp"], "gcc -E")
    add("`signal`/`sigaction` calls", lambda d: d["signal"], "gcc -E")
    add("variadic function definitions (`va_start`)", lambda d: d["va_start"], "grep `va_start`, reached `__builtin_va_start`")
    add("bitfields", lambda d: d["bitfield"], "regex on gcc -E (approximate)")
    add("computed goto / labels as values", lambda d: "computed goto" in d["gnu"], "clang -Wgnu-label-as-value")
    add("`vector_size`", lambda d: "vector_size" in d["gnu"], "gcc -E")
    add("`alloca`/`__builtin_alloca`", lambda d: "alloca" in d["gnu"], "gcc -E")
    add("inline asm reached", lambda d: "inline asm" in d["gnu"], "gcc -E")
    add("statement expressions", lambda d: "statement expression" in d["gnu"], "clang -Wgnu-statement-expression")
    add("nested functions", lambda d: "nested function" in d["gnu"], "clang error")
    add("zero-length arrays", lambda d: "zero-length array" in d["gnu"], "clang -Wzero-length-array")
    add("case ranges", lambda d: "case range" in d["gnu"], "clang -Wgnu-case-range")
    add("`__typeof__`/`typeof`", lambda d: "__typeof__" in d["gnu"] or "typeof_plain" in d["c23"], "gcc -E")
    return "\n".join(["| Feature | Programs | of CTMark 6 | Which | Detected by |", "|---|---|---|---|---|"] + rows)


def table_REVISIONS():
    c = Counter(der(p)["needs"] for p in PROGS)
    ct = defaultdict(list)
    for p in PROGS:
        if p["name"] in CTMARK:
            ct[der(p)["needs"]].append(CTMARK[p["name"]])
    lines = ["| Newest revision whose features the program spells | Programs | CTMark |", "|---|---|---|"]
    for r in ("C89", "C99", "C11", "C23/GNU"):
        lines.append(f"| {r} | {c.get(r, 0)} | {', '.join(ct.get(r, [])) or '—'} |")
    lines += ["", "| C99 construct (clang `-std=gnu89 -pedantic` unless noted) | Programs |", "|---|---|"]
    cc = Counter()
    for p in PROGS:
        for k in der(p)["c99"]:
            cc[k] += 1
    for k, v in cc.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "| GNU dialects GCC 16 accepts (program's own flags) | Programs | CTMark |", "|---|---|---|"]
    sc = Counter(span(der(p)["ok"]) for p in PROGS)
    sct = defaultdict(list)
    for p in PROGS:
        if p["name"] in CTMARK:
            sct[span(der(p)["ok"])].append(CTMARK[p["name"]])
    for k, v in sc.most_common():
        lines.append(f"| {k} | {v} | {', '.join(sct.get(k, [])) or '—'} |")
    gnu = [p for p in PROGS if der(p)["gnu"]]
    lines += ["", f"Programs reaching at least one GNU language extension (excluding `__attribute__` and `__builtin_*`, counted separately in 4.4): **{len(gnu)}**: " + names(gnu) + "."]
    return "\n".join(lines)


def table_GNU23():
    lines = ["| Configuration (GCC 16.1 on Darwin, glibc 2.43 headers, program's own `-D`/`-I`/`-W`/`-f` flags) | Programs with errors | of CTMark 6 | Which |", "|---|---|---|---|"]
    for cfg, lab in (("gcc-default", "default dialect (`gnu23`), every program"), ("gcc-gnu17", "`-std=gnu17`, every program"),
                     ("gcc-gnu11", "`-std=gnu11`, every program"), ("gcc-gnu99", "`-std=gnu99`, every program"),
                     ("gcc-gnu89", "`-std=gnu89`, every program"),
                     ("gcc-pinned", "the dialect the suite passes (C_STANDARD pin or own `-std=`, else default `gnu23`)")):
        ps = [p for p in PROGS if der(p)[cfg][0]]
        ct = [CTMARK[p["name"]] for p in ps if p["name"] in CTMARK]
        lines.append(f"| {lab} | {len(ps)} | {len(ct)}{': ' + ', '.join(ct) if ct else ''} | {names(ps, 60)} |")
    cls = Counter()
    progs_by = defaultdict(set)
    for p in PROGS:
        n, c = der(p)["gcc-default"]
        for k, v in c.items():
            cls[k] += v
            progs_by[k].add(p["name"])
    lines += ["", "| gnu23 error class (message-based) | Errors | Programs |", "|---|---|---|"]
    for k, v in cls.most_common():
        lines.append(f"| {k} | {v} | {len(progs_by[k])} |")
    fail23 = [p for p in PROGS if der(p)["gcc-default"][0]]
    pinned = [p for p in fail23 if p["c_standard"] or any(f.startswith("-std=") for f in (p["CFLAGS"] or []))]
    unp = [p for p in fail23 if p not in pinned]
    lines += ["", f"Of the {len(fail23)} programs that fail at `gnu23`, {len(pinned)} carry a pin that keeps the suite from compiling them at `gnu23`, and {len(unp)} do not: {names(unp)}."]
    allpinned = [p for p in PROGS if p["c_standard"] in ("17", "90")]
    passing_pinned = [p for p in allpinned if not der(p)["gcc-default"][0]]
    lines.append(f"Of the {len(allpinned)} programs pinned to `C_STANDARD 17` or `90`, {len(passing_pinned)} compile at `gnu23` anyway: {names(passing_pinned) or '—'}.")
    return "\n".join(lines)


def table_FALLOUT():
    rows = ["| If the slice dropped | Programs that fall out | CTMark six | Which | Basis |", "|---|---|---|---|---|"]

    def add(label, pred, basis):
        ps = [p for p in PROGS if pred(der(p))]
        ct = {CTMARK[p["name"]] for p in ps if p["name"] in CTMARK}
        ctxt = "; ".join(f"{v} {'out' if v in ct else 'in'}" for v in ("sqlite3", "ClamAV", "consumer-typeset", "lencod", "mafft", "SPASS"))
        rows.append(f"| {label} | **{len(ps)}** | {ctxt} | {names(ps) or '—'} | {basis} |")
    add("`long double` (binary128)", lambda d: d["ld"] in ("arith", "decl") or d["ld_printf"] or d["ld_mathl"], "reached after `gcc -E`; AST confirms arithmetic")
    add("`__int128`", lambda d: d["int128"], "no occurrence, even in inactive branches")
    add("`_Complex`", lambda d: d["cx"], "reached after `gcc -E`")
    add("VLAs", lambda d: d["vla"], "clang `-Wvla` in program source")
    add("`_Atomic` and threads (`<threads.h>`, pthreads, TLS)", lambda d: d["thr"], "reached after `gcc -E`")
    add("C11 as a whole (language features and C11 headers spelled by the program)", lambda d: d["c11"], "see 4.2; glibc's own `_Generic` macros are section C")
    add("C11 as a whole, counted by GCC 16 failing at `-std=gnu99`", lambda d: d["gcc-gnu99"][0] and not d["gcc-gnu17"][0], "compiles at gnu17 but not gnu99")
    add("pre-C23 rules: slice compiles only with C23 rules (GCC 15's default `gnu23`)", lambda d: d["gcc-default"][0], "GCC 16 errors at `gnu23`")
    add("C99 as a whole, ISO reading: slice is strict C89", lambda d: d["c99"], "program spells any C99 construct (4.2)")
    add("C99 as a whole, GCC reading: slice is `gnu89` (GCC accepts many C99 features there as extensions)", lambda d: d["gcc-gnu89"][0], "GCC 16 errors at `-std=gnu89`")
    return "\n".join(rows)


def table_HEADERS():
    c = Counter()
    for p in PROGS:
        for h in der(p)["inc"]:
            c[h] += 1
    std = ("assert.h complex.h ctype.h errno.h fenv.h float.h inttypes.h iso646.h limits.h locale.h math.h setjmp.h "
           "signal.h stdalign.h stdarg.h stdatomic.h stdbit.h stdbool.h stdckdint.h stddef.h stdint.h stdio.h stdlib.h "
           "stdnoreturn.h string.h tgmath.h threads.h time.h uchar.h wchar.h wctype.h").split()
    iso = [f"`<{h}>` {c[h]}" for h in std if c.get(h)]
    other = [f"`<{h}>` {v}" for h, v in sorted(c.items(), key=lambda x: (-x[1], x[0])) if h not in std]
    return (f"**ISO C headers** ({len(iso)} of the {len(std)} in C23), with the number of programs: " + ", ".join(iso) +
            f".\n\n**Other headers** ({len(other)}: POSIX, Linux, BSD and non-portable): " + ", ".join(other) + ".")


def table_ATTRS():
    a, b, asp, bsp, pr = Counter(), Counter(), Counter(), Counter(), Counter()
    for p in PROGS:
        d = der(p)
        for k in d["attrs"]:
            a[k] += 1
        for k in d["builtins"]:
            b[k] += 1
        for k in d["attrs_spelled"]:
            asp[k] += 1
        for k in d["builtins_spelled"]:
            bsp[k] += 1
        for k in d["pragmas"]:
            pr[k] += 1
    def fmt(cn):
        return ", ".join(f"`{k}` {v}" for k, v in sorted(cn.items(), key=lambda x: (-x[1], x[0]))) or "none"
    return "\n".join([
        f"- **`__attribute__` names reached after `gcc -E`** (programs): {fmt(a)}.",
        f"- **`__attribute__` names spelled anywhere in program files, any branch** (programs): {fmt(asp)}.",
        f"- **`__builtin_*` reached after `gcc -E`**, without `__builtin_va_*` from `<stdarg.h>` (programs): {fmt(b)}.",
        f"- **`__builtin_*` spelled anywhere in program files, any branch** (programs): {fmt(bsp)}.",
        f"- **`#pragma`s reached after `gcc -E`** (programs): {fmt(pr)}."])


def table_LONGDOUBLE():
    lines = ["| Program | `long double` expression nodes in program files (clang AST, gnu17, aarch64-linux-gnu) | Distinct source lines |", "|---|---|---|"]
    for n, v in LD.items():
        nodes = ", ".join(f"{k} {c}" for k, c in sorted(v["nodes"].items(), key=lambda x: -x[1])) or "none (all hits are in inactive branches)"
        lines.append(f"| {n} | {nodes} | {v['sites']} |")
    return "\n".join(lines)


TORT = load("torture.json")
GLIBC = load("glibc.json")


def table_TORTURE():
    d = TORT
    f = d["features"]
    order = [("nested function (clang)", "nested functions (clang: \"function definition is not allowed here\")"),
             ("long double", "`long double`"), ("__int128", "`__int128`, `__int128_t`, `__uint128_t`, `mode(TI)`"),
             ("_Complex (any)", "`_Complex`, `__complex__`, `__real__`/`__imag__`, `<complex.h>`"),
             ("complex integer", "of which complex integer types (`_Complex int`, `__complex__ char`, …)"),
             ("vector_size", "`vector_size`"), ("VLA (clang -Wvla)", "VLAs (clang `-Wvla`)"),
             ("labels as values (clang)", "computed goto / labels as values (clang `-Wgnu-label-as-value`)"),
             ("computed goto (grep)", "computed goto / labels as values (grep `goto *`, `&&label`; includes false positives)"),
             ("any __builtin_*", "any `__builtin_*`"), ("inline asm", "inline asm (`asm`/`__asm__` followed by `(`)"),
             ("_Atomic", "`_Atomic`, `<stdatomic.h>`"), ("__atomic_/__sync_ builtins", "`__atomic_*`/`__sync_*` calls"),
             ("_BitInt", "`_BitInt`"), ("_Float16/32/64/128", "`_FloatN`"), ("setjmp/longjmp", "setjmp/longjmp, including `__builtin_setjmp`"),
             ("statement expression", "statement expressions (grep `({`)"), ("__attribute__", "`__attribute__`"),
             ("has an options/target dg- directive", "an options or target `dg-` directive (list below)"),
             ("has a .x control file", "a `.x` Tcl control file beside it")]
    lines = ["| Tests using | Tests | Share |", "|---|---|---|"]
    for k, lab in order:
        n = f.get(k, 0)
        lines.append(f"| {lab} | {n} | {100.0 * n / d['tests']:.1f}% |")
    lines += ["", "**Top 30 `__builtin_*` by number of tests:** " +
              ", ".join(f"`{b}` {n}" for b, n in d["builtins_by_tests"][:30]) + "."]
    lines += ["", "**`dg-` directive kinds (tests):** " + ", ".join(f"`{k}` {n}" for k, n in d["dg_kinds"]) + "."]
    lines += ["", "**Options in `dg-options`/`dg-additional-options` (tests, top 20):** " +
              ", ".join(f"`{k}` {n}" for k, n in d["dg_options"][:20]) + "."]
    lines += ["", "**Target and skip directives (tests, top 20):** " +
              "; ".join(f"`{k}` {n}" for k, n in d["dg_targets"][:20]) + "."]
    return "\n".join(lines)


def table_GLIBC_PAIRS():
    lines = ["| Configuration pair (gcc-16, aarch64-linux-gnu identity, 47 root headers) | Header lines present only in the first | Constructs in those lines (lines) |", "|---|---|---|"]
    for k, v in GLIBC["pairs"].items():
        cs = ", ".join(f"{c} {x['n']}" for c, x in sorted(v["constructs"].items(), key=lambda y: -y[1]["n"]))
        lines.append(f"| `{k}` | {v['lines']} | {cs or '—'} |")
    return "\n".join(lines)

UNIQ_LINES = {}


def main():
    tpl, out = sys.argv[2], sys.argv[3]
    lts = sys.argv[4]
    for r in SCAN.values():
        for f in r["files"]:
            if f not in UNIQ_LINES and lts:
                UNIQ_LINES[f] = open(os.path.join(lts, f), encoding="latin-1").read().count("\n")
    text = open(tpl).read()

    def rep(m):
        fn = globals().get("table_" + m.group(1))
        if not fn:
            return f"*(table {m.group(1)} not generated yet)*"
        try:
            return fn()
        except Exception as e:  # missing data for a later stage
            return f"*(table {m.group(1)} not available: {type(e).__name__}: {e})*"
    text = re.sub(r"\{\{([A-Z0-9_]+)\}\}", rep, text)
    open(out, "w").write(text)


if __name__ == "__main__":
    main()
