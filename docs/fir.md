# FIR

What FIR holds in the first slice, what it means, how HIR → FIR builds it, how it is printed and what its verifier checks. FIR is the SSA control-flow-graph layer between HIR and MIR ([ADR 0008](adr/0008-five-fixed-ir-layers-each-lowering-removes-one-kind-of-structure.md)). HIR → FIR removes structured control flow and mutable variables: the CFG is built directly from HIR with Braun et al.'s algorithm, with block parameters instead of φ-nodes. Storage follows [docs/ir-data-layout.md](ir-data-layout.md) and isn't restated here; terms follow [GLOSSARY.md](../GLOSSARY.md).

## Entities

FIR has two containers. The **FIR module** lives for the translation unit and holds every global and the signature of every function. A **FIR body** lives for one function: HIR → FIR builds it, the verifier checks it, and it is cleared once the function has been lowered to MIR.

| Entity | Id | Record | Columns |
|---|---|---|---|
| function | `function_id` | return type, flags (internal, defined, prototyped), parameter-type range | name, location |
| global | `global_id` | flags (internal, defined, zerofill), initializer | name, location |
| block | `block_id` | parameter range, instruction range | none |
| value | `value_id` | kind, type, payload | name, location |
| instruction | `inst_id` | opcode, type, flags, three 32-bit fields | location |

