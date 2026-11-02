# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# RUN: %python %s

"""x runs on Python 3.10 and newer, so its code must parse as 3.10: checked here with whatever
Python runs the tests. ast's feature_version catches most newer syntax; it does not catch Python
3.12's f-strings that reuse their own quote inside a replacement field, which the tokenizer does."""

import ast
import tempfile
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = [ROOT / "x.py", *sorted((ROOT / "utils" / "xtool").rglob("*.py"))]


def nested_quotes(path):
    """The lines of f-strings that use their own quote character inside a replacement field."""
    if not hasattr(tokenize, "FSTRING_START"):
        return []
    found, quotes = [], []
    with open(path, "rb") as stream:
        for token in tokenize.tokenize(stream.readline):
            if token.type in (tokenize.STRING, tokenize.FSTRING_START) and quotes:
                quote = token.string.lstrip("rRbBfFuU")[:1]
                if quote in quotes:
                    found.append(token.start[0])
            if token.type == tokenize.FSTRING_START:
                quotes.append(token.string.lstrip("rRbBfFuU")[:1])
            elif token.type == tokenize.FSTRING_END:
                quotes.pop()
    return found


class SyntaxFloor(unittest.TestCase):
    def test_every_file_parses_as_python_3_10(self):
        for path in FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(), str(path), feature_version=(3, 10))
                self.assertEqual(nested_quotes(path), [], "f-strings that reuse their quote")

    def test_the_checks_catch_what_they_should(self):
        with self.assertRaises(SyntaxError):
            ast.parse("def f[T](x): pass\n", feature_version=(3, 10))
        if hasattr(tokenize, "FSTRING_START"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "f.py"
                path.write_text("a = f\"{'ok'}\"\nb = f\"{\"no\"}\"\n")
                self.assertEqual(nested_quotes(path), [2])


if __name__ == "__main__":
    unittest.main()
