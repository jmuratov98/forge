# IR layers and their boundaries

Forge compiles through four representations below each frontend's AST: **Ingot** (HIR), **Billet** (FIR), **Blank** (MIR), and **Stamp** (MC). There is no SelectionDAG. One lowering pass selects instructions directly from Billet into Blank, the way Cranelift and Go do. Calling conventions are lowered at that same boundary, not in the frontends. SelectionDAG is clang -O2's most expensive pass, LLVM is replacing it, and the whole compile-time budget is 1.25× gcc or clang, so the backend keeps as few layers and passes as -O2 code quality allows.

```
AST ──► Ingot ──► Billet ──► Blank ──► Stamp ──► text assembly / object file
```

- **Ingot**: a typed tree, independent of the source language, with target data layout already resolved. It has no optimization passes, is built one function at a time, and is freed once that function is lowered. It exists to do once what every frontend would otherwise repeat: build the CFG from structured control flow, lower scope cleanups (destructors, `__finally`, `defer`) together with unwind edges, and construct SSA.
- **Ingot → Billet** builds the CFG and SSA directly (Braun et al.), so there is no mem2reg pass. At -O0 every local is a stack slot, so debuggers can read and write it. Above -O0, scalar locals whose address is never taken go straight into SSA.
- **Billet**: SSA with block parameters, shared by every language and target. It depends on the target only through its data layout and through any target intrinsics a module uses (amended by ADR 0011). Calls keep C-level signatures and pass aggregates by value. Calls can carry an unwind successor, and the exception model must cover both Itanium landing pads and MSVC funclets. No language construct reaches Billet; it grows only through intrinsics. Its last pass is a target-aware **legalization** that rewrites types and operations the target lacks (`__int128`, `_BitInt(N)`, 128-bit `long double`, missing vectors) into legal ones, so that lowering only ever sees legal Billet.
- **Billet → Blank** is one pass. It lowers calling conventions (including `va_arg`) from one module per target, and selects instructions by matching patterns over trees of single-use SSA values.
- **Blank**: one target's instructions over virtual registers, in SSA until register allocation. The pipeline is: peepholes, then a pluggable register allocator, then frame layout and prologue/epilogue, then emission to Stamp.
- **Stamp**: encodable instructions, sections, symbols, directives, and fixups. It has no pass pipeline, only assembler work (fixup resolution, relaxation, layout). The compiler and fas's assembly parser both produce it, and inline asm goes through that parser. A text printer and the object writers consume it.

All optimization levels run the same pipeline; -O0 skips passes. Below module-level Billet, each function goes through the backend independently, so code generation can later run in parallel. Billet and Blank have text formats that round-trip, so a single pass can be tested on its own. Ingot has a dump format only. Every node and instruction in every layer carries a source location.

## Considered options

- **LLVM's SelectionDAG path** (Billet → DAG per basic block → Blank): rejected. It adds an IR used only for instruction selection, that IR sees one block at a time, and selection on it costs 18–20% of clang -O2's pass time.
- **GlobalISel shape** (generic Blank, legalized, assigned register banks, and selected in place): rejected. It needs four passes over a machine-level IR, which take about 53% of pass time at AArch64 -O0. Selecting directly from Billet does the same job in one pass.
- **Calling conventions lowered by the frontends**, as Clang does into LLVM IR: rejected. Every frontend would reimplement every target's conventions, and LLVM is now building an ABI library to undo that. Apple's variadic rules fail silently when wrong, so they belong in exactly one module that can be tested.
- **No Ingot, with each AST lowered straight to Billet** through a shared builder, as Clang does: rejected. CFG construction, cleanups, and SSA construction would be written three times, once each for C, C++, and the Forge language. ClangIR's 10–30% slowdown at -O2 is why Ingot runs no passes and lives one function at a time.
- **An -O0 fast path** that bypasses layers, like FastISel or TPDE: rejected for now. Lowering from Billet is already a single pass, and a second backend doubles maintenance. Revisit with measurements if -O0 misses its bound.
- **Phi nodes in Billet**: rejected in favor of block parameters, which avoid phi-placement rules and lost-copy problems.

## Consequences

- Still open: the exception model's detailed design (needed before M7 brings SEH in C), where C++20 coroutines are lowered, the quality register allocator (M5), and how instruction-selection patterns are written.
- Names: FIR also means Flang's Fortran IR, and MIR also means rustc's mid-level IR. The glossary pins down Forge's meanings.
