# Glossary

**Forge**
The whole toolchain: the driver, the compilers, the assembler (fas), the linker (fold), the standard libraries, and the developer tools.
_Avoid_: using "forge" alone to mean the homebrew language or any single compiler.

**Forge language**
The homebrew programming language that Forge compiles alongside C and C++. Placeholder name; may be renamed.
_Avoid_: "forge" (unqualified).

**Forge's C compiler**
The part of Forge that compiles C, from ANSI C through C2y.

**Forge's C++ compiler**
The part of Forge that compiles C++, from C++98 through C++26.

**Forge runtime**
The low-level support Forge links into every program it builds, on every platform: the startup objects that run before `main`, and the compiler builtins that generated code calls for operations the target lacks.
_Avoid_: using "runtime" for the unwinder, the C++ ABI support, or a runtime for the Forge language. Those are separate.

**Drop-in replacement**
The property that Forge can stand in for gcc, clang, or msvc in an existing build: it accepts their command-line flags, links against libraries and objects they built, and compiles the platform's system headers. It does not promise every flag or identical output.

**Ingot** (HIR, _High IR_)
The typed, tree-shaped representation that every frontend lowers its source into, whatever the language. It is the first layer that is independent of the source language.
_Avoid_: "AST" for it; each frontend's AST is the language-specific tree above it.

**Billet** (FIR, _Forge's IR_)
The SSA representation shared by every language and every target, where optimization happens. It depends on the target only through its data layout, never through its calling conventions.
_Avoid_: confusing it with Flang's FIR.

**Blank** (MIR, _Machine IR_)
The representation of one function as one target's instructions, where register allocation happens.
_Avoid_: "MIR" in rustc's sense of a mid-level IR.

**Stamp** (MC or MCIR, _Machine Code_)
The last representation before bytes: encodable instructions with the sections, symbols, and relocations of an object file. Both the compiler and fas produce it.
