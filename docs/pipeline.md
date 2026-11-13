# Pipeline shape and component boundaries

Status: draft, 2026-11-13. Stable-name prefix: `[pipe]`.

## 1 Scope [pipe.scope]

1 This document specifies how Forge's components are packaged and connected: libraries versus processes, the driver, the compiler executables, the interfaces between compiler, assembler and linker, and the shared object-file code. The seams it defines are tabulated in [roadmap.seams].

## 2 Shape [pipe.shape]

1 Every component shall be a library under a thin `main`. All state shall live in a per-compile context. There shall be no global options and no mutable static registries.

2 The toolchain shall still run as separate processes, so the libraries stay reusable by the linter, the formatter, the debugger and any later in-process use.

## 3 Executables [pipe.exe]

1 The executables are GCC- and binutils-style:

- (1.1) `fcc` is the driver. `f++` is a second name for the same binary; `argv[0]` picks the default language.
- (1.2) `fcc1` (C) and `fcc1plus` (C++) are compiler executables, installed in `libexec/forge/<version>/`. The driver spawns them, and users never run them. The split is a packaging split and, per [front.shape], a code split: `fcc1` links only the C frontend and `fcc1plus` only the C++ frontend.
- (1.3) `fas` and `fold` are separate executables, built when their milestone arrives ([roadmap.fog]).
- (1.4) The binary utilities are `ar`, `nm`, `objdump`, `objcopy`, `strip`, a readelf equivalent and a symbolizer. Each is a thin executable over the shared object readers and the ISA module. When each arrives is left to the fully-self-hosted ordering ([roadmap.fog]).

2 Every Forge executable shall use the diagnostics engine and take `--explain=<id>` ([diag.docs]).

## 4 Driver and jobs [pipe.driver]

1 The driver shall spawn one compiler job per translation unit. It shall never compile in process.

2 *One option language.* A compile job's command line uses the driver's own flag spellings, fully resolved: an explicit `--target`, every include directory and macro, and the output path. One option table defines both sides ([compat.tracking]). The public driver rejects the few internal-only flags.

3 `-###` shall print the jobs. Pasting a printed job line shall reproduce the job.

4 `-E`, and the preprocessing rerun of [pipe.crash], run in the compiler executable. There is no separate `cpp` executable.

5 The driver spawns whichever linker `-fuse-ld` names: GNU `ld` in milestones 1 and 2, `fold` once it exists.

## 5 Crash reproducer [pipe.crash]

1 When a compiler job dies by a signal or an internal-error exit, the driver shall rerun that job's preprocessing. It shall write the preprocessed source and the job line to a temp directory, and print their paths after the compiler's own stack trace and crash context. `-fno-crash-diagnostics` turns this off.

2 The crash report's first line is specified in [diag.crash].

## 6 Host toolchain discovery [pipe.layout]

1 The driver shall discover the host toolchain with a small table of layouts for each supported target, relative to `--sysroot`. A layout locates the GCC installation (libgcc, `crtbegin`, and libstdc++ headers for the bootstrap), glibc's crt files, `as` and `ld`. `--gcc-install-dir` and `-B` override it.

2 For milestone 1 the table has one entry: Ubuntu 26.04 multiarch on aarch64.

## 7 Resource headers [pipe.resource]

1 Forge shall ship its own headers in `libexec/forge/<version>/include/`: `stddef.h`, `stdarg.h`, `stdint.h`, `float.h`, `limits.h`, `stdatomic.h`, `unwind.h`, and intrinsic headers such as `arm_neon.h` when a target needs them.

2 They are searched after the `-I` directories. GCC's private include directory shall never be searched. Any extension that the header inventories found only in that directory is Forge's to choose, not GCC's to dictate.

## 8 Emission [pipe.emit]

1 Codegen shall write to an in-memory *machine-code stream* of sections, labels, instructions, data and directives. The stream has two adapters, the *assembly printer* and the *object writer*. Later, `fas`'s assembler parser feeds the same stream.

