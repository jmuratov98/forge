#!/usr/bin/env python3
"""Raw token counts over the closure (comments stripped) as a coverage check
against scan.py.  usage: rawgrep.py MANIFEST CLOSURE_JSON SCAN_JSON"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx  # noqa: E402

PATTERNS = {
    "__builtin_": r"\b__builtin_\w+",
    "__sync_": r"\b__sync_\w+",
    "__atomic_ (call)": r"\b__atomic_\w+\s*\(",
    "[[__gnu__": r"\[\[\s*__gnu__",
    "[[gnu": r"\[\[\s*gnu\b",
    "__attribute": r"\b__attribute(?:__)?\b",
    "_Pragma": r"\b_Pragma\b",
    "#pragma": r"^\s*#\s*pragma\b",
    "__asm": r"\b__asm(?:__)?\b",
    "asm": r"\basm\b",
    "__typeof": r"\b__typeof(?:__)?\b",
    "__int128": r"\b__u?int128(?:_t)?\b",
    "_Float": r"\b_Float\d+x?\b",
    "__label__": r"\b__label__\b",
    "__extension__": r"\b__extension__\b",
    "__is_ (call)": r"\b__is_\w+\s*\(",
    "__has_ (call)": r"\b__has_\w+\s*\(",
    "__decltype": r"\b__decltype\b",
    "__restrict": r"\b__restrict(?:__)?\b",
}


def main():
    manifest = hx.load_manifest(sys.argv[1])
    closure = json.load(open(sys.argv[2]))
    counts = collections.Counter()
    names = collections.defaultdict(collections.Counter)
    for f in closure["files"]:
        for ll in hx.logical_lines(hx.read_text(manifest, f)):
            code = re.sub(r'"(?:\\.|[^"\\])*"', '""', ll.code)
            for k, p in PATTERNS.items():
                for m in re.finditer(p, code, re.M):
                    counts[k] += 1
                    names[k][m.group(0).rstrip("( ")] += 1
    for k in PATTERNS:
        print("%-16s %5d  distinct=%d" % (k, counts[k], len(names[k])))
    for k in ("__sync_", "__atomic_ (call)", "__is_ (call)", "__has_ (call)"):
        print(k, dict(names[k].most_common(200)))


if __name__ == "__main__":
    main()
