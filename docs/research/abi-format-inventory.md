# ABI and object-format inventory

Research for GitHub issue #3 (parent map #1). Throwaway branch `research/abi-format-inventory`; never merged, no PR.

**Question.** What do SysV x86-64, AAPCS64 (including Apple's arm64 variant), the Itanium C++ ABI, ELF, Mach-O, PE/COFF and DWARF each demand of a compiler, an assembler and a linker?

**Method.** Primary sources only: the specifications themselves, or the vendor's own header files and documentation. Every source was downloaded as raw text (LaTeX, reST, Markdown, HTML, C headers, PDF to text) and read directly; no secondary write-ups were used for any claim in sections 1 to 9. Where a primary source could not be located, the claim is listed in section 11 and not asserted anywhere else.

**Role split used below.**

- *Compiler*: what the code generator and front end must emit or decide (layout, calling sequence, symbol naming, unwind and debug data).
- *Assembler*: what must be encodable in an object file (sections, symbols, relocations, directives, CFI/line tables).
- *Linker*: what must be resolved, merged, laid out, synthesised or rewritten (relocation processing, GOT/PLT/stubs, COMDAT, veneers, unwind tables, headers).

Where a spec does not assign a duty to one role explicitly, the duty is attributed by what the spec's mechanism requires, and marked *(inferred)*.

## 0. Sources and versions

| Short name | Document | Location | Version as read |
|---|---|---|---|
| psABI-x86-64 | System V ABI, AMD64 Architecture Processor Supplement (`low-level-sys-info.tex`, `object-files.tex`) | https://gitlab.com/x86-psABIs/x86-64-ABI (master) | master, fetched 2026-11-09 |
| AAPCS64 | Procedure Call Standard for the Arm 64-bit Architecture | https://github.com/ARM-software/abi-aa/blob/main/aapcs64/aapcs64.rst | main, fetched 2026-11-09 (change history up to 2025Q4) |
| AAELF64 | ELF for the Arm 64-bit Architecture | https://github.com/ARM-software/abi-aa/blob/main/aaelf64/aaelf64.rst | main, fetched 2026-11-09 |
| AADWARF64 | DWARF for the Arm 64-bit Architecture | https://github.com/ARM-software/abi-aa/blob/main/aadwarf64/aadwarf64.rst | main, fetched 2026-11-09 |
| Apple-arm64 | Writing ARM64 code for Apple platforms | https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms | fetched 2026-11-09 via Apple's documentation JSON endpoint |
| Itanium-C++ | Itanium C++ ABI (`abi.html`) and Exception Handling (`abi-eh.html`, rev 1.22) | https://itanium-cxx-abi.github.io/cxx-abi/ | fetched 2026-11-09; revision history last entries 2016 |
| gABI | System V ABI, generic part, chapters 4 and 5 | https://www.sco.com/developers/gabi/latest/contents.html | "DRAFT - 10 June 2013" |
| Mach-O headers | `mach-o/loader.h`, `nlist.h`, `reloc.h`, `arm64/reloc.h`, `x86_64/reloc.h` | https://github.com/apple-oss-distributions/xnu/tree/main/EXTERNAL_HEADERS/mach-o | main, fetched 2026-11-09 |
| Mach-O SDK headers | `compact_unwind_encoding.h`, `fixup-chains.h` | local macOS SDK (`xcrun --show-sdk-path`)/usr/include/mach-o; fixup-chains also at apple-oss-distributions/dyld | CommandLineTools MacOSX.sdk on the research host |
| PE | PE Format | https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/Debug/pe-format.md (rendered at learn.microsoft.com/windows/win32/debug/pe-format) | docs branch, fetched 2026-11-09 |
| MSVC-x64 | x64 calling convention, software conventions, exception handling | https://github.com/MicrosoftDocs/cpp-docs/tree/main/docs/build | main; x64-calling-convention.md dated 03/19/2025 |
| MSVC-arm64 | ARM64 Windows ABI conventions, ARM64 exception handling | same directory | main |
| DWARF5 | DWARF Debugging Information Format Version 5 | https://dwarfstd.org/doc/DWARF5.pdf | February 13, 2017 |

A note on dating: the gABI text on sco.com is the current generic draft but is dated 2013; psABI documents are living. Nothing below depends on a specific revision unless stated.

## 1. SysV x86-64 psABI

Applies to ELF x86-64 systems (the supplement is an ELF psABI). Whether Darwin x86-64 follows it is not stated in the sources read; the Mach-O x86-64 relocation header and SDK compact-unwind header only show x86-64 is supported (see section 11).

### 1.1 Compiler

- **Fundamental types** (psABI-x86-64 sec. 1.2): `char` 1, `short` 2, `int`/`float` 4, `long` and pointers 8 (LP64) or 4 (ILP32); `long long` 8; `__int128` 16 bytes with 16-byte alignment; `long double` is 80-bit x87 extended stored in 16 bytes; `__float128` 16; `_Float16` and `__bf16` 2; `__m128`/`__m256`/`__m512` 16/32/64 with matching alignment. `_Alignof(max_align_t)` is 16. `_BitInt(N)` is defined (N <= 64 as the smallest containing integer, larger as 64-bit chunks).
- **Stack** (sec. 2.2): the stack is 16-byte aligned (32 or 64 if `__m256`/`__m512` is passed in memory) immediately before the `call`, so that `rsp + 8` is a multiple of 16 on entry. The 128 bytes below `rsp` are a **red zone** that signal and interrupt handlers must not touch; leaf functions may use it as their whole frame.
- **Argument classification** (sec. 2.3): each eightbyte of an argument is classified INTEGER, SSE, SSEUP, X87, X87UP, COMPLEX_X87, NO_CLASS or MEMORY. Aggregates over eight eightbytes, or with unaligned fields, are MEMORY. Per-eightbyte merge rules: equal stays; NO_CLASS yields the other; MEMORY wins; INTEGER beats SSE; any X87 variant mixed with another class gives MEMORY; otherwise SSE. Post-merge cleanup rules then apply (MEMORY forces whole object to memory; stray X87UP forces memory; SSEUP not after SSE becomes SSE). **Non-trivial C++ objects are passed by invisible reference** (INTEGER class pointer).
- **Register assignment**: INTEGER in `rdi, rsi, rdx, rcx, r8, r9`; SSE in `xmm0` to `xmm7`; everything else, and any argument for which not all eightbytes fit in the remaining registers, goes to the stack (right to left, with partial register assignment reverted). Varargs: `%al` carries an upper bound (0 to 8) on vector registers used; `__m256`/`__m512` varargs go on the stack.
- **Return**: INTEGER in `rax`, `rdx`; SSE in `xmm0`, `xmm1`; X87 in `st0`; COMPLEX_X87 in `st0`/`st1`; MEMORY via hidden pointer in `rdi`, returned again in `rax`.
- **Callee-saved**: `rbx, rbp, r12 to r15, rsp`, plus MXCSR control bits and the x87 control word; `%fs` is the thread pointer. Caller-saved: everything else including all vector registers and `k0` to `k7`. `r10` is the static-chain register, `r11` is scratch. DF must be clear at call and return. `emms` is required after MMX use.
- **Code models** (sec. 5, "Coding Examples"): small, kernel, medium, large and PIC variants. The compiler must choose one and emit the matching sequences (`movabs` and indirect branches for large; GOT base in `r15` for medium/large PIC). Small model: symbols within 0 to 2^31 - 2^24 - 1.
- **Micro-architecture levels** (sec. 1.1): `x86-64` baseline (CMOV, CX8, FPU, FXSR, MMX, SSE, SSE2), `-v2` (adds POPCNT, SSE3 to SSE4.2, CMPXCHG16B, LAHF-SAHF), `-v3` (AVX, AVX2, BMI1/2, F16C, FMA, LZCNT, MOVBE), `-v4` (AVX512F/BW/CD/DQ/VL). Fallback code for `glibc-hwcaps` selection must be built for baseline `x86-64`.

### 1.2 Assembler / object format (ELF supplement, `object-files.tex`)

- **Relocations**: LP64 uses only `Elf64_Rela` (explicit addend). The relocation table defines, among others: `R_X86_64_64` (S+A), `PC32` (S+A-P), `PLT32` (L+A-P), `GOTPCREL` (G+GOT+A-P), `32`/`32S`, `GLOB_DAT`, `JUMP_SLOT`, `RELATIVE` (B+A), `IRELATIVE`, TLS relocations (`TLSGD`, `TLSLD`, `DTPOFF32`, `GOTTPOFF`, `TPOFF32`, `GOTPC32_TLSDESC`, `TLSDESC_CALL`, `TLSDESC`), and the relaxable GOT forms `GOTPCRELX`, `REX_GOTPCRELX`, plus APX `CODE_4/5/6_*` variants. The assembler must pick `GOTPCRELX` (starts 2 bytes before the relocation offset), `REX_GOTPCRELX` (3 bytes, REX prefix) or the `CODE_n_` form according to where the instruction starts, so the linker can relax.
- **Sections**: `SHT_X86_64_UNWIND` (0x70000001) for `.eh_frame`; `.got`, `.plt`; large-model sections `.lbss .ldata .lgot .lplt .lrodata .ltext` with flag `SHF_X86_64_LARGE` (0x10000000).
- **Symbols**: `STT_GNU_IFUNC` (resolver returning a function pointer, evaluated at load time) is optional.
- **`.eh_frame`**: one CIE per subsection followed by FDEs; one FDE per contiguous code piece; C++ template instantiations each get their own preceding CIE. With the preferred encoding the section is fully resolvable at link time and can sit in the text segment. Augmentation string supports `z`, `L` (LSDA pointer encoding), `R` (FDE pointer encoding), `P` (personality); `z` must come first.

### 1.3 Linker

- Resolve the relocation set above, including **relaxation** of `GOTPCRELX`-family relocations (psABI sec. on optimisation, `opt_gotpcrelx`) *(the relaxation rules themselves were not read; the existence of the relocation types for that purpose is stated in the text)*.
- Synthesise `.got`, `.plt` and, for large models, `.lgot`/`.lplt`; order sections so small-model sections stay within 2 GB (`.plt .init .fini .text .got .rodata .rodata1 .data .data1 .bss`) and large ones follow (`.lplt .ltext .lgot .lrodata ... .lbss`).
- Build the `.eh_frame` table (and per the Linux extensions `.eh_frame_hdr`, which the psABI references but does not define).
- Process-entry contract it must be compatible with (sec. 4): `rsp` 16-byte aligned, `rdx` holds an `atexit` function pointer, `rbp` should be zero to mark the deepest frame; initial stack carries argc, argv, envp and the auxiliary vector (`AT_HWCAP`, `AT_PLATFORM`, `AT_RANDOM`, ...).

### 1.4 DWARF (sec. 6, "DWARF Definition")

Register mapping: 0 to 7 = `rax, rdx, rcx, rbx, rsi, rdi, rbp, rsp`; 8 to 15 = `r8` to `r15`; 16 = return address; 17 to 32 = `xmm0` to `xmm15`; 33 to 40 = `st0` to `st7`; 41 to 48 = `mm0` to `mm7`; 49 = rFLAGS; 50 to 55 = segment regs; 58/59 = `fs.base`/`gs.base`; 64 = mxcsr; 65/66 = x87 control/status; 67 to 82 = `xmm16` to `xmm31`; 118 to 125 = `k0` to `k7`; 130 to 145 = APX `r16` to `r31`; 146 to 153 = `tmm0` to `tmm7`; 154 = tilecfg. The psABI states that the x86-64 ABI "does not define a debug format" but that any DWARF system on x86-64 shall use this mapping, and (sec. 7, "Stack Unwind Algorithm") that `.eh_frame` is identical in format to `.debug_frame` with the extensions listed there.

## 2. AAPCS64 (generic Arm 64-bit procedure call standard)

### 2.1 Compiler

- **Registers** (AAPCS64 "Machine Registers"): `x0` to `x7` arguments/results; `x8` indirect-result location register; `x9` to `x15` caller-saved; `x16`/`x17` (IP0/IP1) intra-procedure-call scratch, usable by linker veneers and PLT code, otherwise caller-saved; `x18` platform register (caller-saved if the platform does not claim it; the platform ABI must document any use); `x19` to `x28` callee-saved; `x29` FP; `x30` LR. `v0` to `v7` arguments/results; `v8` to `v15` callee-saved **low 64 bits only**; `v16` to `v31` caller-saved. NZCV undefined across public interfaces. With SVE: if a routine takes or returns scalable vector/predicate arguments, `z8` to `z23` and `p4` to `p15` become callee-saved.
- **Stack**: `SP` must be 16-byte aligned whenever memory is accessed through it, and at every public interface.
- **Frame chain** ("The Frame Pointer"): conforming code builds a linked list of two-doubleword frame records; `FP` points to the innermost; low doubleword = previous record, high doubleword = LR on entry (signed first if return-address signing is used); chain ends at zero. **The platform must state its minimum conformance level** (always valid; valid except leaf/tail routines; valid except any routine may skip; or no requirement).
- **Argument passing** (stages A to C): NGRN/NSRN/NSAA state machine. Stage B: composites over 16 bytes are copied to caller memory and replaced by a pointer (B.4); other composites rounded up to a multiple of 8 bytes (B.5). Stage C: floats/short vectors to `v[NSRN]` (C.1); HFA/HVA (at most 4 same-type members) to consecutive `v` registers if they fit, else NSRN set to 8 and the argument goes to the stack (C.2, C.3); integers/pointers to `x[NGRN]` (C.9); 16-aligned arguments need an even NGRN (C.10); 16-byte integers use a register pair x[NGRN], x[NGRN+1] (C.11); composites of up to 16 bytes go to consecutive `x` registers (C.12); otherwise NGRN set to 8 and the argument is copied to the stack at NSAA aligned to max(8, natural alignment) (C.13 to C.17). Padding bits have unspecified values.
- **Callee narrows**: "Unlike in the 32-bit AAPCS, named integral values must be narrowed by the callee rather than the caller" (generic AAPCS64; Apple reverses this, see sec. 3).
- **Variadic**: the generic rules treat named arguments as normal and anonymous arguments by the same algorithm; `va_list` is `struct __va_list { void *__stack; void *__gr_top; void *__vr_top; int __gr_offs; int __vr_offs; }` (in C++ it lives in namespace `std`).
- **Result return**: any result that would be passed in registers as an argument is returned in the same registers; otherwise the caller reserves memory and passes its address in `x8`.
- **Types** (Table 1, language mappings): integers 1/2/4/8 aligned to size, 16-byte integers aligned 16; pointers 8 bytes; half/single/double/quad floats (`long double` is IEEE binary128 quad in the generic standard); short vectors 8/16 bytes; scalable vectors and predicates. Half precision has IEEE, Arm Alternative and bfloat16 formats; the base standard uses IEEE.
- **Data models**: `sizeof(long)`, `wchar_t` and pointer size vary by data model (the standard covers variants); interworking between variants is not defined within one process, and 32-bit/64-bit interworking is not supported.

### 2.2 Assembler

- Instruction streams need **mapping symbols** (AAELF64 "Mapping symbols"): `$x` starts a run of A64 instructions, `$d` a run of data; all are `STT_NOTYPE`, `STB_LOCAL`, size zero; a section containing instructions must have one at its start; relocations may not reference them.
- Must emit relocations from the AAELF64 set (see 2.4).

### 2.3 Linker (AAPCS64 "Use of IP0 and IP1 by the linker")

- `B`/`BL` reach is +/-128 MB, so the linker **may insert veneers** at any branch exposed to a relocation that supports long branches. A veneer must preserve every register except IP0, IP1 and the condition flags. Therefore a conforming program must assume IP0/IP1 may be clobbered at any such branch (this is a constraint on compiler-generated code too).

### 2.4 ELF for AArch64 (AAELF64)

- Static vs dynamic relocations are distinguished. Relocation sets include `R_AARCH64_ABS64`, `CALL26` (283), `JUMP26` (282; both check +/-2^27), `ADR_PREL_PG_HI21` (275; with the `LO12` family), the GOT family (`ADR_GOT_PAGE`, `LD64_GOT_LO12_NC`, ...), TLS (traditional and TLS descriptors, `TLSDESC_LDR/ADD/CALL` to permit relaxation), dynamic `GLOB_DAT`, `JUMP_SLOT`, `RELATIVE`, `IRELATIVE`. Files may use REL, RELA or a mix, but one place uses only one type; RELA is required when the addend does not fit the place.
- Veneer eligibility (AAELF64 "Call and Jump relocations"): a linker may veneer a `CALL26`/`JUMP26`/`PLT32` only if the target is `STT_FUNC`, or in a different input section, or undefined; otherwise it must diagnose. An unresolved weak `CALL26` becomes a no-op on platforms without symbol preemption.
- **BTI**: veneers that use an indirect branch must target a BTI or BTI-compatible instruction, otherwise the linker must add a BTI landing veneer. The program-property (GNU property) encoding of BTI/PAC has moved to the SysV ABI document and was not read here.
- Pointer authentication ELF ABI is separately specified (`pauthabielf64`); only its existence was confirmed.

### 2.5 DWARF for AArch64 (AADWARF64)

DWARF registers: 0 to 30 = `x0` to `x30`; 31 = SP; 32 = PC; 33 = ELR_mode; 34 = `RA_SIGN_STATE` pseudo-register; 35 to 39 = TPIDR registers; 46 = VG; 47 = FFR; 48 to 63 = `p0` to `p15`; 64 to 95 = `v0` to `v31`; 96 to 127 = `z0` to `z31`. AArch64 defines CFI extensions for return-address signing (`DW_CFA_AARCH64_negate_ra_state`, and in 2025Q4 `DW_CFA_AARCH64_set_ra_state`, marked Alpha).

## 3. Apple arm64 (differences from AAPCS64)

All from the Apple-arm64 page unless marked.

### 3.1 Compiler

- **Register use**: `x18` is reserved; do not use it. The frame pointer `x29` **must always address a valid frame record** (leaf functions and tail calls may omit the record), so stack traces are meaningful without debug info. The red zone is the 128 bytes below SP.
- **Types**: `char` is signed; `wchar_t` is 32-bit signed; `long` 64-bit; `__fp16` is IEEE 754-2008; **`long double` is identical to `double`** (not quad). Sizes: `BOOL`/`bool`/`char` 1; `short` 2; `int` 4; `long`, `long long`, pointers, `size_t`, `NSInteger`, `CFIndex`, `fpos_t`, `off_t` 8.
- **Argument passing deviations**:
  1. Stack arguments may use slots that are not multiples of 8 bytes (naturally packed), with padding only to preserve 8-byte alignment of the total and 16-byte SP alignment.
  2. A 16-byte-aligned argument in integer registers may start in an odd-numbered `xN` (generic rule C.10 requires even).
  3. **The caller** sign- or zero-extends arguments narrower than 32 bits (generic: the callee does).
  4. Empty struct parameters may be ignored (GNU C extension, and C++ where permitted).
- **Variadic arguments**: Apple initialises registers (Stage A) and pads/extends (Stage B) as usual, but then every variadic argument is placed in **8-byte stack slots** (the page lists: round up the NSAA to 8 bytes; assign to the appropriate number of 8-byte stack slots; the first item of that list is printed as "Round up the Next SIMD and Floating-point Register Number (NSRN)..." in the source and is presumably a typo for NSAA). Consequently **`va_list` is `char *`**, not the AAPCS64 struct, and is not in `std` in C++.
- **C++ ABI differences** (the Apple page says the generic ARM64 C++ ABI mirrors Itanium and lists departures): mangled `va_list` is `Pc`, not `St9__va_list`; NEON vector type manglings match 32-bit ARM (`17__simd128_int32_t`, not `11_int32x4_t`); empty structs ignored when passing unless they have a non-trivial destructor/copy constructor (then treated as one byte member); **C1/C2 constructors and D1/D2 destructors return `this`** (as in the 32-bit ARM C++ ABI); array cookie is a fixed two `size_t` words with no extra alignment; guard variables are nominally `uint64_t` (prototypes of `__cxa_guard_acquire/release/abort` change); a pointer to an `extern "C"` function is **not** interchangeable with one to an `extern "C++"` function.
- **DIT**: Apple documents Data-Independent Timing control for constant-time crypto (`timingsafe_enable_if_supported`/`timingsafe_restore_if_supported`, PSTATE.DIT bit 24, `sb` barrier). This is a library/intrinsics concern, noted for completeness.

### 3.2 Assembler and linker

The Apple page does not address them. Format-level duties come from Mach-O (section 6).

## 4. Itanium C++ ABI

Apple states that the generic ARM64 C++ ABI mirrors Itanium and that Apple's own arm64 C++ ABI departs from it in listed ways (sec. 3.1). The Itanium document is a specification of the C++ language entities layered on a C psABI; `abi.html` sec. 1.4 states it starts "from the Itanium processor-specific ABI as the standard for the underlying C interfaces".

### 4.1 Compiler

- **Data layout** (ch. 2): POD layout (2.2); data member pointers and member function pointers `{ptr, adj}` (2.3; the ABI notes the 32-bit ARM variant, where `adj` is left-shifted by one and its low bit says whether `ptr` is virtual); non-POD class layout and primary bases (2.4); **vtable layout** (2.5): components and order, construction of the table incl. primary/indirect-primary bases; VTTs and construction vtables during construction (2.6); **array `operator new` cookies** (2.7, a `size_t` count stored before elements when the element type has a non-trivial destructor or a usual sized array deallocation function takes `size_t`); **guard variables** (2.8, 64 bits, first byte 0 before and 1 after initialization); **RTTI** (2.9): `type_info` layout and equality (pointer equality iff equivalent; achieved by symbol preemption, COMDAT or similar), emission with the primary vtable, `dynamic_cast` algorithm, exception handler matching algorithm. Cross-references inside RTTI to possibly-incomplete types must be weak.
- **Calling** (ch. 3, layered on the C psABI): `this` first (3.1.2.1); VTT parameter (3.1.2.2); **non-trivial-for-calls class arguments are passed by reference to a caller-allocated temporary**, with the caller running the destructor after the call, even if the caller throws (3.1.2.3); the same applies to variadic arguments (`va_arg` retrieves the address); empty parameters (3.1.2.6); non-trivial return values via hidden pointer (3.1.3.1); constructor/destructor return values (3.1.3.5/6; void generically, `this` on 32-bit ARM and Apple arm64).
- **Virtual calls** (3.2): vtable index dispatch, `__cxa_pure_virtual` for pure virtuals (3.2.6), deleted-virtual API (3.2.7).
- **Runtime APIs the compiler targets** (3.3): subobject constructors/destructors (mangled forms C1 complete, C2 base, C3 allocating; D0 deleting, D1 complete, D2 base), `__cxa_guard_acquire/release/abort` (taking a pointer to the 64-bit guard), array construction/destruction helpers, `__cxa_atexit(f, p, d)` with `&__dso_handle` (the linker "should define a hidden symbol `__dso_handle`").
- **Name mangling** (5.1): grammar rooted at `<mangled-name> ::= _Z <encoding>`, with special names `TV` (vtable), `TT` (VTT), `TI` (typeinfo), `TS` (typeinfo name) and guard `GV`; substitution/compression rules (5.1.10); closure types (5.1.8); `abi_tag` mangling (revision [160602]).
- **Exception handling** (separate document, three levels). Level I (base ABI): two-phase unwinding framework with `_Unwind_RaiseException`, `_Unwind_Resume`, `_Unwind_ForcedUnwind`, per-frame **personality routine** that the compiler must reference for every frame needing language-specific handling, and unwinder-managed exception object headers. Level II (C++ ABI): `__cxa_allocate_exception`, `__cxa_throw`, `__cxa_begin_catch`, `__cxa_end_catch`, `__cxa_rethrow`, landing pads that call `_Unwind_Resume` when done, cleanups, catch-matching via personality using RTTI. Level III is a suggested implementation only. The documents define the *contract* with the personality routine and landing-pad control flow; the LSDA table encoding and `.eh_frame` details come from the psABI / LSB, and no LSDA format definition appears in `abi-eh.html` (searched for "LSDA"; zero hits).

### 4.2 Assembler and linker (ch. 5.2 "Vague Linkage", 5.3)

- **COMDAT is the mechanism**: duplicates are removed using ELF `SHT_GROUP` with `GRP_COMDAT`, keyed by a signature symbol (gABI). Required for: out-of-line copies of inline functions (key = mangled name); static data and string literals in inline functions (and their guard variables, which must be weak); vtables, VTTs and construction vtables (emitted in one COMDAT per class, keyed by the vtable's mangled name, *unless* the class has a key function or is attached to a module, in which case they are emitted uniquely); `type_info` for types without a unique vtable; instantiated templates. "Key function" = the first non-pure virtual function that is not inline at the point of class definition.
- The linker must therefore keep one copy per COMDAT signature and discard the rest as a unit (all members of the group), and keep global/weak symbol definitions inside a group consistent (gABI sec. "Section Groups").
- 5.3: on Itanium (IA-64) the unwind table must be in `SHT_IA_64_UNWIND` with a `PT_IA_64_UNWIND` program header; this clause is specific to IA-64, and the x86-64 and AArch64 unwind sections come from their own supplements (sections 1.2 and 2.4).
- Non-ELF platforms: "On platforms that do not use COMDATs, the tables are emitted separately, and unreferenced tables can be omitted". Mach-O and COFF have their own equivalents (sections 6 and 7).
- Scope warning from sec. 1.4: the ABI does **not** specify the C++ standard library; only runtime interfaces that inherently interact between object files (construction, destruction, exceptions) are fixed.
- The MSVC C++ ABI is not an Itanium variant. No primary specification of it was found (section 11).

## 5. ELF (generic ABI)

### 5.1 Compiler

- Chooses sections, symbol binding/visibility (`STB_LOCAL/GLOBAL/WEAK`; `STV_DEFAULT/INTERNAL/HIDDEN/PROTECTED`, where a `STB_LOCAL` symbol may not be `STV_PROTECTED`), TLS model (`STT_TLS` symbols, `SHF_TLS` sections `.tdata`/`.tbss`, `PT_TLS`), COMDAT grouping (`SHF_GROUP`, `SHT_GROUP`), init/fini arrays (`.init_array`, `.fini_array`, `.preinit_array`).

### 5.2 Assembler (object-file writer)

- **ELF header** (ch. 4): class (32/64), data encoding, `e_machine`; the section-name string table index uses the `SHN_XINDEX` (0xffff) escape when it is >= `SHN_LORESERVE` (0xff00), with the real value in `sh_link` of section header 0; `e_shnum` is zero when the count does not fit, and `SHT_SYMTAB_SHNDX` carries extended symbol section indices.
- **Section header types and flags**: `SHT_PROGBITS`, `SHT_SYMTAB`, `SHT_STRTAB`, `SHT_RELA`/`SHT_REL`, `SHT_NOBITS`, `SHT_NOTE`, `SHT_INIT_ARRAY`, `SHT_GROUP`, `SHT_SYMTAB_SHNDX`; flags `SHF_WRITE/ALLOC/EXECINSTR`, `SHF_MERGE`, `SHF_STRINGS`, `SHF_INFO_LINK`, `SHF_LINK_ORDER`, `SHF_GROUP`, `SHF_TLS`, `SHF_COMPRESSED` (not combinable with `SHF_ALLOC`).
- **Symbol table**: all `STB_LOCAL` symbols precede the non-locals; a file symbol is `STB_LOCAL` and precedes the other locals; `st_other` carries visibility.
- **Relocations**: `Elf{32,64}_Rel` and `_Rela`; processor supplements define the types (sections 1 and 2.4).
- **Section groups**: `SHT_GROUP` section data = flag word (`GRP_COMDAT` 0x1) + member section indices; `sh_link`/`sh_info` name the symbol table and signature symbol; members carry `SHF_GROUP`; the group header's flags are 0.

### 5.3 Linker

- Duplicate COMDAT groups with the same signature: keep exactly one and discard the others as a unit.
- Merge `SHF_MERGE` sections; honour `SHF_LINK_ORDER`; apply the order constraint on locals/globals; handle the `SHN_XINDEX` escapes.
- **Program loading** (ch. 5): build program headers (`PT_LOAD`, `PT_DYNAMIC`, `PT_INTERP`, `PT_NOTE`, `PT_TLS`, ...); loadable segments must have **congruent `p_vaddr` and `p_offset` modulo the page size**; base address is derived from the lowest `PT_LOAD` `p_vaddr` and the maximum page size.
- **Dynamic linking**: build `.dynamic` (`DT_NEEDED`, `DT_SYMBOLIC`, `DT_INIT_ARRAY`/`DT_INIT_ARRAYSZ`, `DT_FLAGS`, ...), the GOT and PLT (processor-specific), the hash table, dynamic relocations, and the initialization/termination arrays.
- Note: this gABI draft predates widely-used extensions (`.gnu.hash`, `DT_RELR`, `.eh_frame_hdr`, `GNU_PROPERTY`); where the psABIs reference them (`STT_GNU_IFUNC`, `.eh_frame_hdr` in "Linux Extensions to gABI", https://gitlab.com/x86-psABIs/Linux-ABI) they are defined elsewhere, which was not read.

## 6. Mach-O

Primary sources are Apple's own headers; there is no prose specification of equivalent completeness in the sources read. Where behaviour is only inferable from header comments it is noted.

### 6.1 Compiler

- Chooses segment/section placement by name and type: `__TEXT,__text`, `__DATA`, `__LINKEDIT`, `__PAGEZERO` (SEG_ names in `loader.h`); section types `S_REGULAR`, `S_ZEROFILL` (0x1), `S_CSTRING_LITERALS` (0x2), `S_LITERAL_POINTERS`, `S_NON_LAZY_SYMBOL_POINTERS` (0x6), `S_LAZY_SYMBOL_POINTERS` (0x7), `S_SYMBOL_STUBS` (0x8), `S_MOD_INIT_FUNC_POINTERS` (0x9), `S_MOD_TERM_FUNC_POINTERS` (0xa), `S_COALESCED` (0xb), `S_16BYTE_LITERALS` (0xe), `S_THREAD_LOCAL_REGULAR/ZEROFILL/VARIABLES` (0x11 to 0x13), `S_INIT_FUNC_OFFSETS` (0x16); attributes `S_ATTR_PURE_INSTRUCTIONS`, `S_ATTR_NO_DEAD_STRIP`, `S_ATTR_LIVE_SUPPORT`, `S_ATTR_SOME_INSTRUCTIONS`, `S_ATTR_DEBUG`, etc.
- **Thread-locals** use TLV descriptors (`S_THREAD_LOCAL_VARIABLES`) and the `*_TLV`/`*_TLVP_*` relocations, not ELF-style TLS models; `MH_HAS_TLV_DESCRIPTORS` flags images that contain them.
- **Weak/coalesced semantic**: `N_WEAK_DEF` marks a coalesced weak definition; `N_WEAK_REF` a weak reference; `N_NO_DEAD_STRIP`; `N_ALT_ENTRY` = symbol "pinned to the previous content" (an additional entry point inside an atom).
- **Compact unwind** (`compact_unwind_encoding.h`, SDK): per-function 32-bit encodings with modes. x86-64: `RBP_FRAME` (0x01000000), `STACK_IMMD` (0x02), `STACK_IND` (0x03), `DWARF` (0x04). arm64: `FRAMELESS` (0x02), `DWARF` (0x03), `FRAME` (0x04). Common flag bits: `UNWIND_IS_NOT_FUNCTION_START` 0x80000000, `UNWIND_HAS_LSDA` 0x40000000, personality index mask 0x30000000. The `DWARF` modes mean the function's unwind info is the FDE in `__eh_frame`.

### 6.2 Assembler (object writer, `MH_OBJECT`)

- `mach_header_64` (magic `0xfeedfacf`) with load commands (`LC_SEGMENT_64`, `LC_SYMTAB`, `LC_DYSYMTAB`, ...); `LC_LINKER_OPTION` carries linker options in objects; `LC_BUILD_VERSION` records platform and minimum OS (`PLATFORM_MACOS` = 1, `PLATFORM_IOS` = 2 ...). The header flag **`MH_SUBSECTIONS_VIA_SYMBOLS`** (0x2000) declares it "safe to divide up the sections into sub-sections via symbols for dead code stripping", i.e. each non-`N_ALT_ENTRY` symbol starts an atom the linker may move or drop.
- **Symbols** (`nlist`): `n_type` bit fields `N_STAB` (0xe0), `N_PEXT`, `N_TYPE` (`N_UNDF` 0x0, `N_ABS` 0x2, `N_SECT` 0xe, ...), `N_EXT` (0x01); `n_desc` flags `N_WEAK_REF` 0x40, `N_WEAK_DEF` 0x80, `N_SYMBOL_RESOLVER` 0x100, `N_ALT_ENTRY` 0x200, `N_NO_DEAD_STRIP`/`N_DESC_DISCARDED` 0x20. Common symbols are `N_UNDF` + `N_EXT` with nonzero value.
- **Relocations** (`relocation_info`, 8 bytes: `r_address`, 24-bit `r_symbolnum`, `r_pcrel`, 2-bit `r_length` (0=byte..3=quad), `r_extern`, 4-bit `r_type`):
  - **x86-64**: `UNSIGNED, SIGNED, BRANCH, GOT_LOAD, GOT, SUBTRACTOR, SIGNED_1/2/4, TLV`. Scattered relocations are *not* used. The header explains that the assembler emits "almost all" relocations as external, and that a reference to a local label is expressed against the **previous non-local symbol** (or a section ordinal when there is none), with the label's offset carried in the data. `SUBTRACTOR` must be followed by `UNSIGNED` (encodes `A - B`).
  - **arm64**: `UNSIGNED, SUBTRACTOR, BRANCH26, PAGE21, PAGEOFF12, GOT_LOAD_PAGE21, GOT_LOAD_PAGEOFF12, POINTER_TO_GOT, TLVP_LOAD_PAGE21, TLVP_LOAD_PAGEOFF12, ADDEND`. `SUBTRACTOR` must be followed by `UNSIGNED`, and `ADDEND` must be followed by `PAGE21` or `PAGEOFF12` (header comments). `PAGEOFF12` is "offset within page, scaled by `r_length`".
- **Unwind in objects** (SDK `compact_unwind_encoding.h`): compilers can emit standard DWARF FDEs in `__TEXT,__eh_frame`, or compact unwind rows in `__LD,__compact_unwind`. That section is a table with one row per function that needs unwind info and has `S_ATTR_DEBUG` set so older linkers ignore it; the linker consumes it and it never reaches a final executable.

### 6.3 Linker

- Build `MH_EXECUTE`/`MH_DYLIB`/`MH_BUNDLE` images: synthesise `__LINKEDIT` content: symbol and string tables, `LC_DYSYMTAB` (indirect symbol table for stubs and non-lazy pointers: `reserved1` is the index, `reserved2` the stub size), `LC_FUNCTION_STARTS`, `LC_DATA_IN_CODE`, `LC_UUID`, `LC_SOURCE_VERSION`, `LC_BUILD_VERSION`, `LC_MAIN` (replaces `LC_UNIXTHREAD`), `LC_LOAD_DYLIB`/`LC_ID_DYLIB`/`LC_RPATH`, `LC_CODE_SIGNATURE`.
- **Dyld info**: either classic `LC_DYLD_INFO_ONLY` or **chained fixups** `LC_DYLD_CHAINED_FIXUPS` with `LC_DYLD_EXPORTS_TRIE` (both `LC_REQ_DYLD`). `fixup-chains.h` defines chained pointer formats (`DYLD_CHAINED_PTR_ARM64E`, `_64`, `_64_OFFSET`, ...) and imports formats.
- Coalesce `S_COALESCED`/weak definitions; dead-strip per symbol atom when `MH_SUBSECTIONS_VIA_SYMBOLS`; generate lazy-pointer/stub sections; PIE (`MH_PIE`) for executables; two-level namespace (`MH_TWOLEVEL`).
- **Unwind** (SDK header): when creating the final image the linker creates a `__TEXT,__unwind_info` section giving the runtime fast access to unwind info per function: compact encodings are stored in it directly; for functions with DWARF unwind info it holds the offset of the FDE in the final `__TEXT,__eh_frame`. The header notes the linker previously converted some DWARF unwind info to compact form but "that is fragile and no longer done". The binary layout of `__unwind_info` pages was not read in detail.
- **arm64 macOS code signature**: see section 11; Apple's own wording was not located.

### 6.4 DWARF on Mach-O

The headers read do not describe where DWARF lives. `nlist.h` only states that any `N_STAB` bit set marks "a symbolic debugging entry", and `stab.h` exists in the SDK; see section 11.

## 7. PE/COFF (Windows)

### 7.1 Compiler

- **x64 calling convention** (MSVC-x64; Windows-specific, **not** SysV): four register slots; integers in `RCX, RDX, R8, R9`; floats in `XMM0` to `XMM3` by position (one register per position, shared between int and float positions); fifth and later on the stack; caller allocates **32 bytes of shadow space**; arguments not 1/2/4/8 bytes, `__m128`, arrays and strings are passed by pointer to caller memory; 8/16/32/64-bit aggregates are passed as integers; varargs duplicate floating-point values in both integer and XMM slots; return in `RAX` (<= 64 bit scalars and qualifying aggregates) or `XMM0`, otherwise via hidden pointer in `RCX` returned in `RAX`; stack 16-byte aligned except in prologs/epilogs and leaf functions. **Nonvolatile**: `RBX, RBP, RDI, RSI, RSP, R12` to `R15` and `XMM6` to `XMM15`; (APX `R30/R31` per the page).
- **Prologs/epilogs are restricted** so they can be described in unwind data; every function that allocates stack, calls other functions, saves nonvolatile registers or uses exception handling needs unwind data.
- **ARM64 Windows** (MSVC-arm64): follows AAPCS64 for non-variadic calls, with differences: `x18` is the TEB pointer in user mode (KPCR in kernel mode) and is reserved; **frame pointer `x29` is required**, must point to the previous `{x29, x30}` pair, for ETW fast stack walking; variadic functions use general registers only (no SIMD registers) as if composites were stored to an imaginary stack whose first 64 bytes load `x0` to `x7`; `x16`/`x17` volatile.
- **TLS**: PE provides static TLS through the `.tls` section and TLS directory (`__declspec(thread)`), with callbacks.
- The C++ ABI on MSVC targets is MSVC's own, for which no primary specification was located (section 11).

### 7.2 Assembler (COFF object writer)

- COFF file header (20 bytes: Machine, NumberOfSections, TimeDateStamp, PointerToSymbolTable, NumberOfSymbols, SizeOfOptionalHeader (zero for objects), Characteristics). Machine values: `IMAGE_FILE_MACHINE_AMD64` 0x8664, `ARM64` 0xAA64, `ARM64EC` 0xA641. Section headers are 40 bytes; names are 8 bytes, longer names are `/<decimal offset into string table>` and **executable images do not support names longer than 8 characters** (they are truncated when written to an image).
- **Relocations** per machine: x64 `IMAGE_REL_AMD64_ADDR64/ADDR32/ADDR32NB/REL32/REL32_1..5/SECTION/SECREL/...`; ARM64 `IMAGE_REL_ARM64_ADDR32/ADDR32NB/ADDR64`, `BRANCH26` (0x0003), `PAGEBASE_REL21`, `REL21`, `PAGEOFFSET_12A/12L`, `SECREL*`, `BRANCH19/14`, `REL32`.
- **Symbols**: COFF symbol table with auxiliary records (function definitions, `.bf/.ef`, weak externals, file, section definitions); section number values; storage classes.
- **COMDAT** (`IMAGE_SCN_LNK_COMDAT`): selection types `NODUPLICATES=1, ANY=2, SAME_SIZE=3, EXACT_MATCH=4, ASSOCIATIVE=5, LARGEST=6`, given in the section-definition auxiliary record; the first symbol for the section must be the section symbol. This is PE's analogue of ELF `SHT_GROUP`.
- `.drectve` (`IMAGE_SCN_LNK_INFO`): linker options as text; removed by the linker. `.debug$S/$T/$P/$F`: Visual C++ (CodeView) debug sections; the linker turns them into a PDB.
- Exception data in x64 objects: `.pdata` (array of `RUNTIME_FUNCTION { begin RVA, end RVA, unwind-info RVA }`, DWORD aligned, sorted) and `.xdata` (`UNWIND_INFO` with version, flags, prolog size, unwind codes, optional handler or chained info).

### 7.3 Linker

- Lay out an image: MS-DOS stub, `PE\0\0` signature, COFF header, optional header (SectionAlignment default = page size and >= FileAlignment; FileAlignment 512 to 64K power of two, default 512; `SizeOfImage` multiple of SectionAlignment), data directories, section table; **the Windows loader limits the number of sections to 96**; section VAs are ascending and adjacent.
- Build import tables (`.idata`: import directory table, ILT, hint/name table, IAT), export table (`.edata`), delay-load tables, base relocations (`.reloc`; "image files do not contain COFF relocations", they carry base relocations instead), TLS directory and `.tls`, load-config structure, resources (`.rsrc`), debug directory, `.pdata`.
- Process `.drectve` directives, COMDAT selection, weak externals, import-library thunks.
- Authenticode attribute certificate table is image-only and file-offset based.

## 8. DWARF 5

### 8.1 Compiler (producer)

- Emits the DIE tree (`.debug_info`/`.debug_abbrev`), types, location expressions/lists (`.debug_loclists`), ranges (`.debug_rnglists`), line tables (`.debug_line`), macro info, name indices (`.debug_names`), and call frame information. Unit headers carry a 2-byte version (5). `DW_AT_producer` identifies the compiler. Line table header supports `DW_LNCT_MD5` file checksums. 32-bit vs 64-bit DWARF is selectable (initial length `0xffffffff` + 8-byte length marks 64-bit; the two can coexist in one linked object). Register-number and address-class mappings are **target-defined** (supplied by the psABIs in sections 1.4 and 2.5), DWARF itself does not fix them.
- Producer choices: type units / type signatures (sec. 7.32 hash), split DWARF (skeleton unit + `.dwo`), DWARF package files (`.dwp`, `.debug_cu_index`), supplementary object files.

### 8.2 Assembler

- DWARF 5 sec. 7.3.1 states the producer "must emit the relocation information appropriate to the object file format and the target processor architecture" for these references (from the spec's own list): the `debug_abbrev_offset` in each unit header; `DW_FORM_addr`; `DW_OP_addr`; `DW_FORM_sec_offset`; `DW_FORM_ref_addr` (symbolic binding plus relocation); `DW_FORM_strp`; `.debug_addr` and `.debug_aranges` entries; address-bearing `.debug_loclists`/`.debug_rnglists` entries; `DW_LNE_set_address` in `.debug_line`; `.debug_str_offsets` entries (possibly implicit); `debug_info_offset` in `.debug_aranges` and the CU list in `.debug_names`; and `initial_location` of FDEs in `.debug_frame`. Operands of class constant and flag, and `DW_FORM_string` and `DW_FORM_ref1/2/4/8/udata`, need none.
- The object format must be "capable of representing these separate sections" and the cross-section references, with section-relative relocation support (ELF `.debug_*` with section-offset relocations; for COFF/PE see the long-section-name rule in section 7.2).

### 8.3 Linker

- Combine each `.debug_*` section from all inputs, apply the relocations above, and rewrite cross-section offsets so references point into the merged sections. In split-DWARF the second partition (`.debug_info.dwo`, etc.) "may be left in the object files and ignored by the linker"; the first partition (line tables, frame tables, `.debug_addr`, skeleton unit, `.debug_names`, `.debug_aranges`, `.debug_str`) is still processed. This is an explicit design lever to cut link time.
- DWARF 5 defines **`.debug_frame`** only; `.eh_frame` is not mentioned in the DWARF 5 text (zero grep hits). Its format comes from the psABI (x86-64 sec. 6 "Stack Unwind Algorithm": identical to `.debug_frame` with extensions) and from the LSB.
- Chapter 7 details: LEB128, forms, tag/attribute/operation encodings; Appendix B summarises section relationships.

## 9. Cross-cutting matrix (target triple to demands)

This restates the above; nothing here is new evidence.

| Target | Calling convention | C++ ABI | Object/image format | Unwind | Debug info |
|---|---|---|---|---|---|
| Linux x86-64 | SysV psABI | Itanium | ELF (`Elf64_Rela`; GOTPCRELX relaxation) | `.eh_frame` (`SHT_X86_64_UNWIND`), personality + LSDA | DWARF (psABI reg map) |
| Linux AArch64 | AAPCS64 | Itanium (generic AArch64 C++ ABI "CPPABI64", IHI 0059, referenced by AAPCS64's reference list; not read) | ELF (AAELF64; veneers; mapping symbols; BTI/PAC properties) | `.eh_frame` | DWARF (AADWARF64 reg map, RA-sign CFA ops) |
| macOS x86-64 | SysV-derived *(inferred, see section 11)* | Itanium | Mach-O (`X86_64_RELOC_*`) | compact unwind (RBP_FRAME, STACK_IMMD/IND, DWARF) + `__eh_frame` | DWARF in objects/dSYM |
| macOS/iOS arm64 | AAPCS64 + Apple deviations (x18 reserved, fp mandatory, caller extends, `va_list` = `char*`, `long double` = double) | Itanium + Apple departures (C1/D1 return `this`, array cookie, guard `uint64_t`, ...) | Mach-O (`ARM64_RELOC_*`, chained fixups) | compact unwind (FRAMELESS, FRAME, DWARF) | DWARF |
| Windows x64 | Microsoft x64 (shadow space, RCX/RDX/R8/R9) | MSVC (unspecified here) or Itanium in MinGW-style environments *(inferred, no primary source read)* | PE32+/COFF (`IMAGE_REL_AMD64_*`; COMDAT selection types) | `.pdata` + `.xdata` | CodeView/PDB (`.debug$S/$T`); DWARF would have to cope with the PE rule that images do not support section names longer than 8 characters (sec. 7.2) |
| Windows ARM64 | AAPCS64 + Windows deviations (x18 = TEB, fp required, variadics in x regs) | as above | PE32+/COFF (`IMAGE_REL_ARM64_*`) | ARM64 `.pdata`/`.xdata` (not read in detail) | CodeView/PDB |

## 10. What this feeds (observations only, not decisions)

These are facts the downstream tickets will have to take a position on; each is traceable to a section above. They are deliberately phrased as constraints, not recommendations.

- **Target matrix.** Three object formats, three unwind formats, two debug formats, and at least four distinct calling conventions (SysV x86-64, AAPCS64, Apple arm64, Windows x64) plus the Windows arm64 variant. The Apple arm64 and Windows arm64 deviations are small, enumerated lists (sec. 3.1, 7.1) layered on AAPCS64, so one AAPCS64 implementation with per-platform switches covers three targets. Windows x64 is the odd one out (no eightbyte classification, shadow space, `RDI`/`RSI`/`XMM6-15` callee-saved).
- **Pipeline shape.** All three container formats model the same abstractions (sections, symbols, relocations, COMDAT/coalescing, TLS, init arrays), but with different relocation encodings: ELF `Rela` with explicit addends, Mach-O 8-byte `relocation_info` with `SUBTRACTOR`/`ADDEND` pair records and atoms-by-symbol, COFF with per-machine `IMAGE_REL_*` and COMDAT selection kinds. DWARF's own list of relocation-bearing fields (sec. 8.2) is the minimum a "fas" must support in every format. The linker's per-architecture work is dominated by relocation relaxation (x86-64 `GOTPCRELX`), veneers (AArch64 +/-128 MB, IP0/IP1), stubs (Mach-O), and import tables (PE).
- **Performance.** DWARF explicitly designs split-DWARF to keep bulk debug info out of the linker (sec. 8.3). Mach-O's `MH_SUBSECTIONS_VIA_SYMBOLS` makes atom-level dead stripping a header-level contract. x86-64 `GOTPCRELX` relaxation and AArch64 veneer insertion are linker-time costs that depend on code-model choices made by the compiler. Itanium COMDAT rules (vtable and `type_info` emission) determine how much duplicate work the compiler and linker do for C++.
- **Self-hosting (milestone 1).** Stage0 clang/gcc and Forge-built stage1/stage2 only need to agree on the C++ ABI of the platform's system libraries (Itanium on ELF/Mach-O); the Itanium document warns (sec. 1.4) that the standard library is outside the ABI.

## 11. Gaps, unverified claims and follow-ups

Not asserted above as fact, or asserted with the caveat shown:

1. **Mach-O prose specification.** Apple's archived "OS X ABI Mach-O File Format Reference" and the current ld64/dyld sources describe load-command semantics, the `__unwind_info` page layout and where DWARF/dSYM debug info lives; these were not read. Only headers (`loader.h`, `nlist.h`, `reloc.h`, arm64/x86_64 `reloc.h`, SDK `compact_unwind_encoding.h` and `fixup-chains.h`) were.
2. **Darwin x86-64 = SysV psABI.** Not stated in any source read; the Mach-O x86-64 relocation header and SDK unwind modes only show x86-64 is supported. A primary statement (Apple's "Mac OS X ABI Function Call Guide" or the psABI preamble) was not located.
3. **arm64 macOS executables must be code-signed (ad hoc suffices).** Widely cited. The only first-party text found was Apple's Big Sur release notes via secondary quotation; the Apple release-notes JSON endpoints tried did not contain the sentence. LLVM's lld/ld64 behaviour (ad hoc signing by default for arm64) was seen only in search results and is not a specification. Treat as unverified until the primary text is located.
4. **Apple arm64 member function pointer encoding.** Apple lists which 32-bit ARM Itanium variations it adopts; the member-pointer `adj` encoding is not mentioned there, so it is assumed to follow the generic Itanium form *(not stated)*.
5. **Generic AArch64 C++ ABI (CPPABI64, ARM IHI 0059)** and the **AArch64 SysV program property / BTI-PAC ELF notes** are referenced by AAPCS64/AAELF64 but not read.
6. **Windows ARM64 unwind format and PE ARM64 relocation details** are only partially read.
7. **MSVC C++ ABI (name mangling, vftable/RTTI layout, EH tables).** No primary specification found. Per project rules ("understand gcc extensions, MSVC in compat mode") it is out of scope for the map, but anything targeting `*-windows-msvc` ABI compatibility will need a source; the usual substitutes (Clang source, Itanium-style reverse engineering) are not primary.
8. **ELF extensions beyond the 2013 generic draft** (`.gnu.hash`, `DT_RELR`, `GNU_PROPERTY`, `.eh_frame_hdr`, `PT_GNU_EH_FRAME`, relaxation rules) live in "Linux Extensions to gABI" (https://gitlab.com/x86-psABIs/Linux-ABI) and the psABI relaxation sections; not read.
9. **x86-64 TLS models** are in Drepper's "ELF Handling For Thread-Local Storage" (not read); only the relocation names were confirmed from the psABI.
10. **Itanium LSDA format** and `.eh_frame` encoding details (LSB / `libunwind` documentation) not read.
11. DWARF 5 was read as text extracted from the PDF; section numbers cited in the form `sec. 7.3.1` are the document's own. DWARF 6 drafts exist but were not consulted.
