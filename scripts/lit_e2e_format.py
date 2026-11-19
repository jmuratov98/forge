"""The lit test format for end-to-end cases (docs/testing.md).

A case is one .c file with no RUN: lines. The format compiles it with the
compiler under test, runs the result, and compares its exit code and stdout
with the expectation block at the end of the file. lit's REQUIRES: and
UNSUPPORTED: lines work as usual.
"""

import json
import os
import shlex
import sys

import lit.Test
import lit.TestRunner
import lit.formats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e_cases  # noqa: E402


class E2EFormat(lit.formats.FileBasedTest):
    def __init__(self, compile_command):
        """compile_command is a list; {src}, {out} and {obj} are filled in."""
        self.compile_command = compile_command

    def execute(self, test, litConfig):
        parsed = lit.TestRunner.parseIntegratedTestScript(test, require_script=False)
        if isinstance(parsed, lit.Test.Result):
            return parsed
        if litConfig.noExecute:
            return lit.Test.Result(lit.Test.PASS)

        source = test.getSourcePath()
        with open(source, encoding="utf-8") as case:
            text = case.read()
        tmp_dir, _ = lit.TestRunner.getTempPaths(test)
        timeout = litConfig.maxIndividualTestTime or e2e_cases.DEFAULT_TIMEOUT
        try:
            expected = e2e_cases.parse_expectation(text)
            actual = e2e_cases.build_and_run(source, self.compile_command, tmp_dir,
                                             env=test.config.environment, timeout=timeout)
        except e2e_cases.CaseError as error:
            return lit.Test.Result(lit.Test.FAIL, str(error))

        problem = e2e_cases.compare(expected, actual)
        if problem:
            return lit.Test.Result(lit.Test.FAIL, problem)
        return lit.Test.Result(lit.Test.PASS)


def compile_command_from(config, lit_config, default):
    """The `e2e_compile_command` parameter (a command line) overrides default."""
    override = lit_config.params.get("e2e_compile_command")
    return shlex.split(override) if override else default


def format_from_json(path):
    """A format whose compile command is the JSON list in path; the self-test
    suites use the host's C compiler in place of Forge this way."""
    with open(path, encoding="utf-8") as command:
        return E2EFormat(json.load(command))
