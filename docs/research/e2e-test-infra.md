# End-to-end test infrastructure used by compilers

Research for issue #5. It reports facts and trade-offs and makes no decision for Forge.

**Forge constraints this note checks against.** Forge is Apache-2.0 WITH LLVM-exception, uses
googletest for unit tests, and ships no third-party dependencies. A test-only dependency is
acceptable only if Forge could eventually build it. CI hosts are Linux, macOS, Windows (MSVC)
and MinGW.

**Sources.** Every claim below was checked against the project's own source tree, licence
file or official documentation. Trees were read at these commits (shallow clones, 2026-11-17):

| Project | Source | Commit / version |
| --- | --- | --- |
| llvm-project (lit, FileCheck, docs) | github.com/llvm/llvm-project | `5f67339` (2026-11-17) |
| llvm-test-suite | github.com/llvm/llvm-test-suite | `3a7192db` (2026-11-17) |
| GCC testsuite | github.com/gcc-mirror/gcc | `b1ab6f7` (2026-11-17) |
| DejaGnu | mirrors.kernel.org/gnu/dejagnu | release 1.6.3 tarball |
| c-testsuite | github.com/c-testsuite/c-testsuite | `5c72756` (2020-03-09; last push 2020-09-30) |
| chibicc | github.com/rui314/chibicc | `90d1f7f` (2020-12-07) |
| cproc | git.sr.ht/~mcf/cproc | `d1c53dd` (2026-06-01) |
| TinyCC (TCC) | repo.or.cz/tinycc.git | `f830a16` (2026-11-13) |
| scc (simple-cc) | git.simple-cc.org/scc | `66f99bc` (2026-09-15) |
| Csmith | github.com/csmith-project/csmith | `0cdc710` (2026-03-01) |
| YARPGen | github.com/intel/yarpgen | `1adb290` (2026-10-08) |
| C-Reduce / C-Vise | github.com/csmith-project/creduce, github.com/marxin/cvise | `31e855e` / `134d6f6` |
| writing-a-c-compiler-tests | github.com/nlsandler/writing-a-c-compiler-tests | `ae12014` (2026-02-16) |

---

## 1. Summary table

| Tool / corpus | Kind | Runtime needed | Licence | Vendor into Forge repo? | Could Forge eventually build it? |
| --- | --- | --- | --- | --- | --- |
| **lit** | test runner | Python >= 3.8; on Windows also `cmp grep sed diff echo` | Apache-2.0 WITH LLVM-exception | Licence-identical to Forge | Pure Python. CPython is C11 (see 6.2) |
| **FileCheck** | output pattern matcher | C++, links `LLVMSupport` | Apache-2.0 WITH LLVM-exception | Licence-identical, but pulls in LLVMSupport | C++17 plus LLVMSupport |
| **DejaGnu** | test runner | Expect -> Tcl; `runtest` is `/bin/sh` | GPL-3.0-or-later | Copyleft (separate program) | Tcl and Expect are C |
| **GCC torture** (`gcc.c-torture`) | corpus, about 3,900 `.c` | DejaGnu, or your own runner | GPL-3.0-or-later (part of GCC) | Copyleft, "aggregate" clause applies | n/a (data) |
| **llvm-test-suite** | corpus and benchmarks | CMake >= 3.20, lit, its own C tools | Apache-2.0 WITH LLVM-exception, plus about 70 third-party dirs | Mixed. Includes a GPL torture copy | n/a |
| **c-testsuite** | corpus, 220 single-file tests | POSIX sh; Python 3 for some scripts | Harness MIT. Tests: per-test `.otags` (ISC and LGPL-2.1) | Mostly permissive. 69 tests are LGPL-2.1 | n/a |
| **TCC `tests/tests2`** | corpus, 145 tests + `.expect` | make, diff | BSD-3 (picoc) + LGPL-2.1 (TCC changes) | Copyleft (LGPL) | n/a |
| **chibicc `test/`** | corpus, 41 self-checking tests | bash, make, host `cc` to link | MIT | Permissive | n/a |
| **cproc `test/`** | IR golden-file tests, 187 `.c` | POSIX sh, diff | ISC | Permissive, but expects QBE IR | n/a |
| **writing-a-c-compiler-tests** | corpus, 1,630 `.c` by chapter | Python >= 3.8, `gcc` on PATH | MIT | Permissive | n/a |
| **Csmith** | random program generator | C++20, CMake >= 3.16, `m4` at build | BSD-2-Clause-style | Permissive | C++20 |
| **YARPGen** | random program generator | C++17, CMake; `run_gen.py` is Python | Apache-2.0 (+ BSL-1.0 hash) | Permissive | C++17 |
| **C-Reduce / C-Vise** | test-case reducer | Perl / Python 3.10+, **links LLVM/Clang** | NCSA | Permissive | Needs libclang |

