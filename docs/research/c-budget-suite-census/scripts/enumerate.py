"""Enumerate the programs llvm-test-suite builds under the requested trees.

Usage: python3 -I enumerate.py LTS_ROOT OUT_JSON

Reads CMakeLists.txt files as text (never runs CMake). Evaluates a fixed
configuration: ARCH=AArch64, TARGET_OS=CMAKE_SYSTEM_NAME=Linux,
ENDIAN=little, no SMALL_/LARGE_PROBLEM_SIZE, TEST_SUITE_BENCHMARKING_ONLY off.
Directory-scope variables (CFLAGS, CPPFLAGS, CXXFLAGS, LDFLAGS, FP_TOLERANCE,
FP_ABSTOLERANCE, NO_REFERENCE_OUTPUT, HASH_PROGRAM_OUTPUT, Source,
add_definitions) are inherited by add_subdirectory children, as in CMake.
Conditions the evaluator does not know are recorded in 'unknown_conds' and
treated as false.
"""
import json
import os
import re
import sys

ROOTS = ["SingleSource/Benchmarks", "MultiSource/Benchmarks",
         "MultiSource/Applications/ClamAV", "MultiSource/Applications/SPASS",
         "MultiSource/Applications/sqlite3", "MultiSource/Applications/JM/lencod"]
KNOWN = {"ARCH": "AArch64", "TARGET_OS": "Linux", "CMAKE_SYSTEM_NAME": "Linux",
         "ENDIAN": "little"}
# Variables whose truth value is fixed for this configuration.
TRUTH = {"SMALL_PROBLEM_SIZE": False, "LARGE_PROBLEM_SIZE": False,
         "TEST_SUITE_BENCHMARKING_ONLY": False, "MIPS_IS_MIPS64_ENABLED": False,
         "BEMAN_EXECUTION_HAVE_CXX23": True,
         # check_* results assumed for Ubuntu 26.04 arm64 with GCC:
         "HAVE_RE_COMP": True,            # re_comp is exported by glibc's libc
         "HAVE_SGTTY_INCLUDE": True,      # libc6-dev 2.43 ships /usr/include/sgtty.h
         "HAVE_SYS_QUEUE_INCLUDE": True,  # libc6-dev ships sys/queue.h (C++ only user)
         "HAS_AARCH64_FMV": False,        # needs __init_cpu_features from the runtime
         "COMPILER_HAS_NO_DEFINE_TARGET_OS_MACROS": False}  # clang-only flag
SRC_EXT = (".c", ".cpp", ".cc")


def tokenize(text):
    """Yield (command, [args], line) from CMake text."""
    i, n, line = 0, len(text), 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1; i += 1; continue
        if c.isspace():
            i += 1; continue
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[i:])
        if not m:
            i += 1; continue
        name = m.group(0); i += len(name)
        while i < n and text[i] in " \t":
            i += 1
        if i >= n or text[i] != "(":
            continue
        start_line = line
        i += 1; depth = 1; args = []; cur = ""; quoted = False
        while i < n and depth:
            c = text[i]
            if c == "\n":
                line += 1
            if quoted:
                if c == "\\" and i + 1 < n:
                    cur += text[i:i + 2]; i += 2; continue
                if c == '"':
                    quoted = False; args.append(cur); cur = None
                else:
                    cur += c
                i += 1; continue
            if c == '"' and cur:
                # quote inside an unquoted argument: CMake keeps it literally
                j = text.index('"', i + 1)
                cur += text[i:j + 1]; i = j + 1; continue
            if c == '"':
                quoted = True; cur = ""; i += 1; continue
            if c == "#":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if c == "(":
                depth += 1; cur = (cur or "") + c
            elif c == ")":
                depth -= 1
                if depth:
                    cur = (cur or "") + c
            elif c.isspace():
                if cur:
                    args.append(cur)
                cur = ""
            else:
                cur = (cur or "") + c
            i += 1
        if cur:
            args.append(cur)
        yield name.lower(), [a for a in args if a is not None], start_line


