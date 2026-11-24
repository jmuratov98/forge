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

## C

**C dialect**:
The variant of C a compilation is checked against, selected by `-std=`: either an ISO standard (`c89`) or a GNU dialect, which is a standard plus GCC's extensions (`gnu89`).
_Avoid_: standard (for a GNU dialect), language mode

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

**Lowering**:
The translation of a program from one IR layer to the next, which removes one kind of structure.

**Block argument**:
A value that a FIR or MIR block receives from each predecessor's branch, in place of a φ-node.
_Avoid_: φ-node, phi

## Development

**dev script**:
The developer entry point (`dev.py` and its `dev`, `dev.bat` and `dev.ps1` shims) that sets up, builds, tests and lints Forge. It is not part of Forge's shipped tools.
_Avoid_: the wrapper, forge.py

## Source locations

**Spelling location**:
Where a token's characters are written in the source.
_Avoid_: source location (when this one specifically is meant)

**Expansion location**:
Where the macro that produced a token was used; for nested expansions, each level has its own.
_Avoid_: instantiation location, use site

## Host tools

**Host assembler**:
The platform's own assembler, which `forge` runs to produce object files until fas exists.
_Avoid_: system `as` (when the platform-neutral role is meant)

## Driver

**Phase**:
One step a driver input passes through: preprocess, compile, assemble or link. An input starts at the phase its type implies and stops at the phase its mode names.
_Avoid_: stage, pass (a pass transforms IR)

**Job**:
One concrete unit of driver work produced from the phases: an in-process call or a subprocess command line.
_Avoid_: task, step
