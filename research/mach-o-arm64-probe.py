#!/usr/bin/env python3
"""Throwaway: hand-write minimal arm64 MH_OBJECT files to probe what ld64 requires.

usage: mkobj.py OUT [flags...]
flags: nodysym nobuild nosubsec badorder internal addend ret42 unsorted
"""
import struct, sys

out = sys.argv[1]
opts = set(sys.argv[2:])

MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
MH_OBJECT = 1
MH_SUBSECTIONS_VIA_SYMBOLS = 0x2000
LC_SEGMENT_64, LC_SYMTAB, LC_DYSYMTAB, LC_BUILD_VERSION = 0x19, 0x2, 0xB, 0x32
S_ATTR_PURE_INSTRUCTIONS, S_ATTR_SOME_INSTRUCTIONS = 0x80000000, 0x400
S_CSTRING_LITERALS = 0x2
N_EXT, N_SECT, N_UNDF = 0x1, 0xE, 0x0
(UNSIGNED, SUBTRACTOR, BRANCH26, PAGE21, PAGEOFF12, GOT_PAGE21, GOT_PAGEOFF12,
 PTR_TO_GOT, TLVP_PAGE21, TLVP_PAGEOFF12, ADDEND) = range(11)

def w(*insns):
    return b"".join(struct.pack("<I", i) for i in insns)

def reloc(addr, symnum, pcrel, length, extern, rtype):
    return struct.pack("<iI", addr, (symnum & 0xFFFFFF) | (pcrel << 24) | (length << 25) | (extern << 27) | (rtype << 28))

pre = b"XX" if "addend" in opts else b""
cstring = pre + b"hello from forge probe\0"

if "ret42" in opts:
    text = w(0x52800540, 0xD65F03C0)  # mov w0,#42 ; ret
    syms = [("_main", N_SECT | N_EXT, 1, 0)]
    relocs_spec = []
    sections = [("__text", "__TEXT", text, 2, S_ATTR_PURE_INSTRUCTIONS | S_ATTR_SOME_INSTRUCTIONS)]
else:
    text = w(
        0xA9BF7BFD,  # 0x00 stp x29,x30,[sp,#-16]!
        0x910003FD,  # 0x04 mov x29,sp
        0x90000000,  # 0x08 adrp x0, str@PAGE
        0x91000000,  # 0x0c add x0,x0, str@PAGEOFF
        0x94000000,  # 0x10 bl _puts
        0x90000008,  # 0x14 adrp x8, _ext_var@GOTPAGE
        0xF9400108,  # 0x18 ldr x8,[x8, _ext_var@GOTPAGEOFF]
        0xB9400100,  # 0x1c ldr w0,[x8]
        0xA8C17BFD,  # 0x20 ldp x29,x30,[sp],#16
        0xD65F03C0,  # 0x24 ret
    )
    sections = [
        ("__text", "__TEXT", text, 2, S_ATTR_PURE_INSTRUCTIONS | S_ATTR_SOME_INSTRUCTIONS),
        ("__cstring", "__TEXT", cstring, 0, S_CSTRING_LITERALS),
    ]
    # symbols: (name, type, sect, value-within-section)
    syms = [("l_.str", N_SECT, 2, 0), ("_main", N_SECT | N_EXT, 1, 0),
            ("_ext_var", N_UNDF | N_EXT, 0, 0), ("_puts", N_UNDF | N_EXT, 0, 0)]
    if "badorder" in opts:  # externals before locals
        syms = [syms[1], syms[0], syms[2], syms[3]]

# lay out section addresses (object address space starts at 0)
addr = 0
sect_addr = []
for _, _, data, align, _ in sections:
    a = 1 << align
    addr = (addr + a - 1) & ~(a - 1)
    sect_addr.append(addr)
    addr += len(data)
vmsize = addr