---

## 2. LLVM: lit + FileCheck

### 2.1 lit (LLVM Integrated Tester)

- lit is "a portable tool for executing LLVM and Clang style test suites". It discovers
  tests, runs them in parallel and summarises the results (`llvm/docs/CommandGuide/lit.md`).
- **Runtime: Python.** The source is `llvm/utils/lit/` (`lit.py`, `setup.py`,
  `pyproject.toml`). LLVM lists `python >= 3.8` for "automated testing" in its build
  requirements (`llvm/docs/GettingStarted.md`, requirements table). lit can be installed
  on its own from PyPI (`pip install lit`) or from the monorepo subdirectory
  (`llvm/docs/TestSuiteGuide.md`).
- **Test format.** A test file carries `RUN:` lines: shell-like pipelines with substitutions
  such as `%s` (the source file) and `%t` (a temp path). It can also carry `REQUIRES:`,
  `UNSUPPORTED:` and `XFAIL:` lines that gate the test on features (`llvm/docs/TestingGuide.md`).
  `split-file` lets one test file hold several inputs (`TestingGuide.md`).
- **Shell.** lit has an internal pipeline runner (the "internal shell"). As of LLVM 23,
  `ShTest(execute_external=True)` raises an error that says the option "will be removed in
  LLVM-24. Please move to using the internal shell" (`utils/lit/lit/formats/shtest.py`).
  The internal shell is what makes lit work on Windows without bash.
- **Windows.** LLVM's lit config looks for `cmp.exe`, `grep.exe`, `sed.exe`, `diff.exe`
  and `echo.exe`. When they are missing it falls back to Git for Windows' Unix tools and
  forces the internal shell (`utils/lit/lit/llvm/config.py`). `GettingStartedVS.md`
  tells MSVC users to install Python and "Git for Windows with bash tools".
- **Licence.** `llvm/utils/lit/LICENSE.TXT` is Apache-2.0 WITH LLVM-exception, the same as Forge.

### 2.2 FileCheck

- FileCheck reads a check file and matches its directives against stdin: `CHECK`,
  `CHECK-NEXT`, `CHECK-SAME`, `CHECK-EMPTY`, `CHECK-NOT`, `CHECK-COUNT`, `CHECK-DAG`,
  `CHECK-LABEL`, `COM:`, and `--check-prefixes`. Patterns are fixed strings mixed with
  `{{POSIX ERE}}`, string variables `[[VAR:regex]]`, and numeric substitution blocks
  (`llvm/docs/CommandGuide/FileCheck.md`).
- **Runtime: native C++.** The driver is `llvm/utils/FileCheck/FileCheck.cpp` (1,227 lines)
  and the engine is `llvm/lib/FileCheck/FileCheck.cpp` (2,789 lines). Its CMake file
  links `LLVMFileCheck LLVMSupport` (`llvm/utils/FileCheck/CMakeLists.txt`), and the
  engine includes `llvm/ADT/*` and `llvm/Support/*` headers. Building it on its own
  therefore means building LLVMSupport too.
