# Intermediate representations

Status: draft, 2026-11-13. Stable-name prefix: `[ir]`.

## 1 Scope [ir.scope]

1 This document specifies Forge's three intermediate representations (HIR, FIR and MIR), the shared lowering between the first two, their in-memory layout and their text forms. MIR's internals are in [codegen.mir]; the passes that run on FIR are in [opt].

## 2 Levels [ir.levels]

1 There shall be three IR levels, followed by the machine-code stream of [pipe.emit]:

- (1.1) *HIR*: the language-independent structured tree that every frontend emits;
- (1.2) *FIR*: the target-independent SSA instruction set the optimizer works on;
- (1.3) *MIR*: target instructions over virtual and then physical registers.

2 *One pipeline at every optimization level.* Every compile runs AST → HIR → FIR → MIR → stream. At `-O0` the optimization pipeline is empty except for the `always_inline` inliner ([opt.module]), and the register allocator is the local allocator ([codegen.regalloc]). There is one instruction selector and no selection-DAG level.

## 3 HIR [ir.hir]

1 HIR is the frontend → IR seam. C, C++ and, later, the forge language all emit it. A frontend shall emit only HIR that has passed semantic checking. No passes run on HIR in milestone 1; later high-level passes, such as devirtualization or coroutine elision, may run on it.

2 HIR is a structured tree. It holds:

- (2.1) types: integers with their signedness, floats, pointers, records and unions with fields and bitfields, arrays and functions;
- (2.2) named variables and expression trees;
- (2.3) structured control flow, with `goto` and labels as an escape hatch;
- (2.4) scopes with cleanups;
- (2.5) globals with their initializers.

3 HIR has no C++ concepts. The C++ frontend owns the Itanium C++ ABI: layout, vtables, virtual calls, mangling and static-init guards. It lowers them into plain HIR records, globals and indirect calls. A language-neutral virtual-call or object notion shall be added only when a high-level pass needs one.

4 HIR record types carry the "non-trivial for calls" bit, which the C++ frontend sets ([targets.abi.strategy]).

5 HIR is lowered and freed one function at a time ([ir.layout]).

## 4 The shared lowering [ir.lowering]

1 One HIR → FIR lowering shall serve every frontend. It does the hard parts once.

2 *ABI classification.* The lowering calls the target's ABI interface ([targets.abi.strategy]). Frontends do not call it. The optimizer then cleans up the coercion code, which protects runtime speed.

3 *SSA construction.* The lowering builds SSA directly, with Braun et al.'s on-the-fly algorithm ("Simple and Efficient Construction of Static Single Assignment Form", 2013):

- (3.1) at `-O1` and above, scalars whose address is never taken become SSA values while lowering;
- (3.2) at `-O0`, every variable gets a stack slot, so each has a memory home as debuggers expect;
- (3.3) aggregates and address-taken variables always go to memory.

4 The lowering also does short-circuit operators, `switch`, cleanups on every scope exit, aggregate copies and bitfield access.

5 *Types that FIR lacks.* `_Complex` is split into scalar pairs ([m1.types]). If a dialect enables `_BitInt`, it expands into multi-word operations or library calls here; until it is implemented it raises the not-yet-supported error ([m1.dialect]).

6 `-fwrapv` and `-fno-strict-overflow` make the lowering omit `nsw` ([opt.flags]).

## 5 FIR [ir.fir]

### 5.1 Form and types [ir.fir.types]

1 FIR is SSA with *block parameters*, not phi instructions. A branch passes arguments to its target block the way a call does.

2 FIR types are scalars only:

- (2.1) signless `i8`, `i16`, `i32` and `i64`, and `i128`;
- (2.2) `f32`, `f64` and `f128`;
- (2.3) one opaque `ptr`, with addressing by `ptr + offset`;
- (2.4) vectors, later ([roadmap.fog]).

3 There are no aggregate types. Aggregates exist only as memory with a size and an alignment.

4 `i128` and `f128` are in FIR because milestone 1 keeps `__int128` and binary128 `long double` ([m1.types]).

### 5.2 Undefined behaviour [ir.fir.ub]

1 Undefined behaviour is modelled with poison only. A flagged operation (`nsw`, `nuw`, `exact`) yields poison when its flag is violated. Branching on poison is undefined behaviour, and `freeze` stops it propagating. There is no `undef`.

