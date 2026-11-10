# C budget-suite census

Research for GitHub issue #10, "Milestone-1 C slice definition". Throwaway branch `research/c-budget-suite-census`; never merged, no PR. This file is generated: `c-budget-suite-census/scripts/report.py` fills the tables in `c-budget-suite-census/scripts/main.md`, so edit the template, not this file.

**Question.** Milestone 1 compiles C for aarch64-unknown-linux-gnu (Ubuntu 26.04: GCC 15.2, glibc 2.43, binutils 2.46) at `-O0`. What do the C programs in llvm-test-suite's CTMark and Benchmarks trees need from a C compiler? Which ISO C revision, which GNU extensions, and do they use `long double`, `__int128`, `_Complex`, VLAs, atomics or threads? Do they compile under GCC 15's default `gnu23`? Parts B and C take lighter passes over GCC's C torture tests and glibc's C-mode header steering. This note records facts only. It makes no decisions and recommends nothing.

**Method in one paragraph.** All inputs are primary: llvm-test-suite's own CMake files and sources, and Ubuntu 26.04's own glibc headers (section 0). Nothing from a download was built or executed. CMake files were read as text by `enumerate.py`, which evaluates a fixed configuration: ARCH=AArch64, TARGET_OS=Linux, little-endian, default problem size, `TEST_SUITE_BENCHMARKING_ONLY` off. Features were found three ways:

1. `scan.py` greps every file a program reaches through quoted `#include`s. Comments are stripped and string contents blanked. It sees every `#if` branch.
2. `pp.py` greps the `gcc-16 -E` output, keeping only lines from the program's own files. It sees only the branches GCC's identity selects, but it also sees system-header macros that expand in program code.
3. `diag.py` runs `-fsyntax-only` with Apple clang 17 retargeted to `aarch64-unknown-linux-gnu`, and with Homebrew GCC 16 on Darwin. Both use `-nostdinc` against Ubuntu's glibc 2.43 and kernel headers. Only diagnostics located in files under the test-suite tree are kept.

Every number below comes from that data.

## 0. Sources and versions

| Input | Version | Where | Integrity |
|---|---|---|---|
| llvm-test-suite | `main` at **`2ecf20c22c4c25051026fa450e0b0beb7d922209`** (2026-11-08, "[CTMark] Add beman.execution as a modern C++ benchmark (#512)") | `https://github.com/llvm/llvm-test-suite`, `git clone --depth 1 --filter=blob:none --sparse` | git object hashes |
| libc6-dev (arm64) | **2.43-2ubuntu2.4** (resolute-updates and resolute-security) | `http://ports.ubuntu.com/ubuntu-ports/pool/main/g/glibc/libc6-dev_2.43-2ubuntu2.4_arm64.deb`, 1843700 bytes | SHA256 `f6f7705d3e6bb982c173a42cc5b2516eddebe2d846c4861ee7d7c9d66ebee916`; matches the `Packages.gz` entry |
| linux-libc-dev (arm64) | 7.0.0-43.43 (resolute-updates and resolute-security) | `.../pool/main/l/linux/linux-libc-dev_7.0.0-43.43_arm64.deb`, 1859028 bytes | SHA256 `3d6313ac30170df8614618fd1aeb864606c378d90aa18e5d2012aad46861d753`; matches the index |

- **Sparse checkout.** The requested paths were `CTMark/`, `SingleSource/Benchmarks/`, `MultiSource/Benchmarks/`, `cmake/` and the top-level `CMakeLists.txt`. Four of CTMark's six C programs are symlinks into `MultiSource/Applications/` (section 1.2), so those four directories were added: `ClamAV/`, `SPASS/`, `sqlite3/` and `JM/lencod/`. Four intermediate `CMakeLists.txt` files were added so the inherited scope is visible: `SingleSource/`, `MultiSource/`, `MultiSource/Applications/` and `MultiSource/Applications/JM/`. Nothing else outside the request was checked out.
- **Ubuntu indexes.** The indexes are `dists/{resolute,resolute-updates,resolute-security}/main/binary-arm64/Packages.gz`. Each SHA256 matches its `Release` file. resolute-updates `Release` is dated 10 Nov 2026 11:02:35 UTC (`Packages.gz` `b7740a25…accb`), resolute-security 10 Nov 2026 10:29:21 UTC (`7cc3d5d0…ee11`), resolute 23 Apr 2026 (`1095e9e8…e297`). The release pocket has libc6-dev 2.43-2ubuntu2. The earlier note `docs/research/host-header-extensions.md` (branch `research/host-header-extensions`, section 0) found its `/usr/include` byte-identical to 2.43-2ubuntu2.4.
- **Tools.** Apple clang 17.0.0 (clang-1700.0.13.5), run with `--target=aarch64-unknown-linux-gnu -nostdinc` plus its own resource headers. Homebrew GCC 16.1.0 (`aarch64-apple-darwin24`), run with `-nostdinc` plus its own `include/` directory. GCC was given the Linux identity: `-U__APPLE__ -U__MACH__ -U__APPLE_CC__ -D__linux__ -D__gnu_linux__ -D__unix__ -D__ELF__ -funsigned-char`. Both force-include glibc's `stdc-predef.h`, as GCC does on glibc systems. Python 3.15.1 ran the scripts, always with `python3 -I`.
- **Scripts.** All are in `c-budget-suite-census/scripts/`; each docstring gives its arguments. The pipeline is: `enumerate.py`, then `scan.py`, then `pp.py`, then `diag.py` once per configuration in section 4, then `longdouble.py`, then `report.py`. Part B uses `torture.py`; Part C uses `glibc_c.py`.

