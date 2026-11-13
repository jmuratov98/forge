# Targets, ABI strategy and the bootstrap host

Status: draft, 2026-11-13. Stable-name prefix: `[targets]`.

## 1 Scope [targets.scope]

1 This document specifies the platforms Forge targets in milestones 1 and 2, the ABIs it implements there, the strategy by which a target owns ABI classification, and the host that runs the bootstrap. The rollout of later targets is in the fog ([roadmap.fog]).

## 2 The milestone-1 target [targets.m1]

1 Milestone 1 covers one triple, used as both host and target: `aarch64-unknown-linux-gnu`. There is no second target; milestone 1 is host only. The second target comes after the optimizer ([roadmap.later]).

2 The target is:

- (2.1) AArch64, base ISA ARMv8.0-A;
- (2.2) little-endian, LP64, hard-float with AdvSIMD always present, unsigned `char`, small code model;
- (2.3) ELF64 relocatable objects with AArch64 ELF relocations;
- (2.4) glibc and libgcc, with the crt files linked in; libstdc++ from milestone 2.

3 `-march` and `-mcpu` select the `FEAT_` gating imported from Arm's specification ([codegen.isa.aarch64]). Codegen emits only what the selected architecture allows, and stays ARMv8.0 by default, which is correct on every later CPU.

## 3 Atomics [targets.atomics]

1 Atomics shall be lowered as GCC's `-moutline-atomics` does. Plain atomic loads and stores are inline `ldar` and `stlr`. Read-modify-write operations and compare-and-exchange call libgcc's `__aarch64_*` helpers, which pick LSE at run time.

2 Milestone 1 encodes no LL/SC loops and no LSE instructions. `-mno-outline-atomics` is a not-yet-supported error until the inline LL/SC pseudos of [codegen.mir] land.

## 4 Output [targets.output]

1 The output is a PIE executable linked by GNU `ld`. Forge's own libraries link statically into the executables, and glibc and libstdc++ load dynamically (Ubuntu GCC's defaults). No shared objects are built.

2 `-fPIC` and `-fpic` code generation is nonetheless delivered in milestone 1 ([compat.pic]). `-shared`, `-static` and `-static-pie` stay not-yet-supported. `-fvisibility` is ignored, because going through the GOT is always correct.

## 5 ABIs [targets.abi]

1 Forge implements, for aarch64 Linux:

- (1.1) *AAPCS64* in full, including HFA and HVA arguments and defining variadic functions with the struct `va_list`;
- (1.2) the *Linux AArch64 psABI*;
- (1.3) from milestone 2, the *Itanium C++ ABI with ARM's AArch64 deviations*: mangling, object layout, vtables, and static-init guards (guard variables, array cookies, the member-function-pointer virtual bit).

2 *TLS.* A program's own TLS in a PIE executable is local-exec: Forge accesses it through `tpidr_el0` plus an offset. Under `-fPIC` and `-fpic`, TLS uses TLS descriptors (`TLSDESC`), the aarch64 general-dynamic model.

3 Every function keeps an `x29`/`x30` frame record at `-O0`, so backtraces work without unwind tables. At `-O1` and above, shrink-wrapping places the frame record only on the paths that need a frame ([opt.layout]).

## 6 ABI strategy [targets.abi.strategy]

1 The target shall own C ABI classification, through the *ABI interface* that the shared HIR → FIR lowering calls ([ir.lowering]). A frontend describes a type in HIR (size, alignment, fields, and the "non-trivial for calls" bit); the target says where each piece is passed.

2 FIR shall only see signatures that have been through the ABI: explicit indirect-result pointers, register-sized pieces and `va_arg` sequences.

3 A record marked non-trivial for calls is passed by address. On AArch64 the indirect result goes in `x8`.

4 The ABI interface classifies a complex value as a two-member homogeneous aggregate ([m1.types]).

5 Each later target brings its own ABI behind the same interface. Milestone 1 has one adapter, so the interface stays a hypothetical seam until the second target ([roadmap.seams]).

6 The C ABI is checked by the ABI interop check of [m1.gates].

## 7 The bootstrap host [targets.bootstrap]

1 The host is Ubuntu 26.04 LTS: GCC 15.2, glibc 2.43, binutils 2.46. Its libstdc++ and glibc headers, under `-std=c++20`, are the header surface milestone 2 must parse.

2 One container image, pinned by digest, runs in a Lima VM on the developer's Apple Silicon Mac and on GitHub's `ubuntu-26.04-arm` runners. It is refreshed only deliberately, so an upstream package update cannot break a check without a Forge change.

