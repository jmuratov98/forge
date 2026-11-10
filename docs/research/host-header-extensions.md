# Host header extension inventory

Research for GitHub issue #9 (parent map #1). Throwaway branch `research/host-header-extensions`; never merged, no PR. This file is generated: `host-header-extensions/scripts/report.py` splices tables into `host-header-extensions/scripts/main.md`, so edit the template, not this file. The full tables are in the generated appendix [host-header-extensions/inventory.md](host-header-extensions/inventory.md).

**Question.** Which compiler builtins, attributes, pragmas and language extensions do the headers on the milestone 1 bootstrap host (Ubuntu 26.04 arm64: glibc 2.43, libstdc++ and libgcc from GCC 15.2) use when compiled as C++20 on aarch64? Under which `#if` guards are they pulled in, and which of those guards can Forge steer through the macros it predefines?

**Method.** Primary sources only: the header text from the Ubuntu archive (section 0), the GCC 15.2.0 manual and CPP manual, and eight GCC 15.2.0 source files that hold facts the manual does not state (predefined macros, the builtin, trait and keyword tables). No GCC was run; the research host is macOS. The pipeline was:

1. **Static closure.** Starting from 142 root headers (section 1), every `#include` and `#include_next` was followed regardless of the conditionals around it. Each one was resolved against g++'s search list for this target. Result: 681 headers.
2. **Instrumented preprocessing.** Every header was copied with a marker `#pragma` after each `#if`, `#ifdef`, `#ifndef`, `#elif` and `#else`. Each root was then preprocessed alone (`-E`, `-nostdinc -nostdinc++`, `--target=aarch64-unknown-linux-gnu -std=c++20`) against the copied tree by Apple clang 17, once per configuration below. The markers that survive show which branches were entered. Clang was used only as a preprocessor. GCC's identity was imposed with `-U`/`-D` and a forced include of `gcc15-delta.h`, which holds the predefined macros where GCC 15.2 differs from clang, each taken from `c-cppbuiltin.cc` or `aarch64-c.cc`. A second forced include supplied GCC's answers to every `__has_builtin` query the headers make, derived from `cp-trait.def`, `builtins.def`, the `c_common_reswords` table, `cp/decl.cc` and the manual (appendix C.5). A third forced include was `stdc-predef.h`, as `glibc-c.cc` does for g++.
3. **Scan.** A tokenizer-based scanner records every extension occurrence in the closure together with its stack of enclosing conditionals; comments and string literals are excluded.
   - An occurrence is *reached* in a configuration if the preprocessor entered its conditional block for at least one root. For an occurrence inside a `#define` body, the macro must also be referenced, directly or through other macros, from entered code or from an entered `#if`.
   - Two coverage checks found one name the scanner's tables missed, `__integer_pack`, which is now included: (a) the closure against GCC's `c_common_reswords`; (b) the closure against every builtin name in the manual's index.

Every number below comes from that data; nothing was taken from a secondary write-up.

**Configurations.**

| Name | Identity | Flags beyond `-std=c++20` |
|---|---|---|
| `m1` | GCC 15.2 (`__GNUC__ 15`, `__GNUC_MINOR__ 2`, `__GNUG__ 15`, no `__clang__`) | `-fno-exceptions -fno-rtti -O2`: Forge's milestone 1 build. **"M1" below means this configuration.** |
| `m1-O0` | GCC 15.2 | as m1 with `-O0` |
| `m1-fortify` | GCC 15.2 | as m1 plus `-D_FORTIFY_SOURCE=3`, which Ubuntu's g++ adds by default at `-O2` (section 0) |
| `gcc-eh` | GCC 15.2 | as m1 with exceptions and RTTI on |
| `m1-gnu` | GCC 15.2 | as m1 under `-std=gnu++20` (no `__STRICT_ANSI__`; `__GLIBCXX_TYPE_INT_N_0=__int128`) |
| `clang` | Apple clang 17's own (`__clang__`, `__clang_major__ 17`, `__GNUC__ 4`, `__GNUC_MINOR__ 2`) | `-fno-exceptions -fno-rtti -O2` |
| `neither` | no `__GNUC__`, `__clang__` or related version macros | `-fno-exceptions -fno-rtti -O2` |

The flag lists are in appendix A. PIE and outline atomics are absent from the table because no header in the closure tests `__PIC__`, `__PIE__`, `__pic__`, `__pie__` or any `__ARM_FEATURE_*` macro: `-fPIE` and `-moutline-atomics` change code generation only, never which header text is compiled. Forge's other milestone 1 rules are already in the m1 flags or only exclude code: no `long double` or `__int128` in Forge's own code, no non-trivial `thread_local`, no `-g`.

**Reachability labels.**
- *M1 (n roots)*: the construct appears in entered code for n of the 142 roots.
- *M1 (via macro)*: it sits in a macro body that M1-entered code expands.
- *M1 macro only*: it sits in an entered macro definition that no header expands. It becomes live only when user code uses the macro: `assert`, `va_start`, `offsetof`, `INFINITY`.
- *X only*: reached only in configuration X.
- *not reached*: in no configuration.

