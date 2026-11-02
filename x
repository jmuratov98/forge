#!/bin/sh
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# Runs x.py with the first Python 3.10 or newer on PATH.
for python in python3 python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$python" >/dev/null 2>&1 &&
        "$python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        exec "$python" "$(dirname "$0")/x.py" "$@"
    fi
done
echo "x: error: x.py needs Python 3.10 or newer on PATH" >&2
exit 3
