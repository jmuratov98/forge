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

<!-- GEN:closure -->

The static closure is an upper bound: it follows includes inside every branch, so it reaches, for example, the parallel-mode and PSTL TBB/OpenMP backends that no configuration enters. Fifteen includes do not resolve (appendix B): BSD/Darwin headers from GCC's `stddef.h`, TBB, OpenMP, `<config.h>`, and `gnu/stubs-lp64_be.h`. None is reached. In this document, "reached" always means the entered set, never the static set.

## 2. Predefined-macro steering surface

Across the closure, 2,695 distinct identifiers appear in `#if` expressions. Of these, 698 are never defined by any header in the closure: they come from the compiler, the command line or the user. Appendix C lists all of them with test counts, the GCC 15.2 value with its source, the Apple clang 17 value, an example site, the verbatim test and the first line it selects. The subsections below cover the ones that select between compiler-specific paths.

### 2.1 Compiler identity

Column *Tests/files/live in M1* counts `#if` lines that test the macro: all of them, the files they are in, and how many are evaluated in M1 (that is, their own enclosing block was entered).

<!-- GEN:steer_identity -->

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

<!-- GEN:identity_diff -->

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

<!-- GEN:builtins_trait_m1 -->

### 3.2 Memory, bit, overflow and math builtins

**Bit, byte-swap and overflow.**

<!-- GEN:builtins_bit_m1 -->

**Memory and string library builtins** (class L: libstdc++ calls them only outside constant evaluation, behind `std::__is_constant_evaluated()`; checked in char_traits.h, array, stl_algobase.h, not proven for every site).

<!-- GEN:builtins_memory_m1 -->

**Floating-point classification and constants.** Variants are folded, so `__builtin_nan{,f,l}` stands for three names. These are class M because `std::numeric_limits` members are `constexpr` and use `__builtin_huge_val*`, `__builtin_nan*` and `__builtin_nans*` (limits:1723-1729).

<!-- GEN:builtins_fpclass_m1 -->

**Math library builtins.** There are 296 names (747 uses), mostly `<cmath>` overloads that forward `std::sin(float)` to `__builtin_sinf` and so on. 207 are reached in M1. The 89 that are not are almost all `_Float128` variants reached only under C++23 macros. All are class L: the corresponding libm function is a correct lowering. The full table is appendix F.8.

### 3.3 Atomics

All 16 are reached in M1. Most uses are in bits/atomic_base.h and bits/atomic_wait.h. The widest-reaching is `__atomic_fetch_add`, in 33 roots, because ext/atomicity.h:68-73 uses it in `__exchange_and_add` and `__atomic_add`, libstdc++'s reference-count helpers. No `__sync_*` builtin is used anywhere in the closure. The manual specifies the memory-model argument; milestone 1 lowers these the way `-moutline-atomics` does (an ABI-level choice; no header tests it).

<!-- GEN:atomics_m1 -->

### 3.4 Varargs

<!-- GEN:builtins_varargs_m1 -->

`__builtin_va_arg_pack` and `__builtin_va_arg_pack_len` are reached only through glibc's fortify wrappers (`__va_arg_pack`, section 3.7).

### 3.5 Control-flow and hint builtins

<!-- GEN:builtins_control_m1 -->

### 3.6 Constexpr-relevant and language-support builtins

<!-- GEN:builtins_constexpr_m1 -->

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

<!-- GEN:builtins_fortify_m1 -->

### 3.8 Attributes

**GNU attributes** (`__attribute__((...))`, `__attribute((...))` and `[[gnu::...]]`/`[[__gnu__::...]]`). Many reach M1 only through glibc's or libstdc++'s wrapper macros (appendix E lists each macro and its M1 expansion). In C++ glibc's `__THROW` is `noexcept (true)`, not `__attribute__ ((__nothrow__))` (cdefs.h:85-88), so the `nothrow` attribute is **not reached** in C++ at all.

<!-- GEN:attributes_m1 -->

**Standard attributes.** libstdc++ mostly uses the reserved `__name__` spellings.

<!-- GEN:std_attributes_m1 -->

### 3.9 Pragmas

<!-- GEN:pragmas_m1 -->

`#pragma GCC system_header` opens 222 headers. GCC's CPP manual says it gives "the code that follows ... the same treatment as a system header": warnings other than `#warning` are suppressed (System-Headers page). It changes no semantics.

### 3.10 Keyword, type and syntax extensions

