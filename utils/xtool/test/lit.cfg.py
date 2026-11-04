# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# x's own tests: unit tests of its pure functions (*_test.py, unittest) and command-line tests
# (*.test) that run x with --dry-run or against a fixture repository. They need no build, so this
# suite has no site config, and ./x test runs it once rather than once per configuration.

import os
import platform
import shutil
import sys

import lit.formats

config.name = "xtool"
config.test_format = lit.formats.ShTest(execute_external=False)
config.suffixes = [".test", ".py"]
config.excludes = ["Inputs", "lit.cfg.py"]
config.test_source_root = os.path.dirname(__file__)
root = os.path.dirname(os.path.dirname(os.path.dirname(config.test_source_root)))
# Not the source tree: lit keeps each test's %t under the exec root.
config.test_exec_root = os.path.join(root, ".forge", "test", "xtool")

config.environment["LC_ALL"] = "C"
config.environment["NO_COLOR"] = "1"
config.environment["PYTHONDONTWRITEBYTECODE"] = "1"
# The tests decide which tools x sees: $CXX would change build directory names.
config.environment.pop("CXX", None)

system = {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform, sys.platform)
config.available_features.add("host-" + system)

# On Windows x finds MSVC with vswhere and vcvarsall.bat, and Visual Studio's setup API and the
# batch file find the installations through these, which lit does not pass on.
if system == "windows":
    for name in ("ProgramData", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
                 "CommonProgramFiles", "CommonProgramFiles(x86)", "windir", "LOCALAPPDATA",
                 "APPDATA"):
        if os.environ.get(name):
            config.environment[name] = os.environ[name]

# ./x test passes the premake and ninja it uses; the tests that run x's build commands need them.
for name, feature in (("FORGE_PREMAKE5", "premake"), ("FORGE_NINJA", "ninja")):
    if os.environ.get(name):
        config.environment[name] = os.environ[name]
        config.available_features.add(feature)


def quote(argument):
    if argument and not any(c in argument for c in " \t\"'\\$&|;<>()*?[]{}~#"):
        return argument
    return '"' + argument.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Run with lit's Python, the venv's, which has requests for the setup tests.
python = quote(sys.executable)
config.substitutions.append(("%python", python))
config.substitutions.append(("%x", python + " " + quote(os.path.join(root, "x.py"))))

filecheck = os.environ.get("FORGE_FILECHECK") or shutil.which("FileCheck")
if not filecheck:
    lit_config.fatal("FileCheck not found: put it on PATH or set FORGE_FILECHECK to its path")
replacement = quote(filecheck)
if platform.system() != "Windows":
    replacement = replacement.replace("\\", "\\\\")
config.substitutions.append((r"(?<![\w./\\-])FileCheck\b", replacement))
