#!/usr/bin/env python3
"""Host header extension inventory tooling (Forge research, issue #9).

All paths inside the data are *logical* install paths (/usr/include/...).
The manifest (built by manifest.py) maps them to extracted files.

Subcommands:
  closure MANIFEST OUT_JSON            static include closure of the root set
  instrument MANIFEST OUT_DIR OUT_JSON  copy every header with marker pragmas
  active OUT_JSON PREPROCESSED...       collect marker ids seen in -E output

The extension scan itself is scan.py (it imports this module).
"""
import json
import os
import re
import sys

SEARCH = [
    "/usr/include/c++/15",
    "/usr/include/aarch64-linux-gnu/c++/15",
    "/usr/include/c++/15/backward",
    "/usr/lib/gcc/aarch64-linux-gnu/15/include",
    "/usr/local/include",
    "/usr/include/aarch64-linux-gnu",
    "/usr/include",
]

CXX20_HEADERS = """algorithm any array atomic barrier bit bitset charconv chrono codecvt
compare complex concepts condition_variable coroutine deque exception execution
filesystem format forward_list fstream functional future initializer_list iomanip
ios iosfwd iostream istream iterator latch limits list locale map memory
memory_resource mutex new numbers numeric optional ostream queue random ranges
ratio regex scoped_allocator semaphore set shared_mutex source_location span
sstream stack stdexcept stop_token streambuf string string_view strstream
syncstream system_error thread tuple type_traits typeindex typeinfo
unordered_map unordered_set utility valarray variant vector version
cassert cctype cerrno cfenv cfloat cinttypes climits clocale cmath csetjmp
csignal cstdarg cstddef cstdint cstdio cstdlib cstring ctime cuchar cwchar cwctype""".split()

DEPR_C_HEADERS = """assert.h complex.h ctype.h errno.h fenv.h float.h inttypes.h iso646.h
limits.h locale.h math.h setjmp.h signal.h stdalign.h stdarg.h stdbool.h stddef.h
stdint.h stdio.h stdlib.h string.h tgmath.h time.h uchar.h wchar.h wctype.h""".split()

EXTRA_HEADERS = ["bits/stdc++.h", "cxxabi.h"]

POSIX_HEADERS = """unistd.h fcntl.h sys/stat.h sys/mman.h sys/types.h sys/wait.h signal.h
dirent.h dlfcn.h pthread.h errno.h time.h sys/time.h sys/resource.h poll.h spawn.h
execinfo.h link.h elf.h""".split()


def root_names():
    seen = []
    for n in CXX20_HEADERS + DEPR_C_HEADERS + EXTRA_HEADERS + POSIX_HEADERS:
        if n not in seen:
            seen.append(n)
    return seen


def load_manifest(path):
    with open(path) as f:
        return json.load(f)


def read_text(manifest, logical):
    with open(manifest[logical]["phys"], "rb") as f:
        return f.read().decode("latin-1")


# --------------------------------------------------------------------------
# Lexing: logical lines with comments removed.

class LLine:
    __slots__ = ("start", "end", "code")

    def __init__(self, start, end, code):
        self.start = start  # 1-based first physical line
        self.end = end      # 1-based last physical line
        self.code = code    # comment-free text, continuations joined


