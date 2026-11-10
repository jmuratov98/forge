"""Preprocess every C program and count features in reached program lines.

Usage: python3 -I pp.py LTS_ROOT PROGRAMS_JSON DEB_ROOT OUT_JSON

Runs gcc-16 -E with the same sysroot, identity and per-program flags as
diag.py's gcc-pinned configuration (the std the suite itself passes). The
linemarkers in the output tell which lines come from files under LTS_ROOT;
only those lines are scanned, with scan.py's FEATURES regexes. Because this
is after preprocessing, inactive #if branches are gone, but macros from
system headers that expand in program code (for example glibc's assert)
are counted too. Nothing from LTS_ROOT or DEB_ROOT is executed.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


diag = load("diag")
scan = load("scan")
MARK = re.compile(r'^# (\d+) "([^"]*)"')


def main():
    root, pj, deb, out = sys.argv[1:5]
    base = [a for a in diag.sysroot_args("gcc", deb) if a not in ("-fsyntax-only",)] + ["-E", "-w"]
    progs = [p for p in json.load(open(pj))["programs"] if p["lang"] == "C"]
    rootn = os.path.realpath(root) + "/"
    jobs, meta = [], []
    for p in progs:
        pdir = os.path.join(root, p["dir"])
        pf = diag.prog_flags(p, True)
        own = [f for f in (p["CFLAGS"] or []) + (p["CPPFLAGS"] or []) if f.startswith("-std=")]
        if own:
            pf = own[-1:] + pf
        elif p["c_standard"]:
            pf = ["-std=gnu" + p["c_standard"].replace("90", "89")] + pf
        for s in p["sources"]:
            jobs.append((base + pf + [s], pdir))
            meta.append(p)

    def run(job):
        r = subprocess.run(job[0], cwd=job[1], capture_output=True, text=True, errors="replace")
        cur, keep, cwd = None, [], job[1]
        for line in r.stdout.splitlines():
            m = MARK.match(line)
            if m:
                path = os.path.realpath(os.path.join(cwd, m.group(2)))
                cur = path.startswith(rootn)
                continue
            if cur:
                keep.append(line)
        return "\n".join(keep), r.returncode

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(run, jobs))
    res = {}
    for p, (text, rc) in zip(meta, results):
        k = p["dir"] + "|" + p["name"]
        e = res.setdefault(k, {"name": p["name"], "dir": p["dir"], "features": Counter(),
                               "builtins": Counter(), "attributes": Counter(), "pragmas": Counter(),
                               "rc": []})
        e["rc"].append(rc)
        code, strs = scan.strip(text)
        for name, rx in scan.FEATURES.items():
            n = len(rx.findall(code))
            if n:
                e["features"][name] += n
        e["builtins"].update(scan.BUILTIN.findall(code))
        e["attributes"].update(scan.attr_names(code))
        for a, b in scan.PRAGMA.findall(code):
            e["pragmas"][(a + " " + b).strip()] += 1
        n = sum(len(scan.FMT_L.findall(s.replace("%%", ""))) for s in strs)
        if n:
            e["features"]["printf_L"] += n
    json.dump(list(res.values()), open(out, "w"), indent=0)
    print(f"programs={len(res)} nonzero_rc={sum(1 for e in res.values() if any(e['rc']))}")


if __name__ == "__main__":
    main()
