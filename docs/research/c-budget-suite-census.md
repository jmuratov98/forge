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

| Measure | Value |
|---|---|
| Test programs the fixed configuration defines under the scanned trees | 320 |
| C programs (every source `.c`) | **252** |
| C++ programs | 66 |
| Mixed C and C++ (not counted as C) | 2: CLAMR, 7zip-benchmark |
| Distinct program files reached (`.c` sources, `#include`d `.c`, local headers) | 2212 |
| Lines in those distinct `.c` files | **692,051** |
| Lines in those distinct local headers | 119,478 |
| Total lines of C (distinct `.c` + `.h`) | **811,529** |

| Suite directory | C programs |
|---|---|
| `MA/ClamAV` | 1 |
| `MA/JM` | 1 |
| `MA/SPASS` | 1 |
| `MA/sqlite3` | 1 |
| `MS/ASCI_Purple` | 1 |
| `MS/ASC_Sequoia` | 3 |
| `MS/BitBench` | 4 |
| `MS/DOE-ProxyApps-C` | 7 |
| `MS/Fhourstones` | 1 |
| `MS/Fhourstones-3.1` | 1 |
| `MS/FreeBench` | 7 |
| `MS/MallocBench` | 3 |
| `MS/McCat` | 10 |
| `MS/MiBench` | 17 |
| `MS/NPB-serial` | 1 |
| `MS/Olden` | 10 |
| `MS/Prolangs-C` | 16 |
| `MS/Ptrdist` | 5 |
| `MS/Rodinia` | 4 |
| `MS/SciMark2-C` | 1 |
| `MS/TSVC` | 36 |
| `MS/Trimaran` | 6 |
| `MS/VersaBench` | 5 |
| `MS/llubenchmark` | 1 |
| `MS/mafft` | 1 |
| `MS/mediabench` | 6 |
| `MS/nbench` | 1 |
| `MS/sim` | 1 |
| `SS/BenchmarkGame` | 8 |
| `SS/CoyoteBench` | 3 |
| `SS/Dhrystone` | 2 |
| `SS/Linpack` | 1 |
| `SS/McGill` | 4 |
| `SS/Misc` | 27 |
| `SS/Polybench` | 30 |
| `SS/Shootout` | 14 |
| `SS/Stanford` | 11 |

"Program" means one test executable. A `llvm_multisource()` call is one program. A `llvm_singlesource()` directory gives one program per source file (`cmake/modules/SingleMultiSource.cmake`, `llvm_singlesource` and `llvm_multisource`). The counts are for the configuration in the method paragraph. Programs that CMake adds only on other targets are not included, for example `aarch64-init-cpu-features.c` in `SingleSource/Benchmarks/Misc`, which is added only when `__init_cpu_features` links (`HAS_AARCH64_FMV`). Five `check_*` results had to be assumed for Ubuntu 26.04 arm64 with GCC; they are listed in `enumerate.py`'s `TRUTH` table. The two that change membership are:
- `HAVE_SGTTY_INCLUDE` is true, because libc6-dev 2.43 ships `/usr/include/sgtty.h`. This adds office-ispell.
- `HAVE_RE_COMP` is true, because glibc's libc exports `re_comp`. This adds plot2fig and archie. That one was not verified against a libc6 binary (section 9).

Line counts are physical lines (`\n` count). The totals count each distinct file once, because Polybench's 30 programs, for example, share `utilities/polybench.h`. Per-program counts in section 3 include every file that program reaches.

### 1.2 CTMark

`CTMark/CMakeLists.txt` adds eleven subdirectories. Each `CTMark/<name>` entry is a git symlink (mode `120000`) into the MultiSource tree. CTMark therefore builds the very same `CMakeLists.txt`, sources and flags as the MultiSource entry; it is a subset, not a copy. Six of the eleven are C:

| CTMark entry | Symlink target | Test target | `.c` files | Lines (.c + local .h) | std the suite passes |
|---|---|---|---|---|---|
| `CTMark/consumer-typeset` | `../MultiSource/Benchmarks/MiBench/consumer-typeset` | `consumer-typeset` | 51 | 42,454 | c99 (CFLAGS) |
| `CTMark/mafft` | `../MultiSource/Benchmarks/mafft` | `pairlocalalign` | 29 | 38,498 | gnu17 (C_STANDARD 17) |
| `CTMark/ClamAV` | `../MultiSource/Applications/ClamAV` | `clamscan` | 99 | 81,762 | gnu17 (C_STANDARD 17) |
| `CTMark/SPASS` | `../MultiSource/Applications/SPASS` | `SPASS` | 51 | 82,077 | gnu17 (C_STANDARD 17) |
| `CTMark/sqlite3` | `../MultiSource/Applications/sqlite3` | `sqlite3` | 2 | 89,311 | gnu17 (C_STANDARD 17) |
| `CTMark/lencod` | `../MultiSource/Applications/JM/lencod` | `lencod` | 55 | 63,262 | gnu17 (C_STANDARD 17) |

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

| Flag | Programs | Which (up to 12) |
|---|---|---|
| `link -lm` | 200 |  |
| `std not pinned (compiler default)` | 177 | fasta, fannkuch, n-body, nsieve-bits, partialsums, puzzle, recursive, spectral-norm, almabench, huffbench, lpbench, linpack-pc … |
| `-Wno-error=incompatible-pointer-types` | 69 | correlation, covariance, gemm, gemver, gesummv, symm, syr2k, syrk, trmm, 2mm, 3mm, atax … |
| `-Wno-implicit-int` | 50 | dry, fldry, ReedSolomon, evalloop, fbench, ffbench, flops-1, flops-2, flops-3, flops-4, flops-5, flops-6 … |
| `std gnu99 via C_STANDARD` | 38 | ControlFlow-dbl, ControlFlow-flt, ControlLoops-dbl, ControlLoops-flt, CrossingThresholds-dbl, CrossingThresholds-flt, Equivalencing-dbl, Equivalencing-flt, Expansion-dbl, Expansion-flt, GlobalDataFlow-dbl, GlobalDataFlow-flt … |
| `std gnu17 via C_STANDARD` | 33 | dry, fldry, flops, Shootout-methcall, Shootout-objinst, smg2000, five11, fhourstones, gs, cfrac, imp, trie … |
| `-ffp-contract=off` | 15 | linpack-pc, correlation, covariance, gemver, gesummv, symm, trmm, 2mm, 3mm, atax, bicg, gramschmidt … |
| `-Wno-implicit-function-declaration` | 9 | gs, mybison, plot2fig, archie, anagram, yacr2, nbench, network-patricia, office-ispell |
| `-fcommon` | 8 | IRSmk, bh, timberwolfmc, compiler, loader, simulator, miniAMR, lencod |
| `-Wno-int-conversion` | 6 | mybison, assembler, football, unix-smail, beamformer, Recurrences-flt |
| `std c99 via -std= in CFLAGS` | 2 | CoMD, consumer-typeset |
| `std gnu89 via C_STANDARD` | 2 | espresso, cdecl |
| `-Wno-incompatible-function-pointer-types` | 1 | unix-tbl |
| `-fno-strict-aliasing` | 1 | SPASS |

### 3.2 Reference outputs and tolerances

Every one of the 252 C programs has a reference output, and none sets `NO_REFERENCE_OUTPUT`. 52 also set `HASH_PROGRAM_OUTPUT`. fpcmp tolerances appear in 3.3's last column: `r` is `FP_TOLERANCE`, `a` is `FP_ABSTOLERANCE`, "exact" means neither is set. The 30 Polybench programs pass `-DFP_ABSTOLERANCE=1e-5` with `add_definitions`. That is a macro for the program's own comparison code (for example `adi.c:202` `double AbsTolerance = FP_ABSTOLERANCE;`), not an fpcmp option; they are verified by hash.

### 3.3 Table

Directories are abbreviated: `SS` = `SingleSource/Benchmarks`, `MS` = `MultiSource/Benchmarks`, `MA` = `MultiSource/Applications`. CTMark's six are in bold. `-DNDEBUG` (global) is omitted. "Lines" is `.c` plus local headers reached by that program.

