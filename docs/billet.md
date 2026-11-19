# Billet

Billet is Forge's SSA representation, shared by every language and target (ADR 0007). This page lists its types and instructions and how they carry calling-convention and aliasing information. [ADR 0011](adr/0011-billet-types-and-instructions.md) records why. What a module holds besides functions (globals, linkage, attributes, and the module-level tables named below) is decided in [What does a Billet module contain?](https://github.com/jmuratov98/forge/issues/27).

## Types

| Type          | Meaning                                                                                                                       |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `iN`          | Signless integer, 1 ≤ N ≤ 65535. `i1` is the boolean type. Signedness belongs to operations, never to the type.               |
| `f16` `bf16` `f32` `f64` `f80` `f128` | IEEE half, bfloat16, single, double, x87 extended, and IEEE quad. The frontend picks `long double`'s type from the target. |
| `ptr`         | An opaque address, as wide as the data layout says. There are no address spaces.                                             |
| `<N x T>`     | Fixed-length vector of integers, floats, or `ptr`. There are no scalable vectors.                                            |
| aggregate     | A layout describing memory. Never an SSA value.                                                                               |

### Aggregates

An aggregate type is a size, an alignment, and a list of fields. Each field has a byte offset and a type, which is a scalar, a vector, another aggregate, or an array `[N x T]`.

- **Unions** are fields that overlap.
- **Bitfields** appear as the integer type of their storage unit.
- **Padding** is whatever no field covers. **Packing** is just a smaller alignment.
- A **`complex`** marker distinguishes `_Complex T` from a struct of two `T`s, which some conventions pass differently.

Aggregate types are structural: two identical layouts are the same type. A name such as `type %Point = …` is a printing alias only.

Calling-convention lowering classifies arguments by reading these fields. Rules from the source language that change how a type is passed are the frontend's job. For example, the C++ frontend passes a type that is non-trivial for the purposes of calls through an explicit pointer.

Aggregates live in stack slots and globals, and are copied with `memcpy`. A call takes an aggregate as a by-value operand that names its type and address. An aggregate return names a **result slot**.

### Constants

Every value is an instruction result or a block parameter, so constants are instructions too: `iconst`, `fconst`, `null`, and `poison`. Instruction selection folds them into immediates. Float constants are stored as bit patterns and folded with core's software floating point (ADR 0005).

## Undefined behavior

- There is **poison** and no `undef`. `freeze` turns poison into an arbitrary but fixed value.
- `nsw`, `nuw`, and `exact` flags make overflow or inexact results poison.
- Integer division by zero and `INT_MIN / -1` are **immediate UB**, as are loads, stores, and calls through invalid pointers.
- Other out-of-range results are poison. Examples are a shift amount of at least the width, and a float-to-int conversion that doesn't fit.

## Instructions

| Group              | Instructions                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------------- |
| Constants          | `iconst` `fconst` `null` `poison`                                                                  |
| Integer            | `iadd` `isub` `imul` `sdiv` `udiv` `srem` `urem` `ineg` `band` `bor` `bxor` `bnot` `shl` `ushr` `sshr` |
| Float              | `fadd` `fsub` `fmul` `fdiv` `fneg`                                                                 |
| Compare and select | `icmp` `fcmp` `select` `freeze`                                                                    |
| Convert            | `trunc` `zext` `sext` `fptrunc` `fpext` `fptosi` `fptoui` `sitofp` `uitofp` `bitcast` `ptrtoint` `inttoptr` |
| Memory             | `load` `store` `atomic.rmw` `cmpxchg` `fence`                                                      |
| Addresses          | `ptr.add` `stack.addr` `alloca` `symbol.addr`                                                      |
| Vectors            | `extractlane` `insertlane` `shuffle` `splat`                                                       |
| Calls              | `call` `call_indirect` `intrinsic` `asm`                                                           |
| Terminators        | `br` `br_if` `switch` `br.indirect` `return` `unreachable` `try_call`                              |

- Integer and float instructions work on vectors lane by lane. Comparisons of vectors produce `<N x i1>`.
- `icmp` predicates: `eq ne slt sle sgt sge ult ule ugt uge`. `fcmp` has ordered and unordered forms of each relation.
- Rotates, bit counting, byte swaps, `fma`, `sqrt`, `copysign`, `min`, and `max` are intrinsics. `fmod` is a library call.
- An instruction can define several results: `cmpxchg` gives `(old, i1)`, and the overflow intrinsics give `(iN, i1)`. A function returns at most one value.
- `br.indirect` lists every block it can reach. It implements GNU `&&label`.
- `asm` holds the template, constraints, operands, and clobbers. fas parses it when Billet is lowered to Blank.

### Memory

- `load` and `store` carry an alignment, an optional `volatile`, an optional atomic ordering, and an optional alias class.
- Atomic orderings are C11's (`relaxed`, `acquire`, `release`, `acq_rel`, `seq_cst`). A single-thread scope implements `atomic_signal_fence`.
- Any non-aggregate type can be loaded or stored except `i1`. `_Bool` is `i8` in memory, and other `iN` occupy their storage size from the data layout.
- Addresses are computed only with `ptr.add base, byte_offset`. Ingot has already resolved every offset and stride.

### Stack memory

A function declares fixed-size **stack slots** in its header, each with a size, an alignment, and optionally an aggregate type. `stack.addr` takes a slot's address. `alloca` allocates dynamically sized memory, for VLAs and `alloca()`. At -O0 every local is a stack slot.

