# Billet

Billet is Forge's SSA representation, shared by every language and target (ADR 0007). This page lists its types and instructions, how they carry calling-convention and aliasing information, and what a module holds besides functions. [ADR 0011](adr/0011-billet-types-and-instructions.md) and [ADR 0014](adr/0014-what-a-billet-module-holds.md) record why.

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
| Addresses          | `ptr.add` `stack.addr` `alloca` `symbol.addr` `tls.addr`                                           |
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

A Billet instruction's source location is a **debug location**: a file, a line, and a column, with an inlining scope to come. It keeps what DWARF line tables need and no macro expansion stack. How Ingot → Billet produces it is in [source.md](source.md#below-the-ast).

## Aliasing

A load, store, or memory intrinsic can carry an **alias class**, which is an id into the module's **alias tree**. The tree's root means "may alias anything".

Which access gets which class is a language rule: C's effective type, C++'s dynamic type, `char`, `std::byte`, `may_alias`, and union punning. The frontends build the classes, Ingot carries them unread on its memory accesses, and Ingot → Billet copies them over. With `-fno-strict-aliasing`, or at -O0, there are no classes.

`restrict` is `noalias` on a parameter. Scoped noalias, which matters once functions are inlined, is designed together with the inliner in M5, as are the alias tree's node kinds.

## Data layout

Billet reads these from the data layout, which the module's [header](#header) states:

- endianness
- pointer width
- the storage size and ABI alignment of each scalar type
- the size and alignment of `va_list`

Loads, stores, and stack slots still state their alignment explicitly. Which types are **legal** on a target is part of the target description, which legalization reads. How a target triple produces a data layout is decided with the target description too.

## Modules

A module is one translation unit: its functions, globals, aliases, and ifuncs, plus the module-level tables they refer to. [ADR 0014](adr/0014-what-a-billet-module-holds.md) records why it has this shape.

### Header

The header makes a module self-contained, so a `.billet` file compiles the same way whatever command line reads it:

- the **target triple**, including the OS version (`arm64-apple-macosx14.0.0`), which Mach-O's `.build_version` needs
- the **data layout**, printed resolved rather than derived from the triple
- a baseline **CPU** and **feature set** (`-march`, `-mcpu`), which the verifier checks target intrinsics against
- the **relocation model**: `static`, `pic`, or `pie`
- the **code model** (`-mcmodel`)
- the **frame-pointer policy**: `all`, `non_leaf`, or `none`
- whether **semantic interposition** is allowed (`-fno-semantic-interposition` turns it off)
- the compilation directory, the main source file's name, and an **ident** string (`.ident`)

Pipeline settings such as the `-O` level and the register allocator aren't part of the module. There is no open set of "module flags".

### Symbols

Functions, globals, aliases, and ifuncs share one namespace of `@name`s, and each name appears once in a module.

| Kind     | What it is                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------- |
| function | A signature, and for a definition, a body                                                      |
| global   | A variable or constant, and for a definition, an initializer                                   |
| alias    | Another symbol plus a constant offset (`__attribute__((alias))`, C++ constructor aliases)       |
| ifunc    | A symbol whose address a resolver function picks at load time. ELF only                        |

A name is the language-level linkage name, such as a C identifier or a C++ mangled name. Lowering adds the platform's prefix, such as Mach-O's `_`. A name marked **verbatim** came from `asm("label")` and gets no prefix. macOS headers rely on this, for example `__asm("_" "fopen" "$DARWIN_EXTSN")`. Names that aren't identifiers are printed in quotes. Lowering may rename private symbols.

Every symbol carries:

- a **linkage** (below)
- a **visibility**: `default`, `hidden`, or `protected`
- a **DLL storage class**: none, `dllimport`, or `dllexport` (COFF only)
- `unnamed_addr`, when its address isn't significant and identical constants may be merged
- `used`, which keeps it in the object file even when nothing refers to it (`__attribute__((used))`), and `retain`, which also keeps it from the linker's garbage collection
- optionally, an explicit **section**, in the object format's own syntax (`"__DATA,__foo"`, `".mysec"`)
- optionally, a **COMDAT** (below)

### Linkage

