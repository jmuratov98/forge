# Every FIR edge carries its own block arguments

Every successor of a FIR terminator is an edge: a target block and one block argument per parameter of that block. `br` has one edge, `br_if` two, and `switch` a default edge plus one per case, so any edge can feed a block parameter, a `switch` case included. FIR has no trampoline blocks and no critical-edge splitting: HIR → FIR builds exactly the blocks the source's control flow has, and fills each edge's arguments once construction has finished. C makes `switch` targets common join points (`case 1:` falling into `default:`), so a `switch` that couldn't pass arguments would need extra blocks that exist only because of FIR's encoding.

## Considered Options

- **Parameterless `switch` targets, with a trampoline block per edge that needs arguments** (`bbN: br target(args)`). FIR would have one kind of terminator edge without arguments, but Braun's construction would have to decide, each time it adds a parameter to a block, which already-emitted `switch` edges into it need a trampoline, and the trampolines multiply with the cases.
- **Splitting critical edges in FIR** (LLVM's code preparation). It gives every edge a block to hold its moves, but FIR then contains blocks the source never had, and only the register allocator needs them.

## Consequences

- A critical edge (from a block with several successors into a block with several predecessors) can carry arguments. When an edge's moves are not all no-ops, the register allocator places them in a new block on that edge.
- Edges are records in a pool, not entities with ids. A terminator stores the start of its edges, and an edge stores its target, the range of its arguments in the value pool, and a case value for a `switch`.
- Edge arguments are written once, at the end of the function, after the last block parameter has been settled. The verifier checks that every edge passes exactly as many arguments as its target has parameters.
