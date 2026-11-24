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

**Block parameter**:
A value that a FIR or MIR block receives from each predecessor's edge, in place of a φ-node.
_Avoid_: φ-node, phi

**Block argument**:
The value an edge passes for one block parameter.

**Edge**:
One successor of a FIR or MIR terminator: a target block and one block argument per parameter of that block.
_Avoid_: branch target (which leaves out the arguments)

**Parallel move**:
A set of moves that read all their sources before any destination is written: what one edge's block arguments become when register allocation removes them.
_Avoid_: phi copies, swap

**Module**:
One IR layer's representation of a translation unit: its globals and functions. HIR and MCIR modules keep every function's body; FIR and MIR modules keep only signatures, and their bodies come and go one function at a time.
_Avoid_: translation unit (the C source), object file (what an MCIR module becomes)

**Body**:
One function's code in an IR layer, as distinct from its signature in the module.
_Avoid_: function body (the C syntax), function IR

**Local**:
A parameter or automatic variable of one function in HIR. A C `static` local is not a local: it becomes a global.
_Avoid_: variable (alone), temporary

**Global**:
A variable of the module rather than of one function, including a C `static` local hoisted out of its function.
_Avoid_: static (which names a linkage), file-scope variable

**Label**:
A position in a HIR body that `goto` and `switch` jump to. Each C `case` and `default` becomes an unnamed label.
_Avoid_: case, case label (in HIR)

**Virtual register**:
A value in a MIR body before register allocation, of one register class and defined exactly once.
_Avoid_: temporary

**Physical register**:
A register of the target machine, which a MIR operand names once register allocation has run or where the ABI fixes it.
_Avoid_: hardware register, machine register

**Scratch register**:
A physical register that register allocation never assigns, kept for the moves and address computations that register allocation and frame lowering insert.
_Avoid_: reserved register (one the platform forbids, such as `x18`)

**Register class**:
The kind of value a virtual register holds, which fixes its width and which physical registers can hold it.
_Avoid_: register type, register bank

**Constraint**:
A requirement on where a MIR operand lives: a particular physical register, or the same register as another operand of its instruction.
_Avoid_: hint, precolouring

**Frame object**:
A region of a function's stack frame that a MIR body names by index: the caller's argument area, the area for its own calls' arguments, or a spill slot.
_Avoid_: stack slot (alone)

**Spill slot**:
The frame object that holds one virtual register's value wherever no register holds it.
_Avoid_: stack slot, spill area

**Frame record**:
The saved frame pointer and return address that a function which makes calls keeps at the top of its stack frame, and that the frame pointer points at.
_Avoid_: frame pointer (the register that points at it), stack frame (the whole frame)

**Leaf function**:
A function that makes no calls, and so keeps no frame record.
_Avoid_: frameless function (a leaf can still have a frame for its spill slots)

**MIR state**:
How far register allocation and frame lowering have rewritten a MIR body: before allocation, after it, or after frame lowering.
_Avoid_: phase (the driver's), stage

**Symbol**:
A name in an MCIR module for a position in a section, or for something another object defines. A named symbol carries a C-level name into the object's symbol table, a private one reaches the table but is never exported, and a temporary one never leaves the assembler.
_Avoid_: label (in MCIR; Label is HIR's), local label

**Atom**:
A contiguous run of one section's contents, starting at its symbol, that the linker moves or strips as a unit: in the slice, one function's code or one global's data.
_Avoid_: fragment, chunk, subsection

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
