#!/bin/sh
# Run a command with the instrumented header trees bind-mounted over the real
# ones. Only for use inside `unshare -m` (a private mount namespace), as root:
#   sudo env C13_WORK=$W unshare -m sh probe-mount.sh $W/inst CMD...
set -eu
inst=$1
shift
mount --bind "$inst/usr-include" /usr/include
mount --bind "$inst/gcc-include" /usr/lib/gcc/aarch64-linux-gnu/15/include
exec "$@"
