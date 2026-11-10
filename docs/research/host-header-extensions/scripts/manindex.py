#!/usr/bin/env python3
"""Index the GCC 15.2 HTML manual: builtin/attribute/trait names -> page,
anchor and first sentence of the description.

usage: manindex.py GCC_HTML_DIR CPP_HTML_DIR OUT_JSON
"""
import html
import json
import os
import re
import sys

TAG = re.compile(r"<[^>]+>")


def text_of(fragment):
    t = TAG.sub("", fragment)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def first_sentence(t, limit=170):
    m = re.search(r"^(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + " ..."
    return s


def main():
    gdir, cdir, out = sys.argv[1:4]
    index = {"builtin": {}, "attribute": {}, "library_functions": {}, "pages": {}}
    for d, manual in ((gdir, "gcc"), (cdir, "cpp")):
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".html"):
                continue
            t = open(os.path.join(d, fn), encoding="utf-8", errors="replace").read()
            m = re.search(r"<title>(.*?)</title>", t, re.S)
            index["pages"][manual + "/" + fn] = text_of(m.group(1)) if m else fn
            # deftypefn-style entries: <dt ... id="anchor"> ... <strong class="def-name">NAME</strong>
            for dm in re.finditer(r'<dt class="deftypefnx?" id="([^"]+)">(.*?)</dt>', t, re.S):
                anchor, dt = dm.group(1), dm.group(2)
                nm = re.search(r'<strong class="def-name">([^<]+)</strong>', dt)
                if not nm:
                    continue
                name = html.unescape(nm.group(1)).strip()
                # description: following <dd>
                rest = t[dm.end():]
                dd = re.search(r"<dd>(.*?)</dd>", rest, re.S)
                # if an x-entry (deftypefnx) the dd belongs to the group; still fine
                desc = first_sentence(text_of(dd.group(1))) if dd else ""
                index["builtin"].setdefault(name, []).append(
                    {"page": manual + "/" + fn, "anchor": anchor, "desc": desc})
            # attribute-style entries (one <dt> may carry several anchors)
            for am in re.finditer(r"<dt>(.*?)</dt>", t, re.S):
                dt = am.group(1)
                for an in re.finditer(r'id="(index-([A-Za-z0-9_]+?)-(function|variable|type|enumerator|label|statement)-attribute[^"]*)"', dt):
                    anchor, raw, kind = an.group(1), an.group(2), an.group(3)
                    name = re.sub(r"_00([0-9a-f]{2})", lambda m: chr(int(m.group(1), 16)), raw)
                    rest = t[am.end():]
                    dd = re.search(r"<dd>(.*?)</dd>", rest, re.S)
                    desc = first_sentence(text_of(dd.group(1))) if dd else ""
                    lst = index["attribute"].setdefault(name, [])
                    if not any(e["page"] == manual + "/" + fn and e["kind"] == kind for e in lst):
                        lst.append({"page": manual + "/" + fn, "anchor": anchor, "kind": kind, "desc": desc})
            # C++ attributes page uses a different layout
            if fn == "C_002b_002b-Attributes.html":
                for am in re.finditer(r'<dt><a id="(index-([^"]+?))"></a><span><code class="code">(.*?)</code>', t, re.S):
                    anchor, name = am.group(1), text_of(am.group(3))
                    name = re.split(r"[\s(]", name)[0]
                    rest = t[am.end():]
                    dd = re.search(r"<dd>(.*?)</dd>", rest, re.S)
                    desc = first_sentence(text_of(dd.group(1))) if dd else ""
                    index["attribute"].setdefault(name, []).append(
                        {"page": manual + "/" + fn, "anchor": anchor, "kind": "c++", "desc": desc})
    # library builtins: every <code> token in Library-Builtins.html
    lb = open(os.path.join(gdir, "Library-Builtins.html"), encoding="utf-8").read()
    for cm in re.finditer(r'<code class="code">([A-Za-z_][A-Za-z0-9_]*)</code>', lb):
        index["library_functions"][cm.group(1)] = "gcc/Library-Builtins.html"
    with open(out, "w") as f:
        json.dump(index, f, indent=0, sort_keys=True)
    print(len(index["builtin"]), "builtin defs;", len(index["attribute"]), "attributes;",
          len(index["library_functions"]), "library function names", file=sys.stderr)


if __name__ == "__main__":
    main()
