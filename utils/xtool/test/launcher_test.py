# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""Which Python the ./x script runs x.py with. In Git Bash, MSYS2 and Cygwin it must find a native
Windows Python before MSYS2's python3; elsewhere it takes the first Python 3.10 on PATH. Only fakes
are on PATH: uname, cygpath, and Pythons that answer the script's checks and then print how they
were run."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# The native check is the one that mentions MSC; every fake passes the version check.
FAKE_PYTHON = """\
for argument; do
    case $argument in
        *"MSC v."*) exit {status} ;;
        *version_info*) exit 0 ;;
    esac
done
echo "{name} $*"
"""


@unittest.skipIf(os.name == "nt", "the fakes are shell scripts")
class Launcher(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.bin = Path(directory.name)
        os.symlink(shutil.which("dirname"), self.bin / "dirname")
        self.fake("cygpath", 'echo "windows:$2"')

    def fake(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def pythons(self, *, native=(), msys2=()):
        for name in native:
            self.fake(name, FAKE_PYTHON.format(status=0, name=name))
        for name in msys2:
            self.fake(name, FAKE_PYTHON.format(status=1, name=name))

    def x(self, system):
        self.fake("uname", f"echo {system}\n")
        completed = subprocess.run(["/bin/sh", str(ROOT / "x"), "doctor", "-v"], capture_output=True,
                                   text=True, env={"PATH": str(self.bin)})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout.strip()

    def test_msys2_python3_is_passed_over_for_the_python_launcher(self):
        self.pythons(native=["py"], msys2=["python", "python3"])
        self.assertEqual(self.x("MSYS_NT-10.0-26100"), f"py -3 windows:{ROOT}/x.py doctor -v")

    def test_a_native_python_on_path_comes_first(self):
        self.pythons(native=["python", "py"], msys2=["python3"])
        self.assertEqual(self.x("MINGW64_NT-10.0-26100"), f"python windows:{ROOT}/x.py doctor -v")

    def test_cygwin(self):
        self.pythons(native=["python3"], msys2=["python"])
        self.assertEqual(self.x("CYGWIN_NT-10.0-26100"), f"python3 windows:{ROOT}/x.py doctor -v")

    def test_without_a_native_python_x_py_says_what_to_install(self):
        self.pythons(msys2=["python", "python3"])
        self.assertEqual(self.x("MINGW64_NT-10.0-26100"), f"python3 {ROOT}/x.py doctor -v")

    def test_other_hosts_take_the_first_python_on_path(self):
        self.pythons(native=["python", "py"], msys2=["python3"])
        self.assertEqual(self.x("Linux"), f"python3 {ROOT}/x.py doctor -v")


if __name__ == "__main__":
    unittest.main()
