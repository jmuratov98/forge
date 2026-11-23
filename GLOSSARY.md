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

**fcc1**:
Forge's C compiler proper: the program that turns C source into assembly. `forge` runs it in-process or as a separate process.
_Avoid_: cc1 (GCC's), the frontend (fcc1 runs the backend too)

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

## Driver

**Phase**:
One step a driver input passes through: preprocess, compile, assemble or link. An input starts at the phase its type implies and stops at the phase its mode names.
_Avoid_: stage, pass (a pass transforms IR)

**Job**:
One concrete unit of driver work produced from the phases: an in-process call or a subprocess command line.
_Avoid_: task, step
