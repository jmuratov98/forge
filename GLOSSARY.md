# Forge

Forge is a C++20 compiler toolchain built as a learning project: compilers for C, C++ and the Forge Language, plus the assembler, linker and developer tools around them.

## Products

**Forge**:
The toolchain as a whole: every tool and library in this project.
_Avoid_: using "Forge" alone to mean the language

**Forge Language**:
The project's own programming language, compiled by Forge alongside C and C++.
_Avoid_: Forge (unqualified), forge-lang

**forge**:
The compiler driver binary; the command users invoke in place of `gcc`, `clang` or `cl`.
_Avoid_: fcc, the compiler (when the driver specifically is meant)

**fas**:
Forge's assembler.

**fold**:
Forge's linker, also invocable under compatibility names such as `ld.fold`, `fld` and `fold-link.exe`.

## Intermediate representations

**AST**:
A language-specific syntax tree owned by one frontend (C, C++ or Forge Language), lowered into HIR.

**HIR** (High IR):
The language-independent, non-SSA representation shared by every language frontend.

**FIR** (Forge IR):
The SSA representation in which target-independent optimization happens.
_Avoid_: SIR

**MIR** (Machine IR):
A target-specific representation of instructions over virtual or physical registers.

**MCIR** (Machine Code IR):
The representation closest to encoded machine instructions, from which object files and assembly are emitted.

## Source locations

**Spelling location**:
Where a token's characters are written in the source.
_Avoid_: source location (when this one specifically is meant)

**Expansion location**:
Where the macro that produced a token was used; for nested expansions, each level has its own.
_Avoid_: instantiation location, use site
