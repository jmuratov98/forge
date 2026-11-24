# MCIR

What MCIR holds in the first slice, what it means, how MIR → MCIR builds it, how it is printed and what its verifier checks. MCIR is the last IR layer, after MIR ([ADR 0008](adr/0008-five-fixed-ir-layers-each-lowering-removes-one-kind-of-structure.md)). MIR → MCIR removes the CFG: blocks become temporary symbols in a straight run of instructions, and the module becomes an object module of sections, atoms and symbols. In the slice MCIR has one consumer, the assembly printer behind `-S` and `-c` ([ADR 0007](adr/0007-forge-emits-assembly-and-runs-the-host-assembler-until-fas.md)). fas will later parse assembly into MCIR and add an encoder and an object writer, so MCIR models a whole object module and nothing in it is specific to C. How instructions are stored is [ADR 0014](adr/0014-mcir-stores-each-aarch64-instruction-as-one-fixed-record-in-its-architectural-form.md). Storage follows [docs/ir-data-layout.md](ir-data-layout.md) and isn't restated here; terms follow [GLOSSARY.md](../GLOSSARY.md).

## Entities

The MCIR module is the only container. It lives for the translation unit. MIR → MCIR appends to it one function at a time and then the globals, and nothing is ever removed.

| Entity | Id | Record | Columns |
|---|---|---|---|
| section | `section_id`, 8-bit | segment name, section name, type, attributes | none |
| atom | `atom_id` | section, log2 alignment, symbol, contents | none: its location is its symbol's |
| symbol | `symbol_id` | kind, binding, atom (invalid when undefined), offset | name, location |
| instruction | `inst_id` | see [Instructions](#instructions) | location |
| data item | `data_id` | kind, value or symbol reference | location |

- **Module fields.** The module also holds its platform and minimum OS version (`macos 11.0` in the slice) and whether the object splits its sections into atoms by symbol (always, in the slice). MIR → MCIR sets them from the target, and both printers print them. fas's parser will fill them from `.build_version` and `.subsections_via_symbols`.
- **Sections** are Mach-O's own. Their segment and section names are interned strings (`__TEXT`, `__text`), their type is `regular` or `zerofill` in the slice, and their attributes are the ones a `.section` directive writes (`pure_instructions`). A section's alignment is the largest of its atoms', computed when needed. `section_id` is `forge::id<section, std::uint8_t>`, because a Mach-O object has at most 255 sections. Sections are created the first time something goes in them. The slice uses `__TEXT,__text` (`regular`, `pure_instructions`), `__DATA,__data` (`regular`) and `__DATA,__bss` (`zerofill`).
- **Atoms.** An atom is a contiguous run of one section's contents that starts at its symbol. What its contents are depends on its section. In a section with `pure_instructions`, they're a range of the instruction array. In a `zerofill` section, they're a size in bytes and no items. In any other section, they're a range of the data-item array. A section's contents are its atoms in array order. The module therefore needs no array per section, and sections can interleave freely, as string literals in `__cstring` will once the subset grows.
- **Symbols.**
  - Each symbol is **named**, **private** or **temporary**. Its binding is `global` or `local`, and private and temporary symbols are always local.
  - A defined symbol names a position: its atom and an offset into that atom's instructions or data items. An atom's own symbol is at offset 0. An undefined symbol has no atom.
  - Names are interned strings at C level, with no leading `_`; only the printers spell them for Darwin. A temporary symbol made by MIR → MCIR has no name. fas's parser will keep the names it reads (`Lloop`).
- **Records** are 16 bytes for a section, an atom, an instruction and a data item, and 12 for a symbol.

## Instructions

Each instruction is one 16-byte record ([ADR 0014](adr/0014-mcir-stores-each-aarch64-instruction-as-one-fixed-record-in-its-architectural-form.md)):

| Field | Size | Holds |
|---|---|---|
| opcode | 2 bytes | the instruction's form, such as `add_shifted` or `ldr_imm` |
| flags | 1 byte | the width (`w` or `x`), and a symbol reference's modifier |
| kind | 1 byte | a condition code, shift kind or extend kind, as the format says |
| operands | 4 × 1 byte | registers, or small fields such as a shift amount, as the format says |
| payload | 8 bytes | an immediate, or a symbol reference: a `symbol_id` and a `std::int32_t` addend |

- **Opcodes** are the ARM ARM's instruction forms. An instruction with several encodings has one opcode for each (`add_imm`, `add_shifted`). Width doesn't double the set, because `w` or `x` is a flag. Each opcode has a **format**, which says what every field means. The printers, the verifier, and later fas's encoder and parser, each switch over format. MIR's opcodes are the same enum, plus MIR's own pseudos, and none of those pseudos reaches MCIR.
- **Base forms only.** MCIR has no alias opcodes. `cmp w0, #10` is stored as `subs_imm wzr, w0, #10`, `mov w0, #5` as `movz w0, #5`, and `mul` as `madd` with `zr` added. The `-S` printer chooses the aliases.
- **Values are stored as the base instruction's assembly writes them**, not as encoded bitfields:
  - load and store offsets in bytes, unscaled
  - `imm12` and its shift (0 or 12)
  - `imm16` and its shift (0, 16, 32 or 48)
  - a logical immediate as its value (`0xff`)
  - `ldp`/`stp` offsets in bytes

  The verifier checks that each one can be encoded. Encoding (scaling, `N:immr:imms`) belongs to the encoder, which arrives with fas.
- **Registers** take one byte: `0`–`30`, `zr` or `sp`. The width comes from the instruction's width flag and its format, so `ldr w0, [x1]` has a `w` data register and an `x` base register. Every register slot takes either `sp` or `zr` for register 31, as its encoding does, never both.
- **Symbol references** are a symbol, a modifier and an addend. The modifiers are `none`, `page`, `pageoff`, `gotpage` and `gotpageoff`, and their spelling (`@PAGE`) belongs to the printer. Every branch target is a reference with `none`, and a branch to a block refers to that block's temporary symbol. The addend is 0 everywhere in the slice.

### The slice's forms

These are the forms the instruction-selection patterns fixed so far need. MIR's design adds a form whenever its instruction selection uses a new one. Operands are written as `-emit-mcir` prints them. `rd/sp` is a slot that takes `sp` for register 31, and every other register slot takes `zr`.

| Opcode | Operands | `-S` prints |
|---|---|---|
| `add_imm`, `sub_imm` | rd/sp, rn/sp, imm12, shift | `mov rd, rn` for `add_imm` with 0 when either register is `sp` |
| `adds_imm`, `subs_imm` | rd, rn/sp, imm12, shift | `cmn` / `cmp` when rd is `zr` |
| `add_shifted`, `sub_shifted`, `subs_shifted` | rd, rn, rm, shift kind, amount | `neg` for `sub_shifted` from `zr`; `cmp` for `subs_shifted` into `zr` |
| `and_shifted`, `orr_shifted`, `eor_shifted`, `orn_shifted` | rd, rn, rm, shift kind, amount | `mov` for `orr_shifted` from `zr` with no shift; `mvn` for `orn_shifted` from `zr` |
| `and_imm`, `orr_imm`, `eor_imm` | rd/sp, rn, logical immediate | `mov` for `orr_imm` from `zr` when no `movz`/`movn` gives the value |
| `madd`, `msub` | rd, rn, rm, ra | `mul` / `mneg` when ra is `zr` |
| `sdiv`, `udiv` | rd, rn, rm | |
| `lslv`, `lsrv`, `asrv` | rd, rn, rm | `lsl`, `lsr`, `asr` |
| `ubfm`, `sbfm` | rd, rn, immr, imms | `lsl`, `lsr` or `asr` with an immediate, or their other aliases, by the ARM ARM's rules |
| `movz`, `movn`, `movk` | rd, imm16, shift | `mov` for `movz` and `movn` where the ARM ARM prefers it |
| `csinc` | rd, rn, rm, condition | `cset` when rn and rm are `zr`, `cinc` when they're the same other register |
| `adrp` | rd, `page` or `gotpage` reference | |
| `ldr_imm`, `str_imm` | rt, rn/sp, byte offset, or a `pageoff` reference (or `gotpageoff` on a 64-bit `ldr_imm`) | `ldr`, `str` |
| `ldur`, `stur` | rt, rn/sp, signed byte offset | |
| `ldp_offset`, `ldp_pre`, `ldp_post`, `stp_offset`, `stp_pre`, `stp_post` | rt, rt2, rn/sp, byte offset | `ldp`, `stp` |
| `b`, `bl` | reference | |
| `b_cond` | condition, reference to a temporary | `b.<cond>` |
| `cbz`, `cbnz` | rt, reference to a temporary | |
| `ret` | rn | `ret` when rn is `x30` |

The aliases follow the ARM ARM's *preferred disassembly* conditions, which are what LLVM's printer and `llvm-objdump` print.

## Data items

A data item is one directive's worth of a data section: a kind and either a value or a symbol reference. The slice has one kind, `long`, a 32-bit value. Later kinds (`byte`, `short`, `quad`, a symbol reference such as `.quad _g+4`, strings in a pool) arrive with the types that need them.

## From MIR

MIR → MCIR runs once per function, after that function's frame lowering and its MIR verifier. It runs once more for the globals, after the last function. It keeps two side tables: MIR function or global → symbol, for the translation unit, and MIR block → temporary symbol, for one function.

**Before the first function**

- It sets the module fields from the target.
- It creates every module symbol up front: one named symbol per function of the MIR module, then one per global, in module order. An internal declaration that is never defined is skipped. Sema guarantees nothing refers to it, and Mach-O has no undefined local symbols. External entities are `global` and internal ones `local`. Each symbol takes its function's or global's location and stays undefined until its atom is appended.
- **Names are made unique as the symbols are created**, by clang's scheme. A name that an earlier symbol already has gets the first free suffix of `.1`, `.2`, …, so two `static int n` in `f` become `f.n` and `f.n.1`. Only internal names repeat: external names are unique by the time they reach HIR. The suffix is not the `.N` entity id that the HIR and FIR printers add to repeated names. Those are display only, and this is the symbol's real name.

**Each function**

- It appends one atom in `__TEXT,__text`, aligned to 2², with the function's symbol defined at offset 0.
- A first walk over the blocks' branches finds every block that a branch targets, not counting a `b` to the next block in layout. It creates their temporary symbols in layout order. A block reached only by falling through gets none, and neither does the entry block, which has no predecessors.
- A second walk goes through the blocks in layout order:
  - It defines each block's temporary symbol at the atom's current offset.
  - It copies each instruction with its opcode and fields unchanged. Block targets become references to temporary symbols, and MIR's references to functions and globals become references to their symbols.
  - It drops a `b` to the next block.
- A block's branches arrive as real instructions: a conditional branch followed by a `b` to the other target, a single `b`, or `ret`. There is no instruction selection, every MIR pseudo has been expanded, and register allocation has removed every block parameter.

**After the last function**

- Each defined global gets one atom, in module order, aligned to 2²:
  - A global with an initializer goes in `__DATA,__data`, with one `long` item.
  - A zerofill global goes in `__DATA,__bss`, with size 4.
- A declared global gets no atom, and its symbol stays undefined.
- The verifier runs, then the printers.

Appending the globals after the functions puts the text section first in the output, as clang does.

## Locations

Every MCIR entity has a location, following the rules in [docs/ir-data-layout.md](ir-data-layout.md#locations), with these choices:

- An **instruction** takes its MIR instruction's. MIR's own rules have already given register-allocation moves and the prologue and epilogue theirs.
- A **data item** takes its global's.
- A **named symbol** takes its function's or global's, which is the declaration's for an undefined one. A **temporary symbol** takes its block's, which is the location of the block's first instruction.
- An **atom** stores none and takes its symbol's.
- A **section** has none. It serves the whole translation unit, and no source position means anything for `__DATA,__bss`. The verifier doesn't ask for one.

## Printed form

`-emit-mcir` prints what MCIR stores. It prints the module once, after the globals' atoms are appended and the verifier passes, because the module lives for the translation unit. It prints no locations.

- **Header:** `module "t.c" macos 11.0, subsections_via_symbols`.
- **Sections** print in id order as `section __TEXT,__text regular, pure_instructions`, each followed by its atoms in array order.
- **Atoms** print as `atom @add global, align 2`, indented two spaces, with their contents below, indented four. A zerofill atom ends its line with `size 4` and has no contents.
- **Symbols:** `@name` for named and private ones, with their real names. Those are unique, so no `.N` is added. A temporary symbol prints as `^N`, where `N` is its id, outdented to the atom's level at its position, as FIR's blocks are: `^5:`.
- **Instructions** print in their stored form:
  - the opcode's name, then the operands in the base instruction's assembly order
  - no aliases
  - `wzr`/`xzr` and `sp` explicit
  - every field printed, defaults included (`lsl #0`)
  - `b_cond` prints its condition as an operand: `b_cond le, ^5`
- **References** print as `@f`, `^5`, `page(@g)`, `pageoff(@g)`, `gotpage(@e)` and `gotpageoff(@e)`, with any addend inside the parentheses: `pageoff(@g+4)`.
- **Data items** print as `long 5`.
- **Undefined symbols** print last, one per line, as `undefined @putchar`.

## Assembly

The `-S` printer writes Apple-syntax assembly, which is what `forge -c` hands to the host assembler. The output is byte-for-byte deterministic, with `\n` line endings on every host ([How the slice produces the .o](https://github.com/jmuratov98/forge/issues/14)).

- **Start:** `.section __TEXT,__text,regular,pure_instructions` and `.build_version macos, 11, 0`, as clang begins, even when the module has no code.
- **Atoms** print in array order, with a `.section` line whenever the section changes. A `regular` section with no attributes prints as `.section __DATA,__data`.
  - **Named symbols:** a global named symbol first gets `.globl _f`. Then the atom prints `.p2align 2`, with `, 0x0` added in data sections as clang does, then `_f:`, then its contents.
  - **Zerofill atoms** print as one self-contained `.zerofill __DATA,__bss,_f.n,4,2` at column 0, which switches no section.
- **Spelling:**
  - named symbols as `_name`
  - private symbols as `l_name`
  - unnamed temporary symbols as `L<id>`, the id the dump prints as `^<id>`
  - modifiers as `_g@PAGE`, `_g@PAGEOFF`, `_e@GOTPAGE` and `_e@GOTPAGEOFF`
- **Undefined symbols** print nothing of their own. The assembler creates them from the references.
- **Instructions** print as `\t<mnemonic>\t<operands>`, with the preferred alias from [The slice's forms](#the-slices-forms) and LLVM's operand spelling: `#` and decimal for arithmetic immediates (`#-16`), hex for logical immediates (`#0xff`), `[x8, _g@PAGEOFF]`, `[sp, #-16]!`, `[sp], #16`.
- **Data items:** `\t.long\t5`.
- **No comments:** no `; =0x5`, `; %bb.N` or `; -- Begin function`. No `.loh` or `.cfi_*` directives either.
- **End:** `.subsections_via_symbols` at column 0, as the last line.

## Verifier

These checks run after the structural checks every verifier starts with ([docs/ir-data-layout.md](ir-data-layout.md#verification)), and only if those pass. The verifier runs once, after the globals' atoms are appended and before either printer, in Debug and RelWithAsserts.

- **Sections**
  - No two sections have the same segment and section names.
  - A `zerofill` section holds only zerofill atoms, a section with `pure_instructions` only code atoms, and any other section only data atoms. Mixed contents (jump tables, literal pools) aren't in the slice.
- **Atoms**
  - Taken in atom order, the code atoms' ranges cover the instruction array with no gaps or overlaps, and the data atoms' ranges do the same for the data-item array.
  - Every atom is non-empty, and starts at its own named or private symbol, defined at offset 0 of that atom.
  - A code atom is aligned to at least 2², and its last instruction is `b`, `br` or `ret`, so nothing falls through into the next atom.
- **Symbols**
  - Named and private symbols have names, and no two of them have the same one.
  - An undefined symbol is named and `global`.
  - A defined symbol's offset lies inside its atom.
  - Every temporary symbol is defined, at an instruction of a code atom, and only instructions of that same atom refer to it.
  - In the slice, no named or private symbol is defined in the middle of an atom.
- **Instructions**
  - The opcode is valid, and every field is valid for its format:
    - Every register slot holds what it can take for register 31, `sp` or `zr`.
    - Fields the format doesn't use are zero.
  - Every immediate can be encoded:
    - `imm12` with a shift of 0 or 12
    - `imm16` with a shift the width allows
    - logical immediates
    - byte offsets aligned to the access size and in range
    - shift amounts below the width
    - `immr`/`imms` below the width
- **References**
  - The modifier fits the form:
    - `adrp` takes `page` or `gotpage`.
    - `add_imm` takes `pageoff`.
    - An unsigned-offset load or store takes `pageoff`, and a 64-bit `ldr_imm` may take `gotpageoff`.
    - Branches take `none`.
  - GOT modifiers refer only to named symbols.
  - `b_cond`, `cbz` and `cbnz`, and later `tbz` and `tbnz`, refer only to temporary symbols.
  - The addend is 0 on GOT references and references to temporary symbols, and fits in Mach-O's signed 24 bits on every other reference.
- **Data items:** in the slice, only `long`.

Not checked here:

- **x18 and frame records.** That x18 is never used and that every non-leaf function builds a frame record are C codegen and ABI rules, for MIR's verifier after register allocation. They aren't MCIR well-formedness, and fas will take hand-written assembly.
- **Branch and fixup ranges.** Checking them needs a layout. The host assembler reports them in the slice, and the encoder will later.

## What MCIR's consumers need

ADR 0008 asks each layer to say which lowering removes the structure it adds. Nothing comes after MCIR. Its consumers turn it into text or an object file:

- **The assembly printer**, in the slice, as above.
- **fas**, later: an assembly parser that builds this same module, then an encoder that switches over format and an object writer. The writer:
  - lays out the sections, with zerofill ones last, and the atoms in each section
  - resolves temporary symbols and conditional branches within their atoms
  - writes a relocation for every other reference, with an `ADDEND` record before any nonzero addend
  - writes only the undefined symbols something refers to
  - adds `S_ATTR_SOME_INSTRUCTIONS` to sections that hold instructions, as `as` does

## Worked examples

`docs/ir-data-layout.md` shows `add` at every layer. Here it is in memory, with locations written as `line:col`:

```
MCIR   module "t.c"   macos 11.0, subsections_via_symbols
         sections  [0] __TEXT,__text  regular  pure_instructions
         atoms     [0] s0  align 2  symbol 0  insts [0, 2)
         symbols   [0] add  named  global  atom 0 + 0                    1:5
         insts     [0] add_shifted  w  lsl  w0 w0 w1 0   payload 0       1:34
                   [1] ret          x       x30          payload 0       1:25
```

`-emit-mcir`:

```
module "t.c" macos 11.0, subsections_via_symbols

section __TEXT,__text regular, pure_instructions
  atom @add global, align 2
    add_shifted w0, w0, w1, lsl #0
    ret x30
```

`-S`:

```
	.section	__TEXT,__text,regular,pure_instructions
	.build_version macos, 11, 0
	.globl	_add
	.p2align	2
_add:
	add	w0, w0, w1
	ret
.subsections_via_symbols
```

A call, a branch, a global and a `static` local. The instructions are illustrative, because instruction selection and frame lowering belong to MIR's design:

```c
int g = 5;
int putchar(int);

int f(int x) {
  static int n;
  n += x;
  if (x > 10)
    putchar(x);
  return g + n;
}
```

Symbols are created up front: functions first, then globals, in module order. So `putchar` is 0, `f` is 1, `g` is 2 and `f.n` is 3. The branch target's temporary symbol is 4.

```
module "t.c" macos 11.0, subsections_via_symbols

section __TEXT,__text regular, pure_instructions
  atom @f global, align 2
    stp_pre x29, x30, [sp, #-16]!
    add_imm x29, sp, #0, lsl #0
    adrp x8, page(@f.n)
    ldr_imm w9, [x8, pageoff(@f.n)]
    add_shifted w9, w9, w0, lsl #0
    str_imm w9, [x8, pageoff(@f.n)]
    subs_imm wzr, w0, #10, lsl #0
    b_cond le, ^4
    bl @putchar
  ^4:
    adrp x8, page(@g)
    ldr_imm w8, [x8, pageoff(@g)]
    adrp x9, page(@f.n)
    ldr_imm w9, [x9, pageoff(@f.n)]
    add_shifted w0, w8, w9, lsl #0
    ldp_post x29, x30, [sp], #16
    ret x30

section __DATA,__data regular
  atom @g global, align 2
    long 5

section __DATA,__bss zerofill
  atom @f.n local, align 2, size 4

undefined @putchar
```

```
	.section	__TEXT,__text,regular,pure_instructions
	.build_version macos, 11, 0
	.globl	_f
	.p2align	2
_f:
	stp	x29, x30, [sp, #-16]!
	mov	x29, sp
	adrp	x8, _f.n@PAGE
	ldr	w9, [x8, _f.n@PAGEOFF]
	add	w9, w9, w0
	str	w9, [x8, _f.n@PAGEOFF]
	cmp	w0, #10
	b.le	L4
	bl	_putchar
L4:
	adrp	x8, _g@PAGE
	ldr	w8, [x8, _g@PAGEOFF]
	adrp	x9, _f.n@PAGE
	ldr	w9, [x9, _f.n@PAGEOFF]
	add	w0, w8, w9
	ldp	x29, x30, [sp], #16
	ret
	.section	__DATA,__data
	.globl	_g
	.p2align	2, 0x0
_g:
	.long	5
.zerofill __DATA,__bss,_f.n,4,2
.subsections_via_symbols
```

`putchar` never reaches the assembly as a symbol of its own: `bl _putchar` makes the assembler create it.

A second `static int n` in another block of `f` would get the symbol `f.n.1`, and `_f.n.1` in the assembly.
