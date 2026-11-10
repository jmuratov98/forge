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
  pedantic) python3 -I "$S/accept.py" pedantic && python3 -I "$S/accept.py" pedantic-noext ;;
  pp)      python3 -I "$S/pp.py" ;;
  extract) python3 -I "$S/extract.py" ;;
  fob)     python3 -I "$S/pp.py" fob -D_FILE_OFFSET_BITS=64 -D_TIME_BITS=64 &&
           python3 -I "$S/extract.py" pp-fob ;;
  gccsrc)  sh "$S/gccsrc.sh" "$W/gccsrc" ;;
  gccnames) python3 -I "$S/gccnames.py" ;;
  probe)   python3 -I "$S/probe.py" instrument
           sudo env C13_WORK="$W" unshare -m sh "$S/probe-mount.sh" "$W/inst" python3 -I "$S/probe.py" run
           sudo chown -R "$(id -u):$(id -g)" "$W" ;;
  flips)   sudo env C13_WORK="$W" unshare -m sh "$S/probe-mount.sh" "$W/inst" python3 -I "$S/probe.py" flips
           sudo chown -R "$(id -u):$(id -g)" "$W" ;;
  vmscan)  python3 -I "$S/vmscan.py" ;;
  export)  rm -rf "$W/export"; mkdir -p "$W/export"; python3 -I "$S/export.py" "$W/export" ;;
  *) echo "unknown step $1" >&2; exit 2 ;;
esac
