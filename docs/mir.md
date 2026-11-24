# MIR

What MIR holds in the first slice, what it means, how FIR → MIR builds it, how register allocation and frame lowering rewrite it, how it is printed and what its verifier checks. MIR is the target-specific layer between FIR and MCIR ([ADR 0008](adr/0008-five-fixed-ir-layers-each-lowering-removes-one-kind-of-structure.md)): AArch64 instructions for `aarch64-apple-darwin` over virtual registers, still SSA with block parameters. FIR → MIR removes target independence. Register allocation removes the block parameters and the virtual registers, and frame lowering adds the prologue and epilogue and turns frame objects into stack offsets. Storage follows [docs/ir-data-layout.md](ir-data-layout.md) and isn't restated; terms follow [GLOSSARY.md](../GLOSSARY.md).

Three decisions are recorded as ADRs: terminators keep their edges and MIR → MCIR picks the branch form ([ADR 0015](adr/0015-mir-terminators-keep-their-edges-and-mir-to-mcir-picks-the-branch-form.md)), opcodes are one per encoding with no pseudo-instructions ([ADR 0016](adr/0016-mir-opcodes-are-one-per-encoding-and-mir-has-no-pseudo-instructions.md)), and the ABI and the condition flags are operand constraints and implicit operands ([ADR 0017](adr/0017-the-abi-and-the-condition-flags-are-operand-constraints-and-implicit-operands.md)).

## Entities

MIR has two containers. The **MIR module** lives for the translation unit and holds every global and the signature of every function. A **MIR body** lives for one function: instruction selection builds it, register allocation and frame lowering rewrite it, and it is cleared once the function has been appended to MCIR.

| Entity | Id | Record | Columns |
|---|---|---|---|
| function | `function_id` | return type, flags (internal, defined), parameter-type range | name, location |
| global | `global_id` | flags (internal, defined, zerofill), initializer | name, location |
| block | `block_id` | parameter range, instruction range | none |
| virtual register | `vreg_id` | register class | location |
| instruction | `inst_id` | opcode, operand range, edge range | location |
| frame object | `frame_object_id` | kind, alignment, size | location |

