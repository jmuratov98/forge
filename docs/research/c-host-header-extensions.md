# C-mode host header extension inventory

Research for GitHub issue #13 (parent map #1; consumer "Drop-in compatibility surface", #8). This is the C-mode counterpart of #9, which covered C++20 only. Throwaway branch `research/c-host-header-extensions`: never merged, no PR. This file is generated: `c-host-header-extensions/scripts/report.py` fills the tables into `scripts/main.md`, so edit the template, not this file. The full per-name table is the generated appendix [c-host-header-extensions/inventory.md](c-host-header-extensions/inventory.md); the same rows are in `data/inventory.tsv`.

**Question.** Which GCC extension names do glibc 2.43's headers and the kernel UAPI headers reach when compiled as C under milestone 1's configuration? For each one, must Forge implement it (M), may it lower to the same-named libc/libm call (L), or is it safe to accept and ignore (A)?

**Answer in brief.**
- The C headers reach **165 names**: 82 reached by header code and 83 only inside macros that no header expands.
  - Classes: 125 M, 3 L, 37 A.
  - 17 of them appear only in GCC's own `<stddef.h>`, `<stdarg.h>`, `<float.h>` and the `<stdint.h>`/`<limits.h>` wrappers, which Forge replaces with its own headers.
  - Restricted to glibc and kernel text, the count is 148: 77 reached by header code (47 M, 1 L, 29 A) and 71 macro only (61 M, 2 L, 8 A).
