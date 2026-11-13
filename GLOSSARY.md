# Forge

A toolchain of C and C++ compilers, an assembler, a linker and their supporting libraries, built to bootstrap itself and to replace GCC 15.2 as a drop-in. This glossary fixes the vocabulary used by the architecture roadmap in `docs/roadmap.md`.

## Toolchain shape

**Driver**:
The `fcc`/`f++` program users run. It plans jobs and spawns them.
_Avoid_: front end, compiler (when the whole program is meant)

**Job**:
One spawned tool run (compile, assemble or link) with a fully resolved command line.
_Avoid_: invocation, step

**Compiler executable**:
`fcc1` or `fcc1plus`: the program that runs one compile job. Users never run it directly.
_Avoid_: cc1, compiler proper

**Reproducer**:
The preprocessed source and job line the driver writes when a compiler job crashes.
_Avoid_: crash dump

**Resource headers**:
The compiler-owned headers shipped next to the compiler executables, such as `stddef.h` and `stdarg.h`.
_Avoid_: builtin headers, GCC's private headers

**Layout table**:
The driver's per-target list of where the host toolchain's pieces live.
_Avoid_: toolchain detector

**Machine-code stream**:
The ordered sections, labels, instructions, data and directives that codegen or the assembler's parser hands to an emission adapter.

**Assembly printer**:
The machine-code stream's adapter that writes assembly text.

**Object writer**:
The machine-code stream's adapter that writes an object file directly.

**Object reader**:
A per-format zero-copy view of an object file or archive.

**Target module**:
Everything one target supplies behind the target interface.

**ISA module**:
A target's generated instruction knowledge: encode, decode, print and parse.

**ABI interface**:
The target's calling-convention classifier. It takes a type description and says where each piece is passed.
_Avoid_: calling-convention lowering

**Seam**:
A boundary with an interface that is real only once a second adapter exists behind it.

**Stage0, stage1, stage2, stage3**:
The successive builds of Forge in a bootstrap. Stage0 is built by GCC or clang; stage1 is stage0 compiling Forge; each later stage is the previous one compiling Forge again.

## Languages and frontends

**Frontend**:
One language's parser, AST, sema and AST → HIR emitter. `fcc1` holds the C frontend; `fcc1plus` holds the C++ one.
_Avoid_: front end, compiler

**C-family core**:
The library both frontends share above the preprocessor: the feature table, keyword sets, builtin, attribute and pragma tables, the type system with C layout, constant arithmetic and format checking.

**Dialect**:
A language, a revision and a GNU-mode flag, as `-std=` selects them.
_Avoid_: standard, mode

**Revision**:
One published standard, such as C17 or C++20.

**Dialect feature**:
A named language rule that the feature table turns on or off for a dialect.

**Feature table**:
The one table that maps each dialect to its features, its version macros and its extension warnings.

**Extension warning**:
The diagnostic for using a later revision's feature in an earlier dialect.

**Not-yet-supported error**:
The diagnostic for a feature, flag or extension that is enabled or listed but not implemented. It names the feature.
_Avoid_: sorry, unimplemented

**Not-planned error**:
The diagnostic for a flag or extension that Forge does not intend to support. It names the row, as the not-yet-supported error does.

**C23 baseline**:
The C23 rules milestone 1 implements so that a default `gnu23` compile works: the keywords that alias C11 spellings, `bool`/`true`/`false`, `()` meaning `(void)`, and the reservation of the other C23 keywords.

**Body arena**:
The arena that holds one function body's AST, freed once its HIR is emitted.

## Intermediate representations

**HIR**:
The language-independent, structured tree that every frontend emits. It is the frontend-to-IR seam.

**FIR (Forge IR)**:
The target-independent instruction set in SSA form with block parameters, holding only scalar types. The optimizer works on it.

**MIR (machine IR)**:
The ISA module's instructions plus generic pseudos. It is in SSA over virtual registers until allocation, then over physical registers.

**Shared lowering**:
The one HIR → FIR translation that every frontend reuses.

**Block parameter**:
A value that a block receives from every branch into it. It takes the place of a phi instruction.

**Poison**:
The value an operation yields when one of its undefined-behaviour flags is violated.

**Handle**:
A 32-bit index naming an entity in its function's arena or in a module table.

## Code generation

**Generic pseudo**:
One of MIR's fixed, target-independent non-instructions, such as copy, call, spill or inline asm.

**Target pseudo**:
A target-specific MIR instruction whose expansion the ISA description declares.

**ISA description**:
A target's `.isa` files, written in Forge's fixed-schema language. The generator turns them into the ISA module.