## Calls

`call` is an ordinary instruction. Unless it is marked `nounwind`, it may unwind, which propagates to the caller.

`try_call` is a terminator with a normal successor and an unwind successor. Its results arrive as block arguments of the normal successor. What the unwind successor receives, and how MSVC funclets mark their scope, are left to the exception model, which is designed before M7.

Calling-convention lowering runs after Billet, so every call (direct, indirect, `try_call`) carries a full **signature**:

- the parameter and result types, with aggregate operands typed as above
- the number of **fixed parameters**, which decides where variadic arguments start (Apple arm64 puts them all on the stack)
- `sext` and `zext` flags on narrow integer parameters and results
- `noalias` on pointer parameters, for `restrict`
- a **convention** selector, which defaults to the target's C convention

`va_list` is plain memory, with its size and alignment from the data layout. `va_start`, `va_arg`, `va_copy`, and `va_end` are intrinsics taking a `ptr` to it, and only calling-convention lowering reads what's inside.

## Intrinsics

An intrinsic is its own instruction, `intrinsic <name>(args) -> results`. It is never a call to a reserved symbol. One registry records each intrinsic's type rules, memory effects, and whether it can unwind. The generic intrinsics include `memcpy`, `memset`, `memmove`, the `va_*` intrinsics, `trap`, `assume`, `expect`, `fmuladd`, `stacksave`, `stackrestore`, the overflow arithmetic, and the bit operations.

**Target intrinsics** are named by ISA (`aarch64.neon.sdot`). A module that uses one can be compiled only for a target with that ISA, and generic passes treat it as an opaque operation with the effects it declares. Each ISA library registers its own intrinsics, so `billet` never names a target.

## Data on instructions

There is no generic metadata. Every field an instruction carries is defined by Billet:

- its source location
- flags: `nsw`, `nuw`, `exact`, `volatile`, `nounwind`, and the fast-math flags
- an alignment
- an atomic ordering
- an alias class

The fast-math flags are LLVM's seven: `nnan ninf nsz arcp contract afn reassoc`. Every floating-point operation assumes the default floating-point environment.

Contraction follows `#pragma STDC FP_CONTRACT` and `-ffp-contract`, the way clang does it:

- `on` (clang's default): the C frontend emits the `fmuladd` intrinsic for each multiply and add within one expression. `fmuladd` is fused or not as the target decides, and that decision is fixed per target, so output doesn't depend on the host (ADR 0005). arm64 always fuses.
- `fast`: the frontend sets `contract` on `fmul` and `fadd`, which allows fusing across expressions.
- `off`: neither.

A Billet source location is a file, a line, and a column, with an inlining scope to come. It keeps what DWARF line tables need and no macro expansion stack.

## Aliasing

A load, store, or memory intrinsic can carry an **alias class**, which is an id into the module's **alias tree**. The tree's root means "may alias anything".

Which access gets which class is a language rule: C's effective type, C++'s dynamic type, `char`, `std::byte`, `may_alias`, and union punning. The frontends build the classes, Ingot carries them unread on its memory accesses, and Ingot → Billet copies them over. With `-fno-strict-aliasing`, or at -O0, there are no classes.

`restrict` is `noalias` on a parameter. Scoped noalias, which matters once functions are inlined, is designed together with the inliner in M5, as are the alias tree's node kinds.

## Data layout

Billet reads these from the data layout:

- endianness
- pointer width
- the storage size and ABI alignment of each scalar type
- the size and alignment of `va_list`

Loads, stores, and stack slots still state their alignment explicitly. Which types are **legal** on a target is part of the target description, which legalization reads. How a target triple produces a data layout is decided with the target description too.

## Text format

The text format round-trips. Its conventions:

- `%name` for values, `^name` for blocks, `@name` for symbols, and a type after each definition.
- A function's parameters are its entry block's parameters.
- One instruction per line, ending in `loc(<file>:<line>:<col>)`, which refers to the module's file table.
- Floats are printed as hex floats, or as raw bits where a hex float can't show the value (for example, NaN payloads). They are never printed in decimal.

The exact grammar is written along with the parser, as part of Milestone 1.

```
file 0 "sum.c"

func @sum(ptr, i32) -> i32 {
^entry(%a: ptr, %n: i32):
  %z: i32 = iconst 0                      loc(0:2:11)
  br ^loop(%z, %z)                        loc(0:3:3)
^loop(%i: i32, %acc: i32):
  %done: i1 = icmp sge %i, %n             loc(0:3:19)
  br_if %done, ^exit(%acc), ^body         loc(0:3:3)
^body:
  %off: i64 = sext %i                     loc(0:4:12)
  %off4: i64 = imul %off, 4               loc(0:4:12)
  %p: ptr = ptr.add %a, %off4             loc(0:4:12)
  %x: i32 = load align 4 %p               loc(0:4:12)
  %acc2: i32 = iadd nsw %acc, %x          loc(0:4:9)
  %one: i32 = iconst 1                    loc(0:3:24)
  %i2: i32 = iadd nsw %i, %one            loc(0:3:24)
  br ^loop(%i2, %acc2)                    loc(0:3:3)
^exit(%r: i32):
  return %r                               loc(0:5:3)
}
```

## Not yet decided

Each of these can be added without breaking anything:

- the alias tree's contents and scoped noalias (M5)
- strict FP and `FENV_ACCESS`
- scalable vectors
- guaranteed tail calls (`musttail`)
- multiple return values for functions