## 1. The programs

### 1.1 Counts

{{COUNTS}}

"Program" means one test executable. A `llvm_multisource()` call is one program. A `llvm_singlesource()` directory gives one program per source file (`cmake/modules/SingleMultiSource.cmake`, `llvm_singlesource` and `llvm_multisource`). The counts are for the configuration in the method paragraph. Programs that CMake adds only on other targets are not included, for example `aarch64-init-cpu-features.c` in `SingleSource/Benchmarks/Misc`, which is added only when `__init_cpu_features` links (`HAS_AARCH64_FMV`). Five `check_*` results had to be assumed for Ubuntu 26.04 arm64 with GCC; they are listed in `enumerate.py`'s `TRUTH` table. The two that change membership are:
- `HAVE_SGTTY_INCLUDE` is true, because libc6-dev 2.43 ships `/usr/include/sgtty.h`. This adds office-ispell.
- `HAVE_RE_COMP` is true, because glibc's libc exports `re_comp`. This adds plot2fig and archie. That one was not verified against a libc6 binary (section 9).

Line counts are physical lines (`\n` count). The totals count each distinct file once, because Polybench's 30 programs, for example, share `utilities/polybench.h`. Per-program counts in section 3 include every file that program reaches.

### 1.2 CTMark

`CTMark/CMakeLists.txt` adds eleven subdirectories. Each `CTMark/<name>` entry is a git symlink (mode `120000`) into the MultiSource tree. CTMark therefore builds the very same `CMakeLists.txt`, sources and flags as the MultiSource entry; it is a subset, not a copy. Six of the eleven are C:

{{CTMARK}}

The other five are C++ (Bullet, tramp3d-v4, kimwitu++ and beman-execution) or mixed C and C++ (7zip). `CTMark/README.md` says the subset is meant for compile-time measurement (`-DTEST_SUITE_SUBDIRS=.../CTMark -DTEST_SUITE_RUN_BENCHMARKS=0`). The top-level `CMakeLists.txt` drops `CTMark` from the default subdirectory list, so a default configure builds these programs only through MultiSource.

## 2. What the suite does globally for C

From the top-level `CMakeLists.txt` and `cmake/modules/`:

- **No default `-std=`.** `project(test-suite C CXX)` sets no `CMAKE_C_STANDARD`, so each program gets the compiler's default dialect. That is gnu23 for GCC 15 (`gcc-16 -dM -E` here reports `__STDC_VERSION__ 202311L`) and gnu17 for clang. A program opts out with `set_property(TARGET … PROPERTY C_STANDARD N)`. With CMake's default `C_EXTENSIONS` (ON), that becomes `-std=gnuN`. 73 of the 252 C programs set it, and two more put `-std=c99` in their `CFLAGS` (section 3.1).
- **`add_definitions(-DNDEBUG)`** (top-level `CMakeLists.txt`). "The test-suite is designed to be built in release mode anyway and falls over unless -DNDEBUG is set". `CMAKE_BUILD_TYPE` defaults to `Release`. Every compile here passes `-DNDEBUG`.
- **`add_definitions(-w)`** while `TEST_SUITE_SUPPRESS_WARNINGS` is ON, which is the default. It suppresses warnings only. GCC 14+ turns `-Wimplicit-function-declaration`, `-Wimplicit-int`, `-Wint-conversion`, `-Wincompatible-pointer-types` and `-Wreturn-mismatch` into errors, and `-w` does not silence them: a probe with gcc-16 `-w` still reports them as `error:`. The suite works around this program by program: `-Wno-implicit-int` (50 programs), `-Wno-error=incompatible-pointer-types` (69), `-Wno-int-conversion` (6), `-Wno-implicit-function-declaration` (9).
- **`add_definitions(-Werror=date-time)`** for reproducible builds.
- **Flags are applied to every source.** `llvm_test_executable_no_test` (`cmake/modules/TestSuite.cmake`) appends `CFLAGS`, `CPPFLAGS`, `CXXFLAGS` and `FFLAGS` to the target's `COMPILE_FLAGS` property, so `CXXFLAGS` also reach C files. `LDFLAGS` go to `LINK_LIBRARIES`.
- **Verification.** `llvm_test_traditional` (`cmake/modules/SingleMultiSource.cmake`) runs the program in its source directory and, when `HASH_PROGRAM_OUTPUT` is set, hashes the output. Unless `NO_REFERENCE_OUTPUT` is set, it diffs the output against `<name>.reference_output`, with optional `.little-endian`, `.small`/`.large` or `.<TARGET_OS>` variants. The diff tool is `fpcmp`, with `-r FP_TOLERANCE` (relative), `-a FP_ABSTOLERANCE` (absolute) and `-i` on Windows.
- **Other globals.** PowerPC adds `-ffp-contract=off`. AIX adds `-D_XOPEN_SOURCE=700`; z/OS adds `-D_ALL_SOURCE`. `TEST_SUITE_DISABLE_PIE` adds `-Wl,-no_pie` only on non-AArch64 Apple, and its "TODO" says nothing is done on Linux. None of these apply to aarch64 Linux.
- **No GCC-version-specific flags.** Nothing in `cmake/` or the top-level file tests the C compiler's version or adds flags for newer GCC or clang. The only compiler-ID test for C is clang-cl (`/FIstdio.h`). The GCC 14 and GCC 15 adaptations are all per program: the `-Wno-*` flags above and the `C_STANDARD` pins.

