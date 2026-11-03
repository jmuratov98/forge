# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

forge is a C/C++ compiler toolchain written in C++20. It will compile C89–C23, C++98–C++26 and its
own "forge" language. Today only the `core` component exists (`config.hpp`, assertions, stack
traces, crash context, version); designs live as specs under `docs/`.

## Commands

Everything goes through `./x` (Python 3.10+, stdlib core in `utils/xtool/`). `./x --help` and
`./x <command> --help` are authoritative.

```sh
./x setup                      # pinned premake5, ninja, venv (lit, clang-format, clang-tidy), googletest
./x doctor                     # what is installed, which compilers config.hpp accepts, build dirs
./x build [-c Debug,Release|all] [--shared --std=c++23 --exceptions --lto --assertions --werror ...]
./x test                       # builds, then lit over forge/test, forge/unittests and utils/xtool/test
./x test forge/test/host/assert-format.cpp     # one lit test (any source path or directory)
./x test forge/unittests/core                  # one unit-test binary
GTEST_FILTER='assertions.*' ./x test forge/unittests/core   # GoogleTest cases
./x test utils/xtool/test      # x's own tests; no forge build needed
./x test --filter REGEX        # lit name filter;  `./x test -- -a` passes args to lit
./x format [--check] [PATH]    # clang-format over forge/ (never forge/test/)
./x lint [--only|--skip files,layering,workflows,headers,clang-tidy] [--fix] [PATH]
./x check                      # format --check, lint, build, test: the pre-push gate
./x -n build ...               # dry run: print the premake/ninja commands only
./x run <tool> ...             # run a pinned tool (premake5, lit, clang-tidy, FileCheck, ...)
```

- FileCheck is never downloaded: put it on PATH or set `FORGE_FILECHECK` (Homebrew `llvm` works).
- Each set of build options gets its own directory: `build/` for defaults, otherwise
  `build-<compiler>-<options>` (e.g. `build-shared-std-c++23`). `--werror` is part of the name, so
  it is a separate build. Outputs land in `<build-dir>/<Config>/bin`.
- Warnings are fatal only with `--werror`, which CI always passes; use it before calling code clean.
- `./x configure` writes `compile_commands.json` at the root for clangd.
- Exit codes: 1 failure, 2 usage error, 3 something `./x setup` provides is missing.

## Architecture

### Build: premake DSL, described as data

- `premake5.lua` → `premake/options.lua` (options) + `premake/forge.lua` (DSL).
- `forge/premake5.lua` only *returns data*: a list of `forge.component { "name", dependencies = {...} }`
  and `forge.test { ... }`. `forge.emit` in `premake/forge.lua` alone decides the project shape:
  one static library per component (link order = reverse post-order of the dependency closure,
  computed there because premake does not propagate static links), or with `--shared` a single
  `libforge` with hidden visibility and `FORGE_API` exports. Cycle checks run in both modes.
- A component is `forge/include/forge/<name>/*.hpp` + `forge/source/forge/<name>/*.{hpp,cpp}`; a
  test is `forge/unittests/<name>/`, built as `forge_<name>_unittests`. A component without `.cpp`
  files gets kind `None` and is never linked.
- `forge.baseline()` is what every linked object must agree on (standard, no RTTI, exceptions,
  sanitizers, LTO, config macros) plus unwind tables, which stack traces need in every frame;
  third_party (googletest) applies it but never forge's warnings.
- Configurations: Debug, Release, RelDeb (= Release + debug info, not -O2 like CMake), Sanitize
  (assertions on, ASan+UBSan by default). Assertions also turn on libstdc++/libc++ hardening.
- `premake5 forge-describe` prints the configurations, the `Forge`-category options and the
  component graph as JSON. `./x` builds its CLI and the layering lint from it, so **a new build
  option is added only in `premake/options.lua`**; never mirror options in Python.
- After the action runs, premake writes `<build>/<Config>/{test,unittests}/lit.site.cfg.py`
  carrying that configuration's lit features and the exact host compile command.