- **Licence:** Apache-2.0 WITH LLVM-exception (top-level `LICENSE.TXT`).

### 2.3 Clang's `-verify` (diagnostic tests inside the compiler)

- Clang's tests come in four kinds: unit tests, **diagnostic tests** using `-cc1 -verify`,
  AST-dump tests piped to FileCheck, and LLVM IR tests piped to FileCheck
  (`clang/docs/InternalsManual.md`, "Testing").
- `-verify` reads comments such as `// expected-error {{use of undeclared identifier 'B'}}`,
  including line offsets (`expected-error@+1`) and counts (`0-1`), and compares them
  against the diagnostics it produced. "If all of the expected diagnostics match … the
  invocation will return normally" (`InternalsManual.md`, "Verifying Diagnostics").
- The mechanism is built into the compiler itself, so diagnostic tests need no outside
  runtime beyond the runner that calls it.

## 3. GCC: DejaGnu + dg directives + torture

### 3.1 DejaGnu

- "The driver that runs this testsuite is called DejaGnu"; `make check` runs the whole
  testsuite (`gcc/testsuite/README`).
- **Runtime: Tcl + Expect + POSIX sh.** "DejaGnu is written in Expect, which in turn uses
  Tcl" (DejaGnu 1.6.3 `README`). The `runtest` entry point is a `#!/bin/sh` script.
  GCC's prerequisites list "DejaGnu version 1.5.3 (or later)", "Expect" and "Tcl" as
  "Necessary to run the GCC testsuite" (gcc.gnu.org/install/prerequisites.html).
  Parts of GCC's testsuite also use Python modules (g++: `pytest` and others; SARIF:
  `check-jsonschema`, skipped when absent) (same page).