## 3. Per-program flags

### 3.1 Flag frequencies

`-D`/`-U`/`-I` flags are per program and listed in 3.3. This table counts the other flags across the 252 C programs. "std" rows give the dialect the suite asks for.

{{FLAGSUMMARY}}

### 3.2 Reference outputs and tolerances

Every one of the 252 C programs has a reference output, and none sets `NO_REFERENCE_OUTPUT`. 52 also set `HASH_PROGRAM_OUTPUT`. fpcmp tolerances appear in 3.3's last column: `r` is `FP_TOLERANCE`, `a` is `FP_ABSTOLERANCE`, "exact" means neither is set. The 30 Polybench programs pass `-DFP_ABSTOLERANCE=1e-5` with `add_definitions`. That is a macro for the program's own comparison code (for example `adi.c:202` `double AbsTolerance = FP_ABSTOLERANCE;`), not an fpcmp option; they are verified by hash.

### 3.3 Table

Directories are abbreviated: `SS` = `SingleSource/Benchmarks`, `MS` = `MultiSource/Benchmarks`, `MA` = `MultiSource/Applications`. CTMark's six are in bold. `-DNDEBUG` (global) is omitted. "Lines" is `.c` plus local headers reached by that program.

{{FLAGS}}

## 4. Language features

### 4.1 How features were detected

- **Reached (`gcc -E`).** Most counts come from `pp.py`, which preprocesses each program with gcc-16 in the dialect the suite passes, with glibc 2.43 headers and the program's flags, and keeps only lines from the program's own files. Code in inactive `#if` branches is not counted; for example ClamAV's and consumer-lame's `long double` appear only in such branches. The identity is GCC's (`__GNUC__` 16, no `__clang__`), so where a program tests `__GNUC__` the GCC path is the one counted.
- **Diagnostics (clang).** VLAs, K&R definitions, `()` declarations, implicit int, implicit declarations, computed goto and the C99/C11/C23 extension warnings come from clang's diagnostics in program files. Clang ran with `--target=aarch64-unknown-linux-gnu` against the same glibc headers. The flags were `-std=gnu17 -pedantic -Wvla -Wgnu -Wc23-extensions -Wimplicit-int -Wimplicit-function-declaration -Wdeprecated-non-prototype -Wstrict-prototypes`, plus `-std=gnu99 -pedantic -Wc11-extensions` and `-std=gnu89 -pedantic`. The default-error diagnostics were downgraded with `-Wno-error=…`, so a file keeps going after the first one. The program's own `-W` flags were dropped for these runs so the warnings fire.
- **Grep (`scan.py`).** Grep, which also sees inactive branches, supplies `//` comments, `#define f(...)` variadic macros, the include lists and the "inactive" rows.
- **Apple SDK.** No Apple SDK header was used, so nothing broke for SDK reasons. The section-0 fallback was not needed.
- **No C++-only constructs.** No program hit a clang error for a construct GCC accepts (nested functions, for example). The only clang errors in program files under `-std=gnu17` are `restrict` used as an identifier, in espresso and cdecl, which the suite pins to C90.

{{FEATURE_COUNTS}}

### 4.2 Revisions

