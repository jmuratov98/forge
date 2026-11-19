# Testing

How Forge is tested. Why tests may use outside tools is explained in [ADR 0009](adr/0009-tests-may-use-outside-tools.md).

## Workflow

Forge is built test-first:

1. **Write a failing test.** Every behavior change starts with a test that fails.
2. **Make it pass.**
3. **Refactor.**

Put the test at the highest layer that can observe the behavior. That way, reworking the inside of a layer doesn't break its tests.

- **Compiler behavior** gets an end-to-end case, or an IR test once that layer has a text format.
- **Diagnostics** get a verify test: a source file whose `expected-error {{…}}` comments state what Forge must report ([diagnostics.md](diagnostics.md#testing)).
- **googletest** is for core and for self-contained algorithms such as the register allocator or core's hash map.

Running a single test must take well under a second:

- one end-to-end case: `lit path/to/case.c`
- one googletest: its binary with `--gtest_filter`, or from the IDE's test explorer

## Layers

| Layer                           | What it checks                                                                                                     | Arrives          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------- |
| Unit tests                      | googletest, one binary per component library; at M0, one binary that checks the toolchain's flags                  | M0               |
| End-to-end                      | Compile a program, run it, and compare its exit code and stdout with committed expectations                        | M0 runner, M1 corpus |
| Cross-host assembly             | Every CI host compiles the end-to-end corpus for arm64 macOS; CI checks that the assembly is byte-identical across hosts | M1           |
| Diagnostic tests                | Compile a file with the verify consumer, which checks the diagnostics against the `expected-…` comments in it       | M1               |
| IR tests                        | Feed text into one layer and match its output against patterns                                                     | When each layer's text format lands |
| Cross-host objects              | The same check as cross-host assembly, applied to object files ([ADR 0005](adr/0005-byte-identical-output-across-hosts.md)) | M3 (fas)  |
| Differential and fuzzing        | Random programs from Csmith- or YARPGen-style generators, compared live against clang and gcc across `-O` levels   | M5 (optimizer)   |
| Bootstrap                       | Stage-2 and stage-3 builds of Forge compared with `cmp`                                                            | M9               |

Every CI host runs the unit tests. End-to-end binaries run only on hosts that can execute the target. In M1, that's arm64 macOS.

The pattern matcher for IR tests (FileCheck, a port, or one of our own) is chosen when the first IR text format lands.

## Runners

- **lit**: runs all file-based tests (end-to-end, diagnostic, and later IR tests).
- **CTest**: runs googletest, which registers through `gtest_discover_tests` so IDE test explorers list each test.
- **`check`**: a single CMake target that runs both.

## End-to-end cases

An end-to-end case is a single C file with an expectation block at the end. It has no `RUN:` lines: a custom lit test format in Forge's lit config compiles the file with Forge, runs the result, and compares it with the block.

```c
#include <stdio.h>

int main(void) {
    puts("hello");
    return 2 + 3;
}

// EXPECT-EXIT: 5
// EXPECT-STDOUT: hello
```

The expectation block:

- **Exit code.** `EXPECT-EXIT` is required and comes first.
- **Stdout.** Each line of stdout is one `EXPECT-STDOUT:` line. No such lines means stdout must be empty. The comparison is exact, except that `\r\n` counts as `\n`, so a case passes on Windows. A program whose stdout doesn't end in a newline can't be written this way.
- **Restrictions.** lit's `REQUIRES:` and `UNSUPPORTED:` restrict a case to the targets that can run it.

Nobody writes the block by hand. `update-e2e`, a Python script modeled on LLVM's `update_test_checks.py`, compiles each case with clang, runs it, and rewrites the block. You review the diff before committing. The TDD loop for a compiler feature is:

1. Write the program.
2. Run `update-e2e`.
3. Watch the case fail under Forge.
4. Make it pass.

In M1, a case is one translation unit with no stdin and no arguments. Multi-file cases, stdin, and arguments are added when a milestone needs them.

Forge can't compile at M0, so the runner and `update-e2e` are tested with the host's C compiler standing in for Forge: the format takes its compile command as a lit parameter (`--param e2e_compile_command='...'`), and the self-test in `test/e2e-format/` points it at the compiler CMake found. Forge's own corpus is `test/e2e/`, empty until M1.

## Corpora

- **Forge's own corpus** is written for Forge and vendored. It is the only corpus M1 uses.
- **Permissive corpora** may be vendored with their notices kept. Examples:
  - chibicc's tests (MIT)
  - the ISC half of c-testsuite
  - writing-a-c-compiler-tests (MIT)
  - llvm-test-suite's own tests (Apache-2.0 WITH LLVM-exception)
- **Copyleft corpora** are fetched at test time, pinned to a commit, and never vendored. These include the GCC torture tests, c-testsuite's LGPL half, and TCC's tests.
- **Real-world projects** (Lua, SQLite) are fetched and pinned the same way.

## Test dependencies

- **googletest**: CMake `FetchContent`, pinned to a release tag and hash, with a `find_package` fallback for offline builds. It is built with `GTEST_HAS_EXCEPTIONS=0` ([ADR 0003](adr/0003-implementation-language-subset.md)).
- **lit**: installed with `pip` from a pinned requirements file. Tests need Python 3.8 or later.
- **Windows**: lit's shell-style tests need `grep` and `sed`, which come from Git for Windows. The bootstrap comparison at M9 will add `cmp`.
- **Reference compilers**: `update-e2e` needs clang. CI doesn't.

## Benchmarks

Compile time and generated-code speed are measured against the roadmap's speed goals by a separate benchmark harness, not by the tests. Timings are noisy and depend on the host, so they don't belong in a pass/fail suite. Its design is decided in [How are compile speed and generated-code quality benchmarked?](https://github.com/jmuratov98/forge/issues/21).