2 Milestone 1 ships only the assembly printer, and the driver spawns GNU `as`. Inline asm, asm labels and top-level asm pass through as text, so milestone 1 needs no assembler parser.

3 The object writer arrives with `fas`. From then on:

- (3.1) the compilers write objects in process and parse inline asm through `fas`'s parser library;
- (3.2) the printer-plus-external-assembler path stays, for `-S` and `-fno-integrated-as`;
- (3.3) GNU `as` becomes the oracle: for any translation unit, Forge's object shall match the object GNU `as` builds from the printed text.

4 No temp-file path may reach an object file, so stages and reruns compare byte for byte.

5 Branch relaxation is done by Forge, not by the external assembler ([codegen.pipeline]).

## 9 Object-file code [pipe.objects]

1 Per-format definitions and zero-copy *object readers* (ELF now; Mach-O and COFF later) are shared by `fold`, the binary utilities and the debugger. There is no format-neutral model for reading.

2 One format-neutral object writer (sections, fragments, fixups and symbols, then a per-format serializer) is shared by the compiler and `fas`. ELF is its only serializer, so its format seam stays hypothetical until a non-ELF target arrives.

3 `fold` has one linking core per format and writes its output itself, not through the object writer.

## 10 Targets [pipe.targets]

1 One build shall carry every target, picked at run time with `--target`, each behind one *target interface*. A build option can leave targets out. Milestone 1 has one adapter, aarch64, so this retargeting seam stays hypothetical until the second target.

2 The target owns C ABI classification, through the *ABI interface* ([targets.abi.strategy]). The ABI interface is called by the shared HIR → FIR lowering ([ir.lowering]).

3 One ISA description per target is generated into one *ISA module*: encoding, decoding, assembly syntax and operand constraints. Codegen, `fas`, `fold`'s veneers and relaxation, and the disassembler all use it. Milestone 1 uses its printer, encoder and decoder ([codegen.isa]).

## 11 Linking [pipe.link]

1 Files on disk are the only input to the linker: ELF objects and archives. LTO adds a second path later ([roadmap.fog]).

2 In-memory handoff to `fold`, and incremental relinking, are in the fog rather than out of scope.

## Annex A (informative): Rationale and departures [pipe.rationale]

1 *Libraries without mutable globals.* This departs from LLVM, whose `cl::opt` globals and statics make reuse inside a process and threading fragile. It also departs from GCC, whose globals put libgccjit behind one lock.

2 *One option language.* This departs from clang's separate `-cc1` language (`-triple` against `--target`), which is a second interface to keep in sync.

3 *Host toolchain discovery.* This departs from clang's `GCCInstallationDetector`, which guesses across every distro's layout; Forge lists only the layouts of the targets it supports.

4 *Resource headers.* GCC's headers are written against GCC's internal builtins and change with each GCC release. Owning the headers ties them to the builtins Forge actually implements. Not searching GCC's private directory matches clang.

5 *Object-file code.* BFD showed that a format-neutral model for reading is lossy and slow, and lld dropped its format-neutral atom model for one port per format.

6 *Targets.* One build carrying every target avoids GCC's separate cross-toolchain build per target. A frontend-side ABI would depart from clang, where each frontend reimplements the C ABI in its own codegen, and from Rust, Zig and Swift, which each copy it.

7 *ISA module.* LLVM's TableGen-backed MC works this way; GCC and binutils maintain the `.md` patterns and the opcode tables separately.

## Annex B (informative): Provenance [pipe.prov]

1 [Pipeline shape and component boundaries](https://github.com/jmuratov98/forge/issues/4), refined by [IR design](https://github.com/jmuratov98/forge/issues/5) (the shared lowering calls the ABI interface), [Frontend strategy](https://github.com/jmuratov98/forge/issues/6) (no separate `cpp`; code split) and [Diagnostics model, formats and fix-its](https://github.com/jmuratov98/forge/issues/14) (crash report).
