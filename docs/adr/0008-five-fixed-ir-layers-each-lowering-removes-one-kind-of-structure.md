# Five fixed IR layers, each lowering removes one kind of structure

Forge compiles through five fixed IR layers, AST → HIR → FIR → MIR → MCIR, from the first slice on, with none skipped or merged while the compiler is small. Each layer is a concrete set of C++ types, not an extensible dialect (ADR 0001), and each lowering removes one named kind of structure. Skipping FIR would force SSA construction into MIR, or a non-SSA MIR that rules out SSA-based register allocators; merging MIR into MCIR would lose the seam fas reuses (ADR 0007). A thin layer is affordable because each lowering is one linear pass over dense arrays.

| Lowering | Removes |
|---|---|
| AST → HIR | the source language's syntax and implicit rules (names resolved, conversions explicit) |
| HIR → FIR | structured control flow and mutable variables: FIR is an SSA CFG with block arguments, built directly by Braun et al.'s algorithm |
| FIR → MIR | target independence: target instructions over virtual registers, still SSA |
| MIR register allocation and frame lowering | SSA and virtual registers |
| MIR → MCIR | the CFG and the alias opcodes: linear, labelled instructions in their base forms, and data, in an object module |

## Considered Options

- **Skip FIR until optimizations exist.** Rejected: building FIR with Braun is cheap, and without it MIR would have to construct SSA itself or give up SSA.
- **Fuse MIR and MCIR** (as TPDE and Cranelift do). Rejected: MCIR is the assembly printer's input and fas's seam.

## Consequences

- SSA starts at HIR → FIR and ends at register allocation. Nothing above FIR is SSA, and nothing after allocation is.
- Every layer has a printer and a verifier, and every node or instruction in every layer carries a source location.
- A per-layer ticket that adds structure to its layer has to say which lowering removes it.
