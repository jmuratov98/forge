# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""x's exit codes: 2 for a usage error, 3 when what ./x setup provides is missing, 0 for help.
The setup-dependent cases run against an empty fixture repository with only a tools.json."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

X = Path(__file__).resolve().parents[3] / "x.py"


class ExitCodes(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "utils" / "xtool").mkdir(parents=True)
        shutil.copy(X.parent / "utils" / "xtool" / "tools.json", self.root / "utils" / "xtool")
        self.environment = {name: value for name, value in os.environ.items()
                            if name not in ("FORGE_PREMAKE5", "FORGE_NINJA", "CXX")}

    def tearDown(self):
        self.directory.cleanup()

    def x(self, *arguments):
        return subprocess.run([sys.executable, str(X), "--root", str(self.root), *arguments],
                              capture_output=True, text=True, env=self.environment)

    def test_help(self):
        self.assertEqual(self.x().returncode, 0)
        self.assertEqual(self.x("--help").returncode, 0)
        # A build command's help works before setup, without the forge options.
        build = self.x("build", "--help")
        self.assertEqual(build.returncode, 0)
        self.assertIn("listed once ./x setup has installed premake", " ".join(build.stdout.split()))

    def test_usage_errors(self):
        self.assertEqual(self.x("frobnicate").returncode, 2)
        self.assertEqual(self.x("setup", "--only", "nonsense").returncode, 2)
        self.assertEqual(self.x("-q", "doctor", "-v").returncode, 2)
        self.assertEqual(self.x("doctor", "--", "extra").returncode, 2)

    def test_setup_required(self):
        build = self.x("build")
        self.assertEqual(build.returncode, 3)
        self.assertIn("premake5 5.0.0 is not set up: run ./x setup", build.stderr)
        self.assertEqual(self.x("doctor").returncode, 3)
        self.assertEqual(self.x("format", "--check").returncode, 3)

    def test_clean_all_needs_no_setup(self):
        (self.root / "build").mkdir()
        made = self.root / "build-shared"
        made.mkdir()
        (made / ".forge-build.json").write_text("{}")
        clean = self.x("clean", "--all")
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertFalse(made.exists())
        self.assertTrue((self.root / "build").exists(), "./x did not make build/, so it stays")


if __name__ == "__main__":
    unittest.main()