**Operand kind**:
A description entry that says how an operand is written in assembly, encoded in bits, and constrained.

**Selection rule**:
A declarative rewrite from a FIR pattern to MIR instructions, in a target's `.isel` file.

**Rules compiler**:
The part of the generator that turns rule files into a matcher, checking overlap and totality.

**Local allocator**:
The `-O0` register allocator. It works one block at a time and gives every cross-block value a stack slot.

**Decoupled allocator**:
The optimized register allocator, which spills until pressure fits, then assigns and coalesces in SSA.

**Allocation checker**:
The symbolic checker that proves an allocation preserved its input's values.

**Frame lowering**:
The pass that lays out the stack frame and writes the prologue and epilogue.

**Branch relaxation**:
Rewriting out-of-range branches into in-range sequences.

**AARCHMRS**:
Arm's machine-readable architecture specification, from which Forge imports the aarch64 ISA description.

## Optimizer

**Pass**:
A named transformation over FIR or MIR that runs as one table entry.

**Pipeline table**:
The fixed list of passes for one `-O` level.

**Flag map**:
The committed table from GCC optimization flags to Forge passes. It defines each `-O` level.

**Analysis**:
A derived fact about a function or module, such as def-use or dominators, which the pass manager caches and invalidates.

**Def-use analysis**:
The use-lists, built on demand for the passes that need them.

**Preserved set**:
The bitmask of analyses that a pass reports as still valid after it runs.

**Simplifier**:
The `simplify` pass and its `fir.simplify` rules.

**Memory SSA**:
The on-demand analysis that orders a function's memory operations into versions.

**Phase**:
One of the four stages of a module's optimization above `-O0`.

**FIR interpreter**:
The reference executor for FIR, used as the optimizer's test oracle.

**Shrink-wrapping**:
Placing the prologue and epilogue only on the paths that need a frame.

## Drop-in compatibility

**Drop-in**:
Accepting upstream GCC 15.2's command lines and source, and behaving as it does, with PIE by default.
_Avoid_: compatible, GCC-like

**Compatibility table**:
One of the two committed tables, flags or extensions, that generate the option parser and the core's tables.

**Row status**:
A table row's state: implemented, ignored, not-yet-supported, not-planned or unknown.

**Ignored**:
Accepted with no effect. Allowed only when the output stays correct.

**Tier**:
A row's priority, P0 to P3.

**Drop-in corpus**:
The pinned project list that the non-gating nightly builds to measure demand for P2 rows.

## Diagnostics

**Diagnostic**:
One message from any Forge executable, with an ID, a level, a primary location and optional notes and fix-its.
_Avoid_: error message, warning (as the generic term)

**Diagnostic ID**:
The global, unprefixed, kebab-case name of one diagnostic, such as `unused-variable`.

**Catalog**:
The merged set of per-component diagnostic tables. It is the single source for the enum, tests, docs pages and `--explain`.

**Diagnostics engine**:
The library that takes structured diagnostics and hands them to sinks. It holds no compiler state.

**Sink**:
An output adapter of the diagnostics engine: GCC text, forge text, SARIF, `-verify`, or an in-memory IDE sink.

**Style**:
The text layout a sink prints: `gcc` (GCC 15.2's layout, the default) or `forge` (rustc-like).

**Permerror**:
A diagnostic that is an error unless `-fpermissive` or `-Wno-error=X` is given.

**Pedwarn**:
A diagnostic that is a warning, which `-pedantic-errors` turns into an error.

## Performance and verification

**Budget**:
The ceiling on a cost ratio (geomean 1.2×, single benchmark 1.5×) for one metric at one `-O` level.

**Cost ratio**:
Forge's cost divided by the reference compiler's cost on one benchmark.

**Reference compiler**:
A compiler from the pinned image that Forge is measured against: GCC 15.2, or clang once `fas` lands.

**Budget suite**:
The fixed set of benchmarks a budget is computed over.

**Gate**:
A budget or check whose breach fails CI or blocks a milestone.

**Report**:
A budget or check that is only published, never blocking.

**Header sweep**:
The gate that compiles each installed glibc header alone and requires `fcc` to accept every one GCC accepts.

**Expected-error skip**:
A skip-list entry that must stop with the not-yet-supported or not-planned error naming its feature.
_Avoid_: XFAIL

**Repeatability check**:
The determinism gate that compiles the same translation unit twice, from different directories, and requires identical output.

**Host-independence check**:
The determinism gate that compares the output of `fcc` built by GCC with that of `fcc` built by clang.

**ABI interop check**:
Generated tests that link Forge-built and GCC-built objects across one call boundary.
