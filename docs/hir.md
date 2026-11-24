# HIR

What HIR holds in the first slice, what it means, how it is printed and what its verifier checks. HIR is the language-independent, non-SSA layer between each frontend's AST and FIR ([ADR 0008](adr/0008-five-fixed-ir-layers-each-lowering-removes-one-kind-of-structure.md)). AST → HIR removes the source language's syntax and implicit rules: names are resolved to entities, every conversion is a node, and HIR → FIR has nothing left to infer from C. Control flow stays structured, with `goto` and labels. Storage follows [docs/ir-data-layout.md](ir-data-layout.md) and isn't restated here; terms follow [GLOSSARY.md](../GLOSSARY.md).

## Entities

The HIR module is the only container. It lives for the translation unit, keeps every body, and is built once by AST → HIR and never edited afterwards.

| Entity | Id | Record | Columns |
|---|---|---|---|
| function | `function_id` | return type, flags (internal, defined, prototyped), parameter-type range, body (invalid for a declaration) | name, location |
| global | `global_id` | type, flags (internal, defined), initializer value | name, location |
| body | `body_id` | root block, first local, first label | none: its location is its function's |
| local | `local_id` | type | name, location |
| label | `label_id` | none | name (invalid when unnamed), location |
| statement | `stmt_id` | kind, flags, three 32-bit fields | location |
| expression | `expr_id` | kind, type, flags, three 32-bit fields | location |

- **Pools:** `std::vector<stmt_id>` (block contents), `std::vector<expr_id>` (call arguments), `std::vector<switch_case>` (switch tables) and `std::vector<type>` (parameter types).
- **Bodies.** A body's locals begin with its parameters, in order. Its locals and its labels each run up to where the next body's begin, or to the end of the array. AST → HIR lowers one function at a time, so each range is contiguous and a body needs to store only where it starts.
- **Statements and expressions** are separate arrays with their own ids, so a statement can't be used as an operand. Only expressions have a type. An expression statement is an `eval` statement.
- **Names** are interned-string ids. For functions and globals the name is the linkage name; its spelling as a symbol (`_add`) is MCIR's. Names don't have to be unique: two blocks of one function can each hold a `static int n`.
- **Records** fit in 16 bytes. Two need care. A `switch` keeps its case count and default label in its table's first entry (see [Statements](#statements)), and a body stores only where its locals and labels start.

## Types

`s32`, `u32` and `void`, as a `std::uint8_t` `enum class`. The integer types are 32-bit two's complement. Locals and globals are `s32` or `u32`. `void` is only a function's return type and the type of expressions built on calls to void functions. "Integer" below means `s32` or `u32`.

## Statements

| Kind | Fields | Meaning |
|---|---|---|
| `block` | statement range | Runs its statements in order. A block never directly contains a block. |
| `eval` | expression | Evaluates the expression and discards its value. |
| `if` | condition, then block, else block (invalid when absent) | |
| `loop` | test (none, first or last), condition (invalid when there is no test), body block, step expression (invalid when absent) | See below. |
| `switch` | controlling expression, body block, case table start | See below. |
| `label` | label | Marks where the label is. Falling into it does nothing. |
| `goto` | label | Jumps to the label. |
| `break` | none | Leaves the innermost enclosing loop or switch. |
| `continue` | none | Goes to the innermost enclosing loop's step, then its test. |
| `return` | expression (invalid in a void function) | |

**Loop.** A loop tested first evaluates its condition before each iteration and leaves when it is zero. A loop tested last runs its body, then its step, then its test. A loop with no test runs until a `break`, `goto` or `return` leaves it. After the body, and on `continue`, the step runs and then the test.

**Switch.** A table entry is `switch_case { std::uint32_t value; label_id target; }`. The first entry is a header: its value is the number of cases, and its target is the default label, invalid when there is no default. The cases follow it. A switch evaluates its controlling expression and jumps to the label of the case whose value equals it, otherwise to the default label, otherwise past the body. Each case value has the controlling expression's type.

## Expressions