**Class labels** (the downstream ticket's buckets):
- **M**: the semantics must be implemented correctly.
- **L**: a call to the same-named library function, or for `abs` the obvious expression, is a correct implementation outside constant evaluation.
- **A**: accepting the construct and ignoring it preserves behaviour.

## 0. Sources and versions

| Package | Version (suite) | Archive URL (`http://ports.ubuntu.com/ubuntu-ports/` + path) | Size | SHA256 (Packages index, matched the download) |
|---|---|---|---|---|
| libc6-dev | 2.43-2ubuntu2.4 (resolute-updates and resolute-security) | `pool/main/g/glibc/libc6-dev_2.43-2ubuntu2.4_arm64.deb` | 1843700 | `f6f7705d3e6bb982c173a42cc5b2516eddebe2d846c4861ee7d7c9d66ebee916` |
| libc6-dev (release pocket, cross-check only) | 2.43-2ubuntu2 (resolute) | `pool/main/g/glibc/libc6-dev_2.43-2ubuntu2_arm64.deb` | 1844200 | `26060610ffbcb3e7260d113e659dbedfe0bacd5dd116affa3bde72431184d328` |
| linux-libc-dev | 7.0.0-43.43 (resolute-updates) | `pool/main/l/linux/linux-libc-dev_7.0.0-43.43_arm64.deb` | 1859028 | `3d6313ac30170df8614618fd1aeb864606c378d90aa18e5d2012aad46861d753` |
| libstdc++-15-dev | 15.2.0-16ubuntu1 (resolute) | `pool/main/g/gcc-15/libstdc++-15-dev_15.2.0-16ubuntu1_arm64.deb` | 2871808 | `f3a53cb1834a15fda5b509332a0f473ca4f1f0dd9a04da355c939df449914f9b` |
| libgcc-15-dev | 15.2.0-16ubuntu1 (resolute) | `pool/main/g/gcc-15/libgcc-15-dev_15.2.0-16ubuntu1_arm64.deb` | 2600202 | `d088c97ff459ab243eb369666dfc43b92f278556e45d72c2def4d7657d728fe4` |
| gcc-15 (man page only) | 15.2.0-16ubuntu1 (resolute) | `pool/main/g/gcc-15/gcc-15_15.2.0-16ubuntu1_arm64.deb` | 528112 | `772d57b952842e600fd7823b2aa217394d78b70756406a6b0e89297eb8d03fe8` |
| gcc-15-aarch64-linux-gnu (not used for headers) | 15.2.0-16ubuntu1 (resolute) | `pool/main/g/gcc-15/gcc-15-aarch64-linux-gnu_15.2.0-16ubuntu1_arm64.deb` | 23124142 | `e3483ce05b22e201393a40a8cea4414144dc73f45ca902dcc026123f76312d6a` |

- **Indexes.** The indexes are `dists/{resolute,resolute-updates,resolute-security}/main/binary-arm64/Packages.gz` under the same base URL. Their `Release` files are dated 23 Apr 2026, 9 Nov 2026 17:22 UTC and 9 Nov 2026 19:40 UTC. Each `Packages.gz` SHA256 matches its `Release` entry:
  - resolute: `1095e9e8f2be837e0b3b3c2415b2f892ca4fd896048833799d51e6adeb3ce297`
  - resolute-updates: `b1a1151d61cc6ddb560c7b6763efb92ab86cfba4d7af12ada7c48a8139fe6f97`
  - resolute-security: `bf3cac7b822075bebc499dc445a54c76162bc6129b4a5f5a3e8a8db8fc86a0c9`
- **Versions.** The newest version of each package across the three suites was used. resolute-security lists linux-libc-dev 7.0.0-42.42 and the release pocket lists 7.0.0-14.14. The headers under `/usr/include` of the two libc6-dev versions are byte-identical (`diff -r`), so the glibc result does not depend on which pocket a host has. The libgcc-15-dev package provides `/usr/lib/gcc/aarch64-linux-gnu/15/include`.
- **Ubuntu driver defaults.** These are from `gcc-15.1`, the man page in the gcc-15 package. "In Ubuntu 24.04 and later versions, `-D_FORTIFY_SOURCE=3`, is set by default, and is activated when `-O` is set to 2 or higher". The man page's other Ubuntu notes cover `-fstack-protector-strong`, `-fstack-clash-protection`, `-fcf-protection` and, from 25.10, `-fzero-init-padding-bits=all`. None of those changes header text.
- **GCC manuals.** The GCC manual is <https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/> and the CPP manual is <https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/>. They were read from the HTML tarballs in the same directory; each `index.html` says "version 15.2.0":
  - `gcc-html.tar.gz`: SHA256 `dfe83e34dfdac265b8b9a9630dfcbb2521f754243026c0a9b466e7ac121e4784`
  - `cpp-html.tar.gz`: SHA256 `6b6eeece2c66a610b416bb572e5bae04be6dd98c09c113772e8e71b2e3749df1`
- **GCC sources.** These are from tag `releases/gcc-15.2.0` (SHA256 prefixes):
  - `gcc/c-family/c-cppbuiltin.cc` (`46f777bb`)
  - `gcc/config/aarch64/aarch64-c.cc` (`8bb80f6e`)
  - `gcc/config/glibc-c.cc` (`0ff050b3`)
  - `gcc/builtins.def` (`457a2c7e`)
  - `gcc/cp/cp-trait.def` (`f34132ef`)
  - `gcc/c-family/c-common.cc` (`da25f3f8`)
  - `gcc/cp/decl.cc` (`3c210acd`)
  - `gcc/coroutine-builtins.def` (`1fb851b7`)
- **Tools.** Apple clang 17.0.0 (clang-1700.0.13.5) was the preprocessor. Its predefines (`clang -x c++ -std=c++20 --target=aarch64-unknown-linux-gnu -nostdinc -nostdinc++ -dM -E /dev/null`) are the "Apple clang 17 value" column below. Python 3 ran the scripts in `host-header-extensions/scripts/`. The scripts never execute anything from the packages.
- **Pipeline.** Each script's docstring gives its arguments. `OUT` is a data directory whose parent also holds `manual/gcc/gcc` and `manual/cpp/cpp`; run every script with `python3 -I`.
  1. `manifest.py` maps logical `/usr/include` paths to the extracted packages.
  2. `hx.py closure` computes the static closure.
  3. `hx.py instrument` writes the marker copies.
  4. `manindex.py` indexes the manuals.
  5. `scan.py` records the extension occurrences.
  6. `clang ... -dM -E /dev/null` writes `OUT/pp/clang-predef.txt`.
  7. Bootstrap: `pp.py ... clang`, then `steer.py`, then `gccanswers.py`, which writes the `__has_builtin` answer header.
  8. `pp.py ... m1 m1-O0 m1-fortify gcc-eh m1-gnu clang neither`, then `steer.py` again.
  9. `report.py` with `main.md` produces this file; with `appendix.md` it produces `inventory.md`.

## 1. Scope and closure

**Roots (142).**
- The 98 C++ library headers of C++20 in libstdc++ (`<algorithm>` to `<version>`, including `<codecvt>`, `<strstream>` and the 21 `<cxxx>` headers).
- The 26 C++ `<xxx.h>` C headers (`<assert.h>` to `<wctype.h>`).
- `<bits/stdc++.h>` and `<cxxabi.h>`.
- The 16 requested POSIX/Linux headers not already listed: `<unistd.h>`, `<fcntl.h>`, `<sys/stat.h>`, `<sys/mman.h>`, `<sys/types.h>`, `<sys/wait.h>`, `<dirent.h>`, `<dlfcn.h>`, `<pthread.h>`, `<sys/time.h>`, `<sys/resource.h>`, `<poll.h>`, `<spawn.h>`, `<execinfo.h>`, `<link.h>` and `<elf.h>`. `<signal.h>`, `<errno.h>` and `<time.h>` are in the C list.

All 142 resolve and all preprocess without error in every configuration.

**Search list** (g++'s order for `aarch64-linux-gnu` C++; section 5 notes it was not confirmed by running g++):
1. `/usr/include/c++/15`
2. `/usr/include/aarch64-linux-gnu/c++/15`
3. `/usr/include/c++/15/backward`
4. `/usr/lib/gcc/aarch64-linux-gnu/15/include`
5. `/usr/local/include`
6. `/usr/include/aarch64-linux-gnu`
7. `/usr/include`

`#include_next` resumes after the directory where the current header was found.

| Package | Headers in static closure | Headers entered in M1 (union over roots) |
|---|---|---|
| libc6-dev | 216 | 192 |
| libgcc-15-dev | 14 | 9 |
| libstdc++-15-dev | 427 | 323 |
| linux-libc-dev | 24 | 24 |
| total | 681 | 548 |

The static closure is an upper bound: it follows includes inside every branch, so it reaches, for example, the parallel-mode and PSTL TBB/OpenMP backends that no configuration enters. Fifteen includes do not resolve (appendix B): BSD/Darwin headers from GCC's `stddef.h`, TBB, OpenMP, `<config.h>`, and `gnu/stubs-lp64_be.h`. None is reached. In this document, "reached" always means the entered set, never the static set.

## 2. Predefined-macro steering surface

Across the closure, 2,695 distinct identifiers appear in `#if` expressions. Of these, 698 are never defined by any header in the closure: they come from the compiler, the command line or the user. Appendix C lists all of them with test counts, the GCC 15.2 value with its source, the Apple clang 17 value, an example site, the verbatim test and the first line it selects. The subsections below cover the ones that select between compiler-specific paths.

### 2.1 Compiler identity

Column *Tests/files/live in M1* counts `#if` lines that test the macro: all of them, the files they are in, and how many are evaluated in M1 (that is, their own enclosing block was entered).

| Macro | Tests/files/live in M1 | g++ 15.2 value (source) | Apple clang 17 value | Example site | Test (verbatim) | First line it selects |
|---|---|---|---|---|---|---|
| `__GNUC__` | 30/17/28 | 15 (cpp manual Common Predefined Macros) | `4` | aarch64/sys/cdefs.h:408 | `#if (defined __GNUC__ && __GNUC__ >= 2) \|\| (__clang_major__ >= 4)` | `# define __REDIRECT(name, proto, alias) name proto __asm__ (__ASMNAME (#alias))` |
| `__GNUC_MINOR__` | 1/1/1 | 2 (cpp manual) | `2` | features.h:178 | `#if defined __GNUC__ && defined __GNUC_MINOR__` | `# define __GNUC_PREREQ(maj, min) ((__GNUC__ << 16) + __GNUC_MINOR__ >= ((maj) << 16) + (mi` |
| `__GNUG__` | 2/1/2 | 15 (c-cppbuiltin.cc) | `4` | gcc/stddef.h:228 | `#if !(defined (__GNUG__) && defined (size_t))` | `typedef __SIZE_TYPE__ size_t;` |
| `__clang__` | 13/6/12 | undefined (-) | `1` | c++/aarch64/bits/c++config.h:515 | `#if !defined _GLIBCXX_CLANG && defined __clang__` | `# define _GLIBCXX_CLANG __clang__` |
| `__clang_major__` | 13/3/11 | undefined (-) | `17` | aarch64/sys/cdefs.h:42 | `#if (defined __has_attribute && (!defined __clang_minor__ \|\| 3 < __clang_major__ + (5 <= __clang_min` | `# define __glibc_has_attribute(attr) __has_attribute (attr)` |
| `__clang_minor__` | 4/2/4 | undefined (-) | `0` | aarch64/sys/cdefs.h:42 | `#if (defined __has_attribute && (!defined __clang_minor__ \|\| 3 < __clang_major__ + (5 <= __clang_min` | `# define __glibc_has_attribute(attr) __has_attribute (attr)` |
| `__clang_literal_encoding__` | 2/2/1 | undefined | `"UTF-8"` | c++/bits/unicode.h:1064 | `#elif defined __clang_literal_encoding__` | `if constexpr (is_same_v<_CharT, char>)` |
| `__clang_wide_literal_encoding__` | 1/1/0 | undefined | `"UTF-32"` | c++/bits/unicode.h:1067 | `#if defined _GLIBCXX_USE_WCHAR_T && defined __clang_wide_literal_encoding__` | `else` |
| `_GLIBCXX_CLANG` | 14/7/9 | undefined (c++config.h:515 defines it from __clang__) | `undefined` | c++/aarch64/bits/c++config.h:515 | `#if !defined _GLIBCXX_CLANG && defined __clang__` | `# define _GLIBCXX_CLANG __clang__` |
| `__INTEL_COMPILER` | 14/3/12 | undefined | `undefined` | c++/pstl/glue_execution_defs.h:22 | `#if defined(__INTEL_COMPILER)` | `template <class _Tp>` |
| `__EDG__` | 1/1/1 | undefined | `undefined` | c++/ext/aligned_buffer.h:55 | `#ifdef __EDG__` | `struct _Tp2 { _Tp _M_t; };` |
| `_MSC_VER` | 8/2/7 | undefined | `undefined` | c++/pstl/pstl_config.h:33 | `#ifdef _MSC_VER` | `# define _PSTL_PRAGMA(x) __pragma(x)` |
| `__CUDACC__` | 4/4/4 | undefined | `undefined` | c++/bits/std_abs.h:140 | `#if !defined(__STRICT_ANSI__) && defined(_GLIBCXX_USE_FLOAT128) && !defined(__CUDACC__)` | `__extension__ inline _GLIBCXX_CONSTEXPR` |
| `__TINYC__` | 1/1/1 | undefined | `undefined` | aarch64/sys/cdefs.h:444 | `#if !(defined __GNUC__ \|\| defined __clang__ \|\| defined __TINYC__)` | `# define __attribute__(xyz)` |
| `__HP_cc` | 1/1/1 | undefined | `undefined` | aarch64/sys/cdefs.h:378 | `#if defined __STDC_VERSION__ && __STDC_VERSION__ >= 199901L && !defined __HP_cc` | `# define __flexarr []` |
| `__ICC` | 1/1/0 | undefined | `undefined` | c++/parallel/balanced_quicksort.h:400 | `#if !defined(__ICC) && !defined(__ECC)` | `# pragma omp flush` |
| `__ECC` | 1/1/0 | undefined | `undefined` | c++/parallel/balanced_quicksort.h:400 | `#if !defined(__ICC) && !defined(__ECC)` | `# pragma omp flush` |
| `__BIONIC__` | 2/1/1 | undefined | `undefined` | c++/aarch64/bits/gthr-default.h:132 | `#ifndef __BIONIC__` | `__gthrw(pthread_cancel)` |
| `__GNUC_STDC_INLINE__` | 2/1/2 | 1 unless flag_gnu89_inline (c-cppbuiltin.cc) | `undefined` | aarch64/sys/cdefs.h:618 | `#if (!defined __cplusplus \|\| __GNUC_PREREQ (4,3) \|\| (defined __clang__ && (defined __GNUC_STDC_INLIN` | `# if defined __GNUC_STDC_INLINE__ \|\| defined __cplusplus` |
| `__GNUC_GNU_INLINE__` | 1/1/1 | 1 if flag_gnu89_inline, else undefined (c-cppbuiltin.cc) | `1` | aarch64/sys/cdefs.h:618 | `#if (!defined __cplusplus \|\| __GNUC_PREREQ (4,3) \|\| (defined __clang__ && (defined __GNUC_STDC_INLIN` | `# if defined __GNUC_STDC_INLINE__ \|\| defined __cplusplus` |

**Version thresholds.**
- glibc wraps most version tests in `__GNUC_PREREQ (maj, min)` (features.h:178), defined as `((__GNUC__ << 16) + __GNUC_MINOR__ >= ((maj) << 16) + (min))`. Without `__GNUC__` or `__GNUC_MINOR__` it is `0` (features.h:182). There are 149 sites with 33 distinct thresholds, from (2, 4) up to **(13, 0)**; (13, 0) has 29 sites, all `_FloatN` handling. So any `__GNUC__ >= 13` selects exactly the glibc code that 15.2 does.
- `__glibc_clang_prereq (maj, min)` (features.h:189) is the clang counterpart: 14 sites, 9 thresholds up to (12, 0). glibc also tests `__clang_major__` directly, at thresholds 3, 4, 5 and 9 (cdefs.h:84, 218, 230, 408, 653).
- libstdc++ tests versions in four places:
  - `__GNUC__ >= 5 && !defined(_GLIBCXX_CLANG)` (bits/locale_facets_nonio.tcc:1476)
  - `_PSTL_GCC_VERSION >= 100000` and `>= 40900` (pstl/pstl_config.h:85, 124, 130; `<execution>` only)
  - `__clang_major__ >= 20` for the `__array_rank` builtin (type_traits:1488, 3661)
- Everything else in libstdc++ asks `__has_builtin` (section 2.2) or tests `_GLIBCXX_CLANG`. libstdc++ defines `_GLIBCXX_CLANG` from `__clang__` (c++config.h:515) "as an alternate macro to test for clang". A command-line `-D_GLIBCXX_CLANG=0` is turned into "not defined" (c++config.h:519).

### 2.2 Query operators

These are answered by the compiler, independent of the identity macros. Appendix C.5 lists every operand with its sites and GCC's answer.

| Operator (directly or via wrapper) | Distinct operands | Sites | Evaluated in M1 | What the answers select |
|---|---|---|---|---|
| `__has_builtin`, `_GLIBCXX_HAS_BUILTIN`, `_GLIBCXX_USE_BUILTIN_TRAIT`, `__glibc_has_builtin` | 61 | 109 | 93 | builtin vs library template for 31 traits and the three generic bit builtins (`_GLIBCXX_USE_BUILTIN_TRAIT`); `__builtin_clear_padding` in `<atomic>`; `__integer_pack` vs `__make_integer_seq`; `__builtin_operator_new`; `__builtin_bit_cast` for `std::bit_cast`; `__builtin_is_constant_evaluated` for `std::__is_constant_evaluated` |
| `__has_attribute`, `__glibc_has_attribute` | 18 | 19 | 19 | glibc's attribute macros fall back to `__has_attribute` when `__GNUC_PREREQ` fails; libstdc++ tests `__init_priority__` (iostream:80), `__assume__` (stl_bvector.h:194), `__always_inline__` (gthr-default.h:48) |
| `__has_cpp_attribute` | 1 | 1 | 1 | `__no_unique_address__` (tuple:89) |
| `__has_feature`, `__has_extension` (via `__glibc_has_extension`) | 5 | 5 | 4 | `address_sanitizer`, `thread_sanitizer`, `modules`; `__attribute_deprecated_with_message__`, `c_generic_selections` |
| `__has_include` | 10 | 11 | 11 | four Linux UAPI headers; `<pstl/pstl_config.h>`, `<stdint-gcc.h>`, `<sys/single_threaded.h>`, `<sanitizer/tsan_interface.h>` |
| `__is_identifier` (`#ifdef`) | 1 | 1 | 1 | c++config.h:894: if defined, `_GLIBCXX_HAS_BUILTIN(B)` becomes `(__has_builtin(B) \|\| ! __is_identifier(B))` |

Facts about the answers:
- Of the 61 `__has_builtin` operands, GCC 15.2 has 58. It lacks three: `__make_integer_seq` (Clang's, utility.h:148, 176), `__builtin_nansq` (an x86-only builtin per the manual; limits:2153) and `__builtin_fclose` (in no GCC table; wchar.h:730, which then omits a `malloc(fclose)` deallocator attribute).
- new_allocator.h:115 and stl_tempbuf.h:69 test `__has_builtin(__builtin_operator_new) >= 201802L`, a value comparison rather than a truth test. The CPP manual says only that `__has_builtin` evaluates to "a constant integer with a nonzero value" (`__has_builtin` page). The m1 run assumed GCC answers 1, which selects `::operator new`; see section 5.
- GCC 15.2's CPP manual documents `__has_feature` and `__has_extension` ("only provided for compatibility with Clang"). `__is_identifier` is Clang-only.

### 2.3 Language-mode, option and type macros that select paths

All values are g++ 15.2's for the m1 flags, with their source. Appendix C.2 to C.4 lists the rest.

| Macro | g++ 15.2 (source) | What it selects (example site) |
|---|---|---|
| `__STRICT_ANSI__` | 1 (`c-cppbuiltin.cc`: `if (flag_iso)`) | strict-mode `__int128` specializations (bits/cpp_type_traits.h:560, iterator_concepts.h:220, limits:1665). Under gnu++20 instead, `__int128` is an integral type to `<type_traits>`, `<limits>` and `std::hash` (appendix D.7). |
| `__GLIBCXX_TYPE_INT_N_0` | undefined; `__int128` without `flag_iso` (`c-cppbuiltin.cc`: `!flag_iso \|\| bitsize == POINTER_SIZE`) | 15 tests in 10 files (type_traits:419, cstddef:96, functional_hash.h:177) |
| `__SIZEOF_INT128__` | 16 | every M1 use of `__int128` (23 tests in 14 files: `<format>`, `<charconv>`, `<ranges>`, `<random>`, `<limits>`, `<compare>`) |
| `__OPTIMIZE__` (and `__NO_INLINE__`, `__OPTIMIZE_SIZE__`) | 1 at `-O1` and up | features.h:552 `__USE_EXTERN_INLINES` (glibc's extern-inline bodies); string.h/strings.h `__OPTIMIZE__` inline overloads that call `__builtin_strchr` etc. **Without it, libstdc++ defines `_GLIBCXX_ASSERTIONS`** (c++config.h:601), which also sets `_GLIBCXX_EXTERN_TEMPLATE -1` (c++config.h:610), so `std::string` is no longer an extern template. m1 vs m1-O0 differ in 36 + 4 blocks. |
| `__cpp_exceptions`, `__EXCEPTIONS` | undefined (`-fno-exceptions`) | `_GLIBCXX_THROW_OR_ABORT(E)` is `(__builtin_abort(), (void)(E))` (c++config.h:264); `__try`/`__catch` become `if (true)`/`if (false)` (bits/exception_defines.h:38); pthread.h:565 drops the C++ cleanup class. 30 blocks are entered only in gcc-eh and 18 only in m1 (appendix D.5). |
| `__cpp_rtti`, `__GXX_RTTI` | undefined (`-fno-rtti`) | `std::any::type()`, `std::function::target_type()`, `shared_ptr` deleter lookup, `<locale>` facet checks (any:336, std_function.h:188, shared_ptr_base.h:539) |
| `_FORTIFY_SOURCE` | not predefined by GCC; Ubuntu's driver adds 3 at `-O2` | features.h:449 then sets `__USE_FORTIFY_LEVEL`. 15 more headers and 122 more blocks are entered, adding 16 `__builtin___*_chk` builtins, `__builtin_dynamic_object_size`, `__builtin_va_arg_pack` and 88 more `__REDIRECT` declarations (sections 3.7, 3.11). |
| `__cpp_sized_deallocation` | 201309L (`c-cppbuiltin.cc`: `if (flag_sized_deallocation)`) | sized `operator delete` declarations and their use in allocators (new:147, 190; new_allocator.h:158; stl_tempbuf.h:104). Apple clang 17 does not predefine it. |
| `__FLT32_DIG__`, `__FLT64_DIG__`, `__FLT128_DIG__`, `__FLT16_DIG__`, `__BFLT16_DIG__` | defined (`builtin_define_float_constants`) | `std::formatter` and `std::numeric_limits` for `_Float32`, `_Float64`, `_Float128`, `_Float16` (format:2761, 2783, 2805, 3857; limits:1995) and `__gnu_cxx::__bfloat16_t = __decltype(0.0bf16)` (c++config.h:886). Apple clang predefines none but `__FLT16_DIG__`. |
| `__STDCPP_FLOAT16_T__` and the other `__STDCPP_*_T__` | undefined (`c-cppbuiltin.cc`: only `cxx_dialect > cxx20`) | C++23 extended floating-point specializations in `<atomic>`, `<cmath>`, `<limits>`, `<format>` stay off |
| `__GNUC_EXECUTION_CHARSET_NAME`, `__GNUC_WIDE_EXECUTION_CHARSET_NAME` | `"UTF-8"`, `"UTF-32LE"` | literal-encoding detection (bits/unicode.h:1027, 1040); clang's equivalent is `__clang_literal_encoding__` (unicode.h:1064) |
| `__GCC_IEC_559`, `__GCC_IEC_559_COMPLEX` | 2, 2 (`cpp_iec_559_value`) | stdc-predef.h:36, 46: `__STDC_IEC_559__` and friends are defined only if > 0, and unconditionally when the macro is absent |
| `__WCHAR_MIN__` | `0U` | bits/wchar.h:41 `__WCHAR_MIN`; otherwise a `L'\0' - 1 > 0` test (bits/wchar.h:43) |
| `__GCC_ATOMIC_TEST_AND_SET_TRUEVAL`, `__GCC_ATOMIC_*_LOCK_FREE`, `__GCC_DESTRUCTIVE_SIZE` | target values | `atomic_flag` storage type (atomic_base.h:179), `__cpp_lib_atomic_lock_free_type_aliases` (version.h:839), `hardware_destructive_interference_size` (version.h:444) |
| `__DEPRECATED` | 1 | `_GLIBCXX_DEPRECATED` attributes (c++config.h:109) and `<strstream>`'s `#warning` (backward/backward_warning.h:32) |
| `__GXX_WEAK__` | 1 | gthr-default.h:106. The weak-reference path also needs `_GLIBCXX_GTHREAD_USE_WEAK`, which is 0 on this glibc, so `weakref` is never reached. |

Some compiler-predefined macros are used as values in M1-reached code, not tested. A Forge that replaces the compiler must supply them too (appendix C.8 lists them all):
- type names (`__INT64_TYPE__` and others);
- limits and float characteristics for `<limits.h>`, `<float.h>` and `<limits>`;
- `__ATOMIC_RELAXED` to `__ATOMIC_SEQ_CST` and the `__GCC_ATOMIC_*_LOCK_FREE` set;
- `__STDCPP_DEFAULT_NEW_ALIGNMENT__`, `__GCC_CONSTRUCTIVE_SIZE`;
- `__USER_LABEL_PREFIX__`, which `__REDIRECT` pastes into every asm label (cdefs.h:422).

### 2.4 What changes with the reported identity

Conditional blocks (and whole headers) entered in one configuration but not the other:

| Configurations | Blocks only in first | Blocks only in second | Headers only in first | Headers only in second | Headers entered only in second |
|---|---|---|---|---|---|
| `m1` vs `clang` | 103 | 78 | 0 | 0 |  |
| `m1` vs `neither` | 209 | 140 | 2 | 0 |  |
| `m1` vs `m1-O0` | 36 | 4 | 2 | 0 |  |
| `m1` vs `gcc-eh` | 18 | 30 | 0 | 0 |  |
| `m1` vs `m1-fortify` | 5 | 122 | 0 | 15 | aarch64/bits/fcntl-linux-fortify.h, aarch64/bits/fcntl2.h, aarch64/bits/poll2.h, aarch64/bits/select-decl.h, aarch64/bits/select2.h, aarch64/bits/setjmp2.h, aarch64/bits/stdio2-decl.h, aarch64/bits/stdio2.h, aarch64/bits/stdlib.h, aarch64/bits/string_fortified.h, aarch64/bits/strings_fortified.h, aarch64/bits/unistd-decl.h, aarch64/bits/unistd.h, aarch64/bits/wchar2-decl.h, aarch64/bits/wchar2.h |
| `m1` vs `m1-gnu` | 9 | 39 | 0 | 3 | aarch64/bits/cmathcalls.h, aarch64/bits/mathdef.h, complex.h |

The full block lists are in appendix D. The facts by theme follow; the runs are described in the configuration table at the top.

**Reporting GCC 15.2** (the m1 run) has these consequences for the headers.

*Identity and version tests.*
- **_FloatN become distinct built-in types.** In C++, once `__GNUC_PREREQ (13, 0)` holds, glibc stops `typedef`-ing `_Float32`, `_Float64`, `_Float128`, `_Float32x` and `_Float64x` to float, double and long double (bits/floatn.h:58-84, bits/floatn-common.h:90-288). It switches to the `f32`, `f64`, `f128`, `f32x` and `f64x` literal suffixes and `_Complex _FloatN`. math.h:1532-1583 then specializes `__iseqsig_type` for each of them next to the float/double/long double specializations. That compiles only if the types are distinct.
- **aarch64 vector-math declarations appear** (bits/math-vector.h:190, 200; 8 roots via `<cmath>`/`<math.h>`). AdvSIMD functions over `__Float32x4_t`/`__Float64x2_t` with `__attribute__ ((__aarch64_vector_pcs__))` need GCC 9; SVE functions over the sizeless `__SVFloat32_t`, `__SVFloat64_t` and `__SVBool_t` need GCC 10. Nothing in the headers calls them, but the declarations must parse.
- **glibc's attribute macros are no longer empty.**
  - `__LEAF` (cdefs.h:64), `__attribute_alloc_size__` (459) and `__warnattr`/`__errordecl` (365)
  - `__va_arg_pack` (637), `__attribute_nonstring__` (699) and `__attribute_copy__` (710)
  - `__attr_access`/`__attr_access_none` (843, 859) and `__attr_dealloc` (870), the two-argument `malloc` attribute
  - `__builtin_bswap16/32/64` in bits/byteswap.h:36-72, and `#pragma GCC diagnostic` in bits/stdlib-bsearch.h:32
- **More const-correct C++ overloads.** strings.h:26 and wchar.h:68 add `extern "C++"` overloads carrying asm labels (`index`, `rindex`, `wcschr` and so on). They test only `__GNUC_PREREQ (4, 4)`; string.h:40 also accepts `__glibc_clang_prereq (3, 5)`.
- **libstdc++'s GCC-only branches are taken:** `__GNUC__ >= 5` in locale_facets_nonio.tcc:1476, `__has_attribute(__assume__) && !defined(_GLIBCXX_CLANG)` in stl_bvector.h:194, and no `_GLIBCXX_CLANG` sections.

*Other GCC predefines* (independent of the identity macros):
- `__cpp_sized_deallocation`
- the `__FLT32_DIG__` family and `__BFLT16_DIG__`, which brings in the `bf16` literal suffix at c++config.h:889
- `__GNUC_EXECUTION_CHARSET_NAME`, `__GCC_IEC_559` and `__WCHAR_MIN__` (section 2.3)

*GCC's `__has_builtin` answers:*
- `__integer_pack` in place of `__make_integer_seq` (utility.h:154, 178)
- `__builtin_clear_padding` (atomic:248; atomic_base.h:957, 975)
- `__has_unique_object_representations`
- the layout-compatibility and pointer-interconvertibility traits (version.h:1034, 1054; type_traits:3872-3925)
- `__builtin_toupper` in `<format>` (format:65, 1629, 2931)
- `__remove_reference`, `__is_invocable`, `__is_nothrow_invocable`, `__array_rank` builtin traits

Apple clang 17 answered 0 for these, so they show up in the m1/clang diff.

**Reporting clang** (the clang run used Apple clang 17's own predefines and `__has_*` answers):
- **libstdc++ adjustments.** `_GLIBCXX_CLANG` is defined (c++config.h:515), and `_GLIBCXX_HAS_BUILTIN` adds the `__is_identifier` test (c++config.h:894). libstdc++ then uses:
  - `__make_integer_seq` (utility.h:148, 176)
  - `__builtin_operator_new`/`__builtin_operator_delete`, because Apple clang answers 201802L (new_allocator.h:115, stl_tempbuf.h:69)
  - `#pragma clang diagnostic` around `<complex>` (complex:55, 2745)
  - `__clang_literal_encoding__` (unicode.h:1064)
- **glibc falls back.** Apple clang reports `__GNUC__ 4`, `__GNUC_MINOR__ 2`; glibc's own comment says clang's values "are fixed at 4 and 2 respectively" (features.h:185-188). So every `__GNUC_PREREQ` above (4, 2) is false. glibc's `__glibc_clang_prereq` alternatives restore only some paths: the math.h classification builtins (math.h:1095-1165), string.h const overloads (string.h:40), `_Pragma` warnings (cdefs.h:806) and the vector-math declarations (math-vector.h:194 with `__neon_vector_type__`, 200). The rest fall back:
  - byteswap uses the `__bswap_constant_*` macros (byteswap.h:38, 53, 74);
  - `_FloatN` are typedefs (floatn.h:58-84);
  - strings.h and wchar.h lose their C++ overloads;
  - `__attr_access`, `__attr_dealloc`, `__nonstring__` and `__copy__` become empty;
  - pthread.h:770 declares `__sigsetjmp` without a redirect.
- **Clang-only macros.** `__attribute_overloadable__` becomes `__attribute__((__overloadable__))` (cdefs.h:149), and the clang fortify macros (cdefs.h:218-323) are defined but reached only with `_FORTIFY_SOURCE`.
- **A Forge claiming clang** would choose its own `__clang_major__`. The thresholds that matter are 20 (libstdc++), 12 (`__glibc_clang_prereq`) and 9 (fortify), plus whatever `__GNUC__` it reports alongside. Apple clang's 4.2 value is not forced on it.

**Reporting neither** (the neither run removed `__GNUC__`, `__GNUC_MINOR__`, `__GNUC_PATCHLEVEL__`, `__clang__` and its version macros and the inline-mode macros; caveats in section 5):
- **glibc treats the compiler as non-GNU.**
  - cdefs.h:107-118 defines `__THROW`, `__THROWNL` and `__NTH` as empty, so C library functions lose `noexcept (true)`, which glibc uses for C++ at cdefs.h:84-86.
  - cdefs.h:444 defines `__attribute__(xyz)` as empty for the rest of the translation unit, erasing libstdc++'s GNU attributes as well.
  - cdefs.h:646 defines `__extension__` as empty, and cdefs.h:653-658 does the same for `__restrict`.
  - cdefs.h:408 leaves `__REDIRECT` undefined. The 41 asm-label renames of M1 become object-like macros instead, for example `#define strtol __isoc23_strtol` (stdlib.h:252-275); `<cstdlib>`'s `using ::strtol;` then follows the macro.
  - features.h:552 no longer sets `__USE_EXTERN_INLINES`.
  - limits.h:37 computes the limits itself, and limits.h:122 no longer `#include_next`s GCC's `<limits.h>`.
  - math.h:48-114 defines `HUGE_VAL` as `1e10000`, and `INFINITY`/`NAN` without builtins.
  - assert.h:191-197 makes `__ASSERT_FUNCTION` `((const char *) 0)` in C++, because `__STDC_VERSION__` is not defined there; `__PRETTY_FUNCTION__` is no longer used.
  - stdio.h:55 and wchar.h:41 take `va_list` from `<stdarg.h>` instead of `__gnuc_va_list`.
- **libstdc++ barely changes.** Apart from locale_facets_nonio.tcc:1476 and the PSTL version tests, it does not test `__GNUC__`. Its `__has_builtin` paths were unchanged in this run because clang's answers were kept.

**Same identity, other options:**
- `-O0` adds `_GLIBCXX_ASSERTIONS` and removes the extern inlines (section 2.3).
- Exceptions and RTTI on switch 30 blocks in and 18 out.
- `_FORTIFY_SOURCE=3` adds 122 blocks in 15 headers.
- gnu++20 adds `<complex.h>`'s C99 complex path (`_Complex_I` with the `i` constant suffix) and `__int128` as an integral type.

## 3. Inventory

Each table lists the entries reached in M1, then names the others. The appendix (section F) has every row.

Columns:
- *Uses/files* counts all occurrences in the static closure.
- *Representative site* is an M1-reached occurrence outside a `#define` where one exists.
- *Innermost guard* is the nearest enclosing conditional other than an include guard, verbatim. An `#else` names its `#if`; `(unconditional)` means only the include guard encloses it.
- The semantics note is the first sentence of the GCC 15.2 manual entry, linked, plus a "Forge:" remark where the manual's text is not the whole story.
- Builtins that appear in no manual page are attributed to the GCC table that defines them (`builtins.def`, `cp-trait.def`, `cp/decl.cc`, `c_common_reswords`).

### 3.1 Type traits

There are 60 trait keywords: the 59 of `cp-trait.def` used by the headers, plus `__integer_pack`. Almost all uses are in `<type_traits>`, and all but `__is_scoped_enum` (C++23) are reached in M1.

Of the 59 reached, 37 are named in some `__has_builtin`-style test. For 30 of them the test is `_GLIBCXX_USE_BUILTIN_TRAIT(T)`, which chooses between the builtin and a library template written in standard C++. Naming a trait in one test does not guard every use, though, so the per-use picture is:

- **32 are used only under a conditional that names them.** These are the 30 `_GLIBCXX_USE_BUILTIN_TRAIT` traits plus `__is_layout_compatible` and `__is_pointer_interconvertible_base_of`. If Forge's `__has_builtin` answered 0 for them, libstdc++ would fall back or omit the feature.
- **27 have at least one M1-reached use with no such conditional**, so they must work whatever `__has_builtin` says:
  - `__is_same` (bits/utility.h:115), `__is_trivially_assignable` (stl_algobase.h:417) and `__is_trivially_constructible`, which are tested elsewhere;
  - `__has_unique_object_representations` and `__is_aggregate`, which are tested only indirectly through c++config.h's `_GLIBCXX_HAVE_BUILTIN_*` macros;
  - 22 that are never tested: `__has_trivial_constructor`, `__has_trivial_destructor`, `__has_virtual_destructor`, `__is_abstract`, `__is_assignable`, `__is_base_of`, `__is_class`, `__is_constructible`, `__is_empty`, `__is_enum`, `__is_final`, `__is_literal_type`, `__is_nothrow_assignable`, `__is_nothrow_constructible`, `__is_pod`, `__is_polymorphic`, `__is_standard_layout`, `__is_trivial`, `__is_trivially_copyable`, `__is_union`, `__underlying_type` and `__integer_pack`. `__integer_pack` sits in the `#else` of `__has_builtin(__make_integer_seq)`.

Two caveats:
- `<type_traits>` declares its own class templates `std::__is_invocable` and `std::__is_nothrow_invocable` (type_traits:3215, 3266) and uses them as `__is_invocable<...>`. It also uses the GCC traits of the same names as `__is_invocable(...)` (type_traits:3303, 3333). So the same identifier must work both ways, told apart by context; the scanner counts only the `(` form, plus `__type_pack_element<...>`, which is a type trait taking template-argument syntax (bits/utility.h:236).
- `__integer_pack (length)` is documented on the manual's Type-Traits page ("expands to a template argument pack containing integers from 0 to length-1").

The three trait builtins with a `__builtin_` prefix follow; the full table of keywords is appendix F.1.

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_is_corresponding_member` | builtin (trait) | M | 1/1 | c++/type_traits:3895 | `#if __has_builtin(__builtin_is_corresponding_member)` | M1 (75 roots) | cp/decl.cc (not in manual) |
| `__builtin_is_pointer_interconvertible_with_class` | builtin (trait) | M | 1/1 | c++/type_traits:3925 | `#if __has_builtin(__builtin_is_pointer_interconvertible_with_class)` | M1 (75 roots) | cp/decl.cc (not in manual) |

Not reached in M1 (rows in the appendix): `__builtin_is_virtual_base_of` (not reached).

### 3.2 Memory, bit, overflow and math builtins

**Bit, byte-swap and overflow.**

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_add_overflow` | builtin (bit/overflow) | M | 8/8 | c++/bits/chrono_io.h:2301 | `#if __cplusplus >= 202002L` | M1 (5 roots) | [Integer-Overflow-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Integer-Overflow-Builtins.html#index-_005f_005fbuiltin_005fadd_005foverflow): These built-in functions promote the first two operands into infinite precision signed type and perform addition on those promoted operands. |
| `__builtin_bswap16` | builtin (bit/overflow) | M | 2/2 | aarch64/bits/byteswap.h:37 | `#if __GNUC_PREREQ (4, 8)` | M1 (47 roots) | [Byte-Swapping-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Byte_002dSwapping-Builtins.html#index-_005f_005fbuiltin_005fbswap16): Returns x with the order of the bytes reversed; for example, 0xabcd becomes 0xcdab. |
| `__builtin_bswap32` | builtin (bit/overflow) | M | 2/2 | aarch64/bits/byteswap.h:52 | `#if __GNUC_PREREQ (4, 3)` | M1 (47 roots) | [Byte-Swapping-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Byte_002dSwapping-Builtins.html#index-_005f_005fbuiltin_005fbswap32): Similar to __builtin_bswap16, except the argument and return types are 32-bit. |
| `__builtin_bswap64` | builtin (bit/overflow) | M | 4/2 | aarch64/bits/byteswap.h:73 | `#if __GNUC_PREREQ (4, 3)` | M1 (47 roots) | [Byte-Swapping-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Byte_002dSwapping-Builtins.html#index-_005f_005fbuiltin_005fbswap64): Similar to __builtin_bswap32, except the argument and return types are 64-bit. |
| `__builtin_clzg` | builtin (bit/overflow) | M | 2/2 | c++/bit:209 | `#if _GLIBCXX_USE_BUILTIN_TRAIT(__builtin_clzg)` | M1 (56 roots) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fclzg): Similar to __builtin_clz, except the argument is type-generic unsigned integer (standard, extended or bit-precise) and there is optional second argument with int type. |
| `__builtin_clzl` | builtin (bit/overflow) | M | 3/3 | c++/bits/hashtable_policy.h:666 | `(unconditional)` | M1 (5 roots) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fclzl): Similar to __builtin_clz, except the argument type is unsigned long. |
| `__builtin_clzll` | builtin (bit/overflow) | M | 9/6 | c++/bits/hashtable_policy.h:665 | `(unconditional)` | M1 (16 roots) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fclzll): Similar to __builtin_clz, except the argument type is unsigned long long. |
| `__builtin_ctzg` | builtin (bit/overflow) | M | 1/1 | c++/bit:266 | `#if _GLIBCXX_USE_BUILTIN_TRAIT(__builtin_ctzg)` | M1 (56 roots) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fctzg): Similar to __builtin_ctz, except the argument is type-generic unsigned integer (standard, extended or bit-precise) and there is optional second argument with int type. |
| `__builtin_ctzl` | builtin (bit/overflow) | M | 6/2 | c++/bitset:361 | `(unconditional)` | M1 (&lt;bits/stdc++.h&gt;, &lt;bitset&gt;, &lt;regex&gt;) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fctzl): Similar to __builtin_ctz, except the argument type is unsigned long. |
| `__builtin_mul_overflow` | builtin (bit/overflow) | M | 13/9 | c++/bits/allocator.h:198 | `#if __cplusplus > 201703L` | M1 (49 roots) | [Integer-Overflow-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Integer-Overflow-Builtins.html#index-_005f_005fbuiltin_005fmul_005foverflow): These built-in functions are similar to the add overflow checking built-in functions above, except they perform multiplication, instead of addition. |
| `__builtin_popcountg` | builtin (bit/overflow) | M | 1/1 | c++/bit:308 | `#if _GLIBCXX_USE_BUILTIN_TRAIT(__builtin_popcountg)` | M1 (56 roots) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fpopcountg): Similar to __builtin_popcount, except the argument is type-generic unsigned integer (standard, extended or bit-precise). |
| `__builtin_popcountl` | builtin (bit/overflow) | M | 3/2 | c++/bitset:248 | `(unconditional)` | M1 (&lt;bits/stdc++.h&gt;, &lt;bitset&gt;, &lt;regex&gt;) | [Bit-Operation-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Bit-Operation-Builtins.html#index-_005f_005fbuiltin_005fpopcountl): Similar to __builtin_popcount, except the argument type is unsigned long. |

Not reached in M1 (rows in the appendix): `__builtin_bswap128` (not reached), `__builtin_clz` (not reached), `__builtin_ctz` (not reached), `__builtin_ctzll` (not reached), `__builtin_popcount` (not reached), `__builtin_popcountll` (not reached), `__builtin_sub_overflow` (not reached).

**Memory and string library builtins** (class L: libstdc++ calls them only outside constant evaluation, behind `std::__is_constant_evaluated()`; checked in char_traits.h, array, stl_algobase.h, not proven for every site).

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_abs` | builtin (library) | L | 2/1 | c++/bits/chrono_io.h:975 | `#if __cplusplus >= 202002L` | M1 (&lt;bits/stdc++.h&gt;, &lt;chrono&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `abs`. |
| `__builtin_free` | builtin (library) | L | 1/1 | aarch64/sys/cdefs.h:875 (in `#define __attr_dealloc_free`) | `#if __GNUC_PREREQ (11, 0)` | M1 (via macro) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `free`. |
| `__builtin_index` | builtin (library) | L | 2/1 | strings.h:57 | `#if defined __OPTIMIZE__` | M1 (&lt;bits/stdc++.h&gt;, &lt;cstring&gt;, &lt;string.h&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `index`. |
| `__builtin_labs` | builtin (library) | L | 1/1 | c++/bits/std_abs.h:62 | `#ifndef __CORRECT_ISO_CPP_STDLIB_H_PROTO` | M1 (40 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `labs`. |
| `__builtin_llabs` | builtin (library) | L | 1/1 | c++/bits/std_abs.h:67 | `#ifdef _GLIBCXX_USE_LONG_LONG` | M1 (40 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `llabs`. |
| `__builtin_memchr` | builtin (library) | L | 7/5 | c++/bits/char_traits.h:405 | `(unconditional)` | M1 (54 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `memchr`. |
| `__builtin_memcmp` | builtin (library) | L | 9/7 | c++/array:318 | `#if __cpp_lib_three_way_comparison` | M1 (56 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `memcmp`. |
| `__builtin_memcpy` | builtin (library) | L | 37/13 | c++/aarch64/bits/messages_members.h:58 | `(unconditional)` | M1 (47 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `memcpy`. |
| `__builtin_memmove` | builtin (library) | L | 16/5 | c++/bits/char_traits.h:248 | `(unconditional)` | M1 (53 roots) | builtins.def (not in manual) |
| `__builtin_memset` | builtin (library) | L | 17/10 | c++/bits/char_traits.h:293 | `(unconditional)` | M1 (53 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `memset`. |
| `__builtin_rindex` | builtin (library) | L | 2/1 | strings.h:85 | `#if defined __OPTIMIZE__` | M1 (&lt;bits/stdc++.h&gt;, &lt;cstring&gt;, &lt;string.h&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `rindex`. |
| `__builtin_strchr` | builtin (library) | L | 5/3 | c++/bits/regex_scanner.tcc:100 | `(unconditional)` | M1 (4 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strchr`. |
| `__builtin_strcmp` | builtin (library) | L | 17/8 | c++/aarch64/bits/messages_members.h:54 | `(unconditional)` | M1 (38 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strcmp`. |
| `__builtin_strlen` | builtin (library) | L | 8/6 | c++/aarch64/bits/messages_members.h:56 | `(unconditional)` | M1 (42 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strlen`. |
| `__builtin_strpbrk` | builtin (library) | L | 3/2 | string.h:335 | `#ifdef __OPTIMIZE__` | M1 (&lt;bits/stdc++.h&gt;, &lt;cstring&gt;, &lt;string.h&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strpbrk`. |
| `__builtin_strrchr` | builtin (library) | L | 3/2 | string.h:281 | `#ifdef __OPTIMIZE__` | M1 (&lt;bits/stdc++.h&gt;, &lt;cstring&gt;, &lt;string.h&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strrchr`. |
| `__builtin_strstr` | builtin (library) | L | 3/2 | string.h:366 | `#ifdef __OPTIMIZE__` | M1 (&lt;bits/stdc++.h&gt;, &lt;cstring&gt;, &lt;string.h&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `strstr`. |
| `__builtin_toupper` | builtin (library) | L | 2/1 | c++/format:1630 | `#if __has_builtin(__builtin_toupper)` | M1 (&lt;bits/stdc++.h&gt;, &lt;chrono&gt;, &lt;format&gt;) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `toupper`. |
| `__builtin_vsnprintf` | builtin (library) | L | 1/1 | c++/aarch64/bits/c++locale.h:97 | `#if _GLIBCXX_USE_C99_STDIO` | M1 (34 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `vsnprintf`. |

Not reached in M1 (rows in the appendix): `__builtin_fclose` (not reached), `__builtin_vsprintf` (not reached).

**Floating-point classification and constants.** Variants are folded, so `__builtin_nan{,f,l}` stands for three names. These are class M because `std::numeric_limits` members are `constexpr` and use `__builtin_huge_val*`, `__builtin_nan*` and `__builtin_nans*` (limits:1723-1729).

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_copysign{,f,l,f16,f128}` | builtin (FP class/constant) | M | 15/4 | c++/cmath:2315 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `copysign`. |
| `__builtin_fabs{,f,l,f128}` | builtin (FP class/constant) | M | 23/4 | c++/bits/std_abs.h:78 | `#ifndef __CORRECT_ISO_CPP_MATH_H_PROTO` | M1 (40 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `fabs`. |
| `__builtin_fpclassify` | builtin (FP class/constant) | M | 11/3 | c++/cmath:1109 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005ffpclassify): This built-in implements the C99 fpclassify functionality. |
| `__builtin_huge_val{,f,l,f16,f32,f64,f128,f32x,f64x,f128x}` | builtin (FP class/constant) | M | 25/4 | c++/limits:1723 | `(unconditional)` | M1 (22 roots) | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005fhuge_005fval): Returns a positive infinity, if supported by the floating-point format, else DBL_MAX. |
| `__builtin_inf{,f,l,d32,f128}` | builtin (FP class/constant) | M | 17/6 | math.h:93 (in `#define INFINITY`) | `#if __GNUC_PREREQ (3, 3)` | M1 macro only | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005finf): Similar to __builtin_huge_val, except a warning is generated if the target floating-point format does not support infinities. |
| `__builtin_isfinite` | builtin (FP class/constant) | M | 15/5 | c++/cmath:1134 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (10 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isfinite`. |
| `__builtin_isgreater` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1255 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isgreater`. |
| `__builtin_isgreaterequal` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1281 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isgreaterequal`. |
| `__builtin_isinf` | builtin (FP class/constant) | M | 16/3 | c++/cmath:1156 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isinf`. |
| `__builtin_isinf_sign` | builtin (FP class/constant) | M | 3/2 | c++/compare:588 | `#if __cpp_lib_three_way_comparison >= 201907L` | M1 (65 roots) | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005fisinf_005fsign): Similar to isinf, except the return value is -1 for an argument of -Inf and 1 for an argument of +Inf. |
| `__builtin_isless` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1307 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isless`. |
| `__builtin_islessequal` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1333 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `islessequal`. |
| `__builtin_islessgreater` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1359 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `islessgreater`. |
| `__builtin_isnan{,f,l}` | builtin (FP class/constant) | M | 23/5 | c++/cmath:1183 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (65 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isnan`. |
| `__builtin_isnormal` | builtin (FP class/constant) | M | 12/4 | c++/cmath:1210 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (65 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isnormal`. |
| `__builtin_isunordered` | builtin (FP class/constant) | M | 12/3 | c++/cmath:1385 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (8 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `isunordered`. |
| `__builtin_nan{,f,l,d32,f128}` | builtin (FP class/constant) | M | 18/5 | c++/limits:1726 | `(unconditional)` | M1 (22 roots) | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005fnan): This is an implementation of the ISO C99 function nan. |
| `__builtin_nans{,f,l,d32,d64,f16,f32,f64,d128,d64x,f128,f16b,f32x,f64x,f128x}` | builtin (FP class/constant) | M | 39/5 | c++/limits:1729 | `(unconditional)` | M1 (22 roots) | [Floating-Point-Format-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating_002dPoint-Format-Builtins.html#index-_005f_005fbuiltin_005fnans): Similar to __builtin_nan, except the significand is forced to be a signaling NaN. |
| `__builtin_signbit{,l}` | builtin (FP class/constant) | M | 20/7 | c++/cmath:1233 | `#ifndef __CORRECT_ISO_CPP11_MATH_H_PROTO_FP` | M1 (65 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `signbit`. |

Not reached in M1 (rows in the appendix): `__builtin_nansq` (not reached).

**Math library builtins.** There are 296 names (747 uses), mostly `<cmath>` overloads that forward `std::sin(float)` to `__builtin_sinf` and so on. 207 are reached in M1. The 89 that are not are almost all `_Float128` variants reached only under C++23 macros. All are class L: the corresponding libm function is a correct lowering. The full table is appendix F.8.

### 3.3 Atomics

All 16 are reached in M1. Most uses are in bits/atomic_base.h and bits/atomic_wait.h. The widest-reaching is `__atomic_fetch_add`, in 33 roots, because ext/atomicity.h:68-73 uses it in `__exchange_and_add` and `__atomic_add`, libstdc++'s reference-count helpers. No `__sync_*` builtin is used anywhere in the closure. The manual specifies the memory-model argument; milestone 1 lowers these the way `-moutline-atomics` does (an ABI-level choice; no header tests it).

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__atomic_add_fetch` | builtin (atomic) | M | 11/1 | c++/bits/atomic_base.h:398 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fadd_005ffetch): These built-in functions perform the operation suggested by the name, and return the result of the operation. |
| `__atomic_always_lock_free` | builtin (atomic) | M | 9/4 | c++/atomic:288 | `#ifdef __cpp_lib_atomic_is_always_lock_free` | M1 (14 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005falways_005flock_005ffree): This built-in function returns true if objects of size bytes always generate lock-free atomic instructions for the target architecture. |
| `__atomic_clear` | builtin (atomic) | M | 4/2 | c++/bits/atomic_base.h:290 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fclear): This built-in function performs an atomic clear operation on *ptr. |
| `__atomic_compare_exchange` | builtin (atomic) | M | 5/2 | c++/bits/atomic_base.h:999 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fcompare_005fexchange): This built-in function implements the generic version of __atomic_compare_exchange. |
| `__atomic_compare_exchange_n` | builtin (atomic) | M | 10/3 | c++/bits/atomic_base.h:536 | `(unconditional)` | M1 (14 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fcompare_005fexchange_005fn): This built-in function implements an atomic compare and exchange operation. |
| `__atomic_exchange` | builtin (atomic) | M | 4/3 | c++/atomic:330 | `#else /* of #if __cplusplus < 201103L */` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fexchange): This is the generic version of an atomic exchange. |
| `__atomic_exchange_n` | builtin (atomic) | M | 4/1 | c++/bits/atomic_base.h:519 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fexchange_005fn): This built-in function implements an atomic exchange operation. |
| `__atomic_fetch_add` | builtin (atomic) | M | 15/5 | c++/bits/atomic_base.h:631 | `(unconditional)` | M1 (33 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005ffetch_005fadd): These built-in functions perform the operation suggested by the name, and return the value that had previously been in *ptr. |
| `__atomic_is_lock_free` | builtin (atomic) | M | 8/3 | c++/atomic:274 | `#else /* of #if __cplusplus < 201103L */` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fis_005flock_005ffree): This built-in function returns true if objects of size bytes always generate lock-free atomic instructions for the target architecture. |
| `__atomic_load` | builtin (atomic) | M | 12/5 | c++/atomic:312 | `#else /* of #if __cplusplus < 201103L */` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fload): This is the generic version of an atomic load. |
| `__atomic_load_n` | builtin (atomic) | M | 9/3 | c++/bits/atomic_base.h:263 | `#if __glibcxx_atomic_wait` | M1 (14 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fload_005fn): This built-in function implements an atomic load operation. |
| `__atomic_signal_fence` | builtin (atomic) | M | 2/2 | c++/bits/atomic_base.h:151 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fsignal_005ffence): This built-in function acts as a synchronization fence between a thread and signal handlers based in the same thread. |
| `__atomic_store` | builtin (atomic) | M | 4/3 | c++/atomic:294 | `#else /* of #if __cplusplus < 201103L */` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fstore): This is the generic version of an atomic store. |
| `__atomic_store_n` | builtin (atomic) | M | 4/1 | c++/bits/atomic_base.h:477 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fstore_005fn): This built-in function implements an atomic store operation. |
| `__atomic_test_and_set` | builtin (atomic) | M | 4/2 | c++/bits/atomic_base.h:227 | `(unconditional)` | M1 (11 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005ftest_005fand_005fset): This built-in function performs an atomic test-and-set operation on the byte at *ptr. |
| `__atomic_thread_fence` | builtin (atomic) | M | 8/5 | c++/bits/atomic_base.h:147 | `(unconditional)` | M1 (14 roots) | [__atomic-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fatomic-Builtins.html#index-_005f_005fatomic_005fthread_005ffence): This built-in function acts as a synchronization fence between threads based on the specified memory order. |

### 3.4 Varargs

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_va_arg` | builtin (varargs) | M | 1/1 | gcc/stdarg.h:53 (in `#define va_arg`) | `#ifdef _STDARG_H` | M1 macro only | c_common_reswords (not in manual) |
| `__builtin_va_arg_pack` | builtin (varargs) | M | 1/1 | aarch64/sys/cdefs.h:638 (in `#define __va_arg_pack`) | `#if __GNUC_PREREQ (4,3)` | M1 macro only | [Constructing-Calls](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Constructing-Calls.html#index-_005f_005fbuiltin_005fva_005farg_005fpack): This built-in function represents all anonymous arguments of an inline function. |
| `__builtin_va_arg_pack_len` | builtin (varargs) | M | 1/1 | aarch64/sys/cdefs.h:639 (in `#define __va_arg_pack_len`) | `#if __GNUC_PREREQ (4,3)` | M1 macro only | [Constructing-Calls](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Constructing-Calls.html#index-_005f_005fbuiltin_005fva_005farg_005fpack_005flen): This built-in function returns the number of anonymous arguments of an inline function. |
| `__builtin_va_copy` | builtin (varargs) | M | 2/1 | gcc/stdarg.h:56 (in `#define va_copy`) | `#if !defined(__STRICT_ANSI__) \|\| __STDC_VERSION__ + 0 >= 199900L \|\| __cplusplus + 0 >= 201103L` | M1 macro only | builtins.def (not in manual) |
| `__builtin_va_end` | builtin (varargs) | M | 12/5 | c++/aarch64/bits/c++locale.h:102 | `(unconditional)` | M1 (34 roots) | builtins.def (not in manual) |
| `__builtin_va_list` | builtin (varargs) | M | 4/3 | c++/aarch64/bits/c++locale.h:93 | `(unconditional)` | M1 (43 roots) | builtins.def (not in manual) |
| `__builtin_va_start` | builtin (varargs) | M | 12/5 | c++/aarch64/bits/c++locale.h:94 | `(unconditional)` | M1 (34 roots) | builtins.def (not in manual) |

Not reached in M1 (rows in the appendix): `__builtin_c23_va_start` (not reached).

`__builtin_va_arg_pack` and `__builtin_va_arg_pack_len` are reached only through glibc's fortify wrappers (`__va_arg_pack`, section 3.7).

### 3.5 Control-flow and hint builtins

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_abort` | builtin (control/hint) | M | 5/4 | c++/any:74 | `#else /* of #if __cpp_exceptions */` | M1 (4 roots) | [Library-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Library-Builtins.html): Built-in version of the library function `abort`. |
| `__builtin_alloca` | builtin (control/hint) | M | 28/9 | c++/bits/fstream.tcc:626 | `(unconditional)` | M1 (34 roots) | [Stack-Allocation](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Stack-Allocation.html#index-_005f_005fbuiltin_005falloca): The __builtin_alloca function must be called at block scope. Forge: real stack allocation; used for buffers in <fstream> and <locale> code. |
| `__builtin_assume_aligned` | builtin (control/hint) | A | 1/1 | c++/bits/align.h:100 | `#ifdef __glibcxx_assume_aligned` | M1 (9 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fassume_005faligned): This function returns its first argument, and allows the compiler to assume that the returned pointer is at least align bytes aligned. Forge: identity on the pointer is correct. |
| `__builtin_expect` | builtin (control/hint) | A | 74/30 | c++/bits/basic_ios.h:389 | `(unconditional)` | M1 (55 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fexpect): You may use __builtin_expect to provide the compiler with branch prediction information. Forge: identity on the value is a correct implementation. |
| `__builtin_trap` | builtin (control/hint) | M | 3/3 | c++/array:76 | `#else /* of #if __cplusplus < 201103L */` | M1 (9 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005ftrap): This function causes the program to exit abnormally. |
| `__builtin_unreachable` | builtin (control/hint) | M | 40/16 | c++/array:454 | `#ifdef __cpp_lib_to_array` | M1 (56 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005funreachable): If control flow reaches the point of the __builtin_unreachable, the program is undefined. Forge: any lowering (trap or nothing) is correct for programs that never reach it. |

Not reached in M1 (rows in the appendix): `__builtin_extract_return_addr` (not reached), `__builtin_ia32_pause` (not reached), `__builtin_return_address` (not reached).

### 3.6 Constexpr-relevant and language-support builtins

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_FILE` | builtin (language) | M | 1/1 | assert.h:129 (in `#define __ASSERT_FILE`) | `#if __has_builtin (__builtin_FILE)` | M1 macro only | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fFILE): This function is the equivalent of the preprocessor __FILE__ macro and returns an address constant pointing to the file name containing the invocation of the built-in, ... Forge: its string is embedded at every assert() call site, so it is part of the output bytes. |
| `__builtin_LINE` | builtin (language) | M | 1/1 | assert.h:130 (in `#define __ASSERT_LINE`) | `#if __has_builtin (__builtin_FILE)` | M1 macro only | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fLINE): This function is the equivalent of the preprocessor __LINE__ macro and returns a constant integer expression that evaluates to the line number of the invocation of the ... |
| `__builtin_addressof` | builtin (language) | M | 61/8 | c++/bits/basic_string.h:150 | `#if __glibcxx_constexpr_string >= 201907L` | M1 (66 roots) | c_common_reswords (not in manual) |
| `__builtin_bit_cast` | builtin (language) | M | 16/4 | c++/bit:96 | `#ifdef __cpp_lib_bit_cast` | M1 (68 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fbit_005fcast): The __builtin_bit_cast function is available only in C++. |
| `__builtin_clear_padding` | builtin (language) | M | 2/2 | c++/atomic:251 | `#if __has_builtin(__builtin_clear_padding)` | M1 (11 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fclear_005fpadding): The built-in function __builtin_clear_padding function clears padding bits inside of the object representation of object pointed by ptr, which has to be a pointer. Forge: a no-op for types without padding; atomic<T> compare-exchange depends on it otherwise. |
| `__builtin_constant_p` | builtin (language) | M | 35/14 | c++/bits/char_traits.h:233 | `#if __cplusplus >= 202002L` | M1 (62 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fconstant_005fp): You can use the built-in function __builtin_constant_p to determine if the expression exp is known to be constant at compile time and hence that GCC can perform ... Forge: 0 is correct at run time (manual), but char_traits::move (bits/char_traits.h:233) calls it during constant evaluation and needs 1 for a foldable pointer comparison. |
| `__builtin_coro_destroy` | builtin (language) | M | 2/1 | c++/coroutine:144 | `#ifdef __cpp_lib_coroutine` | M1 (&lt;bits/stdc++.h&gt;, &lt;coroutine&gt;) | builtins.def (not in manual) |
| `__builtin_coro_done` | builtin (language) | M | 2/1 | c++/coroutine:137 | `#ifdef __cpp_lib_coroutine` | M1 (&lt;bits/stdc++.h&gt;, &lt;coroutine&gt;) | builtins.def (not in manual) |
| `__builtin_coro_promise` | builtin (language) | M | 2/1 | c++/coroutine:211 | `#ifdef __cpp_lib_coroutine` | M1 (&lt;bits/stdc++.h&gt;, &lt;coroutine&gt;) | builtins.def (not in manual) |
| `__builtin_coro_resume` | builtin (language) | M | 2/1 | c++/coroutine:142 | `#ifdef __cpp_lib_coroutine` | M1 (&lt;bits/stdc++.h&gt;, &lt;coroutine&gt;) | builtins.def (not in manual) |
| `__builtin_is_constant_evaluated` | builtin (language) | M | 5/3 | c++/aarch64/bits/c++config.h:589 | `#elif __cplusplus >= 201103L && __has_builtin(__builtin_is_constant_evaluated)` | M1 (105 roots) | [Other-Builtins](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Other-Builtins.html#index-_005f_005fbuiltin_005fis_005fconstant_005fevaluated): The __builtin_is_constant_evaluated function is available only in C++. Forge: must be exact; libstdc++ picks constexpr-only code with it. |
| `__builtin_launder` | builtin (language) | M | 1/1 | c++/new:243 | `#ifdef __cpp_lib_launder` | M1 (64 roots) | c_common_reswords (not in manual): Forge: identity is correct unless the optimiser assumes object identity. |
| `__builtin_offsetof` | builtin (language) | M | 1/1 | gcc/stddef.h:431 (in `#define offsetof`) | `#ifdef _STDDEF_H` | M1 macro only | c_common_reswords (not in manual) |
| `__builtin_source_location` | builtin (language) | M | 2/1 | c++/source_location:54 | `#if __cpp_lib_source_location` | M1 (&lt;bits/stdc++.h&gt;, &lt;source_location&gt;) | cp/decl.cc (not in manual) |

Not reached in M1 (rows in the appendix): `__builtin_choose_expr` (not reached), `__builtin_classify_type` (not reached), `__builtin_complex` (not reached), `__builtin_operator_delete` (clang identity only), `__builtin_operator_new` (clang identity only), `__builtin_tgmath` (not reached), `__builtin_types_compatible_p` (not reached).

Load-bearing details:
- **`std::__is_constant_evaluated()`** (c++config.h:576-594) is `if consteval` when `__cpp_if_consteval >= 202106L` (C++23), else `__builtin_is_constant_evaluated()` when `__has_builtin` says so, **else `return false`**. A false answer makes every C++20 `constexpr` `std::string`, `std::vector` and `char_traits` operation take its run-time path inside constant evaluation, where it calls `__builtin_memcpy`, `__builtin_memmove` and `__builtin_strlen` (char_traits.h:230-300).
- **`__builtin_constant_p`** inside constant evaluation: char_traits.h:233 uses `__builtin_constant_p(__s2 < __s1)` to decide whether an overlapping constexpr `move` must copy backwards. If it always returns 0, constexpr `move` of an overlapping range with `__s1 > __s2` takes the forward-copy branch.
- **`__builtin_bit_cast`** backs `std::bit_cast` (bit:96) and `__builtin_addressof` backs `std::addressof` (61 uses). `__builtin_launder` backs `std::launder` (new:243). `__builtin_source_location` backs `std::source_location::current()`, and `__builtin_coro_*` back `std::coroutine_handle`.

### 3.7 Object size and fortify

In M1 only `__builtin_dynamic_object_size` is reached, in `<format>` (format:3530), plus `__builtin_object_size` inside glibc's `__bos` macro, which nothing expands without fortify. Everything else appears only with `_FORTIFY_SOURCE` (the m1-fortify run):
- the 16 `__builtin___*_chk` builtins;
- `__builtin_va_arg_pack`;
- `__builtin_constant_p` on lengths;
- `__REDIRECT_FORTIFY` declarations;
- `extern __always_inline __attribute__((__gnu_inline__, __artificial__))` wrapper bodies.

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__builtin_dynamic_object_size` | builtin (object size) | A | 3/2 | c++/format:3531 | `#if __has_builtin(__builtin_dynamic_object_size)` | M1 (&lt;bits/stdc++.h&gt;, &lt;chrono&gt;, &lt;format&gt;) | [Object-Size-Checking](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Object-Size-Checking.html#index-_005f_005fbuiltin_005fdynamic_005fobject_005fsize): This builtin is similar to __builtin_object_size in that it returns a number of bytes from ptr to the end of the object ptr pointer points to, except that the size ... Forge: the 'unknown' answer is correct (manual). |
| `__builtin_object_size` | builtin (object size) | A | 3/2 | aarch64/sys/cdefs.h:157 (in `#define __bos`) | `(unconditional)` | M1 macro only | [Object-Size-Checking](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Object-Size-Checking.html#index-_005f_005fbuiltin_005fobject_005fsize): This built-in construct returns a constant number of bytes from ptr to the end of the object ptr pointer points to (if known at compile time). Forge: the 'unknown' answer ((size_t)-1 for types 0/1) is correct (manual). |

Not reached in M1 (rows in the appendix): `__builtin___memcpy_chk` (fortify only), `__builtin___memmove_chk` (fortify only), `__builtin___mempcpy_chk` (fortify only), `__builtin___memset_chk` (fortify only), `__builtin___snprintf_chk` (fortify only), `__builtin___sprintf_chk` (fortify only), `__builtin___stpcpy_chk` (fortify only), `__builtin___stpncpy_chk` (fortify only), `__builtin___strcat_chk` (fortify only), `__builtin___strcpy_chk` (fortify only), `__builtin___strncat_chk` (fortify only), `__builtin___strncpy_chk` (fortify only), `__builtin___vfprintf_chk` (not reached), `__builtin___vprintf_chk` (not reached), `__builtin___vsnprintf_chk` (fortify only), `__builtin___vsprintf_chk` (fortify only).

### 3.8 Attributes

**GNU attributes** (`__attribute__((...))`, `__attribute((...))` and `[[gnu::...]]`/`[[__gnu__::...]]`). Many reach M1 only through glibc's or libstdc++'s wrapper macros (appendix E lists each macro and its M1 expansion). In C++ glibc's `__THROW` is `noexcept (true)`, not `__attribute__ ((__nothrow__))` (cdefs.h:85-88), so the `nothrow` attribute is **not reached** in C++ at all.

| Name | Kind | Spellings | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|---|
| `aarch64_vector_pcs` | GNU attribute | __attribute__(()) | M | 1/1 | aarch64/bits/math-vector.h:212 (in `#define __vpcs`) | `#ifdef __ADVSIMD_VEC_MATH_SUPPORTED` | M1 (via macro) | not in manual: Arm vector PCS (not in the GCC manual): changes callee-saved registers of glibc's _ZGVnN* vector-math declarations |
| `abi_tag` | GNU attribute | __attribute(()), __attribute__(()) | M | 17/8 | c++/aarch64/bits/c++config.h:371 | `#if _GLIBCXX_USE_CXX11_ABI` | M1 (105 roots) | [C++-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/C_002b_002b-Attributes.html#index-abi_005ftag-variable-attribute): The abi_tag attribute can be applied to a function, variable, or class declaration. Forge: changes mangled names (B5cxx11) of symbols exported by libstdc++.so. |
| `access` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 10/4 | c++/bits/chrono_io.h:3135 | `#if __cplusplus >= 202002L` | M1 (6 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-access-function-attribute): The access attribute enables the detection of invalid or unsafe accesses by functions to which they apply or their callers, as well as write-only accesses to objects ... |
| `aligned` | GNU attribute | __attribute__(()) | M | 20/9 | aarch64/asm/sigcontext.h:36 | `#ifndef __ASSEMBLER__` | M1 (85 roots) | [Common-Type-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Type-Attributes.html#index-aligned-type-attribute): The aligned attribute specifies a minimum alignment (in bytes) for variables of the specified type. |
| `alloc_align` | GNU attribute | __attribute__(()), via macro | A | 8/4 | c++/bits/memory_resource.h:77 | `#if __cplusplus >= 201703L` | M1 (64 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-alloc_005falign-function-attribute): The alloc_align attribute may be applied to a function that returns a pointer and takes at least one argument of an integer or enumerated type. |
| `alloc_size` | GNU attribute | __attribute__(()) | A | 9/4 | c++/bits/memory_resource.h:77 | `#if __cplusplus >= 201703L` | M1 (64 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-alloc_005fsize-function-attribute): The alloc_size attribute may be applied to a function that returns a pointer and takes at least one argument of an integer or enumerated type. |
| `always_inline` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 297/44 | c++/aarch64/bits/c++config.h:348 | `#if __cplusplus` | M1 (105 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-always_005finline-function-attribute): Generally, functions are not inlined unless optimization is specified. Forge: GCC errors when it cannot inline; ignoring the attribute preserves behaviour. |
| `artificial` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:604 (in `#define __attribute_artificial__`) | `#if __GNUC_PREREQ (4,3) \|\| __glibc_has_attribute (__artificial__)` | M1 macro only | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-artificial-function-attribute): This attribute is useful for small inline wrappers that if possible should appear during debugging as a unit. |
| `assume` | GNU attribute | __attribute__(()) | A | 1/1 | c++/bits/stl_bvector.h:196 | `#if __has_attribute(__assume__) && !defined(_GLIBCXX_CLANG)` | M1 (9 roots) | [Statement-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Statement-Attributes.html#index-assume-statement-attribute): The assume attribute with a null statement serves as portable assumption. Forge: ignoring is safe; acting on it is an optimisation. |
| `cold` | GNU attribute | __attribute__(()) | A | 25/7 | c++/aarch64/bits/c++config.h:351 | `#if __cplusplus` | M1 (105 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-cold-function-attribute): The cold attribute on functions is used to inform the compiler that the function is unlikely to be executed. |
| `const` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 53/18 | aarch64/bits/mathcalls-helper-functions.h:21 | `(unconditional)` | M1 (61 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-const-function-attribute): Calls to functions whose return value is not affected by changes to the observable state of the program and that have no observable effects on such state other than to ... |
| `copy` | GNU attribute | __attribute__(()) | M | 2/2 | aarch64/sys/cdefs.h:713 (in `#define __attribute_copy__`) | `#if __GNUC_PREREQ (9, 0)` | M1 macro only | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-copy-function-attribute): The copy attribute applies the set of attributes with which function has been declared to the declaration of the function to which the attribute is applied. Forge: copies another declaration's attributes; its class is that of the copied set. |
| `deprecated` | GNU attribute | __attribute__(()) | A | 9/6 | c++/iomanip:179 | `(unconditional)` | M1 (4 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-deprecated-function-attribute): The deprecated attribute results in a warning if the function is used anywhere in the source file. |
| `error` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:367 (in `#define __errordecl`) | `#if __GNUC_PREREQ (4,3)` | M1 macro only | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-error-function-attribute): If the error or warning attribute is used on a function declaration and a call to such a function is not eliminated through dead code elimination or other optimizations, ... |
| `externally_visible` | GNU attribute | __attribute__(()) | A | 20/1 | c++/new:139 | `(unconditional)` | M1 (64 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-externally_005fvisible-function-attribute): This attribute, attached to a global variable or function, nullifies the effect of the -fwhole-program command-line option, so the object remains visible outside the ... |
| `flag_enum` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 2/2 | c++/bits/ios_base.h:127 | `(unconditional)` | M1 (28 roots) | [Common-Type-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Type-Attributes.html#index-flag_005fenum-type-attribute): This attribute may be applied to an enumerated type to indicate that its enumerators are used in bitwise operations, so e.g. |
| `format` | GNU attribute | __attribute__(()) | A | 26/4 | c++/bits/functexcept.h:83 | `#if _GLIBCXX_HOSTED` | M1 (61 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-format-function-attribute): The format attribute specifies that a function takes printf, scanf, strftime or strfmon style arguments that should be type-checked against a format string. |
| `format_arg` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:533 (in `#define __attribute_format_arg__`) | `#if __GNUC_PREREQ (2,8) \|\| __glibc_has_attribute (__format_arg__)` | M1 (via macro) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-format_005farg-function-attribute): The format_arg attribute specifies that a function takes one or more format strings for a printf, scanf, strftime or strfmon style function and modifies it (for example, ... |
| `gnu_inline` | GNU attribute | __attribute__(()) | M | 2/1 | aarch64/sys/cdefs.h:622 (in `#define __extern_inline`) | `#if defined __GNUC_STDC_INLINE__ \|\| defined __cplusplus` | M1 (via macro) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-gnu_005finline-function-attribute): This attribute should be used with a function that is also declared with the inline keyword. Forge: extern inline + gnu_inline must never emit an out-of-line body (the symbol is libc's). |
| `leaf` | GNU attribute | __attribute__(()), via macro | A | 2/1 | aarch64/sys/cdefs.h:66 (in `#define __LEAF_ATTR`) | `#if __GNUC_PREREQ (4, 6) && !defined _LIBC` | M1 (via macro) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-leaf-function-attribute): Calls to external functions with this attribute must return to the current compilation unit only by return or by exception handling. |
| `malloc` | GNU attribute | __attribute__(()) | A | 20/4 | c++/bits/valarray_array.h:55 | `(unconditional)` | M1 (64 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-malloc-function-attribute): Attribute malloc indicates that a function is malloc-like, i.e., that the pointer P returned by the function cannot alias any other pointer valid when the function ... |
| `may_alias` | GNU attribute | [[gnu::]], __attribute__(()) | M | 2/2 | c++/bits/std_function.h:85 | `#else /* of #if __cplusplus < 201103L */` | M1 (5 roots) | [Common-Type-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Type-Attributes.html#index-may_005falias-type-attribute): Accesses through pointers to types with this attribute are not subject to type-based alias analysis, but are instead assumed to be able to alias any other type of ... Forge: matters only to an optimiser that does type-based alias analysis. |
| `mode` | GNU attribute | __attribute__(()) | M | 4/3 | c++/aarch64/bits/cxxabi_tweaks.h:46 | `(unconditional)` | M1 (48 roots) | [Common-Type-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Type-Attributes.html#index-mode-type-attribute): This attribute specifies the data type for the declaration—whichever type corresponds to the mode mode. Forge: cxxabi_tweaks.h:46 `__guard` is `int __attribute__((mode (__DI__)))`, a 64-bit guard type. |
| `noclone` | GNU attribute | __attribute__(()) | A | 2/2 | c++/bits/basic_string.h:2822 | `#else /* of #if ! _GLIBCXX_USE_CXX11_ABI */` | M1 (34 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-noclone-function-attribute): This function attribute prevents a function from being considered for cloning—a mechanism that produces specialized copies of functions and which is (currently) ... |
| `noinline` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 7/5 | c++/bits/basic_string.h:2822 | `#else /* of #if ! _GLIBCXX_USE_CXX11_ABI */` | M1 (34 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-noinline-function-attribute): This function attribute prevents a function from being considered for inlining. |
| `nonnull` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 56/15 | c++/bits/basic_string.h:3722 | `#if __cplusplus >= 202002L` | M1 (48 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-nonnull-function-attribute): The nonnull attribute may be applied to a function that takes at least one argument of a pointer type. |
| `nonstring` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:703 (in `#define __attribute_nonstring__`) | `#if __GNUC_PREREQ (8, 0)` | M1 macro only | [Common-Variable-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Variable-Attributes.html#index-nonstring-variable-attribute): The nonstring variable attribute specifies that an object or member declaration with type array of char, signed char, or unsigned char, or pointer to such a type is ... |
| `noreturn` | GNU attribute | [[gnu::]], __attribute__(()) | A | 59/15 | c++/aarch64/bits/c++config.h:348 | `#if __cplusplus` | M1 (111 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-noreturn-function-attribute): A few standard library functions, such as abort and exit, cannot return. Forge: ignoring is safe for correct code; affects code generation and warnings only. |
| `pure` | GNU attribute | __attribute__(()) | A | 9/5 | c++/bits/exception_ptr.h:106 | `(unconditional)` | M1 (33 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-pure-function-attribute): Calls to functions that have no observable effects on the state of the program other than to return a value may lend themselves to optimizations such as common ... |
| `returns_nonnull` | GNU attribute | [[__gnu__::]], __attribute__(()) | A | 15/5 | c++/bits/locale_conv.h:246 | `#else /* of #if __cplusplus < 201103L */` | M1 (46 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-returns_005fnonnull-function-attribute): The returns_nonnull attribute specifies that the function return value should be a non-null pointer. |
| `returns_twice` | GNU attribute | __attribute__(()) | M | 1/1 | aarch64/sys/cdefs.h:884 (in `#define __attribute_returns_twice__`) | `#if __GNUC_PREREQ (4, 1)` | M1 (via macro) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-returns_005ftwice-function-attribute): The returns_twice attribute tells the compiler that a function may return more than one time. Forge: setjmp-like calls; an optimiser must not keep values in registers across them. |
| `unused` | GNU attribute | [[__gnu__::]], __attribute(()), __attribute__(()) | A | 58/23 | c++/aarch64/bits/c++locale.h:74 | `(unconditional)` | M1 (54 roots) | [Common-Variable-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Variable-Attributes.html#index-unused-variable-attribute): This attribute, attached to a variable or structure field, means that the variable or field is meant to be possibly unused. |
| `used` | GNU attribute | __attribute__(()) | A | 2/2 | aarch64/sys/cdefs.h:501 (in `#define __attribute_used__`) | `#if __GNUC_PREREQ (3,1) \|\| __glibc_has_attribute (__used__)` | M1 macro only | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-used-function-attribute): This attribute, attached to a function, means that code must be emitted for the function even if it appears that the function is not referenced. |
| `visibility` | GNU attribute | __attribute__(()) | A | 2/1 | c++/aarch64/bits/c++config.h:650 | `#elif _GLIBCXX_HAVE_IS_CONSTANT_EVALUATED` | M1 (105 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-visibility-function-attribute): This attribute affects the linkage of the declaration to which it is attached. Forge: linkage only; no effect on a PIE that exports nothing. |
| `warn_unused_result` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:577 (in `#define __attribute_warn_unused_result__`) | `#if __GNUC_PREREQ (3,4) \|\| __glibc_has_attribute (__warn_unused_result__)` | M1 (via macro) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-warn_005funused_005fresult-function-attribute): The warn_unused_result attribute causes a warning to be emitted if a caller of the function with this attribute does not use its return value. |
| `warning` | GNU attribute | __attribute__(()) | A | 1/1 | aarch64/sys/cdefs.h:366 (in `#define __warnattr`) | `#if __GNUC_PREREQ (4,3)` | M1 macro only | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-warning-function-attribute): If the error or warning attribute is used on a function declaration and a call to such a function is not eliminated through dead code elimination or other optimizations, ... |
| `weak` | GNU attribute | __attribute__(()) | M | 1/1 | pthread.h:753 | `#ifndef SHARED` | M1 (36 roots) | [Common-Function-Attributes](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Function-Attributes.html#index-weak-function-attribute): The weak attribute causes a declaration of an external symbol to be emitted as a weak symbol rather than a global. Forge: weak undefined reference to __pthread_unwind_next (pthread.h:753) if referenced. |

Not reached in M1 (rows in the appendix): `bitwise` (not reached), `cleanup` (not reached), `diagnose_if` (not reached), `dllimport` (not reached), `enable_if` (not reached), `neon_vector_type` (clang identity only), `nothrow` (not reached), `overloadable` (clang macro only), `pass_dynamic_object_size` (not reached), `pass_object_size` (not reached), `simd` (not reached), `stdcall` (not reached), `unavailable` (not reached), `weakref` (not reached).

**Standard attributes.** libstdc++ mostly uses the reserved `__name__` spellings.

| Name | Kind | Spellings | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|---|
| `[[deprecated]]` | ISO attribute | [[__deprecated__]], [[deprecated]] | A | 15/8 | c++/bits/basic_string.h:1311 | `#if __cplusplus > 201703L` | M1 (34 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[fallthrough]]` | ISO attribute | [[fallthrough]] | A | 7/2 | c++/bits/chrono_io.h:387 | `#if __cplusplus >= 202002L` | M1 (&lt;bits/stdc++.h&gt;, &lt;chrono&gt;, &lt;format&gt;) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[likely]]` | ISO attribute | [[__likely__]], [[likely]] | A | 74/21 | c++/bits/chrono_io.h:2081 | `#if __cplusplus >= 202002L` | M1 (59 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[maybe_unused]]` | ISO attribute | [[__maybe_unused__]], [[maybe_unused]] | A | 9/8 | c++/bits/alloc_traits.h:629 | `#if _GLIBCXX_HOSTED` | M1 (75 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[no_unique_address]]` | ISO attribute | [[__no_unique_address__]], [[no_unique_address]] | M | 77/16 | c++/bits/hashtable_policy.h:1015 | `(unconditional)` | M1 (52 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[nodiscard]]` | ISO attribute | [[__nodiscard__]], [[nodiscard]] | A | 894/73 | c++/array:132 | `#else /* of #if __cplusplus < 201103L */` | M1 (73 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[noreturn]]` | ISO attribute | [[__noreturn__]], [[noreturn]] | A | 21/9 | c++/bits/chrono_io.h:190 | `#if __cplusplus >= 202002L` | M1 (33 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |
| `[[unlikely]]` | ISO attribute | [[__unlikely__]], [[unlikely]] | A | 115/17 | c++/bits/atomic_futex.h:176 | `#if defined(_GLIBCXX_HAVE_LINUX_FUTEX) && ATOMIC_INT_LOCK_FREE > 1` | M1 (55 roots) | ISO C++ attribute; GCC accepts the reserved `__name__` spelling ([Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html)) |

### 3.9 Pragmas

| Name | Kind | Class | Forms seen (count) | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|---|
| `#pragma #` | pragma (_Pragma) | A | _Pragma(# message) (1); _Pragma(# x) (1) | 2/2 | aarch64/sys/cdefs.h:807 (in `#define __glibc_macro_warning1`) | `#if __GNUC_PREREQ (4,8) \|\| __glibc_clang_prereq (3,5)` | M1 (via macro) | [Pragmas](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/Pragmas.html): _Pragma built by stringizing a macro argument (the pragma text is supplied by the caller). |
| `#pragma GCC diagnostic` | pragma (#pragma) | A | GCC diagnostic push (190); GCC diagnostic pop (190); GCC diagnostic ignored "-Wc++17-extensions" (53); GCC diagnostic ignored "-Wdeprecated-declarations" (37) | 585/106 | aarch64/bits/stdlib-bsearch.h:33 | `#if __GNUC_PREREQ(4, 6)` | M1 (110 roots) | [Diagnostic-Pragmas](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Diagnostic-Pragmas.html): GCC allows the user to selectively enable or disable certain types of diagnostics, and change the kind of the diagnostic. |
| `#pragma GCC system_header` | pragma (#pragma) | A | GCC system_header (222) | 222/222 | c++/aarch64/bits/basic_file.h:37 | `(unconditional)` | M1 (34 roots) | [System-Headers](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/System-Headers.html): The header files declaring interfaces to the operating system and runtime libraries often cannot be written in strictly conforming C. |
| `#pragma GCC unroll` | pragma (#pragma) | A | GCC unroll 4 (1) | 1/1 | c++/bits/stl_algobase.h:2094 | `(unconditional)` | M1 (53 roots) | [Loop-Specific-Pragmas](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Loop_002dSpecific-Pragmas.html): With this pragma, the programmer asserts that there are no loop-carried dependencies which would prevent consecutive iterations of the following loop ... |
| `#pragma GCC visibility` | pragma (#pragma) | A | GCC visibility pop (13); GCC visibility push(default) (9); GCC visibility push(hidden) (4) | 26/8 | c++/aarch64/bits/c++config.h:345 | `#if __cplusplus` | M1 (105 roots) | [Visibility-Pragmas](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Visibility-Pragmas.html): This pragma allows the user to set the visibility for multiple declarations without having to give each a visibility attribute (see Declaring ... |

Not reached in M1 (rows in the appendix): `#pragma clang attribute` (not reached), `#pragma clang diagnostic` (clang identity only), `#pragma intrinsic` (not reached), `#pragma omp atomic` (not reached), `#pragma omp barrier` (not reached), `#pragma omp critical` (not reached), `#pragma omp flush` (not reached), `#pragma omp for` (not reached), `#pragma omp parallel` (not reached), `#pragma omp section` (not reached), `#pragma omp sections` (not reached), `#pragma omp single` (not reached).

`#pragma GCC system_header` opens 222 headers. GCC's CPP manual says it gives "the code that follows ... the same treatment as a system header": warnings other than `#warning` are suppressed (System-Headers page). It changes no semantics.

### 3.10 Keyword, type and syntax extensions

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__alignof` | keyword | M | 5/3 | c++/bits/atomic_base.h:784 | `(unconditional)` | M1 (15 roots) | [Alignment](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alignment.html): The keyword __alignof__ determines the alignment requirement of a function, object, or a type, or the minimum alignment usually required by a type. |
| `__alignof__` | keyword | M | 11/6 | c++/bits/atomic_base.h:1304 | `#if __cplusplus > 201703L` | M1 (21 roots) | [Alignment](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alignment.html): The keyword __alignof__ determines the alignment requirement of a function, object, or a type, or the minimum alignment usually required by a type. |
| `__attribute` | keyword | A | 10/4 | c++/complex:1470 | `#if __cplusplus >= 201103L` | M1 (6 roots) | [Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html): GCC provides two different ways to specify attributes: the standard C and C++ syntax using double square brackets, and the older GNU extension syntax ... |
| `__attribute__` | keyword | A | 471/90 | aarch64/asm/sigcontext.h:36 | `#ifndef __ASSEMBLER__` | M1 (121 roots) | [Attribute-Syntax](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Attribute-Syntax.html): GCC provides two different ways to specify attributes: the standard C and C++ syntax using double square brackets, and the older GNU extension syntax ... |
| `__complex__` | keyword | M | 370/2 | c++/complex:953 | `#if _GLIBCXX_USE_C99_COMPLEX` | M1 (4 roots) | [Complex](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Complex.html): GNU complex type specifier; std::complex<float/double/long double> store __complex__ T. |
| `__decltype` | keyword | M | 27/9 | c++/aarch64/bits/c++config.h:889 | `#if defined __cplusplus && defined __BFLT16_DIG__` | M1 (105 roots) | [Alternate-Keywords](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alternate-Keywords.html): Alternate spelling of decltype accepted in all modes (libstdc++ uses it before C++11 checks). |
| `__extension__` | keyword | A | 218/43 | aarch64/bits/atomic_wide_counter.h:27 | `(unconditional)` | M1 (97 roots) | [Alternate-Keywords](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alternate-Keywords.html): Suppresses -pedantic warnings for the following expression or declaration; no semantics. |
| `__imag__` | keyword | M | 20/1 | c++/complex:1476 | `#if __cplusplus >= 201103L` | M1 (4 roots) | [Complex](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Complex.html): Extracts the imaginary part of a complex value (lvalue). |
| `__inline` | keyword | A | 12/3 | aarch64/bits/byteswap.h:33 | `#ifndef _BITS_BYTESWAP_H` | M1 (47 roots) | [Alternate-Keywords](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alternate-Keywords.html): -ansi and the various -std options disable certain keywords that are GNU C extensions. |
| `__int128` | type | M | 38/13 | c++/bits/cpp_type_traits.h:560 | `#if defined __STRICT_ANSI__ && defined __SIZEOF_INT128__` | M1 (77 roots) | [__int128](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fint128.html): As an extension the integer scalar type __int128 is supported for targets which have an integer mode wide enough to hold 128 bits. Forge: every M1 use is gated on __SIZEOF_INT128__ (23 tests). |
| `__null` | keyword | M | 3/3 | gcc/stddef.h:416 (in `#define NULL`) | `#ifdef __GNUG__` | M1 (via macro) | [C++-Extensions](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/C_002b_002b-Extensions.html): g++'s null pointer constant; GCC's stddef.h defines NULL as __null in C++ (C++ Extensions). Forge: GCC's stddef.h defines NULL as __null when __GNUG__ is defined. |
| `__PRETTY_FUNCTION__` | keyword | M | 10/4 | c++/aarch64/bits/c++config.h:629 (in `#define _GLIBCXX_ASSERT_FAIL`) | `#ifdef _GLIBCXX_VERBOSE_ASSERT` | M1 macro only | [Function-Names](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Function-Names.html): GCC provides three magic constants that hold the name of the current function as a string. |
| `__real__` | keyword | M | 51/2 | c++/complex:1472 | `#if __cplusplus >= 201103L` | M1 (4 roots) | [Complex](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Complex.html): Extracts the real part of a complex value (lvalue). |
| `__restrict` | keyword | A | 1203/37 | aarch64/bits/sigthread.h:32 | `(unconditional)` | M1 (78 roots) | [Restricted-Pointers](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Restricted-Pointers.html): Restricted pointer qualifier accepted in C++; an aliasing promise that may be ignored. |
| `__restrict__` | keyword | A | 42/2 | c++/bits/valarray_array.h:95 | `(unconditional)` | M1 (&lt;bits/stdc++.h&gt;, &lt;valarray&gt;) | [Restricted-Pointers](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Restricted-Pointers.html): Restricted pointer qualifier accepted in C++; an aliasing promise that may be ignored. |
| `__signed__` | keyword | A | 6/2 | asm-generic/int-ll64.h:20 | `#ifndef __ASSEMBLY__` | M1 (42 roots) | [Alternate-Keywords](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Alternate-Keywords.html): -ansi and the various -std options disable certain keywords that are GNU C extensions. |
| `__thread` | keyword | M | 2/1 | c++/mutex:834 | `#ifdef _GLIBCXX_HAVE_TLS` | M1 (&lt;bits/stdc++.h&gt;, &lt;future&gt;, &lt;mutex&gt;) | [Thread-Local](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Thread_002dLocal.html): Thread-local storage (TLS) is a mechanism by which variables are allocated such that there is one instance of the variable per extant thread. Forge: TLS variable in <mutex> under _GLIBCXX_HAVE_TLS. |
| `__typeof` | keyword | M | 35/6 | c++/aarch64/bits/c++locale.h:52 | `#if __GLIBC__ > 2 \|\| (__GLIBC__ == 2 && __GLIBC_MINOR__ > 2)` | M1 (34 roots) | [Typeof](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Typeof.html): Another way to refer to the type of an expression is with typeof. |
| `__typeof__` | keyword | M | 59/9 | c++/bits/stl_algo.h:4261 | `(unconditional)` | M1 (7 roots) | [Typeof](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Typeof.html): Another way to refer to the type of an expression is with typeof. |
| `__uint128_t` | type | M | 2/2 | aarch64/asm/sigcontext.h:81 | `#ifndef __ASSEMBLER__` | M1 (4 roots) | [__int128](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/_005f_005fint128.html): As an extension the integer scalar type __int128 is supported for targets which have an integer mode wide enough to hold 128 bits. Forge: unconditional; struct layout in asm/sigcontext.h and sys/user.h. |
| `_Bool` | C keyword | M | 8/3 | gcc/stdbool.h:44 (in `#define _Bool`) | `#else /* of #ifndef __cplusplus */` | M1 macro only | [Standards](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Standards.html): For each language compiled by GCC for which there is a standard, GCC attempts to follow one or more versions of that standard, possibly with some ... |
| `_Complex` | C keyword | M | 20/5 | aarch64/bits/floatn-common.h:151 (in `#define __CFLOAT32`) | `#else /* of #if !__GNUC_PREREQ (7, 0) \|\| (defined __cplusplus && !__GNUC_PREREQ (13, 0)) */` | M1 macro only | [Complex](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Complex.html): ISO C99 supports complex floating data types, and as an extension GCC supports them in C90 mode and in C++. |
| `_Float128` | type | M | 432/20 | c++/format:2808 | `#if defined(__FLT128_DIG__) && _GLIBCXX_FORMAT_F128 == 1` | M1 (45 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ (math.h __iseqsig_type specializations, bits/floatn.h). |
| `_Float16` | type | M | 304/18 | c++/format:3858 | `#if defined(__FLT16_DIG__) && defined(_GLIBCXX_FLOAT_IS_IEEE_BINARY32)` | M1 (&lt;bits/stdc++.h&gt;, &lt;chrono&gt;, &lt;format&gt;) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: reached only through <format> under __FLT16_DIG__. |
| `_Float32` | type | M | 239/18 | c++/format:2764 | `#if defined(__FLT32_DIG__) && defined(_GLIBCXX_FLOAT_IS_IEEE_BINARY32)` | M1 (45 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ (math.h __iseqsig_type specializations, bits/floatn.h). |
| `_Float32x` | type | M | 34/6 | math.h:1569 | `#if __HAVE_FLOAT32X && __GNUC_PREREQ (13, 0)` | M1 (45 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ (math.h __iseqsig_type specializations, bits/floatn.h). |
| `_Float64` | type | M | 258/19 | c++/format:2786 | `#if defined(__FLT64_DIG__) && defined(_GLIBCXX_DOUBLE_IS_IEEE_BINARY64)` | M1 (45 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ (math.h __iseqsig_type specializations, bits/floatn.h). |
| `_Float64x` | type | M | 30/6 | math.h:1579 | `#if __HAVE_FLOAT64X && __GNUC_PREREQ (13, 0)` | M1 (45 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO/IEC TS 18661-3:2015 defines C support for additional floating types _Floatn and _Floatnx, and GCC supports these type names; the set of types ... Forge: if __GNUC__ >= 13 is reported, glibc treats it as a distinct built-in type in C++ (math.h __iseqsig_type specializations, bits/floatn.h). |
| `long double` | ISO type | M | 661/41 | aarch64/bits/link.h:27 | `(unconditional)` | M1 (86 roots) | [Floating-Types](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Floating-Types.html): ISO type, listed because Forge's own code avoids it; on aarch64 it is IEEE binary128. Forge's own code avoids it, but the headers declare it 661 times (layout, mangling). |

Not reached in M1 (rows in the appendix): `__auto_type` (not reached), `__float128` (not reached), `__float80` (not reached), `__ibm128` (not reached), `__inline__` (not reached), `_Alignas` (not reached), `_Alignof` (not reached), `_Atomic` (not reached), `_Float128x` (not reached), `_Generic` (not reached), `_Noreturn` (not reached), `_Static_assert` (not reached).

**Syntax and directives.**

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `#include_next` | directive | M | 14/13 | c++/bits/std_abs.h:44 | `(unconditional)` | M1 (57 roots) | [Wrapper-Headers](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/Wrapper-Headers.html): Sometimes it is necessary to adjust the contents of a system-provided header file without editing it directly. Forge: needed by libstdc++'s <stdlib.h>/<math.h> wrappers and GCC's <limits.h>. |
| `#warning` | directive | A | 15/10 | c++/backward/backward_warning.h:32 | `#ifdef __DEPRECATED` | M1 (&lt;strstream&gt;) | [Diagnostics](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/Diagnostics.html): The directive ‘#error’ causes the preprocessor to report a fatal error. |
| `flexible array member` | syntax | M | 3/2 | aarch64/sys/cdefs.h:384 (in `#define __flexarr`) | `#elif __GNUC_PREREQ (2,97) \|\| defined __clang__` | M1 macro only | [Zero-Length](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Zero-Length.html): Trailing T x[] member; C99 in C, GCC extension in C++. |
| `named variadic macro parameter` | syntax | M | 1/1 | linux/stddef.h:32 (in `#define __struct_group`) | `(unconditional)` | M1 macro only | [Variadic-Macros](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/Variadic-Macros.html): A macro can be declared to accept a variable number of arguments much as a function can. |
| `pp-number suffix bf16` | syntax | M | 58/4 | c++/aarch64/bits/c++config.h:889 | `#if defined __cplusplus && defined __BFLT16_DIG__` | M1 (105 roots) | [Half-Precision](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Half_002dPrecision.html): bf16 literal suffix for __bf16 constants. Forge: c++config.h:889 `__decltype(0.0bf16)` whenever __BFLT16_DIG__ is predefined. |
| `statement expression ({ ... })` | syntax | M | 26/9 | aarch64/bits/cpu-set.h:58 (in `#define __CPU_SET_S`) | `(unconditional)` | M1 macro only | [Statement-Exprs](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Statement-Exprs.html): A compound statement enclosed in parentheses may appear as an expression in GNU C. |
| `zero-length array member` | syntax | M | 4/4 | aarch64/bits/fcntl-linux.h:369 | `#ifdef __USE_GNU` | M1 (&lt;dlfcn.h&gt;, &lt;fcntl.h&gt;, &lt;link.h&gt;) | [Zero-Length](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Zero-Length.html): Trailing T x[0] member; GCC extension in C++ (Zero Length Arrays). |

Not reached in M1 (rows in the appendix): `imaginary constant suffix` (gnu++20 only), `pp-number suffix BF16` (not reached).

`__extension__` precedes 218 declarations and expressions; the manual's Alternate-Keywords page says it only prevents `-pedantic` warnings. The statement expressions are all inside glibc macros (`__CPU_SET_S`, `__bswap_*` fallbacks, `__tobody`) that no M1 header expands.

### 3.11 asm, including glibc's `__REDIRECT` renaming

glibc renames C functions at the assembly level with `__REDIRECT (name, proto, alias)`, which expands to `name proto __asm__ (__ASMNAME (#alias))` (cdefs.h:410). It is defined only for `__GNUC__ >= 2` or `__clang_major__ >= 4` (cdefs.h:408); in C++ the `_NTH` forms put `__THROW` before the label (cdefs.h:411-415). Counting invocations in entered code:

| Configuration | `__REDIRECT*` invocations in entered code | By macro | By header |
|---|---|---|---|
| `m1` | 41 | __REDIRECT 8, __REDIRECT_NTH 32, __REDIRECT_NTHNL 1 | wchar.h 16, stdlib.h 10, stdio.h 6, pthread.h 5, inttypes.h 4 |
| `m1-fortify` | 129 | __REDIRECT 34, __REDIRECT_FORTIFY 3, __REDIRECT_FORTIFY_NTH 3, __REDIRECT_NTH 85, __REDIRECT_NTHNL 4 | aarch64/bits/wchar2-decl.h 31, aarch64/bits/unistd-decl.h 25, wchar.h 16, aarch64/bits/stdlib.h 10, stdlib.h 10, aarch64/bits/stdio2-decl.h 8, stdio.h 6, pthread.h 5, aarch64/bits/fcntl2.h 4, aarch64/bits/poll2.h 4, inttypes.h 4, aarch64/bits/setjmp2.h 3, aarch64/bits/string_fortified.h 2, aarch64/bits/fcntl-linux-fortify.h 1 |
| `neither` | 0 |  |  |

In M1 the 41 are mostly C23/ISO C99 renames: `strtol` to `__isoc23_strtol`, the `strto*`/`wcsto*` families and the `*scanf` families (stdlib.h:217-388, wchar.h:524-907, stdio.h:449-526, inttypes.h:389-399). The chain that selects them is:
1. `_GNU_SOURCE` defines `_ISOC23_SOURCE` (features.h:218-226).
2. That makes `__GLIBC_USE (ISOC23)` true (features.h:267-270).
3. That makes `__GLIBC_USE_C23_STRTOL` 1 (features.h:509-510).

pthread.h adds five more, for example `pthread_yield` to `sched_yield` (pthread.h:479) and `__sigsetjmp_cancel` to `__sigsetjmp` (pthread.h:766). Direct `__asm__` uses, folded by site family:

| Kind | Family | Sites | Count | First operand | Innermost guard (verbatim) | Reached |
|---|---|---|---|---|---|---|
| `asm label (symbol rename)` | macro __REDIRECT | aarch64/sys/cdefs.h:410 | 1 | `__ASMNAME ( # alias )` | `#if (defined __GNUC__ && __GNUC__ >= 2) \|\| (__clang_major__ >= 4)` | M1 |
| `asm label (symbol rename)` | macro __REDIRECT_NTH | aarch64/sys/cdefs.h:412 | 1 | `__ASMNAME ( # alias )` | `#ifdef __cplusplus` | M1 |
| `asm label (symbol rename)` | macro __REDIRECT_NTHNL | aarch64/sys/cdefs.h:414 | 1 | `__ASMNAME ( # alias )` | `#ifdef __cplusplus` | M1 |
| `asm label (symbol rename)` | macro __REDIRECT_NTH | aarch64/sys/cdefs.h:417 | 1 | `__ASMNAME ( # alias )` | `#else /* of #ifdef __cplusplus */` | not reached |
| `asm label (symbol rename)` | macro __REDIRECT_NTHNL | aarch64/sys/cdefs.h:419 | 1 | `__ASMNAME ( # alias )` | `#else /* of #ifdef __cplusplus */` | not reached |
| `asm label (symbol rename)` | macro __LDBL_REDIR_DECL | aarch64/sys/cdefs.h:739, 778 | 2 | `__ASMNAME ( "__" # name "ieee128" )` | `#ifdef __REDIRECT` | not reached |
| `asm label (symbol rename)` | macro __REDIRECT_LDBL | aarch64/sys/cdefs.h:741 | 1 | `__ASMNAME ( "__" # alias "ieee128" )` | `#ifdef __REDIRECT` | not reached |
| `asm label (symbol rename)` | macro __LDBL_REDIR2_DECL | aarch64/sys/cdefs.h:745, 774 | 2 | `__ASMNAME ( "__" # name "ieee128" )` | `#ifdef __REDIRECT` | not reached |
| `asm label (symbol rename)` | macro __LDBL_REDIR1_DECL | aarch64/sys/cdefs.h:751, 776 | 2 | `__ASMNAME ( # alias )` | `#ifdef __REDIRECT` | not reached |
| `asm label (symbol rename)` | long double / _Float128 ABI aliases | c++/bits/locale_facets_nonio.tcc:647 | 1 | `"snprintf"` | `#if defined _GLIBCXX_LONG_DOUBLE_ALT128_COMPAT && defined __LONG_DOUBLE_IEEE128__` | not reached |
| `asm label (symbol rename)` | long double / _Float128 ABI aliases | c++/format:1863, 1867, 1871 | 3 | `"_ZSt8to_charsPcS_e"` | `#ifdef __LONG_DOUBLE_IEEE128__` | not reached |
| `asm label (symbol rename)` | long double / _Float128 ABI aliases | c++/format:1875, 1879, 1883 | 3 | `"_ZSt8to_charsPcS_u9__ieee128"` | `#elif __cplusplus == 202002L` | not reached |
| `asm label (symbol rename)` | long double / _Float128 ABI aliases | c++/format:1904, 1912, 1920 | 3 | `"_ZNSt3__88to_charsEPcS0_DF128_"` | `#if _GLIBCXX_INLINE_VERSION` | not reached |
| `asm label (symbol rename)` | long double / _Float128 ABI aliases | c++/format:1906, 1914, 1922 | 3 | `"_ZSt8to_charsPcS_DF128_"` | `#else /* of #if _GLIBCXX_INLINE_VERSION */` | not reached |
| `inline asm (basic)` | top-level asm statement | c++/iostream:84 | 1 | `".globl _ZSt21ios_base_library_initv"` | `#elif defined(_GLIBCXX_SYMVER_GNU) && defined(__ELF__)` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | signal.h:151 | 1 | `"__xpg_sigpause"` | `#ifdef __GNUC__` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | stdlib.h:762 | 1 | `"at_quick_exit"` | `#ifdef __cplusplus` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | string.h:99, 101, 131, 133, 142, 145, ... | 20 | `"memchr"` | `#ifdef __CORRECT_ISO_CPP_STRING_H_PROTO` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | strings.h:49, 51, 77, 79 | 4 | `"index"` | `#ifdef __CORRECT_ISO_CPP_STRINGS_H_PROTO` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | wchar.h:189, 191, 203, 205, 233, 236, ... | 12 | `"wcschr"` | `#ifdef __CORRECT_ISO_CPP_WCHAR_H_PROTO` | M1 |
| `asm label (symbol rename)` | C++ overload or POSIX alias | wchar.h:366, 372 | 2 | `"btowc"` | `#ifdef __USE_EXTERN_INLINES` | M1 |

Facts:
- There are 40 direct asm labels in M1-reached code.
  - 36 are on `extern "C++"` const-correct overloads in string.h (20), strings.h (4) and wchar.h (12). For example, `extern const char *strchr (const char *__s, int __c) __THROW __asm ("strchr")` (string.h:244) makes a C++ overload refer to the unmangled C symbol.
  - The other four are `__btowc_alias`/`__wctob_alias` (wchar.h:366, 372; helpers of extern-inline `btowc`/`wctob`), `sigpause` to `__xpg_sigpause` (signal.h:151) and the C++ `at_quick_exit` (stdlib.h:762).
- The only top-level asm statement reached is iostream:84, `__extension__ __asm (".globl _ZSt21ios_base_library_initv");`. It is selected when libstdc++ initializes the standard streams inside the library (`_GLIBCXX_USE_INIT_PRIORITY_ATTRIBUTE` and `__has_attribute(__init_priority__)`) on an ELF symbol-versioned target. The emitted reference makes every translation unit that includes `<iostream>` depend on that libstdc++ symbol.
- The `long double`/`_Float128` aliases in `<format>` and `locale_facets_nonio.tcc` need `__LONG_DOUBLE_IEEE128__` or `_GLIBCXX_INLINE_VERSION`, which are powerpc64le and versioned-namespace configurations, so they are never reached.
- No extended or basic `asm` statement inside a function body is reached in any configuration.

### 3.12 aarch64-specific

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__Float32x4_t` | aarch64 type | M | 1/1 | aarch64/bits/math-vector.h:192 | `#if __GNUC_PREREQ(9, 0)` | M1 (8 roots) | Arm ACLE AdvSIMD type (not in the GCC manual); glibc vector-math declarations only. |
| `__Float64x2_t` | aarch64 type | M | 1/1 | aarch64/bits/math-vector.h:193 | `#if __GNUC_PREREQ(9, 0)` | M1 (8 roots) | Arm ACLE AdvSIMD type (not in the GCC manual); glibc vector-math declarations only. |
| `__SVBool_t` | aarch64 type | M | 1/1 | aarch64/bits/math-vector.h:204 | `#if __GNUC_PREREQ(10, 0) \|\| __glibc_clang_prereq(11, 0)` | M1 (8 roots) | Arm ACLE sizeless SVE predicate type (not in the GCC manual); glibc vector-math declarations only. |
| `__SVFloat32_t` | aarch64 type | M | 1/1 | aarch64/bits/math-vector.h:202 | `#if __GNUC_PREREQ(10, 0) \|\| __glibc_clang_prereq(11, 0)` | M1 (8 roots) | Arm ACLE sizeless SVE type (not in the GCC manual); glibc vector-math declarations only. |
| `__SVFloat64_t` | aarch64 type | M | 1/1 | aarch64/bits/math-vector.h:203 | `#if __GNUC_PREREQ(10, 0) \|\| __glibc_clang_prereq(11, 0)` | M1 (8 roots) | Arm ACLE sizeless SVE type (not in the GCC manual); glibc vector-math declarations only. |

They are all in bits/math-vector.h (section 2.4). The `aarch64_vector_pcs` attribute is in the section 3.8 table, reached through `__vpcs`. `__uint128_t` is unconditional in the kernel's `asm/sigcontext.h:81` (`struct fpsimd_context`) and `sys/user.h:32` (`struct user_fpsimd_struct`); it is in the 3.10 table. `long double` on this target is IEEE binary128 (`__LDBL_MANT_DIG__ 113`, and c++config.h:869 selects `_GLIBCXX_LDOUBLE_IS_IEEE_BINARY128`). No NEON or SVE intrinsic header (`arm_neon.h`, `arm_sve.h`) is in the closure.

### 3.13 Preprocessor operators used outside `#if`

| Name | Kind | Class | Uses/files | Representative site | Innermost guard (verbatim) | Reached | Semantics (GCC 15.2 manual) |
|---|---|---|---|---|---|---|---|
| `__has_attribute` | pp operator | M | 1/1 | aarch64/sys/cdefs.h:45 (in `#define __glibc_has_attribute`) | `#if (defined __has_attribute && (!defined __clang_minor__ \|\| 3 < __clang_major__ + (5 <= __clang_minor__)))` | M1 (via macro) | [__has_attribute](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/_005f_005fhas_005fattribute.html): The special operator __has_attribute (operand) may be used in ‘#if’ and ‘#elif’ expressions to test whether the attribute referenced by its operand ... |
| `__has_builtin` | pp operator | M | 3/2 | c++/aarch64/bits/c++config.h:898 (in `#define _GLIBCXX_HAS_BUILTIN`) | `#else /* of #ifdef __is_identifier */` | M1 (via macro) | [__has_builtin](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/_005f_005fhas_005fbuiltin.html): The special operator __has_builtin (operand) may be used in constant integer contexts and in preprocessor ‘#if’ and ‘#elif’ expressions to test ... |
| `__has_extension` | pp operator | M | 1/1 | aarch64/sys/cdefs.h:55 (in `#define __glibc_has_extension`) | `#ifdef __has_extension` | M1 (via macro) | [__has_extension](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/_005f_005fhas_005fextension.html): The special operator __has_extension (operand) may be used in constant integer contexts and in preprocessor ‘#if’ and ‘#elif’ expressions to test ... |
| `__has_include` | pp operator | M | 1/1 | c++/aarch64/bits/c++config.h:937 (in `#define _GLIBCXX_USE_TBB_PAR_BACKEND`) | `#ifndef _GLIBCXX_USE_TBB_PAR_BACKEND` | M1 (via macro) | [__has_include](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/cpp/_005f_005fhas_005finclude.html): The special operators __has_include (operand) and __has_include_next (operand) may be used in ‘#if’ and ‘#elif’ expressions to test whether the ... |

Not reached in M1 (rows in the appendix): `__is_identifier` (clang identity only).

## 4. Counts and observations

### 4.1 Counts per group

*Reached in M1* counts names with label M1 (in code or via macro); *M1 macro only* counts names only in unexpanded macro bodies; the last column splits all M1-reachable names (both kinds) by class.

| Group | Distinct names | Occurrences | Reached in M1 | M1 macro only | Only outside M1 | M1-reachable by class M / L / A |
|---|---|---|---|---|---|---|
| Type-trait keywords (cp-trait.def, `__integer_pack`) | 60 | 209 | 59 | 0 | 1 | 59 / 0 / 0 |
| Type-trait `__builtin_*` (C++ front end) | 3 | 4 | 2 | 0 | 1 | 2 / 0 / 0 |
| Constexpr / language-support builtins | 21 | 215 | 11 | 3 | 7 | 14 / 0 / 0 |
| Control-flow and hint builtins | 9 | 155 | 6 | 0 | 3 | 4 / 0 / 2 |
| Bit, byte-swap and overflow builtins | 19 | 68 | 12 | 0 | 7 | 12 / 0 / 0 |
| Memory/string library builtins | 21 | 139 | 19 | 0 | 2 | 0 / 19 / 0 |
| Floating-point classification/constant builtins | 61 | 310 | 27 | 11 | 23 | 38 / 0 / 0 |
| Math library builtins | 296 | 747 | 207 | 0 | 89 | 0 / 207 / 0 |
| Varargs builtins | 8 | 34 | 3 | 4 | 1 | 7 / 0 / 0 |
| Object-size / fortify builtins | 18 | 28 | 1 | 1 | 16 | 0 / 0 / 2 |
| `__atomic_*` builtins (no `__sync_*` is used) | 16 | 113 | 16 | 0 | 0 | 16 / 0 / 0 |
| GNU attributes | 51 | 774 | 31 | 6 | 14 | 9 / 0 / 28 |
| Standard attributes (incl. reserved spellings) | 8 | 1212 | 8 | 0 | 0 | 1 / 0 / 7 |
| Pragmas | 17 | 930 | 5 | 0 | 12 | 0 / 0 / 5 |
| Keyword and type extensions | 41 | 4720 | 26 | 3 | 12 | 22 / 0 / 7 |
| asm usage (kinds) | 2 | 66 | 2 | 0 | 0 | 2 / 0 / 0 |
| Syntax and directive extensions | 9 | 123 | 4 | 3 | 2 | 6 / 0 / 1 |
| Preprocessor operators (in code) | 5 | 7 | 4 | 0 | 1 | 4 / 0 / 0 |
| aarch64-specific types | 5 | 5 | 5 | 0 | 0 | 5 / 0 / 0 |

Totals: 670 distinct names: of those reachable in M1, 201 are class M, 226 class L and 52 class A; 191 are reachable only outside M1 or not at all. The per-name lists are in appendix G.

### 4.2 Observations: must implement correctly

These are phrased as constraints for the downstream "Drop-in compatibility surface" ticket, not decisions.

1. **Constant-evaluation builtins.**
   - `__builtin_is_constant_evaluated` must be exact (section 3.6); it is the single switch between libstdc++'s constexpr and run-time paths.
   - `__builtin_constant_p` must return 1 for a foldable argument during constant evaluation (char_traits.h:233); outside it, 0 is allowed.
   - `__builtin_bit_cast`, `__builtin_addressof`, `__builtin_launder`, `__builtin_source_location` and the four `__builtin_coro_*` used by `<coroutine>`.
   - The generic bit builtins `__builtin_clzg`, `__builtin_ctzg` and `__builtin_popcountg`, which implement the `constexpr` `<bit>` functions (bit:208, 265, 307).
   - `__builtin_mul_overflow`, which `std::allocator<T>::allocate` calls only *inside* `if (std::__is_constant_evaluated())` (allocator.h:196-198), so only ever during constant evaluation.
   - `__builtin_huge_val*`, `__builtin_nan*` and `__builtin_nans*`, which are `constexpr` in `std::numeric_limits`.
2. **Trait keywords.** These are the 59 reached trait keywords (`__integer_pack` included) and the two reached `__builtin_is_*` trait builtins.
   - 27 have M1 uses outside any test that names them, so `__has_builtin` cannot opt out of them (section 3.1).
   - The other 32 are used only under such a test: libstdc++ falls back to a library template, or omits the feature, if Forge answers 0.
   - The same identifiers also name libstdc++ class templates (`std::__is_invocable`), so they cannot simply be reserved words.
3. **asm labels.**
   - The 41 `__REDIRECT` declarations in M1, which carry real semantic changes such as C23 `0b`-prefix parsing in `__isoc23_strtol` and the `__isoc23_*scanf` family.
   - The 40 direct asm labels, 36 of them on `extern "C++"` overloads.
   - In fortify builds, 129 `__REDIRECT*`. A compiler that ignored them would link against the wrong glibc symbols with no diagnostic.
4. **The top-level `.globl` asm statement** in `<iostream>` (iostream:84) must reach the assembler.
5. **`abi_tag`** (`_GLIBCXX_ABI_TAG_CXX11`, 17 uses) changes the mangled names (`B5cxx11`) of libstdc++ symbols that Forge's objects reference. Ignoring it produces link errors against libstdc++.so.
6. **`gnu_inline` with `extern inline`.** glibc's `__extern_inline` and `__extern_always_inline` (cdefs.h:622-623) are used at `-O2` for `string.h`/`strings.h` C++ overloads, `ctype.h`, `stdlib.h`, `wchar.h` and `pthread.h`. Such a definition may be inlined but must never be emitted out of line, because the symbol belongs to libc.
7. **Layout and type attributes.**
   - `aligned`, `mode` (cxxabi_tweaks.h:46, `__guard` as `__attribute__((mode(__DI__)))`) and `may_alias`.
   - `[[no_unique_address]]` (77 uses, layout of `std::tuple`, hashtables, `ranges` views).
   - `__attribute__((__weak__))` on `__pthread_unwind_next` (pthread.h:753) when referenced.
8. **Types.**
   - `long double` (binary128) and `__uint128_t` for struct layout.
   - `__int128`, if Forge predefines `__SIZEOF_INT128__`.
   - `_Float32`, `_Float64`, `_Float128`, `_Float32x` and `_Float64x` as distinct types if Forge reports `__GNUC__ >= 13` (section 2.4).
   - `__complex__` with `__real__`/`__imag__` for `std::complex`.
   - The ACLE types `__Float32x4_t`, `__Float64x2_t`, `__SVFloat32_t`, `__SVFloat64_t` and `__SVBool_t`, with the `aarch64_vector_pcs` attribute, at least as far as parsing declarations if Forge reports `__GNUC__ >= 10`.
9. **Keywords and syntax.**
   - `__typeof__`/`__typeof`, `__decltype`, `__alignof__`, `__null` (GCC's `NULL`), `__thread` (`<mutex>`) and `__PRETTY_FUNCTION__` (in `assert`).
   - `#include_next`.
   - The zero-length array member (fcntl-linux.h:369 and three others in `<dlfcn.h>`/`<link.h>` paths). glibc's `__flexarr` is defined as `[]` but no M1 header expands it.
   - The `bf16` literal suffix whenever `__BFLT16_DIG__` is predefined.
10. **Varargs and stack builtins.** `__builtin_va_list` and the `va_*` builtins (AAPCS64 `va_list` layout), and `__builtin_alloca` (28 uses).
11. **Atomics.** All 16 `__atomic_*` builtins, `__builtin_clear_padding` (a no-op only for padding-free types), and the predefined `__ATOMIC_*`/`__GCC_ATOMIC_*` values.
12. **Lowering choices that must still be correct (class L).**
    - Every reached math builtin (207) and memory/string builtin (19) may be lowered to a call of the same-named libc/libm function. They are reached from `<cmath>` overloads and from char_traits run-time paths.
    - `__builtin_abort` may likewise be a call to `abort`; it is what `_GLIBCXX_THROW_OR_ABORT` expands to under `-fno-exceptions`.
    - `__builtin_alloca` (stack allocation) and `__builtin_trap` (a trapping instruction) cannot be lowered that way.
13. **Byte-identity hazards** (stage1 against stage2):
    - `__builtin_FILE` and `__PRETTY_FUNCTION__` text are embedded at every `assert` (assert.h:128-137).
    - `__builtin_source_location` embeds file and function names.

    Their spelling must be deterministic and independent of the build directory.

### 4.3 Observations: accept and ignore is safe

- **Attributes.** These change only diagnostics or optimization: `nonnull`, `returns_nonnull`, `format`, `format_arg`, `access`, `alloc_size`, `alloc_align`, `malloc` (including the two-argument deallocator form), `pure`, `const`, `cold`, `leaf`, `warn_unused_result`, `deprecated`, `unused`, `used`, `noinline`, `noclone`, `artificial`, `externally_visible`, `flag_enum`, `nonstring`, `warning` and `error`. `error`/`warning` are reached only through fortify's `__errordecl`/`__warnattr`; GCC turns them into diagnostics when a call survives optimization.
- **Attributes that only need to parse.**
  - `always_inline` (297 uses): the manual says "Failure to inline such a function is diagnosed as an error" (Common-Function-Attributes), so honouring it is a diagnostic, not a semantic.
  - `noreturn`, `assume` and `[[likely]]`/`[[unlikely]]`: ignoring is safe for correct programs; acting on them is an optimization.
- **Standard attributes:** `[[nodiscard]]` (894 uses), `[[deprecated]]`, `[[maybe_unused]]`, `[[fallthrough]]`, `[[noreturn]]`.
- **Builtins.**
  - `__builtin_expect` (74 uses) may be the identity, and `__builtin_assume_aligned` is the identity on its pointer.
  - `__builtin_unreachable` may be lowered to nothing or a trap.
  - `__builtin_object_size`/`__builtin_dynamic_object_size` may return the "unknown" value, as the manual's Object-Size-Checking page allows.
  - `__builtin_constant_p` may return 0 outside constant evaluation. The manual says "A return of 0 does not indicate that the expression is not a constant, but merely that GCC cannot prove it is a constant"; for the exception, see section 4.2 item 1.
- **Pragmas:** `GCC system_header`, `GCC diagnostic` (585 uses, push/pop/ignored), `GCC unroll`, `GCC visibility push/pop` (PIE, no shared objects of Forge's own), and `_Pragma` built from glibc's `__glibc_macro_warning1`.
- **Keywords:** `__extension__`, `__restrict`/`__restrict__` (1,245 uses; an aliasing promise), `__inline`, `__signed__`.
- **Directives:** `#warning` (reached only through `<strstream>`'s deprecation warning).
- **`visibility` attributes and pragmas** on a statically linked PIE matter only for symbols exported from shared objects, which Forge does not build in milestone 1. This is a judgement about Forge's output, not a fact from the headers.

### 4.4 Observations: only reachable outside Forge's configuration

- **Fortify** (`_FORTIFY_SOURCE > 0`, Ubuntu's g++ default at `-O2`):
  - 16 `__builtin___*_chk`;
  - `__builtin_va_arg_pack`/`_len` in always-inline wrappers;
  - `__builtin_constant_p` on lengths;
  - `__REDIRECT_FORTIFY`;
  - 88 more `__REDIRECT*`;
  - the clang `diagnose_if`, `pass_object_size`, `pass_dynamic_object_size`, `enable_if`, `overloadable` and `unavailable` attributes (clang identity plus fortify).

  The stage0 g++ build of Forge on Ubuntu therefore sees this code unless the build passes `-U_FORTIFY_SOURCE` or `-D_FORTIFY_SOURCE=0`; a Forge-built stage1 sees it only if Forge predefines `_FORTIFY_SOURCE`.
- **Exceptions and RTTI:** `try`/`catch` paths, `typeid`, `type_info` comparisons and pthread.h:565's C++ cleanup class (gcc-eh only).
- **`-std=gnu++20`:** `__int128` as an integral type, `__GLIBCXX_TYPE_INT_N_0`, the `i` imaginary constant suffix (complex.h:52) and C99 `<complex.h>`.
- **C++23 and later:** the `__STDCPP_FLOAT*_T__` paths, `__builtin_is_virtual_base_of`, `__is_scoped_enum`, `if consteval`, `__cpp_static_call_operator` and the `BF16` suffix.
- **Clang identity only:**
  - `__make_integer_seq`;
  - `__builtin_operator_new`/`__builtin_operator_delete` (GCC as well, if its `__has_builtin` value is 201802L; section 5);
  - `#pragma clang diagnostic`;
  - `__is_identifier`;
  - `__attribute__((__neon_vector_type__))`.
- **Never reached:**
  - **C-only constructs:** `_Generic`, `_Static_assert` and `_Noreturn` fallbacks, `__builtin_types_compatible_p`, `__builtin_choose_expr`, `__builtin_tgmath`, `__builtin_classify_type`, `__builtin_complex`, `__auto_type` (`<stdatomic.h>`), the `cleanup` attribute (pthread.h C path) and `_Atomic`.
  - **Other targets and ABIs:** `__float128`, `__float80`, `__ibm128`, `__builtin_ia32_pause`, `__builtin_nansq`, `dllimport`/`stdcall`, `#pragma intrinsic`, and the powerpc `long double` asm aliases.
  - **Parallel mode and OpenMP:** `#pragma omp` (9 forms), `weakref` (`_GLIBCXX_GTHREAD_USE_WEAK` is 0), and the `bitwise` kernel checker attribute.

## 5. Known unknowns

1. **No GCC was run.**
   - Reachability comes from preprocessing with Apple clang 17 plus GCC's predefine deltas and `__has_builtin` answers, not from g++ itself.
   - `__has_attribute`, `__has_cpp_attribute`, `__has_feature`, `__has_extension` and `__has_include` were answered by Apple clang in every run. For the 34 operands involved (section 2.2), GCC 15.2 is expected to agree for the GNU attributes, but this was not verified.
   - The g++ search list (section 1) was not confirmed with `g++ -v`, and neither was the absence of an `include-fixed` directory.
2. **Predefines that m1 inherited from clang.**
   - `_GNU_SOURCE 1` came from clang's predefines. GCC's source for it in C++ on GNU/Linux (the driver's `CPLUSPLUS_CPP_SPEC` in `gcc/config/gnu-user.h`) was not read. It decides `__USE_GNU`, and with it the C23 `strtol` redirects.
   - `__GNUC_GNU_INLINE__` was kept from clang, while GCC defines `__GNUC_STDC_INLINE__` unless `flag_gnu89_inline` (`c-cppbuiltin.cc`). The only two tests (cdefs.h:618, 621) give the same result in C++ either way.
3. **`__has_builtin(__builtin_operator_new)`.** Its value in GCC 15.2 is not stated in the manual, and the code that computes `__has_builtin` (`c-family/c-lex.cc`) was not read. If it is 201802L, as for Clang, m1 takes new_allocator.h:116 and stl_tempbuf.h:70, using `__builtin_operator_new`/`__builtin_operator_delete`, rather than `::operator new`.
4. **The "neither" run is impure.** It left Apple clang's `__GNUG__ 4` defined, which affects gcc/stddef.h:228 and `NULL` as `__null` at stddef.h:415. It also kept clang's `__has_*` answers, so the libstdc++ side of "neither" is the clang-answer side.
5. **The "clang" run is Apple clang 17** (`__clang_major__ 17`, `__GNUC__ 4.2`). Another clang, upstream or a different version, reports other version numbers and may answer `__has_builtin` differently, for example for `__array_rank` and `__builtin_clear_padding`, which Apple clang 17 lacks. So the clang-identity diff is specific to Apple clang 17; upstream clang's answers were not consulted.
6. **"Reached" is approximate.**
   - For macro bodies, a reference closure over identifiers stands in for real expansion: an entered `#define` counts if any entered code or `#if` mentions it, even in an unevaluated context. "M1 macro only" can therefore hide uses that user code would trigger, such as `assert` or `offsetof`.
   - Template code is counted when its text is entered, whether or not Forge's sources instantiate it.
   - The scanner is token-based, not a parser. Asm-label detection looks back at the previous token, now restored across `#else`/`#elif` (the fix in the first commit). A trait name counts only before `(` (section 3.1). Detection of zero-length and flexible array members uses line patterns.
7. **The class L claim** (library builtins called only outside constant evaluation) was checked by hand in char_traits.h, array and stl_algobase.h, not at every one of the 226 names' sites.
8. **Not documented in the GCC 15.2 manual:**
   - `aarch64_vector_pcs`, `__Float32x4_t`, `__Float64x2_t`, `__SVFloat32_t`, `__SVFloat64_t`, `__SVBool_t` (Arm ACLE, not read);
   - `__builtin_addressof`, `__builtin_launder`, `__builtin_source_location`, `__builtin_is_corresponding_member`, `__builtin_is_pointer_interconvertible_with_class` and most `cp-trait.def` traits, whose existence comes from GCC's tables but whose semantics come from the C++ standard library they implement.
9. **Ubuntu patches.** The GCC source files were read at upstream tag `releases/gcc-15.2.0`. Ubuntu's 15.2.0-16ubuntu1 may patch them; the package's own sources were not compared. The fetch URLs of those files were not recorded, but the SHA256 prefixes in section 0 identify them.
10. **Out of scope.** Headers outside the 142 roots' closure are not covered, for example `<arm_neon.h>`, C++23 headers such as `<stdatomic.h>` and `<print>`, and `<sys/socket.h>`.
