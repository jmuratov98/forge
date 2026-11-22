# Mach-O relocatable objects and the Apple arm64 ABI

Research for [jmuratov98/forge#2](https://github.com/jmuratov98/forge/issues/2). It feeds the "How the slice produces the .o" decision ([#14](https://github.com/jmuratov98/forge/issues/14)).

**Question.** What must a minimal `aarch64-apple-darwin` `MH_OBJECT` contain for Apple's `ld` to link it and for the result to run? Which `ARM64_RELOC_*` types does a C subset need? How does Apple's arm64 ABI differ from AAPCS64? How does Apple `as` syntax differ from GNU syntax?

## TL;DR

- **Minimum that links and runs:** a `mach_header_64` (`MH_MAGIC_64`, `CPU_TYPE_ARM64`, `CPU_SUBTYPE_ARM64_ALL`, `MH_OBJECT`), followed by **one unnamed `LC_SEGMENT_64`** that holds every section, plus `LC_SYMTAB`. Probes against the shipping linker (ld-1167.5, Xcode 16 CLT) and against `-ld_classic` (ld64) showed:
  - Without `LC_DYSYMTAB`, the object still links and runs.
  - Without `MH_SUBSECTIONS_VIA_SYMBOLS`, it still links and runs, but nothing in it can be dead-stripped.
  - With the symbol table out of order (externals before locals), it still links and runs.
  - Without `LC_BUILD_VERSION`, it links and runs, but ld warns `no platform load command found ... assuming: macOS`.
- **What Forge should emit anyway** (to match clang byte-for-byte in spirit and keep ld quiet): `LC_SEGMENT_64`, `LC_BUILD_VERSION` (platform 1 = macOS, `ntools` 0), `LC_SYMTAB`, and `LC_DYSYMTAB`. Set `MH_SUBSECTIONS_VIA_SYMBOLS`. Order the symbol table locals, then defined externals sorted by name, then undefined externals sorted by name.
- **Relocations a C subset needs:** `BRANCH26` (every `bl`/`b` to a symbol), `PAGE21` + `PAGEOFF12` (address of, or load/store to, a symbol defined in this object), `GOT_LOAD_PAGE21` + `GOT_LOAD_PAGEOFF12` (data symbols that may live elsewhere), `ADDEND` (a `sym+N` with `BRANCH26`/`PAGE21`/`PAGEOFF12`), and `UNSIGNED` (with `r_length=3`, for `.quad sym` pointers in initialized data).
- **Rules ld enforces on those relocations:**
  - `r_extern` must be 1. A section-relative (`r_extern=0`) `PAGE21` is rejected: `relocation ... is not supported`.
  - `r_length` must be 2.
  - `r_pcrel` must be 1 for `BRANCH26`/`PAGE21`/`GOT_LOAD_PAGE21` and 0 for the `PAGEOFF12` forms.
  - Addends go in a preceding `ARM64_RELOC_ADDEND` (a signed 24-bit value in `r_symbolnum`). An addend embedded in the instruction draws a warning.
  - GOT and TLVP loads cannot take an addend at all.
- **Conditional branches (`b.cond`, `cbz`, `tbz`) have no Mach-O relocation.** Forge must resolve them itself, and each target must be in the same atom, meaning the same function. Basic-block labels must be **`L`-prefixed** temporaries. `.L` is *not* special on Darwin: it becomes a real symbol and breaks the branch.
- **Symbols:** C identifiers get a leading `_` (`add` becomes `_add`). Use `L…` for assembler-local labels, which never reach the symbol table. Use `l…` for linker-private ones, which do reach the table and can be relocation targets but are not atom boundaries and are not exported. The string table starts with `\0`, and index 0 means "no name".
- **ABI deltas that matter for the slice:**
  - `x18` is reserved; never touch it.
  - `x29` must always point to a valid frame record; leaf functions may skip it.
  - **Variadic arguments go on the stack**, each in its own 8-byte slot, never in registers, and `va_list` is a `char*`.
  - The **caller** sign- or zero-extends arguments narrower than 32 bits (`char`/`short`/`bool`).
  - Stack arguments are packed at their natural size and alignment instead of 8-byte slots.
  - `char` is signed, `long double` is `double`, and there is a 128-byte red zone.
- **Assembler syntax:**
  - `sym@PAGE` / `sym@PAGEOFF` / `sym@GOTPAGE` / `sym@GOTPAGEOFF` replace ELF's bare `sym` / `:lo12:sym` / `:got:sym` / `:got_lo12:sym`, and the ELF forms are rejected outright.
  - `.section __SEG,__sect[,type[,attrs]]` replaces ELF section flags.
  - There is no `.type`, `.size`, or `.hidden`; use `.private_extern`.
  - `;` or `//` starts a comment, and `%%` separates statements.

## 1. File layout of an `MH_OBJECT`

### Header

`struct mach_header_64` is 32 bytes: `magic`, `cputype`, `cpusubtype`, `filetype`, `ncmds`, `sizeofcmds`, `flags`, `reserved` ([loader.h] L80–89).

| field | value for Forge |
|---|---|
| `magic` | `MH_MAGIC_64` = `0xfeedfacf` ([loader.h] L92) |
| `cputype` | `CPU_TYPE_ARM64` = `CPU_TYPE_ARM \| CPU_ARCH_ABI64` = `0x0100000c` ([machine.h] L87, L111) |
| `cpusubtype` | `CPU_SUBTYPE_ARM64_ALL` = 0 ([machine.h] L339). Plain arm64, not arm64e. |
| `filetype` | `MH_OBJECT` = 1 ([loader.h] L118) |
| `flags` | `MH_SUBSECTIONS_VIA_SYMBOLS` = `0x2000` ([loader.h] L177). Clang sets only this flag on objects (observed below). |

### The one segment

> "The file type MH_OBJECT is a compact format intended as output of the assembler … All sections are in one unnamed segment with no segment padding." ([loader.h] L102–104)

> "The MH_OBJECT format has all of its sections in one segment for compactness. There is no padding to a specified segment boundary and the mach_header and load commands are not part of the segment." ([loader.h] L444–446)

So an object has exactly one `LC_SEGMENT_64` (`cmd` `0x19`, [loader.h] L313) with an empty `segname`. Its `cmdsize` is 72 + 80 × `nsects` (the `section_64` structs follow it directly, [loader.h] L399–411, L473–486). Clang sets `vmaddr` 0, `maxprot`/`initprot` `rwx`, and `fileoff` to the first byte after the load commands.

Each `section_64` names its *real* destination: `segname` is `__TEXT` or `__DATA` even though the containing segment is unnamed. Its `addr` lives in the object's private address space: sections are laid out from 0, each aligned to its `align`, which is a power of 2. `offset` is the file offset of its bytes; zerofill sections get 0. `reloff` and `nreloc` point at that section's relocation entries. In objects, relocations "continue to hang off the section structures" ([loader.h] L959–960), not off `LC_DYSYMTAB`. The linker concatenates same-named sections and keeps each input's alignment ([loader.h] L447–452).

### Sections a C subset needs

These are the names and flags clang 17 emits (observed with `clang -S` and `otool -lv`):

| C construct | section | type / attributes |
|---|---|---|
| functions | `__TEXT,__text` | `S_REGULAR` + `S_ATTR_PURE_INSTRUCTIONS \| S_ATTR_SOME_INSTRUCTIONS` (`0x80000400`), align 2^2 |
| string literals | `__TEXT,__cstring` | `S_CSTRING_LITERALS` (`0x2`), align 2^0. ld splits this section at NULs and deduplicates the strings; labels in it are ignored for atomization (`CStringSection::ignoreLabel` returns true for `L`/`l` names, [ld64 parser] L6226–6228). |
| `const` globals | `__TEXT,__const` | `S_REGULAR` |
| initialized globals | `__DATA,__data` | `S_REGULAR` |
| zero-initialized `static` | `__DATA,__bss` | `S_ZEROFILL` (`0x1`). Takes no file bytes; zero-fill sections sit last in the segment ([loader.h] L437–438). |
| tentative definitions (`int g;`) | *common symbol* (`N_UNDF\|N_EXT`, `n_value` = size, alignment in `n_desc` bits 8–11, [nlist.h] "Common symbols") or, with `-fno-common`, `__DATA,__common` zerofill | Apple's clang driver passes `-fcommon` by default (`clang -###`). Forge can choose either. |
| unwind info | `__LD,__compact_unwind` | `S_ATTR_DEBUG`. **Optional.** The probes below link and run without it. Without it the image has no unwind entries for Forge's functions, which matters only for C++ exceptions and unwinders that pass through those frames; crash backtraces still work through the frame-pointer chain. |

### Load commands

Clang emits these, in this order ([MachObjectWriter.cpp] and `otool -lv`):

1. `LC_SEGMENT_64`
2. `LC_BUILD_VERSION` (`0x32`): `platform`, `minos`, `sdk`, `ntools`. Versions are packed as nibbles `xxxx.yy.zz` ([loader.h] L1308–1320); macOS 14.0 is `0x000E0000`. `PLATFORM_MACOS` = 1 (L1325). Clang emits `ntools` 0 in objects. The *linked* binary's `minos` comes from ld's `-platform_version`, not from the object (observed).
3. `LC_LINKER_OPTIMIZATION_HINT` (`0x2E`). Optional; this is clang's `.loh` ADRP-relaxation hint table.
4. `LC_SYMTAB` (`0x2`): `symoff`, `nsyms`, `stroff`, `strsize` ([loader.h] L913–920).
5. `LC_DYSYMTAB` (`0xb`). For objects, only `ilocalsym`/`nlocalsym`, `iextdefsym`/`nextdefsym`, and `iundefsym`/`nundefsym` are non-zero. The table of contents, module table, and reference table "are only present if the file is a dynamically linked shared library" ([loader.h] L944–952).

LLVM writes `LC_SYMTAB` and `LC_DYSYMTAB` as a pair whenever there are symbols ([MachObjectWriter.cpp] L885–890). The classic ld64 uses `LC_DYSYMTAB` only to find the undefined range. If the command is missing, ld64 treats the whole table as the candidate undefined range ([ld64 parser] L2228–2246), which is why omitting it still worked.

### File order

LLVM writes: header, load commands, section data padded to 8, the relocations for each section (*in reverse order*, "to match 'as'"; ld does not care), data-in-code, the LOH blob, the symbol table, and the string table ([MachObjectWriter.cpp] L1080–1130).

## 2. Symbols and the string table

`struct nlist_64` is 16 bytes: `n_strx` (u32 index into the string table), `n_type` (u8), `n_sect` (u8, a 1-based section ordinal or `NO_SECT` = 0), `n_desc` (u16), and `n_value` (u64) ([nlist.h]).

- **`n_type` bits:** `N_STAB` is `0xe0` (debug entries only), `N_PEXT` `0x10` (private extern), `N_TYPE` mask `0x0e`, and `N_EXT` `0x01`. The `N_TYPE` values are `N_UNDF` 0, `N_ABS` 2, `N_SECT` `0xe`, and `N_INDR` `0xa`.
  - A defined global is `0x0f` (`N_SECT|N_EXT`).
  - A `static` is `0x0e`.
  - An undefined reference is `0x01` with `n_sect` 0 and `n_value` 0.
  - `.private_extern` sets `N_PEXT|N_EXT`: the symbol is visible across objects at link time but is not exported from the image.
- **`n_value` for a defined symbol** is its address in the object's address space: section `addr` + offset. It is *not* section-relative. The linker rebases it by `n_sect` ([nlist.h], "The n_value field for all symbol table entries … gets updated by the link editor").
- **`n_desc`:** a few bits matter later. `N_NO_DEAD_STRIP` is `0x20`, `N_WEAK_REF` `0x40`, `N_WEAK_DEF` `0x80`, and `N_ALT_ENTRY` `0x200`. Common-symbol alignment is in bits 8–11.
- **Leading underscore:** the C name `add` is the symbol `_add`, and `printf` is `_printf` (observed in `t.s` and `nm`). The Darwin C ABI applies this prefix to every external C identifier.
- **Name prefixes** (from ld64's parser, which tests `symbolName[0]`):
  - `L…` is assembler-local. It is never written to the object (the `InternalSymbolPrefix = "L"` setting in [AArch64MCAsmInfo.cpp] L141). ld also ignores `L` labels if they appear (`ignoreLabel`, [ld64 parser] L440).
  - `l…` is linker-private. It is written to the object so that relocations can target it, but ld resolves references to it directly and never exports it ([ld64 parser] L3632, L7914–7920). Clang names string literals `l_.str`, `l_.str.1`, and so on, and adds `ltmpN` section-start symbols, which ld treats as aliases ([ld64 parser] L1691–1697, L2620).
  - `.L…` is **not** special on Darwin. `.Lx` came out as a real local symbol `t .Lx` (observed).
- **Order:** locals, then defined externals sorted by name, then undefined externals sorted by name. LLVM's comment says this matches `as` "even though it doesn't matter for correctness" ([MachObjectWriter.cpp] L613–672), and the `badorder` probe confirms ld accepts other orders. Emit the sorted order anyway, because `LC_DYSYMTAB` describes contiguous ranges.
- **String table:** byte 0 is `\0`, so `n_strx` 0 means the empty name. It is followed by NUL-terminated names, and the total is padded to 8 bytes (observed: `strsize` 80; LLVM uses a `StringTableBuilder` that may tail-merge names).

### `MH_SUBSECTIONS_VIA_SYMBOLS`

Defined as "safe to divide up the sections into sub-sections via symbols for dead code stripping" ([loader.h] L177). With the flag set, ld splits every section into **atoms** at each non-`L`, non-`l` symbol. Atoms are the unit of dead-stripping and reordering. Without it, "an object file without MH_SUBSECTIONS_VIA_SYMBOLS [is modeled] as one in which nothing can be dead stripped", and ld chains atoms with follow-on fixups so they stay together ([ld64 parser] L5892–5894, L9010).

Consequences for Forge:
- Every function symbol starts an atom. Code must not fall through from one function into the next, and **any reference that crosses a function boundary must be a relocation**, never a pre-resolved offset. LLVM emits `BRANCH26` even for `bl` to a `static` function in the same file (observed: `_sub` in `call.o`).
- PC-relative fixups *inside* a function, such as branches to `L` labels, may be resolved by Forge with no relocation.

## 3. Relocations

`struct relocation_info` is 8 bytes. `r_address` (i32) is the offset of the patched instruction in its section. The second word packs these bitfields ([reloc.h] L64–73):

`r_symbolnum:24 | r_pcrel:1 | r_length:2 | r_extern:1 | r_type:4`

Encoded little-endian: `word1 = symnum | pcrel<<24 | length<<25 | extern<<27 | type<<28`.

> "Relocations for arm64 are a bit different than for other architectures in Mach-O: Scattered relocations are not used. Almost all relocations produced by the compiler are external relocations." ([arm64/reloc.h])

| # | type | instruction | pcrel | length | needs | addend |
|---|---|---|---|---|---|---|
| 0 | `ARM64_RELOC_UNSIGNED` | `.quad sym` (data) | 0 | 3 | — | stored in the 8 data bytes |
| 1 | `ARM64_RELOC_SUBTRACTOR` | `.quad a - b` | 0 | 2/3 | followed by `UNSIGNED` | in data |
| 2 | `ARM64_RELOC_BRANCH26` | `b`/`bl sym` | 1 | 2 | extern | via `ADDEND` only |
| 3 | `ARM64_RELOC_PAGE21` | `adrp xN, sym@PAGE` | 1 | 2 | extern | via `ADDEND` only |
| 4 | `ARM64_RELOC_PAGEOFF12` | `add`/`ldr`/`str …, sym@PAGEOFF` | 0 | 2 | extern | via `ADDEND` only |
| 5 | `ARM64_RELOC_GOT_LOAD_PAGE21` | `adrp xN, sym@GOTPAGE` | 1 | 2 | extern | **not allowed** |
| 6 | `ARM64_RELOC_GOT_LOAD_PAGEOFF12` | `ldr xN, [xN, sym@GOTPAGEOFF]` | 0 | 2 | extern | **not allowed** |
| 7 | `ARM64_RELOC_POINTER_TO_GOT` | `.long sym@GOT - .` | 1 | 2 | — | not allowed |
| 8/9 | `ARM64_RELOC_TLVP_LOAD_PAGE21/PAGEOFF12` | thread-locals | — | — | — | out of slice scope |
| 10 | `ARM64_RELOC_ADDEND` | prefix record | 0 | 2 | `r_extern=0`, `r_symbolnum` = signed 24-bit addend, same `r_address` as the next record | — |
| 11 | `ARM64_RELOC_AUTHENTICATED_POINTER` | arm64e only | — | — | — | out of scope |

Sources: the enum and worked examples in [arm64/reloc.h], LLVM's selection logic ([AArch64MachObjectWriter.cpp] L76–118), and ld64's validation ([ld64 parser] L7875–8125). ld64 throws on each of these violations:

- `r_extern == 0` with `BRANCH26`/`PAGE21`/`PAGEOFF12`. The `internal` probe confirmed this against the current ld: `relocation in '_main' is not supported: r_address=0x8, r_type=3, r_extern=0`.
- `r_length != 2` for any instruction relocation.
- A `BRANCH26` or `PAGE21` record without `r_pcrel`, or a `PAGEOFF12` record with it.
- An `ADDEND` whose `r_address` differs from the next record's.
- An `ADDEND` in front of `GOT_LOAD_*`, `TLVP_*`, `SUBTRACTOR`, or `POINTER_TO_GOT`.
- An embedded addend in the instruction *and* an `ADDEND` record. An embedded addend alone only draws a warning (`… has embedded addend. ARM64_RELOC_ADDEND should be used instead`).

Other details:

- **Instruction bytes stay zero** in the immediate fields. `bl` is stored as `0x94000000`, `adrp x0` as `0x90000000`, and `ldr x0,[x0]` as `0xf9400000` ([arm64/reloc.h] examples; `otool -tv` shows `adrp x8, 0`, `bl 0x54`).
- **The `PAGEOFF12` scale comes from the instruction.** ld64 decodes the load/store size bits (`instruction & 0xC0000000`) to scale the imm12 by 1/2/4/8 ([ld64 parser] L8041–8055). Forge always writes `r_length=2`, the size of the instruction word. The header comment "scaled by r_length" is misleading: LLVM always sets `Log2Size = 2` for these ([AArch64MachObjectWriter.cpp] L82).
- **`r_symbolnum` for local targets:** LLVM targets the nearest preceding linker-visible symbol (the "atom") and folds the distance into the addend ([AArch64MachObjectWriter.cpp] L308–316). A target with no such symbol is an error: "Must have non-local symbol earlier in section". The simplest scheme for Forge is to give every relocation target a symbol (`l_.str.N` for literals, the function or variable name otherwise), which is what clang does.
- **Conditional branches:** LLVM rejects `fixup_aarch64_pcrel_branch19` and `branch14` against anything but an assembler-local label in the same atom: "conditional branch requires assembler-local label" ([AArch64MachObjectWriter.cpp] L170–190). Reproduced: `b.eq _h` and `b.eq .Lx` both fail under `.subsections_via_symbols`, and `b.eq Lx` succeeds.
- **Range:** `BRANCH26` reaches ±128 MB, and ld inserts branch islands beyond that. `PAGE21` reaches ±4 GB. Neither is a concern at slice scale.
- **Order inside a section:** relocations need not be sorted, but an `ADDEND` must immediately precede the record it modifies.

### Which relocation for which C construct

This is what clang `-O1` does, observed in `t.s` and `z.s`:

- **Call** (`f()`, including `static` and same-file functions): `bl _f` with `BRANCH26`. For external functions, ld builds the `__stubs` / lazy-binding machinery itself; there is no `@PLT` syntax.
- **Address or load of a global defined in this object** (non-common): `adrp x, _g@PAGE` plus `add`/`ldr x, [x, _g@PAGEOFF]`, giving `PAGE21` + `PAGEOFF12`.
- **Address or load of an extern or common global:** `adrp x, _g@GOTPAGE` + `ldr x, [x, _g@GOTPAGEOFF]` + `ldr w, [x]`, giving `GOT_LOAD_PAGE21` + `GOT_LOAD_PAGEOFF12`. ld relaxes this to a direct `adrp`/`add` when the symbol is in the same image (observed in the linked probe: `ldr x8,[x8]` became `add x8, x8, #0x0`). Using the GOT form for every non-local data reference is therefore always correct, just slightly larger before relaxation.
- **String literal:** `adrp x0, l_.str@PAGE` + `add x0, x0, l_.str@PAGEOFF`, where `l_.str` lives in `__cstring`.
- **Pointer-valued initializer** (`int *p = &g;`): `.quad _g` with `UNSIGNED`, `r_length=3`, `r_extern=1`. Static linking turns it into a rebase or bind fixup.

## 4. Empirical probe (what ld actually accepts)

`research/mach-o-arm64-probe.py` (committed next to this file) writes an `MH_OBJECT` by hand for this program:

```c
int main(void) { puts("hello from forge probe"); return ext_var; }  // ext_var = 7 in a clang-built .o
```

It uses `stp`/`mov x29`, `PAGE21`+`PAGEOFF12` to `l_.str` in `__cstring`, `BRANCH26` to `_puts`, and a `GOT_LOAD` pair for `_ext_var`. It was linked with `clang probe.o e2.o` (ld-1167.5) and with `-Wl,-ld_classic`, then run on macOS 15 (Darwin 24.6) arm64.

| variant | result |
|---|---|
| full (`SEGMENT_64` + `BUILD_VERSION` + `SYMTAB` + `DYSYMTAB`, subsections flag) | links, prints, exit 7 |
| no `LC_DYSYMTAB` | links, runs |
| no `LC_BUILD_VERSION` | links, runs, **warning** `no platform load command found …, assuming: macOS` |
| no `MH_SUBSECTIONS_VIA_SYMBOLS` | links, runs |
| symbol table not in local/extdef/undef order | links, runs |
| `ADDEND` (+2) before `PAGE21` and `PAGEOFF12` into `"XXhello…"` | links, prints `hello…` (addend applied) |
| `PAGE21`/`PAGEOFF12` with `r_extern=0` (section ordinal) | **ld error**: relocation not supported |
| `mov w0,#42; ret` with only `SEGMENT_64` + `SYMTAB`, linked with raw `ld -arch arm64 -platform_version macos 14.0 15.0 -syslibroot $(xcrun --show-sdk-path) -lSystem` | runs, exit 42 |

The linked executable is ad-hoc **linker-signed** (`codesign -dv`: `flags=0x20002(adhoc,linker-signed)`). macOS arm64 refuses to run unsigned code, and ld signs automatically, so Forge's `.o` needs nothing for that. No `__compact_unwind` was emitted, and ld did not complain.

## 5. Apple arm64 ABI vs AAPCS64

Apple says its platforms "diverge from the standard 64-bit ARM architecture in a few specific ways. Apart from these small differences, iOS, tvOS, and macOS adhere to the rest of the 64-bit ARM specification" ([Apple arm64]).

| topic | AAPCS64 (2025Q4) | Apple |
|---|---|---|
| `x18` | "The Platform Register, if needed; otherwise a Caller-saved register" ([AAPCS64] Table 2) | "The platforms reserve register `x18`. Don't use this register." Exclude it from register allocation entirely. |
| frame pointer | The platform chooses one of four conformance levels ([AAPCS64] "The Frame Pointer") | "`x29` must always address a valid frame record. Some functions — such as leaf functions or tail calls — may opt not to create an entry." A frame record is `{prev FP, LR}`, with FP pointing at it; clang emits `stp x29, x30, [sp, #k]; add x29, sp, #k`. |
| SP alignment | `SP mod 16 = 0` at every SP-based access (hardware) and at public interfaces | Same: "requires 16-byte alignment". |
| red zone | "No thread is permitted to access … the inactive region" below SP, so there is no red zone | 128 bytes below SP are preserved and may hold locals in leaf functions. A function that calls must build a frame. |
| narrow integer args | Unused bits are "unspecified", so the **callee** extends | The **caller** sign- or zero-extends any argument narrower than 32 bits. Observed: for `h(char, short, unsigned char)` the caller emits `sxtb`/`sxth`/`and #0xff`, and `int r(char c){return c;}` compiles to a bare `ret`, so the callee trusts the extension. |
| stack-passed args | C.16: values under 8 bytes are rounded up to an 8-byte slot | Packed at natural size and alignment (two `char`s at `sp` and `sp+1`); only the total is padded to 8. |
| `__int128` in registers | Must start in an even `xN` | May start in an odd `xN` (`x1:x2`). |
| **variadic args** | Same register rules as named args; `va_list` is a 5-field struct (`__stack`, `__gr_top`, `__vr_top`, `__gr_offs`, `__vr_offs`) | **Every variadic argument goes on the stack in 8-byte slots** (after default promotions), and NSRN is rounded up. `va_list` is `char*`. Observed for `printf("…", counter, 7)`: `stp x8, x9, [sp]` before `bl _printf`, and only the format string goes in `x0`. |
| empty structs | Not addressed | Ignored as parameters (GNU C extension). |
| `char` | Unsigned | **Signed** |
| `long double` | IEEE quad (128-bit) | Same as `double` |
| `wchar_t` | (platform) | 32-bit signed |
| sizes and alignment | LP64 | LP64: `long` and pointers 8/8, `int` 4/4, `short` 2/2, `bool` 1/1 |
| C++ | Itanium-derived | Constructors and destructors return `this`; `va_list` mangles as `Pc`; and more. Out of scope. |

Everything else follows AAPCS64 unchanged:
- Arguments in `x0`–`x7` / `v0`–`v7`, results in `x0`/`v0`.
- `x8` is the indirect-result register.
- `x19`–`x28`, `x29`, and `sp` are callee-saved; `d8`–`d15` (low 64 bits) are callee-saved.
- `x16`/`x17` are IP0/IP1, which the linker may clobber in stubs and islands.
- `x30` is the LR.

## 6. Apple `as` syntax vs GNU `as`

Source: LLVM's Darwin `MCAsmInfo` ([AArch64MCAsmInfo.cpp] L134–155) and its MachO `@`-specifier table (L32–45). Every row was checked against `clang -c` (Apple clang 17):

| feature | Apple / Mach-O | GNU / ELF | verified |
|---|---|---|---|
| page address | `adrp x0, sym@PAGE` | `adrp x0, sym` | the bare form fails: "ADR/ADRP relocations must be GOT relative" |
| low 12 bits | `add x0, x0, sym@PAGEOFF` | `add x0, x0, :lo12:sym` | `:lo12:` fails |
| GOT | `sym@GOTPAGE` / `sym@GOTPAGEOFF` | `:got:sym` / `:got_lo12:sym` | `:got:` fails |
| TLS | `sym@TLVPPAGE` / `sym@TLVPPAGEOFF` | `:tlsdesc:` etc. | — |
| comment | `;` (`CommentString`); `//` also accepted | `//` | both OK |
| statement separator | `%%` | `;` | OK |
| section | `.section __TEXT,__text,regular,pure_instructions`; shorthands `.text`, `.data`, `.cstring`, `.const` | `.section .text,"ax",@progbits` | ELF form fails: "unknown section type" |
| zero-fill | `.zerofill __DATA,__bss,_s,4,2` (size, log2 align); `.comm _g,4,2` | `.bss` / `.lcomm` / `.comm` (byte align) | — |
| alignment | `.p2align 2`; `.align N` is also log2 | `.p2align`; `.align` is log2 on AArch64 ELF too | OK |
| visibility | `.globl`, `.private_extern`, `.weak_definition`, `.weak_reference` | `.globl`, `.hidden`, `.weak` | `.hidden` fails |
| symbol metadata | none | `.type sym,@function`, `.size` | both fail: "unknown directive" |
| local labels | `L` prefix (`Ltmp0`, `LBB0_1`) | `.L` prefix | `.L` becomes a real symbol |
| platform | `.build_version macos, 14, 0 sdk_version 15, 0` | n/a | — |
| atoms | `.subsections_via_symbols` (last line) | n/a | — |
| linker hints | `.loh AdrpAdd Lloh6, Lloh7` and similar (optional) | n/a | — |
| NEON mnemonics | Apple form printed by default (`AssemblerDialect = Apple`); both parse | generic | — |

## 7. Implications for "How the slice produces the .o"

These are not decisions; they are what any choice must satisfy.

1. **A direct object writer is small.**
   - It emits one segment, about 4 sections (`__text`, `__cstring`, `__data`, `__bss`/`__const`), and `LC_BUILD_VERSION`, `LC_SYMTAB`, and `LC_DYSYMTAB`.
   - It needs a 16-byte nlist table, a string table, and five relocation kinds (`BRANCH26`, `PAGE21`, `PAGEOFF12`, `GOT_LOAD_PAGE21`/`PAGEOFF12`, plus `ADDEND` and `UNSIGNED`).
   - No unwind info, LOH, or data-in-code is needed to link and run.
   - The throwaway probe is about 150 lines of Python.
2. **Going through textual assembly with `clang -c x.s` is also viable**, and gives free cross-checking: Forge's own encoder can be diffed against `clang -c` output (`otool -rv`, `nm -m`, `otool -tv`). But it puts Apple's assembler on the critical path, which only exists on macOS. Cross-compiling CI on Windows and Linux could still check `.s` text with FileCheck, and LLVM's `llvm-mc -triple arm64-apple-macos` accepts the same syntax if CI wants a non-Apple assembler for tests (ADR 0002 permits third-party code only in tests).
3. **Requirements the emitter must meet regardless of route:**
   - Every reference that crosses a function boundary is an external relocation against a symbol.
   - Block labels are `L…`.
   - Literals get an `l_` symbol.
   - Extern data goes through the GOT.
   - `x18` is never allocated.
   - Every non-leaf function builds an `x29`/`x30` frame record.
   - Variadic call sites spill their variadic arguments to 8-byte stack slots.
   - The caller extends sub-`int` arguments.
4. **Link-and-run tests need macOS arm64, as already planned.** The `.o` itself can be validated on any host with `llvm-objdump --macho` / `llvm-readobj`, but those are third-party tools, allowed only in tests. ld signs the output automatically.

## Sources

- [loader.h]: `mach-o/loader.h`, macOS SDK 15.5 (`/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/mach-o/loader.h`). Line numbers are from this copy. The same header is published in Apple's [cctools / xnu](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h).
- [nlist.h]: `mach-o/nlist.h`, same SDK.
- [reloc.h]: `mach-o/reloc.h`, same SDK (`struct relocation_info`).
- [arm64/reloc.h]: `mach-o/arm64/reloc.h`, same SDK. It contains the enum and the worked assembly-to-relocation examples.
- [machine.h]: `mach/machine.h`, same SDK.
- [Apple arm64]: Apple, ["Writing ARM64 code for Apple platforms"](https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms), retrieved 2026-11-21 via its DocC JSON.
- [AAPCS64]: Arm, ["Procedure Call Standard for the Arm 64-bit Architecture"](https://github.com/ARM-software/abi-aa/blob/9f9e067e6c6a5d3c5c8326756500cdbd940b8ff7/aapcs64/aapcs64.rst), 2025Q4, abi-aa @ `9f9e067`.
- [ld64 parser]: [`ld64/src/ld/parsers/macho_relocatable_file.cpp`](https://github.com/apple-oss-distributions/ld64/blob/f60a74eaa2c99585de1dc0f2820e7a9f8aaf522c/src/ld/parsers/macho_relocatable_file.cpp) @ `f60a74e`. This is the open-source *classic* ld64. The shipping default (ld-1167, "ld-prime") is closed-source; its behaviour was checked by the probes in section 4.
- [AArch64MachObjectWriter.cpp]: [`llvm/lib/Target/AArch64/MCTargetDesc/AArch64MachObjectWriter.cpp`](https://github.com/llvm/llvm-project/blob/bb55066964931c9287b04148eb2d97fc7329800d/llvm/lib/Target/AArch64/MCTargetDesc/AArch64MachObjectWriter.cpp) @ `bb55066`.
- [MachObjectWriter.cpp]: [`llvm/lib/MC/MachObjectWriter.cpp`](https://github.com/llvm/llvm-project/blob/bb55066964931c9287b04148eb2d97fc7329800d/llvm/lib/MC/MachObjectWriter.cpp) @ `bb55066`.
- [AArch64MCAsmInfo.cpp]: [`llvm/lib/Target/AArch64/MCTargetDesc/AArch64MCAsmInfo.cpp`](https://github.com/llvm/llvm-project/blob/bb55066964931c9287b04148eb2d97fc7329800d/llvm/lib/Target/AArch64/MCTargetDesc/AArch64MCAsmInfo.cpp) @ `bb55066`.
- Observed: Apple clang 17.0.0 (clang-1700.0.13.5), ld-1167.5, macOS 15 SDK, Darwin 24.6.0 arm64. Tools used: `clang -S`/`-c`, `otool -hv/-lv/-rv/-tv`, `nm -m`, `xxd`, `codesign -dv`.