### 5.3 Other FIR rules [ir.fir.misc]

1 Each FIR module is bound to one target. The frontend has already fixed sizes and offsets. The instruction set itself is target-independent, and target-specific operations are intrinsics supplied by the target module.

2 Atomics are FIR operations with C11 orderings: load, store, read-modify-write, compare-and-exchange and fence. The outline-atomics lowering of [targets.atomics] happens in FIR → MIR.

3 Inline asm passes through FIR and MIR as text plus constraints.

4 Constants are folded with Forge's own software arithmetic.

5 Floating-point mode is per function ([opt.flags]).

## 6 Layout and lifetime [ir.layout]

1 *Arenas and handles.* Each function's blocks, instructions and values shall sit in dense tables, with operands kept in a side pool. They are named by 32-bit index *handles*. Types and constants are interned once per module, in append-only tables. Freeing a function resets its arena. A handle can only be resolved through the function that owns it.

2 *No persistent use-lists.* Def-use is an analysis that the pass manager builds in one scan and drops when a pass invalidates it ([opt.analyses]). The lowering and `-O0` never pay for it.

3 *Function at a time.* The frontend lowers each function's HIR to FIR as soon as that function is checked, then frees the HIR. FIR functions share only the append-only module tables, so optimizing and generating code per function could later run on threads. Milestone 1 is single-threaded, and the budget credits no in-job threads ([perf.measure.threads]).

4 *Source locations.* Every HIR node and every FIR and MIR instruction carries a 32-bit source-location id, for backend diagnostics now and for DWARF later.

## 7 Text forms and tools [ir.text]

1 HIR, FIR and MIR shall each have a printer, a parser that round-trips, and a verifier. The shared lowering can therefore be tested from `.hir` text without any frontend. Pass tests run on `.fir` and `.mir` text through FileCheck and the `--update` flow.

2 The compiler executables read IR text. They read `.hir`, `.fir` and `.mir` inputs through `-x`. Internal-only flags stop at, or start from, a named pass ([opt.manager]). There are no separate `opt` or `llc` tools with their own option language.

3 A binary FIR format is deferred to the LTO fog ([roadmap.fog]). The AST has a dump printer but no parser ([front.ast]).

## Annex A (informative): Rationale and departures [ir.rationale]

1 *One pipeline, no selection DAG.* This departs from LLVM, which keeps three instruction selectors (FastISel, SelectionDAG, GlobalISel), and whose FastISel falls back to SelectionDAG for anything it cannot handle. LLVM built GlobalISel because its per-block DAG is slow and cannot see across blocks.

2 *Three levels.* The user chose the third level, HIR, over a two-level proposal. HIR matches GCC's GENERIC → GIMPLE → RTL shape, not ClangIR's: GENERIC is a language-independent tree that every frontend targets, whereas ClangIR adds a C/C++-specific dialect.

3 *SSA in the lowering.* This departs from LLVM, whose frontends always emit `alloca`s that `mem2reg` then removes. That round trip creates memory traffic only to delete it.

4 *Block parameters.* As in Cranelift, MLIR and Swift SIL. They avoid phi ordering rules, the duplicate phi entries a `switch` needs when two edges reach the same block, and the lost-copy and swap problems when leaving SSA, which becomes plain copies on edges.

5 *Scalar-only types.* Byte-offset addressing is where LLVM itself is heading with `ptradd`.

6 *Poison only.* LLVM's `undef` has been a long-running source of miscompiles (Lee et al., "Taming Undefined Behavior in LLVM", PLDI 2017), and LLVM is removing it.

7 *Arenas.* This departs from LLVM, whose pointer-linked `Instruction` and `Use` objects take a lot of memory and get chased through the cache. Cranelift, Zig's AIR and Carbon's SemIR use dense index tables.

8 *No persistent use-lists.* This departs from LLVM and MLIR, which update use-lists on every operand edit, even at `-O0`.

9 *Function at a time.* GCC and clang are single-threaded per translation unit, and their global state makes that hard to change.

10 *Text tools.* This departs from LLVM's separate tools, for the same reason the pipeline rejected `-cc1`.

## Annex B (informative): Provenance [ir.prov]

1 [IR design](https://github.com/jmuratov98/forge/issues/5); refined by [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10) (`i128`, `f128`, `_Complex`, `_BitInt`), [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11) and [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12) (`-O0` runs one pass; per-function floating-point mode).
