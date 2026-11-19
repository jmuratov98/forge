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
The SSA representation shared by every language and every target, where optimization happens. It depends on the target only through its data layout and through any target intrinsics a module uses, never through its calling conventions.
_Avoid_: confusing it with Flang's FIR.

**Target intrinsic**
A Billet intrinsic that exists only on one instruction set, such as a Neon dot product. A module that uses one can be compiled only for a target with that instruction set.
_Avoid_: "builtin" for it; builtins are what the frontends expose to source code.

**Blank** (MIR, _Machine IR_)
The representation of one function as one target's instructions, where register allocation happens.
_Avoid_: "MIR" in rustc's sense of a mid-level IR.

**Stamp** (MC or MCIR, _Machine Code_)
The last representation before bytes: encodable instructions with the sections, symbols, and relocations of an object file. Both the compiler and fas produce it.

**Source manager**
The part of Forge that owns one translation unit's source: every file it includes and every macro expansion, and the locations that point into them. It answers where a location is: its file, line, and column, what included that file, and which macro expansions produced it.
_Avoid_: "file manager" for it; the file manager sits beneath it and knows nothing of translation units.

**File manager**
The cache of files read through the file-system interface, one entry per file on disk, identified by the operating system rather than by path. Several source managers can share one.

**File-system interface**
The one route by which Forge reads files and directories. Behind it can be the real disk, files held in memory, or in-memory buffers laid over the disk, which is how a language server supplies files the user has not saved.
_Avoid_: "VFS".

**Inclusion**
One entry of a file into a translation unit: the main file, or a file named by one `#include`. A header included twice is two inclusions of one file.
_Avoid_: "file" when one particular entry is meant.

**Expansion**
One use of a macro and the tokens it produced. A token that came from a macro has a chain of expansions, from the innermost macro out to the use in the source the user wrote.

**Spelling position**
The file, line, and column where a piece of text physically is.

**Presumed position**
The file and line a piece of text claims to have, after `#line` directives and line markers. Diagnostics, `__FILE__`, `__LINE__`, and debug locations use it; edits to the source use the spelling position.

**Source location**
A point in a translation unit's source, as the frontends, the C-family layer, fas's assembly parser, and Ingot see it. It knows its inclusion, its spelling position, and, for text that came from a macro, the chain of expansions that produced it. It means something only to the source manager that made it.

**Debug location**
A file, line, and column, which is all Billet, Blank, and Stamp know of where code came from. It is what debug-info line tables record, so it keeps no macro expansions.
_Avoid_: "source location" for it.

**Diagnostic**
One message to the user about their input: a severity, a position (a source location, a debug location, an input such as a file or object, or nothing), a message, and the notes and fix-its that belong to it. Every failure the user hears about is a diagnostic.
_Avoid_: "error" for a diagnostic in general; an error is one severity.

**Diagnostics engine**
The part of Forge that every producer reports diagnostics to during one compilation. It decides each diagnostic's final severity, counts errors, and passes what survives to the diagnostic consumer.

**Diagnostic consumer**
Whatever receives finished diagnostics from the diagnostics engine: a text renderer, a SARIF writer, a language server, or a test checker.

**Warning group**
A named set of warnings that one flag turns on, off, or into errors, such as `unused-variable` for `-Wunused-variable`. Groups nest: `all` contains `unused`, which contains `unused-variable`. Every warning belongs to exactly one group.
_Avoid_: "warning flag" for the group itself; the flag is how a command line names it.

**Note**
A diagnostic's supporting message that points somewhere else, such as "previous declaration is here". A note belongs to one diagnostic and is never reported on its own.

**Fix-it**
A suggested edit attached to a diagnostic or note: replace a range of source text with new text.

**Baseline compiler**
A compiler Forge's speed goals are measured against: gcc and clang on every host, plus AppleClang on macOS. On each metric, the best of them is the bar.
_Avoid_: "reference compiler", which means the compiler the end-to-end tests take their expectations from.

**Baseline series**
A run of benchmark results that all used the same versions of the baseline compilers. Results are only compared within one series.

**Reference machine**
A named, fixed machine, physical or virtual, that benchmarks run on with nothing else running. Results from different reference machines are never compared.
_Avoid_: "benchmark host", "CI runner".
