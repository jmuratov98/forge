#!/usr/bin/env python3
"""Generate the Markdown tables for docs/research/host-header-extensions.md
and splice them into a template at <!-- GEN:name --> markers.

usage: report.py OUTDIR MANIFEST GCCSRC_DIR TEMPLATE_MD OUT_MD
"""
import collections
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx  # noqa: E402

GCC = "https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/"
CPP = "https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/"
CFG_ORDER = ["m1", "m1-O0", "m1-fortify", "gcc-eh", "m1-gnu", "clang", "neither"]

# ---------------------------------------------------------------------------
# manual pages for non-builtin extensions: name -> (manual, page)
PAGES = {
    "__extension__": ("gcc", "Alternate-Keywords.html"),
    "__typeof__": ("gcc", "Typeof.html"), "__typeof": ("gcc", "Typeof.html"),
    "typeof": ("gcc", "Typeof.html"), "__auto_type": ("gcc", "Typeof.html"),
    "__decltype": ("gcc", "Alternate-Keywords.html"),
    "__alignof__": ("gcc", "Alignment.html"), "__alignof": ("gcc", "Alignment.html"),
    "__restrict": ("gcc", "Restricted-Pointers.html"), "__restrict__": ("gcc", "Restricted-Pointers.html"),
    "__inline": ("gcc", "Alternate-Keywords.html"), "__inline__": ("gcc", "Alternate-Keywords.html"),
    "__const": ("gcc", "Alternate-Keywords.html"), "__volatile": ("gcc", "Alternate-Keywords.html"),
    "__signed": ("gcc", "Alternate-Keywords.html"), "__signed__": ("gcc", "Alternate-Keywords.html"),
    "__complex__": ("gcc", "Complex.html"), "__complex": ("gcc", "Complex.html"),
    "__real__": ("gcc", "Complex.html"), "__real": ("gcc", "Complex.html"),
    "__imag__": ("gcc", "Complex.html"), "__imag": ("gcc", "Complex.html"),
    "_Complex": ("gcc", "Complex.html"), "imaginary constant suffix": ("gcc", "Complex.html"),
    "__label__": ("gcc", "Local-Labels.html"), "__thread": ("gcc", "Thread_002dLocal.html"),
    "__null": ("gcc", "C_002b_002b-Extensions.html"),
    "__FUNCTION__": ("gcc", "Function-Names.html"), "__PRETTY_FUNCTION__": ("gcc", "Function-Names.html"),
    "__attribute__": ("gcc", "Attribute-Syntax.html"), "__attribute": ("gcc", "Attribute-Syntax.html"),
    "__int128": ("gcc", "_005f_005fint128.html"), "__int128_t": ("gcc", "_005f_005fint128.html"),
    "__uint128_t": ("gcc", "_005f_005fint128.html"),
    "__float128": ("gcc", "Floating-Types.html"), "__float80": ("gcc", "Floating-Types.html"),
    "__ibm128": ("gcc", "Floating-Types.html"),
    "_Float16": ("gcc", "Floating-Types.html"), "_Float32": ("gcc", "Floating-Types.html"),
    "_Float64": ("gcc", "Floating-Types.html"), "_Float128": ("gcc", "Floating-Types.html"),
    "_Float32x": ("gcc", "Floating-Types.html"), "_Float64x": ("gcc", "Floating-Types.html"),
    "_Float128x": ("gcc", "Floating-Types.html"),
    "__bf16": ("gcc", "Half_002dPrecision.html"), "__fp16": ("gcc", "Half_002dPrecision.html"),
    "pp-number suffix bf16": ("gcc", "Half_002dPrecision.html"),
    "pp-number suffix BF16": ("gcc", "Half_002dPrecision.html"),
    "statement expression ({ ... })": ("gcc", "Statement-Exprs.html"),
    "zero-length array member": ("gcc", "Zero-Length.html"),
    "flexible array member": ("gcc", "Zero-Length.html"),
    "named variadic macro parameter": ("cpp", "Variadic-Macros.html"),
    "GNU comma paste (, ## __VA_ARGS__)": ("cpp", "Variadic-Macros.html"),
    "conditional with omitted operand (?:)": ("gcc", "Conditionals.html"),
    "case range": ("gcc", "Case-Ranges.html"), "computed goto": ("gcc", "Labels-as-Values.html"),
    "asm label (symbol rename)": ("gcc", "Asm-Labels.html"),
    "inline asm (basic)": ("gcc", "Basic-Asm.html"), "inline asm (extended)": ("gcc", "Extended-Asm.html"),
    "#include_next": ("cpp", "Wrapper-Headers.html"), "#warning": ("cpp", "Diagnostics.html"),
    "#pragma GCC system_header": ("cpp", "System-Headers.html"),
    "#pragma GCC diagnostic": ("gcc", "Diagnostic-Pragmas.html"),
    "#pragma GCC visibility": ("gcc", "Visibility-Pragmas.html"),
    "#pragma GCC unroll": ("gcc", "Loop_002dSpecific-Pragmas.html"),
    "#pragma #": ("cpp", "Pragmas.html"),
    "_Atomic": ("gcc", "Standards.html"), "_Bool": ("gcc", "Standards.html"),
    "_Generic": ("gcc", "Standards.html"), "_Static_assert": ("gcc", "Standards.html"),
    "_Alignas": ("gcc", "Standards.html"), "_Alignof": ("gcc", "Standards.html"),
    "_Noreturn": ("gcc", "Standards.html"), "long double": ("gcc", "Floating-Types.html"),
}
NOTE_OVERRIDE = {
    "__extension__": "Suppresses -pedantic warnings for the following expression or declaration; no semantics.",
    "__decltype": "Alternate spelling of decltype accepted in all modes (libstdc++ uses it before C++11 checks).",
    "__null": "g++'s null pointer constant; GCC's stddef.h defines NULL as __null in C++ (C++ Extensions).",
    "__restrict": "Restricted pointer qualifier accepted in C++; an aliasing promise that may be ignored.",
    "__restrict__": "Restricted pointer qualifier accepted in C++; an aliasing promise that may be ignored.",
    "__complex__": "GNU complex type specifier; std::complex<float/double/long double> store __complex__ T.",
    "__real__": "Extracts the real part of a complex value (lvalue).", "__imag__": "Extracts the imaginary part of a complex value (lvalue).",
    "long double": "ISO type, listed because Forge's own code avoids it; on aarch64 it is IEEE binary128.",
    "asm label (symbol rename)": "Declarator followed by __asm__(\"name\") sets the assembler (link) name.",
    "zero-length array member": "Trailing T x[0] member; GCC extension in C++ (Zero Length Arrays).",
    "flexible array member": "Trailing T x[] member; C99 in C, GCC extension in C++.",
    "pp-number suffix bf16": "bf16 literal suffix for __bf16 constants.",
    "pp-number suffix BF16": "BF16 literal suffix for __bf16 constants.",
    "#pragma #": "_Pragma built by stringizing a macro argument (the pragma text is supplied by the caller).",
}

# Observation class per extension: M = semantics observable (types, values,
# ABI, symbols, constant evaluation, control flow); A = accept and may ignore
# (diagnostic or optimisation hint only); L = may be lowered to a call to the
# named libc/libm function or to the identity.  Unlisted builtins default to L
# if they are library builtins, else M.  Attributes default to A.
CLASS_M_ATTR = {"aligned", "packed", "mode", "vector_size", "may_alias", "abi_tag",
                "weak", "weakref", "alias", "gnu_inline", "transparent_union",
                "cleanup", "aarch64_vector_pcs", "section", "tls_model", "init_priority",
                "returns_twice", "neon_vector_type", "common", "nocommon",
                "ifunc", "symver", "copy"}
CLASS_NOTE_ATTR = {
    "always_inline": "Forge: GCC errors when it cannot inline; ignoring the attribute preserves behaviour.",
    "gnu_inline": "Forge: extern inline + gnu_inline must never emit an out-of-line body (the symbol is libc's).",
    "abi_tag": "Forge: changes mangled names (B5cxx11) of symbols exported by libstdc++.so.",
    "visibility": "Forge: linkage only; no effect on a PIE that exports nothing.",
    "may_alias": "Forge: matters only to an optimiser that does type-based alias analysis.",
    "noreturn": "Forge: ignoring is safe for correct code; affects code generation and warnings only.",
    "returns_twice": "Forge: setjmp-like calls; an optimiser must not keep values in registers across them.",
    "assume": "Forge: ignoring is safe; acting on it is an optimisation.",
    "copy": "Forge: copies another declaration's attributes; its class is that of the copied set.",
    "weak": "Forge: weak undefined reference to __pthread_unwind_next (pthread.h:753) if referenced.",
    "mode": "Forge: cxxabi_tweaks.h:46 `__guard` is `int __attribute__((mode (__DI__)))`, a 64-bit guard type.",
}
CLASS_A_BUILTIN = {"__builtin_expect", "__builtin_expect_with_probability", "__builtin_prefetch",
                   "__builtin_assume_aligned", "__builtin_object_size",
                   "__builtin_dynamic_object_size", "__builtin_ia32_pause"}
