#!/bin/sh
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# Runs x.py with the first Python 3.10 or newer on PATH.
x=$(dirname "$0")/x.py

# In Git Bash, MSYS2 or Cygwin, x needs a native Windows CPython, and x.py stops on any other
# (utils/xtool/host.py says why). python.org's has no python3, which MSYS2's has, so the search
# below would pick MSYS2's: look for a native one first. PATH's python comes before the Python
# launcher's, so that setup-python's or an activated venv's wins, as it does on other hosts.
case $(uname -s) in
    MINGW* | MSYS* | CYGWIN*)
        native='import sys; sys.exit(sys.version_info < (3, 10) or "MSC v." not in sys.version)'
        # MSYS2 converts the paths it passes to native programs; Cygwin does not.
        script=$(cygpath -w "$x" 2>/dev/null) || script=$x
        for python in python python3; do
            if command -v "$python" >/dev/null 2>&1 && "$python" -c "$native" 2>/dev/null; then
                exec "$python" "$script" "$@"
            fi
        done
        # py -3, because a plain py may follow x.py's #!/usr/bin/env python3 to the python3 on
        # PATH, MSYS2's.
        if command -v py >/dev/null 2>&1 && py -3 -c "$native" 2>/dev/null; then
            exec py -3 "$script" "$@"
        fi
        ;;
esac

for python in python3 python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$python" >/dev/null 2>&1 &&
        "$python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        exec "$python" "$x" "$@"
    fi
done
echo "x: error: x.py needs Python 3.10 or newer on PATH" >&2
exit 3