- **Pools.** The module has `std::vector<type>` (parameter types). A body has `std::vector<operand>`, shared by block parameters, instruction operands and edge arguments, and `std::vector<edge>`. Operands and edges are records in those pools, not entities with ids.
- **Layout.** A body keeps its **layout** like a FIR body does: the block ids in the order their instruction ranges were written, entry block first, and the entry block is block 0. Instruction selection makes one MIR block for each FIR block with the same id, so FIR's layout carries over. The blocks it adds for a `switch` take new ids and go right after the `switch`'s block. Register allocation's new blocks take new ids too, and each goes right after the block whose edge it sits on ([docs/register-allocation.md](register-allocation.md#edges)).
- **Declarations.** The module has a function entity for every function, declarations included, and a global entity for every global, made in FIR's order. The FIR → MIR mapping is a side table that instruction selection drops when it finishes.
- **Names** are interned-string ids, and a function's or global's name is its linkage name, as in FIR. Virtual registers have no names.
- **Types.** A signature uses `i32` and `void`, as in FIR. A virtual register has a **register class** (see [Registers](#registers)), not a type.
- **Records** are 1 byte for a virtual register, 8 for an operand, a global and a frame object, 12 for an edge and a function, and 16 for an instruction and a block. A call has at most 10 operands (its callee, eight argument registers and a result), so an instruction's operand count fits in 16 bits.

## States

A body has a `state`, and each rewrite sets the next one. The records are the same in every state; the verifier's checks and the printer's output depend on it.

| State | Set by | Holds |
|---|---|---|
| `ssa` | instruction selection | virtual registers, block parameters and edge arguments; frame indices |
| `allocated` | register allocation | physical registers only, and no block parameters or edge arguments; frame indices still symbolic, with spill slots added |
| `final` | frame lowering | no frame indices; the prologue and epilogue are in place |

- Register allocation and frame lowering are copying rewrites ([docs/ir-data-layout.md](ir-data-layout.md#order)): block ids stay, instructions get new ids, and frame lowering copies nothing when it has nothing to insert. Operands are updated in place.
- `-emit-mir=isel` prints a body in `ssa` and `-emit-mir` prints it in `final`. `allocated` is internal.

## Registers

- **Register classes** are `gpr32` and `gpr64`, as a `std::uint8_t` `enum class`. Every value in the slice is `gpr32`. `gpr64` holds addresses (an `adrp` result, a GOT-loaded address) and the registers frame lowering uses.
- **Virtual registers** are a body table of classes. Each is defined once, by a block parameter or by one instruction's def operand.
- **Physical registers** are `x0` to `x30`, `sp` and `nzcv`, as a `std::uint8_t` `enum class`. There is one for each hardware register: `w0` and `x0` are the same physical register, and the class of the operand picks the view. `nzcv` is the condition flags and is never allocated.
- **The zero register** is never an operand. Opcodes imply it (`neg`, `mvn`, `mov_*` and `cmp_*`).
- **`sp`, `x29` and `x30`** are operands only in frame lowering's instructions, as the base of a resolved frame object, and as implicit operands of `bl` and `ret`.
- **Allocatable registers** are `x0`–`x15` ([docs/register-allocation.md](register-allocation.md#registers)). `x16` and `x17` are scratch registers that register allocation never assigns, kept for the moves it inserts and for frame lowering ([ADR 0019](adr/0019-x16-and-x17-are-scratch-registers-that-register-allocation-never-assigns.md)). `x18` is reserved by Apple's ABI. The slice never uses the callee-saved `x19`–`x28` ([ADR 0018](adr/0018-the-slices-register-allocator-is-local-and-values-that-cross-a-block-live-in-spill-slots.md)).

## Operands

An operand is an 8-byte record `{kind, flags, aux, payload}`.

| Kind | Payload | `aux` |
|---|---|---|
| `vreg` | the `vreg_id` | the constraint |
| `preg` | the physical register | the class that selects `w` or `x` |
| `imm` | 32 bits, printed as signed decimal | none |
| `symbol` | a `global_id` or `function_id` | the modifier, and which of the two it is |
| `frame_index` | the `frame_object_id` | none |
| `cc` | the condition code | none |

- **Flags.** `def` marks a def, and a use otherwise. `implicit` marks an operand that isn't written in the assembly.
- **Order.** An instruction's operands are its explicit operands in assembly order, defs first, then its implicit uses, then its implicit defs.
- **Address operands.** `ldr_ui`, `str_ui`, `ldp_ui` and `stp_ui` end with a base and an offset, written `[base, offset]`. The base is a register or a frame index, and the offset is an immediate or a `pageoff` or `gotpageoff` symbol.
- **Condition codes** are `eq ne lt le gt ge lo ls hi hs`. FIR's predicates map `eq`→`eq`, `ne`→`ne`, `slt`→`lt`, `sle`→`le`, `sgt`→`gt`, `sge`→`ge`, `ult`→`lo`, `ule`→`ls`, `ugt`→`hi` and `uge`→`hs`.
- **Symbol modifiers** are `none` (for a call), `page`, `pageoff`, `gotpage` and `gotpageoff`. Darwin's spelling (`@PAGE`, the leading `_`) is MCIR's.

### Constraints and implicit operands

A register operand in `ssa` may carry one constraint, and the class of a virtual register stays in its table.

- **None:** any register of the class.
- **`fixed(preg)`:** that register. Only entry-block parameters and implicit operands carry one: a call's arguments and result, and the value of `ret`.
- **`tied(i)`:** the same register as the def at index `i` of the same instruction. Only `movk` has one.

After allocation a constrained virtual register has become a physical register, and implicit operands stay as physical-register operands so that the allocation checker can see them.

Effects fixed by the opcode don't appear as operands. They are in a `constexpr` table:

| Opcode | Effect |
|---|---|
| `cmp_rr`, `cmp_ri` | defines `nzcv` |
| `b_cond`, `cset` | uses `nzcv` |
| `bl` | defines `x30`; clobbers `x0`–`x17` and `nzcv` |
| `ret` | uses `x30` |

## Opcodes

An opcode is one AArch64 encoding form, and no instruction is a pseudo-instruction: every non-terminator prints as exactly one AArch64 instruction ([ADR 0016](adr/0016-mir-opcodes-are-one-per-encoding-and-mir-has-no-pseudo-instructions.md)). Width comes from the register class, so `add_rr` adds `w` or `x` registers (all of one class). A suffix names the form, `rr` for registers, `ri` for a register and an immediate and `ui` for an unsigned scaled offset, on mnemonics that AArch64 has in several forms. The aliases are opcodes of their own, which is why `wzr` is never an operand. A constexpr table gives each opcode its operand shape, and the verifier checks every instruction against it.

| Opcode | Operands | Notes |
|---|---|---|
| `add_rr`, `sub_rr` | def, use, use | |
| `add_ri`, `sub_ri` | def, use, imm | `sp` may be the def and the first use |
| `mul`, `sdiv`, `udiv` | def, use, use | |
| `msub` | def d, use n, use m, use a | d = a − n × m |
| `and_rr`, `orr_rr`, `eor_rr` | def, use, use | |
| `lsl_rr`, `lsr_rr`, `asr_rr` | def, use, use | the count is taken modulo 32 |
| `lsl_ri`, `lsr_ri`, `asr_ri` | def, use, imm | |
| `neg`, `mvn` | def, use | 0 − a, and the bitwise complement |
| `mov_rr` | def, use | the only move register allocation makes |
| `mov_ri` | def, imm | |
| `movz` | def, imm | |
| `movk` | def, use tied to the def, imm, imm | keeps the half the first imm doesn't write; the second imm is the shift, 0 or 16 |
| `cmp_rr`, `cmp_ri` | use, use / use, imm | |
| `cset` | def, cc | 1 when the condition holds, else 0 |
| `adrp` | def `gpr64`, symbol | modifier `page` or `gotpage` |
| `ldr_ui` | def, address | |
| `str_ui` | use, address | |
| `ldp_ui`, `stp_ui` | def or use, def or use, address | two `gpr64`, in frame lowering only |
| `bl` | symbol | the callee, then implicit operands |
| `b`, `b_cond`, `cbz`, `cbnz`, `ret` | see [Terminators and edges](#terminators-and-edges) | |

**Immediates.** The verifier requires every immediate to be one the assembler accepts. The slice emits only these forms, and no `ldur`, `stur` or `cmn`:

- `add_ri`, `sub_ri` and `cmp_ri` take 0–4095, or a multiple of 4096 up to `0xFFF000` (the assembler writes the second as `lsl #12`).
- `lsl_ri`, `lsr_ri` and `asr_ri` take 0–31.
- `mov_ri` takes a 32-bit value that is one 16-bit chunk at bit 0 or bit 16, or the bitwise complement of one. `movz` and `movk` take a 16-bit chunk.
- `ldr_ui` and `str_ui` take a multiple of the access size, up to 4095 times that size. `ldp_ui` and `stp_ui` take a multiple of 8 from 0 to 504.

**Semantics.** Arithmetic wraps modulo 2³². Division, remainder and shifts that FIR leaves unspecified (division by zero, `INT_MIN` by −1, a count outside 0–31) do what AArch64 does. Only `ldr_ui`, `str_ui` and `bl` touch memory, and no layer reorders them relative to each other. Everything else is pure.

## Terminators and edges

Every block ends in exactly one terminator, and a terminator names its successors as **edges**, as in FIR. An edge is a record `{target block, arguments}`, and the arguments are a range of the operand pool. The edges of a terminator are consecutive in the edge pool, and the instruction stores where they start and how many there are.

| Terminator | Operands | Edges |
|---|---|---|
| `b` | none | the target |
| `b_cond` | a condition code | taken, then not taken |
| `cbz`, `cbnz` | a register | taken (zero for `cbz`, non-zero for `cbnz`), then not taken |
| `ret` | the returned value, implicit | none |

- **Arguments.** In `ssa` an edge passes one `vreg` use for each parameter of its target, all read before any parameter takes its new value, as in FIR. An edge argument is never an immediate. In `allocated` and `final` edges carry no arguments, and an edge's moves have been placed by register allocation: at the end of its block, at the start of its target, or in a new block on the edge when it is a critical edge ([docs/register-allocation.md](register-allocation.md#edges)).
- **No fall-through is recorded.** A terminator doesn't say which successor comes next. MIR → MCIR knows the layout and chooses the branch form:

  | Layout | `b_cond cc, T, F` prints as |
  |---|---|
  | `F` follows | `b.cc T` |
  | `T` follows | `b.!cc F` |
  | neither follows | `b.cc T` then `b F` |

  `cbz` and `cbnz` do the same with the opposite instruction, and a `b` to the block that follows is dropped. The inverse of a condition swaps `eq` with `ne`, `lt` with `ge`, `gt` with `le`, `lo` with `hs` and `hi` with `ls`.
- **Reach.** A conditional branch reaches about 1 MiB, and the slice has no branch relaxation. A function larger than that fails in the host assembler, which is a bug in Forge (ADR 0007, ADR 0009).
- **Flags.** A `b_cond` uses `nzcv`, so a `cmp_*` comes right before it in its block. See [Verifier](#verifier).

## Frame objects

A body has a table of frame objects, each `{kind, alignment, size}`, and an instruction names one through a `frame_index` operand with a separate immediate offset: `[fi0, #4]`. There are three kinds, and the slice has no address-taken locals, so no others.

| Kind | Meaning | Made by |
|---|---|---|
| `incoming` | the caller's stack-argument area, at most one | instruction selection, when the function has more than eight parameters; 4 bytes for each parameter past the eighth |
| `outgoing` | the call area at the bottom of the frame, at most one | instruction selection, when a call has more than eight arguments; the largest call's stack arguments, rounded up to 8 |
| `spill` | the slot of one virtual register that crosses a block boundary or that register allocation spills | register allocation |

The ABI fixes the offsets inside `incoming` and `outgoing`, so instruction selection writes them: the k-th argument past the eighth is at offset 4 × (k − 9) of the `outgoing` object of a call, and of the `incoming` object in a callee. Where an object sits in the frame isn't known until after allocation. Frame lowering assigns every object an `sp`-relative offset and rewrites each `frame_index` operand into an `sp` base with the sum as its offset, so a `final` body has none. The layout of the frame, and how every resulting offset stays encodable, belong to [Stack frames and frame lowering for the slice](https://github.com/jmuratov98/forge/issues/35).

## Calling convention

[Apple's AArch64 ABI](https://github.com/jmuratov98/forge/blob/research/mach-o-arm64-abi/research/mach-o-arm64-abi.md) as the slice needs it:

- Arguments one to eight are passed in `w0`–`w7`. The rest go on the stack in order, lowest address first, each in a packed 4-byte slot at `sp` at the call. Every value is 32 bits, so Apple's rule that the caller extends narrower arguments never comes up.
- The result is in `w0`.
- `x0`–`x17` are caller-saved; `x19`–`x28`, `x29` and `sp` are callee-saved; `x18` is reserved.
- `bl` writes `x30`. A function that contains a `bl` keeps a frame record, `x29` and `x30` stored at the frame's top. A leaf may skip it.
- `sp` is 16-byte aligned wherever it is used.

## From FIR

Instruction selection lowers one function at a time. It builds that function's body in `ssa`, then verifies it. The ABI is lowered here: [constraints](#constraints-and-implicit-operands) put arguments and results in their registers, and arguments past the eighth are stores and loads of frame objects.

### Setup

1. **Virtual registers.** One forward walk over FIR's values gives a virtual register of class `gpr32` to each `param` and `result`, in FIR's value order. Constants, `undef` and `removed` values get none. A value that is later fused or dropped leaves its register unused, so ids have gaps. Instruction selection's own temporaries come after them, in the order it makes them.
2. **Use counts** are computed in one walk over the FIR body, into a side table.
3. **Blocks.** One MIR block per FIR block, with the same id. The entry block's parameters become its first eight parameters, fixed to `w0`–`w7` in order. Parameters past the eighth aren't block parameters: each is the result of a `ldr_ui` from the `incoming` object, at the top of the entry block and only when it is used. Every other block's parameters become block parameters with no constraint.
4. The side tables (FIR value → virtual register, use counts) are dropped when the function is finished.

### The backward walk

Each block is walked from its terminator to its first instruction. The MIR block is written reversed and then flipped, so that every use is seen before its definition, as in [docs/ir-data-layout.md](ir-data-layout.md#order).

- **Dead code.** A pure instruction, or a `load`, whose result no instruction already written uses is dropped. That includes the extra `load` of a `post_assign` to a global.
- **Constants and `undef`** have no defining instruction. A constant becomes an immediate where the opcode has an immediate form that accepts it, and otherwise a new virtual register defined right before its user, one for each use, with no sharing: `mov_ri` when one instruction does it, and otherwise `movz` followed by a `movk` whose use is tied to its def. `undef` as an operand is `mov_ri #0`.
- **Operands.** A constant first operand of a commutative instruction is swapped to the second, and a comparison swaps its operands and mirrors its predicate.

| FIR | MIR |
|---|---|
| `add a, b`, `sub a, b` | `add_rr`, `sub_rr`; `add_ri`, `sub_ri` when `b` is a constant that fits |
| `sub 0, a` | `neg` |
| `xor a, -1` | `mvn` |
| `mul`, `sdiv`, `udiv` | the same opcode; a constant operand is materialized |
| `and`, `or`, `xor` | `and_rr`, `orr_rr`, `eor_rr`; a constant operand is materialized |
| `srem a, b`, `urem a, b` | `sdiv t, a, b` then `msub d, t, b, a`; `udiv` for `urem` |
| `shl`, `lshr`, `ashr` | `lsl`, `lsr`, `asr`: `_ri` for a constant count of 0–31, otherwise `_rr` |
| `icmp` whose only use is the `br_if` of its own block | fused: `cmp_*` right before the terminator, whatever lies between them |
| any other `icmp` | `cmp_*` then `cset` |
| `br`, `br_if`, `switch`, `ret` | see below |

### Conditions

A `br_if` on a fused `icmp` is a `cmp_rr` or `cmp_ri` followed by `b_cond`, with the predicate's condition code and the true edge taken. A `br_if` on any other value `v` is `cbnz v` with the true edge taken. A constant condition is materialized and tested, because FIR doesn't fold it either.

### Switch

A `switch` becomes a compare chain in table order, with no jump table. In the `switch`'s block, `cmp v, c1` is followed by `b_cond eq` whose taken edge goes to case 1 with its arguments and whose not-taken edge goes to a new block. That block holds `cmp v, c2` and a `b_cond eq`, and so on. The last not-taken edge is the default edge. A `switch` with no cases is `b` to the default edge. The new blocks have no parameters and go right after the `switch`'s block in the layout. A case value that doesn't fit `cmp_ri` is materialized and compared with `cmp_rr`.

### Globals

Each access has its own `adrp`, with no sharing.

| FIR | MIR |
|---|---|
| `load` of a defined global | `adrp %a, @g@page`; `ldr_ui %v, [%a, @g@pageoff]` |
| `store` to a defined global | `adrp %a, @g@page`; `str_ui %v, [%a, @g@pageoff]` |
| `load` of a declared global | `adrp %a, @g@gotpage`; `ldr_ui %p, [%a, @g@gotpageoff]` with `%p` a `gpr64`; `ldr_ui %v, [%p, #0]` |
| `store` to a declared global | the same, ending in `str_ui %v, [%p, #0]` |

A global is defined when it is defined in this translation unit, internal or external, zerofill or not. A tentative definition is zerofill and defined, so the slice has no common symbols. The GOT form is for a global defined elsewhere.

### Calls and returns

- **A call** is `bl` with the callee's `symbol` first. Then come each register argument as an implicit use, fixed to `w0`–`w7` in order, and, only when the call's value is used, an implicit def fixed to `w0`. Arguments past the eighth are `str_ui` instructions before the `bl`, into the `outgoing` object at offset 4 × (k − 9). A `noproto` call needs nothing different: its arguments are the ones it passes.
- **A return** is `ret` with an implicit use of the value fixed to `w0`, and a bare `ret` in a `void` function. `ret undef` returns `mov_ri #0`.

## Register allocation and frame lowering

Register allocation reads a body in `ssa` and writes one in `allocated` ([docs/register-allocation.md](register-allocation.md)). In the slice it is local, like clang's at `-O0` ([ADR 0018](adr/0018-the-slices-register-allocator-is-local-and-values-that-cross-a-block-live-in-spill-slots.md)): every value that crosses a block boundary has a `spill` frame object, stored after its def and reloaded in each other block that uses it, and each block is allocated on its own by one walk from its terminator up. It gives every virtual register a physical register of its class, honouring fixed constraints, ties and the opcode table's clobbers, and spills every value live across a `bl`. It turns each edge's arguments into one parallel move into the target's parameter slots and puts it where the [terminator rules](#terminators-and-edges) allow. The instructions it adds are `mov_rr`, `ldr_ui`, `str_ui` and the `b` of a new block. None of them writes `nzcv`, so the flags rule holds without register allocation knowing about flags, and they take the location of the instruction they serve.

Frame lowering reads `allocated` and writes `final`. It assigns every frame object an offset and rewrites frame indices, adds the prologue and the epilogue (before every `ret`), keeps a frame record in a function that contains a `bl`, and saves the callee-saved registers the body writes, which in the slice are none (ADR 0018). The prologue and epilogue take the function's location. Its layout is [Stack frames and frame lowering for the slice](https://github.com/jmuratov98/forge/issues/35).

## Locations

Every MIR entity has a location, following the rules in [docs/ir-data-layout.md](ir-data-layout.md#locations), with these choices:

- An **instruction** takes the location of the FIR instruction that made it. The instructions that one FIR instruction makes (`sdiv` and `msub`; `adrp` and `ldr_ui`; a compare chain) all take it, as does a materialized constant for its user.
- A **virtual register** takes its FIR value's location, and a temporary its user's.
- A **block** has no stored location: it takes its first instruction's.
- A **frame object** takes the function's location for `incoming`, the first call that needs it for `outgoing`, and its virtual register's for a `spill`.
- A function or a global takes its FIR entity's.
- Register allocation's moves and spills take the location of the instruction they serve, and an edge's moves that of its terminator ([docs/register-allocation.md](register-allocation.md#the-allocated-body) says which instruction each serves). The prologue and epilogue take the function's.

## Printed form

`-emit-mir=isel` prints each body after instruction selection has built and verified it, and `-emit-mir` prints it after frame lowering has. The module's globals and function signatures print first, as in FIR. No locations are printed.

- **Header.** `func @f(types) -> type state {`. A declaration prints its signature alone.
- **Frame objects** are listed before the first block while a frame index can exist (`ssa`, `allocated`): `fi0: incoming, size 8, align 4`.
- **Blocks** print as `bb3(%0:gpr32 [w0], %1:gpr32):`, or `bb3:` with no parameters, outdented from their instructions by two spaces, in layout order.
- **Instructions.** An opcode prints as its enumerator, not the assembler mnemonic. In `ssa` a def is written on the left of `=`. Once registers are physical the operands print in assembly order with no `=`, so a `final` dump reads like the assembly. Implicit operands come after the explicit ones, uses as `implicit …` and defs as `implicit-def …`.
- **Registers.** A virtual register is `%N`, with its class after a colon on a def or a block parameter (`%2:gpr32`). A physical register prints bare (`w0`, `x8`, `sp`). Ids are indices and gaps stay.
- **Constraints** print in brackets after their operand: `[w0]` for a fixed one and `[=%5]` for a tie.
- **Immediates** are `#N` in signed decimal. `movk` prints its shift as `lsl #16`.
- **Symbols** are `@sink`, `@g@page`, `@g@pageoff`, `@g@gotpage` and `@g@gotpageoff`. A frame object is `fi0`. A condition code prints bare.
- **Addresses** are `[base, offset]`.
- **Edges** are `bb1(%0, %6)`, or `bb1` when there are no arguments, as in `b bb1(%0, %6)`, `b_cond gt, bb2, bb3` and `cbnz %0, bb1, bb2`.
- **Globals** print as in FIR: `global @hits = zerofill`.
- Fixed effects of an opcode (`nzcv`, call clobbers) aren't printed.

## Verifier

These checks run after the structural checks every verifier starts with ([docs/ir-data-layout.md](ir-data-layout.md#verification)), and only if those pass. The verifier runs after instruction selection and after frame lowering in Debug and RelWithAsserts.

- **Every state**
  - Every instruction's operand kinds, count, defs and uses, and register classes follow its opcode's shape, and every immediate satisfies its opcode's rule.
  - `sp`, `x29`, `x30` and `nzcv` appear only where the opcode table and the operand shapes allow, and `x18` never does.
  - A `frame_index` names an object of the body, and its offset plus the access size lies inside the object. `incoming` objects are only read and `outgoing` objects only written.
  - A symbol's modifier is legal for its opcode: `page` only for a defined global, and `gotpage` only for a declared one.
  - **Flags.** A use of `nzcv` is preceded in its block by a def with no `cmp_*` or `bl` between them, and `nzcv` is never live across a block boundary.
- **`ssa`**
  - A virtual register with a use is defined exactly once, and every use is dominated by its def in blocks reachable from the entry. An edge's arguments are used at the end of its block.
  - There are no explicit physical-register operands.
  - `fixed` appears only on entry-block parameters and implicit operands, and `tied` only on `movk`, which ties a def and a use of the same class. The fixed registers of one instruction's uses are distinct, and so are those of its defs.
  - The entry block has no predecessors and at most eight parameters, fixed to `w0` onward in order.
  - Every edge passes one `vreg` for each parameter of its target, of the same class.
  - A `bl` names a function of the module. Its argument uses are fixed to `w0` onward in order with no gap, and its def, if any, to `w0`. A `ret` has an implicit use fixed to `w0` exactly when the function isn't `void`.
- **`allocated` and `final`:** there are no virtual registers, block parameters or edge arguments, and every implicit operand is a physical register.
- **`final`:** there are no frame indices, and every stack adjustment and every `sp`-relative offset is one the assembler accepts, with `sp` adjusted in multiples of 16.
  A function that contains a `bl` keeps a frame record: an `stp_ui` of `x29` and `x30`, and an `add_ri` that sets `x29`, come before its first `bl`.
- **Not checked:** that allocation preserved the program's values, which is the allocation checker's job ([docs/register-allocation.md](register-allocation.md#the-allocation-checker) lists what it asserts; how it is built is still open), that blocks are reachable, and that a virtual register nothing uses is defined.

## What MIR removes, and what MCIR receives

ADR 0008 asks each layer to say which lowering removes the structure it adds. Register allocation removes the block parameters, the virtual registers and SSA, and frame lowering removes the frame indices. MIR → MCIR removes the CFG: blocks become temporary symbols in layout order, and each terminator becomes one or two branch instructions. It also removes the alias opcodes. MCIR stores only the ARM ARM's base forms ([docs/mcir.md](mcir.md)), and MIR keeps aliases on purpose so that a dump reads like the assembly and instruction selection stays simple ([ADR 0016](adr/0016-mir-opcodes-are-one-per-encoding-and-mir-has-no-pseudo-instructions.md)). So MIR → MCIR is a translation, not a copy, and ADR 0008's table names both.

What MCIR's design has to handle:

- **Blocks** are emitted in layout order. A block that a branch targets gets a temporary symbol that takes the block's location, since Darwin's conditional branches need `L` labels in the same function, and a block reached only by falling through gets none.
- **Terminators** print as the branch forms in [Terminators and edges](#terminators-and-edges). A `b_cond` isn't one MCIR instruction.
- **Opcodes.** Every MIR opcode maps to one MCIR form, with the register slots filled in and the width flag set from the operands' class. A register is its number, `zr` or `sp`. Eighteen of the 37 need more than a rename:

  | MIR | MCIR |
  |---|---|
  | `add_rr`, `sub_rr`, `and_rr`, `orr_rr`, `eor_rr` | `add_shifted`, `sub_shifted`, `and_shifted`, `orr_shifted`, `eor_shifted`, with shift `lsl #0` |
  | `add_ri`, `sub_ri` | `add_imm`, `sub_imm`, with the value split into imm12 and shift: up to 4095 is (v, 0), and a larger multiple of 4096 is (v ÷ 4096, 12) |
  | `mul` | `madd` with `zr` as the addend |
  | `lsl_ri n` | `ubfm rd, rn, (32 − n) mod 32, 31 − n` |
  | `lsr_ri n`, `asr_ri n` | `ubfm rd, rn, n, 31` and `sbfm rd, rn, n, 31` |
  | `neg`, `mvn`, `mov_rr` | `sub_shifted`, `orn_shifted`, `orr_shifted`, each from `zr` |
  | `mov_ri v` | `movz rd, c, s` when `v` is the 16-bit chunk `c` at shift `s` (0 or 16), otherwise `movn rd, c, s` with `v` = ~(`c` << `s`) |
  | `cmp_rr`, `cmp_ri` | `subs_shifted`, `subs_imm`, into `zr` |
  | `cset cc` | `csinc rd, zr, zr, !cc` |
  | `lsl_rr`, `lsr_rr`, `asr_rr` | `lslv`, `lsrv`, `asrv` |
  | `ldr_ui`, `str_ui` | `ldr_imm`, `str_imm` |
  | `ldp_ui`, `stp_ui` | `ldp_offset`, `stp_offset` |
  | `sdiv`, `udiv`, `msub`, `movz`, `movk`, `adrp`, `bl`, `ret` | the same name |

- **Symbols and operands.** Implicit operands and the state aren't part of the assembly. A symbol operand keeps its modifier. A function becomes a named symbol, global for an external function and local for an internal one, and a declaration becomes an undefined one. Internal names need not be unique in FIR, so MCIR makes them unique. A global becomes `__DATA,__data` or, when it is zerofill, `__DATA,__bss`.
- **Locations** are the instruction's.

## Worked examples

Ids come from the rules above: a virtual register for every FIR parameter and result in value order, then temporaries in the order instruction selection makes them. `docs/ir-data-layout.md` shows `add` in memory. Each example is shown in `ssa` and after register allocation, in `allocated` (which no flag prints), by the rules in [docs/register-allocation.md](register-allocation.md). Frame lowering's `final` forms belong to [Stack frames and frame lowering for the slice](https://github.com/jmuratov98/forge/issues/35), except for `add`, where it inserts nothing.

`int add(int a, int b) { return a + b; }`, whose FIR is in [docs/fir.md](fir.md#worked-examples):

```
func @add(i32, i32) -> i32 ssa {
bb0(%0:gpr32 [w0], %1:gpr32 [w1]):
  %2:gpr32 = add_rr %0, %1
  ret implicit %2 [w0]
}
```

```
func @add(i32, i32) -> i32 final {
bb0:
  add_rr w0, w0, w1
  ret implicit w0
}
```

A loop, `sum` from [docs/fir.md](fir.md#worked-examples). `%2` is the fused `icmp`'s register, which nothing uses, and `%6` is the constant 0 that the edge into `bb1` passes:

```
func @sum(i32) -> i32 ssa {
bb0(%0:gpr32 [w0]):
  %6:gpr32 = mov_ri #0
  b bb1(%0, %6)
bb1(%1:gpr32, %3:gpr32):
  cmp_ri %1, #0
  b_cond gt, bb2, bb3
bb2:
  %4:gpr32 = add_rr %3, %1
  %5:gpr32 = sub_ri %1, #1
  b bb1(%5, %4)
bb3:
  ret implicit %3 [w0]
}
```

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

`bb1`'s parameters cross block boundaries, so they live in `fi0` and `fi1`, and each edge into `bb1` stores its arguments there before its `b`. The `b bb1` in `bb0` is dropped by MIR → MCIR because `bb1` follows, and `b_cond gt, bb2, bb3` prints as `b.le bb3` because `bb2` follows.

A callee with ten parameters. Its FIR is `%10 = add i32 %a, %i`, `%11 = add i32 %10, %j` and `ret %11`. Parameters nine and ten come from the `incoming` object and are virtual registers 8 and 9, in FIR's value order. Nothing crosses a block or a call, so register allocation inserts nothing:

```
func @callee(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32 ssa {
  fi0: incoming, size 8, align 4
bb0(%0:gpr32 [w0], %1:gpr32 [w1], %2:gpr32 [w2], %3:gpr32 [w3], %4:gpr32 [w4], %5:gpr32 [w5], %6:gpr32 [w6], %7:gpr32 [w7]):
  %8:gpr32 = ldr_ui [fi0, #0]
  %9:gpr32 = ldr_ui [fi0, #4]
  %10:gpr32 = add_rr %0, %8
  %11:gpr32 = add_rr %10, %9
  ret implicit %11 [w0]
}
```

```
func @callee(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32 allocated {
  fi0: incoming, size 8, align 4
bb0:
  ldr_ui w8, [fi0, #0]
  ldr_ui w9, [fi0, #4]
  add_rr w8, w0, w8
  add_rr w0, w8, w9
  ret implicit w0
}
```

A call with ten arguments, `int caller(int x) { return sink(x, 1, 2, 3, 4, 5, 6, 7, 8, x + 9); }`. Its FIR is below, and its constants are values 1 to 9:

```
func @caller(i32) -> i32 {
bb0(%x: i32):
  %10 = add i32 %x, 9
  %11 = call i32 @sink(%x, 1, 2, 3, 4, 5, 6, 7, 8, %10)
  ret %11
}
```

Arguments nine and ten are stored into the `outgoing` object, and the rest are constants materialized into the registers the call fixes:

```
func @sink(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32

func @caller(i32) -> i32 ssa {
  fi0: outgoing, size 8, align 4
bb0(%0:gpr32 [w0]):
  %1:gpr32 = add_ri %0, #9
  %10:gpr32 = mov_ri #8
  str_ui %10, [fi0, #0]
  str_ui %1, [fi0, #4]
  %3:gpr32 = mov_ri #1
  %4:gpr32 = mov_ri #2
  %5:gpr32 = mov_ri #3
  %6:gpr32 = mov_ri #4
  %7:gpr32 = mov_ri #5
  %8:gpr32 = mov_ri #6
  %9:gpr32 = mov_ri #7
  bl @sink, implicit %0 [w0], implicit %3 [w1], implicit %4 [w2], implicit %5 [w3], implicit %6 [w4], implicit %7 [w5], implicit %8 [w6], implicit %9 [w7], implicit-def %2:gpr32 [w0]
  ret implicit %2 [w0]
}
```

Register allocation inserts nothing either: `%0` is used before the call and not after it, and each constant passed in a register is defined straight into the register its argument is fixed to:

```
func @sink(i32, i32, i32, i32, i32, i32, i32, i32, i32, i32) -> i32

func @caller(i32) -> i32 allocated {
  fi0: outgoing, size 8, align 4
bb0:
  add_ri w8, w0, #9
  mov_ri w9, #8
  str_ui w9, [fi0, #0]
  str_ui w8, [fi0, #4]
  mov_ri w1, #1
  mov_ri w2, #2
  mov_ri w3, #3
  mov_ri w4, #4
  mov_ri w5, #5
  mov_ri w6, #6
  mov_ri w7, #7
  bl @sink, implicit w0, implicit w1, implicit w2, implicit w3, implicit w4, implicit w5, implicit w6, implicit w7, implicit-def w0
  ret implicit w0
}
```

A `switch` and a global:

```c
int hits;
int pick(int x) {
  switch (x) {
  case 0: return hits;
  case 7: hits = 1; return 20;
  }
  return -1;
}
```

Its FIR has the default edge to `bb1`, created first, then a block for each case, and `bb1` laid out last:

```
global @hits = zerofill

func @pick(i32) -> i32 {
bb0(%x: i32):
  switch %x, default bb1 [0: bb2, 7: bb3]
bb2:
  %1 = load i32 @hits
  ret %1
bb3:
  store i32 @hits, 1
  ret 20
bb1:
  ret -1
}
```

The compare chain adds `bb4` after `bb0`. Each global access has its own `adrp`, and `ret` fixes its constant to `w0`:

```
global @hits = zerofill

func @pick(i32) -> i32 ssa {
bb0(%0:gpr32 [w0]):
  cmp_ri %0, #0
  b_cond eq, bb2, bb4
bb4:
  cmp_ri %0, #7
  b_cond eq, bb3, bb1
bb2:
  %2:gpr64 = adrp @hits@page
  %1:gpr32 = ldr_ui [%2, @hits@pageoff]
  ret implicit %1 [w0]
bb3:
  %4:gpr32 = mov_ri #1
  %5:gpr64 = adrp @hits@page
  str_ui %4, [%5, @hits@pageoff]
  %3:gpr32 = mov_ri #20
  ret implicit %3 [w0]
bb1:
  %6:gpr32 = mov_ri #-1
  ret implicit %6 [w0]
}
```

```
global @hits = zerofill

func @pick(i32) -> i32 allocated {
  fi0: spill, size 4, align 4
bb0:
  str_ui w0, [fi0, #0]
  cmp_ri w0, #0
  b_cond eq, bb2, bb4
bb4:
  ldr_ui w0, [fi0, #0]
  cmp_ri w0, #7
  b_cond eq, bb3, bb1
bb2:
  adrp x8, @hits@page
  ldr_ui w0, [x8, @hits@pageoff]
  ret implicit w0
bb3:
  mov_ri w8, #1
  adrp x9, @hits@page
  str_ui w8, [x9, @hits@pageoff]
  mov_ri w0, #20
  ret implicit w0
bb1:
  mov_ri w0, #-1
  ret implicit w0
}
```

`%0` is used in `bb4` as well as `bb0`, so it crosses a block boundary: it is stored at the top of the entry block and reloaded in `bb4`. The layout is `bb0 bb4 bb2 bb3 bb1`, so MIR → MCIR prints `bb0`'s `b_cond` as `b.eq` to `bb2`, because `bb4` follows. It prints `bb4`'s as `b.eq` to `bb3` and then `b` to `bb1`, because neither follows.