| # | Program | Directory | `.c` | Lines | std | `-D`/`-U`/`-I` | `-W`/`-f`/other | Link | Reference output; fpcmp |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **clamscan** (CTMark ClamAV) | `MA/ClamAV` | 99 | 81,762 | gnu17 (C_STANDARD 17) | `-DHAVE_CONFIG_H` `-DDONT_LOCK_DBDIRS` `-DC_LINUX` `-DFPU_WORDS_BIGENDIAN=0` `-DWORDS_BIGENDIAN=0` + 2 `-I` | `-Wno-error=incompatible-pointer-types` `target_link_libraries(${Intl_LIBRARIES}) after find_package(Intl): empty on glibc, whose libc holds libintl` | — | yes; exact |
| 2 | **lencod** (CTMark lencod) | `MA/JM/lencod` | 55 | 63,262 | gnu17 (C_STANDARD 17) | `-D__USE_LARGEFILE64` `-D_FILE_OFFSET_BITS=64` | `-fcommon` | -lm | yes; r 0.025 |
| 3 | **SPASS** (CTMark SPASS) | `MA/SPASS` | 51 | 82,077 | gnu17 (C_STANDARD 17) | `-DCLOCK_NO_TIMING` | `-fno-strict-aliasing` | -lm | yes; hash |
| 4 | **sqlite3** (CTMark sqlite3) | `MA/sqlite3` | 2 | 89,311 | gnu17 (C_STANDARD 17) | `-DSTDC_HEADERS=1` `-DHAVE_SYS_TYPES_H=1` `-DHAVE_SYS_STAT_H=1` `-DHAVE_STDLIB_H=1` `-DHAVE_STRING_H=1` `-DHAVE_MEMORY_H=1` `-DHAVE_STRINGS_H=1` `-DHAVE_INTTYPES_H=1` `-DHAVE_STDINT_H=1` `-DHAVE_UNISTD_H=1` `-DSQLITE_OMIT_LOAD_EXTENSION=1` `-DSQLITE_THREADSAFE=0` + 1 `-I` | — | — | yes; r 1.0e-9 |
| 5 | smg2000 | `MS/ASCI_Purple/SMG2000` | 53 | 27,907 | gnu17 (C_STANDARD 17) | `-D_POSIX_SOURCE` `-DHYPRE_TIMING` `-DHYPRE_SEQUENTIAL` + 1 `-I` | — | -lm | yes; exact |
| 6 | AMGmk | `MS/ASC_Sequoia/AMGmk` | 8 | 3,127 | — | — | — | -lm | yes; exact |
| 7 | CrystalMk | `MS/ASC_Sequoia/CrystalMk` | 6 | 416 | — | — | — | -lm | yes; exact |
| 8 | IRSmk | `MS/ASC_Sequoia/IRSmk` | 3 | 454 | — | — | `-fcommon` | -lm | yes; exact |
| 9 | drop3 | `MS/BitBench/drop3` | 1 | 104 | — | — | — | — | yes; exact |
| 10 | five11 | `MS/BitBench/five11` | 1 | 195 | gnu17 (C_STANDARD 17) | — | — | — | yes; exact |
| 11 | uudecode | `MS/BitBench/uudecode` | 1 | 177 | — | — | `-Wno-implicit-int` | — | yes; exact |
| 12 | uuencode | `MS/BitBench/uuencode` | 1 | 201 | — | — | `-Wno-implicit-int` | — | yes; exact |
| 13 | CoMD | `MS/DOE-ProxyApps-C/CoMD` | 14 | 5,666 | c99 (CFLAGS) | `-DDOUBLE` | — | -lm | yes; exact |
| 14 | PathFinder | `MS/DOE-ProxyApps-C/Pathfinder` | 15 | 5,634 | gnu17 (C_STANDARD 17) | — | — | -lm | yes; exact |
| 15 | rsbench | `MS/DOE-ProxyApps-C/RSBench` | 7 | 1,169 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; exact |
| 16 | SimpleMOC | `MS/DOE-ProxyApps-C/SimpleMOC` | 11 | 3,952 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; exact |
| 17 | XSBench | `MS/DOE-ProxyApps-C/XSBench` | 6 | 1,339 | — | `-DVERIFICATION` | — | -lm | yes; exact |
| 18 | miniAMR | `MS/DOE-ProxyApps-C/miniAMR` | 14 | 4,070 | — | — + 1 `-I` | `-fcommon` | -lm | yes; exact |
| 19 | miniGMG | `MS/DOE-ProxyApps-C/miniGMG` | 6 | 3,797 | — | `-D__PRINT_NORM` | — | -lm | yes; a 0.00000001 |
| 20 | fhourstones | `MS/Fhourstones` | 4 | 514 | gnu17 (C_STANDARD 17) | `-DUNIX` `-DTRANSIZE=1050011` `-DPROBES=8` `-DREPORTPLY=8` | — | — | yes; exact |
| 21 | fhourstones3.1 | `MS/Fhourstones-3.1` | 1 | 451 | — | — | — | — | yes; exact |
| 22 | analyzer | `MS/FreeBench/analyzer` | 5 | 922 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | — | yes; exact |
| 23 | distray | `MS/FreeBench/distray` | 1 | 447 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | -lm | yes; hash |
| 24 | fourinarow | `MS/FreeBench/fourinarow` | 1 | 702 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | — | yes; exact |
| 25 | mason | `MS/FreeBench/mason` | 1 | 385 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | — | yes; exact |
| 26 | neural | `MS/FreeBench/neural` | 1 | 785 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | -lm | yes; exact |
| 27 | pcompress2 | `MS/FreeBench/pcompress2` | 5 | 903 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | — | yes; exact |
| 28 | pifft | `MS/FreeBench/pifft` | 2 | 4,185 | — | `-DVERSION="1.00"` `-DCOMPDATE="today"` `-DCFLAGS=""` `-DHOSTNAME="thishost"` | — | -lm | yes; exact |
| 29 | cfrac | `MS/MallocBench/cfrac` | 28 | 4,074 | gnu17 (C_STANDARD 17) | `-DNOMEMOPT` | — | -lm | yes; exact |
| 30 | espresso | `MS/MallocBench/espresso` | 41 | 14,936 | gnu89 (C_STANDARD 90) | `-DNOMEMOPT` | — | — | yes; exact |
| 31 | gs | `MS/MallocBench/gs` | 64 | 22,989 | gnu17 (C_STANDARD 17) | `-DNOMEMOPT` `-DGS_LIB_DEFAULT=".:./fonts"` `-DNOPRIVATE` | `-Wno-implicit-function-declaration` `-Wno-implicit-int` | -lm | yes; exact |
| 32 | qbsort | `MS/McCat/01-qbsort` | 3 | 374 | — | — | — | -lm | yes; hash |
| 33 | testtrie | `MS/McCat/03-testtrie` | 3 | 339 | — | — | — | -lm | yes; exact |
| 34 | bisect | `MS/McCat/04-bisect` | 3 | 463 | — | — | — | -lm | yes; r 0.001 |
| 35 | eks | `MS/McCat/05-eks` | 7 | 1,178 | — | — | — | -lm | yes; exact |
| 36 | main | `MS/McCat/08-main` | 4 | 1,210 | — | — | — | -lm | yes; hash |
| 37 | vor | `MS/McCat/09-vor` | 6 | 1,401 | — | — | — | -lm | yes; exact |
| 38 | iotest | `MS/McCat/12-IOtest` | 4 | 418 | — | — | — | — | yes; exact |
| 39 | trie | `MS/McCat/15-trie` | 1 | 356 | gnu17 (C_STANDARD 17) | — | — | -lm | yes; exact |
| 40 | bintr | `MS/McCat/17-bintr` | 2 | 456 | — | — | — | -lm | yes; exact |
| 41 | imp | `MS/McCat/18-imp` | 4 | 2,658 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` | -lm | yes; exact |
| 42 | automotive-basicmath | `MS/MiBench/automotive-basicmath` | 4 | 496 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 43 | automotive-bitcount | `MS/MiBench/automotive-bitcount` | 9 | 944 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 44 | automotive-susan | `MS/MiBench/automotive-susan` | 1 | 2,125 | — | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 45 | consumer-jpeg | `MS/MiBench/consumer-jpeg` | 54 | 26,098 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 46 | consumer-lame | `MS/MiBench/consumer-lame` | 33 | 21,752 | — | `-DHAVEMPGLIB` `-DLAMEPARSE` `-D__NO_MATH_INLINES` `-DLAMESNDFILE` | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 47 | **consumer-typeset** (CTMark consumer-typeset) | `MS/MiBench/consumer-typeset` | 51 | 42,454 | c99 (CFLAGS) | `-DOS_UNIX=1` `-DOS_DOS=0` `-DOS_MAC=0` `-DDB_FIX=0` `-DUSE_STAT=1` `-DSAFE_DFT=0` `-DCOLLATE=1` `-DLIB_DIR="lout.lib"` `-DFONT_DIR="font"` `-DMAPS_DIR="maps"` `-DINCL_DIR="include"` `-DDATA_DIR="data"` `-DHYPH_DIR="hyph"` `-DLOCALE_DIR="locale"` `-DCHAR_IN=1` `-DCHAR_OUT=0` `-DLOCALE_ON=1` `-DASSERT_ON=1` `-DDEBUG_ON=0` `-DPDF_COMPRESSION=0` `-D_FORTIFY_SOURCE=0` | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 48 | network-dijkstra | `MS/MiBench/network-dijkstra` | 1 | 175 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 49 | network-patricia | `MS/MiBench/network-patricia` | 2 | 600 | — | — | `-Wno-implicit-function-declaration` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 50 | office-ispell | `MS/MiBench/office-ispell` | 12 | 10,532 | gnu17 (C_STANDARD 17) | `-Dconst=` | `-Wno-implicit-function-declaration` `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 51 | office-stringsearch | `MS/MiBench/office-stringsearch` | 4 | 3,037 | — | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 52 | security-blowfish | `MS/MiBench/security-blowfish` | 7 | 1,915 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 53 | security-rijndael | `MS/MiBench/security-rijndael` | 2 | 1,779 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 54 | security-sha | `MS/MiBench/security-sha` | 2 | 276 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 55 | telecomm-CRC32 | `MS/MiBench/telecomm-CRC32` | 1 | 286 | — | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 56 | telecomm-fft | `MS/MiBench/telecomm-FFT` | 3 | 623 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; a 0.00001, hash, in-program FP_ABSTOLERANCE=1e-5 |
| 57 | telecomm-adpcm | `MS/MiBench/telecomm-adpcm` | 2 | 302 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 58 | telecomm-gsm | `MS/MiBench/telecomm-gsm` | 23 | 6,040 | — | `-DSTUPID_COMPILER` `-DNeedFunctionPrototypes=1` `-DSASR` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash |
| 59 | is | `MS/NPB-serial/is` | 1 | 779 | — | — | — | — | yes; exact |
| 60 | bh | `MS/Olden/bh` | 4 | 2,077 | gnu17 (C_STANDARD 17) | `-DTORONTO` | `-Wno-implicit-int` `-fcommon` | -lm | yes; exact |
| 61 | bisort | `MS/Olden/bisort` | 2 | 350 | gnu17 (C_STANDARD 17) | `-DTORONTO` | — | -lm | yes; exact |
| 62 | em3d | `MS/Olden/em3d` | 5 | 688 | — | `-DTORONTO` | — | — | yes; exact |
| 63 | health | `MS/Olden/health` | 4 | 504 | — | `-DTORONTO` | — | -lm | yes; r 0.001 |
| 64 | mst | `MS/Olden/mst` | 4 | 428 | — | `-DTORONTO` | — | — | yes; exact |
| 65 | perimeter | `MS/Olden/perimeter` | 3 | 484 | — | `-DTORONTO` | — | — | yes; exact |
| 66 | power | `MS/Olden/power` | 3 | 622 | — | `-DTORONTO` | — | -lm | yes; r 0.00001 |
| 67 | treeadd | `MS/Olden/treeadd` | 3 | 245 | — | `-DTORONTO` | — | — | yes; exact |
| 68 | tsp | `MS/Olden/tsp` | 4 | 582 | — | `-DTORONTO` | — | -lm | yes; exact |
| 69 | voronoi | `MS/Olden/voronoi` | 4 | 1,151 | gnu17 (C_STANDARD 17) | `-DTORONTO` | — | -lm | yes; hash |
| 70 | timberwolfmc | `MS/Prolangs-C/TimberWolfMC` | 109 | 24,958 | gnu17 (C_STANDARD 17) | — | `-fcommon` `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 71 | agrep | `MS/Prolangs-C/agrep` | 13 | 3,977 | — | — | `-Wno-implicit-int` | — | yes; hash |
| 72 | allroots | `MS/Prolangs-C/allroots` | 3 | 205 | — | — | — | -lm | yes; exact |
| 73 | archie | `MS/Prolangs-C/archie-client` | 14 | 5,500 | — | — | `-Wno-implicit-function-declaration` | — | yes; exact |
| 74 | assembler | `MS/Prolangs-C/assembler` | 12 | 3,171 | gnu17 (C_STANDARD 17) | — | `-Wno-int-conversion` | -lm | yes; exact |
| 75 | mybison | `MS/Prolangs-C/bison` | 18 | 8,339 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-function-declaration` `-Wno-implicit-int` `-Wno-int-conversion` | — | yes; exact |
| 76 | cdecl | `MS/Prolangs-C/cdecl` | 1 | 3,826 | gnu89 (C_STANDARD 90) | — | — | — | yes; exact |
| 77 | compiler | `MS/Prolangs-C/compiler` | 7 | 2,369 | — | — | `-fcommon` | — | yes; exact |
| 78 | fixoutput | `MS/Prolangs-C/fixoutput` | 2 | 460 | — | — | `-Wno-implicit-int` | — | yes; exact |
| 79 | football | `MS/Prolangs-C/football` | 4 | 2,257 | — | — | `-Wno-int-conversion` | — | yes; exact |
| 80 | gnugo | `MS/Prolangs-C/gnugo` | 26 | 2,941 | — | — | — | — | yes; hash |
| 81 | loader | `MS/Prolangs-C/loader` | 8 | 1,452 | gnu17 (C_STANDARD 17) | — | `-fcommon` | -lm | yes; exact |
| 82 | plot2fig | `MS/Prolangs-C/plot2fig` | 21 | 1,538 | — | — | `-Wno-implicit-function-declaration` | -lm | yes; exact |
| 83 | simulator | `MS/Prolangs-C/simulator` | 13 | 4,477 | gnu17 (C_STANDARD 17) | — | `-fcommon` | -lm | yes; exact |
| 84 | unix-smail | `MS/Prolangs-C/unix-smail` | 11 | 3,527 | gnu17 (C_STANDARD 17) | — | `-Wno-int-conversion` | — | yes; exact |
| 85 | unix-tbl | `MS/Prolangs-C/unix-tbl` | 22 | 2,829 | — | — | `-Wno-implicit-int` `-Wno-incompatible-function-pointer-types` | — | yes; exact |
| 86 | anagram | `MS/Ptrdist/anagram` | 1 | 657 | — | — | `-Wno-implicit-function-declaration` | — | yes; exact |
| 87 | bc | `MS/Ptrdist/bc` | 9 | 7,289 | — | — | `-Wno-implicit-int` | — | yes; hash |
| 88 | ft | `MS/Ptrdist/ft` | 5 | 1,666 | — | — | `-Wno-implicit-int` | — | yes; hash |
| 89 | ks | `MS/Ptrdist/ks` | 2 | 783 | — | — | — | — | yes; exact |
| 90 | yacr2 | `MS/Ptrdist/yacr2` | 7 | 3,987 | — | `-DTODD` | `-Wno-implicit-function-declaration` | — | yes; hash |
| 91 | backprop | `MS/Rodinia/backprop` | 3 | 300 | — | — + 1 `-I` | — | -lm | yes; a 0.00001 |
| 92 | hotspot | `MS/Rodinia/hotspot` | 3 | 280 | — | — + 1 `-I` | — | — | yes; a 0.00001 |
| 93 | pathfinder | `MS/Rodinia/pathfinder` | 3 | 142 | — | — + 1 `-I` | — | — | yes; hash |
| 94 | srad | `MS/Rodinia/srad` | 3 | 425 | — | `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` | -lm | yes; a 0.00001 |
| 95 | scimark2 | `MS/SciMark2-C` | 10 | 1,220 | — | — | — | -lm | yes; exact |
| 96 | ControlFlow-dbl | `MS/TSVC/ControlFlow-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 97 | ControlFlow-flt | `MS/TSVC/ControlFlow-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 98 | ControlLoops-dbl | `MS/TSVC/ControlLoops-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 99 | ControlLoops-flt | `MS/TSVC/ControlLoops-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 100 | CrossingThresholds-dbl | `MS/TSVC/CrossingThresholds-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 101 | CrossingThresholds-flt | `MS/TSVC/CrossingThresholds-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 102 | Equivalencing-dbl | `MS/TSVC/Equivalencing-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 103 | Equivalencing-flt | `MS/TSVC/Equivalencing-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 104 | Expansion-dbl | `MS/TSVC/Expansion-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 105 | Expansion-flt | `MS/TSVC/Expansion-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 106 | GlobalDataFlow-dbl | `MS/TSVC/GlobalDataFlow-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 107 | GlobalDataFlow-flt | `MS/TSVC/GlobalDataFlow-flt` | 2 | 5,861 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 108 | IndirectAddressing-dbl | `MS/TSVC/IndirectAddressing-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 109 | IndirectAddressing-flt | `MS/TSVC/IndirectAddressing-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 110 | InductionVariable-dbl | `MS/TSVC/InductionVariable-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 111 | InductionVariable-flt | `MS/TSVC/InductionVariable-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 112 | LinearDependence-dbl | `MS/TSVC/LinearDependence-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 113 | LinearDependence-flt | `MS/TSVC/LinearDependence-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 114 | LoopRerolling-dbl | `MS/TSVC/LoopRerolling-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 115 | LoopRerolling-flt | `MS/TSVC/LoopRerolling-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 116 | LoopRestructuring-dbl | `MS/TSVC/LoopRestructuring-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 117 | LoopRestructuring-flt | `MS/TSVC/LoopRestructuring-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 118 | NodeSplitting-dbl | `MS/TSVC/NodeSplitting-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 119 | NodeSplitting-flt | `MS/TSVC/NodeSplitting-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 120 | Packing-dbl | `MS/TSVC/Packing-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 121 | Packing-flt | `MS/TSVC/Packing-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 122 | Recurrences-dbl | `MS/TSVC/Recurrences-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 123 | Recurrences-flt | `MS/TSVC/Recurrences-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | `-Wno-int-conversion` | -lm | yes; a 0.0 |
| 124 | Reductions-dbl | `MS/TSVC/Reductions-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 125 | Reductions-flt | `MS/TSVC/Reductions-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 126 | Searching-dbl | `MS/TSVC/Searching-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 127 | Searching-flt | `MS/TSVC/Searching-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 128 | StatementReordering-dbl | `MS/TSVC/StatementReordering-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 129 | StatementReordering-flt | `MS/TSVC/StatementReordering-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 130 | Symbolics-dbl | `MS/TSVC/Symbolics-dbl` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 131 | Symbolics-flt | `MS/TSVC/Symbolics-flt` | 2 | 5,860 | gnu99 (C_STANDARD 99) | — | — | -lm | yes; a 0.0 |
| 132 | enc-3des | `MS/Trimaran/enc-3des` | 1 | 644 | — | — | — | — | yes; exact |
| 133 | enc-md5 | `MS/Trimaran/enc-md5` | 1 | 317 | — | — | — | — | yes; exact |
| 134 | enc-pc1 | `MS/Trimaran/enc-pc1` | 1 | 335 | — | — | `-Wno-implicit-int` | — | yes; exact |
| 135 | enc-rc4 | `MS/Trimaran/enc-rc4` | 1 | 166 | — | — | — | — | yes; exact |
| 136 | netbench-crc | `MS/Trimaran/netbench-crc` | 2 | 10,347 | gnu17 (C_STANDARD 17) | — | — | — | yes; exact |
| 137 | netbench-url | `MS/Trimaran/netbench-url` | 4 | 10,950 | — | — | — | — | yes; exact |
| 138 | 8b10b | `MS/VersaBench/8b10b` | 3 | 480 | — | — | — | — | yes; exact |
| 139 | beamformer | `MS/VersaBench/beamformer` | 1 | 691 | — | — | `-Wno-int-conversion` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 140 | bmm | `MS/VersaBench/bmm` | 1 | 246 | — | — | — | — | yes; exact |
| 141 | dbms | `MS/VersaBench/dbms` | 41 | 6,925 | — | — | — | -lm | yes; exact |
| 142 | ecbdes | `MS/VersaBench/ecbdes` | 4 | 2,126 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` | — | yes; exact |
| 143 | llu | `MS/llubenchmark` | 1 | 191 | — | — | — | — | yes; exact |
| 144 | **pairlocalalign** (CTMark mafft) | `MS/mafft` | 29 | 38,498 | gnu17 (C_STANDARD 17) | `-DLLVM` | — | -lm | yes; hash |
| 145 | rawcaudio | `MS/mediabench/adpcm/rawcaudio` | 2 | 302 | — | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | — | yes; exact |
| 146 | rawdaudio | `MS/mediabench/adpcm/rawdaudio` | 2 | 302 | — | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | — | yes; hash |
| 147 | encode | `MS/mediabench/g721/g721encode` | 6 | 1,595 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` `-Wno-error=incompatible-pointer-types` | — | yes; exact |
| 148 | toast | `MS/mediabench/gsm/toast` | 23 | 6,039 | — | `-DNeedFunctionPrototypes=1` `-DSASR` | `-Wno-error=incompatible-pointer-types` | — | yes; exact |
| 149 | cjpeg | `MS/mediabench/jpeg/jpeg-6a` | 54 | 26,865 | — | — | `-Wno-error=incompatible-pointer-types` | — | yes; exact |
| 150 | mpeg2decode | `MS/mediabench/mpeg2/mpeg2dec` | 16 | 9,844 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 151 | nbench | `MS/nbench` | 5 | 9,645 | gnu17 (C_STANDARD 17) | `-DBASE_ITERATIONS=25` | `-Wno-implicit-function-declaration` | -lm | yes; exact |
| 152 | sim | `MS/sim` | 1 | 1,592 | gnu17 (C_STANDARD 17) | `-DUNIX` | `-Wno-implicit-int` | — | yes; exact |
| 153 | fannkuch | `SS/BenchmarkGame` | 1 | 104 | — | — | — | -lm | yes; exact |
| 154 | n-body | `SS/BenchmarkGame` | 1 | 141 | — | — | — | -lm | yes; exact |
| 155 | nsieve-bits | `SS/BenchmarkGame` | 1 | 35 | — | — | — | -lm | yes; exact |
| 156 | partialsums | `SS/BenchmarkGame` | 1 | 67 | — | — | — | -lm | yes; exact |
| 157 | puzzle | `SS/BenchmarkGame` | 1 | 84 | — | — | — | -lm | yes; exact |
| 158 | recursive | `SS/BenchmarkGame` | 1 | 54 | — | — | — | -lm | yes; exact |
| 159 | spectral-norm | `SS/BenchmarkGame` | 1 | 52 | — | — | — | -lm | yes; exact |
| 160 | fasta | `SS/BenchmarkGame/Large` | 1 | 136 | — | — | — | -lm | yes; hash |
| 161 | almabench | `SS/CoyoteBench` | 1 | 390 | — | — | — | -lm | yes; exact |
| 162 | huffbench | `SS/CoyoteBench` | 1 | 491 | — | — | — | -lm | yes; exact |
| 163 | lpbench | `SS/CoyoteBench` | 1 | 414 | — | — | — | -lm | yes; exact |
| 164 | dry | `SS/Dhrystone` | 1 | 550 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` | -lm | yes; exact |
| 165 | fldry | `SS/Dhrystone` | 1 | 560 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` | -lm | yes; exact |
| 166 | linpack-pc | `SS/Linpack` | 1 | 1,226 | — | `-DFMA_DISABLED=1` | `-ffp-contract=off` | -lm | yes; r 0.0001 |
| 167 | chomp | `SS/McGill` | 1 | 429 | — | — | — | -lm | yes; r 0.001 |
| 168 | exptree | `SS/McGill` | 1 | 389 | — | — | — | -lm | yes; r 0.001 |
| 169 | misr | `SS/McGill` | 1 | 291 | — | — | — | -lm | yes; r 0.001 |
| 170 | queens | `SS/McGill` | 1 | 370 | — | — | — | -lm | yes; r 0.001 |
| 171 | ReedSolomon | `SS/Misc` | 1 | 447 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 172 | dt | `SS/Misc` | 1 | 51 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 173 | evalloop | `SS/Misc` | 1 | 121 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 174 | fbench | `SS/Misc` | 1 | 829 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 175 | ffbench | `SS/Misc` | 1 | 361 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 176 | flops | `SS/Misc` | 1 | 1,180 | gnu17 (C_STANDARD 17) | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 177 | flops-1 | `SS/Misc` | 1 | 269 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 178 | flops-2 | `SS/Misc` | 1 | 275 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 179 | flops-3 | `SS/Misc` | 1 | 269 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 180 | flops-4 | `SS/Misc` | 1 | 271 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 181 | flops-5 | `SS/Misc` | 1 | 268 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 182 | flops-6 | `SS/Misc` | 1 | 271 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 183 | flops-7 | `SS/Misc` | 1 | 277 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 184 | flops-8 | `SS/Misc` | 1 | 273 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 185 | fp-convert | `SS/Misc` | 1 | 45 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 186 | himenobmtxpa | `SS/Misc` | 1 | 317 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 187 | lowercase | `SS/Misc` | 1 | 58 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 188 | mandel | `SS/Misc` | 1 | 48 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 189 | mandel-2 | `SS/Misc` | 1 | 28 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 190 | matmul_f64_4x4 | `SS/Misc` | 1 | 72 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 191 | oourafft | `SS/Misc` | 1 | 763 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 192 | perlin | `SS/Misc` | 1 | 80 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 193 | pi | `SS/Misc` | 1 | 64 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 194 | revertBits | `SS/Misc` | 1 | 67 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 195 | richards_benchmark | `SS/Misc` | 1 | 408 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 196 | salsa20 | `SS/Misc` | 1 | 75 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 197 | whetstone | `SS/Misc` | 1 | 439 | — | — | `-Wno-implicit-int` | -lm | yes; r 0.001 |
| 198 | correlation | `SS/Polybench/datamining/correlation` | 1 | 1,244 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 199 | covariance | `SS/Polybench/datamining/covariance` | 1 | 1,188 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 200 | gemm | `SS/Polybench/linear-algebra/blas/gemm` | 1 | 1,204 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 201 | gemver | `SS/Polybench/linear-algebra/blas/gemver` | 1 | 1,242 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 202 | gesummv | `SS/Polybench/linear-algebra/blas/gesummv` | 1 | 1,176 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 203 | symm | `SS/Polybench/linear-algebra/blas/symm` | 1 | 1,206 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 204 | syr2k | `SS/Polybench/linear-algebra/blas/syr2k` | 1 | 1,198 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 205 | syrk | `SS/Polybench/linear-algebra/blas/syrk` | 1 | 1,179 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 206 | trmm | `SS/Polybench/linear-algebra/blas/trmm` | 1 | 1,179 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 207 | 2mm | `SS/Polybench/linear-algebra/kernels/2mm` | 1 | 1,230 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 208 | 3mm | `SS/Polybench/linear-algebra/kernels/3mm` | 1 | 1,243 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 209 | atax | `SS/Polybench/linear-algebra/kernels/atax` | 1 | 1,162 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 210 | bicg | `SS/Polybench/linear-algebra/kernels/bicg` | 1 | 1,190 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 211 | doitgen | `SS/Polybench/linear-algebra/kernels/doitgen` | 1 | 1,178 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 212 | mvt | `SS/Polybench/linear-algebra/kernels/mvt` | 1 | 1,189 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 213 | cholesky | `SS/Polybench/linear-algebra/solvers/cholesky` | 1 | 1,186 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 214 | durbin | `SS/Polybench/linear-algebra/solvers/durbin` | 1 | 1,175 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 215 | gramschmidt | `SS/Polybench/linear-algebra/solvers/gramschmidt` | 1 | 1,219 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 216 | lu | `SS/Polybench/linear-algebra/solvers/lu` | 1 | 1,162 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 217 | ludcmp | `SS/Polybench/linear-algebra/solvers/ludcmp` | 1 | 1,242 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 218 | trisolv | `SS/Polybench/linear-algebra/solvers/trisolv` | 1 | 1,148 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 219 | deriche | `SS/Polybench/medley/deriche` | 1 | 1,306 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 220 | floyd-warshall | `SS/Polybench/medley/floyd-warshall` | 1 | 1,132 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 221 | nussinov | `SS/Polybench/medley/nussinov` | 1 | 1,176 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 222 | adi | `SS/Polybench/stencils/adi` | 1 | 1,241 | — | `-DPOLYBENCH_DUMP_ARRAYS` `-DFMA_DISABLED=1` + 1 `-I` | `-ffp-contract=off` `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 223 | fdtd-2d | `SS/Polybench/stencils/fdtd-2d` | 1 | 1,219 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 224 | heat-3d | `SS/Polybench/stencils/heat-3d` | 1 | 1,182 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 225 | jacobi-1d | `SS/Polybench/stencils/jacobi-1d` | 1 | 1,144 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 226 | jacobi-2d | `SS/Polybench/stencils/jacobi-2d` | 1 | 1,153 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 227 | seidel-2d | `SS/Polybench/stencils/seidel-2d` | 1 | 1,139 | — | `-DPOLYBENCH_DUMP_ARRAYS` + 1 `-I` | `-Wno-error=incompatible-pointer-types` | -lm | yes; hash, in-program FP_ABSTOLERANCE=1e-5 |
| 228 | Shootout-ackermann | `SS/Shootout` | 1 | 23 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 229 | Shootout-ary3 | `SS/Shootout` | 1 | 45 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 230 | Shootout-fib2 | `SS/Shootout` | 1 | 27 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 231 | Shootout-hash | `SS/Shootout` | 1 | 219 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 232 | Shootout-heapsort | `SS/Shootout` | 1 | 81 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 233 | Shootout-hello | `SS/Shootout` | 1 | 12 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 234 | Shootout-lists | `SS/Shootout` | 1 | 231 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 235 | Shootout-matrix | `SS/Shootout` | 1 | 71 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 236 | Shootout-methcall | `SS/Shootout` | 1 | 94 | gnu17 (C_STANDARD 17) | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 237 | Shootout-nestedloop | `SS/Shootout` | 1 | 31 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 238 | Shootout-objinst | `SS/Shootout` | 1 | 105 | gnu17 (C_STANDARD 17) | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 239 | Shootout-random | `SS/Shootout` | 1 | 36 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 240 | Shootout-sieve | `SS/Shootout` | 1 | 39 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 241 | Shootout-strcat | `SS/Shootout` | 1 | 36 | — | — | `-Wno-error=incompatible-pointer-types` | -lm | yes; exact |
| 242 | Bubblesort | `SS/Stanford` | 1 | 171 | — | — | — | -lm | yes; r 0.001 |
| 243 | FloatMM | `SS/Stanford` | 1 | 160 | — | — | — | -lm | yes; r 0.001 |
| 244 | IntMM | `SS/Stanford` | 1 | 159 | — | — | — | -lm | yes; r 0.001 |
| 245 | Oscar | `SS/Stanford` | 1 | 323 | — | — | — | -lm | yes; r 0.001 |
| 246 | Perm | `SS/Stanford` | 1 | 169 | — | — | — | -lm | yes; r 0.001 |
| 247 | Puzzle | `SS/Stanford` | 1 | 225 | — | — | — | -lm | yes; r 0.001 |
| 248 | Queens | `SS/Stanford` | 1 | 188 | — | — | — | -lm | yes; r 0.001 |
| 249 | Quicksort | `SS/Stanford` | 1 | 174 | — | — | — | -lm | yes; r 0.001 |
| 250 | RealMM | `SS/Stanford` | 1 | 161 | — | — | — | -lm | yes; r 0.001 |
| 251 | Towers | `SS/Stanford` | 1 | 218 | — | — | — | -lm | yes; r 0.001 |
| 252 | Treesort | `SS/Stanford` | 1 | 187 | — | — | — | -lm | yes; r 0.001 |