- The set barely depends on the dialect. 238 of 241 roots are accepted in all eight configurations, and 69 names are reached by header code in every one of them.
- The configuration differences are few and concrete (section 3.3):
  - `_GNU_SOURCE` adds `transparent_union`, the `_FloatN` declarations and the `__isoc23_*` renames (in every dialect).
  - gnu89 needs GNU89 `extern inline` semantics for `<error.h>`, where glibc omits `gnu_inline`.
  - gnu23 adds `bool` and `nullptr` (the latter in GCC's own `<stddef.h>`).
- GCC 15.2 answers every `__has_*` query the headers evaluate with 1, except `__has_builtin (__builtin_fclose)`, which is 0.

## Method

Real GCC, observed in a VM; no header text is interpreted by hand. The user approved the VM.

| Step | Script | What it does |
|---|---|---|
| 0 | `facts.sh` | package versions and hashes, `gcc-15 -v`, the specs Ubuntu's driver adds, `-dM` predefines per configuration |
| 1 | `roots.py` | root set from `dpkg -L libc6-dev` (#10's sweep rule) |
| 2 | `accept.py` | `gcc-15 -fsyntax-only` on every root × configuration; a pedantic pass (`-Wpedantic -Wc90-c99-compat -Wc99-c11-compat -Wc11-c23-compat -Wsystem-headers`), repeated with `-D__extension__=` so the extensions glibc marks with `__extension__` are diagnosed too |
| 3 | `pp.py` | `gcc-15 -E -dD` on every accepted pair (1,904 runs) |
| 4 | `gccsrc.sh`, `gccnames.py` | GCC 15.2.0's own tables; then gcc-15 itself classifies each of the 4,217 reserved identifiers and 39 attribute spellings the headers emit (`__has_builtin`, `int X;`, `typedef X t;`, `__has_attribute`) |
| 5 | `extract.py` | reached constructs, from the linemarkers (below) |
| 6 | `probe.py`, `probe-mount.sh` | which conditionals and `__has_*` operands GCC evaluated, its answers, and what changes when an answer is flipped (section 4) |
| 7 | `vmscan.py` | package owner of each opened header; every directive line and whether GCC entered it |
| 8 | `export.py`, `report.py`, `classes.py` | tables, classes, delta against #9 |

`vm.sh STEP` runs each step inside the VM. Raw `-E` output (23 MB compressed) stays in the VM's `~/c13`. The scripts regenerate it.

**Reachability, as #9 defined it but observed rather than inferred.** For each emitted line, the linemarkers give the header and line. The extractor compares the construct's tokens with that header line's own text, up to the next emitted line or directive:
- **code**: the tokens are written there.
- **via macro**: they are not; a macro that header code expanded produced them. The defining macro is found among the macros the line's identifiers reach.
- **macro only**: the construct sits in a `#define` that GCC processed (it appears in `-dD` output) but no header expanded. It becomes live only when user code expands the macro, for example `isnan`, `va_arg`, `offsetof`, `static_assert`, `CMPLX`.

**Origin.** The package of the header text that holds the construct: `glibc` is libc6-dev, `kernel` is linux-libc-dev (`dpkg -L`). `gcc` means GCC's own include directory; Forge ships its own versions of those headers, so those names are listed but are not requirements on glibc.

**Classes** are #9's:
- **M**: the semantics must be implemented correctly.
- **L**: a call to the same-named library function (or for `abs` the obvious expression) is a correct implementation outside constant evaluation.
- **A**: accepting the construct and ignoring it preserves behaviour.

A name #9 classified keeps #9's class unless C mode changes the reasoning; every change is in section 6.2. `scripts/classes.py` holds every class decision with its reason.

## 0. Sources and versions

**VM.** Lima 2.2.1 VM `forge-c13` (vz, native aarch64, 4 CPUs, 8 GiB), template `ubuntu-26.04`, running Ubuntu 26.04.1 LTS with kernel 7.0.0-34-generic (`data/facts/os-release.txt`, `uname.txt`).

**Packages.** Installed with apt from the template's mirror, `http://archive.ubuntu.com/ubuntu` (resolute, resolute-updates, resolute-security; `data/facts/apt-policy.txt`). The candidates were exactly #9's pins, so nothing was fetched by hand. The re-downloaded .debs hash to #9's section 0 values (`data/facts/deb-sha256.txt`), and `dpkg --verify` reports no changed file.

| Package | Version | SHA256 of the .deb |
|---|---|---|
| libc6-dev | 2.43-2ubuntu2.4 | `f6f7705d3e6bb982c173a42cc5b2516eddebe2d846c4861ee7d7c9d66ebee916` |
| linux-libc-dev | 7.0.0-43.43 | `3d6313ac30170df8614618fd1aeb864606c378d90aa18e5d2012aad46861d753` |
| gcc-15 | 15.2.0-16ubuntu1 | `772d57b952842e600fd7823b2aa217394d78b70756406a6b0e89297eb8d03fe8` |
| gcc-15-aarch64-linux-gnu | 15.2.0-16ubuntu1 | `e3483ce05b22e201393a40a8cea4414144dc73f45ca902dcc026123f76312d6a` |
| libgcc-15-dev | 15.2.0-16ubuntu1 | `d088c97ff459ab243eb369666dfc43b92f278556e45d72c2def4d7657d728fe4` |
| cpp-15-aarch64-linux-gnu | 15.2.0-16ubuntu1 | `57e316dfd840b2483a7e9db8af05f240712afa0f15f2d0f3a4426723c11646a7` |

**The compiler.**
- `gcc-15 -v` reports "gcc version 15.2.0 (Ubuntu 15.2.0-16ubuntu1)", Target `aarch64-linux-gnu` (Debian's triplet for `aarch64-unknown-linux-gnu`), configured `--enable-default-pie` (`data/facts/gcc-v.txt`).
- `gcc-15` is `/usr/bin/aarch64-linux-gnu-gcc-15`. Every run calls `gcc-15` by name.

**Driver defaults** (`gcc-15 -dumpspecs`, `*distro_defaults_cpp` and `*distro_defaults`, `data/facts/dumpspecs.txt`):
- `%{!O0:%{O*:%{!D_FORTIFY_SOURCE=*:%{!U_FORTIFY_SOURCE:-D_FORTIFY_SOURCE=3}}}}`, so there is no fortify at -O0. The -O0 cc1 line is `-mlittle-endian -mabi=lp64 -fasynchronous-unwind-tables -fstack-protector-strong -Wformat -Wformat-security -fstack-clash-protection -fzero-init-padding-bits=all -Wbidi-chars=any`; at -O2 it adds `-D_FORTIFY_SOURCE=3` (`v-E-O0.txt`, `v-E-O2.txt`).
- C search list: `/usr/lib/gcc/aarch64-linux-gnu/15/include`, `/usr/local/include`, `/usr/include/aarch64-linux-gnu`, `/usr/include`. There is no `include-fixed`.

**Predefines** (`gcc-15 -O0 [-std=…] [-D_GNU_SOURCE] -E -dM -x c /dev/null`, `data/facts/predef/`):
- `__OPTIMIZE__` and `_FORTIFY_SOURCE` are undefined in all eight configurations (`O0-checks.txt`).
- The default dialect's predefines equal `-std=gnu23`'s byte for byte, so `gnu23` is run with no `-std`.
- Between dialects only these differ:
  - gnu89 has `__GNUC_GNU_INLINE__` where the others have `__GNUC_STDC_INLINE__`;
  - `__STDC_VERSION__` is absent in gnu89, then `199901L` (gnu99), `201710L` (gnu17) and `202311L` (gnu23);
  - gnu99 and later add `__STDC_UTF_16__` and `__STDC_UTF_32__`;
  - gnu23 adds `__CHAR8_TYPE__` and `__GCC_ATOMIC_CHAR8_T_LOCK_FREE`.
- `_GNU_SOURCE` adds only itself.
- Fixed values that matter here: `__GNUC__ 15`, `__GNUC_MINOR__ 2`, `__SIZEOF_INT128__ 16`, `__LDBL_MANT_DIG__ 113` (binary128), `__FLT128_MANT_DIG__ 113`, `__CHAR_UNSIGNED__ 1`, `__USER_LABEL_PREFIX__` empty.

**GCC sources.**
- The GNU release tarball `https://ftp.gnu.org/gnu/gcc/gcc-15.2.0/gcc-15.2.0.tar.xz`. Its signature checks against `gnu-keyring.gpg` ("Good signature from Richard Guenther", key `7F74F97C103468EE5D750B583AB00996FC26A641`); SHA256 `438fd996826b0c82485a29da03a72d71d6e3541a83ec702df4271f6fe025d24e`.
- gcc.gnu.org's gitweb refused blob downloads with HTTP 429, so the tarball replaced #9's per-file tag fetch.
- Ubuntu builds 15.2.0 plus `debian/patches/git-updates.diff`: "updates from the 15 branch upto 20260321 (fa37bfd7f2d)" (`gcc-15_15.2.0-16ubuntu1.debian.tar.xz`, SHA256 `1c8154422ea6352d5453b1f27884a6639170d66725b7bb3e372baa1fc43b6f96`).
- That patch touches `c-common.cc`, `c-decl.cc`, `aarch64.cc`, `aarch64-builtins.cc` and `aarch64-sve-builtins.cc`. Its hunk headers (`c_build_shufflevector`, `c_common_get_alias_set`, `fold_offsetof`, `braced_list_to_string`, `build_compound_literal`, `finish_struct`, and code generation in the aarch64 files) show it touches none of the name tables used here: `c_common_reswords`, `builtins.def`, `c_common_gnu_attributes`, `init_pragma` and `names_builtin_p`. Every answer below comes from the installed Ubuntu binary in any case.

## 1. Root set and accepted set

**Roots.** `dpkg -L libc6-dev` lists 476 regular files under `/usr/include`. Skipping the 235 under a `bits/` directory leaves **241 roots**. libc6-dev ships no `linux/` or `asm/` headers, and its only non-`.h` file (`bits/stab.def`) is under `bits/`. Each TU is `#include <root>` (`data/roots.tsv`).

| Configuration | Roots | Accepted | Rejected |
|---|---|---|---|
| gnu89 | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu89+gs | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu99 | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu99+gs | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu17 | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu17+gs | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu23 | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |
| gnu23+gs | 241 | 238 | `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`, `<gnu/lib-names-lp64.h>`, `<regexp.h>` |

The three rejected roots fail the same way in every configuration (`data/accept.tsv`):

- `<finclude/aarch64-linux-gnu/math-vector-fortran.h>`: finclude/aarch64-linux-gnu/math-vector-fortran.h:1: expected identifier or ‘(’ before ‘!’ token
- `<gnu/lib-names-lp64.h>`: aarch64/gnu/lib-names-lp64.h:3: #error "Never use <gnu/lib-names-lp64.h> directly; include <gnu/lib-names.h> instead."
- `<regexp.h>`: regexp.h:29: #error "The GNU C Library no longer implements <regexp.h>."

The only warning in an accepted pair is `sys/elf.h:22`'s `#warning`.

**Headers GCC opened** (linemarkers with flag 1, union over accepted pairs; `data/opened-headers.tsv`):

| Package | Opened (any configuration) | gnu89 | gnu89+gs | gnu99 | gnu99+gs | gnu17 | gnu17+gs | gnu23 | gnu23+gs |
|---|---|---|---|---|---|---|---|---|---|
| glibc | 436 | 423 | 435 | 423 | 435 | 423 | 435 | 425 | 435 |
| kernel | 64 | 59 | 64 | 59 | 64 | 59 | 64 | 59 | 64 |
| gcc | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 | 7 |

## 2. Checks on the method

- **Instrumentation is transparent.** The probe tree rewrote 4,483 conditionals and 247 query operands in the 507 opened headers, keeping every line number. Re-running all 1,904 pairs against it gave emitted code identical to the plain run in 1,904 of 1,904 (`data/probe-summary.txt`). Six conditionals in `pthread.h` were left as they are because a comment spans lines inside the directive; none holds a query.
- **Builtins.** Every `__builtin_*` the headers emit is known to gcc-15:
  - `__has_builtin` answers 1 for all of them except `__builtin_complex`, `__builtin_tgmath` and `__builtin_va_list` (and `__builtin_c23_va_start` before gnu23, where it is not yet a keyword: `D_C23`);
  - the first two are `c_common_reswords` entries that GCC's C `names_builtin_p` omits (`gcc/c/c-decl.cc:11795-11823`), and `__builtin_va_list` is a predeclared type.
- **Attributes.** All 39 attribute spellings inside `__attribute__ ((...))` answer non-zero to `__has_attribute` in every configuration. `__deprecated__` and `__noreturn__` answer `202311`, even under gnu89.
- **Keywords.** Every reserved word of `c_common_reswords` (`gcc/c-family/c-common.cc:393`) that appears in emitted text or `#define` bodies is in the inventory, except two groups:
  - the C89 keywords;
  - `char8_t`, `char16_t`, `char32_t`, `wchar_t`, `class`, `end`, `protocol` and `selector`, which are C++ or Objective-C words (flags `D_CXXONLY`, `D_CXX_OBJC`, `D_OBJC`) and ordinary identifiers in C.
- **Pragmas and directives.** `vmscan.py` found 12 `#pragma` lines and one `_Pragma` in the opened headers.
  - The entered ones are `regex.h:535/536/696` and GCC's `stdint.h` and `syslimits.h` push/ignored/pop.
  - `uchar.h:43-49` is never entered.
  - The `_Pragma` is in `__glibc_macro_warning1` (sys/cdefs.h:807), a macro no header expands.
  - No opened header has `#pragma GCC system_header`, `once`, `pack`, `push_macro` or `GCC visibility`.
- **asm.** Every `__asm__` in emitted text is a symbol label. No basic or extended asm statement is reached in any configuration.
- **GCC's own extension diagnostics** (section 3.5) all map to inventory rows. Three constructs appear only there, and are added as rows from that data: parameter-array qualifiers, a VLA parameter, and enumerators beyond `int`.

## 3. Inventory

### 3.1 Counts

Columns *glibc* and *kernel UAPI* count names with at least one occurrence in that package (a name can be in both). *Only GCC's own headers* counts names neither package contains.

| Group | Names | Reached by header code | Macro only | M | L | A | glibc | kernel UAPI | only GCC's own headers |
|---|---|---|---|---|---|---|---|---|---|
| Builtins | 81 | 14 | 67 | 76 | 3 | 2 | 68 | 1 | 13 |
| Attributes | 35 | 28 | 7 | 10 | 0 | 25 | 35 | 2 | 0 |
| Keywords and types | 29 | 24 | 5 | 25 | 0 | 4 | 23 | 6 | 3 |
| Pragmas | 2 | 1 | 1 | 0 | 0 | 2 | 2 | 0 | 0 |
| asm labels | 1 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| Syntax and directives | 17 | 14 | 3 | 13 | 0 | 4 | 14 | 7 | 1 |
| **Total** | **165** | **82** | **83** | **125** | **3** | **37** | **143** | **16** | **17** |

Restricted to names in glibc or kernel text:

| Status (glibc or kernel origin) | Names | M | L | A |
|---|---|---|---|---|
| reached | 77 | 47 | 1 | 29 |
| macro only | 71 | 61 | 2 | 8 |

### 3.2 Per configuration

| Configuration | Names reached by header code | of which M / L / A | Macro only |
|---|---|---|---|
| gnu89 | 69 | 40 / 1 / 28 | 66 |
| gnu89+gs | 76 | 47 / 1 / 28 | 77 |
| gnu99 | 71 | 41 / 1 / 29 | 66 |
| gnu99+gs | 78 | 48 / 1 / 29 | 77 |
| gnu17 | 72 | 42 / 1 / 29 | 68 |
| gnu17+gs | 79 | 49 / 1 / 29 | 77 |
| gnu23 | 76 | 46 / 1 / 29 | 75 |
| gnu23+gs | 82 | 52 / 1 / 29 | 80 |

### 3.3 What depends on the configuration

All other names have the same status in all eight configurations. The 69 names reached by header code in every configuration are: `asm label (symbol rename)`, `aarch64_vector_pcs`, `access`, `aligned`, `alloc_align`, `alloc_size`, `always_inline`, `cold`, `const`, `deprecated`, `format`, `format_arg`, `indirect_return`, `leaf`, `malloc`, `may_alias`, `mode`, `nonnull`, `nonstring`, `noreturn`, `nothrow`, `packed`, `pure`, `returns_twice`, `unused`, `warn_unused_result`, `weak`, `__builtin_bswap16`, `__builtin_bswap32`, `__builtin_bswap64`, `__builtin_clz`, `__builtin_clzll`, `__builtin_constant_p`, `__builtin_ctz`, `__builtin_ctzll`, `__builtin_expect`, `__builtin_free`, `__builtin_popcount`, `__builtin_popcountll`, `__builtin_va_arg_pack`, `__builtin_va_list`, `_Bool`, `_Complex`, `__Float32x4_t`, `__Float64x2_t`, `__SVBool_t`, `__SVFloat32_t`, `__SVFloat64_t`, `__attribute__`, `__extension__`, `__inline`, `__inline__`, `__int128`, `__restrict`, `__signed__`, `__uint128_t`, `#pragma GCC diagnostic`, `#include_next`, `#warning`, `anonymous struct or union member`, `enum trailing comma`, `enumerator value outside int`, `flexible array member`, `long double`, `long long`, `long long constant`, `named variadic macro parameter`, `qualifier in parameter array declarator ([__restrict])`, `zero-length array member`.

| Name | Class | Reached by header code in | Macro only in | Origin |
|---|---|---|---|---|
| `gnu_inline` | M | gnu99, gnu17, gnu23 | - | glibc |
| `transparent_union` | M | +gs only (all dialects) | - | glibc |
| `__builtin_c23_va_start` | M | - | gnu23 | gcc |
| `__builtin_complex` | M | - | gnu89+gs, gnu99+gs, gnu17, gnu23 | glibc |
| `__builtin_huge_valf128` | M | - | +gs only (all dialects) | glibc |
| `__builtin_huge_valf32` | M | - | +gs only (all dialects) | glibc |
| `__builtin_huge_valf32x` | M | - | +gs only (all dialects) | glibc |
| `__builtin_huge_valf64` | M | - | +gs only (all dialects) | glibc |
| `__builtin_huge_valf64x` | M | - | +gs only (all dialects) | glibc |
| `__builtin_infd32` | M | - | gnu23 | gcc |
| `__builtin_nand32` | M | - | gnu23 | gcc |
| `__builtin_nans` | M | - | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | gcc+glibc |
| `__builtin_nansd128` | M | - | gnu23 | gcc |
| `__builtin_nansd32` | M | - | gnu23 | gcc |
| `__builtin_nansd64` | M | - | gnu23 | gcc |
| `__builtin_nansf` | M | - | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | gcc+glibc |
| `__builtin_nansf128` | M | - | +gs only (all dialects) | glibc |
| `__builtin_nansf32` | M | - | +gs only (all dialects) | glibc |
| `__builtin_nansf32x` | M | - | +gs only (all dialects) | glibc |
| `__builtin_nansf64` | M | - | +gs only (all dialects) | glibc |
| `__builtin_nansf64x` | M | - | +gs only (all dialects) | glibc |
| `__builtin_nansl` | M | - | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | gcc+glibc |
| `__builtin_unreachable` | M | - | gnu23 | gcc |
| `__builtin_va_start` | M | - | gnu89, gnu99, gnu17 | gcc |
| `_Float128` | M | +gs only (all dialects) | without _GNU_SOURCE only | glibc |
| `_Float32` | M | +gs only (all dialects) | without _GNU_SOURCE only | glibc |
| `_Float32x` | M | +gs only (all dialects) | without _GNU_SOURCE only | glibc |
| `_Float64` | M | +gs only (all dialects) | without _GNU_SOURCE only | glibc |
| `_Float64x` | M | +gs only (all dialects) | without _GNU_SOURCE only | glibc |
| `_Static_assert` | M | - | gnu89+gs, gnu99+gs, gnu17 | glibc |
| `_Thread_local` | M | - | gnu89, gnu99, gnu17 | glibc |
| `__alignof__` | M | gnu17, gnu23 | - | gcc |
| `__typeof` | M | - | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | glibc |
| `__typeof__` | M | gnu23 | gnu89, gnu99, gnu17 | gcc |
| `bool` | M | gnu23 | - | glibc |
| `nullptr` | M | gnu23 | - | gcc |
| `variable-length array parameter` | A | gnu99, gnu17, gnu23 | - | glibc |
| `variadic macro (__VA_ARGS__)` | M | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | - | gcc+glibc |

Read with the header text:
- **`_GNU_SOURCE`** defines `_ISOC23_SOURCE` (features.h:217-226), so `__GLIBC_USE (ISOC23)` (features.h:268-272) and `__GLIBC_USE (C23_STRTOL)` (features.h:509-510) hold in every dialect. That is where the `__isoc23_*` renames come from (section 5). It also brings in:
  - `transparent_union` for `__SOCKADDR_ARG` (sys/socket.h:57-84, `!defined __USE_GNU` selects plain pointers);
  - the `strtof128`/`_Float128` declarations;
  - the `pthread_*_np` and `sigpause` renames;
  - the six `__has_include ("linux/...")` probes (section 4).
- **gnu89.** `__GNUC_GNU_INLINE__` makes glibc define `__extern_always_inline` as `extern __always_inline` without `__attribute__ ((__gnu_inline__))` (sys/cdefs.h:618-628). So `gnu_inline` is reached only in gnu99, gnu17 and gnu23, and in gnu89 `<error.h>`'s `error` wrapper (bits/error.h:36-43) relies on GNU89 `extern inline` semantics. Also:
  - without `_GNU_SOURCE`, the C99 `__isoc99_*scanf` renames apply in gnu89 as in gnu99 and gnu17 (features.h:490-501);
  - with `_GNU_SOURCE`, gnu89 keeps glibc's old GNU `scanf` (`__GLIBC_USE_DEPRECATED_SCANF`), so `gnu89+gs` has no scanf rename at all.
- **gnu23** adds C23 surface:
  - `bool` in `<stdbit.h>` declarations;
  - `nullptr`/`__typeof__` in GCC's `<stddef.h>` (`nullptr_t`) and `__builtin_c23_va_start` in GCC's `va_start`;
  - `__builtin_unreachable` in GCC's `unreachable()`;
  - the decimal-float constants in GCC's `<float.h>`;
  - the `__isoc23_*` renames without `_GNU_SOURCE`.

  Before C23, glibc's `static_assert` and `thread_local` are macros for `_Static_assert` and `_Thread_local` (assert.h:210, threads.h:31-34).

### 3.4 Notable reached constructs

Full rows are in the appendix. Facts that decide a class or are new relative to #9:

- **Builtins reached by header code.**
  - `__builtin_bswap16/32/64` (bits/byteswap.h, 77 roots).
  - `__builtin_clz`, `__builtin_clzll`, `__builtin_ctz`, `__builtin_ctzll`, `__builtin_popcount` and `__builtin_popcountll` in `<stdbit.h>`'s inline helpers.
  - `__builtin_constant_p`: glibc's `error` wrapper and the kernel's `__swab*` macros (linux/swab.h).
  - `__builtin_va_arg_pack`, via `__va_arg_pack` in bits/error.h:40-42, at -O0.
  - `__builtin_expect`, via `__glibc_likely` in sys/ifunc.h.
  - `__builtin_free`, via `__attr_dealloc_free`.
  - `__builtin_va_list` (GCC's `<stdarg.h>`).

  Everything else in `<math.h>`, `<tgmath.h>`, `<stdbit.h>`, `<complex.h>`, `<fpu_control.h>` and `<alloca.h>` is macro only: `isnan`, `HUGE_VAL`, `stdc_leading_zeros`, `CMPLX`, `_FPU_GETCW`, `alloca` and so on.
- **`__builtin_constant_p` in C.** There is no C++ constant evaluation, but the kernel's `__swab16(x)` and friends are `__builtin_constant_p(x) ? ___constant_swab16(x) : __fswab16(x)`. Used in a static initializer, that is a constant expression only if `__builtin_constant_p` returns 1 for a constant argument. So it stays M, for a C reason.
- **Attributes new in C.**
  - `nothrow`, through glibc's C `__THROW` (sys/cdefs.h:77-79), in 162 roots; in C++ `__THROW` is `noexcept`.
  - `transparent_union` (`_GNU_SOURCE`, 24 roots).
  - `packed` (arpa/tftp.h and kernel UAPI structs).
  - `indirect_return` (`swapcontext`, ucontext.h:43).
- **The kernel UAPI headers contribute** `__int128` (linux/types.h:12-13, `__s128`/`__u128`, under `__SIZEOF_INT128__`), `__signed__`, `__inline__`, `__uint128_t` (asm/sigcontext.h), the named variadic macro `__struct_group(TAG, NAME, ATTRS, MEMBERS...)` (linux/stddef.h:32, 52 roots), flexible arrays, anonymous unions and enum trailing commas. They also use glibc's `__always_inline` (linux/byteorder/little_endian.h:45-53).
- **GCC's own headers** account for the rest:
  - `#include_next`, reached only in GCC's `limits.h:210`, `syslimits.h:9` and `stdint.h:11`; glibc's own `#include_next` (limits.h:124) is never entered in C mode;
  - `#pragma GCC diagnostic` around those;
  - `__alignof__` and `long double` in `max_align_t`;
  - `__builtin_offsetof`, the `va_*` builtins, `__builtin_unreachable`, and the decimal-float builtins.

### 3.5 GCC's own extension diagnostics

`-Wpedantic -Wc90-c99-compat -Wc99-c11-compat -Wc11-c23-compat -Wsystem-headers` with `-D__extension__=`, over every accepted pair (`data/pedantic.tsv` also has the run with `__extension__` kept). It lists every construct GCC itself treats as an extension or as later-revision syntax in that dialect, except those GCC exempts in system headers outright: it diagnosed no `__int128` or `_FloatN` here.

| GCC diagnostic | Option | Configurations | Roots (max) | Sites | Example sites |
|---|---|---|---|---|---|
| ISO C90 does not support ‘long long’ | -Wlong-long | all 8 | 104 | 76 | aarch64/bits/atomic_wide_counter.h:27, aarch64/bits/mathcalls.h:194, aarch64/bits/mathcalls.h:197 ... |
| ISO C90 doesn’t support unnamed structs/unions | -Wc99-c11-compat | gnu89 | 12 | 29 | aarch64/bits/ptrace-shared.h:120, aarch64/bits/termios-struct.h:36, aarch64/bits/termios-struct.h:41 ... |
| ISO C99 doesn’t support unnamed structs/unions | -Wc99-c11-compat | gnu99, gnu17, gnu23 | 12 | 29 | aarch64/bits/ptrace-shared.h:120, aarch64/bits/termios-struct.h:36, aarch64/bits/termios-struct.h:41 ... |
| comma at end of enumerator list | -Wc90-c99-compat | all 8 | 14 | 19 | aarch64/bits/fenv.h:40, aarch64/bits/types/idtype_t.h:10, aarch64/sys/ifunc.h:73 ... |
| ISO C90 does not support ‘static’ or type qualifiers in parameter array declarators | -Wc90-c99-compat | all 8 | 5 | 10 | aarch64/bits/spawn_ext.h:49, aarch64/bits/spawn_ext.h:50, aarch64/bits/spawn_ext.h:61 ... |
| ISO C forbids zero-size array ‘X’ | -Wpedantic | all 8 | 13 | 8 | aarch64/bits/fcntl-linux.h:369, aio.h:52, arpa/tftp.h:58 ... |
| use of C99 long long integer constant | -Wlong-long | all 8 | 3 | 4 | aarch64/sys/ifunc.h:86, linux/swab.h:139, linux/swab.h:202 ... |
| struct has no named members | -Wpedantic | gnu89, gnu99 | 4 | 4 | linux/rseq.h:78, linux/socket.h:16, netinet/tcp.h:98 ... |
| union has no named members | -Wpedantic | gnu89, gnu99 | 2 | 2 | netinet/tcp.h:100, netinet/udp.h:57 |
| ISO C restricts enumerator values to range of ‘int’ before C23 | -Wc11-c23-compat | all 8 | 2 | 2 | aarch64/sys/epoll.h:66, aarch64/sys/mount.h:124 |
| anonymous variadic macros were introduced in C99 | - | gnu99+gs, gnu17+gs, gnu23 | 2 | 2 | assert.h:156, gcc/stdarg.h:48 |
| ISO C does not permit named variadic macros | -Wvariadic-macros | all 8 | 52 | 1 | linux/stddef.h:32 |
| ‘#warning’ before C23 is a GCC extension | -Wpedantic | gnu89, gnu99, gnu17 | 1 | 1 | aarch64/sys/elf.h:22 |
| #warning "This header is obsolete; use <sys/procfs.h> instead." | -Wcpp | all 8 | 1 | 1 | aarch64/sys/elf.h:22 |
| anonymous variadic macros were introduced in C99 | -Wvariadic-macros | gnu89+gs | 1 | 1 | assert.h:156 |
| ISO C90 forbids variable length array ‘X’ | -Wc90-c99-compat | gnu99, gnu17, gnu23 | 2 | 1 | regex.h:686 |
| ‘X’ redefined | - | gnu23 | 6 | 1 | gcc/limits.h:200 |
| ISO C does not support ‘nullptr’ before C23 | -Wc11-c23-compat | gnu23 | 5 | 1 | gcc/stddef.h:465 |
| ‘#warning’ before C23 is a GCC extension | -Wc11-c23-compat | gnu23 | 1 | 1 | aarch64/sys/elf.h:22 |

## 4. `__has_*` steering

`probe.py` rewrote each query operand `Q` in the opened headers as `((__forge_flip_K) ? !(Q) : ((Q) ? (__forge_qt_K + (Q)) : (__forge_qf_K + (Q))))`. It rewrote each conditional the same way, and ran every pair with `-Wundef`.
- **Evaluation.** libcpp warns about an undefined identifier only when it evaluates it, not when `&&`/`||`/`?:` skips it (`skip_eval`, `libcpp/expr.cc`). So each warning records that GCC evaluated that operand, and `qt`/`qf` records its answer.
- **Flips.** `-D__forge_flip_K=1` makes GCC see the opposite answer. The flip runs re-ran up to 3 roots per (operand, configuration) and diffed the `-E -dD` output: 2,349 runs, 1,695 with a change.
- **Scope.** Operands are calls of `__has_builtin`, `__has_attribute`, `__has_c_attribute`, `__has_include`, `__has_include_next`, `__has_feature`, `__has_extension`, and of glibc's `__glibc_has_*`, `__GNUC_PREREQ` and `__glibc_clang_prereq`, plus `defined OP`.

The opened headers hold 247 such operands (`data/queries.tsv`):
- **142 are evaluated** in at least one configuration.
- **67 are short-circuited** every time: their directive is evaluated but `||`/`&&` skips them. These are mostly glibc's `__GNUC_PREREQ (x, y) || __glibc_has_attribute (__x__)`, where the version test already holds.
- **38 sit in blocks GCC never enters.**

No header uses `__has_c_attribute`, `__has_include_next` or `__has_feature` in an evaluated position.

**The queries that steer** (every evaluated operand other than the version macros):

| Site | Query | GCC 15.2 answer | Evaluated in | Roots (max) | If answered the other way (flip run) |
|---|---|---|---|---|---|
| aarch64/bits/fcntl-linux.h:466 | `defined __has_include` | 1 | +gs only (all dialects) | 6 | 111 lines; loses `aligned`, `empty struct or union`, `flexible array member`, `long long` |
| aarch64/bits/fcntl-linux.h:467 | `__has_include ("linux/openat2.h")` | 1 | +gs only (all dialects) | 6 | 111 lines; loses `aligned`, `empty struct or union`, `flexible array member`, `long long` |
| aarch64/bits/indirect-return.h:29 | `__glibc_has_attribute (__indirect_return__)` | 1 | all 8 | 1 | 4 lines; loses `indirect_return`, `nothrow`; gains `nothrow` |
| aarch64/bits/sched.h:59 | `defined __has_include` | 1 | +gs only (all dialects) | 4 | 32 lines; no listed construct lost |
| aarch64/bits/sched.h:60 | `__has_include ("linux/sched/types.h")` | 1 | +gs only (all dialects) | 4 | 32 lines; no listed construct lost |
| aarch64/bits/statx.h:29 | `defined __has_include` | 1 | +gs only (all dialects) | 2 | 231 lines; loses `aligned`, `empty struct or union`, `flexible array member`, `long long` |
| aarch64/bits/statx.h:30 | `__has_include ("linux/stat.h")` | 1 | +gs only (all dialects) | 2 | 231 lines; loses `aligned`, `empty struct or union`, `flexible array member`, `long long` |
| aarch64/bits/unistd_ext.h:36 | `defined __has_include` | 1 | +gs only (all dialects) | 9 | 5 lines; no listed construct lost |
| aarch64/bits/unistd_ext.h:37 | `__has_include ("linux/close_range.h")` | 1 | +gs only (all dialects) | 9 | 5 lines; no listed construct lost |
| aarch64/sys/cdefs.h:42 | `defined __has_attribute` | 1 | all 8 | 209 | 2 lines; no listed construct lost |
| aarch64/sys/cdefs.h:49 | `defined __has_builtin` | 1 | all 8 | 209 | 2 lines; no listed construct lost |
| aarch64/sys/cdefs.h:54 | `defined __has_extension` | 1 | all 8 | 209 | 2 lines; no listed construct lost |
| aarch64/sys/mount.h:30 | `defined __has_include` | 1 | all 8 | 1 | 260 lines; loses `aligned`, `anonymous struct or union member`, `empty struct or union`, `enum trailing comma`, `flexible array member`, `long long` |
| aarch64/sys/mount.h:31 | `__has_include ("linux/mount.h")` | 1 | all 8 | 1 | 260 lines; loses `aligned`, `anonymous struct or union member`, `empty struct or union`, `enum trailing comma`, `flexible array member`, `long long` |
| aarch64/sys/rseq.h:28 | `defined __has_include` | 1 | all 8 | 1 | 7 lines; no listed construct lost |
| aarch64/sys/rseq.h:29 | `__has_include ("linux/rseq.h")` | 1 | all 8 | 1 | 352 lines; loses `aligned`, `always_inline`, `__builtin_constant_p`, `anonymous struct or union member`, `empty struct or union`, `enum trailing comma`, `flexible array member`, `long long`, `long long constant`; gains `aligned`, `enum trailing comma` |
| stdbit.h:67 | `__glibc_has_builtin (__builtin_stdc_leading_zeros)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_leading_zeros`; gains `long long constant` |
| stdbit.h:123 | `__glibc_has_builtin (__builtin_stdc_leading_ones)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_leading_ones`; gains `long long`, `long long constant` |
| stdbit.h:179 | `__glibc_has_builtin (__builtin_stdc_trailing_zeros)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_trailing_zeros` |
| stdbit.h:237 | `__glibc_has_builtin (__builtin_stdc_trailing_ones)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_trailing_ones` |
| stdbit.h:291 | `__glibc_has_builtin (__builtin_stdc_first_leading_zero)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_first_leading_zero` |
| stdbit.h:349 | `__glibc_has_builtin (__builtin_stdc_first_leading_one)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_first_leading_one` |
| stdbit.h:407 | `__glibc_has_builtin (__builtin_stdc_first_trailing_zero)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_first_trailing_zero` |
| stdbit.h:465 | `__glibc_has_builtin (__builtin_stdc_first_trailing_one)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_first_trailing_one` |
| stdbit.h:523 | `__glibc_has_builtin (__builtin_stdc_count_zeros)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_count_zeros`; gains `long long constant` |
| stdbit.h:579 | `__glibc_has_builtin (__builtin_stdc_count_ones)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_count_ones` |
| stdbit.h:633 | `__glibc_has_builtin (__builtin_stdc_has_single_bit)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_has_single_bit` |
| stdbit.h:688 | `__glibc_has_builtin (__builtin_stdc_bit_width)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_bit_width` |
| stdbit.h:742 | `__glibc_has_builtin (__builtin_stdc_bit_floor)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_bit_floor` |
| stdbit.h:798 | `__glibc_has_builtin (__builtin_stdc_bit_ceil)` | 1 | all 8 | 1 | 2 lines; loses `__builtin_stdc_bit_ceil` |
| wchar.h:729 | `defined __has_builtin` | 1 | all 8 | 1 | no change |
| wchar.h:730 | `__has_builtin (__builtin_fclose)` | 0 | all 8 | 1 | 4 lines; loses `malloc`; gains `malloc`, `__builtin_fclose` |

Reading the table:
- **Every answer is 1** except `__has_builtin (__builtin_fclose)` (wchar.h:730), where GCC says 0. A Forge that answered 1 would add `__attr_dealloc (__builtin_fclose, 1)`, a `malloc` attribute naming a builtin, to `open_wmemstream` (wchar.h:728-744) whenever `<stdio.h>` has not already defined the macro.
- **The six `__has_include ("linux/...")` probes** choose between the kernel's UAPI definitions and glibc's own copies:
  - `<sys/mount.h>`: 260 changed lines;
  - `<sys/rseq.h>`: 352;
  - `<bits/statx.h>`: 231;
  - `<bits/fcntl-linux.h>` (`openat2`): 111;
  - `<bits/sched.h>`: 32;
  - `<bits/unistd_ext.h>`: 5.

  Answering 0 swaps in glibc's fallbacks: the kernel's flexible arrays, anonymous unions and aligned `long long` members disappear. Only `<sys/mount.h>` and `<sys/rseq.h>` ask without `_GNU_SOURCE`.
- **The 14 `__glibc_has_builtin (__builtin_stdc_*)` operands** choose `<stdbit.h>`'s builtin path. Answering 0 gives the inline fallbacks, which use `__builtin_clzll`, `__builtin_ctzll` and `__builtin_popcountll`.
- **`defined __has_attribute`, `defined __has_builtin` and `defined __has_extension`** (sys/cdefs.h:42, 49, 54) define glibc's `__glibc_has_*` wrappers. If they were 0, the wrappers become `0` and `__glibc_has_attribute (__indirect_return__)` (bits/indirect-return.h:29) would drop `indirect_return`.

**Version tests.** Every `__GNUC_PREREQ` threshold in the opened headers is ≤ (13, 0), so GCC 15.2 passes them all; every `__glibc_clang_prereq` is skipped. Flipping one operand shows what a lower reported version loses at that site:

| Test | Sites in opened headers | Evaluated | Flip changes output | Constructs lost when flipped |
|---|---|---|---|---|
| `__GNUC_PREREQ (2,4)` | 1 | 1 | 1 | - |
| `__GNUC_PREREQ (2,5)` | 1 | 1 | 0 | - |
| `__GNUC_PREREQ (2,6)` | 1 | 0 | 0 | - |
| `__GNUC_PREREQ (2,7)` | 6 | 6 | 3 | `__builtin_tgmath`, `mode`, `transparent_union` |
| `__GNUC_PREREQ (2,8)` | 4 | 2 | 1 | - |
| `__GNUC_PREREQ (2,91)` | 2 | 2 | 2 | `__builtin_memcmp`, `__builtin_memset` |
| `__GNUC_PREREQ (2,92)` | 1 | 1 | 1 | - |
| `__GNUC_PREREQ (2,95)` | 1 | 0 | 0 | - |
| `__GNUC_PREREQ (2,96)` | 2 | 2 | 0 | - |
| `__GNUC_PREREQ (2,97)` | 3 | 3 | 2 | `leaf`, `long double`, `nothrow` |
| `__GNUC_PREREQ (3,0)` | 2 | 2 | 2 | `statement expression ({ ... })`, `zero-length array member` |
| `__GNUC_PREREQ (3,1)` | 4 | 3 | 2 | `__builtin_isgreater`, `__builtin_isgreaterequal`, `__builtin_isless`, `__builtin_islessequal`, `__builtin_islessgreater`, `__builtin_isunordered` |
| `__GNUC_PREREQ (3,2)` | 2 | 2 | 0 | - |
| `__GNUC_PREREQ (3,3)` | 6 | 6 | 5 | `__builtin_huge_val`, `__builtin_huge_valf`, `__builtin_huge_vall`, `__builtin_inff`, `__builtin_nanf`, `__builtin_nans`, `__builtin_nansf`, `__builtin_nansl` |
| `__GNUC_PREREQ (3,4)` | 17 | 17 | 0 | - |
| `__GNUC_PREREQ (4,0)` | 1 | 0 | 0 | - |
| `__GNUC_PREREQ (4,1)` | 2 | 1 | 1 | `returns_twice` |
| `__GNUC_PREREQ (4,3)` | 8 | 7 | 5 | `__builtin_bswap32`, `__builtin_bswap64`, `__builtin_va_arg_pack_len`, `__builtin_va_arg_pack`, `alloc_size`, `error`, `warning` |
| `__GNUC_PREREQ (4,4)` | 8 | 5 | 5 | `__builtin_fpclassify`, `__builtin_isfinite`, `__builtin_isinf_sign`, `__builtin_isnan`, `__builtin_isnormal` |
| `__GNUC_PREREQ (4,5)` | 1 | 1 | 0 | - |
| `__GNUC_PREREQ (4,6)` | 2 | 2 | 2 | `leaf` |
| `__GNUC_PREREQ (4,7)` | 2 | 2 | 2 | `__builtin_complex`, `long double` |
| `__GNUC_PREREQ (4,8)` | 2 | 2 | 2 | `_Pragma (text from a macro argument)`, `__builtin_bswap16` |
| `__GNUC_PREREQ (4,9)` | 3 | 3 | 0 | - |
| `__GNUC_PREREQ (6,0)` | 3 | 2 | 2 | `__builtin_aarch64_get_fpcr`, `__builtin_aarch64_get_fpsr`, `__builtin_aarch64_set_fpcr`, `__builtin_aarch64_set_fpsr`, `__builtin_signbit` |
| `__GNUC_PREREQ (7,0)` | 34 | 21 | 21 | - |
| `__GNUC_PREREQ (7,1)` | 1 | 1 | 1 | `may_alias` |
| `__GNUC_PREREQ (8,0)` | 2 | 2 | 2 | `__builtin_tgmath`, `nonstring` |
| `__GNUC_PREREQ (9,0)` | 2 | 2 | 2 | `aarch64_vector_pcs`, `copy` |
| `__GNUC_PREREQ (10,0)` | 4 | 4 | 2 | `access` |
| `__GNUC_PREREQ (11,0)` | 4 | 4 | 4 | `__builtin_free`, `access`, `asm label (symbol rename)`, `malloc`, `nothrow`, `returns_twice` |
| `__GNUC_PREREQ (12,0)` | 2 | 0 | 0 | - |
| `__GNUC_PREREQ (13,0)` | 31 | 3 | 3 | `__builtin_tgmath` |
| `__glibc_clang_prereq (2,8)` | 4 | 0 | 0 | - |
| `__glibc_clang_prereq (3,3)` | 1 | 0 | 0 | - |
| `__glibc_clang_prereq (3,5)` | 2 | 0 | 0 | - |
| `__glibc_clang_prereq (3,7)` | 1 | 0 | 0 | - |
| `__glibc_clang_prereq (8,0)` | 1 | 0 | 0 | - |
| `__glibc_clang_prereq (9,0)` | 2 | 0 | 0 | - |
| `__glibc_clang_prereq (11,0)` | 1 | 0 | 0 | - |
| `__glibc_clang_prereq (12,0)` | 1 | 0 | 0 | - |

Two facts follow:
- Where glibc writes `__GNUC_PREREQ (x, y) || __glibc_has_attribute (__a__)` (sys/cdefs.h:77-603), flipping the version test changes nothing ("Flip changes output" 0), because GCC's `__has_attribute` answer then selects the same attribute. A Forge that reports a lower `__GNUC__` but answers `__has_attribute` like GCC gets the same declarations at those sites.
- The tests without such a fallback decide `__builtin_bswap*`, the `<math.h>` classification builtins, `HUGE_VAL`/`INFINITY`/`NAN`, the `<tgmath.h>` builtin path and the `access`/`malloc`/`copy`/`nonstring`/`may_alias` attributes.

## 5. asm labels

glibc renames functions with `__REDIRECT (name, proto, alias)`, which in C expands to `name proto __asm__ ("" "alias")` (`__REDIRECT_NTH` appends the `__THROW` attribute after the label). Distinct (declared name, label) pairs in code that header text emitted:

| Configuration | Distinct renames | `__isoc23_*` | `__isoc99_*` | Other | Added by `-D_FILE_OFFSET_BITS=64 -D_TIME_BITS=64` |
|---|---|---|---|---|---|
| gnu89 | 19 | 0 | 12 | 7 | 56 |
| gnu89+gs | 35 | 24 | 0 | 11 | 65 |
| gnu99 | 19 | 0 | 12 | 7 | 56 |
| gnu99+gs | 47 | 36 | 0 | 11 | 65 |
| gnu17 | 19 | 0 | 12 | 7 | 56 |
| gnu17+gs | 47 | 36 | 0 | 11 | 65 |
| gnu23 | 33 | 26 | 0 | 7 | 56 |
| gnu23+gs | 47 | 36 | 0 | 11 | 65 |

The ISO C families, with the configurations that select them:

| Declared name | asm label | Configurations | Site |
|---|---|---|---|
| `fscanf` | `__isoc23_fscanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:449 |
| `fwscanf` | `__isoc23_fwscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:820 |
| `scanf` | `__isoc23_scanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:452 |
| `sscanf` | `__isoc23_sscanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:454 |
| `strtoimax` | `__isoc23_strtoimax` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | inttypes.h:389 |
| `strtol` | `__isoc23_strtol` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:219 |
| `strtol_l` | `__isoc23_strtol_l` | +gs only (all dialects) | stdlib.h:369 |
| `strtoll` | `__isoc23_strtoll` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:242 |
| `strtoq` | `__isoc23_strtoll` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:230 |
| `strtoll_l` | `__isoc23_strtoll_l` | +gs only (all dialects) | stdlib.h:381 |
| `strtoul` | `__isoc23_strtoul` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:223 |
| `strtoul_l` | `__isoc23_strtoul_l` | +gs only (all dialects) | stdlib.h:374 |
| `strtoull` | `__isoc23_strtoull` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:247 |
| `strtouq` | `__isoc23_strtoull` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | stdlib.h:235 |
| `strtoull_l` | `__isoc23_strtoull_l` | +gs only (all dialects) | stdlib.h:388 |
| `strtoumax` | `__isoc23_strtoumax` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | inttypes.h:392 |
| `swscanf` | `__isoc23_swscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:827 |
| `vfscanf` | `__isoc23_vfscanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:518 |
| `vfwscanf` | `__isoc23_vfwscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:900 |
| `vscanf` | `__isoc23_vscanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:523 |
| `vsscanf` | `__isoc23_vsscanf` | gnu99+gs, gnu17+gs, gnu23 | stdio.h:526 |
| `vswscanf` | `__isoc23_vswscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:907 |
| `vwscanf` | `__isoc23_vwscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:904 |
| `wcstoimax` | `__isoc23_wcstoimax` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | inttypes.h:395 |
| `wcstol` | `__isoc23_wcstol` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | wchar.h:525 |
| `wcstol_l` | `__isoc23_wcstol_l` | +gs only (all dialects) | wchar.h:609 |
| `wcstoll` | `__isoc23_wcstoll` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | wchar.h:533 |
| `wcstoq` | `__isoc23_wcstoll` | +gs only (all dialects) | wchar.h:544 |
| `wcstoll_l` | `__isoc23_wcstoll_l` | +gs only (all dialects) | wchar.h:619 |
| `wcstoul` | `__isoc23_wcstoul` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | wchar.h:528 |
| `wcstoul_l` | `__isoc23_wcstoul_l` | +gs only (all dialects) | wchar.h:613 |
| `wcstoull` | `__isoc23_wcstoull` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | wchar.h:538 |
| `wcstouq` | `__isoc23_wcstoull` | +gs only (all dialects) | wchar.h:548 |
| `wcstoull_l` | `__isoc23_wcstoull_l` | +gs only (all dialects) | wchar.h:625 |
| `wcstoumax` | `__isoc23_wcstoumax` | gnu89+gs, gnu99+gs, gnu17+gs, gnu23 | inttypes.h:399 |
| `wscanf` | `__isoc23_wscanf` | gnu99+gs, gnu17+gs, gnu23 | wchar.h:824 |
| `fscanf` | `__isoc99_fscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:470 |
| `fwscanf` | `__isoc99_fwscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:844 |
| `scanf` | `__isoc99_scanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:473 |
| `sscanf` | `__isoc99_sscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:475 |
| `swscanf` | `__isoc99_swscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:851 |
| `vfscanf` | `__isoc99_vfscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:547 |
| `vfwscanf` | `__isoc99_vfwscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:926 |
| `vscanf` | `__isoc99_vscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:552 |
| `vsscanf` | `__isoc99_vsscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | stdio.h:555 |
| `vswscanf` | `__isoc99_vswscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:933 |
| `vwscanf` | `__isoc99_vwscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:930 |
| `wscanf` | `__isoc99_wscanf` | gnu89 (no gs), gnu99 (no gs), gnu17 (no gs) | wchar.h:848 |

The other renames:

| Declared name | asm label | Configurations | Site |
|---|---|---|---|
| `__error_alias` | `error` | all 8 | aarch64/bits/error.h:24 |
| `__error_at_line_alias` | `error_at_line` | all 8 | aarch64/bits/error.h:46 |
| `__error_at_line_noreturn` | `error_at_line` | all 8 | aarch64/bits/error.h:52 |
| `__error_noreturn` | `error` | all 8 | aarch64/bits/error.h:28 |
| `__sigsetjmp_cancel` | `__sigsetjmp` | all 8 | pthread.h:766 |
| `ntp_gettime` | `ntp_gettimex` | all 8 | aarch64/sys/timex.h:62 |
| `pthread_mutex_consistent_np` | `pthread_mutex_consistent` | +gs only (all dialects) | pthread.h:859 |
| `pthread_mutexattr_getrobust_np` | `pthread_mutexattr_getrobust` | +gs only (all dialects) | pthread.h:935 |
| `pthread_mutexattr_setrobust_np` | `pthread_mutexattr_setrobust` | +gs only (all dialects) | pthread.h:951 |
| `pthread_yield` | `sched_yield` | +gs only (all dialects) | pthread.h:479 |
| `sigpause` | `__xpg_sigpause` | +gs only (all dialects) | signal.h:151 |
| `strerror_r` | `__xpg_strerror_r` | without _GNU_SOURCE only | string.h:464 |

- **No `_FILE_OFFSET_BITS`/`_TIME_BITS` rename** occurs in the eight configurations; neither macro is defined by default.
- **Side run.** A run with `-D_FILE_OFFSET_BITS=64 -D_TIME_BITS=64` added the 65 LFS renames listed below, even though `off_t` is already 64-bit on LP64; libc exports both names. `aio_cancel`→`aio_cancel64`, `aio_error`→`aio_error64`, `aio_fsync`→`aio_fsync64`, `aio_read`→`aio_read64`, `aio_return`→`aio_return64`, `aio_suspend`→`aio_suspend64`, `aio_write`→`aio_write64`, `alphasort`→`alphasort64`, `creat`→`creat64`, `fallocate`→`fallocate64`, `fcntl`→`fcntl64`, `fgetpos`→`fgetpos64`, `fopen`→`fopen64`, `freopen`→`freopen64`, `fseeko`→`fseeko64`, `fsetpos`→`fsetpos64`, `fstat`→`fstat64`, `fstatat`→`fstatat64`, `fstatfs`→`fstatfs64`, `fstatvfs`→`fstatvfs64`, `ftello`→`ftello64`, `ftruncate`→`ftruncate64`, `fts_children`→`fts64_children`, `fts_close`→`fts64_close`, `fts_open`→`fts64_open`, `fts_read`→`fts64_read`, `fts_set`→`fts64_set`, `ftw`→`ftw64`, `getdirentries`→`getdirentries64`, `getrlimit`→`getrlimit64`, `glob`→`glob64`, `globfree`→`globfree64`, `lio_listio`→`lio_listio64`, `lockf`→`lockf64`, `lseek`→`lseek64`, `lstat`→`lstat64`, `mkostemp`→`mkostemp64`, `mkostemps`→`mkostemps64`, `mkstemp`→`mkstemp64`, `mkstemps`→`mkstemps64`, `mmap`→`mmap64`, `nftw`→`nftw64`, `open`→`open64`, `openat`→`openat64`, `posix_fadvise`→`posix_fadvise64`, `posix_fallocate`→`posix_fallocate64`, `pread`→`pread64`, `preadv`→`preadv64`, `preadv2`→`preadv64v2`, `prlimit`→`prlimit64`, `pwrite`→`pwrite64`, `pwritev`→`pwritev64`, `pwritev2`→`pwritev64v2`, `readdir`→`readdir64`, `readdir_r`→`readdir64_r`, `scandir`→`scandir64`, `scandirat`→`scandirat64`, `sendfile`→`sendfile64`, `setrlimit`→`setrlimit64`, `stat`→`stat64`, `statfs`→`statfs64`, `statvfs`→`statvfs64`, `tmpfile`→`tmpfile64`, `truncate`→`truncate64`, `versionsort`→`versionsort64`.
- **Forge must emit the asm label as the symbol.** Calling `strtol` under `gnu23` must reference `__isoc23_strtol`, which parses `0b` prefixes. `__isoc99_scanf` keeps C99 `%a` semantics; without the rename, plain `scanf` is glibc's GNU-compatible scanf.

## 6. Delta against #9

### 6.1 New in C mode

These 46 names are not in #9, or #9 reached them only outside its M1 configuration. 40 of them are class M: `packed`, `transparent_union`, `__builtin_aarch64_get_fpcr`, `__builtin_aarch64_get_fpsr`, `__builtin_aarch64_set_fpcr`, `__builtin_aarch64_set_fpsr`, `__builtin_c23_va_start`, `__builtin_clz`, `__builtin_complex`, `__builtin_ctz`, `__builtin_ctzll`, `__builtin_popcount`, `__builtin_popcountll`, `__builtin_stdc_bit_ceil`, `__builtin_stdc_bit_floor`, `__builtin_stdc_bit_width`, `__builtin_stdc_count_ones`, `__builtin_stdc_count_zeros`, `__builtin_stdc_first_leading_one`, `__builtin_stdc_first_leading_zero`, `__builtin_stdc_first_trailing_one`, `__builtin_stdc_first_trailing_zero`, `__builtin_stdc_has_single_bit`, `__builtin_stdc_leading_ones`, `__builtin_stdc_leading_zeros`, `__builtin_stdc_trailing_ones`, `__builtin_stdc_trailing_zeros`, `__builtin_tgmath`, `_Generic`, `_Static_assert`, `_Thread_local`, `bool`, `nullptr`, `anonymous struct or union member`, `empty struct or union`, `enumerator value outside int`, `imaginary constant suffix`, `long long`, `long long constant`, `variadic macro (__VA_ARGS__)`.

| Name | Class | C mode | Origin | #9 status |
|---|---|---|---|---|
| `indirect_return` | A | via macro: all 8 (max 1 roots) | glibc | not in #9 |
| `nothrow` | A | via macro: all 8 (max 162 roots) | glibc | #9: not reached |
| `packed` | M | code: all 8 (max 5 roots) | glibc+kernel | not in #9 |
| `transparent_union` | M | code: +gs only (all dialects) (max 24 roots) | glibc | not in #9 |
| `__builtin_aarch64_get_fpcr` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_aarch64_get_fpsr` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_aarch64_set_fpcr` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_aarch64_set_fpsr` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_c23_va_start` | M | macro only: gnu23 | gcc | #9: not reached |
| `__builtin_clz` | M | code: all 8 (max 1 roots) | glibc | #9: not reached |
| `__builtin_complex` | M | macro only: gnu89+gs, gnu99+gs, gnu17, gnu23 | glibc | #9: not reached |
| `__builtin_ctz` | M | code: all 8 (max 1 roots) | glibc | #9: not reached |
| `__builtin_ctzll` | M | code: all 8 (max 1 roots) | glibc | #9: not reached |
| `__builtin_popcount` | M | code: all 8 (max 1 roots) | glibc | #9: not reached |
| `__builtin_popcountll` | M | code: all 8 (max 1 roots) | glibc | #9: not reached |
| `__builtin_stdc_bit_ceil` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_bit_floor` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_bit_width` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_count_ones` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_count_zeros` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_first_leading_one` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_first_leading_zero` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_first_trailing_one` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_first_trailing_zero` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_has_single_bit` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_leading_ones` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_leading_zeros` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_trailing_ones` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_stdc_trailing_zeros` | M | macro only: all 8 | glibc | not in #9 |
| `__builtin_tgmath` | M | macro only: all 8 | glibc | #9: not reached |
| `_Generic` | M | macro only: all 8 | glibc | #9: not reached |
| `_Static_assert` | M | macro only: gnu89+gs, gnu99+gs, gnu17 | glibc | #9: not reached |
| `_Thread_local` | M | macro only: gnu89, gnu99, gnu17 | glibc | not in #9 |
| `__inline__` | A | code, via macro: all 8 (max 2 roots) | kernel | #9: not reached |
| `bool` | M | code: gnu23 (max 1 roots) | glibc | not in #9 |
| `nullptr` | M | code: gnu23 (max 5 roots) | gcc | not in #9 |
| `anonymous struct or union member` | M | code: all 8 (max 12 roots) | glibc+kernel | not in #9 |
| `empty struct or union` | M | macro only: all 8 | kernel | not in #9 |
| `enum trailing comma` | A | code: all 8 (max 14 roots) | glibc+kernel | not in #9 |
| `enumerator value outside int` | M | code: all 8 (max 2 roots) | glibc | not in #9 |
| `imaginary constant suffix` | M | macro only: all 8 | glibc | #9: gnu++20 only |
| `long long` | M | code: all 8 (max 104 roots) | gcc+glibc+kernel | not in #9 |
| `long long constant` | M | via macro: all 8 (max 3 roots) | glibc+kernel | not in #9 |
| `qualifier in parameter array declarator ([__restrict])` | A | code: all 8 (max 5 roots) | glibc | not in #9 |
| `variable-length array parameter` | A | code: gnu99, gnu17, gnu23 (max 2 roots) | glibc | not in #9 |
| `variadic macro (__VA_ARGS__)` | M | code: gnu89+gs, gnu99+gs, gnu17+gs, gnu23 (max 2 roots) | gcc+glibc | not in #9 |

### 6.2 Class changes

| Name | #9 class | C-mode class | Reason |
|---|---|---|---|
| `__inline` | A | M | A in #9. Under gnu89 glibc's `__extern_always_inline` is `extern __inline __attribute__ ((__always_inline__))` without `gnu_inline` (sys/cdefs.h:618-628, `__GNUC_GNU_INLINE__`), and <error.h> reaches such bodies at -O0 (bits/error.h). GNU89 `extern inline` must not emit an out-of-line definition; dropping `__inline` turns the body into an external definition of libc's `error`. |
| `__signed__` | A | M | A in #9. `__signed__` is the keyword `signed`: the kernel's `typedef __signed__ char __s8;` (asm-generic/int-ll64.h:20) needs a signed char, and plain char is unsigned on aarch64 (`__CHAR_UNSIGNED__` is predefined), so ignoring the keyword changes the type. The reasoning holds in C++ too; #9's A is corrected here. |

No other name changes class. The `__inline` change is C-specific. The `__signed__` change corrects #9; its reasoning holds in C++ as well.

### 6.3 #9 names not reached in C mode

468 names #9 reached in M1 (including M1 macro only) do not occur in C mode. Almost all are C++-only: libstdc++ builtins and traits, `<cmath>` overloads, `__atomic_*`, coroutines, standard `[[...]]` attributes, `abi_tag`, `visibility`, `#pragma GCC system_header`/`visibility`/`unroll`, `__null`, `__decltype` and `__complex__`/`__real__`/`__imag__`.

The four preprocessor operators of #9's F.19 (`__has_attribute`, `__has_builtin`, `__has_extension`, `__has_include`) are not missing. In C they are used in `#if`, and section 4 covers them; `__has_extension` is only tested with `defined`, since its calls are short-circuited.

- **Atomic builtins** (16): `__atomic_add_fetch` (M), `__atomic_always_lock_free` (M), `__atomic_clear` (M), `__atomic_compare_exchange` (M), `__atomic_compare_exchange_n` (M), `__atomic_exchange` (M), `__atomic_exchange_n` (M), `__atomic_fetch_add` (M), ... (appendix C)
- **Bit, byte-swap and overflow builtins** (8): `__builtin_add_overflow` (M), `__builtin_clzg` (M), `__builtin_clzl` (M), `__builtin_ctzg` (M), `__builtin_ctzl` (M), `__builtin_mul_overflow` (M), `__builtin_popcountg` (M), `__builtin_popcountl` (M)
- **Control-flow and hint builtins** (3): `__builtin_abort` (M), `__builtin_assume_aligned` (A), `__builtin_trap` (M)
- **Floating-point classification and constant builtins** (25): `__builtin_copysign` (M), `__builtin_copysignf` (M), `__builtin_copysignf128` (M), `__builtin_copysignf16` (M), `__builtin_copysignl` (M), `__builtin_fabs` (M), `__builtin_fabsf` (M), `__builtin_fabsf128` (M), ... (appendix C)
- **G.1** (1): `inline asm (basic)` (M)
- **GNU attributes** (6): `abi_tag` (M), `assume` (A), `externally_visible` (A), `flag_enum` (A), `noclone` (A), `visibility` (A)
- **Keyword and type extensions** (10): `_Float16` (M), `__alignof` (M), `__attribute` (A), `__complex__` (M), `__decltype` (M), `__imag__` (M), `__null` (M), `__real__` (M), ... (appendix C)
- **Language-support and constexpr builtins** (12): `__builtin_FILE` (M), `__builtin_LINE` (M), `__builtin_addressof` (M), `__builtin_bit_cast` (M), `__builtin_clear_padding` (M), `__builtin_coro_destroy` (M), `__builtin_coro_done` (M), `__builtin_coro_promise` (M), ... (appendix C)
- **Math library builtins** (293): `__builtin_acos` (L), `__builtin_acosf` (L), `__builtin_acosf128` (L), `__builtin_acosh` (L), `__builtin_acoshf` (L), `__builtin_acoshf128` (L), `__builtin_acoshl` (L), `__builtin_acosl` (L), ... (appendix C)
- **Memory and string library builtins** (16): `__builtin_abs` (L), `__builtin_index` (L), `__builtin_labs` (L), `__builtin_llabs` (L), `__builtin_memchr` (L), `__builtin_memcpy` (L), `__builtin_memmove` (L), `__builtin_rindex` (L), ... (appendix C)
- **Object-size and fortify builtins** (1): `__builtin_dynamic_object_size` (A)
- **Pragmas** (3): `#pragma GCC system_header` (A), `#pragma GCC unroll` (A), `#pragma GCC visibility` (A)
- **Preprocessor operators used outside `#if`** (4): `__has_attribute` (M), `__has_builtin` (M), `__has_extension` (M), `__has_include` (M)
- **Standard attributes** (8): `[[deprecated]]` (A), `[[fallthrough]]` (A), `[[likely]]` (A), `[[maybe_unused]]` (A), `[[no_unique_address]]` (M), `[[nodiscard]]` (A), `[[noreturn]]` (A), `[[unlikely]]` (A)
- **Syntax and directive extensions** (1): `pp-number suffix bf16` (M)
- **Type-trait builtins** (2): `__builtin_is_corresponding_member` (M), `__builtin_is_pointer_interconvertible_with_class` (M)
- **Type-trait keywords** (59): `__add_lvalue_reference` (M), `__add_pointer` (M), `__add_rvalue_reference` (M), `__array_rank` (M), `__decay` (M), `__has_trivial_constructor` (M), `__has_trivial_destructor` (M), `__has_unique_object_representations` (M), ... (appendix C)

## 7. Facts for #8

1. **Reached by header code in every configuration** (69 names, section 3.3): the core attribute set, `__builtin_bswap*`, `<stdbit.h>`'s bit builtins, `__builtin_constant_p`, `__builtin_va_arg_pack`, `__builtin_va_list`, `_Bool`, `_Complex`, the aarch64 vector-math types, `__int128`/`__uint128_t` and `long double` (binary128). Also these syntax features: `long long`, flexible and zero-length arrays, anonymous struct/union members, enum trailing commas, enumerators beyond `int`, and the kernel's named variadic macro.
2. **Only with `_GNU_SOURCE`:**
   - `transparent_union`;
   - `_FloatN` declarations;
   - the `__isoc23_*` renames before gnu23;
   - the `pthread_*_np`/`sigpause` renames;
   - the `__has_include ("linux/...")` probes in four glibc headers.
3. **Dialect-specific:**
   - gnu89 relies on GNU89 `extern inline` (no `gnu_inline` attribute) for `<error.h>`.
   - `__isoc99_*scanf` without `_GNU_SOURCE` before gnu23, and no scanf rename in `gnu89+gs`.
   - gnu23 adds `bool` (`<stdbit.h>`) and, in GCC's own headers, `nullptr` and `__builtin_c23_va_start`.
   - Anonymous struct/union members are C11; under gnu89/gnu99 GCC accepts them as an extension.
4. **Not reached in any configuration:**
   - inline asm statements;
   - `__atomic_*`/`__sync_*`;
   - `typeof`/`typeof_unqual` (only `__typeof`/`__typeof__`), `__auto_type`, `_BitInt`, `[[...]]` attributes and `__has_c_attribute`;
   - `#pragma GCC system_header`/`once`/`pack`;
   - `cleanup`, `weakref` and `visibility`.

   `#include_next` is needed only by GCC's own wrapper headers, which Forge replaces.
5. **Macro-only names become requirements as soon as user code uses the macro:** 83 names, mostly `<math.h>`, `<tgmath.h>`, `<stdbit.h>`, `<complex.h>`, `assert`, `va_*`, `offsetof`, `alloca`, `static_assert` and `thread_local`. Which of them the C budget suite expands was not measured here.
6. **`__has_*` answers.** Answer them as GCC 15.2 does (section 4). If `__has_include` is wrong, `<sys/mount.h>` and `<sys/rseq.h>` switch definitions; if `__glibc_has_builtin (__builtin_stdc_*)` is wrong, `<stdbit.h>` switches path; and `__has_builtin (__builtin_fclose)` must stay 0.
7. **Predefined macros.** Header code expands 1 compiler-predefined macros (appendix B), which a GCC-compatible Forge must predefine with GCC's values.

## 8. Against Part C and #9

**Part C** (#10's census, gcc-16 on macOS with an imposed identity, 47 roots) is **confirmed** on these points:
- `_GNU_SOURCE` brings C23 content in every dialect;
- `__glibc_const_generic` is defined in every dialect and used only in function-like macros (macro only here);
- glibc has no `__glibc_has_c_attribute` and no `[[`;
- the `__isoc23_` renames;
- `CMPLX` as `__builtin_complex` from C11;
- `static_assert`/`thread_local` as macros before C23;
- no fortify or extern inlines at -O0.

Part C is **corrected or extended** on these:
- Its dialect diff did not vary `_GNU_SOURCE`. Variadic `assert(...)` (assert.h:156 under GCC; Part C cites the strict-mode line 144) and `CMPLX` also appear with `_GNU_SOURCE` in gnu89/gnu99.
- "`nullptr` not emitted" holds for glibc text only: GCC 15's own `<stddef.h>:465` emits it under gnu23.
- Part C's 47 roots missed `<error.h>`, whose `extern inline` wrapper is reached at -O0.

**#9** (C++20, inferred from header text with an imposed identity) is **confirmed** on these points:
- glibc's version thresholds stop at (13, 0);
- the `__REDIRECT` mechanism;
- the class of every shared name except `__inline` and `__signed__` (section 6.2).

#9's known unknown 1 (no GCC run) is now settled for C, and its `__has_*` answers match GCC's where the same queries occur: `__has_builtin (__builtin_fclose)` is 0, as #9 inferred.

## 9. Known unknowns

1. **Which macro produced a via-macro construct** is taken from the macros the line's identifiers reach in the TU, using every definition of each name in that TU. Reachability itself is exact (the token is in GCC's output and not in the header line), but the named macro can be wrong when several reached macros contain the token.
2. **Syntax detection is token-level.**
   - Struct context, anonymous members and array members are found by a brace walk, not a parser.
   - GCC's pedantic diagnostics cross-check them (3.5), but GCC exempts some constructs in system headers outright (`__int128`, `_FloatN`), so the pedantic list is a lower bound.
   - The anonymous-member detector counts 12 roots where GCC reports 29 sites; the rows use both.
3. **Macro-only names** are live only when user code expands the macro. No user code was compiled.
4. **Flips change one operand at a time**, in at most 3 roots per (operand, configuration). Reporting a different GCC version, which moves every `__GNUC_PREREQ` at once, was not simulated.
5. **The six `pthread.h` conditionals** not instrumented (comment inside the directive) were not tracked for block entry; they hold no query.
6. **Ubuntu's gcc-15** is 15.2.0 plus the branch to 2026-03-21. The name tables were read from the 15.2.0 tarball, and the hunk check covers only the files listed in section 0. All observed answers are the binary's own.
7. **Out of scope:**
   - -O0 only, so `__USE_EXTERN_INLINES` bodies and fortify (Part C covered those at -O2);
   - roots other than libc6-dev's;
   - `linux/` and `asm/` roots, which are reached only through glibc;
   - `_POSIX_C_SOURCE`/`_XOPEN_SOURCE` combinations;
   - strict `-std=c*` dialects.
8. **Classes are judgements on the stated reasons.** Two depend on how Forge implements other things:
   - `indirect_return` is A only while Forge does not enable branch-target identification;
   - the `__inline` M (gnu89) matters only if Forge emits code for `extern inline` bodies.
