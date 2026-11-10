#!/usr/bin/env python3
"""Print selected fields of named packages from Debian Packages files.

usage: pkgquery.py PACKAGES_FILE NAME [NAME ...]
"""
import sys

FIELDS = ("Package", "Version", "Source", "Filename", "Size", "SHA256", "Depends", "Pre-Depends")


def main():
    path = sys.argv[1]
    names = set(sys.argv[2:])
    with open(path, encoding="utf-8", errors="replace") as f:
        data = f.read()
    for stanza in data.split("\n\n"):
        rec = {}
        for line in stanza.splitlines():
            if line[:1] in (" ", "\t") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            rec[k] = v.strip()
        if rec.get("Package") in names:
            for k in FIELDS:
                if k in rec:
                    print(f"{k}: {rec[k]}")
            print()


if __name__ == "__main__":
    main()
