"""backdate FILE: set FILE's modification time to 2001. untouched FILE: exit 0
only if it still has that time, that is, nothing rewrote it since."""
import os
import sys

BACKDATED = 1000000000

action, path = sys.argv[1:]
if action == "backdate":
    os.utime(path, (BACKDATED, BACKDATED))
elif action == "untouched":
    sys.exit(0 if int(os.stat(path).st_mtime) == BACKDATED else "%s was rewritten" % path)