"Needs" is the newest ISO revision with a construct the program spells and reaches:
- **C99** means any of: `//` comments, `long long`, mixed declarations and code, a declaration in a `for` initializer, `_Bool`, `inline`, `restrict`, a VLA, a flexible array member, a compound literal, a hex float, a variadic macro, a non-constant aggregate initializer, or a C99 header (`<stdint.h>`, `<stdbool.h>`, `<inttypes.h>`, `<complex.h>`, `<fenv.h>`, `<tgmath.h>`).
- **C11** means a C11 keyword or one of `<stdalign.h>`, `<stdatomic.h>`, `<stdnoreturn.h>`, `<threads.h>`, `<uchar.h>`. No program spells any of them, so no program reaches C11.
- **C17 is not a column.** C17 added no language features over C11 (it is a defect-correction revision), so it would always equal the C11 row.
- **"C23/GNU"** marks a C23 construct that GCC has long accepted as a GNU extension in older dialects: an empty initializer `{}` (gs) or `#warning` (miniGMG).

Library functions (`snprintf`, `strtoll`, …) are not counted; section 9 says why.

"GCC 16 accepts" is the range of `-std=gnuNN` that GCC 16 compiles without errors, with the program's own flags. It is the measured counterpart: the oldest dialect shows what the program needs, the newest shows what C23 removed.

{{REVISIONS}}

### 4.3 `long double`

AArch64 Linux makes `long double` IEEE binary128 (`__LDBL_MANT_DIG__` 113 for this target). Two programs reach it:

{{LONGDOUBLE}}

- **automotive-basicmath** (`MS/MiBench/automotive-basicmath/cubic.c:19-21`) declares `long double a1 = b/a, a2 = c/a, a3 = d/a;` and computes `Q` and `R` in `long double`. The `FloatingCast` nodes are the conversions to and from `double` around calls to `sqrt`, `cos`, `acos` and `pow`. It calls no `*l` function and uses no `%L` format. `snipmath.h:45` also declares `long double ldfloor(long double)`.
- **sqlite3** (version 3.5.7, amalgamation generated 2008-03-17; `sqlite3.c:553`). `sqlite3.c:6276-6277`: `#ifndef LONGDOUBLE_TYPE` / `# define LONGDOUBLE_TYPE long double`. The only other definition, `sqlite_int64` at `:6160`, applies under `SQLITE_OMIT_FLOATING_POINT`, which the suite does not set. Three places use it:
  - **Float printing.** `vxprintf` holds the value in `LONGDOUBLE_TYPE realvalue` (`:13881`), loaded with `va_arg(ap,double)` (`:14091`). It normalises by repeated `*= 1e-32`, `*= 1e-8`, `*= 0.1`, `*= 1e8`, `*= 10.0` (`:14120-14124`) and adds a rounder (`:14111`, `:14144`). It then extracts digits with `et_getdigit(LONGDOUBLE_TYPE *val, int *cnt)` (`:13796`): `digit = (int)*val; … *val = (*val - d)*10.0;`. That stops after 16 digits.
  - **`sqlite3AtoF`** (`:15853`) accumulates `LONGDOUBLE_TYPE v1` with `v1 = v1*10.0 + (*z - '0')`. It keeps a `long double` `divisor` and `scale` (`scale *= 1.0e+64` etc.) and finally stores into a `double *pResult`.
  - **No library use.** Neither place uses `%Lf` or any `*l` function. All `long double` work is the four arithmetic operators, comparisons and conversions to and from `double` and `int`.
  - **Tolerance.** The suite compares sqlite3's output with `FP_TOLERANCE 1.0e-9`. `MultiSource/Applications/CMakeLists.txt` excludes sqlite3 only on PowerPC and XCore, so it is also configured on AArch64 Darwin, where `long double` is IEEE double (`gcc-16 -dM -E` there: `__SIZEOF_LONG_DOUBLE__ 8`, `__LDBL_MANT_DIG__ 53`). Whether the reference output still matches there was not checked (section 9).
- **Inactive only.** consumer-lame and clamscan mention `long double` only inside inactive branches: the AST of the active code has no `long double` node.
- **Nothing else.** No program has `%Lf`/`%Le`/`%Lg` formats or calls a `<math.h>` `*l` function.

### 4.4 Attributes, builtins and pragmas

The "reached" lists include expansions of glibc macros in program code. For example `__builtin_va_*` comes from `<stdarg.h>`, so it is left out of the builtin list. The "spelled" lists are grep over the program's own files across every branch.

{{ATTRS}}

### 4.5 System headers

`#include <…>` targets in the program's files, plus quoted includes that name a standard header and do not resolve locally. Grep-level, so includes in inactive branches count too.

{{HEADERS}}

### 4.6 Per-program table

