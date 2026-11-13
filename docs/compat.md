# Drop-in compatibility surface

Status: draft, 2026-11-13. Stable-name prefix: `[compat]`.

## 1 Scope [compat.scope]

1 This document specifies what it means for Forge to be a drop-in for GCC: the reference, the identity `fcc` reports, the status every flag and extension has, the milestone-1 surface, how rows are prioritised and how compatibility is tracked. The diagnostics half of compatibility (warning flags, output format) is in [diag].

## 2 Reference [compat.reference]

1 *Drop-in* means upstream GCC 15.2 with PIE by default, as the pinned Ubuntu 26.04 image ships it. `fcc` shall accept GCC's command lines and behave as upstream GCC 15.2 does.

2 Ubuntu's own spec-file defaults are not Forge's defaults: the stack protector, stack-clash protection and `-mbranch-protection=standard` ([compat.hardening]). The budget runs of [perf.reference] keep turning them off on GCC.

3 clang spellings count only as aliases of GCC flags, such as `-fcolor-diagnostics` for `-fdiagnostics-color`. Each clang-only flag or extension gets a table row and is prioritised like any other row.

## 3 Identity [compat.identity]

1 *Predefined macros.*

- (1.1) `__GNUC__` is 15, `__GNUC_MINOR__` is 2 and `__GNUC_PATCHLEVEL__` is 0.
- (1.2) `__forge__` is defined to 1, and `__forge_major__`, `__forge_minor__` and `__forge_patchlevel__` give Forge's version.
- (1.3) `__clang__` is never defined.
- (1.4) The rest is GCC 15.2's aarch64-linux set, as the C-mode inventory dumped it, in `docs/research/c-host-header-extensions/data/facts/predef/` on `research/c-host-header-extensions`. The exceptions are `__VERSION__`, which carries Forge's banner, and `__OPTIMIZE__`, which follows the level.

2 `--version` shall print Forge's own banner, with no "Free Software Foundation" string. `-dumpversion` and `-dumpfullversion` print Forge's own version, as clang prints its own.

3 *Build-system identity* follows from the macros:

- (3.1) CMake identifies the compiler from the macros alone, so it reports `GNU` 15.2.0. `__forge__` changes nothing there.
- (3.2) Autoconf decides `GCC=yes` from `__GNUC__` alone, and libtool treats any `__GNUC__` compiler as GCC, whatever its name.
- (3.3) Meson needs the FSF string in `--version`, and ccache guesses from the binary's name, so `fcc` is "other" to both. Support for both is upstreamed under a `forge` id, keyed on `__forge__`. Until then, ccache users set `compiler_type=gcc`, and the corpus nightly ([compat.tiers]) pins a Meson with Forge's patch applied.

## 4 Flag statuses [compat.status]

1 Every flag shall have one of five statuses:

- (1.1) *implemented*;
- (1.2) *ignored*, allowed only when the output is still correct without the flag;
- (1.3) *not-yet-supported*: the not-yet-supported error of [front.defaults], naming the flag. Any flag that changes semantics, ABI or codegen and is not implemented has this status;
- (1.4) *not-planned*: an error that says Forge does not intend to support the flag;
- (1.5) *unknown*: anything GCC 15.2 does not know either. It gets GCC's "unrecognized command-line option" error, except that an unknown `-Wno-X` is silent, with GCC's note when other diagnostics are emitted.

2 The rule decides:

- (2.1) *Ignored:* GCC `-W` names Forge has not implemented; `--param` (the inline thresholds stay Forge's own); the `-f<opt>` optimization flags while only `-O0` exists; `-fno-strict-aliasing` and `-fstrict-aliasing` (there is no type-based alias analysis); `-fomit-frame-pointer` and `-momit-leaf-frame-pointer` (they permit dropping the frame record; they do not require it, so keeping it is correct); `-fvisibility` (going through the GOT is always correct).
- (2.2) *Not-yet-supported:* `-mno-outline-atomics`, until the inline LL/SC pseudos of [codegen.mir] land. Ignoring it would leave the libgcc dependency a freestanding build asked to drop.
- (2.3) `-march` and `-mcpu` are accepted for any value the imported `FEAT_` table knows. The `__ARM_FEATURE_*` macros and the `.arch` passed to GNU `as` follow the selection. Codegen stays ARMv8.0 ([targets.m1]).

3 The warning for an ignored `optimize` attribute or `#pragma GCC optimize` is GCC's `-Wattributes`, so a build's existing `-Wno-attributes` silences it.

## 5 The milestone-1 flag surface (P0) [compat.p0]

1 Everything in this clause is implemented in milestone 1.

2 *The gates' flags* ([m1.gates]):

- (2.1) `-std=gnu89`, `gnu99`, `gnu17` and `c99`, plus `-DNDEBUG`, `-w`, `-Werror=date-time`, `-fpermissive` and `-lm`;
- (2.2) the GCC 14+ error downgrades `-Wno-implicit-int`, `-Wno-error=incompatible-pointer-types`, `-Wno-implicit-function-declaration` and `-Wno-int-conversion`;
- (2.3) `-fcommon`, `-ffp-contract=off` and `-fno-strict-aliasing`;
- (2.4) each torture test's `dg-options`.

3 *Driver flags* ([pipe.driver]): `-###`, `-fno-crash-diagnostics`, `--sysroot`, `--gcc-install-dir`, `-B`, `-fuse-ld`, `-S`, `-c`, `-E` and `-o`.

4 *What CMake, Meson and Autotools pass on a default configure and build:*

- (4.1) dependency output: `-MD`, `-MMD`, `-MF`, `-MT`, `-MQ` and `-MP`;
- (4.2) `-fdiagnostics-color`, `-Wall`, `-Winvalid-pch` and `-D_FILE_OFFSET_BITS=64`. Meson passes the last one on every compile, so its 56 `*64` asm-label renames are on the default path;
- (4.3) `-cpp`, `-x c`, `-` (standard input) and `-E -dM`;
- (4.4) `-v`, whose include search list (from `#include <...> search starts here:` to `End of search list.`) and link line match GCC's exact format. CMake and Meson parse both;
- (4.5) `-print-sysroot`, `-print-prog-name=`, `-print-search-dirs`, `-print-multi-os-directory`, `-print-file-name` and `-dumpmachine`;
- (4.6) the linker pass-throughs `-Wl,` and `-Xlinker`, which carry `--as-needed`, `--no-undefined`, `--start-group`, `-rpath` and the rest;
- (4.7) `@file` response files, in GCC's quoting;
- (4.8) `-pthread` and `-rdynamic`;
- (4.9) `-fPIE`/`-fpie`, `-pie` and `-fPIC`/`-fpic` ([compat.pic]).

5 Include and macro flags: `-I`, `-isystem`, `-iquote`, `-idirafter`, `-include`, `-D`, `-U`, `-L` and `-l`.

6 *`-std=`:* every GCC 15.2 spelling for C89–C23 and C++98–C++26, including `iso9899:*` and the old draft aliases (`c9x`, `c1x`, `c2x`, `gnu2x`, `c++0x`, `c++2a`, `c++2c` and the rest). The C2y spellings `c2y` and `gnu2y` are not-planned, because working drafts are out of scope.

7 *Still not-yet-supported in milestone 1:* `-shared`, `-static`, `-static-pie`, `-g`, and `-O1` and above.

## 6 PIC [compat.pic]

1 `-fPIC` and `-fpic` codegen shall be implemented in milestone 1. Defined globals that may be preempted go through the GOT. TLS uses TLS descriptors (`TLSDESC`), the aarch64 general-dynamic model. `-fPIE` stays the default, with local-exec TLS.

2 `-shared` stays not-yet-supported, so milestone 1 still links only PIE executables ([targets.output]). The lit tests cover the codegen; no new gate is added.

## 7 Dialect overrides [compat.dialect]

1 Implemented in milestone 1: `-fgnu89-inline`, `-fno-asm`, `-trigraphs`, `-fsigned-char`/`-funsigned-char`, `-fsigned-bitfields`/`-funsigned-bitfields`, `-fpermissive`, `-fcommon`/`-fno-common`, `-fdollars-in-identifiers`, `-fno-builtin`, `-fno-builtin-<fn>`, `-ffreestanding`, `-fhosted`, `-fwrapv`, `-fno-strict-overflow`, `-fshort-enums` and `-fshort-wchar`.

2 Not-yet-supported: `-fms-extensions`, `-fplan9-extensions` and `-fpack-struct`.

## 8 Hardening [compat.hardening]

1 In milestone 1 the opt-out forms are accepted as no-ops, because they match Forge's defaults: `-fno-stack-protector`, `-fno-stack-clash-protection` and `-mbranch-protection=none`.

2 The enabling forms raise the not-yet-supported error: `-fstack-protector`, `-fstack-protector-strong`, `-fstack-protector-all`, `-fstack-clash-protection`, and `-mbranch-protection=standard`, `pac-ret` and `bti`.

3 They are P1, implemented with milestone 3, the optimizer milestone. That is when Ubuntu's `dpkg-buildflags` sets (`-O2` with these flags) first become buildable. `-mbranch-protection=standard` needs PAC and BTI in frame lowering (`paciasp`/`autiasp`, and `bti c` at indirect-branch targets) plus the GNU property note in each object; the stack protector needs a canary in frame lowering; stack-clash protection needs probing for large frames.

4 `indirect_return` becomes must-implement once BTI exists. Until then it is ignored, as the C-mode inventory classed it.

5 `_FORTIFY_SOURCE` is a plain macro. At `-O0` glibc compiles no fortify code, so it needs nothing in milestone 1.

## 9 Extensions [compat.extensions]

1 Milestone 1 shall implement every GNU C extension the gates reach:

- (1.1) the header sweep's names from the C-mode inventory: the *must-implement* names implemented, the *accept-and-ignore* names accepted and ignored, and the 3 names that *lower to a libc or libm call* lowered to their calls;
- (1.2) the macro-only names that gated programs expand;
- (1.3) the suite's attributes (`aligned`, `optimize`, `noinline`, `const`, `format`, `noreturn`, `packed` and `vector_size`), builtins (`__builtin_alloca`, `isnan`, `huge_val`, `isinf_sign`, `memcpy` and `offsetof`) and pragmas (`STDC FP_CONTRACT`, `scop`/`endscop`, `omp` without `-fopenmp`, and `ident`);
- (1.4) the GNU language extensions in the suite's 7 programs;
- (1.5) from the torture tests: `vector_size` (24 tests), computed goto (17), inline asm (96) and complex integer types (7).

2 *Nested functions are not-planned.* clang never supported them, and GCC's version needs trampolines on an executable stack. Their 30 torture tests become expected-error skips that stop with the not-planned error. They come back only on demand, and then only with heap trampolines, as GCC 14's `-ftrampoline-impl=heap` does.

3 *Carried from the C-mode inventory:*

- (3.1) GNU89 `extern inline` semantics, for `<error.h>`'s `error` wrapper at `-O0`; no out-of-line `error` may be emitted;
- (3.2) `__signed__` shall be implemented in both languages, and `__inline` in C;
- (3.3) every asm label is honoured. `-D_FILE_OFFSET_BITS=64 -D_TIME_BITS=64` add 56 `*64` renames (65 with `_GNU_SOURCE`) even on LP64.

4 *`__has_*` answers.* They shall answer as GCC 15.2 does: 1 for every query the headers evaluate, except `__has_builtin (__builtin_fclose)`, which is 0. This agrees with "true only for what is implemented" ([front.core]) because milestone 1 implements every name the headers steer on. Any other answer to `__has_include ("linux/…")` or to `__glibc_has_builtin (__builtin_stdc_*)` switches `<sys/mount.h>`, `<sys/rseq.h>` and `<stdbit.h>` onto different code.

5 *Milestone 2 (C++).* P0 is the must-implement names of the C++ header inventory that Forge's own build reaches, plus whatever Forge's own source uses. The C extensions that the C++ frontend accepts (variable-length arrays, `_Complex`, compound literals and pre-C++20 designated initializers) are P2 or P3 after the bootstrap, unless Forge's source or the libstdc++ headers reach them.

## 10 Extension warnings [compat.warnings]

1 A later-revision feature used in an earlier dialect shall warn by default, under clang's names: `-Wc99-extensions`, `-Wc11-extensions`, `-Wc23-extensions` and `-Wc++NN-extensions`. This holds even where GCC is silent, such as `long long` or `_Static_assert` in `gnu89`. The warnings are suppressed in system headers.

2 GCC's `-Wc90-c99-compat`, `-Wc99-c11-compat` and `-Wc11-c23-compat` keep GCC's meaning: they warn about any feature missing from the older revision, even in a newer mode.

3 GNU extensions that do not come from a later revision, such as statement expressions, keep GCC's severity: a pedwarn only under `-Wpedantic`. `-pedantic-errors` makes all of them errors.

## 11 Priority [compat.tiers]

1 Each row has a tier:

- (1.1) *P0*: what the current milestone's gates need. P0 blocks the milestone.
- (1.2) *P1*: what standard build flag sets need: Ubuntu's `dpkg-buildflags`, and the CMake, Meson and Autotools defaults. Each row lands once its milestone makes it usable, as `-O2` and `-g` do.
- (1.3) *P2*: ranked by measured demand in the corpus.
- (1.4) *P3*: on request.

2 *The drop-in corpus* is a non-gating nightly report, from milestone 1. It builds a pinned list of real C projects with their own build systems and `CC=fcc`, overriding only `-O` and `-g`. Every not-yet-supported and not-planned error names its table row. The report counts how many projects hit each row, and that count ranks P2. Picking the projects is left to whoever builds the nightly. Meson projects use the patched, pinned Meson ([compat.identity]).

## 12 Tracking [compat.tracking]

1 Two committed tables, one for flags and one for extensions, shall be the single source. They are fixed-schema text, like the `.isa` files, and a C++ generator built in-tree reads them ([codegen.isa.gen]). There is no Python tooling, and no generated C++ is committed.

2 *The flags table generates* the driver's option parser. Every compiler job takes the same option language ([pipe.driver]). *The extensions table generates* the C-family core's builtin, attribute and pragma tables, and so the `__has_*` answers. The flag map of [opt.levels] is columns of the flags table.

3 *Columns:* name, GCC spelling, clang alias, kind, status, milestone, tier, mapped pass, tests, and a comment giving the reason for the status. The extension warnings, the identity flags and the `-std=` spellings are rows like any other.

4 *CI checks:*

- (4.1) every flag the pinned image's GCC 15.2 lists (`gcc -Q --help=common,optimizers,warnings,target,params,c,c++`) has a row;
- (4.2) the extensions table is seeded from the two header inventories and the gates' census;
- (4.3) every implemented row names at least one test;
- (4.4) a compatibility status page is generated into `docs/`.

## Annex A (informative): Rationale and departures [compat.rationale]

1 The user overrode three recommendations: Forge's own `__forge__` version macros, spelled out by the user; `-dumpversion` and `-dumpfullversion` printing Forge's own version, not GCC's; and extension warnings always on, clang style, rather than only where GCC rejects the feature.

2 *Extension warnings.* GCC accepts many of these features silently in GNU modes. Forge warns, as clang does, because its feature table accepts more than GCC's ([front.dialects]), and the user wants that leniency to stay visible.

3 *Nested functions.* Not-planned, because clang never supported them and GCC's trampolines need an executable stack.

4 *Ignored flags.* "Ignored" is allowed only when the output stays correct; a flag that changes semantics, ABI or codegen and is not implemented is never ignored.

## Annex B (informative): Header-inventory facts [compat.facts]

1 *C-mode inventory* (`research/c-host-header-extensions`, 300bbd7, run on real GCC 15.2 in a Lima VM). GCC accepts 238 of 241 root headers in all 8 configurations (`gnu89`, `gnu99`, `gnu17`, `gnu23`, each with and without `-D_GNU_SOURCE`). They reach 165 names: 125 must be implemented, 3 may lower to a libc or libm call, and 37 are safe to accept and ignore. Of the 165, 82 are reached by header code and 83 sit in macro bodies that are live only when user code uses `<math.h>`, `<tgmath.h>`, `<stdbit.h>`, `CMPLX`, `assert`, `va_*`, `offsetof` or `alloca`. 46 names are new compared with C++ mode; 40 of them must be implemented.

2 *C++ inventory* (`research/host-header-extensions`, 7c6166f). Any `__GNUC__ >= 13` selects exactly the code GCC 15.2 sees. Reporting as clang, or as neither, selects different header code, so Forge reports as GCC. Of 670 names, 201 must be implemented, 226 may lower to a libc or libm call and 52 are safe to ignore, under the milestone-2 configuration. GCC was not run for this inventory.

3 *`gnu89` and `_GNU_SOURCE`.* `gnu89` needs GNU89 `extern inline` semantics. `_GNU_SOURCE` brings in `transparent_union` (24 roots), the `_FloatN` declarations, the `__isoc23_*` renames in dialects before `gnu23`, and four extra `linux/*.h` probes. The distinct asm-label renames are 19 in `gnu89`/`gnu99`/`gnu17`, 33 in `gnu23`, 35 in `gnu89` with `_GNU_SOURCE`, and 47 in the other three dialects with it.

4 *Never reached in C:* `__atomic_*`, `__sync_*`, `typeof`, `_BitInt`, `[[…]]`, `#pragma GCC system_header`, `once` and `pack`, `cleanup`, `weakref` and `visibility`.

## Annex C (informative): Provenance [compat.prov]

1 [Drop-in compatibility surface](https://github.com/jmuratov98/forge/issues/8); inputs from [C-mode host header extension inventory](https://github.com/jmuratov98/forge/issues/13), [Host header extension inventory](https://github.com/jmuratov98/forge/issues/9), [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10), [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12), [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11) and [Frontend strategy](https://github.com/jmuratov98/forge/issues/6). The facts on build-system detection come from a research pass over CMake v4.4.5, Meson 1.12.1, Autoconf 2.72, Automake 1.19, libtool 2.5.4 and ccache v4.14.3.
