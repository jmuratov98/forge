# Milestone 1: the C vertical slice

Status: draft, 2026-11-13. Stable-name prefix: `[m1]`.

This is the handoff definition for milestone 1. It cross-cuts the area specifications: it says what each one must deliver by milestone 1 and what proves the slice done. The area specifications hold the detail; this document holds the cut.

## 1 Scope [m1.scope]

1 Milestone 1 delivers `fcc` and `fcc1`. Built by GCC 15.2 or by the image's clang, they compile C for `aarch64-unknown-linux-gnu` at `-O0`, through the assembly printer, GNU `as` and GNU `ld`, on the pinned Ubuntu 26.04 image ([targets.bootstrap]).

2 Milestone 1 builds only the C side. The C frontend sits on the shared lexer and preprocessor and on the C-family core. Nothing from the C++ frontend is needed ([front.shape]).

3 Everything not listed as delivered here raises the *not-yet-supported error* ([roadmap.rules]).

## 2 Target and environment [m1.target]

1 The target is the one of [targets.m1]: host and target are `aarch64-unknown-linux-gnu`, ARMv8.0-A, little-endian, LP64, hard-float with AdvSIMD, unsigned `char`, small code model. Outline atomics are used ([targets.atomics]). The output is an ELF64 PIE executable linked by GNU `ld`, with glibc and libgcc.

2 `-fPIC` and `-fpic` code generation is delivered ([compat.pic]). `-shared`, `-static`, `-static-pie`, `-g`, and `-O1` and above are not-yet-supported errors ([compat.p0]).

3 All gates run in the pinned Ubuntu 26.04 image: one container image, pinned by digest, in a Lima VM on the developer's Apple Silicon Mac and on GitHub's `ubuntu-26.04-arm` runners ([targets.bootstrap]).

## 3 Language [m1.dialect]

1 The slice implements C89 through C17 in full, including C11's optional features:

- (1.1) variable-length arrays;
- (1.2) `_Complex float`, `_Complex double` and `_Complex long double`;
- (1.3) `_Atomic`, lowered with outline atomics, with the `<stdatomic.h>` resource header;
- (1.4) `_Thread_local`, on local-exec TLS (a program's own TLS in a PIE executable is always local-exec).

2 The slice implements a *C23 baseline* so that a default `gnu23` compile works ([front.defaults]):

- (2.1) the keywords `bool`, `true`, `false`, `static_assert`, `alignas`, `alignof` and `thread_local` (the last four being the C11 spellings under new names);
- (2.2) `()` in a declaration means `(void)`;
- (2.3) every other C23 keyword is reserved.

3 Every other C23 feature raises the not-yet-supported error: `constexpr`, `auto`, `typeof`, `nullptr`, `[[...]]`, `_BitInt`, `#embed`, digit separators and the rest. Removed features keep GCC 15's severity; for example, K&R definitions still compile at `gnu23`, with a warning.

4 `_Float32`, `_Float64`, `_Float128`, `_Float32x` and `_Float64x` are distinct built-in types in every C dialect, with the formats float, double, binary128, double and binary128.

5 The slice implements every GNU C extension that the gates reach ([compat.extensions]), and the P0 flag surface of [compat.p0].

6 [Note 1: Paragraph 2 pulls a few C23 rules ahead of the chronological revision order ([front.order]). It lets `int main()` compile at the fixed default, and lets the gates compile the suite with its own flags exactly as GCC 15 sees it, with no `-std` injected. — end note]

## 4 Types and exclusions [m1.types]

1 `long double` is IEEE binary128. `f128` joins FIR's scalars. Arithmetic, comparisons and conversions call libgcc's soft-float routines (`__addtf3`, `__multf3`, `__extenddftf2`, `__fixtfsi` and the rest). Values pass in `q` registers under AAPCS64. Constants are folded with Forge's software arithmetic.

2 `__int128` is supported in full, and `__SIZEOF_INT128__` is predefined as GCC predefines it. `i128` joins FIR's scalars. Add, subtract, multiply, shifts and comparisons are inline sequences on pairs of virtual registers. Division, remainder and floating conversions call libgcc (`__divti3`, `__udivti3`, `__modti3`, `__umodti3`, `__floattidf`, `__fixdfti` and the rest). Values pass in even-numbered register pairs.

3 `_Complex` is split into scalar pairs in the shared HIR → FIR lowering and never reaches MIR. Multiplication and division call libgcc's `__mulsc3`, `__muldc3`, `__multc3`, `__divsc3`, `__divdc3` and `__divtc3`. The ABI interface classifies a complex value as a two-member homogeneous aggregate.

4 There is no debug information: no `.debug_*` sections and no `.cfi_*` directives, hence no `.eh_frame`. `-g` raises the not-yet-supported error. Every function keeps its `x29`/`x30` frame record, so backtraces still work. Thread cancellation still works through glibc's end-of-stack fallback.

5 Only `-O0` is delivered. `-O1` and above raise the not-yet-supported error. `-O0` runs exactly one pass, the `always_inline` inliner ([opt.module]). `-ffp-contract` defaults to GCC's (`fast` in GNU dialects), but GCC forms no fused multiply-adds at `-O0`, so milestone 1's selection rules do not contract `fmul` with `fadd`.

6 [Note 1: This departs from GCC, whose aarch64 Linux default emits `.eh_frame` (asynchronous unwind tables). Forge's objects lack it, so glibc's `backtrace()` and `perf` stop at Forge frames. — end note]

## 5 What milestone 1 delivers [m1.deliver]

1 *Driver and host* ([pipe]):

- (1.1) `fcc` spawns one `fcc1` job per translation unit, then GNU `as`, then GNU `ld` ([pipe.driver]);
- (1.2) the layout table has one entry, Ubuntu 26.04 multiarch on aarch64 ([pipe.layout]);
- (1.3) the resource headers ([pipe.resource]);
- (1.4) the automatic crash reproducer ([pipe.crash]);
- (1.5) inline asm, asm labels and top-level asm pass through as text, so no assembler parser is needed ([pipe.emit]).

2 *Frontend* ([front]): the lexer and preprocessor, the C-family core with its feature table and its builtin, attribute and pragma tables, the C frontend with its own parser, AST and sema (including GNU89 `extern inline` semantics, so that no out-of-line `error` is emitted from `<error.h>`'s wrapper at `-O0`, [compat.extensions]), and the C constant evaluator (integer constant expressions and address constants in static initializers; C23 `constexpr` objects wait for the feature, which is a not-yet-supported error in milestone 1).

3 *IR* ([ir]): HIR with its printer, round-tripping parser and verifier; the shared HIR → FIR lowering; FIR with the same three tools; `f128` and `i128`.

4 *Code generation* ([codegen.m1]):

- (4.1) the AARCHMRS import and the hand-written operand-kind table;
- (4.2) the generator and the rules compiler;
- (4.3) the AArch64 selection rules, including libgcc calls for `f128` and `i128`, and outline-atomics calls;
- (4.4) the local allocator and the allocation checker;
- (4.5) frame lowering, pseudo expansion and branch relaxation;
- (4.6) the generated printer, encoder and decoder, with the oracle test against GNU `as`;
- (4.7) common symbols (`.comm`) in the machine-code stream, for `-fcommon` ([codegen.m1]).

5 *Diagnostics* ([diag.m1]): the engine and tables, both styles, `-fdiagnostics-show-id`, carets and labels, include and macro notes, text and parseable fix-its, `-fdiagnostics-generate-patch`, SARIF 2.1.0, colour and URLs, all control flags and pragmas, the column options, `--explain`, generated docs and the determinism gate. Not delivered: C++ template context, the speculative capture scope, `-fopt-info` and inlined-call-site pragma checks.

6 *Compatibility* ([compat]): the P0 rows of [compat.p0], the identity macros and banner of [compat.identity], the corpus nightly of [compat.tiers].

## 6 Gates [m1.gates]

1 Everything runs at `-O0` in the pinned image. Each gate shall be green on `main`.

2 Gate 1, *lit tests*. Forge's own lit tests, with `-verify` and FileCheck.

3 Gate 2, *the budget suite against its reference outputs*.

- (3.1) The suite is llvm-test-suite, pinned to one commit and refreshed only deliberately, like the image.
- (3.2) The scope is every C program it configures for aarch64 Linux that GCC 15.2 builds and passes as configured: about 249 of 252, all but plot2fig, archie and unix-tbl. GCC defines the set, so no program is dropped to suit Forge. The three GCC rejects are reported upstream, not patched.
- (3.3) The harness is the suite's own CMake and lit, with `CC=fcc`.
- (3.4) A program passes when its output matches `<name>.reference_output` within its `fpcmp` tolerances.
- (3.5) The `-O0` compile-time and runtime budgets of [perf] bind on this same set.

4 Gate 3, *GCC 15's `gcc.c-torture/execute`* (1,809 tests in the census). They run from a pinned, separate checkout; the tests are GPL-3 and shall never be vendored. Each test's `dg-options` are honoured: 75 need `-std=gnu89` and 32 need `-fpermissive`.

5 Gate 4, *the ABI interop check*. Generated tests split callers and callees between Forge-built and GCC-built objects, in both directions, modelled on GCC's `struct-layout-1` compat harness. Coverage: structs, bitfields, HFAs and HVAs, variadic calls, `long double`, `__int128` and `_Complex`.

6 Gate 5, *the header sweep*.

- (6.1) One translation unit per header in libc6-dev's `/usr/include`, skipping `bits/` and the kernel's `linux/` and `asm/`. Kernel headers are covered wherever glibc includes them.
- (6.2) Each builds with and without `-D_GNU_SOURCE`, at `gnu89`, `gnu99`, `gnu17` and the default `gnu23`.
- (6.3) Wherever `gcc -fsyntax-only` accepts a translation unit, `fcc` shall accept it too. GCC defines the set; there is no hand-kept list.

7 Gate 6, *determinism*.

- (7.1) Repeatability: each translation unit compiled twice, from a different working directory and temp directory with ASLR on, gives byte-identical `.s` and `.o`. This checks that no temp path reaches an object.
- (7.2) Host independence: `fcc` built by GCC 15.2 and `fcc` built by the image's clang emit byte-identical `.s`.

8 Gate 7, *differential fuzzing*, is a report, not a gate. csmith and yarpgen programs built by Forge and GCC shall print the same checksum. It runs nightly. A fuzz find is a new bug, not a regression.

## 7 Skips [m1.skips]

1 Every skip is an expected-error skip. Each entry on the torture or suite skip list names the feature the test needs. The harness checks that `fcc` stops with the not-yet-supported (or, for nested functions, not-planned) error that names that feature. An unexpected pass fails the run, as lit's XPASS does.

2 A skip can therefore not hide a crash or a miscompile, and the list records which features are still missing. It shrinks as they land.

3 [Note 1: This departs from GCC's and LLVM's XFAIL, which accepts any failure. — end note]

## 8 CI [m1.ci]

1 This adds to the CI design. It is built once compiler code exists.

| Tier | Runs |
|---|---|
| Ready-PR full tier (the gate) | lit tests; header sweep; c-torture/execute; ABI interop on fixed seeds; repeatability on the torture tests and sqlite3; GCC-vs-clang `.s` identity on sqlite3; sqlite3 `-O0` perf ([perf.ci]) |
| Nightly, no fail-fast | the budget suite against reference outputs; both determinism checks across the whole suite; ABI interop on fresh seeds; the csmith/yarpgen report; the whole perf suite ([perf.ci]); the drop-in corpus ([compat.tiers]) |
| PR tier | unchanged |

## 9 Definition of done [m1.done]

1 Milestone 1 is done when every gate of [m1.gates] is green on `main`, and the milestone-end runtime check in the Mac's Lima VM ([perf.measure.runtime]) passes.

## Annex A (informative): Rationale and departures [m1.rationale]

1 *Why the slice is cut here.* The census (Annex B) shows the budget suite is 252 C programs. 112 need only C89 features, 137 need C99 and none needs C11. GCC rejects 37 at `gnu23`, and the suite pins 34 of them below C23. sqlite3 does real binary128 arithmetic, which is why `long double` is complete. No suite program uses `__int128`, but 15 torture tests do, and `<signal.h>` in every gnu mode reaches `__uint128_t vregs[32]` through `<asm/sigcontext.h>`; the user chose full `__int128` over objects only.

2 *Departures.*

- (2.1) The host-independence check moves the stage0 identity check forward from the bootstrap, so undefined behaviour and evaluation-order dependence in Forge are caught while the codebase is small. Neither GCC nor LLVM gates on host-compiler independence; GCC compares only its own stage2 and stage3.
- (2.2) Expected-error skips replace XFAIL ([m1.skips]).

3 *Why `-fPIC` is in.* Meson builds static libraries with `-fPIC` by default (`b_staticpic`) and libtool compiles with `-fPIC -DPIC`. The change from PIE on aarch64 is small and is covered by lit tests; no new gate is added ([compat.pic]).

## Annex B (informative): Census facts [m1.census]

1 Facts come from `research/c-budget-suite-census` at 3fbb812: llvm-test-suite at `2ecf20c2`, GCC's `releases/gcc-15` torture tests at `7b7cd17e`, Ubuntu 26.04's libc6-dev 2.43-2ubuntu2.4. Compile results came from Homebrew GCC 16.1 given the Linux identity, not from GCC 15.2 on glibc; its "Known unknowns" section lists the rest.

2 Feature use in the suite: `_Complex` in 3 programs (mandel, mandel-2, rsbench), VLAs in 9 (ClamAV among them), `_Atomic` and threads in none. 177 programs pin no `-std` and so compile at the compiler's default, `gnu23` for GCC 15. GCC at `gnu23` rejects 37 programs because `()` now means `(void)` and `bool`, `true` and `false` became keywords.

3 glibc at `202311L` adds very little: `_Generic` qualifier-preserving macros for `strchr` and ten others, `bool` in `<stdbit.h>`, a variadic `assert`, `char8_t` and `__isoc23_` asm-label redirects. It adds no `[[...]]`, `typeof`, `constexpr` or `nullptr`. `_GNU_SOURCE` turns the C23 content on in every dialect.

4 At `-O0`, `__OPTIMIZE__` is undefined, so fortify and the extern-inline bodies are never compiled and `-D_FORTIFY_SOURCE=3` adds nothing.

## Annex C (informative): Provenance [m1.prov]

1 [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10); [Drop-in compatibility surface](https://github.com/jmuratov98/forge/issues/8) (P0 surface, `-fPIC`); [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11) (inherited codegen work); [Diagnostics model, formats and fix-its](https://github.com/jmuratov98/forge/issues/14) (what ships); [Pipeline shape and component boundaries](https://github.com/jmuratov98/forge/issues/4) and [Milestone-1 target matrix](https://github.com/jmuratov98/forge/issues/2) (target, driver, host); [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12) (`always_inline` at `-O0`); [Performance budget and measurement](https://github.com/jmuratov98/forge/issues/7) (budgets bound on the gate set).