Columns:
- **"Needs"** and **"GCC 16 accepts"**: see 4.2.
- **`long double`**: "arith" means arithmetic is reached; "inactive" means grep-only.
- **K&R defs**: K&R function definitions.
- **`f()` called with args**: calls that pass arguments to a function declared `()`.
- **`f()` decl conflicts**: `()` declarations that conflict with a definition or another declaration once `()` means `(void)`.
- **implicit int**, **implicit decl**: clang diagnostic counts in program files.
- **gnu23 errors**: GCC 16's errors at its default dialect, grouped by message.

{{FEATURES}}

## 5. GCC's default `gnu23` versus `gnu17`

This was measured with GCC 16.1 (Homebrew, `aarch64-apple-darwin24`) given the Linux identity (section 0), not GCC 15.2 on Ubuntu. GCC 16's default is `gnu23`, as GCC 15's is. Each configuration passes the program's own `-D`, `-I`, `-f` and `-W` flags; the `-W` flags are how the suite keeps GCC 14+ permerrors off. Only errors located in program files are counted.

{{GNU23}}

Observations from the error text (`diag-gcc-*.json`):
- **What C23 changes.**
  - **`()` now means `(void)`.** Almost all gnu23 errors come from this. Old-style declarations such as `extern int fputs(), fputc();` (plot2fig `closepl.c:29`) now conflict with glibc's prototypes, and calls that pass arguments to `()`-declared functions are now "too many arguments".
  - **Keywords.** The second cause is `bool`, `true` and `false` becoming keywords: `typedef … bool` in trie and bh, `enum { false, true }` in the Shootout programs and timberwolfmc, and a `bool` parameter name in SPASS's `dfgparser.y`.
- **K&R definitions still compile in GCC 16 at `gnu23`.** A probe gave `int bar(x) int x; { return x; }` only `warning: old-style function definition [-Wold-style-definition]`, under both `-std=c23` and the default. Clang 17 at `-std=gnu23` rejects the same line with "unknown type name 'x'". So the K&R column in 4.6 does not by itself predict a GCC gnu23 failure; the `()`-call and conflict columns do.
- **unix-tbl: glibc's C23 `strchr` macro.** `t3.c:6` has `#define index strchr` before `#include <string.h>`. At `gnu23`, glibc 2.43 defines `strchr(S, C)` as `__glibc_const_generic (S, const char *, strchr (S, C))`, a `_Generic` (`string.h:263-265`, `sys/cdefs.h:837-840`). `<strings.h>`'s declaration of `index` then expands into that macro, giving "expected identifier or '(' before '_Generic'". This is the only gnu23 error caused by header text rather than program text.
- **unix-tbl also fails at gnu17** with "passing argument 2 of 'signal' from incompatible pointer type" (`t1.c:41`). Its `CMakeLists.txt` adds `-Wno-incompatible-function-pointer-types`, a clang-only spelling. GCC's flag is `-Wno-incompatible-pointer-types`.
- **espresso and cdecl fail at gnu17, gnu11 and gnu99** because of implicit int and `restrict` used as an identifier. The suite pins both to `C_STANDARD 90` (`-std=gnu89`), where they compile.
- **What GCC 15 sees as the suite configures it.** Without a pin the suite compiles at the compiler's default (section 2), so with GCC 15 or 16 three programs fail as configured:
  - plot2fig and archie fail at `gnu23` only;
  - unix-tbl fails at `gnu23`, and at `gnu17` because of its clang-only flag.

## 6. Fallout if the slice dropped a feature

Programs that would fall out if milestone 1 dropped each item. "Falls out" means the program reaches the construct after `gcc -E` (or clang reports it in program code); a construct only in inactive branches does not count. CTMark's six are listed individually.

{{FALLOUT}}

- **C11 row.** Every program that compiles at `gnu17` also compiles at `gnu99` and `gnu11` under GCC 16 (4.2), and none spells a C11 construct. The 33 programs pinned to `C_STANDARD 17` are pinned to stay below C23, not because they need C11. A slice limited to C99 would still meet C11 constructs in glibc's headers (Part C).
- **C99 rows.** All 46 programs that fail at `-std=gnu89` contain `for (int i = …)` declarations ("'for' loop initial declarations are only allowed in C99 or C11 mode", 1,718 errors), and two of them also use `restrict` as a keyword. GCC accepts the rest of the C99 list in 4.2 in `gnu89` as extensions: `//`, `long long`, mixed declarations, `inline`, VLAs, flexible arrays and `_Bool`.
- **Inactive branches.** `long double` and pthreads appear only in inactive branches in four programs (4.1). sqlite3 is built with `-DSQLITE_THREADSAFE=0`. smg2000 uses `-DHYPRE_SEQUENTIAL`. ClamAV's and AMGmk's pthread code is not reached on this configuration. No C program's flags include `-pthread`.

## 7. Part B: GCC C torture tests (grep-level)