### Tests: lit everywhere

- `forge/test/` (lit, `lit.cfg.py`): `build/*.lua` are premake scripts run via `%premake` against
  `Inputs/fixture.lua`, checking generated ninja files; `host/*.cpp` compile forge headers with the
  consumer's exact flags via `%host_cxx_syntax`, checking compile-time contracts and `#error`s.
- `forge/unittests/` – GoogleTest binaries, run by lit's GoogleTest format (sharded).
- `utils/xtool/test/` – `*_test.py` (unittest) and `*.test` (lit + FileCheck over `./x -n`).
- `utils/xtool/lit_runner.py` passes lit a config map (as llvm-lit does), which is why
  `./x test <source path>` works.
- Features come from premake, not guesses: `debug`/`release`/`reldeb`/`sanitize`, `asserts`,
  `exceptions`, `shared`, `asan`/`ubsan`/`tsan`, `host-std-c++20`, `host-cxx-{gcc,clang,msvc}`,
  `host-{linux,macos,windows}`, `host-{x86_64,aarch64}`.
- Files under `forge/test/` (except `lit.cfg.py`/`lit.local.cfg`) are test inputs: no SPDX line,
  never clang-formatted (`forge/test/.clang-format` disables it), because columns matter.

### Lint stages (`utils/xtool/cmd_lint.py`, rules in `lints.py`)

`files` (SPDX, `#pragma once`, whitespace) → `layering` (includes must follow the component graph)
→ `workflows` (pinned actionlint + zizmor) → `headers` (each header compiles alone, twice) →
`clang-tidy` (pinned, `WarningsAsErrors: '*'`, cached by content).

### CI

`.github/workflows/ci.yml` reads rows from `.github/ci/matrix.json`. Draft PRs and pushes run the
`pr` tier, ready PRs and nightly the `full` tier; the required check is `ci-ok`. Format and the
compiler-free lints run once; `headers,clang-tidy` run per compiler; then `./x build` and
`./x test --no-build` per row. FileCheck in CI is built from pinned llvm-project
(`.github/ci/build-filecheck.sh`). Compiler floor: GCC 13, Clang 17, AppleClang 16, MSVC 19.44.

## Conventions not obvious from tooling

- snake_case for everything (types included); only template parameters are CamelCase. Members
  `m_`, static members `s_`, globals `g_`; public struct fields are unprefixed. Macros `FORGE_*`.
- Every `FORGE_` config macro is always defined to 0 or 1 and tested with `#if`, never `#ifdef`
  (`-Wundef` catches mistakes). premake passes all build macros; `config.hpp` `#error`s if one is
  missing, so a standalone compile must `-D` them all (see `main.cpp`). `config.hpp` stays pure
  preprocessor. Compiler-provided macros use `#ifdef`; `#elif defined(X)` lines carry
  `// NOLINT(readability-use-concise-preprocessor-directives)`.
- `FORGE_ASSERT` is for bugs in forge only; problems in the program being compiled are diagnostics.
  With assertions off the condition is neither evaluated nor assumed, but checks still fire during
  constant evaluation. Messages are `std::format` literals checked at compile time.
- New source files start with `// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception`
  (`./x lint --fix` adds it). Include order is enforced by clang-format: local, `forge/`,
  third-party, C++ std, C system.
- Comments explain *why*, including why forge departs from LLVM/GCC. Do not copy LLVM/GCC
  practice blindly: when a design follows or departs from it, say which and why.

## Design specs

Ask the user (don't default) on code style, naming, lint gates and CI shape; those are their calls.

## Project skills and agents

- `/forge-spec`: write or check a `docs/` spec (`scripts/check_spec.py` checks numbering, stable
  names, notes, element order, cross-references).
- `/forge-component`: add a component (`scripts/new_component.py` scaffolds it and updates
  `forge/premake5.lua`).
- `/forge-lit-test`: which suite a test belongs in, and the lit conventions for each.
- `forge-reviewer` agent: read-only review for spec conformance and forge conventions.