| Kind | Operands | Type |
|---|---|---|
| `const` | the value's bits | `s32` or `u32` |
| `read_local`, `read_global` | the local or global | its type |
| `old` | none | the target's type of the nearest enclosing `assign` or `post_assign` |
| `undef` | none | `s32` or `u32` |
| `neg`, `not` | a | T → T |
| `add`, `sub`, `mul`, `div`, `rem`, `and`, `or`, `xor` | a, b | T, T → T |
| `shl`, `shr` | a, b | T, any integer → T |
| `eq`, `ne`, `lt`, `le`, `gt`, `ge` | a, b | T, T → `s32`; the record's type field holds T |
| `land`, `lor` | a, b | any integers → `s32` |
| `cond` | condition, a, b | any integer; T, T → T, where T may be `void` |
| `seq` | a, b | anything, T → T |
| `assign`, `post_assign` | target (a local or a global, told apart by a flag), value | the target's type T: T → T |
| `call` | function, argument range, a prototyped flag | the callee's return type |
| `convert` | a | `s32` → `u32` or `u32` → `s32`; the record's type is the target |

- `not` is bitwise. `div`, `rem`, `shr` and the comparisons take their signedness from T: signed `div` truncates toward zero, signed `rem` takes the sign of the dividend, and `shr` on `s32` is arithmetic ([ADR 0005](adr/0005-forge-defines-its-own-implementation-defined-behaviour.md)).
- Comparisons, `land` and `lor` yield 0 or 1. `land` and `lor` evaluate their right operand only when the left one doesn't decide the result.
- `cond` evaluates only the arm it chooses. `seq` evaluates `a`, discards it and yields `b`.
- `assign` evaluates its value, stores it in the target and yields it. `post_assign` does the same but yields the value the target held before.
- `old` reads the target of the nearest enclosing `assign` or `post_assign` at the point where `old` is evaluated. Read-modify-write is built from these three nodes ([ADR 0012](adr/0012-hir-read-modify-write-reads-its-target-through-an-old-leaf.md)).
- `convert` keeps the 32 bits and changes only the type, so an out-of-range value wraps (ADR 0005).
- `undef` is an unspecified value and appears only as a `return` operand.
- A call whose prototyped flag is clear passes its arguments at their own types, and its argument count isn't checked against the callee. A function's prototyped flag says whether it has a prototype. The call's flag says whether sema checked that call against one, because a later definition can give a function a prototype after an earlier call was checked without it.

## Semantics

- **Evaluation order.** Children are evaluated left to right, call arguments before the call, and `old` where it sits in that order. C leaves the order unspecified, so Forge picks one.
- **Arithmetic** wraps modulo 2³².
- **Undefined:** division or remainder by zero, `s32` division or remainder of `INT_MIN` by −1, and shift counts outside 0–31. HIR → FIR passes them through, so they do what AArch64 does.
- **Conditions** of `if`, `loop`, `cond`, `land` and `lor` are any integer, true when non-zero.
- **A local read before any assignment** gives an unspecified value. It becomes FIR's `undef` during SSA construction, and HIR has no node for it.

## From the AST

AST → HIR is mechanical. It does no folding, not even of a conversion applied to a constant, and it keeps unreachable code and expression statements without side effects.

| C | HIR |
|---|---|
| nested `{ … }` | flattened into the enclosing list |
| `;` | nothing |
| `int x;`, `auto`, `register` | nothing: the local exists in its body |
| `int x = e;` | `eval assign(%x, e)` where the declaration was |
| block-scope `extern` or function declaration | nothing: names resolve to the module's entities |
| `static int n` in `f` | an internal global named `f.n` |
| `while (c) s` | `loop`, tested first |
| `do s while (c);` | `loop`, tested last |
| `for (i; c; s) b` | `eval i`, then a `loop` tested first (no test when `c` is absent) with step `s` |
| `switch` | a table and unnamed labels |
| `case v:`, `default:` | a `label` statement for an unnamed label in the switch's table |
| `L:` | a `label` statement |
| a conversion sema applied that changes the type | `convert` |
| a cast to the same type, unary `+` | nothing |
| `!x` | `eq.T(x, 0)`, with a 0 of `x`'s type |
| `x op= e` | `assign(x, op.C(old, e))`, where `C` is the computation type, with `convert` wherever a type changes. For shifts, `C` is `x`'s type and `e` keeps its own. |
| `++x`, `--x` | `assign(x, add.T(old, 1))`, `assign(x, sub.T(old, 1))`, with a 1 of `x`'s type |
| `x++`, `x--` | the same with `post_assign` |
| `(f)(x)` | a call of `f` |

