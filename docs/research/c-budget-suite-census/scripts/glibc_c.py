"""Part C: what glibc 2.43's headers emit in C mode under each dialect.

Usage: python3 -I glibc_c.py DEB_ROOT OUT_JSON

Preprocesses a fixed list of root headers with gcc-16 given the
aarch64-linux-gnu identity (diag.py's gcc sysroot), once per configuration,
with -dD so macro definitions are kept. Lines from glibc or kernel headers
are kept with their file:line from the linemarkers. For each configuration
pair (for example c23 against c17) the lines present in one and absent in
the other are classified by the construct regexes in CONSTRUCTS. Nothing in
DEB_ROOT is executed.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("diag", os.path.join(HERE, "diag.py"))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

ROOTS = ("assert.h complex.h ctype.h errno.h fenv.h float.h inttypes.h iso646.h limits.h locale.h math.h "
         "setjmp.h signal.h stdarg.h stdbit.h stdbool.h stddef.h stdint.h stdio.h stdlib.h string.h tgmath.h "
         "threads.h time.h uchar.h wchar.h wctype.h strings.h unistd.h fcntl.h sys/types.h sys/stat.h "
         "sys/time.h sys/times.h sys/resource.h sys/param.h sys/wait.h sys/mman.h sched.h pthread.h dirent.h "
         "netinet/in.h arpa/inet.h libintl.h").split()
CONFIGS = {
    "c17": ["-std=c17", "-O0"], "c23": ["-std=c23", "-O0"],
    "gnu17": ["-std=gnu17", "-O0"], "gnu23": ["-std=gnu23", "-O0"],
    "c11": ["-std=c11", "-O0"], "c99": ["-std=c99", "-O0"],
    "gnu17-O2": ["-std=gnu17", "-O2"], "gnu23-O2": ["-std=gnu23", "-O2"],
    "gnu17-O2-fortify3": ["-std=gnu17", "-O2", "-D_FORTIFY_SOURCE=3"],
    "gnu17-O0-fortify3": ["-std=gnu17", "-O0", "-D_FORTIFY_SOURCE=3"],
}
PAIRS = [("c23", "c17"), ("gnu23", "gnu17"), ("c17", "c11"), ("c11", "c99"),
         ("gnu17-O2", "gnu17"), ("gnu23-O2", "gnu23"), ("gnu17-O2-fortify3", "gnu17-O2"), ("gnu17-O0-fortify3", "gnu17")]
CONSTRUCTS = {
    "_Generic": r"\b_Generic\b",
    "[[...]] attribute": r"\[\[",
    "typeof / typeof_unqual": r"\btypeof(?:_unqual)?\b",
    "__typeof__": r"\b__typeof__\b",
    "bool / true / false": r"\b(?:bool|true|false)\b",
    "_Bool": r"\b_Bool\b",
    "constexpr": r"\bconstexpr\b",
    "nullptr": r"\bnullptr\b",
    "_BitInt": r"\b_BitInt\b",
    "static_assert / _Static_assert": r"\b(?:_Static_assert|static_assert)\b",
    "_Noreturn / noreturn": r"\b(?:_Noreturn|noreturn)\b",
    "_Alignas / alignas / _Alignof": r"\b(?:_Alignas|alignas|_Alignof|alignof)\b",
    "_Thread_local / thread_local": r"\b(?:_Thread_local|thread_local)\b",
    "_Atomic": r"\b_Atomic\b",
    "char8_t / char16_t / char32_t": r"\bchar(?:8|16|32)_t\b",
    "_FloatN / _FloatNx": r"\b_Float(?:16|32|64|128)x?\b",
    "__glibc_const_generic (qualifier-preserving _Generic)": r"\b__glibc_const_generic\b",
    "__builtin_tgmath": r"\b__builtin_tgmath\b",
    "__builtin_choose_expr / __builtin_types_compatible_p": r"\b__builtin_(?:choose_expr|types_compatible_p)\b",
    "__builtin_stdc_*": r"\b__builtin_stdc_\w+",
    "__builtin_*": r"\b__builtin_\w+",
    "__extension__ statement expression": r"__extension__\s*\(\{|\(\{",
    "__extern_always_inline / extern inline function body": r"\bextern\s+__inline\b|__extern_(?:always_)?inline\b|\bextern\s+(?:__inline__|inline)\b",
    "__inline": r"\b__inline\b",
    "__attribute__": r"\b__attribute__\b",
    "asm label (__REDIRECT)": r"__asm__\s*\(\s*\"",
    "restrict": r"\b(?:__restrict|restrict)\b",
    "static array parameter [static N]": r"\[\s*static\b",
    "VLA-style parameter [n]": r"\[\s*__n\s*\]|\[\s*__len\s*\]",
}
CONSTRUCTS = {k: re.compile(v) for k, v in CONSTRUCTS.items()}
MARK = re.compile(r'^# (\d+) "([^"]*)"')


def run(deb, flags, root_hdr):
    base = [a for a in diag.sysroot_args("gcc", deb) if a != "-fsyntax-only"]
    src = f"#include <{root_hdr}>\n"
    if root_hdr == "tgmath.h":
        # gcc-16's Darwin build installs its own tgmath.h ahead of glibc's; Ubuntu's GCC does not
        src = f'#include "{os.path.join(deb, "x-libc6-dev/usr/include/tgmath.h")}"\n'
    r = subprocess.run(base + flags + ["-E", "-dD", "-x", "c", "-"], input=src, capture_output=True, text=True,
                       errors="replace")
    lines, cur, ln = [], None, 0
    incroot = os.path.join(deb, "x-")
    for line in r.stdout.splitlines():
        m = MARK.match(line)
        if m:
            cur, ln = m.group(2), int(m.group(1))
            continue
        if cur and cur.startswith(incroot) and line.strip():
            rel = re.sub(r"^.*?/usr/include/", "", cur)
            if not line.startswith("#define __") or "(" in line.split()[1]:
                lines.append((rel, ln, line.strip()))
            elif line.startswith("#define"):
                lines.append((rel, ln, line.strip()))
        ln += 1
    return lines, r.returncode, r.stderr[:400]


def main():
    deb, out = sys.argv[1:3]
    data = {}
    errs = {}
    for cfg, fl in CONFIGS.items():
        allines = {}
        for h in ROOTS:
            lines, rc, err = run(deb, fl, h)
            if rc:
                errs[f"{cfg} {h}"] = err
            for rel, ln, text in lines:
                allines[(rel, text)] = ln
        data[cfg] = allines
    res = {"errors": errs, "pairs": {}}
    for a, b in PAIRS:
        extra = {k: v for k, v in data[a].items() if k not in data[b]}
        cls = defaultdict(list)
        for (rel, text), ln in sorted(extra.items(), key=lambda x: (x[0][0], x[1])):
            hit = [k for k, rx in CONSTRUCTS.items() if rx.search(text)]
            for k in hit or ["(no listed construct)"]:
                cls[k].append(f"{rel}:{ln}: {text[:160]}")
        files = Counter(rel for (rel, _t) in extra)
        res["pairs"][f"{a} minus {b}"] = {"lines": len(extra), "files": files.most_common(),
                                         "constructs": {k: {"n": len(v), "examples": v[:12]} for k, v in cls.items()}}
        print(f"{a} minus {b}: {len(extra)} lines; " + ", ".join(f"{k} {len(v)}" for k, v in sorted(cls.items(), key=lambda x: -len(x[1]))))
    # constructs present in c17 output at all (needed by a C17 compiler regardless of the pair)
    base = {}
    for cfg in ("c99", "c11", "c17", "gnu17", "c23", "gnu23"):
        c = defaultdict(list)
        for (rel, text), ln in data[cfg].items():
            if text.startswith("#define"):
                continue  # count emitted declarations/code, not macro bodies
            for k, rx in CONSTRUCTS.items():
                if rx.search(text):
                    c[k].append(f"{rel}:{ln}: {text[:160]}")
        base[cfg] = {k: {"n": len(v), "examples": sorted(v)[:8]} for k, v in c.items()}
    res["present"] = base
    # constructs in macro bodies defined under each dialect: live only when user code expands them
    mac = {}
    for cfg in ("c99", "c11", "c17", "gnu17", "c23", "gnu23"):
        c = defaultdict(list)
        for (rel, text), ln in data[cfg].items():
            if not text.startswith("#define"):
                continue
            for k, rx in CONSTRUCTS.items():
                if k in ("__attribute__", "restrict", "__builtin_*", "__inline", "asm label (__REDIRECT)"):
                    continue
                if rx.search(text):
                    c[k].append(f"{rel}:{ln}: {text[:160]}")
        mac[cfg] = {k: {"n": len(v), "examples": sorted(v)[:12]} for k, v in c.items()}
    res["macro_bodies"] = mac
    json.dump(res, open(out, "w"), indent=1)
    print("errors:", list(errs)[:5])


if __name__ == "__main__":
    main()
