---
name: forge-lit-test
description: Write or fix a forge lit test — a compile-time contract of a forge header (forge/test/host), a premake build-system behaviour (forge/test/build), or a ./x command test (utils/xtool/test). Use when adding tests that check compiler errors, #error messages, generated build files or x's output, or when a lit test fails.
---

# forge lit tests

Pick the suite by what is observed:

| Observed                                          | Suite                     | Files   |
| ------------------------------------------------- | ------------------------- | ------- |
| run-time behaviour of a component                 | `forge/unittests/<c>/` (GoogleTest) | `*_test.cpp` |
| what the host compiler says about forge's headers | `forge/test/host/`        | `*.cpp` |
| what premake generates                            | `forge/test/build/`       | `*.lua` |
| what `./x` prints or does                         | `utils/xtool/test/`       | `*.test`, `*_test.py` |

Later suites (forge's own `-verify` diagnostics tests and tool-output tests) will live under
`forge/test/` too; do not invent their format, it is designed already (ask the user).

## Rules for every lit test

- Start with a comment that states the **contract** being tested and why it matters, then the
  RUN lines, then the CHECK lines. See `forge/test/host/assert-format.cpp` and
  `forge/test/build/link-order.lua`.
- Files under `forge/test/` are inputs, not code: **no SPDX line, never clang-formatted** (columns
  in diagnostics depend on layout). `lit.cfg.py`/`lit.local.cfg` are code and keep SPDX.
- RUN lines run in lit's internal shell on every host, Windows included: no `&&` chains that rely
  on bash, no `$(...)`, no shell globbing tricks. Use `not` for expected failures and
  `rm -rf %t` before reusing `%t`.
- `DEFINE: %{compile} = ...` names a repeated command; vary it with `-DCASE=N` and `#if CASE == N`
  blocks rather than writing many files.
- Gate on features, never on guesses: `REQUIRES: asserts`, `UNSUPPORTED: host-cxx-msvc`,
  `%if exceptions %{0%} %else %{1%}`. Available: `debug release reldeb sanitize asserts exceptions
  shared asan ubsan tsan host-std-c++20|c++23 host-cxx-{gcc,clang,msvc} host-{linux,macos,windows}
  host-{x86_64,aarch64}` (xtool suite: `host-*`, `premake`, `ninja`). A new feature belongs in
  `features()` in `premake/forge.lua` or in the suite's `lit.cfg.py`, not in a test.
- FileCheck patterns must match every compiler CI uses (GCC 13+, Clang 17+, AppleClang, MSVC
  19.44+). Check a word all of them print (`basic_format_string`) or a forge `#error` text,
  not one compiler's phrasing. Use `--check-prefix` per case.

## host/ (`%host_cxx_syntax`)

`%host_cxx_syntax` is the consumer's exact compile command (all `FORGE_*` macros, include dirs,
warnings) in syntax-only mode. Override a build macro with `-UFORGE_X -DFORGE_X=0`; `config.hpp`
rejects a missing macro. `%host_werror` is `-Werror` or `/WX`.

## build/ (`%premake`)

`%premake --file=%s --to=%t [--cc=clang --os=linux] ninja` runs the real `premake/forge.lua`
against a fixture: `dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))`, then
`fixture.workspace({ components with sources })` and `forge.emit({...}, third_party)`. Check
generated files with `FileCheck %s --input-file=%t/<project>.ninja`; pin `--cc` and `--os` so the
output is the same on every host. For errors, `not %premake ... 2>&1 | FileCheck %s`.

## utils/xtool/test/

`%x` runs `x.py` with the venv's Python; prefer `%x -n ...` (dry run) so the test builds nothing.
`REQUIRES: premake, ninja` when x must call them. Pure functions get `*_test.py` (unittest).

## Running

```sh
./x test forge/test/host/<file>.cpp        # one test, Debug
./x test -c all forge/test/host            # every configuration (features differ per config)
./x test forge/test/build -- -a            # lit -a: show every command and its output
```

A test that only fails on one compiler: reproduce with `./x test --cxx <compiler> <path>`
(e.g. `--cxx g++-13`), which uses its own build directory.
