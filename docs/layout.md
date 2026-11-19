# Layout

How Forge's source is divided into libraries, which libraries may depend on which, and the names the `forge` binary answers to. Why there is one multi-call binary is in [ADR 0002](adr/0002-libraries-and-one-multi-call-binary.md). Why it answers to these names is in [ADR 0010](adr/0010-command-names-of-the-multi-call-binary.md).

## Top level

| Directory  | Holds                                                                                  |
| ---------- | -------------------------------------------------------------------------------------- |
| `cmake/`   | CMake modules: compiler flags and minimums, build configurations, version generation, the library helper, test setup |
| `docs/`    | ADRs, the roadmap, and the guides                                                      |
| `forge/`   | The host libraries below and the `forge` executable                                    |
| `test/`    | Test suites that cross libraries; `test/e2e/` is the end-to-end corpus                 |
| `scripts/` | Dev and test tooling: `update-e2e`, the lit test format, the policy checks, CI helpers |
| `runtime/` | The Forge runtime, built by Forge for each target (M8)                                 |
| `flibc/`   | The C library, built by Forge for each target (M8)                                     |
| `flibcxx/` | The C++ standard library, built by Forge for each target (M12)                         |

Inside `forge/`, each library lives in a directory named after it, with its own include root, so a library can include only the headers of libraries it links:

| Path                                  | Holds                                                            |
| ------------------------------------- | ---------------------------------------------------------------- |
| `forge/<name>/include/forge/<name>/`  | Public headers. core's sit directly in `include/forge/`          |
| `forge/<name>/src/`                   | Sources and private headers, on no other library's include path  |
| `forge/<name>/test/`                  | The library's googletest sources                                 |

`forge_add_library` ([building.md](building.md)) creates this and enforces the dependency rules below at configure time. The `forge` executable's own source sits directly in `forge/`. Rules that single out core, such as the policy checks on includes and `float`/`double`, recognize it as `forge/core/`.

`scripts/` may use Python and never runs during a plain build ([ADR 0009](adr/0009-tests-may-use-outside-tools.md)). Code generators that run at build time (instruction tables, selection patterns, diagnostic tables) are C++ host executables that live with the library that uses them and follow every rule in [style.md](style.md).

## Libraries

Each library is static. A library's directory appears when its milestone arrives, not before.

| Library    | Holds                                                                                              | Arrives |
| ---------- | -------------------------------------------------------------------------------------------------- | ------- |
| `core`     | Everything in [ADR 0004](adr/0004-core-replaces-the-standard-library.md), plus `forge/version.hpp`  | M1      |
| `driver`   | The options model, mode dispatch, compile orchestration, the list of targets                       | M1      |
| `source`   | The source manager, source locations, and the diagnostics engine                                   | M1      |
| `cfamily`  | The C-family layer ([ADR 0008](adr/0008-split-frontends-over-a-shared-c-family-layer.md))           | M1      |
| `c`        | The C frontend, including C AST → Ingot                                                            | M1      |
| `ingot`    | Ingot, and Ingot → Billet                                                                          | M1      |
| `billet`   | Billet, its passes, and the legalization framework                                                 | M1      |
| `blank`    | Blank, the generic half of Billet → Blank, register allocation, frame layout                       | M1      |
| `stamp`    | Stamp, assembler work (fixups, relaxation, layout), and the text printer                           | M1      |
| `aarch64`  | Everything about one ISA, across layers: legalization hooks, calling conventions, selection patterns, registers, encodings, and its assembly syntax | M1 |
| `object`   | Mach-O, ELF, and COFF readers and writers                                                          | M3      |
| `fas`      | The assembly parser (text → Stamp), shared by fas and inline asm                                   | M3      |
| `fold`     | The linker                                                                                         | M4      |
| `x86_64`   | Like `aarch64`                                                                                     | M2      |
| `riscv`    | Like `aarch64`                                                                                     | M7      |
| `cxx`      | The C++ frontend, including C++ AST → Ingot                                                        | M9      |