def expand(s, vars_):
    def rep(m):
        v = vars_.get(m.group(1))
        if v is None:
            return ""
        return ";".join(v) if isinstance(v, list) else v
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\$\{([A-Za-z0-9_]+)\}", rep, s)
    return s


def eval_cond(args, vars_, unknown):
    toks = [expand(a, vars_) if a.startswith("${") else a for a in args]
    pos = 0

    def atom():
        nonlocal pos
        t = toks[pos]
        if t == "(":
            pos += 1; v = orx(); pos += 1; return v
        if t.startswith("(") and len(t) > 1:  # "(NOT" style glued tokens
            toks[pos] = t[1:]; toks.insert(pos, "("); return atom()
        if t == "NOT":
            pos += 1; return not atom()
        if t == "DEFINED":
            name = toks[pos + 1]; pos += 2
            return TRUTH.get(name, name in KNOWN)
        if pos + 2 <= len(toks) - 1 and toks[pos + 1] in ("STREQUAL", "MATCHES", "VERSION_LESS"):
            lhs, op, rhs = toks[pos], toks[pos + 1], toks[pos + 2].rstrip(")")
            closing = toks[pos + 2].count(")")
            pos += 3
            for _ in range(closing):
                toks.insert(pos, ")")
            lhs = KNOWN.get(lhs, lhs)
            if op == "STREQUAL":
                return lhs == rhs
            if op == "MATCHES":
                return re.search(rhs, lhs) is not None
            return False  # CMAKE_VERSION VERSION_LESS: assume new CMake
        pos += 1
        if t in TRUTH:
            return TRUTH[t]
        unknown.append(t)
        return False

    def andx():
        nonlocal pos
        v = atom()
        while pos < len(toks) and toks[pos] == "AND":
            pos += 1; v = atom() and v
        return v

    def orx():
        nonlocal pos
        v = andx()
        while pos < len(toks) and toks[pos] == "OR":
            pos += 1; v = andx() or v
        return v

    # split glued parentheses: "(NOT" and "Darwin")" handled lazily above
    flat = []
    for t in toks:
        while t.startswith("(") and len(t) > 1:
            flat.append("("); t = t[1:]
        tail = 0
        while t.endswith(")") and len(t) > 1 and t.count("(") < t.count(")"):
            t = t[:-1]; tail += 1
        flat.append(t); flat.extend([")"] * tail)
    toks[:] = flat
    try:
        return orx()
    except IndexError:
        unknown.append(" ".join(args))
        return False


def glob_sources(d):
    return sorted(f for f in os.listdir(d) if f.endswith(SRC_EXT) and os.path.isfile(os.path.join(d, f)))


def ref_output(d, name):
    for suf in (".little-endian", ".Linux", ""):
        p = os.path.join(d, name + ".reference_output" + suf)
        if os.path.exists(p):
            return os.path.basename(p)
    return None


