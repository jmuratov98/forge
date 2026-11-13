# Performance budget and measurement

Status: draft, 2026-11-13. Stable-name prefix: `[perf]`.

## 1 Scope [perf.scope]

1 This document specifies what "about 0.8× to 1.2× of clang and GCC in compile and runtime speed" means concretely: the budget, the reference compilers, how each metric is measured, the benchmark suite, when each budget binds, and how CI enforces it. No code is written under the roadmap, so the tooling of this document is implemented once there is code to measure.

## 2 The budget [perf.budget]

1 For each benchmark, the *cost ratio* is Forge's cost divided by the reference compiler's cost. For runtime, the cost is the running time of the program each compiler built.

2 The *budget* is: the suite's geometric-mean cost ratio shall be at most 1.2, and no benchmark shall exceed 1.5. The 1.5 cap stops one quadratic corner case from hiding in the mean. 0.8× is an aspiration, not a floor: being faster never fails.

3 The rule applies to each metric and each gated `-O` level separately.

4 Inside the budget, regressions are still explained. A change that raises the suite's instruction geomean by more than 1% against `main` shall say why in its pull request description, and the nightly reports any such step. This does not block; it stops slow drift toward 1.2×.

## 3 Reference compilers [perf.reference]

1 Both come from the pinned Ubuntu 26.04 image: GCC 15.2 and the image's default clang.

2 *Compile time* is compared with GCC until `fas` lands. Until then, Forge and GCC both print assembly and run GNU `as`; clang's integrated assembler skips that round trip, so comparing with clang would charge Forge for a cost [pipe.emit] accepted on purpose. Once `fas` brings the object writer, compile time compares with the faster of GCC and clang.

3 *Runtime* is compared with the faster of GCC and clang from the start, because code quality does not depend on the assembler.

4 *One identical, fully spelled-out command line on both sides.* Ubuntu's GCC turns on hardening by default: stack protector, stack-clash protection, `_FORTIFY_SOURCE=3` and `-mbranch-protection=standard`. A default that Forge implements is passed to both compilers, and one it lacks is turned off on both. Every report lists the defaults that were off.

5 Until Forge vectorizes, the `-O2` runtime gate runs the reference compilers with vectorization off ([opt.vector]). Every report lists this.

6 *Gated levels* are `-O0` and `-O2`. `-O0` is the debug-build path, and `-O2` is what distros and Forge itself ship. `-O1`, `-O3`, `-Os` and `-Og` are reported once they exist, with code size for `-Os`.

## 4 Measurement [perf.measure]

### 4.1 Compile time [perf.measure.compile]

1 Compile time shall gate on instruction counts: user-space instructions counted by Valgrind's Cachegrind (`--cache-sim=no --trace-children=yes`), summed over every job that `fcc -c` spawns (the driver, `fcc1` with preprocessing, and GNU `as`). They are compared with `gcc -c` (the driver, `cc1` and `as`). Each translation unit compiles on its own, as make runs it.

2 Counts run with ASLR off (`setarch -R`), so pointer-keyed hashing cannot change them between runs.

3 Also measured, but only reported: GNU `ld`'s run (the same binary on both sides), wall time and peak RSS.

4 Wall time is checked at each milestone end in the Mac VM, because instruction counts miss the cache effects that the dense arenas target. If wall time is over 1.2× while the counts pass, that opens a ticket rather than blocking.

### 4.2 Runtime [perf.measure.runtime]

1 Runtime shall gate on the median of 5 runs in the pinned Ubuntu 26.04 Lima VM on the developer's M4 Mac, with the machine otherwise idle. It is checked at milestone ends and on demand.

2 CI also records each output program's Cachegrind instruction count as a regression signal, never as a gate. Instruction counts are a poor proxy for code speed: they miss scheduling, branch layout and cache behaviour.

### 4.3 Threads [perf.measure.threads]

1 One core per compile job. The budget does not credit threads inside a job, because builds already run translation units in parallel. No milestone schedules in-translation-unit threading until a measured case (a huge single unit, LTO) needs it. Per-function threading stays possible: FIR functions are independent arenas, and libraries hold no mutable globals ([ir.layout]).

## 5 The budget suite [perf.suite]

1 *Compile time:* CTMark's six C programs from llvm-test-suite: sqlite3, ClamAV, consumer-typeset, lencod, mafft and SPASS.

2 *Runtime:* llvm-test-suite's C programs under `SingleSource/Benchmarks` and `MultiSource/Benchmarks`.

3 From milestone 2, Forge's own source is added to both: compiling it, and stage1 compiling the C suite.

4 CTMark's C++ programs (7zip, Bullet, kimwitu++, tramp3d-v4) join once the C++ frontend gets beyond Forge's own subset.

5 SPEC CPU stays optional, because it needs a paid licence and its sources cannot live in a public repository.

6 [Note 1: In milestone 1 the gated set is the set of [m1.gates] (about 249 of the suite's 252 programs). — end note]

## 6 When each budget binds [perf.when]

| Budget | Gates from | Reported before that |
|---|---|---|
| `-O0` compile time, C suite | Milestone 1 | — |
| `-O0` runtime, C suite | Milestone 1 | — |
| `-O0` compile time, Forge's source with `fcc1plus` against `g++` | Milestone 2 (the bootstrap) | — |
| `-O2` compile time and runtime | Milestone 3, the optimizer's milestone | Yes, once `-O2` exists |
| Stage1's own speed (Forge built by Forge) | Together with `-O2` | Yes |

1 Milestone 1 shall compile the C budget suite at `-O0` for its gate to bind; it does so on the set of [m1.gates].

## 7 CI and tooling [perf.ci]

1 This ends the "perf deferred" status of the CI design.

- (1.1) *Ready-PR full tier:* compiles sqlite3 alone at `-O0` under Cachegrind (about 1–2 minutes) and fails on a budget breach, so a regression is caught in the pull request that caused it.
- (1.2) *Nightly:* runs the whole suite at every gated level and reports more-than-1% steps.
- (1.3) `./x bench` runs the same thing locally.
- (1.4) Reference counts are cached by the image digest, because the pinned GCC and clang never change under one digest.
- (1.5) The PR tier does not run perf.

## Annex A (informative): Rationale and departures [perf.rationale]

1 *Geomeans.* SPEC and the LLVM compile-time tracker also summarise with geomeans.

2 *Instruction counts.* This departs from rustc-perf and the LLVM compile-time tracker, which both gate on instructions read from hardware counters on dedicated bare-metal machines. Forge has no such machine, and neither of its hosts is known to expose a PMU: GitHub-hosted runners have [reported missing perf counters](https://github.com/actions/runner-images/issues/4974), and nothing shows Apple's Virtualization framework giving Linux guests one. Cachegrind's counts are deterministic, so a shared CI runner and a Lima VM agree and a 1% change is visible. The 1% explanation rule is modelled on rustc-perf's triage reports.

3 *The suite.* CTMark is picked because it is curated, self-contained, freely licensed and already builds with plain GCC, not because LLVM uses it.

4 *Why wall time is checked at milestone ends.* The dense arenas target cache effects that instruction counts cannot see ([perf.measure.compile]).

## Annex B (informative): Provenance [perf.prov]

1 [Performance budget and measurement](https://github.com/jmuratov98/forge/issues/7), refined by [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12) (milestone 3 binds the `-O2` gates; vectorization off for the reference compilers) and [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10) (the gated set).