CLASS_NOTE_BUILTIN = {
    "__builtin_expect": "Forge: identity on the value is a correct implementation.",
    "__builtin_constant_p": "Forge: 0 is correct at run time (manual), but char_traits::move (bits/char_traits.h:233) "
                            "calls it during constant evaluation and needs 1 for a foldable pointer comparison.",
    "__builtin_object_size": "Forge: the 'unknown' answer ((size_t)-1 for types 0/1) is correct (manual).",
    "__builtin_dynamic_object_size": "Forge: the 'unknown' answer is correct (manual).",
    "__builtin_assume_aligned": "Forge: identity on the pointer is correct.",
    "__builtin_unreachable": "Forge: any lowering (trap or nothing) is correct for programs that never reach it.",
    "__builtin_is_constant_evaluated": "Forge: must be exact; libstdc++ picks constexpr-only code with it.",
    "__builtin_launder": "Forge: identity is correct unless the optimiser assumes object identity.",
    "__builtin_clear_padding": "Forge: a no-op for types without padding; atomic<T> compare-exchange depends on it otherwise.",
    "__builtin_operator_new": "Reached only if __has_builtin(__builtin_operator_new) >= 201802L; the manual does not "
                              "give GCC's value (section 5).",
    "__builtin_operator_delete": "As __builtin_operator_new.",
    "__builtin_FILE": "Forge: its string is embedded at every assert() call site, so it is part of the output bytes.",
    "__builtin_alloca": "Forge: real stack allocation; used for buffers in <fstream> and <locale> code.",
}
FLOATN_NOTE = ("Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ "
               "(math.h __iseqsig_type specializations, bits/floatn.h).")
KW_NOTE = {
    "__int128": "Forge: every M1 use is gated on __SIZEOF_INT128__ (23 tests).",
    "__uint128_t": "Forge: unconditional; struct layout in asm/sigcontext.h and sys/user.h.",
    "_Float32": FLOATN_NOTE, "_Float64": FLOATN_NOTE, "_Float128": FLOATN_NOTE,
    "_Float32x": FLOATN_NOTE, "_Float64x": FLOATN_NOTE,
    "_Float16": "Forge: reached only through <format> under __FLT16_DIG__.",
    "long double": "Forge's own code avoids it, but the headers declare it 661 times (layout, mangling).",
    "__thread": "Forge: TLS variable in <mutex> under _GLIBCXX_HAVE_TLS.",
    "__null": "Forge: GCC's stddef.h defines NULL as __null when __GNUG__ is defined.",
    "pp-number suffix bf16": "Forge: c++config.h:889 `__decltype(0.0bf16)` whenever __BFLT16_DIG__ is predefined.",
    "#include_next": "Forge: needed by libstdc++'s <stdlib.h>/<math.h> wrappers and GCC's <limits.h>.",
    "__Float32x4_t": "Arm ACLE AdvSIMD type (not in the GCC manual); glibc vector-math declarations only.",
    "__Float64x2_t": "Arm ACLE AdvSIMD type (not in the GCC manual); glibc vector-math declarations only.",
    "__SVFloat32_t": "Arm ACLE sizeless SVE type (not in the GCC manual); glibc vector-math declarations only.",
    "__SVFloat64_t": "Arm ACLE sizeless SVE type (not in the GCC manual); glibc vector-math declarations only.",
    "__SVBool_t": "Arm ACLE sizeless SVE predicate type (not in the GCC manual); glibc vector-math declarations only.",
    "__is_identifier": "Clang-only operator; GCC 15.2 has none (c++config.h tests #ifdef __is_identifier).",
}
CLASS_NOTE_ATTR["aarch64_vector_pcs"] = ("Arm vector PCS (not in the GCC manual): changes callee-saved registers "
                                         "of glibc's _ZGVnN* vector-math declarations")
PAGES.update({"__has_attribute": ("cpp", "_005f_005fhas_005fattribute.html"),
              "__has_builtin": ("cpp", "_005f_005fhas_005fbuiltin.html"),
              "__has_extension": ("cpp", "_005f_005fhas_005fextension.html"),
              "__has_include": ("cpp", "_005f_005fhas_005finclude.html")})

# Preferred manual entry kind per attribute, where the first index entry is the
# wrong one for how the headers use the attribute.
ATTR_KIND_PREF = {"aligned": "type", "unused": "variable", "cold": "function", "deprecated": "function",
                  "may_alias": "type", "mode": "type", "packed": "type", "vector_size": "type",
                  "visibility": "function", "noreturn": "function", "const": "function"}


