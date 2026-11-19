# Building and testing

How to build Forge, run its tests, and add to them. Why the build is shaped this way: [ADR 0001](adr/0001-branching-and-versioning.md) (versions), [ADR 0003](adr/0003-implementation-language-subset.md) (the C++ subset), [ADR 0006](adr/0006-failures-and-assertions.md) (configurations), and [testing.md](testing.md) (the test strategy).

## What you need

| Tool    | Version | For                                                                     |
| ------- | ------- | ----------------------------------------------------------------------- |
| CMake   | 3.24+   | The build                                                               |
| Ninja   | any     | The only supported generator                                            |
| C++ compiler | see below | gcc, clang, AppleClang, or MSVC; MinGW-w64 gcc works too           |
| C compiler | the same toolchain's | The end-to-end runner's self-test compiles C with it        |
| Python  | 3.8+    | The tests only. Building Forge without them needs no Python             |
| lit     | pinned in `test/requirements.txt` | The tests only                                |
| clang-tidy | 18+  | Optional: the naming check (`.clang-tidy`)                              |

Building without tests (`-DFORGE_BUILD_TESTS=OFF`) needs neither Python nor the network. With them, the first configure downloads googletest, pinned to a release and a hash; `-DFORGE_SYSTEM_GOOGLETEST=ON` uses an installed one instead.

**Compiler minimums.** Configure rejects anything older. Each is the oldest version that implements every language feature and header on [ADR 0004](adr/0004-core-replaces-the-standard-library.md)'s allowlist (concepts, `consteval`, `constinit`, `<source_location>`, `<bit>`, `<compare>`):

| Compiler   | Minimum                    | CI builds                                                     |
| ---------- | -------------------------- | ------------------------------------------------------------- |
| gcc        | 11                         | 11 and 14, on Linux                                           |
| clang      | 16                         | 16 and 18, on Linux                                           |
| AppleClang | 15                         | the macOS runner's Xcode, which is not pinned to the minimum  |
| MSVC       | 19.30 (Visual Studio 2022) | the Windows runner's Visual Studio 2022, likewise             |

Where CI builds the minimum itself, it is tested. Where it doesn't, the minimum is a claim from the compilers' conformance tables, and the first failure on an older compiler is the evidence to adjust it. MinGW uses gcc's minimum and CI builds the MSYS2 release.

**Windows.** MSVC builds need a Visual Studio developer environment (`vcvars64.bat`, or the "x64 Native Tools" prompt) so Ninja finds `cl`. lit's shell-style tests need `grep` and `sed`: install Git for Windows and put `C:\Program Files\Git\usr\bin` on `PATH` after the MSVC directories, because its `link.exe` would otherwise shadow MSVC's.

## Build and test

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r test/requirements.txt