| Linkage        | Meaning                                                    | ELF                     | Mach-O                                                         | COFF                    | Used for                                              |
| -------------- | ---------------------------------------------------------- | ----------------------- | -------------------------------------------------------------- | ----------------------- | ----------------------------------------------------- |
| `private`      | Not in the object's symbol table                           | `.L` label              | `L` or `l` label                                               | `.L` label              | String literals, jump tables                          |
| `internal`     | Local to the object                                        | `STB_LOCAL`             | non-external symbol                                            | `IMAGE_SYM_CLASS_STATIC` | `static`                                             |
| `external`     | Global definition or declaration                           | `STB_GLOBAL`            | external symbol                                                | `IMAGE_SYM_CLASS_EXTERNAL` | Ordinary C                                         |
| `weak`         | Overridable; the optimizer may not look inside             | `STB_WEAK`              | weak definition                                                | weak external with this default | `__attribute__((weak))` definitions            |
| `weak_odr`     | Every copy is equivalent; always emitted                   | `STB_WEAK` in a COMDAT  | weak definition                                                | COMDAT                  | Explicit template instantiation definitions           |
| `linkonce_odr` | Every copy is equivalent; dropped when unreferenced        | `STB_WEAK` in a COMDAT  | weak definition, `.weak_def_can_be_hidden` when `unnamed_addr` | COMDAT                  | `inline` functions, implicit instantiations, vtables |
| `extern_weak`  | A reference that may stay unresolved (declarations only)   | undefined `STB_WEAK`    | weak reference                                                 | weak external           | `__attribute__((weak))` declarations                  |

A declaration is `external` or `extern_weak`. `private` and `internal` symbols have `default` visibility. `common` (`-fcommon`) and `available_externally` (a definition kept only for inlining, M5) can be added without breaking anything.

### Access through the GOT

No symbol records whether it is resolved within the linkage unit, so no symbol records whether accesses to it go through the GOT. One helper in `billet` answers that from the symbol's linkage, visibility, and DLL storage, whether the module defines it, the relocation model, and the semantic-interposition setting. Lowering and the optimizer both ask it. `private` and `internal` symbols, and `hidden` or `protected` ones, are always resolved within the linkage unit. The rest of the rules are written alongside each object format's lowering.

### Globals

A global has:

- a **size** and an **alignment**
- optionally, a **type**: an aggregate or an array `[N x T]`
- `constant`, when it is never written
- `thread_local` and an optional **TLS model** (`general_dynamic`, `local_dynamic`, `initial_exec`, `local_exec`) from `-ftls-model` or `__attribute__((tls_model))`
- an **initializer**, which is absent for a declaration, `zeroinit`, or a byte image with relocations

The byte image is in the target's byte order, and floats are already bit patterns (ADR 0005). Each **relocation** has an offset into the image, a width, and a target:

- `@sym + addend`
- a block address, `blockaddr(@f, ^b)`, for GNU `&&label` in a static initializer
- either of those minus a second symbol, for label-difference tables

There are no constant expressions. The optimizer folds a load from a `constant` global by reading the bytes, after checking that no relocation overlaps them.

A string literal is a `private unnamed_addr constant` global whose type is `[N x i8]` (or `[N x i16]`, `[N x i32]` for wide strings).

### Sections

A symbol with an explicit section goes there. Otherwise lowering picks a section from the symbol's properties. The first row that matches wins:

| Properties                                                              | ELF                                   | Mach-O                                   |
| ----------------------------------------------------------------------- | ------------------------------------- | ---------------------------------------- |
| `thread_local`                                                          | `.tdata`, or `.tbss` if `zeroinit`    | `__DATA,__thread_data` or `__thread_bss` |
| function                                                                | `.text`                               | `__TEXT,__text`                          |
| `unnamed_addr constant`, no relocations, type `[N x iK]` ending in a NUL | `.rodata.str1.1` (`.str2.2`, `.str4.4`) | `__TEXT,__cstring` (`i8` only)          |
| `constant`, no relocations                                              | `.rodata`                             | `__TEXT,__const`                         |
| `constant`, with relocations                                            | `.data.rel.ro` (`.rodata` under `static`) | `__DATA_CONST,__const`               |
| `zeroinit`                                                              | `.bss`                                | `__DATA,__bss`                           |
| otherwise                                                               | `.data`                               | `__DATA,__data`                          |

COFF's sections are decided in M6. Billet has no kind of global for string literals; the second row is how lowering recognizes them.

### Thread-locals

`tls.addr @x` gives the address of thread-local `@x` in the current thread. `symbol.addr` on a thread-local is a verifier error, because `symbol.addr` is a link-time constant that may be hoisted anywhere, and a thread-local address isn't. Lowering may strengthen a global's TLS model when the relocation model allows it. Mach-O's `__thread_vars` descriptors are lowering's job, and the C++ frontend writes Itanium's `thread_local` wrapper functions itself.

### Functions

A function has:

- a **signature**. For a definition, it is the entry block's parameters.
- its stack slots, and for a definition, its body
- its attributes (below), and optionally a section, an alignment, and a COMDAT

