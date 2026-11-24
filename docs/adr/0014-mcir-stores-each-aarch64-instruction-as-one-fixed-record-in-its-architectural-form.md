# MCIR stores each AArch64 instruction as one fixed record in its architectural form

An MCIR instruction is one 16-byte record, interpreted by the opcode's format. It holds an opcode, a width flag and a reference modifier, a condition or shift kind, four one-byte operand fields, and an 8-byte payload that is either an immediate or a symbol reference.
- **Opcodes** are the ARM ARM's instruction forms (`add_imm`, `add_shifted`, `ldr_imm`, `ldp_pre`), never aliases such as `cmp`, `mov` or `mul`.
- **Values** are stored as the base instruction's assembly writes them (byte offsets, immediates with their shifts, a logical immediate's value), not as encoded bitfields.
- **Registers:** a register field tells `sp` apart from `zr`.

MCIR is the seam fas will reuse (ADR 0007), so one record has to serve the assembly printer now and fas's parser, encoder and object writer later. AArch64's fixed-width instructions have bounded operands, so each fits ADR 0011's 16-byte record with no pool, and one record reads as one line of assembly.

## Considered Options

- **An opcode and an operand list in a pool** (LLVM's `MCInst`). Generic and table-driven, so every consumer can loop over operands. But an instruction then costs about 36 bytes across its record and its operands, and generic operand kinds are a design for the generator framework ADR 0001 dropped.
- **Alias opcodes** (`cmp`, `mov`, `mul`). MIR → MCIR's output would read like the assembly, but one instruction would have two representations that every consumer has to treat as equal, and fas's parser would have to canonicalize them anyway.
- **Encoded fields**, as LLVM does for some operands: a logical immediate as `N:immr:imms`, a load offset scaled by the access size. The encoder becomes trivial, but the printer has to decode, and instruction selection and the parser have to encode. A record would no longer read as its assembly.
- **A bare 5-bit register number**, as in the encoding. Register 31 is `sp` in some slots and `zr` in others, so `add w0, sp, w1` built in shifted-register form would silently encode as `wzr`. A distinct `sp` lets the verifier reject it.

## Consequences

- The printers, the verifier, and later the encoder and parser, are each one switch over format, about twenty in the slice.
- The `-S` printer chooses aliases by the ARM ARM's preferred-disassembly rules. LLVM's printer and `llvm-objdump` follow the same rules, so Forge's assembly and a disassembly of its object pick the same aliases. `-emit-mcir` prints the stored form.
- The verifier checks that every value can be encoded in its form, using the helpers that instruction selection already needs to choose a form.
- MIR uses the same opcode enum and adds its own pseudos, which are all expanded before MIR → MCIR. Sharing a target's opcode table is not the common instruction class ADR 0011 rules out. MIR → MCIR copies instructions and never selects them.
- The record is AArch64's own. x86-64's memory operands won't fit these fields, so another architecture gets its own record, and how both sit behind one module belongs with making the target a parameter.
- The working rules are in [docs/mcir.md](../mcir.md).