A lowering lives with the layer it lowers from. Billet → Blank is the exception: its generic half is in `blank` and its target-specific half is in each ISA library, because otherwise `billet` would depend on every target.

## Dependency rules

| Library                      | Depends on, besides `source` and `core`            |
| ---------------------------- | -------------------------------------------------- |
| `driver`                     | everything                                         |
| `c`, `cxx`                   | `cfamily`, `ingot`                                 |
| `cfamily`                    | `ingot` (to lower the builtin types)               |
| `ingot`                      | `billet`                                           |
| `aarch64`, `x86_64`, `riscv` | `billet`, `blank`, `stamp`, `fas`                  |
| `blank`                      | `billet`                                           |
| `fas`                        | `stamp`                                            |
| `stamp`                      | `object` (from M3)                                 |
| `fold`                       | `object`                                           |
| `billet`, `object`           | nothing else                                       |
| `source`                     | `core` only                                        |

1. `core` depends on nothing. Everything depends on `core`.
2. There are no cycles. Every dependency points toward `core` and down the pipeline.
3. Frontends never depend on each other. `c` and `cxx` depend only on `cfamily`, `source`, and `ingot`.
4. `billet`, `blank`, and `stamp` never name a specific target. Targets plug in through an interface, and only `driver` knows the full list of targets.
5. `fold` depends only on `object`, `source`, and `core`. `fas` depends on `stamp`, `source`, and `core`. Neither depends on Billet, Blank, or a frontend.
6. Every link is `PRIVATE` unless the library's public headers expose the dependency's types.

The build enforces the edges at configure time, from the table in `cmake/library_edges.json`. A CI check reads the generated target graph and rejects any cycle and any edge outside the table, so a raw `target_link_libraries` can't bypass the rule.

## Names

For each library `<name>`, the following match:

| What            | Form              | Example (`fas`)          |
| --------------- | ----------------- | ------------------------ |
| Namespace       | `forge::<name>`   | `forge::fas`             |
| Include path    | `forge/<name>/…`  | `forge/fas/parser.hpp`   |
| CMake target    | `forge_<name>`    | `forge_fas`              |
| CMake alias     | `forge::<name>`   | `forge::fas`             |

`core` is the exception: its namespace is `forge` itself and its headers sit directly under `forge/`, as in `forge/version.hpp`.

## The `forge` binary

One executable, `forge`, built from `driver` and every library it needs. It picks its mode from the name it was invoked under:

| Name        | Mode                                                                  | Arrives |
| ----------- | --------------------------------------------------------------------- | ------- |
| `forge`     | gcc/clang-style driver; picks the language from the file extension    | M1      |
| `forge++`   | The same, but C++ by default and links the C++ runtime                 | M9      |
| `forge-cl`  | cl.exe-style driver                                                   | M6      |
| `fas`       | Assembler, GNU `as` syntax                                            | M3      |
| `ld.fold`   | fold, ELF flavor, GNU ld flags                                        | M4      |
| `ld64.fold` | fold, Mach-O flavor, Apple ld flags                                   | M4      |
| `fold-link` | fold, COFF flavor, link.exe flags                                     | M6      |
| `fld`       | fold in the host's native flavor: Mach-O on macOS, ELF on Linux and MinGW, COFF on MSVC Windows | M4 |

- At M0 `forge` is a `main` that returns 0, built to give the tests something to run. The rest of this section describes what it grows into.
- The mode comes from the basename of `argv[0]`, with any extension stripped.
- A target-triple prefix (`aarch64-linux-gnu-forge`) is reserved for cross-compiling. How it is parsed is decided with the target description.
- `--driver-mode=<mode>` as the first argument overrides the name.
- The aliases are symlinks on Unix and hardlinks on Windows, both in the build tree and in an install. Tests call `fas` and `ld64.fold` by name.
- There are no standalone `fas` or `fold` executables, and no bare `fold` command.
- Future binutils-style tools join the same binary under `forge-` names (`forge-ar`, `forge-nm`) when a milestone needs them.
