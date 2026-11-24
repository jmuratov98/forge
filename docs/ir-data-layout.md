# IR data layout

How every IR layer, from the AST to MCIR, stores what it holds. The reasoning is in [ADR 0011](adr/0011-ir-entities-live-in-dense-arrays-named-by-typed-ids.md); terms follow [GLOSSARY.md](../GLOSSARY.md). Each per-layer design (its node or instruction set, records and printed syntax) builds on these rules and doesn't restate them.

An **entity** is anything a layer refers to: AST and HIR nodes and declarations; FIR values, instructions and blocks; MIR instructions, virtual registers and blocks; MCIR sections, atoms, symbols, instructions and data items.

## Containers and lifetimes

Each lifetime is one container object. It owns its entities' arrays as plain `std::vector`s, and destroying or clearing it frees everything in it. There is no arena allocator and no per-entity heap allocation.

| Container | Lives for | Holds |
|---|---|---|
| AST | the translation unit | the C frontend's tree |
| HIR module | the translation unit | globals, functions and every body |
| FIR module, MIR module | the translation unit | globals and function signatures |
| FIR body, MIR body | one function | that function's blocks, instructions and values or virtual registers |
| MCIR module | the translation unit | sections, atoms, symbols, instructions and data items |

The FIR and MIR bodies are cleared rather than destroyed once their function has been appended to MCIR, so their capacity carries over and they stop allocating after the largest function.

## Ids

An entity is named by a `forge::id<Entity, T>`: an index into the array that holds it, with a distinct C++ type per entity kind.

- **Naming.** Ids are `<entity>_id` and records keep the plain name: `fir::inst_id` names a `fir::inst`. The id is tagged with the record's type (`using inst_id = forge::id<inst>;`), which only needs a forward declaration.
- **Width.** `T` is one of `std::uint8_t`, `std::uint16_t`, `std::uint32_t` and `std::uint64_t` (the `forge::id_storage` concept) and defaults to `std::uint32_t`. `std::unsigned_integral` isn't used, because whether `char` and `wchar_t` satisfy it differs between hosts.
- **Invalid.** A default-constructed id is invalid (all bits set), as is `id::invalid()`. `is_valid()` tests it, and `explicit operator bool` allows `if (id)`. There's no implicit conversion to `bool` or to any integer.
- **Making and reading.** Only explicit construction from a `std::size_t` makes a valid id, and it stops with `FORGE_ASSERT` once the width is exhausted. That is a limit in Forge, not a diagnostic (ADR 0009). `index()` returns a `std::size_t` and checks with `FORGE_DEBUG_ASSERT` that the id is valid.
- **Comparing.** `<=>` is defaulted, which also gives `==`. Ids of different kinds can't be compared. `std::hash` is specialized.
- **Shape.** An id is trivially copyable and exactly `sizeof(T)`, both checked with `static_assert`. Its members are `noexcept`.
- **Indexing.** Indexing a container by id checks the range with `FORGE_DEBUG_ASSERT`, which is on in Debug and RelWithAsserts.
- **Ranges.** `forge::id_range<Id>` is a half-open `[first, end)` range of ids that can be iterated, such as a block's instructions. Ids themselves have no arithmetic.

### Where an id is valid