**Source.** `gcc/testsuite/gcc.c-torture/execute/` from GCC's `releases/gcc-15` branch, via the GitHub mirror `https://github.com/gcc-mirror/gcc`. The tip was **`7b7cd17e123e311a083df49f79822ffabee7205f`** (2026-11-10, "Daily bump."), fetched with `git clone --depth 1 --filter=blob:none --sparse`. The branch tip is later than the 15.2.0 release; the directory was not compared with the `releases/gcc-15.2.0` tag.

**What a test is.** A `.c` file in `execute/` (1,682), a `builtins/*.c` file other than a `*-lib.c` helper (58), or an `ieee/*.c` file (69): **1,809 tests**. `torture.py` counts regex hits on comment-stripped text. Nested functions, VLAs and labels-as-values come from clang (`-std=gnu17`, aarch64-unknown-linux-gnu, glibc 2.43 headers), which reports them per file. **Everything here is grep-level**:
- `#if`-guarded uses count. For example, most `__int128` tests test `__SIZEOF_INT128__` first.
- The inline-asm count includes `asm("")` barriers and target-guarded blocks.
- The grep computed-goto count includes `&&` false positives.

{{TORTURE}}

**C23 adaptations visible in the directives.** GCC 15 made `gnu23` the default. Tests now carry `-std=gnu89` (75 tests), `-std=gnu17` (13) and `-fpermissive` (32), the GCC 14 permerror downgrade. `-fgnu89-inline` appears in 12. These are counts of directive occurrences in test files; the 52 `.x` files can add options too and were not read.

## 8. Part C: glibc 2.43's C-mode steering (time-boxed)

**Source.** libc6-dev 2.43-2ubuntu2.4 (arm64) and linux-libc-dev 7.0.0-43.43, from Ubuntu 26.04's archive (section 0). This is the 26.04 package, so no sourceware fallback was needed.

**Method.** `glibc_c.py` preprocesses 47 root headers with `-E -dD`, using gcc-16 with the aarch64-linux-gnu identity. The roots are the ISO C headers glibc ships plus the POSIX headers the suite uses. It keeps the lines that come from glibc and kernel headers, and diffs configurations. One correction was needed. gcc-16's Darwin build installs its own `tgmath.h`, which shadows glibc's, while Ubuntu's GCC uses glibc's. So `tgmath.h` was included by path. The earlier note's method was followed (`host-header-extensions.md` sections 0 and 2): glibc read from the archive, GCC identity imposed, macros steered with `-std`/`-O`/`-D`. Its C++-mode results were not redone.

**Steering sites** in `/usr/include` (grep, lines that test the macro):
- `__STDC_VERSION__`: 25 lines, 5 files: `features.h`, `sys/cdefs.h`, `assert.h`, `threads.h`, `regex.h`.
- `__GLIBC_USE (ISOC23)`/`ISOC2X`: 59 lines, 19 files.
- `__USE_ISOC11`: 13 lines, 5 files. `__USE_ISOC99`: 59 lines, 16 files.
- `__OPTIMIZE__`: 15 lines, 8 files. `__USE_EXTERN_INLINES`: 17 lines, 14 files.
- `_FORTIFY_SOURCE`/`__USE_FORTIFY_LEVEL`: 103 lines, 26 files.
- **`__glibc_has_c_attribute`: 0.** glibc 2.43 has no such macro, and no header line contains `[[`.
- **`features.h:268-272` selects ISO C23 content in two ways.** `__GLIBC_USE_ISOC23` is 1 when `__STDC_VERSION__ > 201710L`, *or* when `_ISOC23_SOURCE` is defined. `_GNU_SOURCE` defines `_ISOC23_SOURCE` (`features.h:217-226`). So a program that defines `_GNU_SOURCE` gets the C23 header content in every dialect. ClamAV's gnu99 `_Generic` diagnostic in section 4 is this case (`libclamav_mbox.c:1397`, `strchr`).

{{GLIBC_PAIRS}}

"Lines" counts distinct (header, text) pairs, including `#define` lines from `-dD`; "(no listed construct)" lines are ordinary declarations and macros.

