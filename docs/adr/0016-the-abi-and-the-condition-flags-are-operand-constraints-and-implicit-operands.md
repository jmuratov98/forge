# The ABI and the condition flags are operand constraints and implicit operands

MIR gets the calling convention's registers through constraints on the operands that need them, not through copies to and from physical registers. An entry-block parameter, a call's argument or result, and the value of `ret` carry a fixed physical register (`bb0(%0 [w0])`, `ret implicit %2 [w0]`), and the one tied operand in the slice, `movk`'s use, must share its def's register. The condition flags are a physical register, `nzcv`, which `cmp_*` defines and `b_cond` and `cset` use, and a `bl`'s clobbers (`x0`–`x17`, `x30`, `nzcv`) come from a table keyed by opcode. Register allocation therefore needs one mechanism for the ABI, ties and clobbers, and it never has to know about flags: everything it inserts (`mov_rr`, `ldr_ui`, `str_ui`, `movz`, a stack adjustment) leaves them alone, so the verifier only checks that a use of `nzcv` sees a def in the same block with no `cmp_*` or `bl` between them.

## Considered Options

- **Copies to and from physical registers** (LLVM's `COPY $w0`), with the allocator coalescing them away. Constraints on the operands stay one mechanism, while copies make every call and entry a place where the allocator has to recover the obvious assignment, and they put `copy` pseudo-instructions in MIR (ADR 0015).
- **An `args` pseudo-instruction** that defines the incoming registers, so block parameters never carry constraints. Rejected for the same reason, and because the entry block's parameters already are the function's parameters in FIR.
- **Fused `cmp_br` and `cmp_cset` pseudo-instructions,** with no flags register at all. Nothing in MIR would model the flags, but each would expand to two real instructions, and it hides a dependency that is real hardware state.

## Consequences

- The allocator has to honour fixed registers, ties and clobbers, and the allocation checker sees the implicit operands because they stay as physical-register operands after allocation.
- Only entry-block parameters may carry a fixed constraint. A function with more than eight parameters has eight entry parameters, and the rest are `ldr_ui` from the `incoming` frame object.
- An implicit operand isn't in the assembly. Dumps print it (`implicit`, `implicit-def`), and MIR → MCIR drops it.
- Flags never live across a block, so an edge, a spill or a move can't separate a `cmp_*` from its user.