def first_sentence(t, limit=150):
    m = re.search(r"^(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + " ..."
    return s


def page_lead(manual_dir, page, cache={}):
    key = (manual_dir, page)
    if key in cache:
        return cache[key]
    p = os.path.join(manual_dir, page)
    s = ""
    if os.path.exists(p):
        t = open(p, encoding="utf-8").read()
        hm = re.search(r"<h[1-6][^>]*>.*?</h[1-6]>", t, re.S)
        body = t[hm.end():] if hm else t
        m = re.search(r"<p>(.*?)</p>", body, re.S)
        if m:
            s = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
            s = first_sentence(re.sub(r"\s+", " ", s).strip())
    cache[key] = s
    return s


def md(s):
    return s.replace("|", "\\|").replace("\n", " ")


def code(s):
    s = s.replace("|", "\\|")
    if "`" in s:
        return "``" + s + "``"
    return "`" + s + "`"


def short(f):
    return f.replace("/usr/include/c++/15/", "c++/").replace("/usr/include/aarch64-linux-gnu/c++/15/", "c++/aarch64/") \
        .replace("/usr/include/aarch64-linux-gnu/", "aarch64/").replace("/usr/lib/gcc/aarch64-linux-gnu/15/include/", "gcc/") \
        .replace("/usr/include/", "")


def guard_text(g):
    if not g:
        return "(unconditional)"
    if g["kind"] in ("else",):
        prev = g["chain"][-1] if g["chain"] else None
        t = "#else /* of #%s %s */" % (prev[0], prev[1]) if prev else "#else"
    elif g["kind"] in ("elif", "elifdef", "elifndef"):
        t = "#%s %s" % (g["kind"], g["text"])
    else:
        t = "#%s %s" % (g["kind"], g["text"])
    t = " ".join(t.split())
    if len(t) > 110:
        t = t[:107] + "..."
    return t


class Ctx:
    pass


def load(out, man_p, gsrc):
    c = Ctx()
    c.out = out
    c.scan = json.load(open(out + "/scan.json"))
    c.act = json.load(open(out + "/pp/active.json"))
    c.sets = {k: set(v["union"]) for k, v in c.act.items()}
    c.per_root = {k: {r: set(s) for r, s in v["per_root"].items()} for k, v in c.act.items()}
    c.man = json.load(open(out + "/manindex.json"))
    c.steer = json.load(open(out + "/steer.json"))
    c.closure = json.load(open(out + "/closure.json"))
    c.manifest = hx.load_manifest(man_p)
    c.marks = json.load(open(out + "/markers.json"))
    c.hb = json.load(open(out + "/gcc-hb.json"))
    c.gdir = os.path.join(os.path.dirname(out), "manual/gcc/gcc")
    c.cdir = os.path.join(os.path.dirname(out), "manual/cpp/cpp")
    # GCC tables for validating builtin names
    bdef = set()
    for m in re.finditer(r'^DEF_(\w+)\s*\(\s*BUILT_IN_\w+\s*,\s*"([^"]+)"', open(gsrc + "/builtins.def").read(), re.M):
        nm = m.group(2)
        # every DEF_*_BUILTIN wrapper passes "__builtin_" NAME to DEF_BUILTIN
        bdef.add("__builtin_" + nm)
        if "FLOATN" in m.group(1):
            for suf in ("f16", "f32", "f64", "f128", "f32x", "f64x", "f128x"):
                bdef.add("__builtin_" + nm + suf)
    for m in re.finditer(r'DEF_COROUTINE_BUILTIN\s*\(\s*\w+\s*,\s*"([^"]+)"', open(gsrc + "/coroutine-builtins.def").read()):
        bdef.add("__builtin_coro_" + m.group(1))
    cc = open(gsrc + "/c-common.cc").read()
    # builtin type names registered by c-common.cc (e.g. __builtin_va_list)
    for m in re.finditer(r'get_identifier \("(__builtin_\w+)"\)', cc):
        bdef.add(m.group(1))
    c.bdef = bdef
    rw = cc[cc.find("c_common_reswords[] ="):]
    c.reswords = set(re.findall(r'\{ "([^"]+)"', rw[:rw.find("\n};")]))
    c.cpdecl = set(re.findall(r'add_builtin_function\s*\(\s*"([^"]+)"', open(gsrc + "/cp-decl.cc").read()))
    c.traits = set(re.findall(r'^DEFTRAIT_\w+\s*\(\s*\w+\s*,\s*"([^"]+)"', open(gsrc + "/cp-trait.def").read(), re.M))
    c.expanded = {cfg: expanded_macros(c, cfg) for cfg in ("m1", "m1-O0", "m1-fortify", "gcc-eh", "m1-gnu", "clang", "neither")}
    return c


def expanded_macros(c, cfg):
    act = c.sets[cfg]
    used = set()
    for b, ids in c.scan["uses"].items():
        if b in act:
            used.update(ids)
    body_ids = collections.defaultdict(set)
    for d in c.scan["defines"]:
        if d["block"] in act:
            body_ids[d["name"]].update(re.findall(r"[A-Za-z_]\w*", d["body"]))
    # conditionals also expand macros (e.g. __GNUC_PREREQ, __glibc_has_attribute)
    for cd in c.scan["conds"]:
        if cd["block"] in act and cd["kind"] in ("if", "elif"):
            t = re.sub(r"\bdefined\s*\(?\s*\w+\s*\)?", " ", cd["text"])
            used.update(re.findall(r"[A-Za-z_]\w*", t))
    seen = set()
    work = [x for x in used if x in body_ids]
    while work:
        x = work.pop()
        if x in seen:
            continue
        seen.add(x)
        for y in body_ids[x]:
            if y in body_ids and y not in seen:
                work.append(y)
    return seen


def hit_live(c, h, cfg):
    if h["block"] not in c.sets[cfg]:
        return False
    if h["ctx"].startswith("define:"):
        return h["ctx"][7:] in c.expanded[cfg]
    return True


def hit_defined(c, h, cfg):
    return h["block"] in c.sets[cfg]


def status_of(c, hs):
    """Reachability label for a set of hits of one extension."""
    if any(hit_live(c, h, "m1") for h in hs):
        return "M1"
    if any(hit_defined(c, h, "m1") for h in hs):
        return "M1 macro only"
    for cfg, lab in (("m1-O0", "-O0 only"), ("m1-fortify", "fortify only"), ("gcc-eh", "EH/RTTI only"),
                     ("m1-gnu", "gnu++20 only"), ("clang", "clang identity only"), ("neither", "neither-identity only")):
        if any(hit_live(c, h, cfg) for h in hs):
            return lab
    for cfg, lab in (("m1-fortify", "fortify macro only"), ("gcc-eh", "EH macro only"), ("clang", "clang macro only")):
        if any(hit_defined(c, h, cfg) for h in hs):
            return lab
    return "not reached"


def roots_of(c, hs):
    rs = set()
    for h in hs:
        if not hit_live(c, h, "m1") or h["ctx"].startswith("define:"):
            continue
        for r, s in c.per_root["m1"].items():
            if h["block"] in s:
                rs.add(r)
    return rs


def rep_hit(c, hs):
    live = [h for h in hs if hit_live(c, h, "m1") and not h["ctx"].startswith("define:")]
    if not live:
        live = [h for h in hs if hit_live(c, h, "m1")]
    if not live:
        live = [h for h in hs if hit_defined(c, h, "m1")]
    pool = live or hs
    pool = sorted(pool, key=lambda h: (h["file"], h["line"]))
    return pool[0]


def manual_note(c, name, group):
    """(link markdown, sentence)"""
    if name in NOTE_OVERRIDE and name in PAGES:
        man, page = PAGES[name]
        base = GCC if man == "gcc" else CPP
        return "[%s](%s%s)" % (page.replace(".html", "").replace("_002d", "-").replace("_005f", "_").replace("_002b", "+").replace("_0028", "(").replace("_0029", ")"), base, page), NOTE_OVERRIDE[name]
    es = c.man["builtin"].get(name) if group in ("builtin", "trait", "atomic", "sync") else None
    if es:
        e = es[0]
        page = e["page"].split("/")[-1]
        base = GCC if e["page"].startswith("gcc/") else CPP
        return "[%s](%s%s#%s)" % (prettify(page), base, page, e["anchor"]), e["desc"]
    if group == "attribute":
        es = c.man["attribute"].get(name)
        if es:
            pref = [x for x in es if x["kind"] == ATTR_KIND_PREF.get(name)]
            e = (pref or es)[0]
            page = e["page"].split("/")[-1]
            return "[%s](%s%s#%s)" % (prettify(page), GCC, page, e["anchor"]), e["desc"]
        return "not in manual", ""
    if group in ("builtin",) and name.startswith("__builtin_"):
        base = name[len("__builtin_"):]
        if base in c.man["library_functions"]:
            return "[Library-Builtins](%sLibrary-Builtins.html)" % GCC, "Built-in version of the library function `%s`." % base
        stripped = re.sub(r"(f128x|f128|f64x|f64|f32x|f32|f16b|f16|d32|d64x|d64|d128)$", "", base)
        if stripped in c.man["library_functions"] or "__builtin_" + stripped in c.man["builtin"]:
            return "[Library-Builtins](%sLibrary-Builtins.html)" % GCC, "_FloatN/decimal variant of `%s`." % stripped
        if name in c.bdef:
            return "builtins.def (not in manual)", ""
        if name in c.cpdecl:
            return "cp/decl.cc (not in manual)", ""
        if name in c.reswords:
            return "c_common_reswords (not in manual)", ""
        return "**not a GCC 15.2 builtin**", ""
    if group == "trait":
        return "cp-trait.def (not in manual)", ""
    if name in PAGES:
        man, page = PAGES[name]
        base = GCC if man == "gcc" else CPP
        d = c.gdir if man == "gcc" else c.cdir
        return "[%s](%s%s)" % (prettify(page), base, page), page_lead(d, page)
    return "", ""


def prettify(page):
    p = page.replace(".html", "")
    p = re.sub(r"_00([0-9a-f]{2})", lambda m: chr(int(m.group(1), 16)), p)
    return p


# ---------------------------------------------------------------------------
BUILTIN_GROUPS = [
    ("varargs", lambda n: n.startswith("__builtin_va_") or n == "__builtin_c23_va_start"),
    ("fortify", lambda n: n in ("__builtin_object_size", "__builtin_dynamic_object_size")
     or re.match(r"__builtin___\w+_chk$", n) is not None),
    ("trait", lambda n: n in ("__builtin_is_corresponding_member",
                              "__builtin_is_pointer_interconvertible_with_class",
                              "__builtin_is_virtual_base_of")),
    ("constexpr", lambda n: n in ("__builtin_is_constant_evaluated", "__builtin_constant_p",
                                  "__builtin_bit_cast", "__builtin_launder", "__builtin_addressof",
                                  "__builtin_source_location", "__builtin_FILE", "__builtin_LINE",
                                  "__builtin_FUNCTION", "__builtin_operator_new",
                                  "__builtin_operator_delete", "__builtin_clear_padding",
                                  "__builtin_offsetof", "__builtin_choose_expr",
                                  "__builtin_types_compatible_p", "__builtin_classify_type",
                                  "__builtin_tgmath", "__builtin_complex") or n.startswith("__builtin_coro_")),
    ("control", lambda n: n in ("__builtin_expect", "__builtin_unreachable", "__builtin_trap",
                                "__builtin_abort", "__builtin_assume_aligned", "__builtin_alloca",
                                "__builtin_return_address", "__builtin_extract_return_addr",
                                "__builtin_ia32_pause", "__builtin_prefetch", "__builtin_frame_address")),
    ("bit", lambda n: re.match(r"__builtin_(clz|ctz|popcount|parity|ffs|clrsb|bswap|stdc_)", n) is not None
     or n.endswith("_overflow") or n.endswith("_overflow_p")),
    ("memory", lambda n: re.match(r"__builtin_(mem|str|wmem|wcs|index$|rindex$|toupper|tolower|malloc|free|calloc|realloc|vsn?printf|fclose|char_memchr|abs$|labs$|llabs$)", n) is not None),
    ("fpclass", lambda n: re.match(r"__builtin_(huge_val|inf|nans?|is|fpclassify|signbit|copysign|fabs)", n) is not None),
    ("math", lambda n: True),
]


def builtin_group(n):
    for g, f in BUILTIN_GROUPS:
        if f(n):
            return g
    return "math"


def by_name(c, pred):
    d = collections.OrderedDict()
    for h in c.scan["hits"]:
        if pred(h):
            d.setdefault(h["name"], []).append(h)
    return d


def table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def put(gen, key, rows, header):
    """Store the full table under KEY and an M1-only table under KEY_m1; the
    latter lists the names of the other rows after the table."""
    gen[key] = table(rows, header)
    si = header.index("Reached")
    m1 = [r for r in rows if r[si].startswith("M1")]
    rest = [r for r in rows if not r[si].startswith("M1")]
    t = table(m1, header) if m1 else "(no entry is reached in M1)"
    if rest:
        t += ("\n\nNot reached in M1 (rows in the appendix): "
              + ", ".join("%s (%s)" % (r[0], r[si]) for r in rest) + ".")
    gen[key + "_m1"] = t


def hdr(extra=()):
    return HEAD[:2] + list(extra) + HEAD[2:]


def ext_row(c, name, hs, kind, extra_note="", show_name=None, label="", extra=()):
    h = rep_hit(c, hs)
    st = status_of(c, hs)
    files = len({x["file"] for x in hs})
    rs = roots_of(c, hs)
    rtxt = ""
    if st == "M1":
        if rs and len(rs) <= 3:
            rtxt = ", ".join("&lt;%s&gt;" % r for r in sorted(rs))
        elif rs:
            rtxt = "%d roots" % len(rs)
        else:
            rtxt = "via macro"
    link, note = manual_note(c, name, kind)
    note = (note + (" " if note and extra_note else "") + extra_note).strip()
    loc = "%s:%d" % (short(h["file"]), h["line"])
    if h["ctx"].startswith("define:"):
        loc += " (in `#define %s`)" % h["ctx"][7:]
    return ([code(show_name or name), label] + list(extra)
            + [str(len(hs)) + "/" + str(files), loc, code(guard_text(h["guards"][-1] if h["guards"] else None)),
               st + (" (" + rtxt + ")" if rtxt else ""), md(link + (": " if link and note else "") + note)])


HEAD = ["Name", "Kind", "Uses/files", "Representative site", "Innermost guard (verbatim)", "Reached",
        "Semantics (GCC 15.2 manual)"]
KIND_LABEL = {"keyword": "keyword", "c-keyword": "C keyword", "type": "type", "type-std": "ISO type",
              "fallback-define": "fallback macro", "syntax": "syntax", "directive": "directive",
              "aarch64-type": "aarch64 type", "preprocessor": "pp operator"}


def label_of(hs):
    g = collections.Counter(h["group"] for h in hs).most_common(1)[0][0]
    return KIND_LABEL.get(g, g)


BUILTIN_KIND = {"trait": "builtin (trait)", "constexpr": "builtin (language)", "control": "builtin (control/hint)",
                "bit": "builtin (bit/overflow)", "memory": "builtin (library)", "varargs": "builtin (varargs)",
                "fortify": "builtin (object size)", "math": "builtin (library, math)", "fpclass": "builtin (FP class/constant)"}


def gen_builtin_tables(c, counts, classes, gen):
    hits = by_name(c, lambda h: h["group"] == "builtin")
    groups = collections.defaultdict(dict)
    for n, hs in hits.items():
        if n == "__builtin_ret_type":
            continue  # libstdc++ alias in <source_location>, not a builtin
        groups[builtin_group(n)][n] = hs
    # math compression
    for g in ("math", "fpclass"):
        names = set(groups[g])
        base_of = {}
        for n in names:
            b = n
            for suf in ("f128x", "f128", "f64x", "f64", "f32x", "f32", "f16b", "f16", "d128", "d64x", "d64", "d32", "f", "l"):
                if n.endswith(suf) and (n[:-len(suf)] in names or n[:-len(suf)][len("__builtin_"):] in c.man["library_functions"]):
                    b = n[:-len(suf)]
                    break
            base_of[n] = b
        comp = collections.OrderedDict()
        for n in sorted(names):
            comp.setdefault(base_of[n], []).append(n)
        groups[g + "_comp"] = comp
    for g in ("trait", "constexpr", "control", "bit", "memory", "varargs", "fortify"):
        rows = []
        for n in sorted(groups[g]):
            hs = groups[g][n]
            cls = "A" if n in CLASS_A_BUILTIN else ("L" if g == "memory" else "M")
            classes[(g, n)] = (cls, status_of(c, hs))
            rows.append(ext_row(c, n, hs, "builtin", CLASS_NOTE_BUILTIN.get(n, ""), label=BUILTIN_KIND[g],
                                extra=(cls,)))
        counts[g] = (len(groups[g]), sum(len(v) for v in groups[g].values()))
        put(gen, "builtins_" + g, rows, hdr(("Class",)))
    for g in ("math", "fpclass"):
        rows = []
        comp = groups[g + "_comp"]
        for b, variants in comp.items():
            hs = [h for v in variants for h in groups[g][v]]
            suf = sorted({v[len(b):] or "-" for v in variants}, key=lambda s: (len(s), s))
            disp = b + ("{" + ",".join("" if s == "-" else s for s in suf) + "}" if len(variants) > 1 else "")
            cls = "L" if g == "math" else "M"
            for v in variants:
                classes[(g, v)] = (cls, status_of(c, groups[g][v]))
            rows.append(ext_row(c, b if b in groups[g] else variants[0], hs, "builtin", show_name=disp,
                                label=BUILTIN_KIND[g], extra=(cls,)))
        counts[g] = (len(groups[g]), sum(len(v) for v in groups[g].values()))
        put(gen, "builtins_" + g, rows, hdr(("Class",)))


def gen_traits(c, counts, classes, gen):
    hits = by_name(c, lambda h: h["group"] == "trait")
    rows = []
    for n in sorted(hits):
        classes[("trait-keyword", n)] = ("M", status_of(c, hits[n]))
        rows.append(ext_row(c, n, hits[n], "trait", label="trait keyword", extra=("M",)))
    counts["trait-keyword"] = (len(hits), sum(len(v) for v in hits.values()))
    put(gen, "traits", rows, hdr(("Class",)))


def gen_atomics(c, counts, classes, gen):
    hits = by_name(c, lambda h: h["group"] in ("atomic", "sync"))
    rows = []
    for n in sorted(hits):
        classes[("atomic", n)] = ("M", status_of(c, hits[n]))
        rows.append(ext_row(c, n, hits[n], "atomic", label="builtin (atomic)", extra=("M",)))
    counts["atomic"] = (len(hits), sum(len(v) for v in hits.values()))
    put(gen, "atomics", rows, hdr(("Class",)))


def gen_attributes(c, counts, classes, gen):
    hits = by_name(c, lambda h: h["group"] == "attribute")
    rows = []
    for n in sorted(hits):
        hs = hits[n]
        sp = sorted({h.get("syntax", "") for h in hs} - {""})
        cls = "M" if n in CLASS_M_ATTR else "A"
        classes[("attribute", n)] = (cls, status_of(c, hs))
        rows.append(ext_row(c, n, hs, "attribute", CLASS_NOTE_ATTR.get(n, ""), label="GNU attribute",
                            extra=(md(", ".join(sp)), cls)))
    counts["attribute"] = (len(hits), sum(len(v) for v in hits.values()))
    put(gen, "attributes", rows, hdr(("Spellings", "Class")))
    std = by_name(c, lambda h: h["group"] in ("attribute-std", "attribute-cxx11-other"))
    srows = []
    for n in sorted(std):
        hs = std[n]
        sp = sorted({h["spelling"] for h in hs})
        cls = "A" if n not in ("[[no_unique_address]]",) else "M"
        classes[("attribute-std", n)] = (cls, status_of(c, hs))
        r = ext_row(c, n, hs, "attribute-std", label="ISO attribute", extra=(md(", ".join(sp)), cls))
        r[-1] = ("ISO C++ attribute; GCC accepts the reserved `__name__` spelling "
                 "([Attribute-Syntax](%sAttribute-Syntax.html))" % GCC)
        srows.append(r)
    counts["attribute-std"] = (len(std), sum(len(v) for v in std.values()))
    put(gen, "std_attributes", srows, hdr(("Spellings", "Class")))


def gen_simple(c, groups, counts, key, classes, gen, out_key, cls_fn=lambda n: "M"):
    hits = by_name(c, lambda h: h["group"] in groups)
    rows = []
    for n in sorted(hits, key=lambda s: s.lower()):
        hs = hits[n]
        cl = cls_fn(n)
        classes[(key, n)] = (cl, status_of(c, hs))
        rows.append(ext_row(c, n, hs, "x", KW_NOTE.get(n, ""), label=label_of(hs), extra=(cl,)))
    counts[key] = (len(hits), sum(len(v) for v in hits.values()))
    put(gen, out_key, rows, hdr(("Class",)))


def kw_class(n):
    if n in ("__extension__", "__restrict", "__restrict__", "__inline", "__inline__", "__attribute__",
             "__attribute", "__signed__", "__signed", "__const", "__volatile"):
        return "A"
    return "M"


def syn_class(n):
    if n in ("#warning", "#pragma GCC diagnostic", "#pragma GCC system_header", "#pragma clang diagnostic",
             "#pragma GCC unroll", "#pragma clang attribute", "#pragma intrinsic", "#pragma #") or n.startswith("#pragma omp"):
        return "A"
    if n == "#pragma GCC visibility":
        return "A"
    return "M"


def gen_pragmas(c, counts, classes, gen):
    hits = by_name(c, lambda h: h["group"] == "pragma")
    rows = []
    for n in sorted(hits):
        hs = hits[n]
        texts = collections.Counter(h["spelling"] for h in hs)
        top = "; ".join("%s (%d)" % (t[:60], k) for t, k in texts.most_common(4))
        cl = syn_class(n)
        classes[("pragma", n)] = (cl, status_of(c, hs))
        via = "_Pragma" if all(h.get("via") == "_Pragma" for h in hs) else "#pragma"
        rows.append(ext_row(c, n, hs, "x", label="pragma (%s)" % via, extra=(cl, md(top))))
    counts["pragma"] = (len(hits), sum(len(v) for v in hits.values()))
    put(gen, "pragmas", rows, hdr(("Class", "Forms seen (count)")))


def asm_family(h):
    """Coarse family of an asm hit, for the summary table."""
    if h["ctx"].startswith("define:"):
        return "macro " + h["ctx"][7:]
    if h["name"].startswith("inline asm"):
        return "top-level asm statement"
    if h["file"].startswith("/usr/include/c++/"):
        return "long double / _Float128 ABI aliases"
    return "C++ overload or POSIX alias"


def gen_asm(c, counts, classes, gen):
    hits = [h for h in c.scan["hits"] if h["group"] == "asm"]
    rows = []
    for h in sorted(hits, key=lambda h: (h["file"], h["line"])):
        st = status_of(c, [h])
        rows.append([code(h["name"]), "%s:%d" % (short(h["file"]), h["line"]) + (" (`#define %s`)" % h["ctx"][7:] if h["ctx"].startswith("define:") else ""),
                     code(h.get("asm", "").strip()[:70]), code(guard_text(h["guards"][-1] if h["guards"] else None)), st])
    counts["asm"] = (len({h["name"] for h in hits}), len(hits))
    for n in {h["name"] for h in hits}:
        classes[("asm", n)] = ("M", status_of(c, [h for h in hits if h["name"] == n]))
    gen["asm"] = table(rows, ["Kind", "Site", "Operand text", "Innermost guard (verbatim)", "Reached"])
    # summary: one row per (kind, family, file, guard, status)
    grp = collections.OrderedDict()
    for h in sorted(hits, key=lambda h: (h["file"], h["line"])):
        g = h["guards"][-1] if h["guards"] else None
        k = (h["name"], asm_family(h), h["file"], guard_text(g), status_of(c, [h]))
        grp.setdefault(k, []).append(h)
    srows = []
    for (name, fam, f, gt, st), hs in grp.items():
        lines = ", ".join(str(h["line"]) for h in hs[:6]) + (", ..." if len(hs) > 6 else "")
        srows.append([code(name), md(fam), "%s:%s" % (short(f), lines), str(len(hs)),
                      code(hs[0].get("asm", "").strip()[:60]), code(gt), st])
    gen["asm_summary"] = table(srows, ["Kind", "Family", "Sites", "Count", "First operand", "Innermost guard (verbatim)", "Reached"])


REDIRECT_RE = re.compile(r"\b(__REDIRECT(?:_NTH|_NTHNL|_FORTIFY|_FORTIFY_NTH|_LDBL)?)\s*\(")


def gen_redirects(c, gen):
    """Invocations of glibc's __REDIRECT* macros in code lines of entered blocks."""
    fid_of = {p: i for i, p in enumerate(sorted(c.manifest))}
    res = {}
    for cfg in ("m1", "m1-fortify", "neither"):
        act = c.sets[cfg]
        per_file = collections.Counter()
        per_macro = collections.Counter()
        for f in sorted(c.closure["files"]):
            fid = fid_of[f]
            stack, counter = [], 0
            for ll in hx.logical_lines(hx.read_text(c.manifest, f)):
                d, _ = hx.directive(ll)
                if d in hx.COND_OPEN:
                    counter += 1
                    stack.append("%d.%d" % (fid, counter))
                    continue
                if d in hx.COND_MID:
                    counter += 1
                    if stack:
                        stack[-1] = "%d.%d" % (fid, counter)
                    continue
                if d == "endif":
                    if stack:
                        stack.pop()
                    continue
                if d is not None:
                    continue
                if (stack[-1] if stack else "%d.0" % fid) not in act:
                    continue
                for m in REDIRECT_RE.finditer(ll.code):
                    per_file[f] += 1
                    per_macro[m.group(1)] += 1
        res[cfg] = (per_file, per_macro)
    rows = []
    for cfg, (pf, pm) in res.items():
        rows.append([code(cfg), str(sum(pm.values())), md(", ".join("%s %d" % (k, v) for k, v in sorted(pm.items()))),
                     md(", ".join("%s %d" % (short(k), v) for k, v in pf.most_common()))])
    gen["redirects"] = table(rows, ["Configuration", "`__REDIRECT*` invocations in entered code", "By macro", "By header"])


def gen_wrappers(c, files):
    """glibc/libstdc++ wrapper macros whose bodies contain extensions."""
    hits_by_def = collections.defaultdict(list)
    for h in c.scan["hits"]:
        if h["ctx"].startswith("define:") and h["file"] in files and h["group"] not in ("query",):
            hits_by_def[(h["file"], h["line"], h["ctx"][7:])].append(h)
    defs = collections.defaultdict(list)
    for d in c.scan["defines"]:
        if d["file"] in files:
            defs[d["name"]].append(d)
    rows = []
    done = set()
    for (f, line, name), hs in sorted(hits_by_def.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if name in done:
            continue
        done.add(name)
        alts = sorted(defs[name], key=lambda d: d["line"])
        live = [d for d in alts if d["block"] in c.sets["m1"]]
        m1 = live[0] if live else None
        exps = "yes" if name in c.expanded["m1"] else "no"
        alt_txt = "; ".join("%d: %s" % (d["line"], (d["body"] or "(empty)")[:50]) for d in alts if d is not m1)[:160]
        rows.append([code(name + (d_params(alts) or "")), "%s:%d" % (short(f), line),
                     code(((m1["body"] or "(empty)") if m1 else "(not defined in m1)")[:90]),
                     code(guard_text(m1["guards"][-1] if m1 and m1["guards"] else (alts[0]["guards"][-1] if alts[0]["guards"] else None))),
                     exps, md(alt_txt) if alt_txt else ""])
    return table(rows, ["Macro", "First definition", "M1 expansion", "Guard of M1 definition", "Expanded by headers in M1", "Other definitions (line: body)"])


def d_params(alts):
    for d in alts:
        if d["params"]:
            return d["params"]
    return ""


# ---------------------------------------------------------------------------
GCC_VALUES = {
    # value under g++ 15.2 -std=c++20 -fno-exceptions -fno-rtti -O2 on aarch64, with source
    "__cplusplus": ("202002L", "c-cppbuiltin.cc / [cpp.predefined]"),
    "__GNUC__": ("15", "cpp manual Common Predefined Macros"),
    "__GNUC_MINOR__": ("2", "cpp manual"), "__GNUC_PATCHLEVEL__": ("0", "cpp manual"),
    "__GNUG__": ("15", "c-cppbuiltin.cc"), "__clang__": ("undefined", "-"),
    "__clang_major__": ("undefined", "-"), "__clang_minor__": ("undefined", "-"),
    "__STRICT_ANSI__": ("1", "c-cppbuiltin.cc: if (flag_iso)"),
    "__OPTIMIZE__": ("1 at -O1 and above", "cpp manual"), "__NO_INLINE__": ("undefined at -O2", "cpp manual"),
    "__EXCEPTIONS": ("undefined (-fno-exceptions)", "cpp manual"),
    "__cpp_exceptions": ("undefined (-fno-exceptions)", "c-cppbuiltin.cc"),
    "__GXX_RTTI": ("undefined (-fno-rtti)", "cpp manual"), "__cpp_rtti": ("undefined (-fno-rtti)", "c-cppbuiltin.cc"),
    "__SIZEOF_INT128__": ("16", "c-cppbuiltin.cc (int_n_enabled_p)"),
    "__GLIBCXX_TYPE_INT_N_0": ("undefined under -std=c++20; __int128 under -std=gnu++20", "c-cppbuiltin.cc"),
    "__GLIBCXX_BITSIZE_INT_N_0": ("undefined under -std=c++20; 128 under gnu++20", "c-cppbuiltin.cc"),
    "__aarch64__": ("1", "aarch64-c.cc"), "__AARCH64EB__": ("undefined (little-endian)", "aarch64-c.cc"),
    "__LP64__": ("1", "cpp manual"), "__CHAR_UNSIGNED__": ("1", "cpp manual"),
    "__DEPRECATED": ("1", "cpp manual"), "__GXX_WEAK__": ("1", "cpp manual"),
    "__GXX_EXPERIMENTAL_CXX0X__": ("1", "cpp manual"),
    "_GNU_SOURCE": ("1 (g++ on GNU/Linux)", "libstdc++ manual FAQ"),
    "__STDC_HOSTED__": ("1", "cpp manual"), "__STDC__": ("1", "cpp manual"),
    "__STDC_VERSION__": ("undefined in C++", "cpp manual"),
    "__FLT_EVAL_METHOD__": ("0", "aarch64-c.cc"),
    "__GCC_IEC_559": ("2", "c-cppbuiltin.cc cpp_iec_559_value"),
    "__GNUC_EXECUTION_CHARSET_NAME": ("\"UTF-8\"", "c-cppbuiltin.cc"),
    "__WCHAR_MIN__": ("0U", "c-cppbuiltin.cc"), "__LONG_LONG_WIDTH__": ("64", "c-cppbuiltin.cc"),
    "__FLT128_DIG__": ("33", "c-cppbuiltin.cc (FloatN constants)"),
    "__FLT32_DIG__": ("6", "c-cppbuiltin.cc"), "__FLT64_DIG__": ("15", "c-cppbuiltin.cc"),
    "__BFLT16_DIG__": ("2", "c-cppbuiltin.cc (bfloat16_type_node)"),
    "__STDCPP_FLOAT16_T__": ("undefined (only cxx_dialect > cxx20)", "c-cppbuiltin.cc"),
    "__STDCPP_FLOAT32_T__": ("undefined (only > C++20)", "c-cppbuiltin.cc"),
    "__STDCPP_FLOAT64_T__": ("undefined (only > C++20)", "c-cppbuiltin.cc"),
    "__STDCPP_FLOAT128_T__": ("undefined (only > C++20)", "c-cppbuiltin.cc"),
    "__STDCPP_BFLOAT16_T__": ("undefined (only > C++20)", "c-cppbuiltin.cc"),
    "__LDBL_MANT_DIG__": ("113", "c-cppbuiltin.cc"),
    "__cpp_sized_deallocation": ("201309L", "c-cppbuiltin.cc (flag_sized_deallocation)"),
    "__cpp_constexpr": ("202002L", "c-cppbuiltin.cc"), "__cpp_deduction_guides": ("201907L", "c-cppbuiltin.cc"),
    "__cpp_concepts": ("202002L", "c-cppbuiltin.cc"), "__cpp_impl_coroutine": ("201902L", "c-cppbuiltin.cc"),
    "__cpp_impl_three_way_comparison": ("201907L", "c-cppbuiltin.cc"),
    "__cpp_constexpr_dynamic_alloc": ("201907L", "c-cppbuiltin.cc"),
    "__cpp_consteval": ("202211L", "c-cppbuiltin.cc"), "__cpp_char8_t": ("202207L", "c-cppbuiltin.cc"),
    "__cpp_aligned_new": ("201606L", "c-cppbuiltin.cc"), "__cpp_inline_variables": ("201606L", "c-cppbuiltin.cc"),
    "__cpp_if_constexpr": ("201606L", "c-cppbuiltin.cc"), "__cpp_variable_templates": ("201304L", "c-cppbuiltin.cc"),
    "__cpp_conditional_explicit": ("201806L", "c-cppbuiltin.cc"), "__cpp_using_enum": ("201907L", "c-cppbuiltin.cc"),
    "__cpp_generic_lambdas": ("201707L", "c-cppbuiltin.cc"), "__cpp_fold_expressions": ("201603L", "c-cppbuiltin.cc"),
    "__cpp_noexcept_function_type": ("201510L", "c-cppbuiltin.cc"),
    "__cpp_impl_destroying_delete": ("201806L", "c-cppbuiltin.cc"),
    "__cpp_if_consteval": ("undefined (C++23)", "c-cppbuiltin.cc"),
    "__cpp_explicit_this_parameter": ("undefined (C++23)", "c-cppbuiltin.cc"),
    "__cpp_static_call_operator": ("undefined (C++23)", "c-cppbuiltin.cc"),
    "__cpp_pack_indexing": ("undefined (C++26)", "c-cppbuiltin.cc"),
    "__cpp_modules": ("undefined without -fmodules", "c-cppbuiltin.cc"),
    "__cpp_transactional_memory": ("undefined without -fgnu-tm", "c-cppbuiltin.cc"),
    "__cpp_nontype_template_args": ("201911L", "c-cppbuiltin.cc"),
    "__GNUC_STDC_INLINE__": ("see note", "c-cppbuiltin.cc (flag_gnu89_inline)"),
    "__FAST_MATH__": ("undefined", "cpp manual"), "__NO_MATH_ERRNO__": ("undefined", "cpp manual"),
    "__SUPPORT_SNAN__": ("undefined", "cpp manual"),
    "__SANITIZE_ADDRESS__": ("undefined", "cpp manual"), "__SANITIZE_THREAD__": ("undefined", "cpp manual"),
    "_FORTIFY_SOURCE": ("Ubuntu driver: 3 at -O2+", "Ubuntu gcc-15(1) NOTE"),
    "__USER_LABEL_PREFIX__": ("(empty)", "cpp manual"),
    "__ELF__": ("1", "System-specific"), "__linux__": ("1", "System-specific"),
    "__INT_MAX__": ("0x7fffffff", "cpp manual"), "__CHAR_BIT__": ("8", "cpp manual"),
    "__GNUC_GNU_INLINE__": ("1 if flag_gnu89_inline, else undefined", "c-cppbuiltin.cc"),
}
GCC_VALUES["__GNUC_STDC_INLINE__"] = ("1 unless flag_gnu89_inline", "c-cppbuiltin.cc")
for _n in ("__clang_literal_encoding__", "__clang_wide_literal_encoding__", "__INTEL_COMPILER", "__EDG__",
           "_MSC_VER", "__CUDACC__", "__TINYC__", "__HP_cc", "__ICC", "__ECC", "__BIONIC__"):
    GCC_VALUES[_n] = ("undefined", "")
GCC_VALUES["_GLIBCXX_CLANG"] = ("undefined (c++config.h:515 defines it from __clang__)", "")
# Example site to show for a steering macro when the first evaluated one is unrepresentative
PREFERRED_SITE = {"__GNUC__": ("/usr/include/aarch64-linux-gnu/sys/cdefs.h", 408)}

IDENTITY = ["__GNUC__", "__GNUC_MINOR__", "__GNUC_PATCHLEVEL__", "__GNUG__", "__clang__", "__clang_major__",
            "__clang_minor__", "__clang_literal_encoding__", "__clang_wide_literal_encoding__", "_GLIBCXX_CLANG",
            "__INTEL_COMPILER", "__EDG__", "_MSC_VER", "__CUDACC__", "__TINYC__", "__HP_cc", "__ICC", "__ECC",
            "__BIONIC__", "__GNUC_STDC_INLINE__", "__GNUC_GNU_INLINE__"]
LANG = ["__cplusplus", "__STDC__", "__STDC_VERSION__", "__STDC_HOSTED__", "__STRICT_ANSI__", "__OPTIMIZE__",
        "__OPTIMIZE_SIZE__", "__NO_INLINE__", "__EXCEPTIONS", "__cpp_exceptions", "__GXX_RTTI", "__cpp_rtti",
        "__DEPRECATED", "__GXX_WEAK__", "__GXX_EXPERIMENTAL_CXX0X__", "__FAST_MATH__", "__NO_MATH_ERRNO__",
        "__SUPPORT_SNAN__", "__SANITIZE_ADDRESS__", "__SANITIZE_THREAD__", "__ASSEMBLER__",
        "__USER_LABEL_PREFIX__", "_GNU_SOURCE", "_FORTIFY_SOURCE", "_FILE_OFFSET_BITS", "_TIME_BITS",
        "_REENTRANT", "NDEBUG", "_LIBC", "__GNUC_EXECUTION_CHARSET_NAME", "__GNUC_WIDE_EXECUTION_CHARSET_NAME"]
TARGET = ["__aarch64__", "__AARCH64EB__", "__LP64__", "__CHAR_UNSIGNED__", "__ELF__", "__linux__",
          "__BYTE_ORDER__", "__ORDER_LITTLE_ENDIAN__", "__ORDER_BIG_ENDIAN__", "__SIZEOF_INT128__",
          "__GLIBCXX_TYPE_INT_N_0", "__GLIBCXX_BITSIZE_INT_N_0", "__SIZEOF_LONG__", "__SIZEOF_LONG_LONG__",
          "__SIZEOF_INT__", "__CHAR_BIT__", "__INT_MAX__", "__LONG_MAX__", "__SCHAR_MAX__", "__SHRT_MAX__",
          "__WCHAR_MAX__", "__WCHAR_MIN__", "__SIZE_MAX__", "__PTRDIFF_MAX__", "__SIZE_WIDTH__", "__LONG_WIDTH__",
          "__LONG_LONG_WIDTH__", "__INTMAX_WIDTH__", "__INT64_TYPE__", "__UINT64_TYPE__", "__UINT32_TYPE__",
          "__FLT_EVAL_METHOD__", "__GCC_IEC_559", "__GCC_IEC_559_COMPLEX", "__FP_FAST_FMAL",
          "__FLT_MANT_DIG__", "__FLT_MAX_EXP__", "__FLT_MIN_EXP__", "__DBL_MANT_DIG__", "__DBL_MAX_EXP__",
          "__DBL_MIN_EXP__", "__LDBL_MANT_DIG__", "__LDBL_MAX_EXP__", "__LDBL_MIN_EXP__",
          "__FLT16_DIG__", "__FLT32_DIG__", "__FLT64_DIG__", "__FLT128_DIG__", "__BFLT16_DIG__",
          "__STDCPP_FLOAT16_T__", "__STDCPP_FLOAT32_T__", "__STDCPP_FLOAT64_T__", "__STDCPP_FLOAT128_T__",
          "__STDCPP_BFLOAT16_T__", "__LONG_DOUBLE_IEEE128__", "__LONG_DOUBLE_128__", "__LONG_DOUBLE_IBM128__",
          "__FLOAT128__", "__SIZEOF_FLOAT128__", "__SIZEOF_FLOAT80__", "__SIZEOF_IBM128__",
          "__GCC_ATOMIC_TEST_AND_SET_TRUEVAL", "__GCC_ATOMIC_INT_LOCK_FREE", "__GCC_ATOMIC_LONG_LOCK_FREE",
          "__GCC_ATOMIC_CHAR_LOCK_FREE", "__GCC_DESTRUCTIVE_SIZE"]


def first_body_line(c, f, line, cache={}):
    """First logical line after the directive at f:line (what the branch selects)."""
    if f not in cache:
        cache[f] = hx.logical_lines(hx.read_text(c.manifest, f))
    lls = cache[f]
    for i, ll in enumerate(lls):
        if ll.start == line:
            for ll2 in lls[i + 1:i + 8]:
                t = " ".join(ll2.code.split())
                if t:
                    return t[:90]
    return ""


def gen_steer_table(c, names, with_values=True):
    idx = {r["name"]: r for r in c.steer["ids"]}
    clang = {}
    for line in open(os.path.join(c.out, "pp/clang-predef.txt")):
        m = re.match(r"#define (\w+) ?(.*)$", line.rstrip("\n"))
        if m:
            clang[m.group(1)] = m.group(2)
    rows = []
    for n in names:
        r = idx.get(n)
        if not r:
            continue
        sites = [s for s in r["sites"] if s["live"]] or r["sites"]
        pref = [x for x in r["sites"] if (x["file"], x["line"]) == PREFERRED_SITE.get(n)]
        s = (pref or sites)[0]
        sel = first_body_line(c, s["file"], s["line"])
        gv = GCC_VALUES.get(n, ("", ""))
        cv = clang.get(n, "undefined")
        if n in ("__OPTIMIZE__",):
            cv = "1 at -O1+"
        row = [code(n), "%d/%d/%d" % (r["tests"], r["files"], r["m1_sites"])]
        if with_values:
            row += [md(gv[0]) + (" (%s)" % md(gv[1]) if gv[1] else ""), code(cv) if cv else "(empty)"]
        row += ["%s:%d" % (short(s["file"]), s["line"]), code(("#%s %s" % (s["kind"], " ".join(s["text"].split())))[:100]), code(sel) if sel else ""]
        rows.append(row)
    hd = ["Macro", "Tests/files/live in M1"]
    if with_values:
        hd += ["g++ 15.2 value (source)", "Apple clang 17 value"]
    hd += ["Example site", "Test (verbatim)", "First line it selects"]
    return table(rows, hd)


def gen_cpp_ftm(c):
    names = sorted(r["name"] for r in c.steer["ids"] if r["name"].startswith("__cpp_") and r["n_defined_in_headers"] == 0)
    return gen_steer_table(c, names)


def gen_queries(c):
    rows = []
    for q, v in sorted(c.steer["queries"].items(), key=lambda kv: (kv[0].split("(")[0], kv[0])):
        op, arg = q.split("(", 1)
        arg = arg[:-1].strip()
        if op in ("__GNUC_PREREQ", "__glibc_clang_prereq"):
            continue
        ans = ""
        if op in ("__has_builtin", "_GLIBCXX_HAS_BUILTIN", "_GLIBCXX_USE_BUILTIN_TRAIT", "__glibc_has_builtin"):
            d = c.hb.get(arg)
            if d:
                ans = "%d (%s)" % (d["gcc"], "; ".join(d["basis"]))
        rows.append([code(op), code(arg), "%d/%d" % (v["n"], v["live"]), md(", ".join(short(s) for s in v["sites"][:3]) + (" ..." if len(v["sites"]) > 3 else "")), md(ans)])
    return table(rows, ["Operator or wrapper", "Operand", "Sites/live in M1", "Sites", "GCC 15.2 answer (basis)"])


def gen_prereq(c):
    rows = []
    for q, v in sorted(c.steer["queries"].items(), key=lambda kv: kv[0]):
        op, arg = q.split("(", 1)
        if op not in ("__GNUC_PREREQ", "__glibc_clang_prereq"):
            continue
        rows.append([code(op + "(" + arg), "%d/%d" % (v["n"], v["live"]), md(", ".join(short(s) for s in v["sites"][:4]) + (" ..." if len(v["sites"]) > 4 else ""))])
    return table(rows, ["Query", "Sites/live in M1", "Sites"])


def gen_other_ext_macros(c):
    """Never-defined conditional identifiers not covered by the curated tables."""
    covered = set(IDENTITY + LANG + TARGET)
    cats = collections.defaultdict(list)
    for r in c.steer["ids"]:
        n = r["name"]
        if r["n_defined_in_headers"] or n in covered or n.startswith("__cpp_"):
            continue
        if n.startswith("__NR_") or re.match(r"^(IEC_60559|ISOC|LIB_EXT|DEPRECATED_|C23_|ISOC2Y)", n):
            continue
        if re.match(r"^_GLIBCXX|^__GLIBCXX|^_PSTL|^__glibcxx|^PSTL|^TBB|^_GTHREAD|^__GTHREAD", n):
            cats["libstdc++ configuration knobs (user or build-time)"].append(n)
        elif re.match(r"^__(STDC_WANT|need_)|^_[A-Z_]*SOURCE$|^__USE_|^_LIBC|^__LIBC|^_LIBOBJC|^SHARED|^NDEBUG|^_ISOC|^_REENTRANT|^_THREAD_SAFE|^_TIME_BITS|^_FILE_OFFSET|^_FORTIFY", n):
            cats["glibc/C feature and internal protocol macros"].append(n)
        elif re.match(r"^(_WIN32|__CYGWIN__|__MINGW32__|__FreeBSD|__NetBSD__|__DragonFly__|__APPLE__|__sun|__hpux__|__svr4__|__sequent__|_SCO_DS|__BSD|____386BSD|__bsdi__|__BEOS__|__VMS__|WINNT|__vax__|__alpha__|__i860__|__hppa__|__i386__|__x86_64__|__mips|__riscv|__powerpc__|_ARCH_PWR8|_CALL_ELF|__ia64__|__AVR__|__LITTLE_ENDIAN__|__KERNEL__|__CHECKER__|__GNU__|__FreeBSD_kernel__|__BIONIC__|_AIX|__sparc)", n):
            cats["other OS / architecture / tool"].append(n)
        elif n.startswith("__") and (n.endswith("__") or n.startswith("__GCC") or n.startswith("__FLT") or n.startswith("__DBL") or n.startswith("__LDBL")):
            cats["other compiler-predefined macros"].append(n)
        else:
            cats["other (header guards of other headers, kernel types, misc)"].append(n)
    out = []
    for k in sorted(cats):
        out.append("- **%s** (%d): %s" % (k, len(cats[k]), ", ".join(code(x) for x in sorted(cats[k]))))
    return "\n".join(out)


def gen_predef_values(c):
    """Compiler-predefined macros that M1-live header code (or a macro body
    reachable from it) uses as a value rather than in #if."""
    cand = set()
    for line in open(os.path.join(c.out, "pp/clang-predef.txt")):
        m = re.match(r"#define (\w+)", line)
        if m:
            cand.add(m.group(1))
    delta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcc15-delta.h")
    for line in open(delta):
        m = re.match(r"#define (\w+)", line)
        if m:
            cand.add(m.group(1))
    cand |= set(GCC_VALUES)
    cand -= {d["name"] for d in c.scan["defines"]}
    cand = {n for n in cand if n.startswith("__") and not n.startswith("__clang") and n != "__llvm__"}
    act = c.sets["m1"]
    used = collections.Counter()
    for b, ids in c.scan["uses"].items():
        if b in act:
            for x in ids:
                if x in cand:
                    used[x] += 1
    for d in c.scan["defines"]:
        if d["block"] in act and d["name"] in c.expanded["m1"]:
            for x in set(re.findall(r"[A-Za-z_]\w*", d["body"])):
                if x in cand:
                    used[x] += 1
    tested = {r["name"] for r in c.steer["ids"]}
    fams = collections.OrderedDict([
        ("type names", r"_TYPE__$"), ("floating-point characteristics", r"^__(B?FLT|DBL|LDBL|DEC)\d*X?_"),
        ("integer limits and widths", r"_(MAX|MIN|WIDTH)__$"), ("sizes", r"^__SIZEOF_"),
        ("atomics", r"^__(GCC_)?ATOMIC_"), ("byte order", r"ORDER|BYTE_ORDER"), ("other", r"")])
    out = collections.defaultdict(list)
    for n in sorted(used):
        for k, p in fams.items():
            if re.search(p, n):
                out[k].append(code(n) + ("\\*" if n in tested else ""))
                break
    lines = ["- **%s** (%d): %s" % (k, len(v), ", ".join(v)) for k, v in out.items() if v]
    return "\n".join(lines)


def gen_identity_diff(c):
    rows = []
    pairs = [("m1", "clang"), ("m1", "neither"), ("m1", "m1-O0"), ("m1", "gcc-eh"), ("m1", "m1-fortify"), ("m1", "m1-gnu")]
    for a, b in pairs:
        A, B = c.sets[a], c.sets[b]
        fa = {c.marks[k][0] for k in A if k.endswith(".0")}
        fb = {c.marks[k][0] for k in B if k.endswith(".0")}
        rows.append([code(a) + " vs " + code(b), str(len(A - B)), str(len(B - A)), str(len(fa - fb)), str(len(fb - fa)),
                     md(", ".join(sorted(short(x) for x in (fb - fa))))])
    return table(rows, ["Configurations", "Blocks only in first", "Blocks only in second", "Headers only in first", "Headers only in second", "Headers entered only in second"])


def gen_blockdiff_list(c, a, b, mx=400):
    A, B = c.sets[a], c.sets[b]
    lines = []
    cache = {}
    for k in sorted(A - B, key=lambda k: (c.marks[k][0], c.marks[k][1])):
        f, line = c.marks[k]
        if line == 0:
            lines.append("- %s (header entered)" % short(f))
            continue
        if f not in cache:
            cache[f] = {ll.start: ll for ll in hx.logical_lines(hx.read_text(c.manifest, f))}
        ll = cache[f].get(line)
        t = " ".join(ll.code.split())[:110] if ll else ""
        lines.append("- %s:%d %s" % (short(f), line, code(t)))
    return "\n".join(lines[:mx])


def gen_closure(c):
    files = c.closure["files"]
    m1 = {c.marks[k][0] for k in c.sets["m1"] if k.endswith(".0")}
    by = collections.Counter(c.manifest[f]["pkg"] for f in files)
    by1 = collections.Counter(c.manifest[f]["pkg"] for f in m1)
    rows = [[k, str(by[k]), str(by1.get(k, 0))] for k in sorted(by)]
    rows.append(["total", str(len(files)), str(len(m1))])
    t = table(rows, ["Package", "Headers in static closure", "Headers entered in M1 (union over roots)"])
    unres = "\n".join("- %s:%d `#%s <%s>`" % (short(u["file"]), u["line"], u["directive"], u["name"]) for u in c.closure["unresolved"])
    return t, unres


def gen_counts(counts, classes):
    rows = []
    labels = [("trait-keyword", "Type-trait keywords (cp-trait.def, `__integer_pack`)"), ("trait", "Type-trait `__builtin_*` (C++ front end)"),
              ("constexpr", "Constexpr / language-support builtins"), ("control", "Control-flow and hint builtins"),
              ("bit", "Bit, byte-swap and overflow builtins"), ("memory", "Memory/string library builtins"),
              ("fpclass", "Floating-point classification/constant builtins"), ("math", "Math library builtins"),
              ("varargs", "Varargs builtins"), ("fortify", "Object-size / fortify builtins"),
              ("atomic", "`__atomic_*` builtins (no `__sync_*` is used)"), ("attribute", "GNU attributes"),
              ("attribute-std", "Standard attributes (incl. reserved spellings)"), ("pragma", "Pragmas"),
              ("keyword", "Keyword and type extensions"), ("asm", "asm usage (kinds)"),
              ("syntax", "Syntax and directive extensions"), ("preprocessor", "Preprocessor operators (in code)"), ("aarch64", "aarch64-specific types")]
    for k, lab in labels:
        if k not in counts:
            continue
        n, u = counts[k]
        cl = collections.Counter()
        bucket = collections.Counter()
        for (g, nm), (cls, st) in classes.items():
            if g == k:
                cl[st.split(" (")[0]] += 1
                if st.startswith("M1"):
                    bucket[cls] += 1
        m1 = cl.get("M1", 0)
        mo = cl.get("M1 macro only", 0)
        rows.append([lab, str(n), str(u), str(m1), str(mo), str(n - m1 - mo),
                     "%d / %d / %d" % (bucket.get("M", 0), bucket.get("L", 0), bucket.get("A", 0))])
    return table(rows, ["Group", "Distinct names", "Occurrences", "Reached in M1", "M1 macro only",
                        "Only outside M1", "M1-reachable by class M / L / A"])


def gen_class_lists(classes):
    must, acc, low, outside = [], [], [], []
    for (g, n), (cls, st) in sorted(classes.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if not st.startswith("M1"):
            outside.append((g, n, st))
        elif cls == "M":
            must.append((g, n, st))
        elif cls == "L":
            low.append((g, n, st))
        else:
            acc.append((g, n, st))

    def fmt(lst, with_st=False):
        byg = collections.OrderedDict()
        for g, n, st in lst:
            byg.setdefault(g, []).append(code(n) + (" (%s)" % st if with_st else ""))
        return "\n".join("- *%s* (%d): %s" % (g, len(v), ", ".join(v)) for g, v in byg.items())
    return fmt(must), fmt(acc), fmt(low), fmt(outside, True), (len(must), len(acc), len(low), len(outside))


def main():
    out, man_p, gsrc, tmpl, out_md = sys.argv[1:6]
    c = load(out, man_p, gsrc)
    counts = {}
    classes = {}
    gen = {}
    gen_builtin_tables(c, counts, classes, gen)
    gen_traits(c, counts, classes, gen)
    gen_atomics(c, counts, classes, gen)
    gen_attributes(c, counts, classes, gen)
    gen_simple(c, ("keyword", "c-keyword", "type", "type-std", "fallback-define"), counts, "keyword", classes, gen,
               "keywords", kw_class)
    gen_simple(c, ("syntax", "directive"), counts, "syntax", classes, gen, "syntax", syn_class)
    gen_simple(c, ("aarch64-type",), counts, "aarch64", classes, gen, "aarch64")
    gen_pragmas(c, counts, classes, gen)
    gen_asm(c, counts, classes, gen)
    gen_redirects(c, gen)
    gen_simple(c, ("preprocessor",), counts, "preprocessor", classes, gen, "preproc")
    gen["predef_values"] = gen_predef_values(c)
    gen["wrappers_glibc"] = gen_wrappers(c, {"/usr/include/aarch64-linux-gnu/sys/cdefs.h", "/usr/include/features.h"})
    gen["wrappers_libstdcxx"] = gen_wrappers(c, {"/usr/include/aarch64-linux-gnu/c++/15/bits/c++config.h"})
    gen["steer_identity"] = gen_steer_table(c, IDENTITY)
    gen["steer_lang"] = gen_steer_table(c, LANG)
    gen["steer_target"] = gen_steer_table(c, TARGET)
    gen["steer_cpp"] = gen_cpp_ftm(c)
    gen["queries"] = gen_queries(c)
    gen["prereq"] = gen_prereq(c)
    gen["other_macros"] = gen_other_ext_macros(c)
    gen["identity_diff"] = gen_identity_diff(c)
    gen["diff_m1_clang"] = gen_blockdiff_list(c, "m1", "clang")
    gen["diff_clang_m1"] = gen_blockdiff_list(c, "clang", "m1")
    gen["diff_m1_neither"] = gen_blockdiff_list(c, "m1", "neither")
    gen["diff_neither_m1"] = gen_blockdiff_list(c, "neither", "m1")
    gen["diff_eh_m1"] = gen_blockdiff_list(c, "gcc-eh", "m1")
    gen["diff_fortify_m1"] = gen_blockdiff_list(c, "m1-fortify", "m1")
    gen["diff_gnu_m1"] = gen_blockdiff_list(c, "m1-gnu", "m1")
    gen["closure"], gen["unresolved"] = gen_closure(c)
    gen["counts"] = gen_counts(counts, classes)
    m, a, l, o, ns = gen_class_lists(classes)
    gen["class_must"], gen["class_accept"], gen["class_lower"], gen["class_outside"] = m, a, l, o
    gen["class_counts"] = ("%d distinct names: of those reachable in M1, %d are class M, %d class L and %d class A; "
                           "%d are reachable only outside M1 or not at all" % ((sum(ns),) + (ns[0], ns[2], ns[1], ns[3])))
    gen["roots"] = ", ".join(code("<%s>" % r) for r in hx.root_names())
    gen["cfg_flags"] = "\n".join("- `%s`: `%s`" % (k, " ".join(c.act[k]["flags"])) for k in CFG_ORDER)
    text = open(tmpl).read()
    missing = []

    def rep(m):
        k = m.group(1)
        if k not in gen:
            missing.append(k)
            return m.group(0)
        return gen[k]
    text = re.sub(r"<!-- GEN:(\w+) -->", rep, text)
    with open(out_md, "w") as f:
        f.write(text)
    if missing:
        print("missing generators:", missing, file=sys.stderr)
    json.dump({"counts": counts, "classes": {"%s|%s" % k: v for k, v in classes.items()}},
              open(os.path.join(out, "report-data.json"), "w"), indent=0)
    print("wrote", out_md, len(text), "bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
