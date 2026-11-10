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

{{PARTA_FEATURES}}
