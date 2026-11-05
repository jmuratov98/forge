# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""The Pythons x stops on: on Windows every one but a native CPython, which MSVC builds. The
sys.version strings are those of real builds."""

import contextlib
import io
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "utils"))

from xtool import cli, host  # noqa: E402

NATIVE = "3.14.0 (tags/v3.14.0:ebf955d, Oct  7 2025, 10:15:03) [MSC v.1944 64 bit (AMD64)]"
NATIVE_ARM64 = "3.14.0 (tags/v3.14.0:ebf955d, Oct  7 2025, 10:30:34) [MSC v.1944 64 bit (ARM64)]"
MSYS2 = "3.12.11 (main, Jun  4 2025, 10:42:00)  [GCC 15.1.0]"
CYGWIN = "3.9.16 (main, Mar  8 2023, 22:47:22) \n[GCC 11.3.0]"
UCRT64 = "3.12.11 (main, Jun  4 2025, 10:42:00)  [GCC 15.1.0 64 bit (AMD64)]"
CLANG64 = "3.12.11 (main, Jun  4 2025, 10:42:00)  [Clang 20.1.7 ]"
LINUX = "3.12.3 (main, Aug 14 2025, 17:47:21) [GCC 13.3.0]"
MACOS = "3.15.1 (main, Oct  8 2026, 12:00:00) [Clang 17.0.0 (clang-1700.6.3.2)]"


class ForeignPython(unittest.TestCase):
    def test_native_windows_pythons(self):
        self.assertIsNone(host.foreign_python("win32", NATIVE, "Windows"))
        self.assertIsNone(host.foreign_python("win32", NATIVE_ARM64, "Windows"))

    def test_msys2_and_cygwin(self):
        self.assertEqual(host.foreign_python("cygwin", MSYS2, "MSYS_NT-10.0-26100"), "MSYS2's Python")
        # MSYS2's Python in a MinGW shell, and the platform name MSYS2 once gave its Python.
        self.assertEqual(host.foreign_python("cygwin", MSYS2, "MINGW64_NT-10.0-26100"), "MSYS2's Python")
        self.assertEqual(host.foreign_python("msys", MSYS2, "MSYS_NT-10.0-26100"), "MSYS2's Python")
        self.assertEqual(host.foreign_python("cygwin", CYGWIN, "CYGWIN_NT-10.0-26100"), "Cygwin's Python")

    def test_mingw_builds(self):
        self.assertEqual(host.foreign_python("win32", UCRT64, "Windows"), "a MinGW build of Python")
        self.assertEqual(host.foreign_python("win32", CLANG64, "Windows"), "a MinGW build of Python")

    def test_other_hosts(self):
        self.assertIsNone(host.foreign_python("linux", LINUX, "Linux"))
        self.assertIsNone(host.foreign_python("darwin", MACOS, "Darwin"))


class RequireNativePython(unittest.TestCase):
    def test_x_stops_with_what_to_install(self):
        msys2 = types.SimpleNamespace(platform="cygwin", version=MSYS2, executable="/usr/bin/python3.12")
        system = types.SimpleNamespace(system=lambda: "MSYS_NT-10.0-26100")
        stderr = io.StringIO()
        with mock.patch.object(host, "sys", msys2), mock.patch.object(host, "platform", system), \
                contextlib.redirect_stderr(stderr):
            code = cli.main(str(ROOT), ["--help"])
        self.assertEqual(code, 3)
        message = " ".join(stderr.getvalue().split())
        self.assertIn("x: error: x needs a native Windows Python 3.10 or newer", message)
        self.assertIn("/usr/bin/python3.12 is MSYS2's Python", message)
        self.assertIn("MSYS2_PATH_TYPE=inherit", message)


if __name__ == "__main__":
    unittest.main()