def process(root, rel, inherited, programs, unknown_conds):
    d = os.path.join(root, rel)
    cm = os.path.join(d, "CMakeLists.txt")
    if not os.path.exists(cm):
        return
    vars_ = {k: (list(v) if isinstance(v, list) else v) for k, v in inherited.items()}
    vars_["CMAKE_CURRENT_SOURCE_DIR"] = d
    vars_["CMAKE_SOURCE_DIR"] = root
    props = []  # (targets, prop, value)
    extra = []  # (target, kind, args)
    targets = []
    stack = []  # list of [active, taken]
    text = open(cm, encoding="utf-8", errors="replace").read()
    for cmd, args, line in tokenize(text):
        active = all(s[0] for s in stack)
        if cmd == "if":
            unk = []
            v = eval_cond(args, vars_, unk) if active else False
            if unk and active:
                unknown_conds.append(f"{rel}:{line}: if({' '.join(args)}) unknown={unk}")
            stack.append([v, v]); continue
        if cmd == "elseif":
            unk = []
            s = stack[-1]
            outer = all(x[0] for x in stack[:-1])
            v = (not s[1]) and outer and eval_cond(args, vars_, unk)
            s[0] = v; s[1] = s[1] or v; continue
        if cmd == "else":
            s = stack[-1]; s[0] = not s[1]; continue
        if cmd == "endif":
            stack.pop(); continue
        if not active:
            continue
        xargs = []
        for a in args:
            xargs.extend(x for x in expand(a, vars_).split(";") if x != "")
        if cmd == "set":
            if not xargs:
                continue
            name, vals = xargs[0], [x for x in xargs[1:] if x not in ("CACHE", "PARENT_SCOPE")]
            vars_[name] = vals if vals else None
            if vals == []:
                vars_.pop(name, None)
        elif cmd == "list" and xargs and xargs[0] == "APPEND":
            name = xargs[1]
            cur = vars_.get(name) or []
            if not isinstance(cur, list):
                cur = [cur]
            vars_[name] = cur + xargs[2:]
        elif cmd == "list" and xargs and xargs[0] == "REMOVE_ITEM":
            name = xargs[1]
            vars_[name] = [x for x in (vars_.get(name) or []) if x not in xargs[2:]]
        elif cmd == "add_definitions":
            vars_["__DEFS"] = (vars_.get("__DEFS") or []) + xargs
        elif cmd == "add_subdirectory":
            process(root, os.path.join(rel, xargs[0]), vars_, programs, unknown_conds)
        elif cmd == "set_property" and "TARGET" in xargs and "PROPERTY" in xargs:
            ti, pi = xargs.index("TARGET"), xargs.index("PROPERTY")
            props.append((xargs[ti + 1:pi], xargs[pi + 1], xargs[pi + 2:]))
        elif cmd in ("target_compile_options", "target_link_libraries", "target_include_directories"):
            extra.append((xargs[0], cmd, xargs[1:]))
        elif cmd in ("llvm_multisource", "llvm_singlesource"):
            base = {k: vars_.get(k) for k in ("CFLAGS", "CPPFLAGS", "CXXFLAGS", "LDFLAGS", "__DEFS",
                                              "FP_TOLERANCE", "FP_ABSTOLERANCE", "NO_REFERENCE_OUTPUT",
                                              "HASH_PROGRAM_OUTPUT", "RUN_OPTIONS")}
            if cmd == "llvm_multisource":
                tgt = xargs[0]
                srcs = xargs[1:] or glob_sources(d)
                srcs = [os.path.relpath(s, d) if os.path.isabs(s) else s for s in srcs]
                targets.append(dict(name=tgt, test=tgt, dir=rel, sources=srcs, kind="multi", **base))
            else:
                prefix = ""
                if "PREFIX" in xargs:
                    prefix = xargs[xargs.index("PREFIX") + 1]
                srcs = vars_.get("Source") or glob_sources(d)
                if isinstance(srcs, str):
                    srcs = [srcs]
                for s in srcs:
                    nm = os.path.splitext(os.path.basename(s))[0]
                    targets.append(dict(name=prefix + nm, test=nm, dir=rel, sources=[s], kind="single", **base))
    for t in targets:
        t["c_standard"] = None
        t["extra"] = []
        for tl, prop, val in props:
            if t["name"] in tl:
                if prop == "C_STANDARD":
                    t["c_standard"] = val[0]
                else:
                    t.setdefault("props", []).append([prop] + val)
        for tg, kind, a in extra:
            if tg == t["name"]:
                t["extra"].append([kind] + a)
        langs = {os.path.splitext(s)[1] for s in t["sources"]}
        t["lang"] = "C" if langs == {".c"} else ("C++" if ".c" not in langs else "mixed")
        nro = t["NO_REFERENCE_OUTPUT"]
        t["reference_output"] = None if nro else ref_output(os.path.join(root, t["dir"]), t["test"])
        programs.append(t)


def main():
    root, out = sys.argv[1], sys.argv[2]
    programs, unknown = [], []
    for r in ROOTS:
        process(root, r, {}, programs, unknown)
    json.dump({"programs": programs, "unknown_conds": unknown}, open(out, "w"), indent=1)
    c = [p for p in programs if p["lang"] == "C"]
    print(f"programs={len(programs)} C={len(c)} unknown_conds={len(unknown)}")
    for u in unknown:
        print("  ", u)


if __name__ == "__main__":
    main()
