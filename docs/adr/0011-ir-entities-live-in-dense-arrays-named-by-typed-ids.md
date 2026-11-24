# IR entities live in dense arrays named by typed ids

Every layer from the AST to MCIR keeps its entities (nodes, values, instructions, blocks, registers, symbols) in dense arrays owned by one container per lifetime, and names them by 32-bit ids with a distinct C++ type per entity kind. No entity points at another, and there is no arena allocator: destroying or clearing a container frees everything in it, and the FIR and MIR bodies are cleared and reused from one function to the next. Instruction order is array order and changes only by copying: a step that inserts or reorders writes a new array in one linear pass. No layer keeps use-lists, and a pass that needs uses computes them into a side table. ADR 0008 makes five layers affordable only if each lowering is one linear pass over dense arrays; this is the shape of those arrays, and every pass is written against it.

## Considered Options

- **Pointer-linked nodes in bump arenas** (LLVM, clang). The natural fit for a recursive-descent parser and for passes that edit in place, but every reference is an 8-byte pointer to chase, and nodes scatter in memory as the IR is edited. V8 measured about 3x more L1 dcache misses for that reason before replacing sea of nodes with a CFG IR.
- **A linked layout over dense storage** (Cranelift's CLIF: prev/next ids for every instruction and block). Insertion takes constant time and passes can edit in place, at 8 or more bytes per instruction and a scattered order after edits. The slice has no passes that edit in place, and its insertions (register allocation, frame lowering) are linear rewrites anyway, like V8 Turboshaft's copying phases.
- **Use-lists** (LLVM). They make replacing every use of a value proportional to its uses, but every operand write has to maintain them and operand storage roughly doubles. The one replacement the slice needs, removing trivial block parameters during FIR construction, goes through an alias table instead.
- **Variable-size records in one buffer** (Turboshaft). Ids become byte offsets, which side tables can't index densely.

## Consequences

- An id means something only in its own container. Body ids are dead once the body is cleared, module ids last for the translation unit, and no layer stores another layer's ids: a lowering keeps its mappings in side tables.
- A copying rewrite keeps the ids of blocks, values and virtual registers and gives instructions new ids, so a side table keyed by instruction ids doesn't survive it.
- HIR → FIR lowering has to finish a block before it starts the next, and `undef` can't be an instruction.
- Printed ids are array indices, gaps included, so tests capture them with FileCheck variables.
- The working rules are in [docs/ir-data-layout.md](../ir-data-layout.md).