## 4. Language features

### 4.1 How features were detected

- **Reached (`gcc -E`).** Most counts come from `pp.py`, which preprocesses each program with gcc-16 in the dialect the suite passes, with glibc 2.43 headers and the program's flags, and keeps only lines from the program's own files. Code in inactive `#if` branches is not counted; for example ClamAV's and consumer-lame's `long double` appear only in such branches. The identity is GCC's (`__GNUC__` 16, no `__clang__`), so where a program tests `__GNUC__` the GCC path is the one counted.
- **Diagnostics (clang).** VLAs, K&R definitions, `()` declarations, implicit int, implicit declarations, computed goto and the C99/C11/C23 extension warnings come from clang's diagnostics in program files. Clang ran with `--target=aarch64-unknown-linux-gnu` against the same glibc headers. The flags were `-std=gnu17 -pedantic -Wvla -Wgnu -Wc23-extensions -Wimplicit-int -Wimplicit-function-declaration -Wdeprecated-non-prototype -Wstrict-prototypes`, plus `-std=gnu99 -pedantic -Wc11-extensions` and `-std=gnu89 -pedantic`. The default-error diagnostics were downgraded with `-Wno-error=…`, so a file keeps going after the first one. The program's own `-W` flags were dropped for these runs so the warnings fire.
- **Grep (`scan.py`).** Grep, which also sees inactive branches, supplies `//` comments, `#define f(...)` variadic macros, the include lists and the "inactive" rows.
- **Apple SDK.** No Apple SDK header was used, so nothing broke for SDK reasons. The section-0 fallback was not needed.
- **No C++-only constructs.** No program hit a clang error for a construct GCC accepts (nested functions, for example). The only clang errors in program files under `-std=gnu17` are `restrict` used as an identifier, in espresso and cdecl, which the suite pins to C90.

