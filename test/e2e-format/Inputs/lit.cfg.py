# Suites that lit runs inside a test (see ../negative.test), to check how the
# end-to-end format reports a case that fails.
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
build_dir = lit_config.params["forge_build_dir"]
sys.path.insert(0, os.path.join(here, "..", "..", "..", "scripts"))
import lit_e2e_format

config.name = "e2e-format-inputs"
config.suffixes = [".c"]
config.test_source_root = here
config.test_exec_root = os.path.join(build_dir, "test", "e2e-format", "Output", "inputs")
config.environment.update(os.environ)
config.test_format = lit_e2e_format.format_from_json(
    os.path.join(build_dir, "test", "e2e_selftest_compiler.json"))