**Globals.** A defined global always carries an initializer value, which is 0 when none was written, so `int g;` and `int g = 0;` are the same in HIR. HIR → FIR makes a global whose initializer is 0 zerofill. A global or function is external or internal, and declared or defined.

**Labels.** A named label is created at its first `goto` or at its definition, whichever comes first. A `case` or `default` label is created when AST → HIR reaches it.

**Returns.** Unless a function's last top-level statement is already a `return`, AST → HIR appends one:

- `return` in a void function
- `return 0` in `main`
- `return undef.T` in any other function

A `return;` written in a non-void function becomes `return 0` in `main` and `return undef.T` elsewhere. Every function therefore ends in a `return`, and HIR → FIR never has to make up a terminator.

## Locations

Every entity has a location, following the rules in [docs/ir-data-layout.md](ir-data-layout.md#locations).

- An operator takes the location of its operator token, a call the location of its callee's name, and a constant or read the location of its own token.
- A `convert` takes the location of its operand.
- `old`, and the arithmetic node of a compound assignment or `++`/`--`, take the operator's location, as does the synthesized 1.
- An `eval` takes its expression's location, a loop its keyword's, a block its `{`, and a label its name, `case` or `default`.
- A local or a global takes its declarator's location, including a hoisted `static` local.
- An appended `return`, with its `0` or `undef`, takes the function's closing brace.

## Printed form

`-emit-hir` prints the module once AST → HIR has finished: the globals in array order, then the functions in array order. It prints no locations. HIR is built for the whole translation unit before any of it is lowered, and a hoisted `static` local only appears when its function is lowered, so the globals can't be printed first any earlier.

- **Sigils:** `%` for locals, `@` for globals and functions, `^` for labels. Source identifiers such as `add` or `s32` can't be mistaken for HIR's own words.
- **Names** are shown wherever an entity has one. When a name occurs more than once among a function's locals, or among the module's globals and functions, every entity with it prints `.N` after the name, where `N` is its id. An unnamed label prints as `^N`.
- **Type suffixes** appear only where the type selects the operation: `neg`, `not`, the arithmetic, bitwise and shift operators, the comparisons (with their operand type), `convert` and `undef`.
- **Constants** print as `5` for `s32` and `5u` for `u32`.
- **Expressions** are prefix: `add.s32(%a, %b)`, `land(a, b)`, `cond(c, a, b)`, `seq(a, b)`, `assign(%x, v)`, `post_assign(%x, v)`, `call @f(a, b)`, `old`. A call whose prototyped flag is clear prints `call noproto @f(…)`.
- **Statements** are one per line, indented two spaces per level. An `eval` prints as its expression. Labels are outdented one level from the list they mark. Then:
  - `if c { … } else { … }`, with no `else` when there is no else block
  - `loop while c step s { … }`, `loop { … } while c` for a loop tested last, and `loop { … }` for a loop with no test
  - `switch e [0: ^0, 1: ^2, default: ^3] { … }`, with each case value printed as a constant of the controlling type
  - `goto ^L`, `break`, `continue`, `return` and `return e`
- **Functions** print as `func @add(%a: s32, %b: s32) -> s32 { … }` with their non-parameter locals as `local %r: s32` lines at the top of the body. A declaration prints its parameter types alone, as in `func @putchar(s32) -> s32`, with no body. A function without a prototype ends its signature with `noproto`.
- **Globals** print as `global @g: s32 = 5`. A declaration has no initializer, as in `global @e: s32`.
- Internal functions and globals begin with `internal`.

## Verifier

These checks run after the structural checks every verifier starts with ([docs/ir-data-layout.md](ir-data-layout.md#verification)), and only if those pass. The verifier runs after AST → HIR in Debug and RelWithAsserts.

- **Tree**
  - Every statement and expression has exactly one parent, except a body's root block, which belongs to its body, and its id is smaller than its parent's.
  - No statement or expression is shared between functions.
  - No block directly contains a block.
  - The root block of every body ends in a `return`.
- **Types**
  - Every expression's operands follow its kind's rule in [Expressions](#expressions). Conditions are integers, and a `convert` changes the type.
  - A `void` expression is only a call, an `eval`'s expression, either side of a `seq`, or an arm of a `void` `cond`.
  - No local is `void`, and a body's parameter locals have the types in its function's signature.
- **Assignment and return**
  - An `assign` or `post_assign` value has its target's type.
  - `old` appears only inside the value of an `assign` or `post_assign`, and has the type of the nearest enclosing target.
  - `undef` appears only as a `return` operand.
  - A `return` carries a value exactly when its function isn't void, and the value has the function's return type.
- **Calls**
  - The callee is a function of the module, and the call's type is its return type.
  - A call whose prototyped flag is set has a callee with a prototype, and matches its parameter count and types.
- **References and control**
  - Locals and labels are referenced only from their own function.
  - Every label is marked by exactly one `label` statement, and named labels are unique within their function.
  - `break` is inside a loop or switch, and `continue` is inside a loop.
- **Switch**
  - The controlling expression is an integer.
  - Case values are distinct.
  - Every label in the table, the default included, is marked inside the switch's body. Lowering doesn't need this check, but it catches an AST → HIR bug that gives a case to the wrong switch.
- **Module**
  - External globals and functions have unique names.
  - A declared global has no initializer, and a declared function has no body.
  - Every internal global or function that is referenced is defined.

## What HIR → FIR removes

ADR 0008 asks each layer to say which lowering removes the structure it adds. HIR → FIR removes all of it:

- structured statements and labels, which become a CFG
- locals, `assign`, `post_assign` and `old`, which become SSA values
- `land`, `lor` and `cond`, which become branches
- `convert`, which disappears, because FIR's `i32` has no signedness
- HIR's `undef`, which becomes FIR's

## Worked examples

`int add(int a, int b) { return a + b; }`, with locations written as `line:col`:

```
HIR    module "t.c"
         functions  [0] add  (s32, s32) -> s32  external defined prototyped  types[0,2)  body b0   1:5
         bodies     [0] root s1  locals from l0  labels from 0
         locals     [0] a  s32                   1:13
                    [1] b  s32                   1:20
         exprs      [0] read_local  l0           1:32
                    [1] read_local  l1           1:36
                    [2] add.s32     e0 e1        1:34
         stmts      [0] return      e2           1:25
                    [1] block       pool[0,1)    1:23
         pool<stmt_id>  [s0]
         pool<type>     [s32 s32]

printed  func @add(%a: s32, %b: s32) -> s32 {
           return add.s32(%a, %b)
         }
```

A `switch`, a `goto` and `&&`, with a usual arithmetic conversion, a compound assignment and a postfix `++` on a global:

```c
unsigned hits;

int classify(int x, unsigned y) {
  int r = 0;
  switch (x) {
  case 0:
    if (x < y && y != 7)
      goto done;
    r = 1;
    break;
  case 1:
    r += y;
  default:
    hits++;
  }
done:
  return r;
}
```

```
global @hits: u32 = 0

func @classify(%x: s32, %y: u32) -> s32 {
  local %r: s32
  assign(%r, 0)
  switch %x [0: ^0, 1: ^2, default: ^3] {
  ^0:
    if land(lt.u32(convert.u32(%x), %y), ne.u32(%y, convert.u32(7))) {
      goto ^done
    }
    assign(%r, 1)
    break
  ^2:
    assign(%r, convert.s32(add.u32(convert.u32(old), %y)))
  ^3:
    post_assign(@hits, add.u32(old, 1u))
  }
^done:
  return %r
}
```

Label `^1` is `done`, created by the `goto` before `case 1` is reached. The switch's table is `[{2, ^3} {0, ^0} {1, ^2}]`: a header with two cases and the default `^3`, then the cases.

Loops:

```c
unsigned sum(unsigned n) {
  unsigned s = 0, i;
  for (i = 0; i < n; i++)
    s += i;
  do --n; while (n > 10);
  return s;
}
```

```
func @sum(%n: u32) -> u32 {
  local %s: u32
  local %i: u32
  assign(%s, convert.u32(0))
  assign(%i, convert.u32(0))
  loop while lt.u32(%i, %n) step post_assign(%i, add.u32(old, 1u)) {
    assign(%s, add.u32(old, %i))
  }
  loop {
    assign(%n, sub.u32(old, 1u))
  } while gt.u32(%n, convert.u32(10))
  return %s
}
```