| Feature | Programs | of CTMark 6 | Which | Detected by |
|---|---|---|---|---|
| `long double` arithmetic | 2 | 1 | automotive-basicmath, **sqlite3** (CTMark sqlite3) | gcc -E reached + clang AST |
| `long double` only in inactive `#if` branches | 2 | 1 | consumer-lame, **clamscan** (CTMark ClamAV) | grep hit, absent after gcc -E |
| `%Lf`/`%Le`/`%Lg`/`%La` formats | 0 | 0 | — | string literals after gcc -E |
| `<math.h>` `*l` functions, `strtold` | 0 | 0 | — | gcc -E |
| `__int128`, `__uint128_t`, `mode(TI)` | 0 | 0 | — | grep and gcc -E |
| `_BitInt` | 0 | 0 | — | gcc -E |
| `_Complex`/`__complex__`/`complex` | 3 | 0 | mandel-2, mandel, rsbench | gcc -E |
| `<tgmath.h>` | 0 | 0 | — | includes (grep) |
| `<fenv.h>` | 0 | 0 | — | includes (grep) |
| VLA | 9 | 1 | spectral-norm, evalloop, CrystalMk, backprop, pathfinder, miniAMR, SimpleMOC, CoMD, **clamscan** (CTMark ClamAV) | clang -Wvla |
| `_Atomic`, `<stdatomic.h>`, `__atomic_*`/`__sync_*` | 0 | 0 | — | gcc -E |
| `_Thread_local`/`__thread` | 0 | 0 | — | gcc -E |
| pthread calls reached | 0 | 0 | — | gcc -E |
| pthread/TLS/atomics only in inactive branches | 4 | 2 | smg2000, AMGmk, **clamscan** (CTMark ClamAV), **sqlite3** (CTMark sqlite3) | grep hit, absent after gcc -E |
| any C11 construct or C11 header spelled by the program | 0 | 0 | — | gcc -E keywords, includes, clang -std=gnu99 -Wc11-extensions |
| any C99 construct (see 4.2) | 140 | 5 | fasta, partialsums, puzzle, spectral-norm, almabench, huffbench, lpbench, fldry, misr, evalloop, himenobmtxpa, lowercase, mandel-2, mandel, oourafft, perlin, revertBits, salsa20, dt, correlation … (120 more) | clang -std=gnu89 -pedantic, grep |
| C23 construct or extension (`{}` initializer, `#warning`, …) | 3 | 0 | gs, netbench-url, miniGMG | clang -Wc23-extensions, grep |
| K&R function definitions | 31 | 3 | dry, fldry, chomp, fbench, ffbench, flops, smg2000, espresso, cfrac, imp, bisort, em3d, voronoi, assembler, cdecl, simulator, netbench-url, ecbdes, rawcaudio, rawdaudio, toast, mpeg2decode, sim, automotive-susan, **consumer-typeset** (CTMark consumer-typeset), telecomm-gsm, security-blowfish, telecomm-adpcm, office-ispell, **pairlocalalign** (CTMark mafft), **clamscan** (CTMark ClamAV) | clang -Wdeprecated-non-prototype |
| calls with arguments to a `()` declaration | 25 | 2 | dry, fldry, flops, smg2000, five11, fhourstones, espresso, cfrac, imp, bh, voronoi, mybison, timberwolfmc, assembler, loader, plot2fig, simulator, archie, unix-smail, netbench-crc, encode, sim, PathFinder, **pairlocalalign** (CTMark mafft), **lencod** (CTMark lencod) | clang -Wdeprecated-non-prototype |
| `()` declaration that conflicts once `()` means `(void)` | 29 | 3 | dry, fldry, flops, five11, espresso, gs, cfrac, imp, bh, bisort, voronoi, mybison, timberwolfmc, assembler, loader, plot2fig, simulator, archie, unix-smail, netbench-crc, ecbdes, encode, nbench, sim, PathFinder, office-ispell, **pairlocalalign** (CTMark mafft), **sqlite3** (CTMark sqlite3), **lencod** (CTMark lencod) | clang -Wdeprecated-non-prototype |
| implicit int | 29 | 0 | dry, fldry, ReedSolomon, fbench, flops, perlin, uudecode, uuencode, espresso, gs, imp, bh, agrep, mybison, cdecl, fixoutput, unix-tbl, bc, ft, enc-pc1, ecbdes, rawcaudio, rawdaudio, encode, sim, automotive-susan, telecomm-CRC32, office-stringsearch, office-ispell | clang -Wimplicit-int |
| implicit function declarations | 5 | 0 | gs, mybison, plot2fig, archie, office-ispell | clang -Wimplicit-function-declaration |
| hex float literals | 1 | 0 | telecomm-fft | gcc -E + clang gnu89 |
| `restrict` keyword | 3 | 0 | backprop, XSBench, SimpleMOC | gcc -E |
| `inline` keyword | 77 | 2 | fasta, lowercase, oourafft, dt, correlation, covariance, gemm, gemver, gesummv, symm, syr2k, syrk … (65 more) | gcc -E |
| flexible array members | 1 | 1 | **consumer-typeset** (CTMark consumer-typeset) | clang -std=gnu89 -pedantic |
| compound literals | 1 | 0 | fhourstones3.1 | clang -std=gnu89 -pedantic |
| variadic macros (`__VA_ARGS__` or named) | 1 | 0 | netbench-url | grep `#define f(...)`, clang |
| setjmp/longjmp | 2 | 0 | gs, anagram | gcc -E |
| `signal`/`sigaction` calls | 7 | 1 | unix-tbl, unix-smail, bc, toast, telecomm-gsm, office-ispell, **sqlite3** (CTMark sqlite3) | gcc -E |
| variadic function definitions (`va_start`) | 5 | 4 | cdecl, **consumer-typeset** (CTMark consumer-typeset), **clamscan** (CTMark ClamAV), **SPASS** (CTMark SPASS), **sqlite3** (CTMark sqlite3) | grep `va_start`, reached `__builtin_va_start` |
| bitfields | 5 | 3 | fhourstones3.1, **consumer-typeset** (CTMark consumer-typeset), consumer-lame, **clamscan** (CTMark ClamAV), **sqlite3** (CTMark sqlite3) | regex on gcc -E (approximate) |
| computed goto / labels as values | 1 | 0 | evalloop | clang -Wgnu-label-as-value |
| `vector_size` | 1 | 0 | partialsums | gcc -E |
| `alloca`/`__builtin_alloca` | 2 | 1 | consumer-lame, **SPASS** (CTMark SPASS) | gcc -E |
| inline asm reached | 0 | 0 | — | gcc -E |
| statement expressions | 0 | 0 | — | clang -Wgnu-statement-expression |
| nested functions | 0 | 0 | — | clang error |
| zero-length arrays | 0 | 0 | — | clang -Wzero-length-array |
| case ranges | 0 | 0 | — | clang -Wgnu-case-range |
| `__typeof__`/`typeof` | 0 | 0 | — | gcc -E |

