# Register allocation

How the first slice's register allocator turns a MIR body in `ssa` into one in `allocated`, and what the allocation checker asserts. MIR itself is [docs/mir.md](mir.md), storage follows [docs/ir-data-layout.md](ir-data-layout.md), and terms follow [GLOSSARY.md](../GLOSSARY.md).

Two decisions are recorded as ADRs: the allocator is local, and every value that crosses a block boundary lives in its spill slot there ([ADR 0018](adr/0018-the-slices-register-allocator-is-local-and-values-that-cross-a-block-live-in-spill-slots.md)), and `x16` and `x17` are scratch registers ([ADR 0019](adr/0019-x16-and-x17-are-scratch-registers-that-register-allocation-never-assigns.md)).

## Overview

The allocator has the shape of clang's at `-O0`. No register carries a value from one block into another: a value that crosses a block boundary is stored to its spill slot once, right after its def, and reloaded in each other block that uses it. Each block is then allocated on its own, by one walk from its terminator up to its first instruction. A value live across a call is spilled around it, and nothing is coalesced.

- **One allocator.** The driver ignores `-O` in the slice, so every compile uses this one. An allocator chosen by `-O` level, with a forward greedy one for `-O1` and above, belongs to a later effort; it reads and writes the same states and is checked by the same checker.
- **No liveness across blocks.** One walk over the body finds the values that cross a block boundary. Everything else the allocator knows comes from walking one block.
- **Inserted instructions** are `mov_rr`, `ldr_ui` and `str_ui` on spill slots, and `b` at the end of a new block. None of them touches `nzcv`, so the flags rule in [docs/mir.md](mir.md#verifier) holds without the allocator knowing about flags.

## Registers

| Registers | In the slice |
|---|---|
| `x0`–`x15` | allocatable, tried in the order `x8`–`x15`, then `x0`–`x7` |
| `x16`, `x17` | scratch registers, never assigned: `x16` breaks a cycle in a parallel move and `x17` carries a move from one spill slot to another; frame lowering may use them too ([ADR 0019](adr/0019-x16-and-x17-are-scratch-registers-that-register-allocation-never-assigns.md)) |
| `x18` | reserved by Apple's ABI |
| `x19`–`x28` | callee-saved, and never used, so frame lowering saves only the frame record |
| `x29`, `x30`, `sp` | operands only where [docs/mir.md](mir.md#registers) allows; the allocator adds none |

The order tries the caller-saved registers that carry no arguments first, because calls and `ret` want `x0`–`x7`. A physical-register operand's class picks `w` or `x`, as everywhere in MIR.

## Values that cross a block boundary

A virtual register **crosses a block boundary** when it is a parameter of a block other than the entry block, or when it is used in a block other than the one that defines it. An edge argument counts as a use in the edge's own block.

- **Spill slots.** Each crossing value gets a `spill` frame object before the walk, in virtual-register order, after the objects instruction selection made. A slot is 4 bytes for `gpr32` and 8 for `gpr64`, aligned to its size. A value that the walk spills because of a call or a shortage of registers gets its slot when the walk first spills it, in the order the walk meets such values, and in virtual-register order among those that one call spills.
- **Stores.** A crossing value is stored once, right after its def. An entry-block parameter is stored at the top of the entry block, from the register it arrives in. A parameter of any other block is never stored by its block: its incoming edges write its slot.
- **Reloads.** A crossing value is reloaded at the top of every other block that uses it, or lower down where the walk had to evict it.
- Within its own block, a value stays in a register after it is stored, for the uses that follow.

## The walk

Blocks are allocated one at a time, in layout order. Each block is walked from its terminator to its first instruction, and its instructions are written reversed and then flipped, as instruction selection does. During the walk the allocator knows, for each value with a use below the current instruction, the register it occupies there.

### Choosing a register

The walk first meets a value at its last use. The value takes, in order:

1. the register that use is fixed to (`ret`'s `w0`, a call's `w1`);
2. otherwise the register its def is fixed to, if it is free (an entry parameter's `w0`, a `bl` result's `w0`);
3. otherwise the first free register in the allocation order.

A def with no use below it takes its fixed register, or the first free one.

### An instruction

For each instruction, from the bottom of the block up:

1. **A call** spills every value that has a register below it and isn't the call's own result: each one is reloaded right after the `bl`, in slot order, and stored after its def.
2. **Defs** free their registers. A def whose value was given another register below its fixed one writes the fixed register, and a `mov_rr` after the instruction copies it. A def with a spill slot is followed by its store.
3. **Fixed uses** take their registers. A value passed twice to one call keeps its first fixed register, and a `mov_rr` right before the call copies it into the second.
4. **The tied use** of `movk` takes its def's register.
5. **Other uses** take a register by the rules above.

What follows an instruction is in this order: the stores of its defs, the copies of a fixed def, then the reloads. A fixed register that another value occupies is freed by evicting that value; instruction selection's output never needs this, because only a `bl` has a fixed def and it has already spilled everything around it.

### When no register is free

The walk evicts a value that has a register but isn't an operand of the current instruction. It prefers a value that already has a spill slot, which needs no new store, and otherwise the value assigned earliest in the walk. The evicted value is reloaded right after the current instruction, and stored after its def if it wasn't already.

### The top of a block

- **The entry block** first stores each parameter that has a spill slot, from the register it arrives in. Then one parallel move takes every parameter from its fixed register to the register the walk gave it. `int flip(int a, int b) { return g2(b, a); }` makes that move a cycle (see [Worked examples](#worked-examples)).
- **Every other block** reloads, in slot order, each value the walk left in a register at the top. Each of them crosses a block boundary, so it has a slot.

## Edges

Each edge whose arguments aren't all no-ops is one **parallel move** from where each argument is to its parameter's spill slot, read before any slot is written, as the edge's semantics require.

- **Sources.** An argument with a spill slot is read from its slot. Any other argument, which is defined in the edge's own block, gets a register at the end of that block like any use. If none is free it is spilled and read from its slot.
- **Placement**, by the rules in [docs/mir.md](mir.md#terminators-and-edges):
  - at the end of the edge's block, before its `b`, when the block has one successor;
  - at the top of the target, before its reloads, when the target has one predecessor. FIR never gives such a block parameters (one predecessor makes them trivial), but MIR allows it;
  - otherwise, on a critical edge, in a new block holding the moves and a `b` to the target. The new block goes right after its source block, in edge order (taken, then not taken), and takes the next block id in the order new blocks are made. The terminator's edge is retargeted to it.
- Moves at the top of a target or in a new block read the source block's registers, which the branch leaves untouched.
- **No-ops.** A parameter's slot is never its argument's, unless a block passes a parameter of its own target through unchanged, so nearly every critical edge with arguments gets a new block.

### Sequencing a parallel move

A destination is a register (the top of the entry block) or a spill slot (an edge). The resolver repeatedly emits the first pending move whose destination no other pending move reads. When every pending move is blocked, the rest are cycles: it copies the first pending move's destination into `x16`, makes the moves that read that location read `x16` instead, and carries on, which breaks one cycle at a time. A move from one slot to another loads into `x17` and stores it.

| Source → destination | Instructions |
|---|---|
| register → register | `mov_rr` |
| register → slot | `str_ui` |
| slot → register | `ldr_ui` |
| slot → slot | `ldr_ui` into `x17`, then `str_ui` |

## Unreachable blocks

Unreachable blocks are allocated like any other, and reach the object file as dead code, since HIR and FIR keep them too. Nothing in an unreachable region refers to a value outside it ([docs/fir.md](fir.md#semantics)), and every value that crosses into or out of a block is in its slot, so the allocator has nothing to invent for them. The checker skips them.

## The allocated body

- **A copying rewrite** ([docs/ir-data-layout.md](ir-data-layout.md#order)): block ids stay, instructions get new ids, and new blocks get new ids. The layout is the original one with each new block right after its source.
- **Operands.** Every virtual-register operand becomes a physical register of its class, implicit operands included, so the checker can see them. Block parameters and edge arguments are gone.
- **Frame objects.** The `spill` objects follow the `incoming` and `outgoing` objects that instruction selection made. Where they sit in the frame is [docs/frame-lowering.md](frame-lowering.md#the-frame).
- **Locations.** A store after a def, a copy around an instruction and a reload after one take that instruction's location. A reload at the top of a block takes that of the first instruction in the block that uses the value. A store or move at the top of the entry block takes its parameter's virtual register's location. An edge's moves, wherever they go, and a new block's `b` take the location of the edge's terminator.

## The allocation checker

How the checker is built is still open, in the map's IR verification fog. It receives the body in `ssa`, the body in `allocated`, and a side table from the allocator that maps each allocated instruction to the `ssa` instruction it copies or marks it as added, and each new block to its edge. It runs a symbolic dataflow over every block reachable from the entry. For each register and spill slot it tracks the set of virtual registers that location holds: a def removes its virtual register from every location and puts it in its own, `mov_rr`, `ldr_ui` and `str_ui` copy a set, a `bl` empties `x0`–`x17` and `x30`, a merge keeps only what every predecessor agrees on, and an edge renames each argument to its parameter. It doesn't assume that values cross blocks in their slots, so it holds for a later allocator too.

It asserts:

1. **Values.** Every register use of an original instruction reads a location that holds the virtual register the `ssa` instruction used, on every path from the entry.
2. **Constraints.** Every fixed operand is in its register, and `movk`'s def and tied use share one.
3. **Registers.** Only allocatable registers replace virtual registers. `x16` and `x17` appear only in instructions the allocator added, `x18` never appears, and `sp`, `x29` and `x30` appear only where [docs/mir.md](mir.md#registers) allows.
4. **Inserted code.** Each block keeps its original instructions in order, with the same opcodes and the same non-register operands. The only instructions added are `mov_rr`, and `ldr_ui` and `str_ui` on `spill` objects at the object's size, so `nzcv` is untouched.
5. **The CFG.** Every original edge reaches its target directly, or through exactly one new block that holds only moves and a `b` to that target.

Unreachable blocks aren't checked.

## Worked examples

The `ssa` forms are in [docs/mir.md](mir.md#worked-examples) or below. The `allocated` state isn't printed by any flag, but it prints as `final` does, with its frame objects listed first. Frame lowering's `final` forms of these examples are in [docs/frame-lowering.md](frame-lowering.md#worked-examples).

`add` is unchanged: `%0` and `%2` take `w0` and `%1` takes `w1`, so allocation inserts nothing (`add_rr w0, w0, w1` in [docs/ir-data-layout.md](ir-data-layout.md#worked-example)).

### A loop

`sum`'s `bb1` parameters `%1` and `%3` cross block boundaries and get `fi0` and `fi1`. `%0`, `%4`, `%5` and `%6` are used only in the blocks that define them, as edge arguments, so they stay in registers:

```
func @sum(i32) -> i32 allocated {
  fi0: spill, size 4, align 4
  fi1: spill, size 4, align 4
bb0:
  mov_ri w8, #0
  str_ui w0, [fi0, #0]
  str_ui w8, [fi1, #0]
  b bb1
bb1:
  ldr_ui w8, [fi0, #0]
  cmp_ri w8, #0
  b_cond gt, bb2, bb3
bb2:
  ldr_ui w8, [fi0, #0]
  ldr_ui w9, [fi1, #0]
  add_rr w9, w9, w8
  sub_ri w8, w8, #1
  str_ui w8, [fi0, #0]
  str_ui w9, [fi1, #0]
  b bb1
bb3:
  ldr_ui w0, [fi1, #0]
  ret implicit w0
}
```

The edges into `bb1` end in `b`, so their moves go before it, and the edges of `bb1`'s `b_cond` carry no arguments.

### A value live across a call

```c
int h(int);
int twice(int x) { return h(x) + x; }
```

```
func @h(i32) -> i32

func @twice(i32) -> i32 ssa {
bb0(%0:gpr32 [w0]):
  bl @h, implicit %0 [w0], implicit-def %1:gpr32 [w0]
  %2:gpr32 = add_rr %1, %0
  ret implicit %2 [w0]
}
```

Walking up, `ret` gives `%2` `w0`. `add_rr` frees it, `%1` takes `w0` because its def is fixed there, and `%0` takes `w8`. At the `bl`, `%0` has a register below the call, so it is spilled to the new `fi0`, reloaded after the call and stored at the top of the entry block:

```
func @twice(i32) -> i32 allocated {
  fi0: spill, size 4, align 4
bb0:
  str_ui w0, [fi0, #0]
  bl @h, implicit w0, implicit-def w0
  ldr_ui w8, [fi0, #0]
  add_rr w0, w0, w8
  ret implicit w0
}
```

This is clang `-O0`'s shape, without clang's reload of `x` before the call: clang also keeps every local variable in memory between statements, and FIR has none.

### An edge whose parallel move is a cycle

```c
int spin(int n, int a, int b) {
  while (n > 0) { int t = a; a = b; b = t; n -= 1; }
  return a - b;
}
```

```
func @spin(i32, i32, i32) -> i32 ssa {
bb0(%0:gpr32 [w0], %1:gpr32 [w1], %2:gpr32 [w2]):
  b bb1(%0, %1, %2)
bb1(%3:gpr32, %5:gpr32, %6:gpr32):
  cmp_ri %3, #0
  b_cond gt, bb2, bb3
bb2:
  %7:gpr32 = sub_ri %3, #1
  b bb1(%7, %6, %5)
bb3:
  %8:gpr32 = sub_rr %5, %6
  ret implicit %8 [w0]
}
```

`bb2` passes `bb1`'s own parameters `%5` and `%6` back in swapped order, without reading them. They are read from their slots, so the move is `fi0` ← `w8`, `fi1` ← `fi2` and `fi2` ← `fi1`. The first goes straight away, and the other two are a cycle that `x16` breaks:

```
func @spin(i32, i32, i32) -> i32 allocated {
  fi0: spill, size 4, align 4
  fi1: spill, size 4, align 4
  fi2: spill, size 4, align 4
bb0:
  str_ui w0, [fi0, #0]
  str_ui w1, [fi1, #0]
  str_ui w2, [fi2, #0]
  b bb1
bb1:
  ldr_ui w8, [fi0, #0]
  cmp_ri w8, #0
  b_cond gt, bb2, bb3
bb2:
  ldr_ui w8, [fi0, #0]
  sub_ri w8, w8, #1
  str_ui w8, [fi0, #0]
  ldr_ui w16, [fi1, #0]
  ldr_ui w17, [fi2, #0]
  str_ui w17, [fi1, #0]
  str_ui w16, [fi2, #0]
  b bb1
bb3:
  ldr_ui w8, [fi1, #0]
  ldr_ui w9, [fi2, #0]
  sub_rr w0, w8, w9
  ret implicit w0
}
```

`flip` from [The top of a block](#the-top-of-a-block) has the register form of the same cycle: the walk puts `%1` in `w0` and `%0` in `w1` for the call, so the top of the entry block swaps them.

```
func @flip(i32, i32) -> i32 allocated {
bb0:
  mov_rr w16, w1
  mov_rr w1, w0
  mov_rr w0, w16
  bl @g2, implicit w0, implicit w1, implicit-def w0
  ret implicit w0
}
```

### A critical edge

```c
int count(int n) {
  int s = 0;
  do { s += n; n -= 1; } while (n > 0);
  return s;
}
```

A loop tested last ([docs/fir.md](fir.md#control-flow)) puts its test in its own block, whose `b_cond` passes arguments back to the body:

```
func @count(i32) -> i32 ssa {
bb0(%0:gpr32 [w0]):
  %6:gpr32 = mov_ri #0
  b bb1(%6, %0)
bb1(%1:gpr32, %2:gpr32):
  %3:gpr32 = add_rr %1, %2
  %4:gpr32 = sub_ri %2, #1
  b bb2
bb2:
  cmp_ri %4, #0
  b_cond gt, bb1(%3, %4), bb3
bb3:
  ret implicit %3 [w0]
}
```

`bb2` has two successors and `bb1` two predecessors, so the edge `bb2` → `bb1` is critical. Its moves go in the new `bb4`, right after `bb2`. `%3` and `%4` are used outside `bb1`, so they have slots too, and both moves are slot to slot through `x17`:

```
func @count(i32) -> i32 allocated {
  fi0: spill, size 4, align 4
  fi1: spill, size 4, align 4
  fi2: spill, size 4, align 4
  fi3: spill, size 4, align 4
bb0:
  mov_ri w8, #0
  str_ui w8, [fi0, #0]
  str_ui w0, [fi1, #0]
  b bb1
bb1:
  ldr_ui w9, [fi0, #0]
  ldr_ui w8, [fi1, #0]
  add_rr w9, w9, w8
  str_ui w9, [fi2, #0]
  sub_ri w8, w8, #1
  str_ui w8, [fi3, #0]
  b bb2
bb2:
  ldr_ui w8, [fi3, #0]
  cmp_ri w8, #0
  b_cond gt, bb4, bb3
bb4:
  ldr_ui w17, [fi2, #0]
  str_ui w17, [fi0, #0]
  ldr_ui w17, [fi3, #0]
  str_ui w17, [fi1, #0]
  b bb1
bb3:
  ldr_ui w0, [fi2, #0]
  ret implicit w0
}
```

The layout is `bb0 bb1 bb2 bb4 bb3`. MIR → MCIR prints `bb2`'s `b_cond` as `b.le bb3`, because `bb4` follows, and keeps `bb4`'s `b bb1`.
