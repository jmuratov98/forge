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

**C frontend**
The part of Forge's C compiler that turns C source into a C AST and lowers it to Ingot.
_Avoid_: "the frontend" when the C++ frontend could also be meant.

**C++ frontend**
The part of Forge's C++ compiler that turns C++ source into a C++ AST and lowers it to Ingot. It has its own parser, semantic analysis, and AST, separate from the C frontend's.
_Avoid_: "the frontend" when the C frontend could also be meant.

**C-family layer**
The library beneath the C frontend and the C++ frontend that holds what the two languages share: the preprocessor, the lexer, and the rules that are the same in C and C++.
_Avoid_: "c-common", "shared frontend".

**core**
The library every other part of Forge builds on: containers, strings, algorithms, text formatting, I/O, threads, and the platform layer over the host OS. In Forge's own source it takes the place of the C++ standard library.
_Avoid_: "Support", "ADT", or "the standard library" for it; flibc++ is the standard library Forge ships to users.

**Forge runtime**
The low-level support Forge links into every program it builds, on every platform: the startup objects that run before `main`, and the compiler builtins that generated code calls for operations the target lacks.
_Avoid_: using "runtime" for the unwinder, the C++ ABI support, or a runtime for the Forge language. Those are separate.

**Drop-in replacement**
The property that Forge can stand in for gcc, clang, or msvc in an existing build: it accepts their command-line flags, links against libraries and objects they built, and compiles the platform's system headers. It does not promise every flag or identical output.

**driver**
The part of Forge that reads a command line in one of the styles it accepts (gcc/clang, cl.exe, assembler, or linker) and runs the compilers, fas, and fold to carry it out.
_Avoid_: "frontend" for it; a frontend turns source into Ingot.

**fas**
Forge's assembler: it turns assembly source into object files. The compilers read inline assembly through it too.

**fold**
Forge's linker: it combines object files and libraries into executables and shared libraries, in the flavor of each platform's native linker.
_Avoid_: `fold` as a command name; that is the POSIX line-wrapping utility. The command is `fld` or a flavor name.

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
