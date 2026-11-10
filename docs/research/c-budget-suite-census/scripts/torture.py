"""Grep-level census of gcc/testsuite/gcc.c-torture/execute (Part B).

Usage: python3 -I torture.py EXECUTE_DIR DEB_ROOT OUT_JSON

A test is a .c file directly in EXECUTE_DIR, a builtins/*.c file that is
not a *-lib.c helper, or an ieee/*.c file. Features are regex hits on the
comment-stripped text, except nested functions, VLAs and labels as values,
which come from clang -fsyntax-only (aarch64-unknown-linux-gnu, glibc 2.43
headers from DEB_ROOT, -std=gnu17). dg- directives are read from comments.
Nothing in EXECUTE_DIR is executed.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

FEAT = {
    "long double": r"\blong\s+double\b|\bdouble\s+long\b",
    "__int128": r"\b__int128\b|\b__uint128_t\b|\b__int128_t\b|\bmode\s*\(\s*_*TI_*\s*\)",
    "_Complex (any)": r"\b_Complex\b|\b__complex__\b|\b__real__\b|\b__imag__\b|<complex\.h>",
    "complex integer": r"\b(?:_Complex|__complex__)\s+(?:(?:unsigned|signed|long|short|const|volatile)\s+)*(?:int|char|short|long|unsigned|signed)\b|\b(?:int|char|short|long|unsigned|signed)\s+(?:_Complex|__complex__)\b",
    "vector_size": r"\bvector_size\b",
    "computed goto (grep)": r"\bgoto\s*\*|&&\s*[A-Za-z_]\w*\s*[,};)]",
    "inline asm": r"\b(?:__asm__|__asm|asm)\b\s*(?:volatile|__volatile__|__volatile|goto|inline)?\s*\(",
    "_Atomic": r"\b_Atomic\b|<stdatomic\.h>",
    "__atomic_/__sync_ builtins": r"\b__(?:atomic|sync)_\w+\s*\(",
    "_BitInt": r"\b_BitInt\s*\(",
    "_Float16/32/64/128": r"\b_Float(?:16|32|64|128)x?\b",
    "__attribute__": r"\b__attribute__\b",
    "nested function (grep: auto/inline local fn)": r"\bauto\s+(?:int|void|char|long|short|double|float)\s+\w+\s*\(",
    "setjmp/longjmp": r"\b(?:__builtin_)?(?:setjmp|longjmp)\s*\(",
    "statement expression": r"\(\s*\{",
}
FEAT = {k: re.compile(v) for k, v in FEAT.items()}
BUILTIN = re.compile(r"\b(__builtin_\w+)")
DG = re.compile(r"\{\s*(dg-[a-z-]+)\s*(.*?)\}\s*(?:\*/|$)", re.M)


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), t, flags=re.S)
    return re.sub(r"//[^\n]*", "", t)


def tests(d):
    out = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".c"))
    b = os.path.join(d, "builtins")
    out += sorted(os.path.join(b, f) for f in os.listdir(b) if f.endswith(".c") and not f.endswith("-lib.c"))
    i = os.path.join(d, "ieee")
    out += sorted(os.path.join(i, f) for f in os.listdir(i) if f.endswith(".c"))
    return out


def clang_cmd(deb):
    res = subprocess.run(["clang", "-print-resource-dir"], capture_output=True, text=True).stdout.strip()
    libc = os.path.join(deb, "x-libc6-dev/usr/include")
    kern = os.path.join(deb, "x-linux-libc-dev/usr/include")
    a = ["clang", "--target=aarch64-unknown-linux-gnu", "-nostdinc", "-isystem", res + "/include"]
    for x in (libc + "/aarch64-linux-gnu", kern + "/aarch64-linux-gnu", libc, kern):
        a += ["-isystem", x]
    return a + ["-std=gnu17", "-fsyntax-only", "-Wvla", "-Wgnu-label-as-value", "-ferror-limit=0",
                "-Wno-error=implicit-function-declaration", "-Wno-error=implicit-int",
                "-Wno-error=int-conversion", "-Wno-error=incompatible-pointer-types",
                "-Wno-error=incompatible-function-pointer-types", "-Wno-error=return-type",
                "-fdiagnostics-show-option", "-fno-color-diagnostics"]


def main():
    d, deb, out = sys.argv[1:4]
    ts = tests(d)
    base = clang_cmd(deb)

    def run(t):
        r = subprocess.run(base + [t], capture_output=True, text=True, errors="replace", cwd=os.path.dirname(t))
        own = [l for l in r.stderr.splitlines() if l.startswith(os.path.basename(t) + ":") or l.startswith(t + ":")]
        return own

    with ThreadPoolExecutor(max_workers=10) as ex:
        diags = list(ex.map(run, ts))
    feat = defaultdict(list)
    bcount, bocc = Counter(), Counter()
    dgk, dgopt, dgtarget, stdopt = Counter(), Counter(), Counter(), Counter()
    xfiles = 0
    for t, dl in zip(ts, diags):
        rel = os.path.relpath(t, d)
        raw = open(t, encoding="latin-1").read()
        code = strip_comments(raw)
        for k, rx in FEAT.items():
            if rx.search(code):
                feat[k].append(rel)
        if any("function definition is not allowed here" in l for l in dl):
            feat["nested function (clang)"].append(rel)
        if any("[-Wvla]" in l for l in dl):
            feat["VLA (clang -Wvla)"].append(rel)
        if any("[-Wgnu-label-as-value]" in l for l in dl):
            feat["labels as values (clang)"].append(rel)
        bs = BUILTIN.findall(code)
        if bs:
            feat["any __builtin_*"].append(rel)
        bcount.update(set(bs))
        bocc.update(bs)
        kinds = set()
        for kind, body in DG.findall(raw):
            kinds.add(kind)
            if kind in ("dg-options", "dg-additional-options"):
                for o in re.findall(r"-[A-Za-z][\w=+.,/-]*", body):
                    dgopt[o] += 1
                    if o.startswith("-std="):
                        stdopt[o] += 1
            if kind in ("dg-require-effective-target", "dg-skip-if", "dg-xfail-if", "dg-xfail-run-if",
                        "dg-require-ifunc", "dg-require-alias", "dg-require-weak", "dg-require-visibility"):
                dgtarget[(kind + " " + body.strip())[:90]] += 1
        for k in kinds:
            dgk[k] += 1
        if kinds & {"dg-options", "dg-additional-options", "dg-require-effective-target", "dg-skip-if",
                    "dg-xfail-if", "dg-xfail-run-if", "dg-require-ifunc", "dg-require-alias",
                    "dg-require-weak", "dg-require-visibility", "dg-require-stack-size",
                    "dg-require-stack-check", "dg-require-profiling", "dg-require-effective-target"}:
            feat["has an options/target dg- directive"].append(rel)
        if os.path.exists(os.path.splitext(t)[0] + ".x"):
            xfiles += 1
            feat["has a .x control file"].append(rel)
    res = {"tests": len(ts), "top": sum(1 for t in ts if os.path.dirname(t) == d.rstrip("/")),
           "features": {k: len(v) for k, v in feat.items()}, "feature_files": dict(feat),
           "builtins_by_tests": bcount.most_common(), "builtins_occ": dict(bocc),
           "dg_kinds": dgk.most_common(), "dg_options": dgopt.most_common(60), "std_options": stdopt.most_common(),
           "dg_targets": dgtarget.most_common(60), "x_files": xfiles}
    json.dump(res, open(out, "w"), indent=1)
    print(res["tests"], {k: len(v) for k, v in sorted(feat.items())})


if __name__ == "__main__":
    main()
