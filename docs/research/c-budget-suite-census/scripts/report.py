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