### 4.2 Revisions

"Needs" is the newest ISO revision with a construct the program spells and reaches:
- **C99** means any of: `//` comments, `long long`, mixed declarations and code, a declaration in a `for` initializer, `_Bool`, `inline`, `restrict`, a VLA, a flexible array member, a compound literal, a hex float, a variadic macro, a non-constant aggregate initializer, or a C99 header (`<stdint.h>`, `<stdbool.h>`, `<inttypes.h>`, `<complex.h>`, `<fenv.h>`, `<tgmath.h>`).
- **C11** means a C11 keyword or one of `<stdalign.h>`, `<stdatomic.h>`, `<stdnoreturn.h>`, `<threads.h>`, `<uchar.h>`. No program spells any of them, so no program reaches C11.
- **C17 is not a column.** C17 added no language features over C11 (it is a defect-correction revision), so it would always equal the C11 row.
- **"C23/GNU"** marks a C23 construct that GCC has long accepted as a GNU extension in older dialects: an empty initializer `{}` (gs) or `#warning` (miniGMG).

Library functions (`snprintf`, `strtoll`, …) are not counted; section 9 says why.

"GCC 16 accepts" is the range of `-std=gnuNN` that GCC 16 compiles without errors, with the program's own flags. It is the measured counterpart: the oldest dialect shows what the program needs, the newest shows what C23 removed.

| Newest revision whose features the program spells | Programs | CTMark |
|---|---|---|
| C89 | 112 | SPASS |
| C99 | 137 | consumer-typeset, mafft, ClamAV, sqlite3, lencod |
| C11 | 0 | — |
| C23/GNU | 3 | — |

| C99 construct (clang `-std=gnu89 -pedantic` unless noted) | Programs |
|---|---|
| // comments | 121 |
| mixed decls | 88 |
| inline | 77 |
| long long | 47 |
| for-init decl | 47 |
| <stdint.h> | 11 |
| VLA | 9 |
| _Bool | 6 |
| <stdbool.h> | 6 |
| <inttypes.h> | 4 |
| _Complex | 3 |
| <complex.h> | 3 |
| restrict | 3 |
| non-constant aggregate init | 2 |
| compound literal | 1 |
| variadic macro | 1 |
| flexible array | 1 |
| hex float | 1 |