symidx = {s[0]: i for i, s in enumerate(syms)}
relocs = b""
if "ret42" not in opts:
    rs = []
    if "internal" in opts:
        # r_extern=0: r_symbolnum is a 1-based section ordinal
        rs += [reloc(0x08, 2, 1, 2, 0, PAGE21), reloc(0x0C, 2, 0, 2, 0, PAGEOFF12)]
    elif "addend" in opts:
        rs += [reloc(0x08, 2, 0, 2, 0, ADDEND), reloc(0x08, symidx["l_.str"], 1, 2, 1, PAGE21),
               reloc(0x0C, 2, 0, 2, 0, ADDEND), reloc(0x0C, symidx["l_.str"], 0, 2, 1, PAGEOFF12)]
    else:
        rs += [reloc(0x08, symidx["l_.str"], 1, 2, 1, PAGE21), reloc(0x0C, symidx["l_.str"], 0, 2, 1, PAGEOFF12)]
    rs += [reloc(0x10, symidx["_puts"], 1, 2, 1, BRANCH26),
           reloc(0x14, symidx["_ext_var"], 1, 2, 1, GOT_PAGE21),
           reloc(0x18, symidx["_ext_var"], 0, 2, 1, GOT_PAGEOFF12)]
    relocs = b"".join(rs)
    nrel = len(rs)

# load commands
nsect = len(sections)
seg_size = 72 + 80 * nsect
cmds = [seg_size]
if "nobuild" not in opts: cmds.append(24)
cmds.append(24)
if "nodysym" not in opts: cmds.append(80)
sizeofcmds = sum(cmds)
off = 32 + sizeofcmds

# file layout: section data, relocations, symtab, strtab
sect_off = []
body = b""
for i, (_, _, data, align, _) in enumerate(sections):
    # in MH_OBJECT, file offset tracks address: fileoff + addr
    sect_off.append(off + sect_addr[i])
blob = bytearray(vmsize)
for i, (_, _, data, _, _) in enumerate(sections):
    blob[sect_addr[i]:sect_addr[i] + len(data)] = data
body = bytes(blob)
pos = off + len(body)
pad = (-pos) % 8
body += b"\0" * pad; pos += pad
reloff = pos if relocs else 0
body += relocs; pos += len(relocs)
pad = (-pos) % 8
body += b"\0" * pad; pos += pad

strtab = b"\0"
stroffs = {}
for s in syms:
    stroffs[s[0]] = len(strtab)
    strtab += s[0].encode() + b"\0"
strtab += b"\0" * ((-len(strtab)) % 8)
symoff = pos
symtab = b""
for name, ntype, sect, val in syms:
    v = sect_addr[sect - 1] + val if sect else 0
    symtab += struct.pack("<IBBHQ", stroffs[name], ntype, sect, 0, v)
body += symtab; pos += len(symtab)
stroff = pos
body += strtab

flags = 0 if "nosubsec" in opts else MH_SUBSECTIONS_VIA_SYMBOLS
hdr = struct.pack("<IiiIIIII", MH_MAGIC_64, CPU_TYPE_ARM64, 0, MH_OBJECT, len(cmds), sizeofcmds, flags, 0)
lc = struct.pack("<II16sQQQQiiII", LC_SEGMENT_64, seg_size, b"", 0, vmsize, off, vmsize, 7, 7, nsect, 0)
for i, (sn, gn, data, align, fl) in enumerate(sections):
    has_rel = (i == 0 and relocs)
    lc += struct.pack("<16s16sQQIIIIIIII", sn.encode(), gn.encode(), sect_addr[i], len(data), sect_off[i], align,
                      reloff if has_rel else 0, nrel if has_rel else 0, fl, 0, 0, 0)
if "nobuild" not in opts:
    lc += struct.pack("<IIIIII", LC_BUILD_VERSION, 24, 1, 0x000E0000, 0x000F0000, 0)  # macOS 14.0, sdk 15.0
nlocal = sum(1 for s in syms if not (s[1] & N_EXT))
nextdef = sum(1 for s in syms if (s[1] & N_EXT) and (s[1] & 0xE) == N_SECT)
nundef = len(syms) - nlocal - nextdef
lc += struct.pack("<IIII", LC_SYMTAB, 24, symoff, len(syms)) + struct.pack("<II", stroff, len(strtab))
if "nodysym" not in opts:
    lc += struct.pack("<II18I", LC_DYSYMTAB, 80, 0, nlocal, nlocal, nextdef, nlocal + nextdef, nundef, *([0] * 12))
assert len(lc) == sizeofcmds, (len(lc), sizeofcmds)
open(out, "wb").write(hdr + lc + body)