<!-- GEN:keywords_m1 -->

**Syntax and directives.**

<!-- GEN:syntax_m1 -->

`__extension__` precedes 218 declarations and expressions; the manual's Alternate-Keywords page says it only prevents `-pedantic` warnings. The statement expressions are all inside glibc macros (`__CPU_SET_S`, `__bswap_*` fallbacks, `__tobody`) that no M1 header expands.

### 3.11 asm, including glibc's `__REDIRECT` renaming

glibc renames C functions at the assembly level with `__REDIRECT (name, proto, alias)`, which expands to `name proto __asm__ (__ASMNAME (#alias))` (cdefs.h:410). It is defined only for `__GNUC__ >= 2` or `__clang_major__ >= 4` (cdefs.h:408); in C++ the `_NTH` forms put `__THROW` before the label (cdefs.h:411-415). Counting invocations in entered code:

<!-- GEN:redirects -->

In M1 the 41 are mostly C23/ISO C99 renames: `strtol` to `__isoc23_strtol`, the `strto*`/`wcsto*` families and the `*scanf` families (stdlib.h:217-388, wchar.h:524-907, stdio.h:449-526, inttypes.h:389-399). The chain that selects them is:
1. `_GNU_SOURCE` defines `_ISOC23_SOURCE` (features.h:218-226).
2. That makes `__GLIBC_USE (ISOC23)` true (features.h:267-270).
3. That makes `__GLIBC_USE_C23_STRTOL` 1 (features.h:509-510).

pthread.h adds five more, for example `pthread_yield` to `sched_yield` (pthread.h:479) and `__sigsetjmp_cancel` to `__sigsetjmp` (pthread.h:766). Direct `__asm__` uses, folded by site family:

<!-- GEN:asm_summary -->

Facts:
- There are 40 direct asm labels in M1-reached code.
  - 36 are on `extern "C++"` const-correct overloads in string.h (20), strings.h (4) and wchar.h (12). For example, `extern const char *strchr (const char *__s, int __c) __THROW __asm ("strchr")` (string.h:244) makes a C++ overload refer to the unmangled C symbol.
  - The other four are `__btowc_alias`/`__wctob_alias` (wchar.h:366, 372; helpers of extern-inline `btowc`/`wctob`), `sigpause` to `__xpg_sigpause` (signal.h:151) and the C++ `at_quick_exit` (stdlib.h:762).
- The only top-level asm statement reached is iostream:84, `__extension__ __asm (".globl _ZSt21ios_base_library_initv");`. It is selected when libstdc++ initializes the standard streams inside the library (`_GLIBCXX_USE_INIT_PRIORITY_ATTRIBUTE` and `__has_attribute(__init_priority__)`) on an ELF symbol-versioned target. The emitted reference makes every translation unit that includes `<iostream>` depend on that libstdc++ symbol.
- The `long double`/`_Float128` aliases in `<format>` and `locale_facets_nonio.tcc` need `__LONG_DOUBLE_IEEE128__` or `_GLIBCXX_INLINE_VERSION`, which are powerpc64le and versioned-namespace configurations, so they are never reached.
- No extended or basic `asm` statement inside a function body is reached in any configuration.

### 3.12 aarch64-specific

<!-- GEN:aarch64_m1 -->

They are all in bits/math-vector.h (section 2.4). The `aarch64_vector_pcs` attribute is in the section 3.8 table, reached through `__vpcs`. `__uint128_t` is unconditional in the kernel's `asm/sigcontext.h:81` (`struct fpsimd_context`) and `sys/user.h:32` (`struct user_fpsimd_struct`); it is in the 3.10 table. `long double` on this target is IEEE binary128 (`__LDBL_MANT_DIG__ 113`, and c++config.h:869 selects `_GLIBCXX_LDOUBLE_IS_IEEE_BINARY128`). No NEON or SVE intrinsic header (`arm_neon.h`, `arm_sve.h`) is in the closure.

### 3.13 Preprocessor operators used outside `#if`

<!-- GEN:preproc_m1 -->

## 4. Counts and observations

### 4.1 Counts per group

*Reached in M1* counts names with label M1 (in code or via macro); *M1 macro only* counts names only in unexpanded macro bodies; the last column splits all M1-reachable names (both kinds) by class.

<!-- GEN:counts -->

Totals: <!-- GEN:class_counts -->. The per-name lists are in appendix G.

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
