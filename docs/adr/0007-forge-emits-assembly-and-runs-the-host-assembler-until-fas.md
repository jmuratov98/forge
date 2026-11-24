# Forge emits assembly and runs the host assembler until fas exists

Until fas exists, `forge -c` does not write object files itself. MCIR is printed as assembly in the target's own syntax to a temporary file, and the driver runs the host assembler on it: `as -arch arm64` on macOS for the first slice's `aarch64-apple-darwin` target. The goal is to broaden the compiler before building the assembler, so the encoder and object writer arrive with fas, not before. When the host has no assembler for the target (in the slice, every host but macOS), `forge -c` gives a diagnostic and `forge -S` still works.

## Considered Options

- **Write Mach-O directly from MCIR.** A minimal writer is a few hundred lines and would make `forge -c` work on every host. It was deferred, not rejected: it is fas's object writer, built ahead of the assembler.
- **Run `llvm-mc` or `clang` as the assembler on every host.** This would give `-c` everywhere LLVM is installed, but at the cost of discovery logic and an LLVM dependency for users. `llvm-mc` stays a test tool.

## Consequences

- MCIR is the seam fas will reuse: fas will be an assembly parser that produces MCIR, followed by an encoder and object writer. So MCIR models a whole object module (sections, symbols and their binding, labels, instructions with symbolic operands and relocation modifiers, data), not just one function's instructions. The slice only fills in what C codegen needs.
- MCIR records what kind each label is (temporary label, private symbol, named symbol) and stores C-level names. Target-specific spelling (Darwin's leading `_`, `L` temporaries, `l_.str.N`) happens only in the assembly printer, and later in the object writer.
- The host assembler resolves branches and fixups. Darwin has no relocation for conditional branches, so their targets must be `L` temporaries within the same function.
- Tests on hosts without a host assembler for the target assemble `forge -S` output with `llvm-mc` themselves.
