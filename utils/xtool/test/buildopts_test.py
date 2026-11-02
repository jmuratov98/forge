# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""Build options: premake arguments, build directory names, configurations, compilers, targets."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from xtool import buildopts  # noqa: E402
from xtool.ui import UsageError  # noqa: E402

# The shape forge-describe reports, sorted by trigger.
OPTIONS = [
    {"trigger": "assertions", "allowed": []},
    {"trigger": "no-tests", "allowed": []},
    {"trigger": "sanitizers", "value": "LIST", "allowed": []},
    {"trigger": "shared", "allowed": []},
    {"trigger": "std", "value": "STD", "default": "c++20", "allowed": ["c++20", "c++23"]},
    {"trigger": "to", "value": "DIR", "allowed": []},
]
CONFIGS = ["Debug", "Release", "RelDeb", "Sanitize"]


def values(**options):
    return {"forge_" + name: value for name, value in options.items()}


class ForgeArguments(unittest.TestCase):
    def test_defaults_give_no_arguments_and_the_plain_build_directory(self):
        arguments, parts = buildopts.forge_arguments(OPTIONS, values(std="c++20"))
        self.assertEqual(arguments, [])
        self.assertEqual(buildopts.build_dir_name(parts), "build")

    def test_flags_and_values_in_trigger_order(self):
        arguments, parts = buildopts.forge_arguments(
            OPTIONS, values(std="c++23", shared=True, sanitizers="thread,undefined", no_tests=True))
        self.assertEqual(arguments, ["--no-tests", "--sanitizers=thread,undefined", "--shared",
                                     "--std=c++23"])
        self.assertEqual(buildopts.build_dir_name(parts),
                         "build-no-tests-sanitizers-thread+undefined-shared-std-c++23")

    def test_to_is_not_a_forge_option(self):
        triggers = [option["trigger"] for option in buildopts.forge_options({"options": OPTIONS})]
        self.assertNotIn("to", triggers)


class Configs(unittest.TestCase):
    def test_default_is_debug(self):
        self.assertEqual(buildopts.parse_configs(None, CONFIGS), ["Debug"])

    def test_case_insensitive_list_without_repeats(self):
        self.assertEqual(buildopts.parse_configs("release,DEBUG,release", CONFIGS), ["Release", "Debug"])

    def test_all(self):
        self.assertEqual(buildopts.parse_configs("all", CONFIGS), CONFIGS)

    def test_unknown_is_a_usage_error(self):
        with self.assertRaises(UsageError) as raised:
            buildopts.parse_configs("fast", CONFIGS)
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("Debug, Release, RelDeb, Sanitize or all", str(raised.exception))


class Compilers(unittest.TestCase):
    def test_versioned_gcc_has_versioned_siblings(self):
        exists = {"/opt/bin/gcc-16", "/opt/bin/gcc-ar-16"}.__contains__
        self.assertEqual(buildopts.compiler_siblings("/opt/bin/g++-16", "gcc", exists),
                         ("/opt/bin/gcc-16", "/opt/bin/gcc-ar-16"))

    def test_clang_finds_an_unversioned_llvm_ar(self):
        exists = {"/llvm/bin/clang", "/llvm/bin/llvm-ar"}.__contains__
        self.assertEqual(buildopts.compiler_siblings("/llvm/bin/clang++", "clang", exists),
                         ("/llvm/bin/clang", "/llvm/bin/llvm-ar"))

    def test_without_an_lto_archiver_falls_back_to_ar(self):
        exists = {"/usr/bin/clang"}.__contains__
        self.assertEqual(buildopts.compiler_siblings("/usr/bin/clang++", "clang", exists),
                         ("/usr/bin/clang", "ar"))

    def test_an_unrecognized_name_has_no_c_compiler(self):
        self.assertEqual(buildopts.compiler_siblings("/usr/bin/c++", "gcc", lambda path: True),
                         (None, "ar"))

    def test_versions(self):
        self.assertEqual(buildopts.parse_compiler_version(
            "g++-16 (Homebrew GCC 16.1.0) 16.1.0\nCopyright (C) 2026 Free Software Foundation", "16.1.0"),
            ("gcc", "gcc16"))
        self.assertEqual(buildopts.parse_compiler_version(
            "Apple clang version 17.0.0 (clang-1700.0.13.5)", "17.0.0"), ("clang", "appleclang17"))
        self.assertEqual(buildopts.parse_compiler_version(
            "Ubuntu clang version 23.1.4", "23"), ("clang", "clang23"))


class Targets(unittest.TestCase):
    AVAILABLE = {"forge_core_Debug", "forge_core_Release", "forge_core_unittests_Debug",
                 "googletest_Debug", "Debug"}

    def test_short_names_per_configuration(self):
        self.assertEqual(buildopts.map_targets(["core", "core_unittests"], ["Debug"], self.AVAILABLE),
                         ["forge_core_Debug", "forge_core_unittests_Debug"])
        self.assertEqual(buildopts.map_targets(["core"], ["Debug", "Release"], self.AVAILABLE),
                         ["forge_core_Debug", "forge_core_Release"])

    def test_project_and_ninja_names_pass_through(self):
        self.assertEqual(buildopts.map_targets(["googletest", "Debug/bin/x"], ["Debug"], self.AVAILABLE),
                         ["googletest_Debug", "Debug/bin/x"])


class Verbosity(unittest.TestCase):
    def test_ninja(self):
        self.assertEqual(buildopts.ninja_verbosity(-1), ["--quiet"])
        self.assertEqual(buildopts.ninja_verbosity(0), [])
        self.assertEqual(buildopts.ninja_verbosity(1), ["-v"])
        self.assertEqual(buildopts.ninja_verbosity(2), ["-v", "-d", "explain"])


if __name__ == "__main__":
    unittest.main()
