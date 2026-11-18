# Generating code for arm64 macOS

Research for [issue #6](https://github.com/jmuratov98/forge/issues/6): what a compiler that
emits text assembly for arm64 macOS (`aarch64-apple-darwin`, which clang spells
`arm64-apple-macosx`) must get right when it relies on the system `as` and `ld`.

Scope is Milestone 1's C subset: `int`/`long`/`char` and their unsigned forms, pointers,
arrays, globals, functions, recursion, loops, and calls to externally declared functions such
as variadic `printf`. No structs, floats, or preprocessor. This document reports facts. It
makes no decisions for Forge.

**Environment used for the empirical checks:** macOS 15.6 (24G84) on Apple silicon, Apple clang
17.0.0 (clang-1700.0.13.5), Command Line Tools SDK `MacOSX.sdk` 15.5, `ld` = ld-1167.5 (the
"new linker", also called ld-prime). Lines marked **[verified]** were reproduced on this machine;
the scratch files are not in the repo.

Source keys used below (full links in [Sources](#sources)):

- **[Apple]**: Apple, *Writing ARM64 code for Apple platforms*.
- **[AAPCS64]**: Arm, *Procedure Call Standard for the Arm 64-bit Architecture*, abi-aa @ `9f9e067`.
- **[LLVM]**: llvm-project @ `5f67339` (main, 2026-11-17).
- **[ld(1)] / [as(1)]**: man pages shipped with the Command Line Tools on this machine.

---

## 1. Where Apple's arm64 ABI departs from AAPCS64

Apple says its platforms "adhere to the rest of the 64-bit ARM specification" apart from a
short list of differences [Apple]. The ones that touch the Milestone 1 subset:

### 1.1 Variadic arguments go on the stack, every one of them

- **AAPCS64:** anonymous (variadic) arguments are assigned exactly like named ones, first to
  `x0`–`x7`/`v0`–`v7`, then to the stack. `va_list` is a five-field struct (`__stack`,
  `__gr_top`, `__vr_top`, `__gr_offs`, `__vr_offs`) that walks the register save areas and the
  stack [AAPCS64 §"va_list", lines 2963, 3447].
- **Apple:** named arguments use the normal rules, but "for each variadic argument" it goes to
  "the appropriate number of 8-byte stack slots". So `va_list` is just `char *` [Apple,
  "Update code that passes arguments to variadic functions"]. LLVM encodes this as
  `CC_AArch64_DarwinPCS_VarArg`: `i8`/`i16`/`i32` are promoted to `i64`, and then
  "Everything is on the stack", one 8-byte slot each (16-byte aligned slots for 128-bit
  values) [LLVM `AArch64CallingConvention.td` L459-L481]. clang selects
  `CharPtrBuiltinVaList` for Darwin AArch64 [LLVM `clang/lib/Basic/Targets/AArch64.cpp` L2016].
- **Consequence for a call to `printf(fmt, a, b)`:** `fmt` (named) goes in `x0`; `a` is stored
  at `[sp]` and `b` at `[sp, #8]` *at the call*. The caller must have reserved that outgoing
  area, keeping `sp` 16-byte aligned.

  **[verified]** clang for `printf("%d %d\n", 1, g)`:

  ```asm
  ; arm64-apple-macos, -O1
  	mov	w9, #1
  	stp	x9, x8, [sp]          ; both varargs in 8-byte stack slots
  	adrp	x0, l_.str@PAGE
  	add	x0, x0, l_.str@PAGEOFF
  	bl	_printf
  ```

  For `--target=aarch64-linux-gnu`, the same source puts the varargs in `w1` and `w2` (and
  tail-calls `printf`).

  **[verified]** A hand-written `.s` that passes the vararg in `x1` (Linux style) assembles and
  links with no diagnostic, and `printf("value=%d\n")` prints garbage (`value=1871523744`).
  Putting the value in `[sp]` prints `value=42`. Nothing in the toolchain catches this mistake.
- **What counts as variadic:** only the arguments matching `...`. Calling a function through
  a prototype that lacks the `...` (or an unprototyped declaration) uses the non-variadic
  convention. Fixed arguments of a variadic function (e.g. `fmt`) still use registers.
- **Defining variadic functions** (not in Milestone 1): `va_start` yields a `char *` to the
  first anonymous stack slot. There is no register save area to spill.

### 1.2 Stack-passed arguments are packed, not 8-byte slots

Only relevant once a call has more than 8 integer/pointer arguments.

- **AAPCS64:** each stacked argument takes at least 8 bytes. NSAA is rounded up to a multiple
  of 8, and small integers occupy a full 8-byte slot [AAPCS64 rules C.14-C.17, lines
  2066-2082, and "NSAA will have a minimum alignment of 8", line 2103].
- **Apple:** "Function arguments may consume slots on the stack that are not multiples of 8
  bytes." Each takes its natural size and alignment. The total is padded so the stack stays
  aligned [Apple, "Pass arguments to functions correctly"]. LLVM: "Stack slots are sized as
  needed rather than being at least 64-bit". `i8` goes to `CCAssignToStack<1, 1>`, `i16` to
  `<2, 2>`, `i32` to `<4, 4>`, and `i64`/pointers to `<8, 8>` [LLVM
  `AArch64CallingConvention.td` L377-L457].
- **[verified]** For `long big(long×8, char i, char j, int k)`, clang stores `i` at `[sp]`
  (`strb`), `j` at `[sp, #1]` (`strb`), and `k` at `[sp, #4]` (`str w`).
- **Note:** this applies to *named* arguments only. Variadic arguments are never packed
  (§1.1).

### 1.3 The caller extends sub-`int` arguments

- **AAPCS64:** "When an argument is assigned to a register any unused bits in the register have
  unspecified value", so the callee must extend [AAPCS64 line 1997, and line 2097 for
  padding].
- **Apple:** "The caller of a function is responsible for signing or zero-extending any argument
  with fewer than 32 bits" [Apple]. LLVM: `CCIfType<[i1, i8, i16], CCPromoteToType<i32>>` in
  `CC_AArch64_DarwinPCS` [LLVM `AArch64CallingConvention.td`].
- **[verified]** Passing a `char` to `int f(char, unsigned char, short)`: the caller does
  `ldursb w0, …` (sign-extend), `mov w1, #200` (zero-extended), `mov w2, #-5`.
- The guarantee covers 32 bits only. Bits 32-63 of an `int` argument are not specified by
  either ABI. A callee that wants an `int` as a 64-bit value (for example, to index with it)
  extends it itself: clang emits `ldrsw`/`sxtw`.

### 1.4 `x18` is reserved

- **AAPCS64:** `r18` is "the Platform Register, if needed; otherwise a Caller-saved register"
  [AAPCS64 register table, line 849].
- **Apple:** "The platforms reserve register `x18`. Don't use this register." [Apple]. LLVM
  reserves it by default for Darwin (`isX18ReservedByDefault` returns true for
  `TT.isOSDarwin()`) [LLVM `AArch64TargetParser.cpp` L146; `AArch64Subtarget.cpp` L328].
- The register allocator's pool therefore excludes x18, as well as x29 (FP), x30 (LR) and
  sp/xzr (register 31).

### 1.5 `char` is signed

- **AAPCS64:** `char` maps to "unsigned byte" [AAPCS64 line 2792].
- **Apple:** "The `char` type is a signed type." [Apple]. clang's `isSignedCharDefault` returns
  true for AArch64 only when the triple is Darwin or Windows [LLVM
  `clang/lib/Driver/ToolChains/Clang.cpp` L1213].
- **[verified]** `clang -dM -E` does not define `__CHAR_UNSIGNED__`. A `char` load is
  `ldrsb`, and an `unsigned char` load is `ldrb`.

### 1.6 `long double` is `double`

- **AAPCS64:** quad precision (128-bit IEEE 754) [AAPCS64 line 2828].
- **Apple:** "identical to the `double` type" [Apple]. clang:
  `LongDoubleWidth = LongDoubleAlign = SuitableAlign = 64` and `IEEEdouble` [LLVM
  `clang/lib/Basic/Targets/AArch64.cpp` L1967].
- **[verified]** `__SIZEOF_LONG_DOUBLE__ == 8`. This only matters once floats arrive.

### 1.7 Other departures (outside Milestone 1, listed so they aren't lost)

- **Odd-register start for 16-byte-aligned arguments.** Apple allows such an argument to begin
  in an odd `xN` register. AAPCS64 rounds NGRN up to even [Apple; AAPCS64 line 2046].
- **Empty structs** may be ignored as parameters [Apple].
- **`int64_t` is `long long`**, not `long` (`Int64Type = SignedLongLong`) [LLVM clang
  `AArch64.cpp` L1960]. **[verified]** `__INT64_TYPE__` is `long long int`. This matters for
  C++ mangling and `PRId64`, not for code generation.
- **C++ ABI differences** (`va_list` mangles as `Pc`, constructors return `this`, and others)
  [Apple, "Handle C++ differences"].

### 1.8 Things that are the same as AAPCS64 (stated because they are easy to get wrong)

- **Data model is LP64.** Sizes and alignments: `char` 1, `short` 2, `int` 4, `long` 8,
  `long long` 8, pointer 8 [Apple table; **[verified]** `__SIZEOF_LONG__`/`__SIZEOF_POINTER__`
  are 8]. `wchar_t` is a signed 32-bit type [Apple].
- **Argument and result registers:** `x0`–`x7` carry the first 8 integer/pointer arguments,
  and `x0` (`w0` for 32-bit) holds the result. `x8` is the indirect-result register,
  `x9`–`x15` are caller-saved temporaries, and `x19`–`x28` are callee-saved. `x29` is FP and
  `x30` is LR [AAPCS64 register table, lines 838-860]. LLVM's Darwin callee-saved set is LR,
  FP, X19-X28 and D8-D15 [LLVM `AArch64CallingConvention.td` L755].
- **`x16`/`x17` (IP0/IP1) can be clobbered between any `bl` and its target**, by linker
  veneers or stubs [AAPCS64 §"Use of IP0 and IP1 by the linker", line 1250]. **[verified]**
  ld's `__stubs` entry for `_printf` is `adrp x16, …; ldr x16, [x16]; br x16`.
- **SP must be 16-byte aligned** ("SP mod 16 = 0") [AAPCS64 line 1216; Apple].
  **[verified]** The hardware enforces this. A function that does `sub sp, sp, #8` followed by
  `str xzr, [sp]` dies with SIGBUS (exit status 138). Every adjustment of `sp` must therefore
  keep it a multiple of 16, not just the adjustments made at call sites.

### 1.9 Frame pointer and frame records

- **AAPCS64:** a frame record is two 64-bit words, `[FP] = caller's FP` and
  `[FP+8] = LR`. FP points to the innermost record, and the chain ends with 0. A platform
  chooses how strictly FP must be maintained [AAPCS64 lines 1228-1236].
- **Apple:** "The frame pointer register (`x29`) must always address a valid frame record. Some
  functions — such as leaf functions or tail calls — may opt not to create an entry in this
  list." [Apple]. Apple clang passes `-mframe-pointer=non-leaf` by default (**[verified]**
  `clang -###`). LLVM's Darwin layout puts the frame record "at the top of the callee-save
  area" [LLVM `AArch64CallingConvention.td` L754].
- **[verified]** clang's -O0 shape for a non-leaf function:

  ```asm
  	sub	sp, sp, #32
  	stp	x29, x30, [sp, #16]
  	add	x29, sp, #16          ; x29 -> {old x29, x30}
  	…
  	ldp	x29, x30, [sp, #16]
  	add	sp, sp, #32
  	ret
  ```

  The pre-indexed form `stp x29, x30, [sp, #-16]!; mov x29, sp` is equivalent and also valid.

### 1.10 Red zone

- **Apple:** the 128 bytes below `sp` are not modified during exceptions, and user code "can
  potentially make use of the space" [Apple, "Respect the stack's red zone"].
- **LLVM does not use it by default.** The `aarch64-redzone` option defaults to `false`, and
  `canUseRedZone` returns false unless it is set [LLVM `AArch64Options.td` L58;
  `AArch64FrameLowering.cpp` L516]. So clang's output never relies on it. Using it is permitted,
  not required.

---

## 2. Mach-O assembly syntax (what Apple's `as` accepts)

**`as` is clang.** On this machine `/Library/Developer/CommandLineTools/usr/bin/as` is a
303-byte zsh script that strips `-q`/`-Q` and runs `clang -x assembler -c "$@"`.
**[verified]**. as(1) states: "The `as` command is deprecated. It is now calls clang to use
clang's 'intergated assembler'." So "the system assembler" means LLVM's integrated assembler
with the Darwin AArch64 `MCAsmInfo` [LLVM `AArch64MCAsmInfo.cpp` L134; `MCAsmInfoDarwin.cpp`].
`clang -c foo.s` is equivalent.

### 2.1 Symbols and labels

| Kind | Spelling | Notes |
|---|---|---|
| C identifier `foo` | `_foo` | Mach-O mangling: "Private symbols get L prefix. Other symbols get a _ prefix." (data layout `m:o`) [LangRef]. **[verified]** datalayout `e-m:o-…`, `__USER_LABEL_PREFIX__` is `_`. Calls to libc also need it: `bl _printf`. |
| Exported symbol | `.globl _foo` | The entry point `_main` must be `.globl`. A file-`static` symbol simply omits `.globl` (it becomes a non-external symbol, `nm` lowercase letter). |
| Assembler-temporary label | `L…` (e.g. `LBB0_1`, `Lfmt`) | `InternalSymbolPrefix = "L"` [LLVM `AArch64MCAsmInfo.cpp` L142]. Normally absent from the object's symbol table. **[verified]** `LBB*` labels do not appear in `nm`, but an `L` label referenced by an `adrp`/`add` relocation into `__cstring` *does* appear as a non-external symbol (`s Lfmt`). Harmless. |
| Linker-private label | `l…` (e.g. `l_.str`) | `LinkerPrivateGlobalPrefix = "l"` [LLVM `MCAsmInfoDarwin.cpp` L63]. The symbol stays in the `.o` so ld can split sections into atoms at it, then ld drops it from the output. clang uses this for string literals. |
| Numeric local label | `1:` … `b 1f` / `b 1b` | **[verified]** accepted. |

### 2.2 Lexical details that differ from ELF/GNU AArch64 assembly

- **`;` starts a comment**, it is *not* a statement separator (`CommentString = ";"`). The
  statement separator is `%%` (`SeparatorString = "%%"`) [LLVM `AArch64MCAsmInfo.cpp`
  L143-L144]. `//` and `/* */` comments also work. **[verified]** `mov w0,#1 ; add w0,w0,#2`
  assembles to only the `mov`.
- **Relocation operators are `@`-suffixes**, not ELF's `:lo12:` prefixes (`UseAtForSpecifier =
  false`, `MachOAtSpecifiers`) [LLVM `AArch64MCAsmInfo.cpp` L44, L153-L154]:
  - `adrp xN, _sym@PAGE` and `add xN, xN, _sym@PAGEOFF`: the address of a symbol defined in
    this link unit.
  - `adrp xN, _sym@PAGE` and `ldr/str wM, [xN, _sym@PAGEOFF]`: direct load or store.
  - `adrp xN, _sym@GOTPAGE` and `ldr xN, [xN, _sym@GOTPAGEOFF]`: load the symbol's *address*
    from the GOT, then dereference it.
- **Alignment directives take log2.** `AlignmentIsInBytes = false`, so `.align 2` means 4
  bytes. clang emits `.p2align 2` for functions and `.p2align 2, 0x0` for an `int`.
  `.comm sym,size,log2align` is also log2 (`COMMDirectiveAlignmentIsInBytes = false`) [LLVM
  `MCAsmInfoDarwin.cpp` L67-L68].
- **No `.type`/`.size`** (`HasDotTypeDotSizeDirective = false`) [LLVM `MCAsmInfoDarwin.cpp`
  L84].
- **Immediates:** `mov` takes only immediates encodable as a single `movz`/`movn`/`orr`.
  **[verified]** `mov x0, #0x12345678` is rejected ("expected compatible register or logical
  immediate"). Wider constants need `movz` followed by `movk …, lsl #16/32/48`.

### 2.3 `@PAGEOFF` with `ldr`/`str`: the offset is scaled, and ld-prime does not check it

The `ldr`/`str` unsigned-offset form encodes `imm12 × access size`. So `@PAGEOFF` used inside a
4-byte `ldr w` is only correct if the target symbol's address is 4-byte aligned. An 8-byte
`ldr x` needs 8-byte alignment, and so on.

**[verified, surprising]** A 4-byte `ldr w0, [x8, _v@PAGEOFF]` against `_v` placed at an odd
address (after a 1-byte `_pad`):

- The default linker (ld-1167.5 / ld-prime) **links with no diagnostic**. It silently
  truncates the offset (`ldr w0, [x8]`), and the program returns the neighbouring byte (`1`
  instead of `7`).
- `-ld_classic` refuses with `32-bit LDR/STR not 4-byte aligned: from _main … to _v`.
- `-fatal_warnings` does not help, because ld-prime issues no warning.

The emitter therefore has to align every global to at least the width of the access used on
it, or use `adrp` + `add …@PAGEOFF` and then a register-indirect load. clang emits
`.p2align 2` before an `int` global and `.p2align 3` before a pointer.

### 2.4 Sections clang uses for the Milestone 1 subset

**[verified]** All of the following come from `clang -S -O0`:

| Content | Directive |
|---|---|
| Code | `.section __TEXT,__text,regular,pure_instructions` |
| String literals | `.section __TEXT,__cstring,cstring_literals` + `l_.str: .asciz "…"` |
| Read-only initialized data (`static const int k[3]`) | `.section __TEXT,__const` |
| Initialized writable globals (`int g = 5;`, `int *gp = &x;`) | `.section __DATA,__data`. Pointers are `.quad _sym` (ld emits a rebase/fixup for them). |
| Zero-initialized `static` | `.zerofill __DATA,__bss,_zs,4,2` (segment, section, symbol, size, log2 align) |
| Explicitly zero-initialized external (`int zi = 0;`) | `.globl _zi` + `.zerofill __DATA,__common,_zi,4,2` |
| Tentative definition (`int arr[10];`) | `.comm _arr,40,2` because Apple clang passes **`-fcommon`** by default (**[verified]** in `clang -###`). With `-fno-common`, it becomes `.zerofill __DATA,__common,…` like above. |

### 2.5 How code addresses data and functions

**[verified]** clang emits:

- **Global defined in this TU** (`_g`, `static _sg`): `adrp x8, _g@PAGE` + `ldr w8, [x8, _g@PAGEOFF]`.
- **`extern` data not defined in this TU, and `.comm` symbols** (`_arr`, `_ext`): via the GOT,
  `adrp x9, _arr@GOTPAGE` + `ldr x9, [x9, _arr@GOTPAGEOFF]`, then a load through `x9`. clang
  uses the GOT for common symbols because another object may provide the real definition.
  ld relaxes GOT loads to direct `adrp`/`add` when the target ends up in the same image.
  **[verified]** In the linked `t.c` binary, the `_arr@GOTPAGE` + `ldr` pair became
  `adrp x9, …; add x9, x9, #0x14`.
- **String literal address:** `adrp x0, l_.str@PAGE` + `add x0, x0, l_.str@PAGEOFF`.
- **Calls, local or external:** plain `bl _name`. For a symbol defined in a dylib (`_printf`),
  ld synthesizes a `__TEXT,__stubs` entry and a `__got` slot. The compiler emits nothing extra.
  **[verified]** in the linked binary: `bl 0x100000494 ; symbol stub for: _printf`.
- All code is PIC (`-mrelocation-model pic -pic-level 2`); macOS arm64 executables are PIE.
  No absolute-address instruction sequences are used.

### 2.6 Directives clang emits that are optional for a working program

**[verified]** A file containing only `.globl _main / _main: mov w0,#0 / ret`, with no
`.section`, `.p2align`, `.build_version`, CFI, or `.subsections_via_symbols`, assembles, links,
and runs. What each one does:

- **`.build_version macos, 15, 0 sdk_version 15, 5`** writes `LC_BUILD_VERSION` into the
  `.o`. Without it, `as` (clang) uses the triple's default deployment target. **[verified]**
  The object got `minos 15.0, sdk n/a`, and the link and run still worked.
- **`.subsections_via_symbols`** tells ld it may split sections into atoms at each symbol, for
  dead-stripping and reordering (`HasSubsectionsViaSymbols = true` [LLVM
  `MCAsmInfoDarwin.cpp` L65]). With it, code must never fall through from one global symbol
  into the next.
- **`.cfi_startproc` / `.cfi_def_cfa` / `.cfi_offset` / `.cfi_endproc`** feed ld's
  compact-unwind (`__unwind_info`) generation. They are needed for C++ exceptions and unwinders
  that do not follow the frame-pointer chain. `-fno-unwind-tables -fno-asynchronous-unwind-tables`
  removes them from clang's output.
- **`.loh AdrpAdd …` / `Lloh0:`** labels are linker optimization hints (at -O1+), purely
  optional.
- **`.p2align 2` before functions:** instructions are 4 bytes, and the default `__text`
  alignment already satisfies this, but clang states it explicitly.

---

## 3. How the clang driver invokes `as` and `ld`

### 3.1 Compile and assemble

**[verified]** `clang -### hello.c -o hello`:

- clang runs `clang -cc1 -triple arm64-apple-macosx15.0.0 … -emit-obj`, which uses the
  *integrated* assembler, so no separate `as` process starts. Notable cc1 flags:
  `-target-abi darwinpcs`, `-mframe-pointer=non-leaf`, `-mrelocation-model pic`, `-fcommon`,
  `-stack-protector 1`, `-fstack-check`, `-target-cpu apple-m1`,
  `-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk`, `-target-sdk-version=15.5`.
- `clang -c foo.s` runs `clang -cc1as -triple arm64-apple-macosx15.0.0 … -filetype obj`.
- `-fno-integrated-as` runs `/Library/Developer/CommandLineTools/usr/bin/as -Q -arch arm64 -o foo.o foo.s`,
  which is the clang wrapper script from §2.

So invoking `as -arch arm64 -o foo.o foo.s` is equivalent to `clang -c -arch arm64 foo.s -o foo.o`.

### 3.2 Link

**[verified]** The `ld` line from `clang -### hello.c -o hello`:

```
/Library/Developer/CommandLineTools/usr/bin/ld -demangle -lto_library …/libLTO.dylib
  -no_deduplicate -dynamic -arch arm64 -platform_version macos 15.0.0 15.5
  -syslibroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
  -mllvm -enable-linkonceodr-outlining -o hello -L/usr/local/lib hello-1e5df6.o
  -lSystem /Library/Developer/CommandLineTools/usr/lib/clang/17/lib/darwin/libclang_rt.osx.a
```

What matters:

- **`-lSystem` is mandatory.** libSystem provides libc (printf), dyld glue, and the stack-check
  helpers. The driver always adds it for non-DriverKit targets [LLVM
  `clang/lib/Driver/ToolChains/Darwin.cpp` L1887]. **[verified]** Without it: `Undefined
  symbols … "_printf"`.
- **`-syslibroot <SDK>` (or `-L<SDK>/usr/lib`) is mandatory**, because macOS has no
  `/usr/lib/libSystem.dylib` on disk. The libraries live in the dyld shared cache, and the
  linker reads text stubs (`<SDK>/usr/lib/libSystem.tbd`, `libSystem.B.tbd`). **[verified]**
  `ld -o h hello.o -lSystem` with no syslibroot fails: `library 'System' not found`. Either
  `-syslibroot "$(xcrun --show-sdk-path)"` or `-L"$(xcrun --show-sdk-path)/usr/lib"` works.
  The driver derives `-syslibroot` from `--sysroot`, `-isysroot`, or the default sysroot
  [Darwin.cpp L210]. It honours the `SDKROOT` environment variable as a default `-isysroot`
  [Darwin.cpp L2660]. On this machine `SDKROOT` was unset, yet clang still found the CLT SDK.
- **Finding the SDK:** `xcrun --show-sdk-path` prints
  `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk`, and `xcrun --show-sdk-version` prints
  `15.5` **[verified]**. With full Xcode the path is under `Xcode.app`. Hard-coding a path is
  fragile.
- **`-platform_version macos <min> <sdk>`** sets `LC_BUILD_VERSION` in the output (ld(1)
  "-platform_version platform min_version sdk_version"). The driver emits it from the
  deployment target (`-mmacosx-version-min`, `MACOSX_DEPLOYMENT_TARGET`, or SDK/host default)
  [Darwin.cpp L3892]. **[verified]** Optional: when omitted, ld takes the platform and minimum
  version from the input objects' `LC_BUILD_VERSION` and still records the SDK version.
- **`-arch arm64`**: optional on an arm64 host (inferred from the objects) **[verified]**.
- **Entry point:** ld emits `LC_MAIN` pointing at `_main`. No `crt1.o` is linked.
  **[verified]** `otool -l` shows `LC_MAIN` and `LC_LOAD_DYLIB /usr/lib/libSystem.B.dylib`.
  ld(1)'s `-e` text still mentions `start` in `crt1.o`, which is out of date for this
  configuration.
- **`libclang_rt.osx.a`** (compiler-rt builtins) is not needed for the Milestone 1 subset.
  **[verified]** The manual link without it runs. It would matter for helpers like `__muloti4`.
- `-demangle`, `-no_deduplicate`, `-lto_library`, `-mllvm …`, and `-L/usr/local/lib` are
  conveniences or optimizations, not requirements.

**[verified] Minimal working sequence:**

```sh
as -arch arm64 -o hello.o hello.s          # == clang -c hello.s
ld -o hello hello.o -lSystem -syslibroot "$(xcrun --show-sdk-path)"
./hello
```

Alternatively, `clang hello.o -o hello` lets the driver build the ld line.

### 3.3 Code signing

- **Apple silicon refuses to run unsigned arm64 code.** **[verified]** Linking with
  `-no_adhoc_codesign` produces a binary that is SIGKILLed at launch (exit status 137).
- **ld signs automatically.** ld(1): "-adhoc_codesign … The default for Apple Silicon
  binaries is to be ad-hoc codesigned." **[verified]** `codesign -dv` on the manual link shows
  `flags=0x20002(adhoc,linker-signed)`, `Signature=adhoc`. No separate `codesign` step is
  needed with the system ld.
- A binary modified after linking (e.g. patched or stripped by a tool that does not re-sign)
  needs `codesign -s - <file>`. Forge's own future linker (fold) will need to emit an ad-hoc
  `LC_CODE_SIGNATURE` itself. This is noted only because the glossary names fold. It is
  outside this ticket's question.

### 3.4 Which `ld`

Since Xcode 15, the default is a rewritten linker ("ld-prime"). The release notes say: "A new
linker has been written to significantly speed up static linking. It's the default for all
macOS, iOS, tvOS and visionOS binaries … The classic linker can still be explicitly requested
using -ld64, and will be removed in a future release" [Xcode 15 release notes]. The same notes
spell the flag `-Wl,-ld_classic` in their workarounds, and that is the spelling the installed `ld` accepts.
**[verified]** `ld -v` reports `PROJECT:ld-1167.5`. `-ld_classic` still works but warns that it
is deprecated. The classic linker lives at `/Library/Developer/CommandLineTools/usr/bin/ld-classic`.
The behavioural difference found in §2.3 (no alignment check on scaled `@PAGEOFF`) is between
these two.

---

## 4. Reading `clang -S` output as a reference

**[verified]** These invocations produce reference assembly on this machine:

```sh
clang -S -O0 foo.c -o foo.s                         # exactly what the default driver would assemble
clang -S -O0 -fno-unwind-tables -fno-asynchronous-unwind-tables \
      -fno-stack-protector -fno-stack-check -fno-common foo.c -o -   # strips CFI, canaries, chkstk, .comm
clang -S -O1 …                                      # shorter, register-allocated code; adds .loh hints
clang --target=aarch64-linux-gnu -S …               # contrast against plain AAPCS64/ELF
clang -S -emit-llvm foo.c -o -                      # see datalayout/triple and ABI-lowered IR signatures
clang -### foo.c                                    # see the cc1 / as / ld command lines
otool -tv foo.o ; otool -l a.out ; nm -m foo.o ; otool -r foo.o   # disassembly, load commands, symbols, relocations
```

What the default output contains that is *driver policy, not ABI*:

- **Stack protector** (`-stack-protector 1`, the default). Functions with arrays load
  `___stack_chk_guard` via GOT, store a canary at `[x29, #-8]`, compare on exit, and call
  `___stack_chk_fail` on mismatch.
- **Stack probing** (`-fstack-check`, the default). A frame larger than one page (4096 bytes)
  first calls `___chkstk_darwin` with the size in `x9`, through `x16`, and only then
  decrements `sp`. **[verified]** For a 5000-byte local array: `mov w9, #5024; adrp x16,
  ___chkstk_darwin@GOTPAGE; …; blr x16; sub sp, sp, #1, lsl #12; sub sp, sp, #928`. Without
  probing, a large frame can skip the stack guard page.
- **`-fcommon`** turns tentative definitions into `.comm` (see §2.4).
- **CFI directives** (see §2.6).

How to read the `-O0` output:

- **Prologue** `sub sp`, `stp x29, x30`, `add x29`. Locals are addressed off `x29` (`stur/ldur
  [x29, #-N]`, unscaled, for negative offsets) or off `sp` (`str/ldr [sp, #N]`, scaled
  positive offsets).
- **Basic blocks** are `LBB<func>_<n>:` labels. Comments such as `; %bb.0:`,
  `; =>This Inner Loop Header` and `; 4-byte Folded Spill` are annotations only.
- **Integer widths:** `w` registers for 32-bit (`int`, `unsigned`), `x` for 64-bit (`long`,
  pointers). Writing a `w` register zeroes bits 32-63.
- **Loads by type:** `ldrsb`/`ldrb` for `char`/`unsigned char`, `ldrsh`/`ldrh` for
  `short`/`unsigned short`, `ldr w` for `int`, `ldrsw` to load an `int` sign-extended to 64
  bits, and `ldr x` for `long` and pointers.
- **Array indexing:** `ldr w9, [x8, x9, lsl #2]` uses a scaled register offset for `int`
  elements, after `ldrsw x9` sign-extends the index.
- **Comparisons and branches:** `subs`/`cmp` followed by `b.gt`, `b.ge`, `b.ne`, and so on.
  Signed conditions are `lt/le/gt/ge`; unsigned ones are `lo/ls/hi/hs`.
- **Recursion** needs nothing special beyond the frame record and saving live values across
  `bl` (clang -O0 spills them to the frame).

---

## 5. Checklist distilled from the above (facts, not decisions)

A Milestone 1 emitter for `arm64-apple-macosx` that links with the system tools has to:

1. Prefix every C-level symbol with `_`. Use `L`/`l` (or numeric) labels for internal ones.
2. Pass named args in `w0`–`w7`/`x0`–`x7` and further named args packed on the stack at
   natural alignment. Pass **every variadic arg in its own 8-byte stack slot** starting at
   `[sp]`.
3. Sign- or zero-extend `char`/`short` arguments to 32 bits in the caller. Treat plain `char`
   as signed.
4. Never touch `x18`. Assume `x16`/`x17` and all of `x0`–`x15` are clobbered by any call.
   Preserve `x19`–`x28` (and `d8`–`d15` later).
5. Keep `sp` 16-byte aligned at every instruction (the hardware faults otherwise). Maintain a
   valid frame record in `x29` for every non-leaf function.
6. Address globals with `adrp`+`@PAGE`/`@PAGEOFF`, and `extern`/common data with
   `@GOTPAGE`/`@GOTPAGEOFF`. Align each global to at least its load width, because ld-prime
   will not catch a misaligned scaled `@PAGEOFF`.
7. Use `;` or `//` for comments, never `;` as a separator. Use log2 alignment directives and
   Mach-O `segment,section` names.
8. Link with `ld … -lSystem -syslibroot $(xcrun --show-sdk-path)` (or let `clang` drive ld).
   ld ad-hoc signs the output automatically.

---

## 6. Open points not resolved here

- Exact behaviour of `ld` when objects carry *different* `LC_BUILD_VERSION` minimums, or none
  at all mixed with some, was not tested.
- Whether ld-prime diagnoses misaligned `@PAGEOFF` for 8-byte `ldr x` or `ldrh` was not tested.
  Only the 32-bit case was checked (§2.3).
- How ld behaves with an `.s` that omits `.subsections_via_symbols` combined with
  `-dead_strip` (likely: the whole section is one atom) was not tested.
- Apple's documentation text was read via the developer.apple.com JSON endpoint for the page.
  The Apple page's code examples (figures) were not extracted. The prose was.

---

## Sources

- **[Apple]** Apple Developer Documentation, *Writing ARM64 code for Apple platforms*.
  <https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms>
  (read via `https://developer.apple.com/tutorials/data/documentation/xcode/writing-arm64-code-for-apple-platforms.json`, 2026-11-17).
- **[AAPCS64]** Arm, *Procedure Call Standard for the Arm 64-bit Architecture (AArch64)*,
  ARM-software/abi-aa @ `9f9e067e6c6a5d3c5c8326756500cdbd940b8ff7`.
  <https://github.com/ARM-software/abi-aa/blob/9f9e067e6c6a5d3c5c8326756500cdbd940b8ff7/aapcs64/aapcs64.rst>
  The line numbers cited refer to this revision of the `.rst`.
- **[LLVM]** llvm/llvm-project @ `5f673392019e3a4b05bf7208e5f9345f52baf3f3`:
  - `llvm/lib/Target/AArch64/AArch64CallingConvention.td` (L377-L481 `CC_AArch64_DarwinPCS`, `CC_AArch64_DarwinPCS_VarArg`; L754-L757 `CSR_Darwin_AArch64_AAPCS`)
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/Target/AArch64/AArch64CallingConvention.td#L377-L481>
  - `llvm/lib/TargetParser/AArch64TargetParser.cpp` L146 `isX18ReservedByDefault`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/TargetParser/AArch64TargetParser.cpp#L146-L149>
  - `llvm/lib/Target/AArch64/AArch64Subtarget.cpp` L328
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/Target/AArch64/AArch64Subtarget.cpp#L328-L329>
  - `llvm/lib/Target/AArch64/AArch64Options.td` L58 (`aarch64-redzone` default false); `AArch64FrameLowering.cpp` L516 `canUseRedZone`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/Target/AArch64/AArch64Options.td#L58-L59>
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/Target/AArch64/AArch64FrameLowering.cpp#L516-L541>
  - `llvm/lib/Target/AArch64/MCTargetDesc/AArch64MCAsmInfo.cpp` L134-L155 `AArch64MCAsmInfoDarwin`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/Target/AArch64/MCTargetDesc/AArch64MCAsmInfo.cpp#L134-L155>
  - `llvm/lib/MC/MCAsmInfoDarwin.cpp` L63-L88
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/llvm/lib/MC/MCAsmInfoDarwin.cpp#L63-L88>
  - `clang/lib/Basic/Targets/AArch64.cpp` L1957-L1979 `DarwinAArch64TargetInfo`, L2016 `getBuiltinVaListKind`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/clang/lib/Basic/Targets/AArch64.cpp#L1957-L2018>
  - `clang/lib/Driver/ToolChains/Clang.cpp` L1213 `isSignedCharDefault`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/clang/lib/Driver/ToolChains/Clang.cpp#L1213-L1228>
  - `clang/lib/Driver/ToolChains/Darwin.cpp` L210 `AddMachOSysLibRoot`, L1887 `-lSystem`, L2660 `SDKROOT`, L3892 `addPlatformVersionArgs`
    <https://github.com/llvm/llvm-project/blob/5f673392019e3a4b05bf7208e5f9345f52baf3f3/clang/lib/Driver/ToolChains/Darwin.cpp#L210-L227>
- **[LangRef]** LLVM Language Reference, *Data Layout*, `m:o` mangling.
  <https://llvm.org/docs/LangRef.html#data-layout>
- **[ld(1)]**, **[as(1)]**: man pages from Command Line Tools (ld-1167.5), sections
  `-syslibroot`, `-platform_version`, `-adhoc_codesign`, `-no_adhoc_codesign`, `-e`.
- **[Xcode 15 release notes]** "Linking" section (new linker, `-ld_classic`).
  <https://developer.apple.com/documentation/xcode-release-notes/xcode-15-release-notes>