3 The bootstrap check of [roadmap.m2] runs here: stage0 built twice, by the image's GCC 15.2 and by its clang; the two stage1s byte-identical; stage1 equal to stage2 byte for byte across every object file and linked executable, built from identical source paths so `__FILE__` and similar macros match.

## 8 Milestone 2 target items [targets.m2]

1 The bootstrap needs, beyond milestone 1:

- (1.1) the Itanium C++ ABI of [targets.abi];
- (1.2) libstdc++ and the C++20 header surface of the bootstrap host;
- (1.3) `-fno-exceptions` and `-fno-rtti` for Forge's own build, so no `.eh_frame`, no LSDA, no personality routine and no typeinfo are emitted;
- (1.4) `thread_local` only on trivially constructed and destroyed types, so there are no TLS wrapper or init functions and no `__cxa_thread_atexit`, and Forge's own PIE build uses local-exec TLS, not the TLS descriptors that `-fPIC` brings ([targets.abi]);
- (1.5) no debug info: no DWARF, and the bootstrap stages build without `-g`.

2 The extension names that the C++20 header surface reaches are inventoried on `research/host-header-extensions` (Annex C). Of 670 names, 201 must be implemented, 226 may lower to a libc or libm call and 52 may be ignored.

## Annex A (informative): Rationale and departures [targets.rationale]

1 *Why aarch64 Linux first.* Compilers traditionally bootstrap first on x86-64 Linux. aarch64 Linux was chosen for four reasons:

- (1.1) it runs at native speed on the developer's M4 inside a VM, and GitHub's arm64 runners are free for public repositories;
- (1.2) ELF is the best-documented and simplest of the three object formats;
- (1.3) AArch64's fixed-width encoding, 31 general registers and lack of fixed-register instructions make the simplest first backend;
- (1.4) glibc and libstdc++ headers put GCC extensions first, which matches the GCC drop-in goal.

2 macOS was rejected for three reasons: Mach-O is thinly documented, the SDK and libc++ need Clang extensions first, and code signing is mandatory.

3 *Why two stage0 compilers.* Building stage0 with both GCC and clang, and requiring identical stage1s, catches undefined behaviour and evaluation-order dependence in Forge. It is a cheap form of diverse double-compiling. Milestone 1 runs the `.s` form of the check ([m1.gates]).

4 *Why the exclusions held for Forge's own source.* Forge folds target constants with its own software arithmetic, so its source needs no `long double` or `__int128` lowering. Those exclusions were justified by Forge's own source and were re-decided for C in milestone 1 ([m1.types]).

## Annex B (informative): ABI and format research [targets.research]

1 `research/abi-format-inventory` (40790c6) splits what the compiler, assembler and linker each must do, per specification. It covers SysV x86-64, AAPCS64, Apple arm64, the Itanium C++ ABI, ELF, Mach-O, PE/COFF and DWARF 5, with a target matrix. A few facts that bear on later targets:

- (1.1) Darwin x86-64 uses the SysV calling conventions; Apple arm64 departs from AAPCS64 (reserved `x18`, caller-extended arguments under 32 bits, `va_list` as `char*`, `long double` as `double`) and from the generic AArch64 C++ ABI (C1/D1 return `this`, a fixed array cookie, `uint64_t` guards).
- (1.2) Windows x64 is not SysV (shadow space, `RCX`/`RDX`/`R8`/`R9`).
- (1.3) Microsoft does not publish a C++ ABI specification; the best available sources are Clang's Microsoft ABI code and Visual Studio's `ehdata.h` and `rttidata.h`.
- (1.4) Apple removed its Mach-O prose reference; the headers are normative.

2 Known unknowns are listed in section 11 of the findings: the arm64 code-signing citation, MSVC vftable/RTTI/EH layouts, `.gnu.hash` and `DT_RELR`, the Itanium LSDA layout, DWARF location in Mach-O builds, the x86-64 TLSDESC RFC, Windows ARM64 unwind opcodes, and Apple's member-function-pointer encoding. None blocks milestone 1.

## Annex C (informative): Provenance [targets.prov]

1 [Milestone-1 target matrix](https://github.com/jmuratov98/forge/issues/2) (with its 2026-11-10 comment redrawing the milestones); [ABI and object-format inventory](https://github.com/jmuratov98/forge/issues/3) (`research/abi-format-inventory`, 40790c6); [Host header extension inventory](https://github.com/jmuratov98/forge/issues/9) (`research/host-header-extensions`, 7c6166f, GCC not run); [Pipeline shape and component boundaries](https://github.com/jmuratov98/forge/issues/4) and [IR design](https://github.com/jmuratov98/forge/issues/5) (ABI interface); [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10) and [Drop-in compatibility surface](https://github.com/jmuratov98/forge/issues/8) (changes to the target matrix).
