"""Shared definitions for the C-mode host header extension pipeline.

Every script runs inside the Lima VM (Ubuntu 26.04 arm64) with `python3 -I`.
WORK is the VM-local work directory; raw dumps stay there, small results are
copied to the repo's data/ directory by the caller.
"""
import os
import re
import subprocess

GCC = "gcc-15"
WORK = os.path.expanduser(os.environ.get("C13_WORK", "~/c13"))

# The eight milestone-1 C configurations. gnu23 is GCC 15's default, so it
# passes no -std (facts.sh checks that its predefines equal -std=gnu23's).
CONFIGS = [
    ("gnu89", ["-std=gnu89"]),
    ("gnu89+gs", ["-std=gnu89", "-D_GNU_SOURCE"]),
    ("gnu99", ["-std=gnu99"]),
    ("gnu99+gs", ["-std=gnu99", "-D_GNU_SOURCE"]),
    ("gnu17", ["-std=gnu17"]),
    ("gnu17+gs", ["-std=gnu17", "-D_GNU_SOURCE"]),
    ("gnu23", []),
    ("gnu23+gs", ["-D_GNU_SOURCE"]),
]
CONFIG_NAMES = [c for c, _ in CONFIGS]
CONFIG_FLAGS = dict(CONFIGS)
BASE_FLAGS = ["-O0", "-x", "c"]

# Where each header comes from.
GCC_INC = "/usr/lib/gcc/aarch64-linux-gnu/15/include"
MULTIARCH = "/usr/include/aarch64-linux-gnu"


def run_gcc(cfg, extra, src, timeout=120):
    """Run gcc-15 for configuration cfg on the source text src (stdin)."""
    cmd = [GCC] + BASE_FLAGS + CONFIG_FLAGS[cfg] + extra + ["-"]
    p = subprocess.run(cmd, input=src.encode(), capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def tu_for(root):
    return "#include <%s>\n" % root


_owner_cache = {}


def owner(path):
    """Package-level origin of a header path: glibc, kernel, gcc, or other."""
    if path in _owner_cache:
        return _owner_cache[path]
    p = os.path.normpath(path)
    if p.startswith(GCC_INC + "/"):
        o = "gcc"
    elif p.startswith("/usr/include/"):
        o = PKG_OF.get(p)
        if o is None:
            o = "other"
    elif p in ("<built-in>", "<command-line>", "<stdin>"):
        o = p
    else:
        o = "other"
    _owner_cache[path] = o
    return o


def short(path):
    """Shorten a header path for tables."""
    p = os.path.normpath(path)
    if p.startswith(GCC_INC + "/"):
        return "gcc/" + p[len(GCC_INC) + 1:]
    if p.startswith(MULTIARCH + "/"):
        return "aarch64/" + p[len(MULTIARCH) + 1:]
    if p.startswith("/usr/include/"):
        return p[len("/usr/include/"):]
    return p


def load_pkg_map():
    """Map every /usr/include file to the package that ships it."""
    m = {}
    for pkg, tag in (("libc6-dev", "glibc"), ("linux-libc-dev", "kernel")):
        out = subprocess.run(["dpkg", "-L", pkg], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("/usr/include/"):
                m[os.path.normpath(line)] = tag
    return m


PKG_OF = load_pkg_map() if os.path.exists("/usr/bin/dpkg") else {}

# ---------------------------------------------------------------- tokenizer

TOKEN_RE = re.compile(r"""
    (?P<str>(?:u8|u|U|L)?"(?:\\.|[^"\\\n])*")
  | (?P<chr>(?:u8|u|U|L)?'(?:\\.|[^'\\\n])*')
  | (?P<num>\.?\d(?:[eEpP][+-]|[A-Za-z0-9_.']|)*)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<punct>\#\#|::|\.\.\.|->|<<=|>>=|<<|>>|[-+*/%&|^!=<>]=|&&|\|\||\+\+|--|[^\sA-Za-z0-9_])
""", re.X)


def tokenize(code):
    return [(m.lastgroup, m.group(m.lastgroup)) for m in TOKEN_RE.finditer(code)]


def strip_comments(text):
    """Blank out comments, keeping newlines and string literals intact."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(text[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


_src_cache = {}


def source_lines(path):
    """Comment-stripped physical lines of a header (1-based list)."""
    if path not in _src_cache:
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            txt = ""
        _src_cache[path] = [""] + strip_comments(txt).split("\n")
    return _src_cache[path]


# ------------------------------------------------------- -E output parsing

LINEMARKER_RE = re.compile(r'^# (\d+) "((?:\\.|[^"\\])*)"((?: \d)*)\s*$')


def parse_i(text):
    """Parse gcc -E -dD output.

    Returns a list of records (kind, file, line, payload):
      ('code', file, line, text)   an emitted source line
      ('define', file, line, text) a #define from -dD (text after '#define ')
      ('undef', file, line, name)
      ('pragma', file, line, text) text after '#pragma '
      ('enter', file, 0, flags)    a linemarker with flag 1 (file opened)
    """
    recs = []
    cur_file, cur_line = "<stdin>", 1
    for raw in text.split("\n"):
        if raw.startswith("# "):
            m = LINEMARKER_RE.match(raw)
            if m:
                cur_line = int(m.group(1))
                cur_file = m.group(2).encode().decode("unicode_escape")
                flags = m.group(3).split()
                if "1" in flags:
                    recs.append(("enter", cur_file, 0, flags))
                continue
        if raw.startswith("#define "):
            recs.append(("define", cur_file, cur_line, raw[8:]))
        elif raw.startswith("#undef "):
            recs.append(("undef", cur_file, cur_line, raw[7:].strip()))
        elif raw.startswith("#pragma "):
            recs.append(("pragma", cur_file, cur_line, raw[8:]))
        elif raw.strip():
            recs.append(("code", cur_file, cur_line, raw))
        cur_line += 1
    return recs


DEFINE_RE = re.compile(r"^(\w+)(\([^)]*\))?\s?(.*)$", re.S)


def split_define(text):
    m = DEFINE_RE.match(text)
    if not m:
        return text, None, ""
    return m.group(1), m.group(2), m.group(3)
