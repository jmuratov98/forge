#!/usr/bin/env python3
"""Build a manifest mapping logical install paths (/usr/include/...) to
extracted files, across several extracted package roots.

usage: manifest.py OUT_JSON PKGNAME=ROOTDIR [PKGNAME=ROOTDIR ...]

Only regular files and symlinks under usr/include and usr/lib/gcc/*/*/include
are recorded.  Symlinks are recorded with their target (not followed).
Overlapping logical paths across packages are reported on stderr.
"""
import json
import os
import sys


def main():
    out = sys.argv[1]
    entries = {}
    overlaps = []
    for arg in sys.argv[2:]:
        pkg, root = arg.split("=", 1)
        root = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            rel_dir = os.path.relpath(dirpath, root)
            logical_dir = "/" + rel_dir if rel_dir != "." else "/"
            if not (logical_dir.startswith("/usr/include") or "/include" in logical_dir and logical_dir.startswith("/usr/lib/gcc")):
                # still descend; filter at file level
                pass
            names = list(filenames) + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
            for name in names:
                phys = os.path.join(dirpath, name)
                logical = os.path.normpath(os.path.join(logical_dir, name))
                if not (logical.startswith("/usr/include/") or (logical.startswith("/usr/lib/gcc/") and "/include/" in logical)):
                    continue
                rec = {"pkg": pkg, "phys": phys}
                if os.path.islink(phys):
                    rec["symlink"] = os.readlink(phys)
                if logical in entries:
                    overlaps.append((logical, entries[logical]["pkg"], pkg))
                    continue
                entries[logical] = rec
    with open(out, "w") as f:
        json.dump(entries, f, indent=0, sort_keys=True)
    print(f"{len(entries)} files", file=sys.stderr)
    for o in overlaps:
        print("OVERLAP", *o, file=sys.stderr)


if __name__ == "__main__":
    main()