- **Body ids** (FIR values, instructions and blocks; MIR virtual registers, instructions and blocks) mean nothing once the body is cleared for the next function.
- **Module ids** (functions and globals; every MCIR id, since the MCIR module is MCIR's only container) last for the translation unit, and any body of that module may hold them. AST and HIR ids also last for the translation unit.
- **No cross-layer ids.** No layer stores another layer's ids. A lowering keeps its mappings (HIR declaration → FIR global, FIR value → MIR virtual register, MIR block → MCIR temporary symbol) in side tables and drops them when it finishes. Location ids and interned-string ids are shared infrastructure, not IR, so any layer may hold them.
- **Rewrites.** A copying rewrite keeps the ids of everything it doesn't reorder (blocks, values, virtual registers) and gives instructions new ids. A side table keyed by instruction ids doesn't survive a rewrite.

## Records, pools and columns

- **Records.** Each entity kind is an array of fixed-size records holding what passes read on every visit: opcode, flags, type, and either up to two operands inline or a range into a pool. A record is at most 16 bytes, checked with `static_assert`; a layer that needs more says why in its design.
- **Pools.** Variable-length lists (call arguments, branch arguments, `switch` cases, MIR operand lists) live in pools, one `std::vector` per element type (for example `std::vector<fir::value_id>`). A record stores `(start, count)` and reads its list back as a `std::span`. Rewriting a list appends a new copy and leaves the old one unused until the container is cleared.
- **Columns.** Data every entity has but few passes read, such as its location and source name, lives in parallel arrays indexed by the same id. The call that adds an entity appends to every column at once, so a column is always as long as its entity array.

## Order

- In FIR, MIR and MCIR, instruction order is array order, and a block's instructions are a contiguous range of its body's instruction array.
- A record may be updated in place (an operand rewritten, a branch's argument list filled in), but nothing is inserted, moved or deleted in the middle of an array. A step that inserts or reorders, such as register allocation's moves and spills or frame lowering's prologue and epilogue, reads one array and writes a new one in a single linear pass. A step with nothing to insert copies nothing.
- HIR is a tree, built once by AST → HIR and never edited afterwards. Its nodes are created bottom-up, so children have smaller ids than their parents.
- Block ids follow creation order: a forward `goto` creates its target before the target's code is written. Each FIR and MIR body therefore keeps its **layout**, the list of block ids in the order their instruction ranges were written. The entry block is block 0 and comes first. MIR → MCIR emits blocks in layout order.
- Two consequences for the lowerings: HIR → FIR has to finish a block before it starts the next, and instruction selection, which walks each block backwards, writes the block reversed and then flips it.

## Uses and other computed facts

- No layer stores the users of a value. A pass that needs uses or use counts (instruction selection's single-use matching and dead-code dropping, liveness, the verifiers) computes them in one walk.
- When FIR construction removes a trivial block argument, it records the replacement in an alias table. One fix-up walk at the end of the function rewrites every operand through it, and no alias survives construction.
- Computed facts live in **side tables** owned by the pass that computes them, never in the container. Examples are use counts, liveness, the dominator tree, register assignments and a lowering's mappings. `forge::side_table<Id, T>` is a vector indexed by id, sized once from the container's count and filled with a default value. A pass drops its side tables when it ends or hands them explicitly to the next pass; sema's results, for example, are handed to AST → HIR.
- Sparse facts use `std::unordered_map<Id, T>` until profiling justifies a dense hash map of Forge's own.

## Locations

- Every entity has a location, a 32-bit opaque handle kept in a column. How it is encoded (spelling and expansion locations, `#line`) belongs to the shared source-location infrastructure.
- An MCIR section has none. It serves the whole translation unit and stands for no source position, so it has no location column and the verifiers don't ask for one (see [docs/mcir.md](mcir.md#locations)).
- Everything a lowering creates for an entity gets that entity's location. `%` lowered to `sdiv` + `msub` gives both the `%`'s location.
- Code with no single source entity takes the location of what it serves. Register allocation's moves take the location of the instruction they were added for, the prologue and epilogue take the function's, and `main`'s implicit `return 0` takes its closing brace.
- There is no "unknown" location, so the verifiers check that every entity has one. A layer may derive an entity's location instead of storing it (an instruction's result value from its instruction); each layer's design says which.

## Types

Each layer chooses its own types. While the set is small and closed (HIR's `s32`, `u32` and `void`; FIR's `i32`), a type is an `enum class` backed by `std::uint8_t` inside the record. Once types beyond the slice's subset arrive (pointers, structs), they become interned module entities with ids, and the type field grows from 1 byte to 4 within the 16-byte budget.

## Shared code

What the layers share is small: `forge::id`, `forge::id_range`, `forge::side_table`, and generic CFG algorithms (reverse postorder, dominator tree) written against a C++20 concept that both FIR and MIR bodies satisfy. There is no common instruction class, generic IR graph or base class shared by FIR and MIR. Each layer defines its own concrete types (ADR 0001, ADR 0008). Where these pieces live is decided with the source tree.

## Printing

- Printers print an entity by its index (`%7`, `bb3`), gaps included, so a dump matches what a debugger shows at `body[id]`. Nothing is renumbered.
- Where a layer keeps a source name in a column, the printer shows the name instead (`%a`). Each layer's design decides which entities have names.
- Tests capture ids with FileCheck variables (`[[X:%[0-9]+]]`) instead of hard-coding them.

## Verification

Every verifier runs these structural checks first, and runs the layer's own semantic checks (types, dominance, no virtual registers after register allocation) only if they pass. The semantic checks can then index freely.

- Every id stored in the container is in range, and is valid wherever the field requires an entity.
- Every pool range lies inside its pool.
- Every column is as long as its entity array.
- Every entity has a location.
- In FIR and MIR:
  - The layout lists every block exactly once, with the entry block first.
  - Taken in layout order, the blocks' instruction ranges cover the instruction array with no gaps or overlaps.
  - Each block ends in exactly one terminator.
  - Every branch target is a block of the same body.
- In FIR, no alias is left after construction.

The CFG checks are one generic routine over the shared CFG concept; the rest is per-layer code following the same list. Verifiers run after every lowering in Debug and RelWithAsserts.

## Worked example

`int add(int a, int b) { return a + b; }`, with locations written as `line:col`. In memory each one is a 32-bit handle. Field names are illustrative: each layer's design fixes its own records.

```
AST    tree "t.c" (lives for the translation unit)
         nodes  [0] parm_decl   a   int              1:13
                [1] parm_decl   b   int              1:20
                [2] decl_ref    n0                   1:32
                [3] decl_ref    n1                   1:36
                [4] binary      +   n2 n3            1:34
                [5] return      n4                   1:25
                [6] compound    pool[2,3)            1:23
                [7] func_decl   add pool[0,2) n6     1:5
         pool<node_id>  [n0 n1 | n5]
         sema's side table (handed to AST → HIR):  type  n2..n4 → int

HIR    module "t.c" (lives for the translation unit, keeps every body)
         functions  [0] add (s32, s32) -> s32   types[0,2)  body b0   1:5
         bodies     [0] root s1  locals from l0  labels from 0
         locals     [0] a  s32                       1:13
                    [1] b  s32                       1:20
         exprs      [0] read_local  l0               1:32
                    [1] read_local  l1               1:36
                    [2] add.s32     e0 e1            1:34
         stmts      [0] return      e2               1:25
                    [1] block       pool[0,1)        1:23
         pool<stmt_id>  [s0]    pool<type>  [s32 s32]

FIR    module: functions [0] add (i32, i32) -> i32      (signatures only)
       body of add (cleared once it reaches MCIR)
         blocks  [0] bb0  params pool[0,2)  insts [i0, i2)      layout [bb0]
         values  [0] param 0 of bb0   name a                    1:13
                 [1] param 1 of bb0   name b                    1:20
                 [2] result of i0
         insts   [0] add  v0 v1                                 1:34
                 [1] ret  v2                                    1:25
         pool<value_id>  [v0 v1]
       printed:  bb0(%a: i32, %b: i32):
                   %2 = add i32 %a, %b
                   ret %2

MIR    body of add, before register allocation
         blocks  [0] bb0  params pool[0,2)  insts [i0, i2)      layout [bb0]
         vregs   [0] gpr32  [1] gpr32  [2] gpr32
         insts   [0] add.w  ops pool[0,3) = def %2, use %0, use %1     1:34
                 [1] ret    ops pool[3,4) = use %2 [w0]                1:25
       body of add, after register allocation (copied into a new instruction array; bb0 keeps its id)
         insts   [0] add.w  w0, w0, w1                                 1:34
                 [1] ret                                               1:25
       frame lowering: a leaf with no saved registers, so nothing is inserted and nothing is copied

MCIR   module "t.c" (lives for the translation unit)
         sections  [0] __TEXT,__text  regular  pure_instructions      (no location)
         atoms     [0] s0  align 2  symbol 0  insts [0, 2)            (its symbol's location)
         symbols   [0] add  named  global  atom 0 + 0                 1:5
         insts     [0] add_shifted  w  lsl  w0 w0 w1 0                1:34
                   [1] ret          x       x30                       1:25
       isel's FIR value → MIR vreg map and the MIR block → MCIR temporary symbol map
       are side tables that are dropped when each lowering finishes.
```

## Out of scope

Compiling function bodies on several threads. Nothing here is designed for it beyond the coding standards' ban on mutable globals.