A direct call carries its own signature (see [Calls](#calls)), which may differ from the callee's. This happens when C calls through an unprototyped declaration, as in `int f(); f(1, 2.0);`. Lowering always uses the call's signature. The verifier accepts the mismatch, and the optimizer neither inlines across it nor reasons about it.

### Attributes

Attributes are fixed fields, like everything else Billet carries. Those needed for correctness hold at every `-O` level:

| Attribute         | Meaning                                                               |
| ----------------- | --------------------------------------------------------------------- |
| `returns_twice`   | May return more than once (`setjmp`)                                  |
| `noreturn`        | Never returns                                                         |
| `nounwind`        | Never unwinds                                                         |
| `naked`           | No prologue or epilogue                                               |
| target features   | Features added to the module's baseline (`__attribute__((target))`)   |

The others are hints taken from the source, for the optimizer:

- `noinline`, `always_inline`, `inline_hint`, `cold`, `hot`, and `optnone`
- the memory effects of `__attribute__((const))` and `__attribute__((pure))`
- `nonnull`, `dereferenceable(N)`, and `align(N)` on parameters and the result (`returns_nonnull` is `nonnull` on the result)

Hints belong to the function's declaration or definition, not to each call. A call's signature carries only what calling-convention lowering needs (see [Calls](#calls)). Attributes the optimizer infers (`nocapture`, `willreturn`, `nofree`, …) arrive in M5, stack-protector levels arrive with `-fstack-protector`, and the personality function arrives with the exception model.

### Aliases and ifuncs

An alias points at a symbol defined in the same module, plus a constant offset. GNU `as` and gcc both reject an alias to an undefined symbol. Aliases may point at aliases, but not in a cycle. An alias has its own linkage and visibility. It is `thread_local` exactly when its target is. Mach-O can't express aliases, so the verifier rejects them there.

An ifunc names a resolver function defined in the same module. Only ELF has ifuncs.

### COMDAT

The module has a table of COMDATs, each with a name and one of COFF's selection kinds: `any`, `exactmatch`, `largest`, `nodeduplicate`, or `samesize`. A function or global names the COMDAT it belongs to. When several symbols share one, they are kept or dropped together, such as a template's static data member and its guard variable. On COFF, the members other than the one the COMDAT is named after become associative. Mach-O has no COMDATs, so lowering ignores them there and relies on weak definitions. Until M6, only `any` is used.

### Module tables

- The **file table** maps an index to a path as spelled, including names from `#line`, with an optional content checksum, which CodeView requires and DWARF 5 can use. Every debug location's file is an index into it ([source.md](source.md#below-the-ast)). Ingot → Billet fills it.
- **Type aliases** name aggregate types for printing only (see [Aggregates](#aggregates)).
- The **alias tree** holds the alias classes (see [Aliasing](#aliasing)). Until M5 it is just the root.
- **Constructors and destructors** are entries of a function, a priority, and an optional associated global. Lowering emits them into `.init_array`, `__mod_init_func`, or `.CRT$XCU`.
- **Top-level asm** is an ordered list of strings, which fas parses during lowering.

Symbols and tables keep the order the module was built in, and are emitted in that order, so output doesn't depend on the host (ADR 0005).

### Milestone 1

Milestone 1 implements this subset:

- the header, with `pic` as the only relocation model (arm64 macOS is always PIC)
- function definitions and declarations, with `noreturn` and `nounwind`
- globals that are `zeroinit`, or bytes with `@sym + addend` relocations at pointer width; `constant` and `unnamed_addr`
- `private`, `internal`, and `external` linkage, and `default` visibility
- the file table, type aliases, and the alias tree's root

Everything else reaches the parser, printer, and verifier with the milestone that needs it. Verbatim names come in M2.

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

A module's header and tables come before its symbols. The same grammar caveat applies:

```
module "hello.c"
target "arm64-apple-macosx14.0.0" cpu "apple-m1"
reloc pic  code_model small  frame_pointer all
file 0 "hello.c"

global @.str private unnamed_addr constant [7 x i8] align 1 = c"hello\0A\00"

declare @puts(ptr) -> i32 external nounwind

func @main() -> i32 external {
^entry:
  %s: ptr = symbol.addr @.str             loc(0:3:8)
  %r: i32 = call @puts(%s)                loc(0:3:3)
  %z: i32 = iconst 0                      loc(0:4:10)
  return %z                               loc(0:4:3)
}
```

The data layout is part of the header too. Its spelling is written with the parser.

## Not yet decided

Each of these can be added without breaking anything:

- the alias tree's contents and scoped noalias (M5)
- strict FP and `FENV_ACCESS`
- scalable vectors
- guaranteed tail calls (`musttail`)
- multiple return values for functions
- `common` and `available_externally` linkage
- attributes the optimizer infers (M5), stack-protector levels, and the personality function
- debug-info tables beyond the file table