| GNU dialects GCC 16 accepts (program's own flags) | Programs | CTMark |
|---|---|---|
| gnu89–gnu23 | 169 | consumer-typeset, ClamAV |
| gnu99–gnu23 | 46 | — |
| gnu89–gnu17 | 34 | mafft, SPASS, sqlite3, lencod |
| gnu89 | 3 | — |

Programs reaching at least one GNU language extension (excluding `__attribute__` and `__builtin_*`, counted separately in 4.4): **7**: partialsums, evalloop, mandel, netbench-url, network-patricia, consumer-lame, **SPASS** (CTMark SPASS).

### 4.3 `long double`

AArch64 Linux makes `long double` IEEE binary128 (`__LDBL_MANT_DIG__` 113 for this target). Two programs reach it:

| Program | `long double` expression nodes in program files (clang AST, gnu17, aarch64-linux-gnu) | Distinct source lines |
|---|---|---|
| automotive-basicmath | ImplicitCastExpr <LValueToRValue> 28, DeclRefExpr 28, ImplicitCastExpr <FloatingCast> 19, BinaryOperator * 13, BinaryOperator / 8, BinaryOperator - 6, VarDecl 5, ParmVarDecl 4, ParenExpr 2, BinaryOperator + 1, CompoundAssignOperator += 1, CompoundAssignOperator -= 1 | 13 |
| consumer-lame | none (all hits are in inactive branches) | 0 |
| clamscan | none (all hits are in inactive branches) | 0 |
| sqlite3 | DeclRefExpr 42, ImplicitCastExpr <FloatingCast> 27, ImplicitCastExpr <LValueToRValue> 21, CompoundAssignOperator *= 12, BinaryOperator = 6, VarDecl 5, UnaryOperator * 3, ImplicitCastExpr <IntegralToFloating> 3, BinaryOperator * 3, ParenExpr 3, UnaryOperator - 2, CompoundAssignOperator += 2, BinaryOperator + 2, CompoundAssignOperator /= 2, BinaryOperator - 1, ConditionalOperator 1 | 31 |

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

- **`__attribute__` names reached after `gcc -E`** (programs): `aligned` 36, `optimize` 32, `noinline` 4, `const` 1, `format` 1, `noreturn` 1, `packed` 1, `vector_size` 1.
- **`__attribute__` names spelled anywhere in program files, any branch** (programs): `aligned` 36, `optimize` 32, `noinline` 4, `const` 1, `format` 1, `noreturn` 1, `packed` 1, `unused` 1, `vector_size` 1, `visibility` 1.
- **`__builtin_*` reached after `gcc -E`**, without `__builtin_va_*` from `<stdarg.h>` (programs): `__builtin_alloca` 2, `__builtin_isnan` 2, `__builtin_huge_val` 1, `__builtin_isinf_sign` 1, `__builtin_memcpy` 1, `__builtin_offsetof` 1.
- **`__builtin_*` spelled anywhere in program files, any branch** (programs): `__builtin_alloca` 1, `__builtin_bitreverse32` 1, `__builtin_bitreverse64` 1, `__builtin_expect` 1, `__builtin_memcpy` 1, `__builtin_readcyclecounter` 1.
- **`#pragma`s reached after `gcc -E`** (programs): `STDC FP_CONTRACT` 32, `endscop` 30, `scop` 30, `omp parallel` 4, `omp for` 3, `ident` 1, `omp atomic` 1.

### 4.5 System headers

`#include <…>` targets in the program's files, plus quoted includes that name a standard header and do not resolve locally. Grep-level, so includes in inactive branches count too.

**ISO C headers** (19 of the 31 in C23), with the number of programs: `<assert.h>` 84, `<complex.h>` 3, `<ctype.h>` 34, `<errno.h>` 15, `<float.h>` 6, `<inttypes.h>` 4, `<limits.h>` 20, `<locale.h>` 2, `<math.h>` 140, `<setjmp.h>` 2, `<signal.h>` 14, `<stdarg.h>` 8, `<stdbool.h>` 6, `<stddef.h>` 12, `<stdint.h>` 11, `<stdio.h>` 248, `<stdlib.h>` 230, `<string.h>` 159, `<time.h>` 102.

**Other headers** (110: POSIX, Linux, BSD and non-portable): `<unistd.h>` 67, `<sys/types.h>` 66, `<sys/time.h>` 60, `<sys/param.h>` 43, `<sys/times.h>` 42, `<omp.h>` 36, `<sys/resource.h>` 35, `<papi.h>` 31, `<sched.h>` 30, `<strings.h>` 19, `<fcntl.h>` 18, `<sys/stat.h>` 16, `<io.h>` 10, `<windows.h>` 10, `<memory.h>` 8, `<malloc.h>` 7, `<netinet/in.h>` 5, `<pthread.h>` 5, `<sys/socket.h>` 5, `<arpa/inet.h>` 4, `<mpi.h>` 4, `<pwd.h>` 4, `<cm/cmmd.h>` 3, `<dos.h>` 3, `<sys/timeb.h>` 3, `<utime.h>` 3, `<SIOUX.h>` 2, `<Timer.h>` 2, `<alloc.h>` 2, `<alloca.h>` 2, `<console.h>` 2, `<dirent.h>` 2, `<err.h>` 2, `<netdb.h>` 2, `<rle.h>` 2, `<ssdef.h>` 2, `<sys/file.h>` 2, `<sys/ioctl.h>` 2, `<sys/ipc.h>` 2, `<sys/rusage.h>` 2, `<sys/shm.h>` 2, `<sys/syscall.h>` 2, `<sys/timesu.h>` 2, `<sys/wait.h>` 2, `<unix.h>` 2, `<CursorCtl.h>` 1, `<Time.h>` 1, `<Types.h>` 1, `<Winsock2.h>` 1, `<X11/Xlib.h>` 1, `<X11/Xutil.h>` 1, `<X11/extensions/XShm.h>` 1, `<bzlib.h>` 1, `<conio.h>` 1, `<crtdbg.h>` 1, `<dlfcn.h>` 1, `<execinfo.h>` 1, `<features.h>` 1, `<floatingpoint.h>` 1, `<fpu_control.h>` 1, `<getopt.h>` 1, `<gmp.h>` 1, `<gnu-versions.h>` 1, `<grp.h>` 1, `<gtk/gtk.h>` 1, `<iconv.h>` 1, `<in.h>` 1, `<jpidef.h>` 1, `<libintl.h>` 1, `<lowmem.h>` 1, `<mem.h>` 1, `<msdos/cutcp.h>` 1, `<msdos/hostform.h>` 1, `<msdos/netevent.h>` 1, `<net/errno.h>` 1, `<net/if.h>` 1, `<nl_types.h>` 1, `<os2.h>` 1, `<os2def.h>` 1, `<os2safe.h>` 1, `<osfcn.h>` 1, `<pctcp.h>` 1, `<readline/history.h>` 1, `<readline/readline.h>` 1, `<regex.h>` 1, `<rwconf.h>` 1, `<sgtty.h>` 1, `<socket.h>` 1, `<sys/cygwin.h>` 1, `<sys/inet.h>` 1, `<sys/int_types.h>` 1, `<sys/mman.h>` 1, `<sys/mount.h>` 1, `<sys/select.h>` 1, `<sys/utime.h>` 1, `<sys/utsname.h>` 1, `<sys\stat.h>` 1, `<sysexits.h>` 1, `<syslog.h>` 1, `<tcl.h>` 1, `<termcap.h>` 1, `<termio.h>` 1, `<termios.h>` 1, `<toolhelp.h>` 1, `<types.h>` 1, `<unixio.h>` 1, `<unixlib.h>` 1, `<varargs.h>` 1, `<winbase.h>` 1, `<winsock.h>` 1.

### 4.6 Per-program table

Columns:
- **"Needs"** and **"GCC 16 accepts"**: see 4.2.
- **`long double`**: "arith" means arithmetic is reached; "inactive" means grep-only.
- **K&R defs**: K&R function definitions.
- **`f()` called with args**: calls that pass arguments to a function declared `()`.
- **`f()` decl conflicts**: `()` declarations that conflict with a definition or another declaration once `()` means `(void)`.
- **implicit int**, **implicit decl**: clang diagnostic counts in program files.
- **gnu23 errors**: GCC 16's errors at its default dialect, grouped by message.

| # | Program | Needs | GCC 16 accepts | `long double` | `_Complex` | VLA | K&R defs | `f()` called with args | `f()` decl conflicts | implicit int | implicit decl | gnu23 errors (class) | GNU extensions reached |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **clamscan** (CTMark ClamAV) | C99 | gnu89–gnu23 | inactive | — | 1 | 142 | — | — | — | — | 0 | — |
| 2 | **lencod** (CTMark lencod) | C99 | gnu89–gnu17 | — | — | — | — | 2 | 1 | — | — | 3: () now means (void) 3 | — |
| 3 | **SPASS** (CTMark SPASS) | C89 | gnu89–gnu17 | — | — | — | — | — | — | — | — | 14: bool/true/false keywords 13; () now means (void) 1 | alloca |
| 4 | **sqlite3** (CTMark sqlite3) | C99 | gnu89–gnu17 | arith | — | — | — | — | 1 | — | — | 2: () now means (void) 2 | — |
| 5 | smg2000 | C89 | gnu89–gnu17 | — | — | — | 1 | 4 | — | — | — | 8: () now means (void) 8 | — |
| 6 | AMGmk | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 7 | CrystalMk | C99 | gnu89–gnu23 | — | — | 94 | — | — | — | — | — | 0 | — |
| 8 | IRSmk | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 9 | drop3 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 10 | five11 | C99 | gnu89–gnu17 | — | — | — | — | 2 | 2 | — | — | 4: () now means (void) 4 | — |
| 11 | uudecode | C99 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 12 | uuencode | C99 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 13 | CoMD | C99 | gnu99–gnu23 | — | — | 1 | — | — | — | — | — | 0 | — |
| 14 | PathFinder | C99 | gnu89–gnu17 | — | — | — | — | 1 | 1 | — | — | 2: () now means (void) 2 | — |
| 15 | rsbench | C99 | gnu99–gnu23 | — | yes (complex.h) | — | — | — | — | — | — | 0 | — |
| 16 | SimpleMOC | C99 | gnu99–gnu23 | — | — | 5 | — | — | — | — | — | 0 | — |
| 17 | XSBench | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 18 | miniAMR | C99 | gnu99–gnu23 | — | — | 9 | — | — | — | — | — | 0 | — |
| 19 | miniGMG | C23/GNU | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 20 | fhourstones | C99 | gnu89–gnu17 | — | — | — | — | 12 | — | — | — | 12: () now means (void) 12 | — |
| 21 | fhourstones3.1 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 22 | analyzer | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 23 | distray | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 24 | fourinarow | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 25 | mason | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 26 | neural | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 27 | pcompress2 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 28 | pifft | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 29 | cfrac | C99 | gnu89–gnu17 | — | — | — | 60 | 102 | 3 | — | — | 113: () now means (void) 113 | — |
| 30 | espresso | C89 | gnu89 | — | — | — | 341 | 1391 | 370 | 597 | — | 2827: () now means (void) 2205; implicit int 600; restrict is a keyword 14; bool/true/false keywords 6; other 2 | — |
| 31 | gs | C23/GNU | gnu89–gnu17 | — | — | — | — | — | 1 | 2 | 198 | 8: () now means (void) 2; bool/true/false keywords 2; other 2; restrict is a keyword 2 | — |
| 32 | qbsort | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 33 | testtrie | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 34 | bisect | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 35 | eks | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 36 | main | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 37 | vor | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 38 | iotest | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 39 | trie | C89 | gnu89–gnu17 | — | — | — | — | — | — | — | — | 1: bool/true/false keywords 1 | — |
| 40 | bintr | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 41 | imp | C89 | gnu89–gnu17 | — | — | — | 5 | 5 | 4 | 1 | — | 13: () now means (void) 13 | — |
| 42 | automotive-basicmath | C99 | gnu89–gnu23 | arith | — | — | — | — | — | — | — | 0 | — |
| 43 | automotive-bitcount | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 44 | automotive-susan | C89 | gnu89–gnu23 | — | — | — | 18 | — | — | 14 | — | 0 | — |
| 45 | consumer-jpeg | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 46 | consumer-lame | C99 | gnu89–gnu23 | inactive | — | — | — | — | — | — | — | 0 | alloca |
| 47 | **consumer-typeset** (CTMark consumer-typeset) | C99 | gnu89–gnu23 | — | — | — | 2 | — | — | — | — | 0 | — |
| 48 | network-dijkstra | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 49 | network-patricia | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | void* arithmetic |
| 50 | office-ispell | C89 | gnu89–gnu17 | — | — | — | 99 | — | 24 | 3 | 1 | 36: () now means (void) 36 | — |
| 51 | office-stringsearch | C89 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 52 | security-blowfish | C89 | gnu89–gnu23 | — | — | — | 7 | — | — | — | — | 0 | — |
| 53 | security-rijndael | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 54 | security-sha | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 55 | telecomm-CRC32 | C89 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 56 | telecomm-fft | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 57 | telecomm-adpcm | C89 | gnu89–gnu23 | — | — | — | 2 | — | — | — | — | 0 | — |
| 58 | telecomm-gsm | C89 | gnu89–gnu23 | — | — | — | 1 | — | — | — | — | 0 | — |
| 59 | is | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 60 | bh | C89 | gnu89–gnu17 | — | — | — | — | 23 | 10 | 1 | — | 72: () now means (void) 69; bool/true/false keywords 3 | — |
| 61 | bisort | C99 | gnu89–gnu17 | — | — | — | 4 | — | 6 | — | — | 19: () now means (void) 19 | — |
| 62 | em3d | C89 | gnu89–gnu23 | — | — | — | 1 | — | — | — | — | 0 | — |
| 63 | health | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 64 | mst | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 65 | perimeter | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 66 | power | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 67 | treeadd | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 68 | tsp | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 69 | voronoi | C99 | gnu89–gnu17 | — | — | — | 17 | 15 | 16 | — | — | 72: () now means (void) 72 | — |
| 70 | timberwolfmc | C99 | gnu89–gnu17 | — | — | — | — | 35 | 123 | — | — | 167: () now means (void) 166; bool/true/false keywords 1 | — |
| 71 | agrep | C89 | gnu89–gnu23 | — | — | — | — | — | — | 33 | — | 0 | — |
| 72 | allroots | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 73 | archie | C99 | gnu89–gnu17 | — | — | — | — | 83 | 21 | — | 26 | 104: () now means (void) 104 | — |
| 74 | assembler | C89 | gnu89–gnu17 | — | — | — | 7 | 160 | 13 | — | — | 173: () now means (void) 173 | — |
| 75 | mybison | C99 | gnu89–gnu17 | — | — | — | — | 119 | 6 | 1 | 2 | 128: () now means (void) 128 | — |
| 76 | cdecl | C99 | gnu89 | — | — | — | 14 | — | — | 2 | — | 15: restrict is a keyword 13; implicit int 2 | — |
| 77 | compiler | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 78 | fixoutput | C89 | gnu89–gnu23 | — | — | — | — | — | — | 2 | — | 0 | — |
| 79 | football | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 80 | gnugo | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 81 | loader | C89 | gnu89–gnu17 | — | — | — | — | 45 | 2 | — | — | 47: () now means (void) 47 | — |
| 82 | plot2fig | C89 | gnu89–gnu17 | — | — | — | — | 1 | 2 | — | 2 | 3: () now means (void) 3 | — |
| 83 | simulator | C89 | gnu89–gnu17 | — | — | — | 16 | 335 | 4 | — | — | 343: () now means (void) 343 | — |
| 84 | unix-smail | C89 | gnu89–gnu17 | — | — | — | — | 86 | 37 | — | — | 142: () now means (void) 142 | — |
| 85 | unix-tbl | C89 | gnu89 | — | — | — | — | — | — | 2 | — | 2: () now means (void) 1; glibc C23 _Generic macro 1 | — |
| 86 | anagram | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 87 | bc | C89 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 88 | ft | C99 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 89 | ks | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 90 | yacr2 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 91 | backprop | C99 | gnu99–gnu23 | — | — | 14 | — | — | — | — | — | 0 | — |
| 92 | hotspot | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 93 | pathfinder | C99 | gnu99–gnu23 | — | — | 4 | — | — | — | — | — | 0 | — |
| 94 | srad | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 95 | scimark2 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 96 | ControlFlow-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 97 | ControlFlow-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 98 | ControlLoops-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 99 | ControlLoops-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 100 | CrossingThresholds-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 101 | CrossingThresholds-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 102 | Equivalencing-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 103 | Equivalencing-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 104 | Expansion-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 105 | Expansion-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 106 | GlobalDataFlow-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 107 | GlobalDataFlow-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 108 | IndirectAddressing-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 109 | IndirectAddressing-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 110 | InductionVariable-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 111 | InductionVariable-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 112 | LinearDependence-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 113 | LinearDependence-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 114 | LoopRerolling-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 115 | LoopRerolling-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 116 | LoopRestructuring-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 117 | LoopRestructuring-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 118 | NodeSplitting-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 119 | NodeSplitting-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 120 | Packing-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 121 | Packing-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 122 | Recurrences-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 123 | Recurrences-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 124 | Reductions-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 125 | Reductions-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 126 | Searching-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 127 | Searching-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 128 | StatementReordering-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 129 | StatementReordering-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 130 | Symbolics-dbl | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 131 | Symbolics-flt | C99 | gnu99–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 132 | enc-3des | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 133 | enc-md5 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 134 | enc-pc1 | C89 | gnu89–gnu23 | — | — | — | — | — | — | 3 | — | 0 | — |
| 135 | enc-rc4 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 136 | netbench-crc | C89 | gnu89–gnu17 | — | — | — | — | 1 | 1 | — | — | 2: () now means (void) 2 | — |
| 137 | netbench-url | C23/GNU | gnu89–gnu23 | — | — | — | 1 | — | — | — | — | 0 | , ##__VA_ARGS__, named variadic macro |
| 138 | 8b10b | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 139 | beamformer | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 140 | bmm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 141 | dbms | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 142 | ecbdes | C99 | gnu89–gnu17 | — | — | — | 10 | — | 1 | 1 | — | 1: () now means (void) 1 | — |
| 143 | llu | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 144 | **pairlocalalign** (CTMark mafft) | C99 | gnu89–gnu17 | — | — | — | 2 | 4 | 340 | — | — | 357: () now means (void) 357 | — |
| 145 | rawcaudio | C89 | gnu89–gnu23 | — | — | — | 2 | — | — | 1 | — | 0 | — |
| 146 | rawdaudio | C89 | gnu89–gnu23 | — | — | — | 2 | — | — | 1 | — | 0 | — |
| 147 | encode | C89 | gnu89–gnu17 | — | — | — | — | 50 | 8 | 1 | — | 60: () now means (void) 60 | — |
| 148 | toast | C89 | gnu89–gnu23 | — | — | — | 1 | — | — | — | — | 0 | — |
| 149 | cjpeg | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 150 | mpeg2decode | C89 | gnu89–gnu23 | — | — | — | 61 | — | — | — | — | 0 | — |
| 151 | nbench | C89 | gnu89–gnu17 | — | — | — | — | — | 1 | — | — | 1: () now means (void) 1 | — |
| 152 | sim | C89 | gnu89–gnu17 | — | — | — | 11 | 17 | 10 | 8 | — | 46: () now means (void) 46 | — |
| 153 | fannkuch | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 154 | n-body | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 155 | nsieve-bits | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 156 | partialsums | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | vector_size |
| 157 | puzzle | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 158 | recursive | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 159 | spectral-norm | C99 | gnu89–gnu23 | — | — | 3 | — | — | — | — | — | 0 | — |
| 160 | fasta | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 161 | almabench | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 162 | huffbench | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 163 | lpbench | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 164 | dry | C89 | gnu89–gnu17 | — | — | — | 9 | 9 | 9 | 10 | — | 28: () now means (void) 28 | — |
| 165 | fldry | C99 | gnu89–gnu17 | — | — | — | 10 | 9 | 9 | 9 | — | 28: () now means (void) 28 | — |
| 166 | linpack-pc | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 167 | chomp | C89 | gnu89–gnu23 | — | — | — | 2 | — | — | — | — | 0 | — |
| 168 | exptree | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 169 | misr | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 170 | queens | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 171 | ReedSolomon | C89 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 172 | dt | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 173 | evalloop | C99 | gnu99–gnu23 | — | — | 1 | — | — | — | — | — | 0 | computed goto |
| 174 | fbench | C89 | gnu89–gnu23 | — | — | — | 2 | — | — | 1 | — | 0 | — |
| 175 | ffbench | C89 | gnu89–gnu23 | — | — | — | 1 | — | — | — | — | 0 | — |
| 176 | flops | C89 | gnu89–gnu17 | — | — | — | 1 | 22 | 1 | 1 | — | 24: () now means (void) 24 | — |
| 177 | flops-1 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 178 | flops-2 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 179 | flops-3 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 180 | flops-4 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 181 | flops-5 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 182 | flops-6 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 183 | flops-7 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 184 | flops-8 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 185 | fp-convert | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 186 | himenobmtxpa | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 187 | lowercase | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 188 | mandel | C99 | gnu89–gnu23 | — | yes (complex.h) | — | — | — | — | — | — | 0 | __complex__, imaginary constant |
| 189 | mandel-2 | C99 | gnu89–gnu23 | — | yes (complex.h) | — | — | — | — | — | — | 0 | — |
| 190 | matmul_f64_4x4 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 191 | oourafft | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 192 | perlin | C99 | gnu89–gnu23 | — | — | — | — | — | — | 1 | — | 0 | — |
| 193 | pi | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 194 | revertBits | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 195 | richards_benchmark | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 196 | salsa20 | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 197 | whetstone | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 198 | correlation | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 199 | covariance | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 200 | gemm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 201 | gemver | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 202 | gesummv | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 203 | symm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 204 | syr2k | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 205 | syrk | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 206 | trmm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 207 | 2mm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 208 | 3mm | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 209 | atax | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 210 | bicg | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 211 | doitgen | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 212 | mvt | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 213 | cholesky | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 214 | durbin | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 215 | gramschmidt | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 216 | lu | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 217 | ludcmp | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 218 | trisolv | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 219 | deriche | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 220 | floyd-warshall | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 221 | nussinov | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 222 | adi | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 223 | fdtd-2d | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 224 | heat-3d | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 225 | jacobi-1d | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 226 | jacobi-2d | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 227 | seidel-2d | C99 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 228 | Shootout-ackermann | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 229 | Shootout-ary3 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 230 | Shootout-fib2 | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 231 | Shootout-hash | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 232 | Shootout-heapsort | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 233 | Shootout-hello | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 234 | Shootout-lists | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 235 | Shootout-matrix | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 236 | Shootout-methcall | C89 | gnu89–gnu17 | — | — | — | — | — | — | — | — | 1: bool/true/false keywords 1 | — |
| 237 | Shootout-nestedloop | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 238 | Shootout-objinst | C89 | gnu89–gnu17 | — | — | — | — | — | — | — | — | 1: bool/true/false keywords 1 | — |
| 239 | Shootout-random | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 240 | Shootout-sieve | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 241 | Shootout-strcat | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 242 | Bubblesort | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 243 | FloatMM | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 244 | IntMM | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 245 | Oscar | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 246 | Perm | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 247 | Puzzle | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 248 | Queens | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 249 | Quicksort | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 250 | RealMM | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 251 | Towers | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |
| 252 | Treesort | C89 | gnu89–gnu23 | — | — | — | — | — | — | — | — | 0 | — |

## 5. GCC's default `gnu23` versus `gnu17`

This was measured with GCC 16.1 (Homebrew, `aarch64-apple-darwin24`) given the Linux identity (section 0), not GCC 15.2 on Ubuntu. GCC 16's default is `gnu23`, as GCC 15's is. Each configuration passes the program's own `-D`, `-I`, `-f` and `-W` flags; the `-W` flags are how the suite keeps GCC 14+ permerrors off. Only errors located in program files are counted.

| Configuration (GCC 16.1 on Darwin, glibc 2.43 headers, program's own `-D`/`-I`/`-W`/`-f` flags) | Programs with errors | of CTMark 6 | Which |
|---|---|---|---|
| default dialect (`gnu23`), every program | 37 | 4: mafft, SPASS, sqlite3, lencod | dry, fldry, flops, Shootout-methcall, Shootout-objinst, smg2000, five11, fhourstones, espresso, gs, cfrac, imp, trie, bh, bisort, voronoi, mybison, timberwolfmc, assembler, cdecl, loader, plot2fig, simulator, unix-tbl, archie, unix-smail, netbench-crc, ecbdes, encode, nbench, sim, PathFinder, office-ispell, **pairlocalalign** (CTMark mafft), **SPASS** (CTMark SPASS), **sqlite3** (CTMark sqlite3), **lencod** (CTMark lencod) |
| `-std=gnu17`, every program | 3 | 0 | espresso, cdecl, unix-tbl |
| `-std=gnu11`, every program | 3 | 0 | espresso, cdecl, unix-tbl |
| `-std=gnu99`, every program | 3 | 0 | espresso, cdecl, unix-tbl |
| `-std=gnu89`, every program | 46 | 0 | evalloop, hotspot, srad, backprop, pathfinder, ControlFlow-dbl, ControlFlow-flt, ControlLoops-dbl, ControlLoops-flt, CrossingThresholds-dbl, CrossingThresholds-flt, Equivalencing-dbl, Equivalencing-flt, Expansion-dbl, Expansion-flt, GlobalDataFlow-dbl, GlobalDataFlow-flt, IndirectAddressing-dbl, IndirectAddressing-flt, InductionVariable-dbl, InductionVariable-flt, LinearDependence-dbl, LinearDependence-flt, LoopRerolling-dbl, LoopRerolling-flt, LoopRestructuring-dbl, LoopRestructuring-flt, NodeSplitting-dbl, NodeSplitting-flt, Packing-dbl, Packing-flt, Recurrences-dbl, Recurrences-flt, Reductions-dbl, Reductions-flt, Searching-dbl, Searching-flt, StatementReordering-dbl, StatementReordering-flt, Symbolics-dbl, Symbolics-flt, XSBench, rsbench, miniAMR, SimpleMOC, CoMD |
| the dialect the suite passes (C_STANDARD pin or own `-std=`, else default `gnu23`) | 3 | 0 | plot2fig, unix-tbl, archie |

| gnu23 error class (message-based) | Errors | Programs |
|---|---|---|
| () now means (void) | 4215 | 33 |
| implicit int | 602 | 2 |
| restrict is a keyword | 29 | 3 |
| bool/true/false keywords | 28 | 8 |
| other | 4 | 2 |
| glibc C23 _Generic macro | 1 | 1 |

Of the 37 programs that fail at `gnu23`, 34 carry a pin that keeps the suite from compiling them at `gnu23`, and 3 do not: plot2fig, unix-tbl, archie.
Of the 35 programs pinned to `C_STANDARD 17` or `90`, 1 compile at `gnu23` anyway: **clamscan** (CTMark ClamAV).

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

| If the slice dropped | Programs that fall out | CTMark six | Which | Basis |
|---|---|---|---|---|
| `long double` (binary128) | **2** | sqlite3 out; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | automotive-basicmath, **sqlite3** (CTMark sqlite3) | reached after `gcc -E`; AST confirms arithmetic |
| `__int128` | **0** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | — | no occurrence, even in inactive branches |
| `_Complex` | **3** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | mandel-2, mandel, rsbench | reached after `gcc -E` |
| VLAs | **9** | sqlite3 in; ClamAV out; consumer-typeset in; lencod in; mafft in; SPASS in | spectral-norm, evalloop, CrystalMk, backprop, pathfinder, miniAMR, SimpleMOC, CoMD, **clamscan** (CTMark ClamAV) | clang `-Wvla` in program source |
| `_Atomic` and threads (`<threads.h>`, pthreads, TLS) | **0** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | — | reached after `gcc -E` |
| C11 as a whole (language features and C11 headers spelled by the program) | **0** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | — | see 4.2; glibc's own `_Generic` macros are section C |
| C11 as a whole, counted by GCC 16 failing at `-std=gnu99` | **0** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | — | compiles at gnu17 but not gnu99 |
| pre-C23 rules: slice compiles only with C23 rules (GCC 15's default `gnu23`) | **37** | sqlite3 out; ClamAV in; consumer-typeset in; lencod out; mafft out; SPASS out | dry, fldry, flops, Shootout-methcall, Shootout-objinst, smg2000, five11, fhourstones, espresso, gs, cfrac, imp, trie, bh, bisort, voronoi, mybison, timberwolfmc, assembler, cdecl, loader, plot2fig, simulator, unix-tbl, archie, unix-smail, netbench-crc, ecbdes, encode, nbench, sim, PathFinder, office-ispell, **pairlocalalign** (CTMark mafft), **SPASS** (CTMark SPASS), **sqlite3** (CTMark sqlite3), **lencod** (CTMark lencod) | GCC 16 errors at `gnu23` |
| C99 as a whole, ISO reading: slice is strict C89 | **140** | sqlite3 out; ClamAV out; consumer-typeset out; lencod out; mafft out; SPASS in | fasta, partialsums, puzzle, spectral-norm, almabench, huffbench, lpbench, fldry, misr, evalloop, himenobmtxpa, lowercase, mandel-2, mandel, oourafft, perlin, revertBits, salsa20, dt, correlation, covariance, gemm, gemver, gesummv, symm, syr2k, syrk, trmm, 2mm, 3mm, atax, bicg, doitgen, mvt, cholesky, durbin, gramschmidt, lu, ludcmp, trisolv, deriche, floyd-warshall, nussinov, adi, fdtd-2d, heat-3d, jacobi-1d, jacobi-2d, seidel-2d, AMGmk, CrystalMk, IRSmk, drop3, five11, uudecode, uuencode, fhourstones, fhourstones3.1, fourinarow, gs, cfrac, bintr, bisort, health, voronoi, mybison, timberwolfmc, cdecl, archie, ft, yacr2, scimark2, enc-md5, netbench-url, beamformer, bmm, ecbdes, 8b10b, cjpeg, hotspot, srad, backprop, pathfinder, ControlFlow-dbl, ControlFlow-flt, ControlLoops-dbl, ControlLoops-flt, CrossingThresholds-dbl, CrossingThresholds-flt, Equivalencing-dbl, Equivalencing-flt, Expansion-dbl, Expansion-flt, GlobalDataFlow-dbl, GlobalDataFlow-flt, IndirectAddressing-dbl, IndirectAddressing-flt, InductionVariable-dbl, InductionVariable-flt, LinearDependence-dbl, LinearDependence-flt, LoopRerolling-dbl, LoopRerolling-flt, LoopRestructuring-dbl, LoopRestructuring-flt, NodeSplitting-dbl, NodeSplitting-flt, Packing-dbl, Packing-flt, Recurrences-dbl, Recurrences-flt, Reductions-dbl, Reductions-flt, Searching-dbl, Searching-flt, StatementReordering-dbl, StatementReordering-flt, Symbolics-dbl, Symbolics-flt, XSBench, rsbench, PathFinder, miniAMR, miniGMG, SimpleMOC, CoMD, automotive-basicmath, automotive-bitcount, consumer-jpeg, **consumer-typeset** (CTMark consumer-typeset), network-dijkstra, network-patricia, security-rijndael, security-sha, telecomm-fft, consumer-lame, **pairlocalalign** (CTMark mafft), **clamscan** (CTMark ClamAV), **sqlite3** (CTMark sqlite3), **lencod** (CTMark lencod) | program spells any C99 construct (4.2) |
| C99 as a whole, GCC reading: slice is `gnu89` (GCC accepts many C99 features there as extensions) | **46** | sqlite3 in; ClamAV in; consumer-typeset in; lencod in; mafft in; SPASS in | evalloop, hotspot, srad, backprop, pathfinder, ControlFlow-dbl, ControlFlow-flt, ControlLoops-dbl, ControlLoops-flt, CrossingThresholds-dbl, CrossingThresholds-flt, Equivalencing-dbl, Equivalencing-flt, Expansion-dbl, Expansion-flt, GlobalDataFlow-dbl, GlobalDataFlow-flt, IndirectAddressing-dbl, IndirectAddressing-flt, InductionVariable-dbl, InductionVariable-flt, LinearDependence-dbl, LinearDependence-flt, LoopRerolling-dbl, LoopRerolling-flt, LoopRestructuring-dbl, LoopRestructuring-flt, NodeSplitting-dbl, NodeSplitting-flt, Packing-dbl, Packing-flt, Recurrences-dbl, Recurrences-flt, Reductions-dbl, Reductions-flt, Searching-dbl, Searching-flt, StatementReordering-dbl, StatementReordering-flt, Symbolics-dbl, Symbolics-flt, XSBench, rsbench, miniAMR, SimpleMOC, CoMD | GCC 16 errors at `-std=gnu89` |

- **C11 row.** Every program that compiles at `gnu17` also compiles at `gnu99` and `gnu11` under GCC 16 (4.2), and none spells a C11 construct. The 33 programs pinned to `C_STANDARD 17` are pinned to stay below C23, not because they need C11. A slice limited to C99 would still meet C11 constructs in glibc's headers (Part C).
- **C99 rows.** All 46 programs that fail at `-std=gnu89` contain `for (int i = …)` declarations ("'for' loop initial declarations are only allowed in C99 or C11 mode", 1,718 errors), and two of them also use `restrict` as a keyword. GCC accepts the rest of the C99 list in 4.2 in `gnu89` as extensions: `//`, `long long`, mixed declarations, `inline`, VLAs, flexible arrays and `_Bool`.
- **Inactive branches.** `long double` and pthreads appear only in inactive branches in four programs (4.1). sqlite3 is built with `-DSQLITE_THREADSAFE=0`. smg2000 uses `-DHYPRE_SEQUENTIAL`. ClamAV's and AMGmk's pthread code is not reached on this configuration. No C program's flags include `-pthread`.

## 7. Part B: GCC C torture tests (grep-level)

**Source.** `gcc/testsuite/gcc.c-torture/execute/` from GCC's `releases/gcc-15` branch, via the GitHub mirror `https://github.com/gcc-mirror/gcc`. The tip was **`7b7cd17e123e311a083df49f79822ffabee7205f`** (2026-11-10, "Daily bump."), fetched with `git clone --depth 1 --filter=blob:none --sparse`. The branch tip is later than the 15.2.0 release; the directory was not compared with the `releases/gcc-15.2.0` tag.

**What a test is.** A `.c` file in `execute/` (1,682), a `builtins/*.c` file other than a `*-lib.c` helper (58), or an `ieee/*.c` file (69): **1,809 tests**. `torture.py` counts regex hits on comment-stripped text. Nested functions, VLAs and labels-as-values come from clang (`-std=gnu17`, aarch64-unknown-linux-gnu, glibc 2.43 headers), which reports them per file. **Everything here is grep-level**:
- `#if`-guarded uses count. For example, most `__int128` tests test `__SIZEOF_INT128__` first.
- The inline-asm count includes `asm("")` barriers and target-guarded blocks.
- The grep computed-goto count includes `&&` false positives.

| Tests using | Tests | Share |
|---|---|---|
| nested functions (clang: "function definition is not allowed here") | 30 | 1.7% |
| `long double` | 56 | 3.1% |
| `__int128`, `__int128_t`, `__uint128_t`, `mode(TI)` | 15 | 0.8% |
| `_Complex`, `__complex__`, `__real__`/`__imag__`, `<complex.h>` | 24 | 1.3% |
| of which complex integer types (`_Complex int`, `__complex__ char`, …) | 7 | 0.4% |
| `vector_size` | 24 | 1.3% |
| VLAs (clang `-Wvla`) | 23 | 1.3% |
| computed goto / labels as values (clang `-Wgnu-label-as-value`) | 17 | 0.9% |
| computed goto / labels as values (grep `goto *`, `&&label`; includes false positives) | 44 | 2.4% |
| any `__builtin_*` | 573 | 31.7% |
| inline asm (`asm`/`__asm__` followed by `(`) | 96 | 5.3% |
| `_Atomic`, `<stdatomic.h>` | 0 | 0.0% |
| `__atomic_*`/`__sync_*` calls | 1 | 0.1% |
| `_BitInt` | 0 | 0.0% |
| `_FloatN` | 0 | 0.0% |
| setjmp/longjmp, including `__builtin_setjmp` | 21 | 1.2% |
| statement expressions (grep `({`) | 10 | 0.6% |
| `__attribute__` | 554 | 30.6% |
| an options or target `dg-` directive (list below) | 322 | 17.8% |
| a `.x` Tcl control file beside it | 52 | 2.9% |

**Top 30 `__builtin_*` by number of tests:** `__builtin_abort` 409, `__builtin_memset` 39, `__builtin_memcpy` 33, `__builtin_alloca` 23, `__builtin_memcmp` 21, `__builtin_setjmp` 19, `__builtin_strcmp` 18, `__builtin_printf` 16, `__builtin_strlen` 16, `__builtin_strcpy` 10, `__builtin_mul_overflow` 9, `__builtin_malloc` 8, `__builtin_inf` 8, `__builtin_nan` 7, `__builtin_isunordered` 7, `__builtin_expect` 6, `__builtin_prefetch` 6, `__builtin_constant_p` 5, `__builtin_ffs` 5, `__builtin_offsetof` 5, `__builtin_add_overflow` 5, `__builtin_islessgreater` 5, `__builtin_return_address` 4, `__builtin_unreachable` 4, `__builtin_longjmp` 4, `__builtin_copysign` 4, `__builtin_isless` 4, `__builtin_islessequal` 4, `__builtin_isgreaterequal` 4, `__builtin_isgreater` 4.

**`dg-` directive kinds (tests):** `dg-additional-options` 139, `dg-require-effective-target` 129, `dg-options` 43, `dg-skip-if` 37, `dg-add-options` 15, `dg-require-stack-size` 8, `dg-xfail-if` 6, `dg-xfail-run-if` 6, `dg-timeout-factor` 5, `dg-do` 5, `dg-require-alias` 3, `dg-prune-output` 3, `dg-require-weak` 1.

**Options in `dg-options`/`dg-additional-options` (tests, top 20):** `-std=gnu89` 75, `-fpermissive` 32, `-std=gnu17` 13, `-fgnu89-inline` 12, `-fwrapv` 12, `-Wno-psabi` 5, `-fno-inline` 3, `-fmodulo-sched` 3, `-fno-common` 2, `-mno-mmx` 2, `-Wl,-u,_printf_float` 2, `-fno-vect-cost-model` 2, `-O2` 2, `-mtune=i686` 1, `-std=c99` 1, `-fno-trapping-math` 1, `-fnon-call-exceptions` 1, `-DSIGNAL_SUPPRESS` 1, `-mcheck-zero-division` 1, `-Wno-old-style-definition` 1.

**Target and skip directives (tests, top 20):** `dg-require-effective-target int32plus` 56; `dg-require-effective-target label_values` 19; `dg-require-effective-target trampolines` 14; `dg-skip-if "requires io" { freestanding }` 13; `dg-require-effective-target indirect_jumps` 11; `dg-require-effective-target untyped_assembly` 7; `dg-require-effective-target return_address` 6; `dg-require-effective-target run_expensive_tests` 5; `dg-skip-if "memory full + time hog" { "avr-*-*" }` 5; `dg-xfail-run-if {unexpected PTX 'vprintf' return value} { nvptx-*-* }` 4; `dg-require-effective-target c99_runtime` 3; `dg-require-alias ""` 3; `dg-require-effective-target fileio` 3; `dg-skip-if "requires io" { avr-*-* }` 3; `dg-require-effective-target double64plus` 2; `dg-xfail-if "Can not call system libm.a with -msoft-float" { powerpc-*-aix* rs6000-*-aix* ` 2; `dg-skip-if "small alignment" { pdp11-*-* }` 2; `dg-require-effective-target mmap` 2; `dg-skip-if "the executable is at the same position the test tries to remap" { m68k-*-linux` 2; `dg-require-effective-target stdint_types` 2.

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

| Configuration pair (gcc-16, aarch64-linux-gnu identity, 47 root headers) | Header lines present only in the first | Constructs in those lines (lines) |
|---|---|---|
| `c23 minus c17` | 393 | (no listed construct) 208, __attribute__ 154, restrict 30, asm label (__REDIRECT) 24, __glibc_const_generic (qualifier-preserving _Generic) 11, bool / true / false 6, char8_t / char16_t / char32_t 3, _Bool 1, __inline 1 |
| `gnu23 minus gnu17` | 382 | (no listed construct) 203, __attribute__ 150, restrict 28, asm label (__REDIRECT) 26, __glibc_const_generic (qualifier-preserving _Generic) 11, bool / true / false 6, char8_t / char16_t / char32_t 3, _Bool 1, __extension__ statement expression 1, __inline 1 |
| `c17 minus c11` | 0 | — |
| `c11 minus c99` | 15 | (no listed construct) 5, __attribute__ 5, __builtin_* 3, static_assert / _Static_assert 2 |
| `gnu17-O2 minus gnu17` | 127 | (no listed construct) 90, __attribute__ 26, __extern_always_inline / extern inline function body 15, __inline 13, __builtin_* 8, restrict 2, __extension__ statement expression 2 |
| `gnu23-O2 minus gnu23` | 127 | (no listed construct) 90, __attribute__ 26, __extern_always_inline / extern inline function body 15, __inline 13, __builtin_* 8, restrict 2, __extension__ statement expression 2 |
| `gnu17-O2-fortify3 minus gnu17-O2` | 734 | __attribute__ 337, (no listed construct) 194, restrict 168, __builtin_* 101, asm label (__REDIRECT) 85, __extern_always_inline / extern inline function body 29, __inline 29, __extension__ statement expression 1 |
| `gnu17-O0-fortify3 minus gnu17` | 0 | — |

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


