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
      ('return', file, line, flags) a linemarker with flag 2 (back in the
                                   includer; the #include was at line - 1)
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
                elif "2" in flags:
                    recs.append(("return", cur_file, cur_line, flags))
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


# ------------------------------------------------------ construct detection

ASM_WORDS = {"__asm__", "__asm", "asm"}
ATTR_WORDS = {"__attribute__", "__attribute"}
ASM_QUALS = {"volatile", "__volatile__", "__volatile", "goto", "inline", "__inline", "__inline__"}
FP_SUFFIX_RE = re.compile(r"(?:[fF](?:16|32|64|128)x?|[bB][fF]16|[qQwW]|[dD](?:32|64|128)|[dD][fFdDlL])$")


def norm_attr(name):
    if name.startswith("__") and name.endswith("__") and len(name) > 4:
        return name[2:-2]
    return name


def matching(toks, i):
    """toks[i] is an opener; index of its closer (or len-1)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    opener = toks[i][1]
    closer = pairs[opener]
    depth = 0
    for j in range(i, len(toks)):
        if toks[j][0] != "punct":
            continue
        v = toks[j][1]
        if v == opener:
            depth += 1
        elif v == closer:
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def split_commas(toks, a, b):
    parts, depth, s = [], 0, a
    for j in range(a, b):
        k, v = toks[j][0], toks[j][1]
        if k == "punct":
            if v in "([{":
                depth += 1
            elif v in ")]}":
                depth -= 1
            elif v == "," and depth == 0:
                parts.append((s, j))
                s = j + 1
    parts.append((s, b))
    return parts


def join(toks, a, b, limit=120):
    s = " ".join(t[1] for t in toks[a:b])
    return s if len(s) <= limit else s[:limit] + " ..."


def pragma_key(text):
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    if not words or not words[0]:
        return "(empty)"
    if words[0] in ("GCC", "clang", "STDC", "omp", "acc") and len(words) > 1:
        return words[0] + " " + re.sub(r"\(.*$", "", words[1])
    return re.sub(r"\(.*$", "", words[0])


def _brace_kind(toks, i):
    """Classify the '{' at toks[i]: record, enum, stmtexpr or other."""
    if i > 0 and toks[i - 1][1] == "(":
        return "stmtexpr"
    j = i - 1
    steps = 0
    while j >= 0 and steps < 60:
        steps += 1
        k, v = toks[j][0], toks[j][1]
        if v in ("struct", "union"):
            return "record"
        if v == "enum":
            return "enum"
        if k == "punct" and v in (";", "{", "}", "=", ",", ":"):
            return "other"
        if v == ")":
            depth = 0
            while j >= 0:
                if toks[j][1] == ")":
                    depth += 1
                elif toks[j][1] == "(":
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            if j > 1 and toks[j - 1][1] == "(" and toks[j - 2][1] in ATTR_WORDS:
                j -= 3
                continue
            return "other"
        j -= 1
    return "other"


def detect(toks):
    """Find extension constructs in a token list.

    toks: list of tuples whose first two members are (kind, value).
    Returns (index, name, key, form) tuples: name is the inventory name, key
    is the source token used to tell direct from via-macro occurrences, form
    is a short text of the use (arguments etc.).
    """
    out = []
    n = len(toks)
    frames = []
    i = 0
    while i < n:
        k, v = toks[i][0], toks[i][1]
        nxt = toks[i + 1][1] if i + 1 < n else ""
        if k == "num":
            low = v.lower()
            hexa = low.startswith("0x")
            if low.startswith("0b"):
                out.append((i, "syntax:binary integer constant", (v,), v))
            if "'" in v:
                out.append((i, "syntax:digit separator", (v,), v))
            m = FP_SUFFIX_RE.search(v)
            if m and not hexa and re.search(r"[.eE]|^\d+[fFdDbB]", v):
                out.append((i, "syntax:floating suffix " + m.group(0).lower(), (v,), v))
            if not hexa and re.match(r"^[\d.]", v) and re.search(r"(?:[fFlL]?[iIjJ]|[iIjJ][fFlL]?)$", v):
                out.append((i, "syntax:imaginary constant", (v,), v))
            if re.search(r"(?:ll|LL)[uU]?$|[uU](?:ll|LL)$", v):
                out.append((i, "syntax:long long constant", (v,), v))
            i += 1
            continue
        if k == "punct":
            if v == "{":
                kind = _brace_kind(toks, i)
                if kind == "stmtexpr":
                    out.append((i - 1, "syntax:statement expression", ("(", "{"), "({"))
                if kind == "record" and nxt == "}":
                    out.append((i, "syntax:empty struct or union", ("{", "}"), "{ }"))
                frames.append(kind)
            elif v == "}":
                kind = frames.pop() if frames else "other"
                if kind == "enum" and i > 0 and toks[i - 1][1] == ",":
                    out.append((i - 1, "syntax:enum trailing comma", (",", "}"), ", }"))
                if kind == "record" and frames and frames[-1] == "record":
                    j = i + 1
                    while j + 1 < n and toks[j][1] in ATTR_WORDS and toks[j + 1][1] == "(":
                        j = matching(toks, j + 1) + 1
                    if j < n and toks[j][1] == ";":
                        out.append((i, "syntax:anonymous struct or union member", ("}",), "} ;"))
            elif v == "[" and nxt == "[":
                j = matching(toks, i)
                out.append((i, "syntax:[[]] attribute", ("[", "["), join(toks, i, j + 1)))
                for a, b in split_commas(toks, i + 2, j - 1):
                    if a < b and toks[a][0] == "id":
                        nm = toks[a][1]
                        if b - a >= 3 and toks[a + 1][1] == "::":
                            nm = nm + "::" + toks[a + 2][1]
                        out.append((a, "stdattr:" + nm, (toks[a][1],), join(toks, a, b)))
            elif v == "[" and frames and frames[-1] == "record":
                j = matching(toks, i)
                inner = toks[i + 1:j]
                after = toks[j + 1][1] if j + 1 < n else ""
                if after == ";" or after in ATTR_WORDS:
                    if not inner:
                        out.append((i, "syntax:flexible array member", ("[", "]"), "[ ]"))
                    elif len(inner) == 1 and inner[0][1] == "0":
                        out.append((i, "syntax:zero-length array member", ("[", "0", "]"), "[ 0 ]"))
            elif v == "?" and nxt == ":":
                out.append((i, "syntax:conditional with omitted operand", ("?", ":"), "? :"))
            i += 1
            continue
        if k != "id":
            i += 1
            continue
        if v in ATTR_WORDS and nxt == "(" and i + 2 < n and toks[i + 2][1] == "(":
            inner = matching(toks, i + 2)
            for a, b in split_commas(toks, i + 3, inner):
                if a >= b or toks[a][0] != "id":
                    continue
                out.append((a, "attr:" + norm_attr(toks[a][1]), (toks[a][1],), join(toks, a, b)))
            i += 1
            continue
        if v in ASM_WORDS:
            j = i + 1
            quals = []
            while j < n and toks[j][1] in ASM_QUALS:
                quals.append(toks[j][1])
                j += 1
            if j < n and toks[j][1] == "(":
                kc = matching(toks, j)
                inner = toks[j + 1:kc]
                depth, colon = 0, False
                for t in inner:
                    if t[0] == "punct" and t[1] in "([{":
                        depth += 1
                    elif t[0] == "punct" and t[1] in ")]}":
                        depth -= 1
                    elif t[0] == "punct" and t[1] in (":", "::") and depth == 0:
                        colon = True
                pj = i - 1
                while pj >= 0 and toks[pj][1] == "__extension__":
                    pj -= 1
                prev = toks[pj] if pj >= 0 else ("punct", ";")
                is_label = (not quals and not colon and (prev[1] in (")", "]") or prev[0] == "id")
                            and prev[1] not in ("return", "else", "do"))
                if is_label:
                    if inner and all(t[0] == "str" for t in inner):
                        label = "".join(t[1][1:-1] for t in inner)
                    else:
                        label = "<" + join(toks, j + 1, kc) + ">"
                    out.append((i, "asm:label", (v,), label))
                else:
                    out.append((i, "asm:statement (%s)" % ("extended" if colon else "basic"), (v,),
                                (" ".join(quals) + " " + join(toks, j + 1, kc)).strip()))
            i += 1
            continue
        if v == "_Pragma" and nxt == "(":
            j = matching(toks, i + 1)
            arg = " ".join(t[1] for t in toks[i + 2:j])
            if arg.startswith('"') and arg.endswith('"'):
                key = pragma_key(arg[1:-1].replace('\\"', '"'))
            else:
                key = "(text from a macro argument)"
            out.append((i, "pragma:" + key, ("_Pragma",), "_Pragma(" + arg + ")"))
            i += 1
            continue
        if v == "long" and nxt == "long":
            out.append((i, "syntax:long long", ("long", "long"), "long long"))
        elif v == "long" and nxt == "double":
            out.append((i, "syntax:long double", ("long", "double"), "long double"))
        elif v == "goto" and nxt == "*":
            out.append((i, "syntax:computed goto", ("goto", "*"), "goto *"))
        elif v == "enum" and i + 2 < n and toks[i + 1][0] == "id" and toks[i + 2][1] == ":":
            out.append((i, "syntax:enum with fixed underlying type", ("enum",), join(toks, i, i + 5)))
        i += 1
    return out


def define_syntax(params, body_toks):
    """Preprocessor-level constructs of a #define line itself."""
    out = []
    if params:
        p = params[1:-1].strip()
        if re.search(r"\w\s*\.\.\.$", p):
            out.append("syntax:named variadic macro parameter")
        elif p.endswith("..."):
            out.append("syntax:variadic macro (__VA_ARGS__)")
    for i, t in enumerate(body_toks):
        if t[1] == "__VA_OPT__":
            out.append("syntax:__VA_OPT__")
        if (t[1] == "##" and i + 1 < len(body_toks) and body_toks[i + 1][1] == "__VA_ARGS__"
                and i > 0 and body_toks[i - 1][1] == ","):
            out.append("syntax:GNU comma paste (, ## __VA_ARGS__)")
    return out