def logical_lines(text):
    out = []
    n = len(text)
    i = 0
    line = 1
    start = 1
    buf = []
    state = "code"
    prev_sig = ""  # last significant char for pp-number tracking
    in_ppnum = False

    def flush(end_line):
        out.append(LLine(start, end_line, "".join(buf)))

    while i < n:
        c = text[i]
        # line splice
        if c == "\\" and i + 1 < n and text[i + 1] == "\n":
            i += 2
            line += 1
            continue
        if c == "\\" and i + 2 < n and text[i + 1] == "\r" and text[i + 2] == "\n":
            i += 3
            line += 1
            continue
        if state == "code":
            if c == "\n":
                flush(line)
                buf = []
                line += 1
                start = line
                i += 1
                in_ppnum = False
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                state = "block"
                buf.append(" ")
                i += 2
                in_ppnum = False
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "/":
                state = "linec"
                buf.append(" ")
                i += 2
                in_ppnum = False
                continue
            if c == "R" and i + 1 < n and text[i + 1] == '"' and not (buf and (buf[-1].isalnum() or buf[-1] == "_")):
                m = re.match(r'R"([^()\\ \n]{0,16})\(', text[i:])
                if m:
                    delim = ")" + m.group(1) + '"'
                    j = text.find(delim, i + m.end())
                    if j >= 0:
                        seg = text[i:j + len(delim)]
                        buf.append(seg.replace("\n", " "))
                        line += seg.count("\n")
                        i = j + len(delim)
                        continue
            if c == '"':
                state = "str"
                buf.append(c)
                i += 1
                in_ppnum = False
                continue
            if c == "'":
                if in_ppnum:
                    buf.append(c)
                    i += 1
                    continue
                state = "chr"
                buf.append(c)
                i += 1
                continue
            if c.isdigit() and not (buf and (buf[-1].isalnum() or buf[-1] == "_")):
                in_ppnum = True
            elif in_ppnum and not (c.isalnum() or c in "._" or (c in "+-" and buf and buf[-1] in "eEpP")):
                in_ppnum = False
            buf.append(c)
            i += 1
            continue
        if state == "block":
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                state = "code"
                i += 2
                continue
            if c == "\n":
                line += 1
            i += 1
            continue
        if state == "linec":
            if c == "\n":
                state = "code"
                continue  # newline handled in code state
            i += 1
            continue
        if state in ("str", "chr"):
            q = '"' if state == "str" else "'"
            if c == "\\" and i + 1 < n:
                buf.append(text[i:i + 2])
                i += 2
                continue
            if c == "\n":
                state = "code"
                continue
            buf.append(c)
            i += 1
            if c == q:
                state = "code"
            continue
    if buf or start <= line:
        flush(line)
    return out


DIRECTIVE_RE = re.compile(r"^\s*#\s*([A-Za-z_]+)\b(.*)$", re.S)


def directive(ll):
    m = DIRECTIVE_RE.match(ll.code)
    if not m:
        return None, None
    return m.group(1), m.group(2).strip()


INCLUDE_RE = re.compile(r'^\s*([<"])([^>"]+)[>"]')


# --------------------------------------------------------------------------
# Static closure

def resolve(manifest, name, kind, cur_file, cur_dir_idx, is_next):
    """Return (logical_path, dir_index) or (None, None)."""
    if kind == '"' and not is_next:
        cand = os.path.normpath(os.path.join(os.path.dirname(cur_file), name))
        if cand in manifest:
            return cand, cur_dir_idx
    start = 0
    if is_next and cur_dir_idx is not None:
        start = cur_dir_idx + 1
    for idx in range(start, len(SEARCH)):
        cand = os.path.normpath(os.path.join(SEARCH[idx], name))
        if cand in manifest:
            return cand, idx
    return None, None


def cmd_closure(args):
    manifest = load_manifest(args[0])
    out = args[1]
    roots = {}
    missing_roots = []
    for n in root_names():
        p, idx = resolve(manifest, n, "<", "", None, False)
        if p is None:
            missing_roots.append(n)
        else:
            roots[n] = p
    # BFS
    files = {}  # logical -> {"dir_idx":..., "from": [...]}
    queue = []
    for n, p in roots.items():
        _, idx = resolve(manifest, n, "<", "", None, False)
        if p not in files:
            files[p] = {"dir_idx": idx, "via": ["<root %s>" % n]}
            queue.append(p)
    unresolved = []
    computed = []
    edges = []
    while queue:
        f = queue.pop(0)
        idx = files[f]["dir_idx"]
        for ll in logical_lines(read_text(manifest, f)):
            d, rest = directive(ll)
            if d not in ("include", "include_next", "import"):
                continue
            m = INCLUDE_RE.match(rest)
            if not m:
                computed.append({"file": f, "line": ll.start, "text": rest})
                continue
            kind, name = m.group(1), m.group(2)
            p, pidx = resolve(manifest, name, kind, f, idx, d == "include_next")
            if p is None:
                unresolved.append({"file": f, "line": ll.start, "name": name, "directive": d})
                continue
            edges.append([f, ll.start, p])
            if p not in files:
                files[p] = {"dir_idx": pidx, "via": ["%s:%d" % (f, ll.start)]}
                queue.append(p)
            elif len(files[p]["via"]) < 3:
                files[p]["via"].append("%s:%d" % (f, ll.start))
    res = {
        "roots": roots,
        "missing_roots": missing_roots,
        "files": files,
        "unresolved": unresolved,
        "computed": computed,
        "edges": edges,
    }
    with open(out, "w") as fo:
        json.dump(res, fo, indent=1, sort_keys=True)
    by_pkg = {}
    for p in files:
        by_pkg[manifest[p]["pkg"]] = by_pkg.get(manifest[p]["pkg"], 0) + 1
    print("closure:", len(files), "files", by_pkg, file=sys.stderr)
    print("missing roots:", missing_roots, file=sys.stderr)
    print("unresolved includes:", len(unresolved), "computed:", len(computed), file=sys.stderr)


