"""Run -fsyntax-only over every C program and keep program-source diagnostics.

Usage: python3 -I diag.py LTS_ROOT PROGRAMS_JSON DEB_ROOT OUT_JSON CONFIG

DEB_ROOT holds x-libc6-dev/ and x-linux-libc-dev/ (extracted Ubuntu 26.04
arm64 packages). Every compile uses those glibc 2.43 headers instead of a
host SDK. CONFIG is one of the keys of CONFIGS below. The program's own -D,
-U, -I, -include and -f flags are passed; its -w, -std, -O and link flags
are dropped. Its -W flags are dropped for clang (so the feature warnings
fire) and kept for gcc (they are how the suite builds under GCC 14+, and
the gcc runs measure whether the program compiles).
Only diagnostics whose file lies under LTS_ROOT are kept. Nothing from
LTS_ROOT or DEB_ROOT is executed: they are only compiler inputs.
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

DOWNGRADE = ["-Wno-error=implicit-function-declaration", "-Wno-error=implicit-int",
             "-Wno-error=int-conversion", "-Wno-error=incompatible-pointer-types",
             "-Wno-error=return-type"]
CLANG_DOWNGRADE = DOWNGRADE + ["-Wno-error=incompatible-function-pointer-types",
                               "-Wno-error=deprecated-non-prototype"]
GCC_DOWNGRADE = []  # gcc runs keep GCC's default errors: that is what is measured

CLANG_DIAG = ["-pedantic", "-Wvla", "-Wgnu", "-Wc23-extensions", "-Wimplicit-int",
              "-Wimplicit-function-declaration", "-Wdeprecated-non-prototype",
              "-Wstrict-prototypes", "-Wno-error"]

CONFIGS = {
    # clang, Linux target, GNU dialects; the -pedantic extension warnings name the feature
    "clang-gnu17": ("clang", ["-std=gnu17"] + CLANG_DIAG),
    "clang-gnu99": ("clang", ["-std=gnu99", "-pedantic", "-Wc11-extensions", "-Wno-error"]),
    "clang-gnu89": ("clang", ["-std=gnu89", "-pedantic", "-Wno-error"]),
    # gcc-16 (Darwin-hosted), glibc headers, GCC's own default diagnostics only
    "gcc-default": ("gcc", []),
    "gcc-gnu17": ("gcc", ["-std=gnu17"]),
    # what the suite itself asks for: C_STANDARD N -> -std=gnuN (CMake's
    # C_EXTENSIONS defaults to ON); a -std= in the program's CFLAGS wins
    "gcc-pinned": ("gcc", []),
}

LOC_RE = re.compile(r"^([^:\s][^:]*):(\d+):(\d+): (warning|error|fatal error): (.*)$")


def sysroot_args(kind, deb):
    libc = os.path.join(deb, "x-libc6-dev/usr/include")
    kern = os.path.join(deb, "x-linux-libc-dev/usr/include")
    inc = [libc + "/aarch64-linux-gnu", kern + "/aarch64-linux-gnu", libc, kern]
    if kind == "clang":
        res = subprocess.run(["clang", "-print-resource-dir"], capture_output=True, text=True).stdout.strip()
        args = ["clang", "--target=aarch64-unknown-linux-gnu", "-nostdinc", "-isystem", res + "/include"]
        args += CLANG_DOWNGRADE
    else:
        res = subprocess.run(["gcc-16", "-print-file-name=include"], capture_output=True, text=True).stdout.strip()
        args = ["gcc-16", "-nostdinc", "-isystem", res,
                # impose the aarch64-linux-gnu identity on the Darwin-targeted driver
                "-U__APPLE__", "-U__MACH__", "-U__APPLE_CC__",
                "-U__ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__",
                "-U__ENVIRONMENT_OS_VERSION_MIN_REQUIRED__",
                "-D__linux__=1", "-D__linux=1", "-Dlinux=1", "-D__gnu_linux__=1",
                "-D__unix__=1", "-D__unix=1", "-Dunix=1", "-D__ELF__=1", "-funsigned-char"]
        args += GCC_DOWNGRADE
    for d in inc:
        args += ["-isystem", d]
    args += ["-include", os.path.join(libc, "stdc-predef.h")]
    return args + ["-fsyntax-only", "-fdiagnostics-show-option", "-fno-diagnostics-color",
                   "-fmax-errors=0" if kind == "gcc" else "-ferror-limit=0"]


def prog_flags(p, keep_w):
    out = ["-DNDEBUG"]  # top-level CMakeLists.txt: add_definitions(-DNDEBUG)
    flags = (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) + (p["CXXFLAGS"] or []) + (p["__DEFS"] or [])
    i = 0
    while i < len(flags):
        f = flags[i]
        if f in ("-I", "-include", "-D", "-U") and i + 1 < len(flags):
            out += [f, flags[i + 1]]; i += 2; continue
        if f.startswith(("-D", "-U", "-I")) or f == "-pthread":
            out.append(f)
        elif keep_w and f.startswith("-W") and not f.startswith("-Werror=date-time"):
            out.append(f)
        elif f.startswith("-f") and not f.startswith("-fno-define-target-os-macros"):
            out.append(f)
        i += 1
    for e in p["extra"]:
        if e[0] == "target_include_directories":
            out += ["-I" + x for x in e[1:] if os.path.isabs(x)]
    return out


def run_one(job):
    cmd, cwd = job
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace")
    return r.returncode, r.stderr


def main():
    root, pj, deb, out, cfg = sys.argv[1:6]
    kind, extra = CONFIGS[cfg]
    base = sysroot_args(kind, deb) + extra
    progs = [p for p in json.load(open(pj))["programs"] if p["lang"] == "C"]
    jobs, meta = [], []
    for p in progs:
        pdir = os.path.join(root, p["dir"])
        pf = prog_flags(p, kind == "gcc")
        if cfg == "gcc-pinned":
            own = [f for f in (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) if f.startswith("-std=")]
            if own:
                pf = own[-1:] + pf
            elif p["c_standard"]:
                pf = ["-std=gnu" + p["c_standard"].replace("90", "89")] + pf
        for s in p["sources"]:
            jobs.append((base + pf + [s], pdir))
            meta.append((p["name"], p["dir"], s))
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(run_one, jobs))
    rootn = os.path.realpath(root) + "/"
    res = {}
    for (name, d, s), (rc, err) in zip(meta, results):
        key = d + "|" + name
        ent = res.setdefault(key, {"name": name, "dir": d, "files": {}, "diags": [], "fatal": []})
        ent["files"][s] = rc
        for line in err.splitlines():
            m = LOC_RE.match(line)
            if not m:
                continue
            path = os.path.realpath(os.path.join(os.path.join(root, d), m.group(1)))
            if not path.startswith(rootn):
                continue
            msg = m.group(5)
            flag = re.search(r"\[(-W[^\]]+|-fpermissive)\]$", msg)
            ent["diags"].append([os.path.relpath(path, rootn), int(m.group(2)), m.group(4),
                                 flag.group(1) if flag else "", re.sub(r"\s*\[[^\]]+\]$", "", msg)])
            if m.group(4) == "fatal error":
                ent["fatal"].append(msg)
    json.dump({"config": cfg, "cmd_base": base, "programs": list(res.values())}, open(out, "w"), indent=0)
    nerr = sum(1 for e in res.values() if any(x[2] != "warning" for x in e["diags"]))
    print(f"{cfg}: programs={len(res)} files={len(jobs)} programs_with_errors={nerr}")


if __name__ == "__main__":
    main()
