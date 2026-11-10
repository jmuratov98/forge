#!/usr/bin/env python3
"""Accepted set: gcc-15 -fsyntax-only on every root x configuration.

usage: python3 -I accept.py                  -> WORK/accept.json
       python3 -I accept.py pedantic         -> WORK/pedantic.json
       python3 -I accept.py pedantic-noext   -> WORK/pedantic-noext.json

The default run uses only the configuration's flags. A pair is accepted when
gcc-15 exits 0. The pedantic run repeats the accepted pairs with
-Wpedantic -Wc90-c99-compat -Wc99-c11-compat -Wc11-c23-compat -Wsystem-headers
and records every diagnostic: it is GCC's own list of the extensions and
later-revision constructs the headers use without `__extension__`.
pedantic-noext adds -D__extension__= so that the constructs glibc marks with
`__extension__` are diagnosed too (acceptance is unchanged: `__extension__`
only silences pedantic diagnostics).
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DIAG_RE = re.compile(r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+): (?P<kind>warning|error|fatal error|note|pedwarn): (?P<msg>.*?)(?: \[(?P<opt>-W[^\]]+|-f[^\]]+)\])?$")
PEDANTIC = ["-Wpedantic", "-Wc90-c99-compat", "-Wc99-c11-compat", "-Wc11-c23-compat",
            "-Wsystem-headers", "-fdiagnostics-show-option", "-fno-diagnostics-show-caret",
            "-fmax-errors=0", "-fdiagnostics-color=never"]


def roots():
    out = []
    for line in open(os.path.join(common.WORK, "roots.tsv")):
        name, path, why = line.rstrip("\n").split("\t")
        if why == "kept":
            out.append(name)
    return out


def diags(stderr):
    res = []
    for ln in stderr.splitlines():
        m = DIAG_RE.match(ln)
        if m:
            res.append([m.group("file"), int(m.group("line")), m.group("kind"),
                        m.group("msg"), m.group("opt") or ""])
    return res


def one(job):
    cfg, root, extra = job
    rc, _, err = common.run_gcc(cfg, ["-fsyntax-only", "-fdiagnostics-color=never",
                                      "-fno-diagnostics-show-caret"] + extra, common.tu_for(root))
    d = diags(err)
    first_err = next((x for x in d if x[2] in ("error", "fatal error")), None)
    return cfg, root, {"rc": rc, "ok": rc == 0, "first_error": first_err,
                       "n_warning": sum(1 for x in d if x[2] == "warning"),
                       "diags": d}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "accept"
    rs = roots()
    if mode == "accept":
        jobs = [(c, r, []) for c in common.CONFIG_NAMES for r in rs]
        out_p = os.path.join(common.WORK, "accept.json")
    else:
        acc = json.load(open(os.path.join(common.WORK, "accept.json")))
        flags = PEDANTIC + (["-D__extension__="] if mode == "pedantic-noext" else [])
        jobs = [(c, r, flags) for c in common.CONFIG_NAMES for r in rs if acc[c][r]["ok"]]
        out_p = os.path.join(common.WORK, mode + ".json")
    res = {c: {} for c in common.CONFIG_NAMES}
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        for cfg, root, rec in ex.map(one, jobs):
            if mode == "accept":
                # keep only the first few diagnostics of an accepted pair
                rec["diags"] = rec["diags"][:20]
            res[cfg][root] = rec
    json.dump(res, open(out_p, "w"), indent=0, sort_keys=True)
    for c in common.CONFIG_NAMES:
        print(c, "pairs", len(res[c]), "ok", sum(1 for r in res[c].values() if r["ok"]))


if __name__ == "__main__":
    main()