cmake --preset debug
cmake --build --preset debug
cmake --build --preset debug --target check
```

`check` runs both harnesses: CTest for googletest and lit for everything file-based. `check-unit` and `check-lit` run one each. The presets are `debug`, `relwithdebinfo`, `relwithdebinfo-assertions`, `release`, and `ci-` versions of three of them that also treat warnings as errors. A preset's build tree is `build/<preset>`. Pass `-DCMAKE_CXX_COMPILER=...` (and `-DCMAKE_C_COMPILER=...`) to pick a compiler.

One test runs in well under a second:

```sh
lit build/debug/test/cmake/version.test      # one lit test
lit build/debug/test/policy                  # a directory of them
build/debug/bin/toolchain_contract_tests --gtest_filter='toolchain_contract.rtti*'
```

`scripts/ci_build.py --preset ci-debug` runs what a CI job runs: configure, build, `check`.

## Configurations

| Configuration    | Assertions                                                   |
| ---------------- | ------------------------------------------------------------ |
| `Debug`          | always on                                                    |
| `RelWithDebInfo` | off; on with `-DFORGE_ENABLE_ASSERTIONS=ON`                  |
| `Release`        | compiled out; `-DFORGE_ENABLE_ASSERTIONS=ON` is a configure error |

`MinSizeRel` and multi-configuration generators are configure errors. With no `CMAKE_BUILD_TYPE`, configure picks `Debug`. The build resolves whether assertions are on and prints it (`Forge build type: Debug; assertions: ON`); the compile definition that carries it into C++ arrives with `FORGE_ASSERT`.

Every target is compiled as C++20 with extensions off, without RTTI and without exceptions (`/GR- /EHs-c-` and `_HAS_EXCEPTIONS=0` on MSVC). googletest is built the same way, with `GTEST_HAS_EXCEPTIONS=0`. Forge's own targets get strict warnings; `-DFORGE_WARNINGS_AS_ERRORS=ON` makes them errors, as CI does.

## The version

[ADR 0001](adr/0001-branching-and-versioning.md) defines it; configure composes it and prints it (`Forge version: 0.1.0-alpha+dev.local`) and writes `generated/version.inc.hpp` into the build tree. `X.Y.Z` comes from `project(forge VERSION ...)` in the top `CMakeLists.txt`, and the stage (`alpha`, `beta`, `rc`, with an optional `.N`) from `FORGE_VERSION_STAGE` beside it.

- A local build is `+dev.local`: no timestamp or commit, so reconfiguring rebuilds nothing.
- CI passes `-DFORGE_BUILD_TIMESTAMP=YYYYMMDDHHMMSS` (UTC) and `-DFORGE_BUILD_SHA=<first 7 hex characters>` together, giving `+dev.{timestamp}.g{sha}`. One run uses one timestamp and commit on every host.
- Configure never runs git.

`scripts/check_dev_version.py` checks a version against SemVer 2.0.0 and the dev form.

## Adding a library

A library's directory appears when its milestone arrives ([layout.md](layout.md)). Each library `<name>` lives in `forge/<name>/`:

```
forge/<name>/CMakeLists.txt
forge/<name>/include/forge/<name>/...   public headers (core's are in include/forge/)
forge/<name>/src/...                    sources and private headers
forge/<name>/test/...                   its googletest sources
```

Declare it in its `CMakeLists.txt`, add `add_subdirectory(<name>)` to `forge/CMakeLists.txt`, and add a googletest binary in `test/`'s style:

```cmake
forge_add_library(c
  SOURCES src/parser.cpp
  PRIVATE_DEPENDS core source cfamily ingot)
```

`forge_add_library` creates the target `forge_c` and the alias `forge::c`, puts `include/` on the include path of every library that links it, and keeps `src/` private. Dependencies are `PRIVATE` unless listed under `PUBLIC_DEPENDS`, which is for libraries whose types appear in the new library's public headers. An edge that [layout.md](layout.md) does not allow is a configure error. The allowed edges are in `cmake/library_edges.json`; keep the table in `layout.md` in step with it.

## Adding an end-to-end case

A case is one `.c` file under `test/e2e/` that ends with its expectation, as described in [testing.md](testing.md). Nobody writes the block by hand:

```sh
scripts/update-e2e test/e2e/hello.c     # compiles with clang, runs it, rewrites the block
git diff test/e2e/hello.c               # review it
lit build/debug/test/e2e/hello.c        # watch it fail, or pass, under Forge
```

On Windows, run it as `python scripts/update-e2e`. It needs clang by default; `--compile-command 'gcc -o {out} {src}'` uses another reference compiler. Until Forge compiles C, the runner is tested with the host's C compiler standing in for Forge (`test/e2e-format/`).

## Policy checks

These enforce rules from the ADRs and run in `check`, on every host, over Forge's own source:

| Script                         | Rule                                                                        |
| ------------------------------ | --------------------------------------------------------------------------- |
| `scripts/check_includes.py`    | Only [ADR 0004](adr/0004-core-replaces-the-standard-library.md)'s allowlisted standard headers; C library and OS headers only in core; tests exempt |
| `scripts/check_floating_point.py` | No `float` or `double` outside core ([ADR 0005](adr/0005-byte-identical-output-across-hosts.md)) |
| `scripts/check_file_names.py`  | `snake_case` file names ([style.md](style.md))                              |

Each prints `file:line` and the rule, and exits 1. Their tests run them over fixture trees of known violations in `test/policy/`.

The `policy` CI job adds `scripts/check_target_graph.py` (no dependency cycle and no edge outside `cmake/library_edges.json`, even through a raw `target_link_libraries`) and clang-tidy's naming rules (`.clang-tidy`, which encodes the naming table in [style.md](style.md)) over the tree and over the fixtures in `test/tidy/`. Run it with `scripts/ci_policy.py --clang-tidy <clang-tidy>`; on macOS add `--extra-arg=-isysroot$(xcrun --show-sdk-path)`.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request to `main` and every push to `main` and `release/*`. Each host builds and runs `check` in `Debug` and `Release`, and `linux-clang-18` also in `RelWithDebInfo` with assertions. Every job in a run uses one timestamp and commit for the version.

Branch protection on `main` should require these checks, which are named by the workflow:

- `build-test (linux-gcc-11)`
- `build-test (linux-gcc-14)`
- `build-test (linux-clang-16)`
- `build-test (linux-clang-18)`
- `build-test (macos-appleclang)`
- `build-test (windows-msvc)`
- `build-test (windows-mingw)`
- `policy`
