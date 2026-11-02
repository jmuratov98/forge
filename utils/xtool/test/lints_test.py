# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""The files and layering lints, rule by rule, on fixture contents."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from xtool import lints  # noqa: E402

SPDX_CPP = b"// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception\n"


def rules(data, marker="//", header=False):
    return [(d.rule, d.line, d.column) for d in lints.check_content(Path("f"), data, marker, header)]


class Content(unittest.TestCase):
    def test_clean_source(self):
        self.assertEqual(rules(SPDX_CPP + b"\nint x;\n"), [])

    def test_each_rule_with_its_position(self):
        self.assertEqual(rules(b"int x;\n"), [("spdx", 1, 1)])
        self.assertEqual(rules(SPDX_CPP + b"int\tx;\n"), [("tab", 2, 4)])
        self.assertEqual(rules(SPDX_CPP + b"int x;  \n"), [("trailing-whitespace", 2, 7)])
        self.assertEqual(rules(SPDX_CPP + b"int x;"), [("final-newline", 2, 7)])
        self.assertEqual(rules(SPDX_CPP + b"int x;\r\nint y;\r\n"), [("crlf", 2, 7)])

    def test_pragma_once_in_headers(self):
        self.assertEqual(rules(SPDX_CPP + b"int x;\n", header=True), [("pragma-once", 1, 1)])
        self.assertEqual(rules(SPDX_CPP + b"\n#pragma once\n", header=True), [])

    def test_spdx_after_a_shebang(self):
        script = b"#!/bin/sh\n# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception\n"
        self.assertEqual(rules(script, "#"), [])
        self.assertEqual(rules(b"#!/bin/sh\necho\n", "#"), [("spdx", 2, 1)])

    def test_whitespace_only_files_skip_spdx(self):
        self.assertEqual(rules(b"{}\n", ""), [])

    def test_not_utf8(self):
        self.assertEqual(rules(b"\xff\n"), [("encoding", 1, 1)])

    def test_fix_repairs_what_it_can(self):
        fixed = lints.fix_content(b"int x;  \r\nint\ty;", "//")
        self.assertEqual(fixed, SPDX_CPP + b"\nint x;\nint\ty;\n")
        self.assertEqual(rules(fixed), [("tab", 4, 4)])

    def test_fix_puts_spdx_after_a_shebang(self):
        self.assertEqual(lints.fix_content(b"#!/bin/sh\necho\n", "#"),
                         b"#!/bin/sh\n# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception\n\necho\n")


class Scope(unittest.TestCase):
    ROOT = Path("/repo")

    def marker(self, relative):
        return lints.comment_marker(self.ROOT, self.ROOT / relative)

    def test_markers_by_kind(self):
        self.assertEqual(self.marker("forge/source/forge/core/assert.cpp"), "//")
        self.assertEqual(self.marker("premake/forge.lua"), "--")
        self.assertEqual(self.marker("utils/xtool/cli.py"), "#")
        self.assertEqual(self.marker("x"), "#")
        self.assertEqual(self.marker("x.cmd"), "@rem")
        self.assertEqual(self.marker("utils/xtool/tools.json"), "")
        self.assertEqual(self.marker(".github/workflows/ci.yml"), "#")
        self.assertEqual(self.marker(".github/ci/install-compiler.sh"), "#")
        self.assertEqual(self.marker(".github/ci/matrix.json"), "")

    def test_outside_the_scope(self):
        self.assertIsNone(self.marker("main.cpp"))
        self.assertIsNone(self.marker("forge/docs/testing.md"))
        self.assertIsNone(self.marker("third_party/googletest/googletest/src/gtest.cc"))

    def test_test_inputs_are_exempt_but_test_code_is_not(self):
        self.assertIsNone(self.marker("forge/test/host/config-errors.cpp"))
        self.assertIsNone(self.marker("forge/test/build/Inputs/fixture.lua"))
        self.assertIsNone(self.marker("utils/xtool/test/usage.test"))
        self.assertEqual(self.marker("forge/test/lit.cfg.py"), "#")
        self.assertEqual(self.marker("forge/test/host/lit.local.cfg"), "#")
        self.assertEqual(self.marker("utils/xtool/test/lints_test.py"), "#")

    def test_kind(self):
        self.assertEqual([d.rule for d in lints.check_kind(self.ROOT, self.ROOT / "forge/source/forge/core/x.cc")],
                         ["file-kind"])
        self.assertEqual(lints.check_kind(self.ROOT, self.ROOT / "forge/source/forge/core/x.cpp"), [])


