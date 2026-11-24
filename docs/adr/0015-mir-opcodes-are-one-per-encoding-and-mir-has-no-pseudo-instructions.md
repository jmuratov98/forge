# MIR opcodes are one per encoding, and MIR has no pseudo-instructions

A MIR opcode is one AArch64 encoding form of a mnemonic: `add_rr` and `add_ri`, `lsl_rr` and `lsl_ri`, `mov_rr` and `mov_ri`, `cmp_rr` and `cmp_ri`, `ldr_ui`. The register width comes from the operands' register class, not from the opcode, so `add_rr` adds `w` or `x` registers. The aliases `mov`, `cmp`, `neg`, `mvn`, `cset` and `mul` are opcodes of their own, which is why the zero register is never an operand. MIR has no pseudo-instructions: every non-terminator prints as exactly one AArch64 instruction, register allocation's moves are `mov_rr`, and `ret` is the real `ret`. The assembler picks an encoding from the operand values, and instruction selection and frame lowering do the same in Forge, so what the verifier checks is what the assembler will accept: `ldr w0, [x29, #-4]` and `ldr w0, [sp, #2]` assemble as `ldur`, `cmp w0, #-1` as `cmn w0, #1`, `cmp w0, #4096` as `cmp w0, #1, lsl #12`, and `add w0, w1, #4097`, `mov w0, #0x12345678` and `eor w0, w1, #-1` don't assemble at all.

## Considered Options

- **One opcode per mnemonic,** with the form chosen by the operands and a shape table, leaving the choice of encoding to the assembler and later to fas. Smaller at first, and it keeps encoding selection in one place, but then MIR's verifier has to predict what the assembler would pick, and fas's parser needs the same selection to turn assembly back into instructions.
- **Width in the opcode** (`add_wri`, `add_xri`), as LLVM has it. 45 opcodes for the slice instead of 37, and the width would then have two sources of truth, the opcode and the register class.
- **Pseudo-instructions** (LLVM's `COPY`, a fused compare-and-branch). They would make isel and register allocation more generic, but they hide what a MIR dump will print and need expanding before MCIR.

## Consequences

- Instruction selection and frame lowering own the choice of encoding. The slice avoids the hard cases: frame lowering addresses everything from `sp` with non-negative, size-aligned offsets, so there is no `ldur`, `stur` or `cmn_ri`, and a constant that doesn't fit an immediate form is materialized into a register.
- Each opcode has an immediate rule that the verifier checks (`add_ri`, `sub_ri` and `cmp_ri` take 0–4095 or a multiple of 4096 up to `0xFFF000`, and so on; see [docs/mir.md](../mir.md#opcodes)). The verifier is narrower than the assembler.
- Growing the instruction set adds opcodes and rules, such as logical immediates for `and_rr`, and a MIR dump prints opcode names, which tests match.