- **Pools.** The module has `std::vector<type>` (parameter types). A body has `std::vector<value_id>`, shared by block parameters, edge arguments and call arguments, and `std::vector<edge>` (see [Terminators and edges](#terminators-and-edges)). An edge is a record in that pool, not an entity with an id ([ADR 0013](adr/0013-every-fir-edge-carries-its-own-block-arguments.md)).
- **Layout.** A body keeps its **layout**: the block ids in the order their instruction ranges were written, entry block first. The entry block is block 0.
- **Declarations.** The module has a function entity for every function, declarations included, and a global entity for every global. A declared function or global has no body or storage.
- **Names** are interned-string ids. A function's or global's name is its linkage name, as in HIR. A value keeps a name only when it is a parameter that stands for a HIR local.
- **Records** are 8 bytes for a value, 16 for an instruction, an edge and a block, 8 for a global and 12 for a function. A call takes at most 32,767 arguments, because its flags hold the count in 15 bits; going over is a limit in Forge, stopped by `FORGE_ASSERT` (ADR 0009).

## Types

`i32` and `void`, as a `std::uint8_t` `enum class`. FIR doesn't distinguish signed from unsigned: every value is a 32-bit two's complement integer, and signedness belongs to the operation. `void` is only a function's return type and the type of an instruction that defines no value (`store`, a call to a void function, the terminators). No value has type `void`.

## Values

A body has one array of values, separate from the instructions.

| Kind | Payload | Name and location |
|---|---|---|
| `param` | the block that lists it | the HIR local's name and location; a join made for an expression has no name and the operator's location |
| `result` | the instruction that defines it | none; it takes its instruction's location |
| `constant` | the 32 bits | none |
| `undef` | none | none |
| `removed` | none | none |

- **Constants** are interned per function: one value for each distinct 32-bit pattern, created the first time it is used. A join whose arms pass the same constant therefore gets a trivial parameter, which construction removes.
- **`undef`** is one value per function, created on first use. It is an arbitrary `i32` that each use may see differently, and it may be any operand, including a `br_if` condition or a `switch` value. Braun's construction makes it for a local read before any write and for a read in a block with no predecessors, so it appears well beyond HIR's `return undef`. Instruction selection may pick any register or 0.
- Constants and `undef` aren't defined by an instruction, so they are valid anywhere and exempt from dominance.
- **`removed`** is a block parameter that construction found trivial. It keeps its slot so that ids don't move, and nothing refers to it once the function is finished.
- A value is defined exactly once: a parameter by its block's parameter list, a result by the `result` field of one instruction.

## Instructions

Every instruction record is an opcode, a type, a 16-bit `flags` and three 32-bit fields. Every operand is a value, except the global of `load` and `store` and the function of `call`.

| Opcode | Flags | Field 0 | Field 1 | Field 2 |
|---|---|---|---|---|
| `add` `sub` `mul` `and` `or` `xor` `shl` `lshr` `ashr` `sdiv` `udiv` `srem` `urem` | none | result | a | b |
| `icmp` | predicate | result | a | b |
| `load` | none | result | global | none |
| `store` | none | none | global | value |
| `call` | bit 15 set for `noproto`, bits 0–14 the argument count | result (invalid for `void`) | function | start of the arguments in the value pool |
| `br` | none | none | start of its edge | none |
| `br_if` | none | condition | start of its two edges, true then false | none |
| `switch` | none | value | start of its edges, default first | case count |
| `ret` | none | value (invalid in a `void` function) | none | none |

- **Arithmetic** wraps modulo 2³², with no overflow flags. `sdiv` and `srem` truncate toward zero and `srem` takes the sign of the dividend. `ashr` shifts in the sign bit and `lshr` zeros (ADR 0005).
- **`icmp`** takes one of `eq ne slt sle sgt sge ult ule ugt uge` and yields `i32` 1 or 0. FIR has no boolean type. `br_if` and `switch` take any `i32`, and `br_if` goes to its first edge when its condition is non-zero. Instruction selection fuses a single-use `icmp` into the branch it feeds, and tests any other condition against zero.
- **No unary or select opcodes.** HIR's `neg` lowers to `sub 0, x` and `not` to `xor x, -1`. `cond`, `land` and `lor` lower to branches and a block parameter. There are no conversions, because there is one type.
- **Unspecified cases.** Division or remainder by zero, `sdiv` or `srem` of `INT_MIN` by −1, and shift counts outside 0–31 give an unspecified value. HIR → FIR passes them through, so on the slice's target they do what AArch64 does. These instructions are still pure.
- **Effects.** Arithmetic and `icmp` are pure. `load` reads memory, `store` writes it and `call` does both. An unused pure instruction or `load` may be dropped; a `store` or `call` may not. No layer may reorder `load`, `store` and `call` relative to each other.
- **Order.** Within a block, instructions run in array order, and an instruction may use only values defined earlier in its block or in a block that dominates it.

## Terminators and edges

Every block ends in exactly one terminator, and nothing else is a terminator. An **edge** is a record `{target block, arguments, case value}`: the arguments are a range of the value pool, and the case value is used only by the case edges of a `switch`.

- `br` has one edge. `br_if` has two, the true edge then the false edge. `switch` has the default edge first, then one edge per case, in HIR's table order.
- A `switch` always has a default edge: HIR's default label, or the block after the body when HIR has none. Case values are distinct 32-bit patterns, and there may be none. A `switch` goes to the case edge whose value equals its operand, otherwise to the default edge.
- An edge passes one argument for each parameter of its target block, in order. **All of an edge's arguments are read before any of the target's parameters take their new values**, so an edge may pass a block's own parameters to itself in a different order.
- Edges to the same block may repeat within one terminator, and each edge carries its own arguments.
- `ret` leaves the function. Every `return` in HIR is one `ret`: there is no merged exit block.

## Semantics

- **Entry block.** The entry block has no predecessors, and its parameters are the function's parameters, in order.
- **Unreachable blocks** are kept. Code after a `return`, `goto`, `break` or `continue` lowers to blocks with no predecessors, as HIR keeps that code. FIR has no pass that removes them.
- **Dominance** is checked only in blocks reachable from the entry block. Reads in a block with no predecessors give `undef`, so an unreachable region never refers to a value outside itself.
- **Minimality.** Block parameters are not minimal; see [Redundant cycles](#redundant-cycles).

## From HIR

HIR → FIR lowers one function at a time. It builds that function's body, finishes a block before it starts the next, and then verifies the body.

### Variables

- Every HIR **local** is a Braun variable. A body's parameter locals are defined in the entry block, each as the entry block's parameter in the same position, so FIR needs no store for them.
- `read_local` reads the variable in the current block and emits nothing itself. `assign` to a local defines the variable with its value and yields that value. `old` reads the target's variable where it sits. `post_assign` yields the variable's value just before the definition.
- A local read before any write finds `undef`.
- **Globals** aren't variables: see [Globals, calls and returns](#globals-calls-and-returns).
- A value that merges two edges but isn't a HIR local (the result of `land`, `lor` or `cond` used as a value) is a fresh variable of its own, written on each edge and read once in the join. Its block parameter has no name and takes the expression's location.

### Reading a variable

The construction state is kept in side tables owned by the lowering and dropped when the function is finished: each block's predecessors, which blocks are sealed, the current definition of each variable in each block, each unsealed block's incomplete parameters, each parameter's operands (one per predecessor), the users of each parameter, the alias table, the constants and the `undef` value.

Reading variable `v` in block `b`:

- If `b` defines `v`, that is the value, seen through the alias table.
- Otherwise, if `b` isn't sealed, a new parameter of `b` becomes the definition and is recorded as incomplete.
- Otherwise, with no predecessors, the value is `undef`; with one, it is the read of `v` at the end of that predecessor.
- Otherwise, with several, a new parameter of `b` becomes the definition first (which stops cycles), then its operands are read from every predecessor, then it is checked for being trivial.
- Whatever is found is recorded as `b`'s definition of `v`.

### Sealing

A block is sealed once all its predecessors are known, which completes its incomplete parameters.

- The entry block is sealed when it is created, and so is any block only the construct being lowered can reach: the `then` and `else` of an `if` or `cond`, a loop's body, and the `rhs` of `land` and `lor`.
- The `join` of an `if`, `cond`, `land` or `lor` is sealed when both arms are finished.
- At the end of a loop's body, once its `continue`s and `break`s are known, its `step` or `test` block, its back-edge target and its exit are sealed. A `switch`'s exit is sealed at the end of its body.
- An unnamed label (a `case` or `default`) is sealed when its `label` statement is reached: its predecessors are the `switch` edges to it plus the fall-through.
- **A named label is sealed at the end of the function**, because a later backward `goto` can add a predecessor. There is no pre-pass counting jumps, so reads below a named label go through incomplete parameters that are completed at the end.

### Removing trivial block parameters

A parameter is trivial when its operands, seen through the alias table and leaving out itself, are at most one value. Construction replaces it with that value (or with `undef` when there is none) by recording an alias, marking the value `removed`, and checking the trivial-parameter test again for every parameter that used it.

- The users are kept in a side table for block parameters only, mapping a parameter to the parameters whose operands include it. This is Braun's recursion, linear in the parameters, without the use-lists that ADR 0011 rules out.
- Nothing else is rewritten while the function is built. Instruction operands may name a removed parameter until the end of the function, and every read goes through the alias table.

### Redundant cycles

FIR runs no SCC pass, so it accepts **redundant cycles of block parameters on any CFG**: parameters that only feed each other and one outside value. Irreducible CFGs produce them, such as `k` in the `goto` example below. Reducible ones do too, whenever two paths pass the same value:

```c
x = y;
while (c) { if (d) x = y; }
```

Here the loop header's and the join's parameters for `x` each take the other and `y`. In a simulation of this algorithm over 4,000 random `if`/`while` programs, 4 ended with such a cycle when only copies counted, and 29 once interned constants counted too. The verifier doesn't check minimality. A lit test pins the `goto` example's output below, so adding the pass later shows up as a diff.

### End of a function

1. Seal every block still unsealed, which is the named labels.
2. One walk over the instruction array rewrites every value operand, call argument and condition through the alias table.
3. Each block's parameters, minus the removed ones, are written into the value pool and the block records. Each edge's arguments are then written into the pool: for every parameter of the edge's target, the value that parameter takes from the edge's block, seen through the alias table.
4. The side tables are dropped, and the verifier runs (Debug and RelWithAsserts).

### Control flow

A block is created the first time it is targeted or written to, and its id is its creation order. No block is empty or unterminated: after a terminator, no block exists until HIR has something more to lower, which then goes into a fresh block with no predecessors.

| HIR | FIR |
|---|---|
| `if` | a branch on the condition to `then` and `else`, or straight to `join` when there is no `else`; each arm that can fall through ends with `br join`; `join` is sealed after the arms |
| `loop`, tested first | `header` (the test) → `body` or `exit`; the body ends with `br step`, or `br header` with no step; `step` ends with `br header`; `continue` is `br step`, or `br header` with no step |
| `loop`, tested last | the block before it ends with `br body`; `body` → `step` → `test` → `body` or `exit`; `continue` is `br step`, or `br test` with no step |
| `loop`, no test | `body` → `step` → `body`; `exit` is reached only by `break`, `goto` or `return` |
| `switch` | a `switch` terminator in the current block; one block per label in the table, created in table order, default first; `break` is `br exit`, and the end of the body falls into `exit` |
| `label` | `br` into its block when the code before it can fall through; the label starts its block |
| `goto`, `break`, `continue` | `br` |
| `return` | `ret`, with the value if the function isn't void; `return undef.T` is `ret undef` |

- The entry block is never a branch target: when a function starts with a label or a loop, the entry block ends with `br` into it.
- A synthesized `br` takes the location of the statement that needed it: the `if`'s or loop's keyword, the `switch`'s keyword, or the label's.

### Conditions

A condition of an `if` or `loop` that is a `land`, a `lor` or a comparison is lowered straight to control flow. `branch(c, t, f)` lowers `c` from the current block to the blocks `t` and `f`:

- `land(a, b)` is `branch(a, rhs, f)`, then `branch(b, t, f)` in `rhs`.
- `lor(a, b)` is `branch(a, t, rhs)`, then `branch(b, t, f)` in `rhs`.
- A comparison is an `icmp` followed by `br_if` on it.
- Any other condition is evaluated to a value `v` and tested with `br_if v, t, f`.

So `if (a && b)` has no 0/1 value and no join parameter. Conditions aren't folded: HIR doesn't fold and FIR has no passes, so `while (1)` is `br_if 1, …`.

`land`, `lor` and `cond` used as a value become branches and a join with a parameter. `land(a, b)` branches on `a`, passing 0 to the join; `rhs` evaluates `b`, normalizes it with `icmp ne b, 0` (skipped when `b` is already a comparison, `land` or `lor`, which yield 0 or 1), and passes it. `lor` is the same with 1. `cond` joins the values of its two arms, or has no parameter when it is `void`.

### Expressions

| HIR | FIR |
|---|---|
| `const` | the interned constant |
| `read_local`, `old` of a local | a read of the variable |
| `read_global`, `old` of a global | `load` |
| `undef` | the `undef` value |
| `neg a`, `not a` | `sub 0, a`, `xor a, -1` |
| `add` `sub` `mul` `and` `or` `xor` `shl` | the same opcode |
| `div`, `rem` | `sdiv`/`srem` for `s32`, `udiv`/`urem` for `u32` |
| `shr` | `ashr` for `s32`, `lshr` for `u32` |
| `eq`, `ne` | `icmp eq`, `icmp ne` |
| `lt` `le` `gt` `ge` | `icmp` with the signed predicate for `s32`, the unsigned one for `u32` |
| `land`, `lor`, `cond` | branches and a join, as above |
| `seq a, b` | `a` is lowered and discarded, then `b` |
| `assign` to a local, `post_assign` to a local | a definition of the variable; `post_assign` yields the previous value |
| `assign` to a global | `store`, yielding the stored value |
| `post_assign` to a global | `load` just before the `store`, yielding the loaded value |
| `call` | `call`, after its arguments from left to right |
| `convert` | nothing: the operand's value |

Each instruction takes the location of the HIR node that made it. An `icmp ne` that normalizes `land` or `lor` takes the operator's location.

### Globals, calls and returns

- **Globals.** A defined global's initializer of 0 is `zerofill`, which is how HIR → FIR makes the global; any other initializer is kept as written. `load` and `store` name the global directly. No address value exists, because the subset has no `&`. A `post_assign` to a global emits its `load` for the previous value right before the `store`, even when its value is unused: instruction selection drops an unused `load`.
- **Calls.** `call` names its callee by `function_id`, evaluates the arguments first, and carries HIR's prototyped flag as `noproto` when it is clear. A prototyped call must match the callee's parameter count; a `noproto` call isn't checked, as in `int f(); f(1u, 2);`. A call to a `void` function defines no value.
- **Returns.** HIR ends every function with an explicit `return`, so HIR → FIR never makes up a terminator. A `void` function's `ret` has no operand.

## Locations

Every FIR entity has a location, following the rules in [docs/ir-data-layout.md](ir-data-layout.md#locations), with these choices:

- An **instruction** takes the location of the HIR node that made it. A **result value** stores none and takes its instruction's.
- A **block parameter** that stands for a HIR local takes that local's name and location, whether it is a function parameter or a join. A join made for the value of `land`, `lor` or `cond` has no name and takes the operator's location.
- A **block** has no name and no stored location: its location is its first instruction's, and every block has one because every block ends in a terminator.
- A **constant** or `undef` has none. They stand for no source entity, being shared by every use, and the location of a use is its instruction's. The verifier doesn't ask for one.

## Printed form

`-emit-fir` prints the module's globals in array order, then its functions in array order. A body is printed right after it has been built and verified, because the next function's lowering clears it. It prints no locations.

- **Sigils:** `%` for values, `@` for globals and functions, `bb` for blocks.
- **Values.** A function parameter prints its plain name, as in `%a`. Every other parameter that has a name prints `%name.N`, where `N` is its value index. A value with no name prints `%N`. Ids are indices and never renumbered, so removed parameters and constants leave gaps, and the blocks print in layout order, entry first, with their own ids.
- **Constants** print inline as signed decimal (`-1`, not `4294967295`), and `undef` prints as `undef`.
- **Types** follow the opcode on every instruction that isn't a terminator, after any predicate: `add i32 %a, %b`, `icmp slt i32 %a, 0`, `load i32 @g`, `store i32 @g, %v`, `call i32 @f(%a)`, `call void @g()`, `call noproto i32 @f(%x, %y)`. An instruction that defines a value is written `%N = …`. Terminators print no type.
- **Terminators:** `br bb3(%x, %y)`, `br_if %c, bb1(…), bb2(…)`, `switch %v, default bb9(…) [0: bb1(…), 1: bb2]`, `ret %v` and `ret`. An edge with no arguments prints its block alone.
- **Blocks** print as `bb3(%x.7: i32, %s.9: i32):`, or `bb3:` with no parameters, outdented from their instructions by two spaces.
- **Functions** print as `func @add(i32, i32) -> i32 { … }`, the entry block repeating the parameters with their names. A declaration prints its signature alone, as in `func @putchar(i32) -> i32`. A function without a prototype ends its signature with `noproto`, and a `void` one prints `-> void`.
- **Globals** print as `global @g = 5`, `global @hits = zerofill`, and `global @e` for a declaration.
- Internal functions and globals begin with `internal`. Module entities print as in HIR, with `.N` when a name repeats.

## Verifier

These checks run after the structural checks every verifier starts with ([docs/ir-data-layout.md](ir-data-layout.md#verification)), and only if those pass. The verifier runs after HIR → FIR in Debug and RelWithAsserts.

- **Edges**
  - The entry block has no predecessors.
  - Every edge passes exactly as many arguments as its target has parameters.
- **Terminators**
  - A `switch` has a default edge and distinct case values.
  - A `ret` carries a value exactly when its function isn't `void`.
- **Instructions**
  - Every operand follows its opcode's rule in [Instructions](#instructions), and every value operand has type `i32`.
  - A result's type matches its opcode, and a `void` instruction has no result.
  - A call's callee is a function of the module, and its type is the callee's return type. A prototyped call matches the callee's parameter count; a `noproto` call isn't checked.
  - `load` and `store` name a global of the module.
- **Values**
  - Every value is defined once: a `param` by exactly one block's list, a `result` by exactly the instruction its payload names.
  - No operand, argument or edge argument is `removed`.
  - No two constants share a bit pattern, and there is at most one `undef`.
- **Globals**
  - A declared global has no initializer, and a defined global is `zerofill` exactly when its initializer is 0.
  - Every internal global or function that is referenced is defined.
- **Dominance**
  - Every use of a `param` or `result` is dominated by its definition, in blocks reachable from the entry. An edge's arguments are used at the end of the edge's block. Constants and `undef` are exempt, and so is everything in a block with no path from the entry.
- **Not checked:** that block parameters are minimal, and that every block is reachable.

## What FIR removes, and what MIR receives

ADR 0008 asks each layer to say which lowering removes the structure it adds. FIR → MIR removes target independence; the CFG, the values and the block parameters all survive into MIR, which is still SSA. Register allocation removes the block parameters and the SSA values.

What MIR's design has to handle:

- **Critical edges** can carry arguments, so the register allocator puts an edge's moves in a new block when they aren't all no-ops ([ADR 0013](adr/0013-every-fir-edge-carries-its-own-block-arguments.md)).
- **Constants and `undef` are values with no definition.** Instruction selection chooses between an immediate, `movz`/`movk`, and any register for `undef`.
- **`switch`** reaches instruction selection as one terminator with edges that carry arguments.
- **Dead code** is dropped by instruction selection's backward walk: unused pure instructions and unused `load`s, including the extra `load` of a global `post_assign`.
- **Memory order** is array order for `load`, `store` and `call`.
- **Layout** is FIR's block layout, and unreachable blocks are in it.

## Worked examples

Ids come from creation order, so they have gaps: a read creates a block parameter on demand (and some are removed later), and constants and `undef` take an id the first time they are used. `docs/ir-data-layout.md` shows `add` in memory.

`int add(int a, int b) { return a + b; }`:

```
func @add(i32, i32) -> i32 {
bb0(%a: i32, %b: i32):
  %2 = add i32 %a, %b
  ret %2
}
```

A loop:

```c
int sum(int n) {
  int s = 0;
  while (n > 0) { s += n; n -= 1; }
  return s;
}
```

```
func @sum(i32) -> i32 {
bb0(%n: i32):
  br bb1(%n, 0)
bb1(%n.2: i32, %s.4: i32):
  %3 = icmp sgt i32 %n.2, 0
  br_if %3, bb2, bb3
bb2:
  %5 = add i32 %s.4, %n.2
  %7 = sub i32 %n.2, 1
  br bb1(%7, %5)
bb3:
  ret %s.4
}
```

Values 1 and 6 are the constants `0` and `1`, which print inline.

The `classify` function from [docs/hir.md](hir.md#worked-examples), with a `switch`, a `goto`, `&&` and a global:

```
global @hits = zerofill

func @classify(i32, i32) -> i32 {
bb0(%x: i32, %y: i32):
  switch %x, default bb1(0) [0: bb2, 1: bb3]
bb2:
  %3 = icmp ult i32 %x, %y
  br_if %3, bb4, bb5
bb4:
  %5 = icmp ne i32 %y, 7
  br_if %5, bb6, bb5
bb6:
  br bb7(0)
bb5:
  br bb8(1)
bb3:
  %7 = add i32 0, %y
  br bb1(%7)
bb1(%r.13: i32):
  %8 = load i32 @hits
  %9 = add i32 %8, 1
  %10 = load i32 @hits
  store i32 @hits, %9
  br bb8(%r.13)
bb8(%r.12: i32):
  br bb7(%r.12)
bb7(%r.11: i32):
  ret %r.11
}
```

`bb1` is `default` and the fall-through from `case 1`, so the `switch` edge to it passes the `0` that `r` holds there, and `bb3`'s edge passes `r + y`. `bb2` and `bb3` have no parameters: each has one predecessor, so a read of `r` goes through to the entry's `0`. Ids are creation order and the layout follows the code, so `bb5` (the `if`'s join, made by the first `br_if`) is laid out after `bb6`, and `bb7` (`done`, made by the `goto`) comes last. `%10` is the previous value that `hits++` would yield; nothing uses it.

A loop with a `goto` into its body, the CFG's only irreducible shape:

```c
int f(int n, int k, int skip) {
  int s = 0;
  if (skip) goto in;
  while (n > 0) {
    s += 1;
  in:
    n -= k;
  }
  return s;
}
```

```
func @f(i32, i32, i32) -> i32 {
bb0(%n: i32, %k: i32, %skip: i32):
  br_if %skip, bb1, bb2
bb1:
  br bb3(%n, %k, 0)
bb2:
  br bb4(%n, 0, %k)
bb4(%n.4: i32, %s.6: i32, %k.13: i32):
  %5 = icmp sgt i32 %n.4, 0
  br_if %5, bb5, bb6
bb5:
  %8 = add i32 %s.6, 1
  br bb3(%n.4, %k.13, %8)
bb3(%n.9: i32, %k.10: i32, %s.12: i32):
  %11 = sub i32 %n.9, %k.10
  br bb4(%11, %s.12, %k.10)
bb6:
  ret %s.6
}
```

The loop has two entries, `bb4` and `bb3` (the label `in`), so neither dominates the other. Both need `n` and `s`, but `k` is never written: `%k.13` and `%k.10` take each other and `%k`, which makes them a redundant cycle that FIR keeps. The label `in` is named, so `bb3` is sealed last. That is why `%k.13` has the highest id: it is created when sealing `bb3` asks the loop header for `k`.
