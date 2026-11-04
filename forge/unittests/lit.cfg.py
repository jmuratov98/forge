# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# forge's GoogleTest binaries, one forge_<component>_unittests per component, run by lit so that
# they shard and report like the rest of the suite. premake writes a lit.site.cfg.py for every
# configuration, which sets the forge_* values below and then loads this file, so lit runs on a
# configuration's directory: lit -sv build/Debug/unittests

import os

import lit.formats

if not hasattr(config, "forge_bin_dir"):
    lit_config.fatal(
        "run lit on a configuration's unittests directory, such as build/Debug/unittests; "
        "premake writes the lit.site.cfg.py there"
    )

config.name = "forge-unittests"
# Finds forge_*_unittests (.exe on Windows) in the configuration's bin directory.
config.test_format = lit.formats.GoogleTest(".", "_unittests")
config.test_source_root = config.forge_bin_dir
config.test_exec_root = config.forge_bin_dir
config.available_features.update(config.forge_features)

# On macOS each binary has a .dSYM bundle next to it, holding a file with the binary's name that is
# not a test. lit's excludes are names, not patterns.
if os.path.isdir(config.forge_bin_dir):
    config.excludes = [name for name in os.listdir(config.forge_bin_dir) if name.endswith(".dSYM")]

# Where version_test reads VERSION.
config.environment["FORGE_SOURCE_ROOT"] = config.forge_source_root

# lit runs tests in a clean environment; sanitizer settings are what a developer would want kept,
# and FORGE_SYMBOLIZER_PATH turns on the tests that need llvm-symbolizer (docs/stacktrace.md).
for name in (
    "ASAN_OPTIONS",
    "UBSAN_OPTIONS",
    "TSAN_OPTIONS",
    "LSAN_OPTIONS",
    "FORGE_SYMBOLIZER_PATH",
):
    if name in os.environ:
        config.environment[name] = os.environ[name]
