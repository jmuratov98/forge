# C test suites usable for the slice

Research for [#5](https://github.com/jmuratov98/forge/issues/5), feeding the "Test strategy" decision ([#10](https://github.com/jmuratov98/forge/issues/10)).
Gathered 2026-11-21 from each suite's own repository, README and license files. Revisions read are pinned in [Sources](#sources).

## Answer in one table

| Suite | Size | C level | Pass/fail oracle | Needs libc / preprocessor | lit fit | License | Vendor? |
|---|---|---|---|---|---|---|---|
| **Writing a C Compiler tests** (Sandler) | 1,630 `.c` in 20 chapters (valid + invalid) | Grows by chapter: `int`-only up to ch. 10, then `long`, `unsigned`, `double`, pointers, arrays, `char`/strings, `void`/`sizeof`, structs | `expected_results.json`: exit code (845 tests) or exit code + stdout (22); invalid tests must be rejected | No `#include` before ch. 13; libc calls first in ch. 9 (3 files) | Very good: one `.c` gives one result from a JSON table | MIT | **Yes** |
| **c-testsuite** (`single-exec`) | 220 tests | Tagged `c89` 174, `c99` 43, `c11` 2 | Exit 0 **and** stdout+stderr equal to `$t.c.expected` (154 expected files are empty) | Tags: `needs-libc` 63, `needs-cpp` 96; 121 need neither | Very good: `.c` + `.expected` + `.tags` | Runners MIT; tests carry their origin's license (150 from scc, ISC; 69 from TinyCC, LGPL-2.1) | scc-origin tests: yes. TinyCC-origin: better fetched |
| **chibicc `test/`** | 41 files, 1,396 `ASSERT`s | Most of C11 plus GNU extensions | Self-checking: `ASSERT(expected, expr)` calls `assert()` in `test/common`, which `exit(1)`s on mismatch | Yes: `#include "test.h"`, `printf`; `test/common` built by the host `cc` | Fair: file granularity is coarse (one file = hundreds of checks) | MIT | Yes, but needs rewriting for a small subset |
| **GCC `gcc.c-torture`** | `execute/` 1,701 top-level `.c` (+147 `builtins/`, 80 `ieee/`); `compile/` 2,017 | Pre-ANSI to modern GCC C, K&R definitions common, many GNU extensions | Self-checking: `abort()` on failure, `exit(0)` on success. `compile/` tests only have to compile | Most declare `abort`/`exit` themselves; 202 of 1,701 `#include`; 335 carry DejaGnu `dg-*` directives | Fair: needs a `dg-*` directive filter and skip lists | GPL-3.0-or-later (part of GCC) | **No, fetch** |
| **LLVM test-suite `SingleSource`** | 93 top-level `.c` in `UnitTests/`, 36 in `Regression/C/` (plus subdirectories), plus a copy of GCC torture `execute/` | Mixed C, C++, ObjC; many C tests use GNU or Apple extensions | `.reference_output` = stdout followed by `exit N` | Mostly yes (`printf`) | Good in principle, but its own lit format (`litsupport`) is built by CMake; easier to pick files out | Apache-2.0 WITH LLVM-exception, except listed third-party directories (the torture copy stays GPL) | Apache parts: yes, per file |
| **Csmith** | Generator | C99 with `stdint` types, structs, unions, bitfields, pointers, volatiles (each can be turned off) | Differential: prints a checksum; compare against `clang` | Always: `#include "csmith.h"`; a `CSMITH_MINIMAL` runtime avoids system headers but still needs `printf` or `putchar` | Good as a fuzz loop, not as a fixed lit suite | BSD-2-Clause | Install the tool; check in only reduced repro tests |
| **YARPGen** | Generator | `--std=c`: scalar expressions, arrays, loops (loop mode on `main`; scalar mode on branch `v1`) | Prints a hash; `--check-algo=asserts` adds a self-check | Always `#include <stdio.h>`, `printf`; output is 3 files (`init.h`, `func.c`, `driver.c`) | As Csmith | Apache-2.0 | As Csmith |

**For the slice:** Writing a C Compiler's chapters 1 to 9 (and 10) are the closest match to a first `int`-only subset. They are MIT, return-code-only, need no headers, and are already ordered by feature. c-testsuite's 121 tests with neither `needs-libc` nor `needs-cpp` are the next layer. GCC torture and Csmith/YARPGen only start to pay off once the subset has `printf`-level libc calls, a preprocessor (or `clang -E` before Forge) and wider types.

## Facts every suite shares for Forge

- **Forge only emits `.o` (`forge -c foo.c -o foo.o`).** Every suite expects a driver that can produce an executable, so each lit `RUN:` line must link with the host toolchain (`cc foo.o -o foo`) and then run the program. That works only on macOS arm64, as the map already says. (Writing a C Compiler's runner already does this for its library tests: it builds the file under test with `-c` and links with `gcc`. Source: `test_framework/basic.py`, `library_test_helper`.)
- **Calling `printf` needs Apple's variadic convention.** On Apple arm64, *every variadic argument is assigned to 8-byte stack slots*, not registers, and `va_list` is `char *`. ([Apple, "Writing ARM64 code for Apple platforms"](https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms).) Any test that prints is therefore blocked until Forge can make variadic calls. Tests that only check the exit code (Writing a C Compiler chapters 1 to 8, c-testsuite's empty-`.expected` tests that don't need libc, GCC torture's `abort`/`exit` style) avoid this.
- **None of these suites uses lit or FileCheck.** All of them check runtime behaviour. FileCheck tests of Forge's IR and assembly have to be written in-house. cproc's `test/*.qbe` golden files (ISC) are the closest model of that style, but they are specific to QBE.

## Per suite

### Writing a C Compiler tests (Nora Sandler)

- **Repo:** <https://github.com/nlsandler/writing-a-c-compiler-tests>. License **MIT** ("Copyright (c) 2023 Nora Sandler", `LICENSE`). It is the test suite for the book *Writing a C Compiler* (No Starch, July 2024), which targets x64.
- **Coverage by chapter** (titles from the [No Starch table of contents](https://nostarch.com/writing-c-compiler)): 1 A Minimal Compiler; 2 Unary Operators; 3 Binary Operators; 4 Logical and Relational Operators; 5 Local Variables; 6 If Statements and Conditional Expressions; 7 Compound Statements; 8 Loops; 9 Functions; 10 File-scope Variables and Storage-class Specifiers; 11 Long Integers; 12 Unsigned Integers; 13 Floating-Point Numbers; 14 Pointers; 15 Arrays and Pointer Arithmetic; 16 Characters and Strings; 17 Supporting Dynamic Memory Allocation; 18 Structures; 19 Optimizing TACKY Programs; 20 Register Allocation.
- **Counts (`.c` files per chapter, valid + invalid):** ch1 24, ch2 19, ch3 35, ch4 43, ch5 82, ch6 68, ch7 27, ch8 98, ch9 78, ch10 72, ... ch18 308; 1,630 in total. Valid programs in chapters 1 to 10: 7, 12, 26, 37, 45, 43, 16, 54, 36, 38.
- **Structure:** `tests/chapter_N/{valid,invalid_lex,invalid_parse,invalid_semantics,invalid_types,invalid_declarations,invalid_labels,...}/`. Per the README: an invalid test passes if the compiler "terminates with a non-zero exit code and does not produce any output files". A valid test passes if the executable "produces the expected output and terminates with the expected exit code". Expectations are in `expected_results.json` (867 entries: 845 `return_code` only, 22 `return_code` + `stdout`).
- **Optional features** are flagged in `test_properties.json` → `extra_credit_tests` (for example `bitwise`, `compound`, matching runner flags `--bitwise`, `--compound`, ...). `libs` and `assembly_libs` name helper files for multi-file tests. `requires_mathlib` lists tests that need `-lm`.
- **Headers and libc:** no `#include` before chapter 13 (2 files there; most are in ch. 18 and 20). Calls to `printf`/`putchar`/`puts`/`malloc` first appear in ch. 9 (3 files) and ch. 10 (2).
- **Catches:**
  - The bundled Python runner (`test_compiler`) **refuses to run on arm64**. It requires x86_64 and tells macOS-ARM users to use Rosetta (`test_framework/runner.py`, around line 305). It also expects a gcc-like driver (`mycc file.c` → executable, plus `--lex/--parse/--codegen` stage flags). Forge should drive the `.c` files and `expected_results.json` from its own lit config rather than use the runner.
  - `assembly_libs` are x86-64 `.s` files (`*_linux.s` / `*_osx.s`) used by a handful of stack-alignment and page-boundary tests (ch. 9, 10, 16, 18, 20). Skip those on aarch64.
  - Chapter 19 and 20 tests check the *assembly* for x86 instructions (for example, constant-folded `target_*` functions may contain only `mov`/`jmp`/`xor`; see `tests/chapter_19/constant_folding/README.md`). Those checks don't carry over to aarch64, but the programs still run with checked exit codes.
- **lit fit:** very good. Write a lit format, or a generator, that reads `expected_results.json`, runs `forge -c`, links with `cc`, runs the program and compares the exit code and stdout. For `invalid_*` tests, check that Forge exits non-zero and writes no `.o`.

### c-testsuite

- **Repo:** <https://github.com/c-testsuite/c-testsuite> (last push 2020-09-30; the GitHub API reports the license as `NOASSERTION`). The top-level `LICENSE` is MIT (Andrew Chambers) "for all testing software, but not for individual test cases". `tests/LICENSE`: "The licenses of individual test cases can be discovered by a test cases .otag file."
- **Origins** (tallied from the 220 `.otags` files): 150 from **scc** (`git://git.simple-cc.org/scc`, `tests/scc/execute/`); scc's `LICENSE` is the **ISC License**. 69 from **TinyCC** (`git://repo.or.cz/tinycc.git`); TinyCC is **LGPL-2.1** (`COPYING`). Its `RELICENSING` file records most authors agreeing to MIT terms, but not all of them (some answer "NO" or "?"), so treat it as LGPL.
- **Structure** (README): `tests/single-exec/NNNNN.c`, with `main` as the entry point. `$t.c.expected` "must match stdout+stderr of the test", and "the test programs exit with 0 on success". A runner script is called as `./runners/single-exec/$NAME tests/single-exec/case.c` and "must return nonzero on failure". `runners/single-exec/posix` shows the whole protocol: `$CC $CFLAGS t.c -o t.bin && t.bin > t.output 2>&1 && diff -u t.expected t.output`. Output is TAP.
- **Tags** (`$t.c.tags`): `portable` 218, `c89` 174, `c99` 43, `c11` 2 (c89 implies c99 implies c11), `needs-cpp` 96, `needs-libc` 63. **121** tests need neither cpp nor libc, and 154 have an empty `.expected`. Example `00001.c` is `int main() { return 0; }`; `00150.c` uses designated initializers and compound literals.
- **Catches:** the runners are all x86_64-specific (`gcc-x86_64` checks `uname -m`). The README admits that test names are "not stable", and the project looks dormant. Tag queries need TMSU, but filtering the `.tags` files with lit `REQUIRES`/`UNSUPPORTED` or a small script avoids that.
- **lit fit:** very good. Each test is one file with an exact-match expected output, and the tags map onto lit features.

### chibicc (and other small compilers)

- **Repo:** <https://github.com/rui314/chibicc>, **MIT** (Rui Ueyama, 2019). The README says it "supports almost all mandatory features and most optional features of C11 as well as a few GCC language extensions". It does not support complex numbers, K&R prototypes or GCC inline asm (though `test/asm.c` uses basic `asm("...")` with x86 instructions).
- **Structure:** 41 `test/*.c` files with 1,396 `ASSERT(expected, expr)` calls. `test/test.h` defines `ASSERT(x, y)` as `assert(x, y, #y)`. `test/common`, compiled by the *host* `cc`, implements `assert` (print, then `exit(1)` on mismatch) along with some extern helpers. The Makefile does `./chibicc -c -o test/X.o test/X.c` and then `$(CC) -o test/X.exe test/X.o -xc test/common`. That `-c` + host-link shape is exactly Forge's. `test/driver.sh` tests driver flags.
- **Catches:** 27 of 41 files use GNU statement expressions `({ ... })`, in 529 `ASSERT`s. `test.h` declares `printf`/`sprintf` (variadic). `float.c` and `long double` tests assume x87. So most of the final suite is out of reach of an early subset without rewriting.
- **Incremental history:** "Each commit of this project corresponds to a section of the book" (README, 316 commits). The first commit's `test.sh` is `assert 0 0; assert 42 42`: compile, assemble with `gcc -static`, run, compare `$?`. Later commits add one feature at a time (for example `assert 21 '{ return 5+20-4; }'` at the `while` commit). Those shell-level exit-code asserts are a good model for slice smoke tests, and MIT lets Forge copy them.
- **Others checked:** 8cc (MIT), lacc (MIT), Sandler's older `write_a_c_compiler` stages (MIT). TinyCC `tests/tests2/NN_name.c` + `.expect` (LGPL-2.1; already partly in c-testsuite). cproc `test/*.c` + `*.qbe` golden IR plus `runtests` (ISC; checks the frontend's IR text, not behaviour).

### GCC C torture suite

- **Location:** `gcc/testsuite/gcc.c-torture/{compile,execute,unsorted}` in GCC (read from the `gcc-mirror/gcc` GitHub mirror). The driver `execute/execute.exp` is "Copyright (C) 1991-2026 Free Software Foundation" under **GNU GPL v3 or later**. Individual tests mostly have no header (34 of 1,701 top-level `execute/*.c` carry a copyright or GPL notice), so they fall under GCC's GPL-3.0-or-later.
- **Counts:** `execute/` has 1,701 top-level `.c` files, 26 `.x` Tcl side files, `builtins/` 147 entries and `ieee/` 80 entries. `compile/` has 2,017 `.c`.
- **Structure:** `execute.exp` runs every `*.[cS]` with `dg-do-what-default "run"` and options `-w`, under the torture optimization matrix. Tests are self-checking: 1,559 of 1,701 call `abort()`, and success is `exit(0)` or returning from `main`. Example `20000112-1.c` declares `void abort(void); void exit(int);` itself and uses a K&R definition. 335 files carry DejaGnu directives (`dg-additional-options` 141, `dg-require-effective-target` 139, `dg-options` 43, `dg-skip-if` 39, ...). `compile/` tests pass if they compile.
- **Catches:** lots of GNU extensions and K&R C. The LLVM test-suite's copy keeps a "Big list of naughty tests" of GCC extensions Clang doesn't support, a clang-bug list, an `-fwrapv` list, a `-lm` list, an x86-only list, an **AArch64** skip list and a **Darwin** skip list (`SingleSource/Regression/C/gcc-c-torture/execute/CMakeLists.txt`). Forge can reuse those lists as a starting filter.
- **lit fit:** fair. The pass condition is simple (exit 0), but Forge needs a directive filter and skip lists. With GPL-3.0, **fetch at test time (pinned revision) rather than vendor**, at least until Forge has picked its own license.

### LLVM test-suite `SingleSource`

- **Repo:** <https://github.com/llvm/llvm-test-suite>. `LICENSE.TXT`: Apache-2.0 with LLVM Exceptions, plus a table of third-party directories with "additional or alternate copyrights, licenses, and/or restrictions". `SingleSource/Benchmarks/Misc`, `CustomChecked`, `Gizmos`, `Benchmarks/SmallPT`, `Benchmarks/Dhrystone` and `SingleSource/Regression/C/gcc-c-torture/execute` are listed there.
- **Layout:** `SingleSource/{Benchmarks,Regression,UnitTests}`. `UnitTests/` mixes C, C++, ObjC and blocks, with subdirectories `AArch64`, `X86`, `Float`, `Vector`, `SetjmpLongjmp`, `Threads`, ... `Regression/C/` holds C regressions plus `gcc-c-torture/`, a copy of GCC torture `execute/` "Last checked at SVN version 275024" (its `README`).
- **Structure:** each `X.c` has `X.reference_output`, which is stdout followed by a final `exit N` line (for example `2002-05-02-CastTest.reference_output` ends in `exit 0`). Some tests have `.big-endian` / `.AIX` variants. `SingleSource/lit.local.cfg` sets `traditional_output = True`. The top-level `lit.cfg` uses the custom `litsupport.test.TestSuiteTest()` format over CMake-generated `.test` files, and `Regression/C/CMakeLists.txt` adds `-lm`, `-Wno-implicit-int`, ...
- **Catches:** nearly every test prints with `printf`, so it needs variadic calls. Test names are dates and bug IDs, not features. The CMake + `litsupport` harness is heavy and assumes a full compiler driver.
- **lit fit:** cherry-pick. A small Forge lit format can compare `stdout + "exit N"` against `.reference_output`. Apache-licensed files can be vendored one by one with attribution; the torture copy keeps GPL.

### Csmith

- **Repo:** <https://github.com/csmith-project/csmith>. `COPYING`: BSD 2-clause ("often called the 'BSD License'"), University of Utah.
- **What it does** (README): random C programs "free of undefined behaviors", meant for "differential testing as the test oracle". Generate with `csmith > random1.c`, compile with `-I$CSMITH/include`, run, and compare output across compilers. The README notes that "programs might contain infinite loops", so use a timeout.
- **Controls:** a `--no-X` flag for most features (from `src/RandomProgramGenerator.cpp`): `--no-pointers`, `--no-structs`, `--no-unions`, `--no-bitfields`, `--no-arrays`, `--no-volatiles`, `--no-longlong`, `--no-math64`, `--no-float` (float is off by default), `--no-packed-struct`, `--no-jumps`, `--no-divs`, `--no-muls`, `--no-comma-operators`, `--no-builtins`, `--no-safe-math`, `--max-funcs`, `--max-block-depth`, ... It can therefore produce `int`-ish programs.
- **Catches:** output always `#include "csmith.h"`. The default runtime pulls in `<float.h> <math.h> <string.h>` and `printf`s the checksum. `-DCSMITH_MINIMAL` swaps in `csmith_minimal.h`, which declares `printf` itself (or `putchar` with `NO_PRINTF`) and uses `custom_stdint_x86.h` instead of system headers. Forge still needs a preprocessor, or can run `clang -E` first, plus `uint64_t` arithmetic and the safe-math helper functions.
- **Use:** a fuzz or differential job (Forge vs `clang`, both at `-O0`), not a checked-in suite. Reduced failures become regular lit tests.

### YARPGen

- **Repo:** <https://github.com/intel/yarpgen>, **Apache-2.0** (`LICENSE.txt`, Intel + University of Utah).
- **What it does** (README): programs that are "statically and dynamically correct" (no UB, implementation-defined behaviour allowed). Each program "consists of several files", and after it is compiled and run it "produces a decimal number, which is hash of all program global variable values". The main branch targets loop optimizations (PLDI 2023); the scalar-optimization version is on branch `v1` (OOPSLA 2020).
- **Options** (`src/options.cpp`): `--std` ∈ {`c`, `c++` (default), `ispc`, `sycl`}; `--check-algo` ∈ {`hash` (default), `asserts`}. With `asserts`, the driver prints `ERROR: value mismatch`, so programs check themselves without a second compiler. Output files are `init.h`, `func.c`, `driver.c` (`src/program.cpp`); the driver `#include <stdio.h>` and `printf("%llu\n", seed)`.
- **Use:** same as Csmith, but later. It needs multi-file compilation, `unsigned long long`, arrays and loops, and it is tuned to stress optimizers, which the slice doesn't have.

## Suggested layering (input for #10, not a decision)

1. **Slice smoke tests:** hand-written lit tests in chibicc's early `assert N 'prog'` style, plus Forge's own FileCheck IR/asm tests (no external suite supplies those).
2. **Feature conformance:** vendor Writing a C Compiler tests (MIT) from chapter 1 up to whatever the subset reaches, driven by a Forge lit format over `expected_results.json`. Include the `invalid_*` tests for diagnostics.
3. **Broader execution tests:** c-testsuite filtered by tags. Vendor the scc-origin tests (ISC) and fetch the TinyCC-origin ones, or skip them.
4. **Later:** GCC torture fetched at a pinned revision with LLVM's AArch64 and Darwin skip lists; Csmith (`CSMITH_MINIMAL`, features turned off) as a differential job against `clang`.

## Sources

Revisions read (commit, date):

- c-testsuite `5c7275656d75` (2020-03-09): `README.md`, `LICENSE`, `tests/LICENSE`, `runners/single-exec/{posix,gcc-x86_64}`, `tests/single-exec/*.{c,expected,tags,otags}`
- scc `LICENSE`: <https://git.simple-cc.org/scc/file/LICENSE.html>
- TinyCC (GitHub mirror `TinyCC/tinycc`): `COPYING`, `RELICENSING`, `tests/tests2/`
- writing-a-c-compiler-tests `ae12014d2dec` (2026-02-16): `README.md`, `LICENSE`, `expected_results.json`, `test_properties.json`, `test_framework/{basic,runner}.py`, `tests/`
- No Starch, *Writing a C Compiler*: <https://nostarch.com/writing-c-compiler>
- chibicc `90d1f7f199cc` (2020-12-07): `README.md`, `LICENSE`, `Makefile`, `test/{test.h,common,driver.sh,*.c}`; first commit `0522e2d77e3a` and `773115ab2a9c` `test.sh`
- GCC (`gcc-mirror/gcc`) `a3a3f32131a9` (2026-11-22): `gcc/testsuite/gcc.c-torture/`
- llvm-test-suite `ec05cfd8cd10` (2026-11-18): `LICENSE.TXT`, `lit.cfg`, `SingleSource/lit.local.cfg`, `SingleSource/UnitTests/`, `SingleSource/Regression/C/{CMakeLists.txt,gcc-c-torture/README,gcc-c-torture/execute/CMakeLists.txt}`
- Csmith `0cdc710315cf` (2026-03-02): `README.md`, `COPYING`, `runtime/{csmith.h,csmith_minimal.h}`, `src/RandomProgramGenerator.cpp`
- YARPGen `1adb290f4535` (2026-10-08): `README.md`, `LICENSE.txt`, `src/{options,program}.cpp`
- cproc: `LICENSE`, `runtests`, `test/`
- Apple, "Writing ARM64 code for Apple platforms": <https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms>
