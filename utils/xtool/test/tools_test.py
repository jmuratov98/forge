# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""Where x finds the LLVM tools it does not download: the variable that names one wins, then PATH."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from xtool import tools  # noqa: E402
from xtool.host import exe  # noqa: E402


class Symbolizer(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.binary = self.directory / exe("llvm-symbolizer")
        self.binary.write_text("")
        self.binary.chmod(0o755)

    def test_the_variable_wins(self):
        with mock.patch.dict(os.environ, {"FORGE_SYMBOLIZER_PATH": str(self.binary), "PATH": ""}):
            self.assertEqual(tools.find_symbolizer(), self.binary)
            self.assertEqual(tools.symbolizer_environment(), {"FORGE_SYMBOLIZER_PATH": str(self.binary)})

    def test_a_variable_naming_nothing_finds_nothing(self):
        with mock.patch.dict(os.environ, {"FORGE_SYMBOLIZER_PATH": str(self.directory / "missing")}):
            self.assertIsNone(tools.find_symbolizer())
            self.assertEqual(tools.symbolizer_environment(), {})

    def test_path(self):
        environment = {key: value for key, value in os.environ.items() if key != "FORGE_SYMBOLIZER_PATH"}
        environment["PATH"] = str(self.directory)
        with mock.patch.dict(os.environ, environment, clear=True):
            self.assertEqual(tools.find_symbolizer(), self.binary)


if __name__ == "__main__":
    unittest.main()
