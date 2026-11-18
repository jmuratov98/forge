# Roadmap

Each milestone is a vertical slice with a testable exit criterion. Milestones after M1 get their own planning effort when they come up; this ladder fixes their order and their exit criteria, not their contents.

| #   | Milestone             | Adds                                                                                                                                       | Done when                                                                                     |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| M0  | Skeleton              | Repo layout, CMake + Ninja, the multi-call `forge` binary, versioning (ADR 0001), googletest + end-to-end runner, CI on Linux, macOS, Windows (MSVC), and MinGW | CI green on all four hosts; `forge --version` prints a dev version                          |
| M1  | First light           | A small C subset through every IR layer to text assembly for **arm64 macOS**, using the system `as` and `ld`; no optimization                | A corpus of small programs gives the same exit code and stdout as clang                      |
| M2  | Real C                | Full C17, the preprocessor, the platform's system headers, **arm64 Linux and x86-64 Linux**, DWARF line info                               | Lua 5.4 builds and passes its own tests on all three targets                                  |
| M3  | fas                   | Built-in assembler writing ELF and Mach-O objects directly, plus a standalone `fas`; the system `as` is no longer used                      | M2 still passes, built through fas                                                            |
| M4  | fold                  | ELF and Mach-O linker; the system `ld` is no longer used                                                                                   | M2 still passes; fold also links clang-built objects                                          |
| M5  | Optimizer             | Optimization passes                                                                                                                        | Speed goals met on a C benchmark suite                                                        |
| M6  | Windows               | COFF/PE, the Win64 C calling convention, the `cl.exe`-style driver, CodeView/PDB, MinGW                                                    | Lua passes on native Windows and on MinGW                                                     |
| M7  | C breadth             | C89 through C2y modes, GNU and MSVC extensions, RISC-V                                                                                     | SQLite passes its tests on every target                                                       |
| M8  | flibc + Forge runtime | Startup objects, compiler builtins, the C library                                                                                          | Lua and SQLite pass when linked against flibc (Linux)                                         |
| M9  | C++ (Itanium ABI)     | Forge's C++ compiler, the Itanium C++ ABI                                                                                                  | Forge compiles itself against the system libstdc++ or libc++ (self-hosting, first stage)     |
| M10 | C++ (MSVC ABI)        | The MSVC C++ ABI                                                                                                                           | Forge compiles itself on Windows                                                              |
| M11 | More optimization     | C++-oriented optimization                                                                                                                  | Speed goals met on C++ benchmarks                                                             |
| M12 | flibc++               | The C++ standard library, the unwinder, the C++ ABI runtime                                                                                | Forge compiles itself using flibc++ (self-hosting, final stage)                               |
| —   | Forge language        | The Forge language and flibforge                                                                                                           | Planned separately                                                                            |

## Speed goals

Both are upper bounds measured against gcc and clang; being faster is never a miss.

- **Compile time**: at most 1.25× gcc's or clang's, at the same `-O` level.
- **Generated code**: at most 1.25× slower, at `-O2`.
