# x16 and x17 are scratch registers that register allocation never assigns

Register allocation never assigns `x16` or `x17`. They are kept for the instructions that register allocation and frame lowering insert. A parallel move, on an edge or at the top of the entry block, uses `x16` to break a cycle (a loop that passes its own parameters back in swapped order) and `x17` to move a value from one spill slot to another. Frame lowering can use them to reach a frame offset or make a stack adjustment that doesn't fit an immediate: `str w0, [sp, #131000]` and `sub sp, sp, #4112` don't assemble. Every `bl` already clobbers both registers, and Apple's linker may clobber them in stubs and branch islands, so between calls they are the cheapest pair to give up. The allocatable set is `x0`–`x15`, 16 registers, since ADR 0018 leaves `x19`–`x28` unused in the slice.

## Considered Options

- **Scavenging a free register where one is needed, with an emergency spill slot when none is** (LLVM's register scavenger). It keeps two more registers allocatable, but every pass that inserts code has to find a free register at its insertion point, and frame lowering has to reserve a slot for the case where there is none.
- **Any free allocatable register at the edge.** At the end of a block most registers are free under ADR 0018, but not always, so it still needs a fallback.
- **Swapping with three `eor_rr`s,** with no temporary at all. It works only between registers, and the slice's cycles are mostly between spill slots.

## Consequences

- The parallel-move resolver never runs out of registers: it breaks one cycle at a time through `x16`, and a slot-to-slot move goes through `x17`.
- Frame lowering may use both, except inside a slot-to-slot move within a cycle, where the allocator is already using both. There, no register is left for an out-of-range offset, so [Stack frames and frame lowering for the slice](https://github.com/jmuratov98/forge/issues/35) has to keep spill slots within reach of those instructions.
- The allocation checker asserts that `x16` and `x17` appear only in instructions the allocator added ([docs/register-allocation.md](../register-allocation.md#the-allocation-checker)).
- An allocator that gives them back would gain two registers, and frame lowering's out-of-range handling would have to change with it.
