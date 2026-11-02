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

# lit runs tests in a clean environment; sanitizer settings are what a developer would want kept.
for name in ("ASAN_OPTIONS", "UBSAN_OPTIONS", "TSAN_OPTIONS", "LSAN_OPTIONS"):
    if name in os.environ:
        config.environment[name] = os.environ[name]
