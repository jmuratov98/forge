#!/usr/bin/env python3
"""Print '## NAME' sections of a Markdown file.  usage: sect.py FILE WIDTH NAME..."""
import sys

f, width = sys.argv[1], int(sys.argv[2])
names = set(sys.argv[3:])
on = False
for line in open(f):
    if line.startswith("## "):
        on = line[3:].strip() in names
    if on:
        print(line.rstrip("\n")[:width])
