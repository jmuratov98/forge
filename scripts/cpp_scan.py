"""Helpers the policy checks share: finding Forge's C++ sources and reading
them without their comments and string literals.

Not a C++ lexer: it knows just enough (comments, string and character
literals, raw strings, digit separators) that a check doesn't fire on `double`
in a comment or an #include in a block comment.
"""

import os
import re

SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
                   ".inc", ".inl", ".ipp", ".tpp")
RAW_PREFIX = re.compile(r"(?:^|[^A-Za-z0-9_])(?:u8|u|U|L)?R$")


def source_files(root, subdirectory="forge", skip_directories=()):
    """Yields (path, path relative to root, with / separators) for each C++
    source under root/subdirectory, in a stable order."""
    top = os.path.join(root, subdirectory)
    for directory, subdirs, names in os.walk(top):
        subdirs[:] = sorted(d for d in subdirs if d not in skip_directories)
        for name in sorted(names):
            if name.endswith(SOURCE_SUFFIXES):
                path = os.path.join(directory, name)
                yield path, os.path.relpath(path, root).replace(os.sep, "/")


def _blank(text):
    return "".join(c if c == "\n" else " " for c in text)


def blank_comments_and_strings(text):
    """Returns text with every comment and string or character literal replaced
    by spaces, so line numbers and columns are unchanged."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if two == "//":
            j = i
            while j < n and text[j] != "\n":
                j += 2 if text[j] == "\\" and text[j + 1:j + 2] == "\n" else 1
            out.append(_blank(text[i:j]))
            i = j
        elif two == "/*":
            end = text.find("*/", i + 2)
            j = n if end < 0 else end + 2
            out.append(_blank(text[i:j]))
            i = j
        elif c == '"' and RAW_PREFIX.search(text[max(0, i - 4):i]):
            open_paren = text.find("(", i)
            delimiter = text[i + 1:open_paren] if open_paren >= 0 else ""
            end = text.find(")" + delimiter + '"', open_paren) if open_paren >= 0 else -1
            j = n if end < 0 else end + len(delimiter) + 2
            out.append('"' + _blank(text[i + 1:j]))
            i = j
        elif c == '"' or (c == "'" and not _is_digit_separator(text, i)):
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n) if j < n and text[j] == c else j
            out.append(c + _blank(text[i + 1:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _is_digit_separator(text, i):
    """True for the ' in 1'000: the identifier-like run before it starts with a digit."""
    j = i
    while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "_"):
        j -= 1
    return j < i and text[j].isdigit()
