# MIR terminators keep their edges, and MIR → MCIR picks the branch form

Every MIR block ends in one terminator (`b`, `b_cond`, `cbz`, `cbnz` or `ret`), and a terminator names its successors as edges, as in FIR: `b` has one, the conditional terminators a taken edge and a not-taken edge, and before register allocation each edge carries its block arguments. A block doesn't record which successor falls through. MIR → MCIR knows the layout and chooses the branch form: `b.cc T` when the not-taken block follows, the inverted condition aimed at the other target when the taken block follows, `b.cc T` then `b F` when neither does, and a `b` to the next block is dropped. Register allocation adds blocks on critical edges and the layout can change, so no pass has to repair a terminator when it does, and the structural check "each block ends in exactly one terminator" ([docs/ir-data-layout.md](../ir-data-layout.md#verification)) holds in MIR as it does in FIR.

## Considered Options

- **Exposed fall-through, as LLVM's MIR has it:** a block ends in `b.cond T` followed by `b F`, a terminator sequence. Every pass that changes the layout has to fix the pair, and without a cleanup pass redundant branches stay. Clang's own `-O0` output for `if (a < b) return 1; return 2;` has `b.ge LBB1_2` followed by `b LBB1_1`, with `LBB1_1` the next block.

## Consequences

- A `b_cond` terminator isn't one MCIR instruction. MIR → MCIR owns the branch form, the inversion of each condition code,, and dropping a `b` to the next block.
- An edge's moves, and the new block register allocation puts on a critical edge, are placed without looking at fall-through.
- A conditional branch reaches about 1 MiB. Darwin has no relocation for it, so the host assembler resolves it and rejects a farther one with "fixup value out of range": 262,142 skipped instructions assemble and 262,143 don't. The slice has no branch relaxation, so a function larger than that fails in the assembler, which is a bug in Forge (ADR 0007, ADR 0009) and out of reach for the slice's programs.