class Layering(unittest.TestCase):
    COMPONENTS = {"support": [], "core": ["support"], "ir": ["core"]}
    TESTS = {"core": ["core"]}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        for relative in ("forge/include/forge/support/span.hpp", "forge/source/forge/ir/detail.hpp"):
            (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root / relative).write_text("")

    def tearDown(self):
        self.directory.cleanup()

    def check(self, relative, text):
        files = {self.root / relative: text}
        return [(d.rule, d.line, d.message) for d in lints.check_layering(
            self.root, list(files), self.COMPONENTS, self.TESTS, read=files.__getitem__)]

    def test_transitive_dependencies_are_allowed(self):
        self.assertEqual(self.check("forge/source/forge/ir/ir.cpp", '#include "forge/support/span.hpp"\n'), [])

    def test_a_dependent_cannot_be_included(self):
        found = self.check("forge/include/forge/core/core.hpp", '\n#include "forge/ir/ir.hpp"\n')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][:2], ("layering", 2))
        self.assertIn("component 'core' cannot include 'forge/ir/ir.hpp'", found[0][2])

    def test_unit_tests_follow_their_own_dependencies(self):
        self.assertEqual(self.check("forge/unittests/core/core_test.cpp", '#include <forge/support/span.hpp>\n'), [])
        self.assertIn("test 'core' cannot include",
                      self.check("forge/unittests/core/core_test.cpp", '#include "forge/ir/ir.hpp"\n')[0][2])

    def test_public_headers_never_include_private_ones(self):
        found = self.check("forge/include/forge/ir/ir.hpp", '#include "forge/ir/detail.hpp"\n')
        self.assertIn("cannot include the private header", found[0][2])
        self.assertEqual(self.check("forge/source/forge/ir/ir.cpp", '#include "forge/ir/detail.hpp"\n'), [])

    def test_undeclared_components(self):
        self.assertIn("forge.component", self.check("forge/source/forge/lexer/lexer.cpp", "")[0][2])
        self.assertIn("forge.test", self.check("forge/unittests/ir/ir_test.cpp", "")[0][2])
        self.assertIn("has no 'lexer'",
                      self.check("forge/source/forge/ir/ir.cpp", '#include "forge/lexer/token.hpp"\n')[0][2])


class Workflows(unittest.TestCase):
    ROOT = Path("/repo")

    def kind(self, relative):
        return lints.workflow_kind(self.ROOT, self.ROOT / relative)

    def test_kinds(self):
        self.assertEqual(self.kind(".github/workflows/ci.yml"), "workflow")
        self.assertEqual(self.kind(".github/workflows/release.yaml"), "workflow")
        self.assertEqual(self.kind(".github/actions/filecheck/action.yml"), "action")
        self.assertEqual(self.kind(".github/dependabot.yml"), "dependabot")

    def test_other_files_are_not_checked(self):
        self.assertIsNone(self.kind(".github/workflows/scripts/helper.yml"))
        self.assertIsNone(self.kind(".github/ci/matrix.json"))
        self.assertIsNone(self.kind(".github/ci/install-compiler.sh"))
        self.assertIsNone(self.kind("forge/workflows/ci.yml"))

    def test_actionlint_report(self):
        report = [{"message": "job \"a\" needs job \"b\" which does not exist", "filepath": ".github/workflows/ci.yml",
                   "line": 4, "column": 3, "kind": "job-needs"}]
        [diagnostic] = lints.actionlint_diagnostics(self.ROOT, report)
        self.assertEqual(diagnostic.format(lambda path: path.relative_to(self.ROOT).as_posix()),
                         '.github/workflows/ci.yml:4:3: error: job "a" needs job "b" which does not exist '
                         '[actionlint:job-needs]')
        self.assertEqual(lints.actionlint_diagnostics(self.ROOT, None), [])

    @staticmethod
    def zizmor_finding(ident, row, column, ignored=False):
        def location(kind, annotation, row, column):
            return {"symbolic": {"key": {"Local": {"verbatim_path": ".github/workflows/ci.yml"}},
                                 "annotation": annotation, "kind": kind},
                    "concrete": {"location": {"start_point": {"row": row, "column": column}}}}
        return {"ident": ident, "desc": "code injection via template expansion",
                "url": f"https://docs.zizmor.sh/audits/#{ident}", "ignored": ignored,
                "locations": [location("Hidden", "this step", 0, 0),
                              location("Primary", "may expand into attacker-controllable code", row, column)]}

    def test_zizmor_report_uses_the_primary_location_from_1(self):
        [diagnostic] = lints.zizmor_diagnostics(self.ROOT, [self.zizmor_finding("template-injection", 8, 23)])
        self.assertEqual((diagnostic.path, diagnostic.line, diagnostic.column, diagnostic.rule),
                         (self.ROOT / ".github/workflows/ci.yml", 9, 24, "zizmor:template-injection"))
        self.assertIn("may expand into attacker-controllable code", diagnostic.message)

    def test_zizmor_ignored_findings_are_dropped(self):
        self.assertEqual(lints.zizmor_diagnostics(self.ROOT, [self.zizmor_finding("artipacked", 1, 1, True)]), [])


if __name__ == "__main__":
    unittest.main()