# --------------------------------------------------------------------------
# Conditional structure (shared by instrument and scan so block ids agree)

COND_OPEN = ("if", "ifdef", "ifndef")
COND_MID = ("elif", "else", "elifdef", "elifndef")


def blocks_of(lls):
    """Yield per logical line: (ll, directive, rest, stack) where stack is the
    list of active conditional frames *after* processing this line. A frame is
    dict(kind, text, line, block, chain) where chain lists the earlier
    conditions of the same #if group (for #elif/#else)."""
    stack = []
    counter = [0]
    result = []
    first_cond_seen = [False]
    for k, ll in enumerate(lls):
        d, rest = directive(ll)
        if d in COND_OPEN:
            counter[0] += 1
            frame = {"kind": d, "text": rest, "line": ll.start, "block": counter[0],
                     "chain": [], "guard": False}
            if not first_cond_seen[0]:
                first_cond_seen[0] = True
                # include guard: first conditional is #ifndef X / #if !defined X
                # followed by #define X
                gm = re.match(r"^(?:ifndef\s+(\w+)|if\s+!\s*defined\s*\(?\s*(\w+)\s*\)?\s*)$", d + " " + rest)
                if gm:
                    gname = gm.group(1) or gm.group(2)
                    for ll2 in lls[k + 1:k + 4]:
                        d2, r2 = directive(ll2)
                        if d2 == "define" and r2.split()[:1] == [gname]:
                            frame["guard"] = True
                            break
                        if d2 is not None:
                            break
            stack.append(frame)
        elif d in COND_MID:
            if stack:
                prev = stack.pop()
                counter[0] += 1
                chain = prev["chain"] + [(prev["kind"], prev["text"], prev["line"])]
                stack.append({"kind": d, "text": rest, "line": ll.start, "block": counter[0],
                              "chain": chain, "guard": False})
        elif d == "endif":
            if stack:
                stack.pop()
        result.append((ll, d, rest, [dict(fr) for fr in stack] if d in COND_OPEN + COND_MID else None))
    return result


def cmd_instrument(args):
    manifest = load_manifest(args[0])
    outdir = args[1]
    outmap = args[2]
    mapping = {}
    for fid, logical in enumerate(sorted(manifest)):
        text = read_text(manifest, logical)
        phys_lines = text.split("\n")
        lls = logical_lines(text)
        inserts = {}  # after physical line number -> marker id
        stack = []
        counter = 0
        for ll in lls:
            d, rest = directive(ll)
            if d in COND_OPEN:
                counter += 1
                inserts[ll.end] = "%d.%d" % (fid, counter)
                mapping["%d.%d" % (fid, counter)] = [logical, ll.start]
            elif d in COND_MID:
                counter += 1
                inserts[ll.end] = "%d.%d" % (fid, counter)
                mapping["%d.%d" % (fid, counter)] = [logical, ll.start]
        mapping["%d.0" % fid] = [logical, 0]
        out_lines = ["#pragma FORGEMARK %d.0" % fid]
        for no, pl in enumerate(phys_lines, start=1):
            out_lines.append(pl)
            if no in inserts:
                out_lines.append("#pragma FORGEMARK %s" % inserts[no])
        dest = os.path.join(outdir, logical.lstrip("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="latin-1") as fo:
            fo.write("\n".join(out_lines))
    with open(outmap, "w") as fo:
        json.dump(mapping, fo)
    print("instrumented", len(manifest), "files,", len(mapping), "markers", file=sys.stderr)


MARK_RE = re.compile(r"^\s*#pragma FORGEMARK (\d+\.\d+)\s*$")


def cmd_active(args):
    out = args[0]
    seen = set()
    for p in args[1:]:
        with open(p, encoding="latin-1") as f:
            for line in f:
                m = MARK_RE.match(line)
                if m:
                    seen.add(m.group(1))
    with open(out, "w") as fo:
        json.dump(sorted(seen), fo)
    print(len(seen), "active markers", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"closure": cmd_closure, "instrument": cmd_instrument, "active": cmd_active}[cmd](sys.argv[2:])
