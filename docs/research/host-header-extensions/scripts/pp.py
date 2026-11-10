#!/usr/bin/env python3
"""Discovery aid: preprocess every root header against the *instrumented*
copy of the host tree with Xcode clang, once per configuration, and record
which conditional blocks (marker pragmas) were entered.

usage: pp.py INSTR_DIR WORK_DIR OUT_JSON GCC_DELTA_H GCC_HB_H CONFIG [CONFIG ...]

GCC-identity configurations also get -include of GCC_DELTA_H (predefine
corrections), GCC_HB_H (GCC's __has_builtin answers) and the instrumented
stdc-predef.h (GCC pre-includes it on glibc targets).

This only evaluates #if conditions with clang's preprocessor; clang's
__has_builtin/__has_attribute/__has_feature answers are clang's, not GCC's.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx  # noqa: E402

GCC_IDENTITY = [
    "-U__clang__", "-U__clang_major__", "-U__clang_minor__", "-U__clang_patchlevel__",
    "-U__clang_version__", "-U__clang_literal_encoding__", "-U__clang_wide_literal_encoding__",
    "-U__llvm__",
    "-U__GNUC__", "-U__GNUC_MINOR__", "-U__GNUC_PATCHLEVEL__", "-U__GXX_ABI_VERSION", "-U__VERSION__",
    "-D__GNUC__=15", "-D__GNUC_MINOR__=2", "-D__GNUC_PATCHLEVEL__=0",
    "-D__GXX_ABI_VERSION=1020", '-D__VERSION__="15.2.0"',
]
NEITHER_IDENTITY = [
    "-U__clang__", "-U__clang_major__", "-U__clang_minor__", "-U__clang_patchlevel__",
    "-U__clang_version__", "-U__clang_literal_encoding__", "-U__clang_wide_literal_encoding__",
    "-U__llvm__",
    "-U__GNUC__", "-U__GNUC_MINOR__", "-U__GNUC_PATCHLEVEL__", "-U__GNUC_STDC_INLINE__",
    "-U__GNUC_GNU_INLINE__", "-U__GXX_ABI_VERSION",
]
NOEH = ["-fno-exceptions", "-fno-rtti"]

CONFIGS = {
    # milestone-1 configuration with a GCC 15.2 identity
    "m1": GCC_IDENTITY + NOEH + ["-O2"],
    "m1-O0": GCC_IDENTITY + NOEH + ["-O0"],
    "m1-fortify": GCC_IDENTITY + NOEH + ["-O2", "-D_FORTIFY_SOURCE=3"],
    # same identity with exceptions and RTTI on (g++ default)
    "gcc-eh": GCC_IDENTITY + ["-O2"],
    # clang's own identity (Apple clang 17 = clang 4.2.1-compatible __GNUC__)
    "clang": NOEH + ["-O2"],
    # neither __GNUC__ nor __clang__
    "neither": NEITHER_IDENTITY + NOEH + ["-O2"],
    # GNU dialect: GCC then defines __GLIBCXX_TYPE_INT_N_0 and drops __STRICT_ANSI__
    "m1-gnu": GCC_IDENTITY + NOEH + ["-O2", "-std=gnu++20", "-U__STRICT_ANSI__",
                                     "-D__GLIBCXX_TYPE_INT_N_0=__int128",
                                     "-D__GLIBCXX_BITSIZE_INT_N_0=128"],
}
GCC_CONFIGS = {"m1", "m1-O0", "m1-fortify", "gcc-eh", "m1-gnu"}

BASE = ["clang", "-x", "c++", "-std=c++20", "--target=aarch64-unknown-linux-gnu",
        "-nostdinc", "-nostdinc++", "-E", "-P", "-w", "-Wno-unknown-pragmas"]


def main():
    instr, work, out, delta_h, hb_h = sys.argv[1:6]
    configs = sys.argv[6:]
    gcc_extra = ["-include", os.path.abspath(delta_h), "-include", os.path.abspath(hb_h),
                 "-include", os.path.join(os.path.abspath(instr), "usr/include/stdc-predef.h")]
    inc = []
    for d in hx.SEARCH:
        p = os.path.join(instr, d.lstrip("/"))
        if os.path.isdir(p):
            inc += ["-isystem", p]
    os.makedirs(work, exist_ok=True)
    result = {}
    if os.path.exists(out):
        with open(out) as f:
            result = json.load(f)
    roots = hx.root_names()
    for cfg in configs:
        per_root = {}
        union = set()
        errors = {}
        for r in roots:
            tu = os.path.join(work, "tu.cc")
            with open(tu, "w") as f:
                f.write("#include <%s>\n" % r)
            ofile = os.path.join(work, "out.i")
            cmd = BASE + CONFIGS[cfg] + inc + (gcc_extra if cfg in GCC_CONFIGS else []) + [tu, "-o", ofile]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode != 0:
                errs = [l for l in p.stderr.splitlines() if "error" in l][:5]
                errors[r] = errs
            seen = set()
            if os.path.exists(ofile):
                with open(ofile, encoding="latin-1") as f:
                    for line in f:
                        m = hx.MARK_RE.match(line)
                        if m:
                            seen.add(m.group(1))
                os.remove(ofile)
            per_root[r] = sorted(seen)
            union |= seen
        extra = ["-include gcc15-delta.h", "-include gcc15-has-builtin.h",
                 "-include stdc-predef.h"] if cfg in GCC_CONFIGS else []
        result[cfg] = {"flags": CONFIGS[cfg] + extra, "union": sorted(union), "per_root": per_root,
                       "errors": errors}
        print(cfg, len(union), "markers;", len(errors), "roots with errors", file=sys.stderr)
        for r, e in errors.items():
            print("  ", r, e[:2], file=sys.stderr)
    with open(out, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
