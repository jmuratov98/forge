# Frame lowering

How the first slice's frame lowering turns a MIR body in `allocated` into one in `final`: the layout of the stack frame, the prologue and the epilogue, how frame indices become `sp` offsets that the assembler accepts, and the limits that are left. MIR itself is [docs/mir.md](mir.md), register allocation is [docs/register-allocation.md](register-allocation.md), storage follows [docs/ir-data-layout.md](ir-data-layout.md), and terms follow [GLOSSARY.md](../GLOSSARY.md).

One decision is recorded as an ADR: frame lowering pushes the frame record first and addresses every frame object from `sp` ([ADR 0020](adr/0020-frame-lowering-pushes-the-frame-record-first-and-addresses-every-frame-object-from-sp.md)).

## Overview

Frame lowering runs once per function, after register allocation and before the MIR verifier and MIR → MCIR. It:

1. decides whether the function is a **leaf function**, one that contains no `bl`;
2. gives every frame object an offset from `sp`;
3. rewrites every `frame_index` operand into `sp` and that offset, and splits the offsets an instruction can't reach;
4. puts the prologue at the top of the entry block and the epilogue before every `ret`;
5. sets the body's state to `final`.

It is a copying rewrite ([docs/ir-data-layout.md](ir-data-layout.md#order)). When it has nothing to insert (no prologue and no split offset) it rewrites the operands in place and copies nothing, as for `add` and `callee` in [Worked examples](#worked-examples).

## Leaf functions

A leaf function keeps no frame record: `x29` and `x30` are never touched, and `x30` holds the return address throughout. It lowers `sp` only when it has spill slots, and it never has an `outgoing` object, since it makes no call. Apple's ABI lets a leaf skip the frame record, and clang skips it too.

It doesn't use the red zone. Apple preserves 128 bytes below `sp`, but reaching them takes negative offsets (`ldur`, `stur`), which MIR doesn't have, and clang doesn't use them either.

A function that contains a `bl` keeps a frame record, because `bl` overwrites `x30` and Apple's ABI requires `x29` to point at a valid frame record.

## The frame

```
            caller's frame: the incoming area
sp on entry ─────────────────────────────────────
            frame record: x29, x30           ← x29
            padding to 16
            spill slots, last index highest
            outgoing area                     ← sp
```

| Object | Offset from `sp` in the body |
|---|---|
| `outgoing` | 0 |
| `spill`, in frame-index order | the end of the previous object, rounded up to the slot's size (4 or 8) |
| the frame record | L, in a function with a `bl` |
| `incoming` | L + 16, or N in a leaf |

- **L** (in a function with a `bl`) and **N** (in a leaf) are the size of the outgoing area and the spill slots, rounded up to 16. The padding goes at the top, under the frame record.
- **Every frame object is addressed from `sp`**, never from `x29`, the caller's incoming area included. Nothing moves `sp` between the prologue and the epilogue, and a leaf has no `x29`.
- **Spill slots go upward from the outgoing area.** Register allocation makes the slots of the values that cross a block boundary before its walk, so they come first and sit as close to `sp` as the outgoing area allows. They include every block parameter, which is what a cycle in a parallel move writes ([Limits](#limits)).
- **Callee-saved registers.** The slice never writes `x19`–`x28` ([ADR 0018](adr/0018-the-slices-register-allocator-is-local-and-values-that-cross-a-block-live-in-spill-slots.md)). Frame lowering has no code to save them, and the `final` verifier rejects them. An allocator that uses them will push its first pair before the frame record and store the record above it, as clang does (`stp x20, x19, [sp, #-32]!`, then `stp x29, x30, [sp, #16]` and `add x29, sp, #16`), which changes the prologue's first instruction.

## The prologue and the epilogue

In a function that contains a `bl`:

```
stp_pre  x29, x30, [sp, #-16]!          add_ri   sp, sp, #L
add_ri   x29, sp, #0                     ldp_post x29, x30, [sp], #16
sub_ri   sp, sp, #L                      ret
```

In a leaf with N > 0, the prologue is `sub_ri sp, sp, #N` and the epilogue is `add_ri sp, sp, #N` before each `ret`. A leaf with N = 0 gets neither.

- **The frame record is pushed first**, so its store can be encoded whatever the size of the frame. This is clang's shape whenever it doesn't fold the stack adjustment into the frame record's store. Clang at `-O0` folds it for small frames (`sub sp, sp, #32`, `stp x29, x30, [sp, #16]`, `add x29, sp, #16`), but `stp`'s offset reaches only 504, so the folded form needs a second shape for frames over 520 bytes. Both take three instructions on the way in and three on the way out, and the pushed form takes two fewer when L = 0.
- `add_ri x29, sp, #0` prints as `mov x29, sp` in the assembly. The `sub_ri` and its `add_ri` are left out when L = 0.
- **Stack adjustments.** A frame of up to 4095 bytes takes one `sub_ri`. A larger one takes two, as clang does: `sub_ri sp, sp, #(L − L mod 4096)`, which the assembly writes as `#k, lsl #12`, then `sub_ri sp, sp, #(L mod 4096)` when that isn't 0. The epilogue adds them back in the same order. `sp` stays a multiple of 16 between the two.
- **Placement.** The prologue goes at the top of the entry block, before register allocation's stores of the entry parameters. The epilogue goes right before each `ret`, after any reload of the returned value. Both take the function's location.
- **No stack probes.** Clang on Darwin calls `___chkstk_darwin` before it lowers `sp` by 4096 bytes or more, so that a stack overflow hits the guard page instead of skipping it. That takes an indirect call, and the slice leaves probes out. A frame reaches 4096 bytes only with about 1,000 values that cross blocks or a call with about 1,000 arguments.

## Rewriting frame indices

Each `[fiK, #off]` becomes `[sp, #o]`, where `o` is fiK's offset plus `off`, and the operand is updated in place. Only `ldr_ui` and `str_ui` name frame objects: instruction selection's loads from `incoming` and stores to `outgoing`, and register allocation's spills, reloads and moves.

When `o` is beyond the reach of the form (4095 times the access size, so 16,380 for a 4-byte access and 32,760 for an 8-byte one), the access is split:

```
add_ri xR, sp, #(o − o mod 4096)
ldr_ui wD, [xR, #(o mod 4096)]
```

- `o mod 4096` is a multiple of the access size, because `o` is, and the high part is a multiple of 4096 that the [frame size limit](#limits) keeps within `0xFFF000`.
- **R.** A load uses its own destination register (its `x` view), which it overwrites anyway. A store uses a scratch register that holds no value at that point: `x17`, or `x16` when the store is from `w17`.
- **Where `x16` and `x17` hold values** is found by one walk up each block. Neither holds a value across a block boundary: every `bl` clobbers both, and register allocation uses them only inside one parallel move ([ADR 0019](adr/0019-x16-and-x17-are-scratch-registers-that-register-allocation-never-assigns.md)).
- The `add_ri` takes the location of the access it serves.

## Limits

Two limits in Forge stop on `FORGE_ASSERT` ([ADR 0009](adr/0009-only-the-frontend-reports-diagnostics.md)), like FIR's 32,767 call arguments ([docs/fir.md](fir.md#entities)) and the 1 MiB reach of a conditional branch ([docs/mir.md](mir.md#terminators-and-edges)):

- **Frame size.** The frame (L or N) plus the incoming area stays under 16 MiB, so every stack adjustment and every split takes at most two instructions. It isn't reachable in practice: the outgoing area is at most 131,036 bytes, and every spill slot costs at least one 4-byte store in the function's code.
- **A store that no register can address.** Inside a cycle of a parallel move, `x16` holds the value saved to break the cycle while `str_ui w17, [fiP, #0]` writes the next slot ([docs/register-allocation.md](register-allocation.md#sequencing-a-parallel-move)). If that slot lies beyond 16,380 bytes from `sp`, neither scratch register is free for the address. The slots in a cycle are block-parameter slots. Those are `gpr32` and are among the slots made before register allocation's walk, so they sit at most `outgoing + 4 × (values that cross a block)` above `sp`. This takes a call with about 4,000 arguments, or about 4,000 values that cross blocks in one function.

## The final body

- **Copying.** Block ids stay and instructions get new ids, as in register allocation. The layout doesn't change.
- **Frame objects** stay in the body's table, but nothing names them any more, so the printer doesn't list them ([docs/mir.md](mir.md#printed-form)). The frame shows in the prologue's immediates and the `[sp, #off]` operands.
- **The verifier** runs on the result in Debug and RelWithAsserts. Its `final` checks, including the fixed prologue and epilogue, are in [docs/mir.md](mir.md#verifier).

## Worked examples

The `allocated` forms are in [docs/mir.md](mir.md#worked-examples) and [docs/register-allocation.md](register-allocation.md#worked-examples).

`add` and `callee` are leaves with no spill slots, so nothing is inserted. `add` is unchanged, and `callee`'s incoming area is at `sp` itself:

```
func @callee(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32 final {
bb0:
  ldr_ui w8, [sp, #0]
  ldr_ui w9, [sp, #4]
  add_rr w8, w0, w8
  add_rr w0, w8, w9
  ret implicit w0
}
```

### Leaves that spill

`sum` has two slots, 8 bytes, so N = 16 and the padding fills its top half:

```
func @sum(i32) -> i32 final {
bb0:
  sub_ri sp, sp, #16
  mov_ri w8, #0
  str_ui w0, [sp, #0]
  str_ui w8, [sp, #4]
  b bb1
bb1:
  ldr_ui w8, [sp, #0]
  cmp_ri w8, #0
  b_cond gt, bb2, bb3
bb2:
  ldr_ui w8, [sp, #0]
  ldr_ui w9, [sp, #4]
  add_rr w9, w9, w8
  sub_ri w8, w8, #1
  str_ui w8, [sp, #0]
  str_ui w9, [sp, #4]
  b bb1
bb3:
  ldr_ui w0, [sp, #4]
  add_ri sp, sp, #16
  ret implicit w0
}
```

`pick` has three returns, and each gets its own epilogue:

```
global @hits = zerofill

func @pick(i32) -> i32 final {
bb0:
  sub_ri sp, sp, #16
  str_ui w0, [sp, #0]
  cmp_ri w0, #0
  b_cond eq, bb2, bb4
bb4:
  ldr_ui w0, [sp, #0]
  cmp_ri w0, #7
  b_cond eq, bb3, bb1
bb2:
  adrp x8, @hits@page
  ldr_ui w0, [x8, @hits@pageoff]
  add_ri sp, sp, #16
  ret implicit w0
bb3:
  mov_ri w8, #1
  adrp x9, @hits@page
  str_ui w8, [x9, @hits@pageoff]
  mov_ri w0, #20
  add_ri sp, sp, #16
  ret implicit w0
bb1:
  mov_ri w0, #-1
  add_ri sp, sp, #16
  ret implicit w0
}
```

`spin`'s cycle stays in reach, as every cycle does below 16,380 bytes:

```
func @spin(i32, i32, i32) -> i32 final {
bb0:
  sub_ri sp, sp, #16
  str_ui w0, [sp, #0]
  str_ui w1, [sp, #4]
  str_ui w2, [sp, #8]
  b bb1
bb1:
  ldr_ui w8, [sp, #0]
  cmp_ri w8, #0
  b_cond gt, bb2, bb3
bb2:
  ldr_ui w8, [sp, #0]
  sub_ri w8, w8, #1
  str_ui w8, [sp, #0]
  ldr_ui w16, [sp, #4]
  ldr_ui w17, [sp, #8]
  str_ui w17, [sp, #4]
  str_ui w16, [sp, #8]
  b bb1
bb3:
  ldr_ui w8, [sp, #4]
  ldr_ui w9, [sp, #8]
  sub_rr w0, w8, w9
  add_ri sp, sp, #16
  ret implicit w0
}
```

`count`'s four slots fill its 16 bytes exactly:

```
func @count(i32) -> i32 final {
bb0:
  sub_ri sp, sp, #16
  mov_ri w8, #0
  str_ui w8, [sp, #0]
  str_ui w0, [sp, #4]
  b bb1
bb1:
  ldr_ui w9, [sp, #0]
  ldr_ui w8, [sp, #4]
  add_rr w9, w9, w8
  str_ui w9, [sp, #8]
  sub_ri w8, w8, #1
  str_ui w8, [sp, #12]
  b bb2
bb2:
  ldr_ui w8, [sp, #12]
  cmp_ri w8, #0
  b_cond gt, bb4, bb3
bb4:
  ldr_ui w17, [sp, #8]
  str_ui w17, [sp, #0]
  ldr_ui w17, [sp, #12]
  str_ui w17, [sp, #4]
  b bb1
bb3:
  ldr_ui w0, [sp, #8]
  add_ri sp, sp, #16
  ret implicit w0
}
```

### Functions with a call

`caller` passes ten arguments. Its 8-byte outgoing area makes L = 16, and the frame record sits above it:

```
func @sink(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32

func @caller(i32) -> i32 final {
bb0:
  stp_pre x29, x30, [sp, #-16]!
  add_ri x29, sp, #0
  sub_ri sp, sp, #16
  add_ri w8, w0, #9
  mov_ri w9, #8
  str_ui w9, [sp, #0]
  str_ui w8, [sp, #4]
  mov_ri w1, #1
  mov_ri w2, #2
  mov_ri w3, #3
  mov_ri w4, #4
  mov_ri w5, #5
  mov_ri w6, #6
  mov_ri w7, #7
  bl @sink, implicit w0, implicit w1, implicit w2, implicit w3, implicit w4, implicit w5, implicit w6, implicit w7, implicit-def w0
  add_ri sp, sp, #16
  ldp_post x29, x30, [sp], #16
  ret implicit w0
}
```

`twice` spills `x` around the call. Its frame is 32 bytes in all, as clang `-O0`'s is:

```
func @twice(i32) -> i32 final {
bb0:
  stp_pre x29, x30, [sp, #-16]!
  add_ri x29, sp, #0
  sub_ri sp, sp, #16
  str_ui w0, [sp, #0]
  bl @h, implicit w0, implicit-def w0
  ldr_ui w8, [sp, #0]
  add_rr w0, w0, w8
  add_ri sp, sp, #16
  ldp_post x29, x30, [sp], #16
  ret implicit w0
}
```

`flip` has no frame objects, so L = 0 and only the frame record is pushed:

```
func @flip(i32, i32) -> i32 final {
bb0:
  stp_pre x29, x30, [sp, #-16]!
  add_ri x29, sp, #0
  mov_rr w16, w1
  mov_rr w1, w0
  mov_rr w0, w16
  bl @g2, implicit w0, implicit w1, implicit-def w0
  ldp_post x29, x30, [sp], #16
  ret implicit w0
}
```

### An offset out of reach

Take a function that passes 5,000 arguments to one call and has one value that crosses a block. Its outgoing area `fi0` is 4 × 4,992 = 19,968 bytes, and its spill slot `fi1` sits right above it, so L = 19,984. The prologue takes two `sub_ri`s:

```
  stp_pre x29, x30, [sp, #-16]!
  add_ri x29, sp, #0
  sub_ri sp, sp, #16384
  sub_ri sp, sp, #3600
```

The last argument (`str_ui w8, [fi0, #19964]`), a spill (`str_ui w9, [fi1, #0]`) and a reload (`ldr_ui w9, [fi1, #0]`) are each split. The stores go through `x17`, and the reload goes through its own destination:

```
  add_ri x17, sp, #16384
  str_ui w8, [x17, #3580]
  ...
  add_ri x17, sp, #16384
  str_ui w9, [x17, #3584]
  ...
  add_ri x9, sp, #16384
  ldr_ui w9, [x9, #3584]
```

The epilogue adds back `#16384` and then `#3600` before `ldp_post`. The assembly writes `#16384` as `#4, lsl #12`.