**Constructs emitted under `__STDC_VERSION__ == 202311L` and not under `201710L`** (`c23 minus c17`; `gnu23 minus gnu17` differs only in GNU-dialect lines):
- **Qualifier-preserving `_Generic` macros.** 11 function-like macros wrap `__glibc_const_generic`: `memchr`, `strchr`, `strrchr`, `strpbrk`, `strstr` (`string.h:121-380`), `bsearch` (`stdlib.h:991`), and `wcschr`, `wcsrchr`, `wcspbrk`, `wcsstr`, `wmemchr` (`wchar.h:196-302`). The macro itself is a `_Generic`: `_Generic (0 ? (PTR) : (void *) 1, const void *: (CTYPE) (CALL), default: CALL)` (`sys/cdefs.h:837-840`). It is *defined* in every C dialect under GCC ≥ 4.9 (`__HAVE_GENERIC_SELECTION`, `sys/cdefs.h:821-829`) but only *used* under `__GLIBC_USE (ISOC23)`.
- **`bool` in declarations.** `<stdbit.h>` declares `stdc_has_single_bit_*` returning `bool` (`stdbit.h:622-631`) and defines a `static __inline … bool` body (`stdbit.h:660`). Under `201710L` the same declarations use `_Bool`. The other `<stdbit.h>` type-generic macros expand to `__builtin_stdc_*` in both dialects (`stdbit.h:124…`, 14 macros).
- **Variadic `assert(...)`** (`assert.h:144`) with `extern _Bool __assert_single_arg (_Bool);` (`assert.h:117`).
- **`char8_t`, `mbrtoc8` and `c8rtomb`** (`uchar.h:47-72`).
- **`__isoc23_` symbol redirections** for the `strto*`, `wcsto*` and `scanf` families (`stdlib.h:219…`, `inttypes.h:389-399`, `stdio.h:449-526`). These are `__asm__` labels, so the source construct is the same as in C17, but the linked symbol differs.
- **C23 library surface.** This includes `fadd`/`fdiv`/`ffma`/`fmul` and the other narrowing functions (`bits/mathcalls-narrow.h`), `femode_t`, the `__STDC_VERSION_*_H__` macros, and the `iszero`, `issignaling`, `iscanonical` and `iseqsig` macros. `iszero` and `iscanonical` use GNU `__typeof`, not C23 `typeof`.
- **Not emitted in either dialect:** `[[…]]` attributes, C23 `typeof`/`typeof_unqual`, `constexpr`, `nullptr`, `_BitInt`, `#embed`. `<stdckdint.h>` is not part of glibc 2.43; GCC supplies it.

**Constructs that need C11 under `201710L`:**
- **Emitted declarations.** None of the C11 keywords appears in emitted code (`present` in `glibc.json`). `c11 minus c99` adds only declarations: `aligned_alloc`, `at_quick_exit`, `quick_exit`, `timespec_get`, `TIME_UTC`, `CMPLX*` as `__builtin_complex` (`complex.h:62-64`), and `static_assert` defined as `_Static_assert` (`assert.h:210`). `c17 minus c11` is empty.
- **Macro bodies.** These become live only when a program expands them:
  - `static_assert` expands to `_Static_assert` (`assert.h:210`).
  - `thread_local` expands to `_Thread_local` (`threads.h:34`, under `__STDC_VERSION__ <= 201710L`).
  - `__glibc_const_generic` is a `_Generic` (unused unless `_GNU_SOURCE`/`_ISOC23_SOURCE`, see above).
  - glibc's `<tgmath.h>` macros use `__builtin_tgmath` (21 macros, `tgmath.h:131…`; `__HAVE_BUILTIN_TGMATH` is `__GNUC_PREREQ (8, 0)`, `tgmath.h:53`).
  - `<math.h>`'s classification macros expand to builtins: `fpclassify`, `signbit`, `isfinite`, `isnormal`, `isnan`, `isinf` become `__builtin_fpclassify`, `__builtin_signbit`, `__builtin_isfinite`, `__builtin_isnormal`, `__builtin_isnan` and `__builtin_isinf_sign`; `HUGE_VAL`, `INFINITY` and `NAN` become `__builtin_huge_val`, `__builtin_inff` and `__builtin_nanf`.
  - `__MATH_TG` is the `sizeof` chain (`math.h:1058-1064`), because long double is not distinct from `_Float128` on aarch64.
- **GNU constructs in both dialects:** `__extension__ ({ … })` statement expressions in `__CPU_SET_S` and friends (`bits/cpu-set.h:58-99`), `__tobody` (`ctype.h:155`) and `IN6_IS_ADDR_*` (`netinet/in.h:437…`). `_FloatN` typedef names and `_Complex _FloatN` appear in `bits/floatn-common.h` and `math.h` macro bodies.

**Header code reached only when `__OPTIMIZE__` is defined** (`gnu17-O2 minus gnu17`, 127 lines; milestone 1 compiles at `-O0`, so none of it is seen):
- **`__USE_EXTERN_INLINES` bodies.** `features.h:552-556` sets `__USE_EXTERN_INLINES` only under `__OPTIMIZE__`. It brings `extern __inline __attribute__ ((__gnu_inline__))` bodies for:
  - `getc_unlocked`, `getchar`, `putchar`, `feof_unlocked`, `ferror_unlocked` and friends (`bits/stdio.h:29-135`), plus the `fread_unlocked`/`fwrite_unlocked` statement-expression macros (`bits/stdio.h:147-171`);
  - `atoi`, `atol`, `atoll` (`stdlib.h:484-496`) and `atof` (`bits/stdlib-float.h:24`);
  - `bsearch` (`bits/stdlib-bsearch.h:19`), `tolower`/`toupper` (`ctype.h:207-212`), `__cmsg_nxthdr` (`bits/socket.h:323-351`);
  - `pthread_equal` (`pthread.h:1344`), `thrd_equal` (`threads.h:123`), `btowc`/`wctob` (`wchar.h:369-379`).
