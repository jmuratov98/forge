# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""A venv with the other layout, as MSYS2's Python makes one on Windows (bin/, not Scripts\\) and a
Windows Python elsewhere: x calls it foreign, doctor names the Python that made it, and setup
replaces it. The fixture repository has only a tools.json."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

X = Path(__file__).resolve().parents[3] / "x.py"
sys.path.insert(0, str(X.parent / "utils"))

from xtool import tools  # noqa: E402
from xtool.context import Context  # noqa: E402
from xtool.host import FOREIGN_VENV_MAKERS, WINDOWS  # noqa: E402
from xtool.ui import Ui  # noqa: E402

# What the other layout and its pyvenv.cfg look like on this host.
if WINDOWS:
    OTHER_SCRIPTS, OTHER_PYTHON = "bin", "python3.12.exe"
    CONFIG = ("home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.12.11\n"
              "executable = /usr/bin/python3.12.exe\ncommand = /usr/bin/python3 -m venv /c/forge/.forge/venv\n")
    MAKER = "Python 3.12.11 (/usr/bin/python3.12.exe)"
else:
    OTHER_SCRIPTS, OTHER_PYTHON = "Scripts", "python.exe"
    CONFIG = ("home = C:\\Python314\ninclude-system-site-packages = false\nversion = 3.14.0\n"
              "executable = C:\\Python314\\python.exe\ncommand = C:\\Python314\\python.exe -m venv "
              "C:\\forge\\.forge\\venv\n")
    MAKER = "Python 3.14.0 (C:\\Python314\\python.exe)"


class ForeignVenv(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # Resolved, as x resolves --root, for comparing the paths it prints.
        self.root = Path(directory.name).resolve()
        (self.root / "utils" / "xtool").mkdir(parents=True)
        shutil.copy(X.parent / "utils" / "xtool" / "tools.json", self.root / "utils" / "xtool")
        self.ctx = Context(self.root, X.parent, Ui())
        self.environment = {name: value for name, value in os.environ.items()
                            if name not in ("FORGE_PREMAKE5", "FORGE_NINJA", "CXX")}

    def make_foreign_venv(self):
        (self.ctx.venv / OTHER_SCRIPTS).mkdir(parents=True)
        (self.ctx.venv / OTHER_SCRIPTS / OTHER_PYTHON).write_text("")
        (self.ctx.venv / "pyvenv.cfg").write_text(CONFIG)

    def x(self, *arguments):
        return subprocess.run([sys.executable, str(X), "--root", str(self.root), *arguments],
                              capture_output=True, text=True, env=self.environment)

    def test_status(self):
        self.assertEqual(tools.venv_status(self.ctx), "missing")
        self.assertIsNone(tools.venv_maker(self.ctx))
        self.make_foreign_venv()
        self.assertEqual(tools.venv_status(self.ctx), "foreign")
        self.assertEqual(tools.venv_maker(self.ctx), MAKER)

        # This Python's own layout wins, whatever else is in the directory.
        tools.venv_python(self.ctx).parent.mkdir()
        tools.venv_python(self.ctx).write_text("")
        self.assertEqual(tools.venv_status(self.ctx), "missing")
        (self.ctx.venv / tools.STAMP).write_text(json.dumps(tools.expected_venv_stamp(self.ctx)))
        self.assertEqual(tools.venv_status(self.ctx), "ok")

    def test_maker_before_python_3_11(self):
        # Python 3.10 writes no executable.
        self.ctx.venv.mkdir(parents=True)
        (self.ctx.venv / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.10.12\n")
        self.assertEqual(tools.venv_maker(self.ctx), "Python 3.10.12 (/usr/bin)")

    def test_commands_that_need_the_venv_stop(self):
        self.make_foreign_venv()
        lit = self.x("run", "lit")
        self.assertEqual(lit.returncode, 3)
        self.assertIn(f"was made by {MAKER}, {FOREIGN_VENV_MAKERS}: run ./x setup", lit.stderr)

    def test_doctor_names_the_python_that_made_it(self):
        self.make_foreign_venv()
        doctor = self.x("doctor")
        self.assertEqual(doctor.returncode, 3)
        row = next(line for line in doctor.stdout.splitlines() if line.startswith("venv "))
        self.assertEqual(row.split()[1], "foreign")
        self.assertIn(f"made by {MAKER}, {FOREIGN_VENV_MAKERS}: run ./x setup to replace it", row)

    def test_setup_replaces_it(self):
        self.make_foreign_venv()
        setup = self.x("-n", "setup", "--only", "venv")
        self.assertEqual(setup.returncode, 0, setup.stderr)
        self.assertIn("replacing", setup.stdout)
        self.assertIn(f"it was made by {MAKER}, {FOREIGN_VENV_MAKERS}", setup.stdout)
        self.assertIn(f"-m venv {self.ctx.venv}", setup.stdout)


if __name__ == "__main__":
    unittest.main()
