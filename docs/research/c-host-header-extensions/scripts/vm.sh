#!/bin/sh
# Pipeline driver, run inside the VM:  sh vm.sh STEP
# Steps run in order: facts roots accept pp extract gccnames probe flips asm
set -eu
S=$(cd "$(dirname "$0")" && pwd)
W=${C13_WORK:-$HOME/c13}
mkdir -p "$W"
cd "$W"
case "$1" in
  facts)   rm -rf "$W/facts"; sh "$S/facts.sh" "$W/facts" ;;
  roots)   python3 -I "$S/roots.py" "$W/roots.tsv" ;;
  accept)  python3 -I "$S/accept.py" ;;
  pedantic) python3 -I "$S/accept.py" pedantic ;;
  pp)      python3 -I "$S/pp.py" ;;
  extract) python3 -I "$S/extract.py" ;;
  gccsrc)  sh "$S/gccsrc.sh" "$W/gccsrc" ;;
  gccnames) python3 -I "$S/gccnames.py" ;;
  probe)   python3 -I "$S/probe.py" instrument && python3 -I "$S/probe.py" run ;;
  flips)   python3 -I "$S/probe.py" flips ;;
  asm)     python3 -I "$S/asmlabels.py" ;;
  export)  rm -rf "$W/export"; mkdir -p "$W/export"; python3 -I "$S/export.py" "$W/export" ;;
  *) echo "unknown step $1" >&2; exit 2 ;;
esac