- **Macros.** `libintl.h:96` defines `gettext`/`dgettext` as macros, and `dirent.h:228` defines `dirfd`. `netinet/in.h:415` maps `ntohs`/`htons` to `__bswap_*`, and `bits/stdio.h:144` adds the `fread_unlocked` family. These all use `__builtin_expect` and `__builtin_constant_p`.
- **`string.h`.** Its `__OPTIMIZE__` blocks (`string.h:103-362`) are C++-only (`__cplusplus` const overloads), so nothing changes in C.
- **Fortify.** `_FORTIFY_SOURCE` needs `__OPTIMIZE__ > 0` (`features.h:449-450`). With `-D_FORTIFY_SOURCE=3` at `-O0` the preprocessed output is identical to plain `-O0` (`gnu17-O0-fortify3 minus gnu17`: 0 lines), and gcc-16 prints no warning for `<stdio.h>`. At `-O2` it adds 734 lines: `__fortify_function` bodies with `__builtin___*_chk`, `__builtin_object_size`/`__builtin_dynamic_object_size` and `__REDIRECT` labels. Ubuntu's driver turns fortify on only at `-O2` and above (earlier note, section 0).

## 9. Known unknowns

- **Not GCC 15.2 on glibc.** Every "compiles under gnu23/gnu17" result is GCC 16.1 targeting Darwin, given the Linux identity with `-U`/`-D` and pointed at Ubuntu's glibc 2.43 headers.
  - GCC 15.2's diagnostics for these programs were not observed. The permerror set and C23 rules match the GCC 15 release (both default to `gnu23`), but GCC 16 may diagnose some constructs differently.
  - `long double` is 64-bit on this GCC. Only syntax was checked, but a `sizeof (long double)` test in a program would take Darwin's answer.
  - gcc-16's own `stdint.h`, `limits.h` and `tgmath.h` sit ahead of glibc's. On Ubuntu, GCC 15's `stdint.h` and `limits.h` wrap glibc's the same way and there is no GCC `tgmath.h`. No benchmark includes `<tgmath.h>`.
- **Clang identity for features.** VLA, K&R, `()`, implicit-int, implicit-declaration and extension counts are Apple clang 17's diagnostics, with `__clang__` and `__GNUC__` 4. Where a program branches on `__clang__`, those counts follow clang's branch. The reach counts (`gcc -E`) follow GCC's.
- **CMake read as text.** `enumerate.py` evaluates a fixed configuration and five assumed `check_*` results (1.1). `HAVE_RE_COMP` was assumed true without checking a libc6 binary. If it is false, plot2fig and archie drop out of the C count, which would be 250.
- **Assumed CMake defaults.**
  - `C_STANDARD N` was taken to mean `-std=gnuN`, which is CMake's default `C_EXTENSIONS ON`. CMake may omit the flag when the compiler's default already satisfies it (policy CMP0128 and the minimum version 3.20), which is irrelevant for GCC 15 because its default is newer than every pin.
  - CMake's include path for `-I.` (the build directory) was approximated by the source directory.
- **Grep-level items.**
  - Bitfields (a line regex on `gcc -E` output), `inline`/`restrict` keyword counts, include lists (all branches), `#pragma`/attribute/builtin lists and all of Part B are grep-level.
  - The zero-length-array regex had false positives (`x = a[0];`), so 4.1 uses clang's `-Wzero-length-array`, which found none.
  - The per-program "lines" double-counts headers shared between programs; the 1.1 totals do not.
- **Library-level C99/C11 not classified.** "Needs" counts language constructs and C99/C11 headers only. It does not count C99 library functions (`snprintf`, `strtoll`, `isnan` as a function, …), which a slice that links glibc gets anyway.
- **Unknown outcomes.** Whether sqlite3's and basicmath's reference outputs match within their tolerances when `long double` is binary128, or when it is double, was not checked; nothing was run. Whether the 46 gnu89 failures or the 37 gnu23 failures hide further errors behind the first ones is unknown. Errors were counted with `-fmax-errors=0`, but a parse error can mask later code.
- **Part B scope.** Branch tip, not the 15.2.0 tag. The `.x` files were not read. Nested functions and labels-as-values rely on clang parsing the file, so a test that clang rejects earlier may be missed.
- **Part C scope.** 47 roots, not glibc's whole closure. The analysis covers the dialect and optimisation axes only, not `_POSIX_C_SOURCE`/`_XOPEN_SOURCE` combinations.