- **Licence:** GPL-3.0-or-later (DejaGnu `COPYING`, "Version 3, 29 June 2007").
- **dg directives.** Tests carry comments such as `dg-do preprocess|compile|assemble|link|run`
  ("run" means "produce and run an executable file, which is expected to return an exit
  code of 0"), plus `dg-error regexp`, `dg-warning regexp` and `dg-final { … }`
  (gcc.gnu.org/onlinedocs/gccint/Directives.html). In the torture `execute/` tests the most
  common are `dg-additional-options` (171 uses), `dg-require-effective-target` (150) and
  `dg-do` (84) (counted in tree).

### 3.2 The GCC torture tests (`gcc/testsuite/gcc.c-torture/`)

- Layout: `compile/` (2,017 entries) where the test passes if it compiles, `execute/`
  (1,706 entries) where the test passes if the program runs and exits 0, `execute/ieee/`
  for IEEE floating point, plus `compat/` and `unsorted/`. That is 3,942 `.c` files across
  `execute` and `compile` (counted in tree).
- The rules: "DO NOT PUT NON-PORTABLE TESTCASES IN gcc.c-torture … be careful about
  endianness, assumptions about sizes of datatypes"; "For execution tests, put them in
  execute" (`gcc/testsuite/README.gcc`).
- **The oracle is self-checking.** A failing test calls `abort()` and a passing one returns
  0. 1,560 of the 1,701 `execute/*.c` files reference `abort`. There are no expected-output
  files.
- **The option matrix is what makes it "torture".** `lib/c-torture.exp` runs each test at
  `-O0`, `-O1`, `-O2`, `-O3 -fomit-frame-pointer -funroll-loops …`, `-O3 -g`, `-Os` and
  `-Og -g`.
- **The tests lean on GNU C.** 510 of the 1,701 `execute/*.c` files use `__builtin_*` and
  542 use `__attribute__` (counted with grep). A compiler without these extensions needs a
  skip list. MSVC as a reference compiler cannot run them either.
- **Licence.** No separate licence file covers the testsuite. It is distributed as part of
  GCC under `COPYING3` (GPL-3.0-or-later). The `.exp` drivers carry GPL-3.0+ headers.
  About 100 test files carry an FSF copyright line, and only one (`compile/structs.c`)
  carries a full GPL notice. Most tests have no header at all.

## 4. llvm-test-suite

- **What it is.** "benchmark and test programs … The programs come with reference outputs
  so that their correctness can be checked". It is split into `SingleSource/`,
  `MultiSource/`, `MicroBenchmarks/` (uses google-benchmark), `External/`, `Bitcode/`
  and `CTMark/` (`llvm/docs/TestSuiteGuide.md`).
- **What it needs to run.** lit (Python), and CMake >= 3.20 (`CMakeLists.txt`) configured
  with `-DCMAKE_C_COMPILER=<compiler under test>`. It builds its own helpers `timeit.c`,
  `fpcmp.c` and `not.cpp` (`tools/`). Comparing results uses `utils/compare.py` with
  pandas and scipy (`TestSuiteGuide.md`). The top-level CMake has MSVC handling (for
  example ignoring whitespace on WIN32 because of line endings).
- **`External/`** "Contains descriptions and test data for code that cannot be directly
  distributed with the test-suite. The most prominent members … are the SPEC CPU benchmark
  suites" (`TestSuiteGuide.md`). This is the fetch-or-supply-at-test-time pattern.
- **Licence.**
  - The top level is Apache-2.0 WITH LLVM-exception, with a legacy NCSA section
    (`LICENSE.TXT`).
  - The same file lists about 70 directories that are "under different license terms",
    each "in a separate directory tree with its own LICENSE.txt … or … specific license …
    at the top of every file".
  - The list includes `SingleSource/Regression/C/gcc-c-torture/execute`, a copy of GCC
    torture `execute/` (1,521 entries) "Last checked at SVN version 275024". The
    `execute/builtins` tests are not run, and per-arch skip lists are kept in CMake
    (`gcc-c-torture/README`).
  - The list also includes `Fortran/gfortran/{regression,torture}` and MallocBench
    `gawk`, `make`, `perl` and `gs`.
- **Structural fact.** LLVM keeps this suite, with its GPL and other third-party content,
  in a **separate repository** from llvm-project, whose own tree stays Apache-2.0 WITH
  LLVM-exception.

## 5. Smaller compilers

### 5.1 chibicc (MIT)

- The tests are 41 `test/*.c` files that **check themselves**. They use
  `ASSERT(expected, expr)` from `test/test.h`, which prints and calls `exit(1)` on a
  mismatch. Each test is compiled by chibicc but **linked by the host `cc`** with
  `test/common`, which provides `assert` plus the extern functions and variables the
  tests call (`Makefile` rule `test/%.exe`).
- `test/driver.sh` (bash) tests driver flags such as `-o`, `-S`, `--help` and default
  output names.
- **Self-host stage 2.** `make test-stage2` builds chibicc with itself and reruns every
  test (`Makefile`).
- **Real-world programs.** The `test/thirdparty/*.sh` scripts clone **pinned commits** of
  CPython, git, libpng, SQLite and TinyCC, build them with chibicc and run their own test
  suites (`git reset --hard <sha>` and then `make test`). The upstream sources are fetched
  at test time, never vendored.
- Platform: x86-64 System V on Linux (`README.md`).

### 5.2 cproc (ISC)

- The tests are golden files for the **intermediate representation**. `runtests` (POSIX sh)
  compiles each `test/*.c` with `cproc-qbe` and diffs the result against `.qbe` (QBE IR,
  174 files), `.pp` (preprocessor output, 11) or `.err` (expected diagnostics). The target
  arch is encoded in the file name (`name+arch.c`). `test/constraint/` holds
  C23 constraint-violation tests named after the clauses they test
  (`c23-6.4.4.5p9-…`).
- **Bootstrap.** `make bootstrap` builds stage 2 and stage 3 and checks them with
  `cmp stage2/cproc stage3/cproc`, so stage 2 and stage 3 must be byte-identical
  (`Makefile`, `README.md`).
- **Real software.** `doc/software.md` tracks packages known to build. The stated goal is
  to compile "the entire oasis linux system (excluding kernel and libc)".

### 5.3 TinyCC (LGPL-2.1, partially relicensed to MIT)

- **`tests/tests2/`** holds 145 numbered `.c` files with `.expect` files. The Makefile runs
  `tcc -run` (or compile+run), filters the paths out and runs `diff -Nbu` against
  `.expect`. **The `.expect` files can be generated with the host compiler** (`GEN-CC =
  $(CC) -w -std=gnu99 …`), with `GEN-MSC` using `cl` (`tests/tests2/Makefile`). That is
  differential testing frozen into golden files.
- **`tests/tcctest.c`** is differential at test time. `test.ref` is produced by building
  `tcctest.c` with the host `$(CC)`, and `test1` diffs `tcc -run tcctest.c` against it.
  `test2` and `test3` do the same through one and two self-compiled tcc layers
  (`tests/Makefile`).
- `tests/gcctestsuite.sh` runs an **external** checkout of `gcc.c-torture`. It finds the
  checkout through `TESTSUITE_PATH`, and TCC vendors none of it.
- There is also an ABI test against the host compiler (`abitest`) and a Windows batch
  script (`test-win32.bat`).
- **Licence.** TCC is LGPL-2.1 (`COPYING`). `RELICENSING` records contributors agreeing to
  relicense under MIT terms, with some "NO" or "?" entries, so the tree as a whole is still
  LGPL-2.1. `tests/tests2/LICENSE` says: "either directly copied from the picoc project or
  … subsequently modified … All these modifications are licensed under the same terms as
  TinyCC as specified in the file COPYING". It then reproduces the picoc BSD-3-Clause
  licence.

### 5.4 c-testsuite (shared corpus)

- "a collaborative database of C compiler test cases, minimal test runners, and public
  test results" (`README.md`). It has one suite, `single-exec`, with 220 tests (counted).
  Each `NNNNN.c` passes when it exits 0 and its stdout+stderr matches `NNNNN.c.expected`.
  A `.tags` file holds attributes such as `portable`, `c89`/`c99`/`c11`, `needs-cpp`,
  `needs-libc` and `arch-x86_64`. The runner emits TAP.
- **Runtime.** "posix sh, python3, coreutils" (`README.md`). `single-exec` and the runners
  are sh, the reporting scripts (`tapsummary` and others) are Python, and tag queries use
  the third-party TMSU grammar. The bundled runners check `uname -m` for `x86_64`.
- **Licence.** The harness is MIT, "but not for individual test cases. see tests/LICENSE".
  `tests/LICENSE` says "The licenses of individual test cases can be discovered by a test
  cases .otag file". Breakdown by `.otags` (counted):
  - **150** from scc `tests/scc/execute/` (scc is **ISC**, scc `LICENSE`)
  - **69** from TCC `tests/tests2/` (**LGPL-2.1** with picoc **BSD-3**, see 5.3)
  - **1** (`00001.c`, `int main(){return 0;}`) with no origin tag
- **Activity.** The last push to the repository was 2020-09-30 (GitHub API). The pinned
  commit is from 2020-03-09.

### 5.5 writing-a-c-compiler-tests (MIT)

- This is the companion suite to Nora Sandler's *Writing a C Compiler*: 1,630 `.c` files
  grouped by chapter, with valid and invalid cases and `expected_results.json`.
- **Runtime.** "You need the `gcc` command on your path … You also need Python 3.8 or
  later" (`README.md`).

## 6. Differential testing and random program generators

### 6.1 Differential testing patterns found in these trees

| Pattern | Where | Oracle |
| --- | --- | --- |
| Self-checking program | GCC torture `execute/`, chibicc | `abort()` / non-zero exit |
| Golden stdout | c-testsuite, TCC tests2, llvm-test-suite | `diff` / `fpcmp` vs stored output |
| Golden output generated by a reference compiler | TCC `GEN-CC`/`GEN-MSC`, `test.ref` | host `cc`/`cl` output |
| Golden IR or diagnostics | cproc `.qbe`/`.err`, Clang `-verify`, GCC `dg-error` | text match |
| Stage-N bootstrap | cproc (`cmp` stage2/stage3), chibicc stage2, TCC test2/test3 | identical binaries / identical results |
| Real-world builds plus their tests | chibicc thirdparty, cproc `software.md` | upstream `make test` |
| Random programs, cross-compiler/cross-opt | Csmith, YARPGen | equal checksums |

### 6.2 Csmith (BSD-2-Clause style)

- "a random generator of C programs. Its primary purpose is to find compiler bugs with
  random programs, using differential testing as the test oracle … Csmith outputs C
  programs free of undefined behaviors" (`README.md`). Each generated program prints a
  checksum of its globals, and the README's workflow compiles it with gcc and clang and
  compares the outputs. "The generated programs might contain infinite loops … apply
  timeout".
- **Runtime.** It is built with CMake >= 3.16 at `CXX_STANDARD 20` (`src/CMakeLists.txt`),
  and **`m4` is required** to generate runtime headers (`CMakeLists.txt`). Generated
  programs include `runtime/csmith.h` (BSD), which has platform headers including
  `runtime/windows`. There is a Windows build doc (`doc/build-csmith-on-windows.md`). The
  optional drivers `scripts/compiler_test.pl` and `launchn.pl` are Perl, and
  `compare_csmith_outputs.py` and `gen100.py` are Python.
- **Licence:** `COPYING`, "often called the 'BSD License'" (two clauses), © University of Utah.
- **Paper:** Yang, Chen, Eide, Regehr, "Finding and Understanding Bugs in C Compilers",
  PLDI 2011 (linked from `README.md`). `BUGS_REPORTED.TXT` lists the bugs reported.

### 6.3 YARPGen (Apache-2.0)

- It produces "correct runnable C/C++ and DPC++ programs … specifically designed to trigger
  compiler optimization bugs". Each program "produces a decimal number, which is hash of
  all program global variable values … supposed to be the same for all compilers and
  optimization levels". It "managed to find more than 260 bugs" in gcc, clang and others
  (`README.md`).
- There are two generators: `main` tests loops (PLDI 2023 paper) and the `v1` branch tests
  scalar optimisations (OOPSLA 2020 paper). Both papers are in `papers/`. `--std` accepts
  `c`, `c++`, `ispc` and `sycl` (`src/options.cpp`).
- **Runtime.** The generator is C++17 (`set(STD cxx_std_17)`, `src/CMakeLists.txt`) built
  with CMake. The recommended driver, `scripts/run_gen.py`, is **Python**. MSVC is tested
  "from WSL … through `cl-proxy`" (`README.md`).
- **Licence.** `LICENSE.txt` is Apache-2.0, and it "incorporates code of hash function from
  the Boost library" under BSL-1.0.

### 6.4 Test-case reducers (used with the generators)

- **C-Reduce** "is written in Perl, C++, and C". Its prerequisites include LLVM/Clang,
  because `clang_delta` links libclang, and several Perl modules (`INSTALL.md`). Licence:
  NCSA (`COPYING`). Last commit 2024-06-01.
- **C-Vise**, the successor, "is written in Python 3, C++, and C". It needs LLVM/Clang
  18 or later and Python 3.10 or later (`INSTALL.md`), and vendors tree-sitter.
  Licence: NCSA (`LICENSE`).
- Both reducers therefore make LLVM/Clang a build dependency.

## 7. Licence analysis for Forge

These are the facts that matter for Forge's choice. They are not legal advice.

1. **Permissive corpora and tools** can be vendored into an Apache-2.0 WITH LLVM-exception
   repo if their notices are kept: MIT (chibicc, c-testsuite harness,
   writing-a-c-compiler-tests), ISC (scc, cproc), BSD (Csmith, picoc), NCSA (C-Reduce,
   C-Vise), Apache-2.0 (YARPGen), BSL-1.0. Apache-2.0 §4 also asks that modified files
   "carry prominent notices stating that You changed the files".
2. **lit and FileCheck** have exactly Forge's licence, so vendoring them raises no licence
   question. The open question is the dependency (Python, or LLVMSupport).
3. **The GPL-3.0-or-later corpora** (GCC torture, and DejaGnu as a tool) are separate
   programs that are run, not linked into Forge. GPLv3 §5: "Inclusion of a covered work in
   an aggregate does not cause this License to apply to the other parts of the aggregate"
   (`gcc/COPYING3`). Vendoring them is therefore allowed. The cost is a mixed-licence repo
   and source tarballs, plus the GPL obligations on whoever redistributes those files.
   LLVM's choice is a documented precedent: GPL torture code lives only in the **separate**
   llvm-test-suite repo, never in llvm-project.
4. **LGPL-2.1 test files** (TCC tests2, and the 69 TCC-origin tests in c-testsuite) have
   the same character as the GPL corpora: copyleft data, not linked. "Just vendor
   c-testsuite" is therefore not a purely permissive option. Its 150 scc-origin tests are
   ISC and its 69 TCC-origin tests are LGPL-2.1/BSD-3.
5. **Fetching at test time** keeps the repo uniformly Apache-2.0 WITH LLVM-exception.
   Precedents: chibicc's `test/thirdparty/*.sh` pin commit SHAs, TCC's
   `gcctestsuite.sh` takes `TESTSUITE_PATH`, and llvm-test-suite's `External/` covers
   SPEC. The costs are network access in CI, a pinned version to maintain, and upstream
   availability. c-testsuite has been inactive since 2020, and GCC's torture copy in
   llvm-test-suite is pinned at an old SVN revision.

## 8. Forge's constraints against these tools

- **Python appears everywhere.** lit, c-testsuite's reporting scripts, YARPGen's driver,
  C-Vise, writing-a-c-compiler-tests, llvm-test-suite's `compare.py`, and parts of GCC's
  testsuite all use it.
- **Python is buildable C, in principle.** CPython 3.11+ uses "C11 without optional
  features" (PEP 7), and chibicc's `test/thirdparty/cpython.sh` shows a hobby C compiler
  building and testing CPython. Under the rule "tolerated only if Forge could eventually
  build them", Python is therefore not excluded outright. Tcl/Expect (DejaGnu) and Perl
  (Csmith's drivers, C-Reduce) are also C programs. Forge needs to decide whether
  "could build" means the interpreter or something narrower.
- **Some native tools need C++17 or C++20 from Forge's C++ compiler.** FileCheck (with
  LLVMSupport), YARPGen (C++17) and Csmith (C++20) qualify only once Forge's C++ compiler
  is mature. C-Reduce and C-Vise additionally need libclang.
- **Things that need nothing extra.** The self-checking pattern (`abort()`, exit status),
  golden-stdout diffs and stage-N `cmp` need only a shell, or even just CTest and a small
  runner built with the host compiler. cproc and chibicc test this way with POSIX sh/bash
  and diff.
- **CI host notes.**
  - lit on Windows (MSVC) needs Python and Unix tools (Git for Windows).
  - DejaGnu needs `/bin/sh`, Tcl and Expect, so on Windows it needs a POSIX layer.
  - Many GCC torture tests need GNU extensions (`__builtin_*`, `__attribute__`), so MSVC
    cannot serve as the reference compiler for them.
  - The c-testsuite runners as shipped assume `x86_64`.
  - Csmith's runtime ships Windows headers. YARPGen tests MSVC only through WSL.
  - A reference compiler differs by host: gcc or clang on Linux and MinGW, Apple clang
    on macOS, `cl` on MSVC. TCC's Makefile already switches between `GEN-CC` and `GEN-MSC`.
