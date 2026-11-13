# Optimizer pipeline and pass manager

Status: draft, 2026-11-13. Stable-name prefix: `[opt]`.

## 1 Scope [opt.scope]

1 This document specifies how passes and analyses run over FIR (and, for the shared tables, MIR): the pass manager, the analyses and their invalidation, how a module is scheduled, the simplifier, alias analysis, the pass pipeline of each `-O` level, block layout, the semantic flags and attributes the optimizer honours, and how the optimizer is verified. It binds from milestone 3, except where it says milestone 1 ([opt.module]).

## 2 Milestone [opt.milestone]

1 Milestone 3 ships the optimizer ([roadmap.m3]). It comes directly after the bootstrap (milestone 2), before the second target and before `fas` and `fold`. It brings:

- (1.1) the `-O1`, `-O2`, `-O3`, `-Os`, `-Oz`, `-Og` and `-Ofast` pipelines;
- (1.2) the decoupled register allocator ([codegen.regalloc]);
- (1.3) the `-O2` compile-time and runtime gates and stage1's own speed ([perf.when]).

2 The stage check runs again at `-O2`: stage2 and stage3, each built by Forge at `-O2`, shall be byte-identical. Forge's C++ source is the largest real workload the optimizer sees, and a miscompile shows up as a stage mismatch.

3 The optimizer is built and tuned on aarch64 alone, because it works on FIR, which does not depend on the target. The milestone order after it stays in the fog ([roadmap.fog]).

4 Optimizer output shall be deterministic. No pass iterates in an order that depends on a pointer value, because the stage check requires identical output.

## 3 Pass manager [opt.manager]

1 Each `-O` level shall be a fixed table of named entries `{name, function, gate}`, run by a plain loop. A *gate* is a GCC flag name from the flag map ([opt.levels]). Repeated passes get instance names, such as `simplify#2`.

2 *Testing hooks.* These are internal-only flags, which the public driver rejects:

- (2.1) start and stop at a named pass ([ir.text]);
- (2.2) `--passes=a,b,...` runs an exact list over `.fir` input, so a pass test does not depend on its neighbours in the pipeline;
- (2.3) `--pass-limit=N` stops after N pass runs, to bisect a miscompile, as LLVM's `-opt-bisect-limit` does.

3 The verifier runs after every pass in assertion-enabled builds.

4 The MIR pipeline uses the same tables and the same analysis cache ([codegen.pipeline]).

## 4 Analyses [opt.analyses]

1 The analyses are a closed set, an enum. Per function: def-use, dominators, post-dominators, loops, memory SSA, scalar evolution and loop dependence. Per module: the call graph.

2 Each function has a cache. A pass asks for an analysis, and the cache builds it on demand.

3 Each pass returns a bitmask of what it preserved.

- (3.1) "Changed nothing" preserves everything. Most pass runs change nothing, so most analyses survive them.
- (3.2) "Changed instructions only" preserves the CFG analyses: dominators, post-dominators and loops.
- (3.3) Each analysis declares what it depends on. For example, dominators depend on the CFG, and def-use depends on the instructions.
- (3.4) A pass may keep an analysis current itself, such as dominators across an edge split, and say so.

4 Assertion-enabled builds shall recompute every analysis a pass says it preserved, and compare.

## 5 Scheduling the module [opt.module]

1 *At `-O0`* the compiler streams one function at a time and runs exactly one pass: the `always_inline` inliner. This is the only optimization in milestone 1.

- (1.1) GCC and clang both inline `always_inline` callees at `-O0`.
- (1.2) A `gnu_inline` `extern inline` function marked `always_inline` may have no out-of-line definition, so calling it out of line would fail at link time.
- (1.3) Each `always_inline` function's FIR is kept until the end of the translation unit. A caller whose `always_inline` callee has not been lowered yet waits until it is.
- (1.4) Failing to inline an `always_inline` call is an error, as in GCC. The work is FIR cloning and call-site substitution, inside the `-O0` budget.

2 *Above `-O0`* the whole translation unit's FIR stays alive until codegen, in four *phases*:

- (2.1) Phase 1, *early cleanup* of each function, right after it is lowered, while it is hot in cache. This also shrinks its arenas before the rest of the unit is lowered.
- (2.2) Phase 2, *bottom-up over the call graph's strongly connected components*. Inline into each function, then run the function simplification pipeline on it. Callers then see each callee's simplified size and its inferred attributes (`pure`, `const`, `nothrow`, `noreturn`, `nocapture`).
- (2.3) Phase 3, *module passes*: drop unreferenced static functions and globals; make never-written statics constant; remove or propagate the arguments of static functions.
- (2.4) Phase 4, *late passes* for each function, then FIR → MIR → stream. That function's arenas are then reset.

3 Specialized clones made by IPA-CP cloning at `-O3` run the function simplification pipeline before phase 4.

4 Each compile job stays single-threaded ([perf.measure.threads]).

## 6 The simplifier [opt.simplify]

1 The simplifier's rewrites shall be FIR → FIR rules in the selection rules language ([codegen.isel]). They live in one target-independent `fir.simplify` file, which the same generator compiles into a C++ matcher. Targets may add rules of their own.

2 One worklist-driven `simplify` pass applies the rules. It also folds constants with Forge's software arithmetic and removes trivially dead code. The pipeline runs it several times.

3 The generator checks the rules. Overlapping rules need an explicit priority, as in selection. Simplification is not total, so instead of totality the generator checks that each rule's result is no larger than its pattern, which makes rewriting terminate.

4 Libcall folding rules, such as folding `strlen` of a constant or turning `printf("x\n")` into `puts`, are skipped under `-fno-builtin`, `-fno-builtin-<fn>` and `-ffreestanding`.

## 7 Memory and alias analysis [opt.alias]

1 *Memory SSA* is an analysis: one chain of memory versions. It is built only when a pass asks for it, and dropped when memory operations change, which keeps "no persistent use-lists" ([ir.layout]).

2 *Basic alias analysis* knows: distinct stack slots and globals; allocations that never escape; constant offsets from one base; `restrict` parameters; known library calls (`malloc`, `memcpy` and so on); and the attributes `malloc`, `alloc_size`, `pure` and `const`.

3 Type-based alias analysis is deferred. Its trigger is a budget benchmark that misses because the analysis is absent. Until then `-fstrict-aliasing` is accepted and does nothing, which is always safe.

## 8 Vectorization [opt.vector]

1 A later milestone brings vectorization ([roadmap.fog]). Until then, the `-O2` runtime gate runs the reference compilers with vectorization off: GCC with `-fno-tree-vectorize` (GCC 12 and later vectorize at `-O2` with the very-cheap cost model) and clang with `-fno-vectorize -fno-slp-vectorize`. Every report lists this ([perf.reference]).

2 `-fvect-cost-model=dynamic` and `-fversion-loops-for-strides`, from GCC's `-O3`, wait for the vectorizer.

## 9 Pipelines [opt.levels]

1 *The flag map.* A committed flag map shall map GCC 15.2's optimization flags to Forge passes. Each GCC flag maps to the Forge pass that does its job, or is recorded as unmapped with the reason. The flag map is columns of the flags table of [compat.tracking].

2 Each `-O` level is GCC's documented flag set for that level. A Forge pass runs at a level only if one of its flags is in that level's set. `-f<flag>` and `-fno-<flag>` turn the mapped pass on and off; for example, `-O2 -fno-tree-dse` turns off `dse`. Every pass Forge has is mapped wherever GCC enables its flag, which is why `gvn` does partial-redundancy elimination at `-O2`, under `-ftree-pre`.

3 Which GCC flags the driver accepts at all is decided in [compat.status]. A flag that is accepted but unmapped does nothing.

4 `-O2` has 20 distinct passes and runs about 30 passes per function:

```
Phase 1  early, per function, right after lowering
  promote-slots  simplify  cfg  early-cse

Phase 2  bottom-up over call-graph SCCs, per function
  inline         callee cost = its simplified size
  promote-slots  simplify  sccp  cfg
  tailrec        self tail calls -> loops
  gvn            value numbering, load elimination, PRE
  loops:         loop-canon (preheader, rotate, exits)
                 licm  indvars  idiom  unroll-full
  dse  simplify  cfg
  attrs          pure/const/nothrow/noreturn/nocapture

Phase 3  module
  globals        drop dead statics, constify, fold
  args           dead and constant args of statics

Phase 4  late, per function, then FIR -> MIR
  simplify  lsr  select  sink  cfg  layout
```

5 The passes:

- (5.1) `promote-slots` splits stack slots that never escape into scalars, and promotes those to SSA. It covers what the lowering cannot see: aggregates, ABI coercion slots, and locals whose address stops escaping once a callee is inlined.
- (5.2) `cfg` merges and removes blocks, folds constant branches, and does cheap jump threading (`-fthread-jumps`, `-ftree-dominator-opts`).
- (5.3) `gvn` does value numbering, and full-redundancy and load elimination over memory SSA (`-ftree-fre`). It adds PRE under `-ftree-pre`, and partial PRE under `-ftree-partial-pre`. FRE and PRE share one value-numbering engine.
- (5.4) `idiom` turns loops into `memset` and `memcpy` calls (`-ftree-loop-distribute-patterns`).
- (5.5) `lsr` does induction-variable strength reduction against the target's addressing modes (`-fivopts`, `-ftree-slsr`).
- (5.6) `select` if-converts small diamonds into `select`, which becomes `csel` (`-fif-conversion`, `-fssa-phiopt`).
- (5.7) `sink` moves each value next to its single user, which widens what selection can fold (`-ftree-sink`).

6 *The inliner.*

- (6.1) A callee's cost is its own simplified FIR size, which the bottom-up order guarantees; constant arguments that fold earn a bonus.
- (6.2) `always_inline` is forced; `noinline` and `noipa` are respected.
- (6.3) A static function with a single caller is always inlined.
- (6.4) Members of a recursive SCC are inlined only from outside it.
- (6.5) The thresholds are Forge's own, because FIR sizes differ from GIMPLE's, but they follow GCC's ordering across levels.

7 Every pass added later shall show its compile-time cost and its runtime gain on the suite in its pull request.

8 *Unmapped GCC `-O2` flags* include VRP, instruction scheduling, switch conversion, store merging, code hoisting, tail merging and crossjumping, IPA-ICF, isolating erroneous paths, `strlen` optimization, partial inlining and alignment. Each gets a Forge pass only when the `-O2` gate measures a need. Devirtualization waits for the C++ frontend's high-level passes, which are in the templates fog.

9 *Other levels*, from GCC's lists:

- (9.1) `-O1` runs the four phases with the passes whose flags are in GCC's `-O1` set. The inliner runs only for `always_inline` and called-once functions (`-finline-functions-called-once`). There is no `tailrec` or sibling calls (`-foptimize-sibling-calls` is an `-O2` flag), no `idiom`, no `args` (`-fipa-cp`, `-fipa-sra`) and no PRE. `layout` uses the simple algorithm.
- (9.2) `-O3` is `-O2` plus GCC's whole `-O3` set, except the two vectorization flags: `unswitch` (`-funswitch-loops`); `peel` (`-fpeel-loops`: peeling, plus complete unrolling that may grow code); `split-loops` and `split-paths`; `distribute` (`-ftree-loop-distribution`, sharing its engine with `idiom`); `interchange` and `unroll-and-jam`; predictive commoning; IPA-CP cloning (`-fipa-cp-clone`, which makes `args` create specialized clones); partial PRE; a redundant-load pass on MIR after register allocation (`-fgcse-after-reload`); and GCC's higher `-O3` inline limits.
- (9.3) `-funroll-loops` runs a partial and runtime unroller. As in GCC, `-O3` does not turn it on.
- (9.4) `-Os`, `-Oz` and `-Og` follow GCC's lists. `-Og` is `-O1` without `promote-slots` (`-ftree-sra`), `dse`, `select`, `licm` and called-once inlining. Debug info is still in the fog, and that fog revisits `-Og`.
- (9.5) `-Ofast` is `-O3 -ffast-math`, as in GCC.
- (9.6) Every level above `-O0` uses the decoupled allocator.
- (9.7) Only `-O0` and `-O2` are gated. The other levels are reported ([perf.when]).

## 10 Block layout and machine-level additions [opt.layout]

1 `layout` is the last FIR pass, at `-O1` and above. MIR keeps the order it sets ([codegen.pipeline]).

- (1.1) *Static branch probabilities* (`-fguess-branch-probability`) come from `__builtin_expect`; paths that reach `cold` or `noreturn` calls, which are unlikely; loop back-edges, which are likely; and Ball–Larus heuristics.
- (1.2) *Placement* is Pettis–Hansen chain merging at `-O2` (`-freorder-blocks-algorithm=stc`), and the simple algorithm at `-O1` and `-Os`. Cold blocks go to the function's end. Nothing is split into `.text.unlikely` until profile data exists.

2 *Sibling calls* (`-foptimize-sibling-calls`, `-O2`). A pass marks a FIR call `tail` where that is legal, meaning there are no stack arguments beyond the caller's own incoming area and no locals that escape. The target's call lowering then emits `b` instead of `bl` ([codegen.isel]).

3 *Whole-prologue shrink-wrapping* (`-fshrink-wrap`, `-O1` and above) belongs to frame lowering ([codegen.frame]). The frame record, the callee-saved `STP`/`LDP` and the stack adjustment move to the nearest points that dominate and post-dominate every block that needs them. `-fshrink-wrap-separate` (per-register placement) is accepted and does nothing until a benchmark shows it pays.

4 A redundant-load pass joins the MIR pipeline at `-O3` ([codegen.pipeline]). There is still no instruction scheduler, and `-fschedule-insns` and `-fschedule-insns2` are unmapped. `LDP`/`STP` pairing and the peepholes keep the "`-O1` and above" level.

## 11 Flags and attributes [opt.flags]

1 *Flags that change what code means* are honoured:

- (1.1) `-fwrapv` and `-fno-strict-overflow`: the shared lowering omits `nsw`;
- (1.2) `-fno-delete-null-pointer-checks`: no null check is folded away on the assumption that a pointer was already dereferenced or marked `nonnull`;
- (1.3) `-fno-builtin`, `-fno-builtin-<fn>` and `-ffreestanding`: no libcall rules, and no libcall knowledge in alias analysis;
- (1.4) `-ffp-contract`, with GCC's defaults: `fast` in GNU dialects and `off` in ISO ones. The selection rules form `fmadd` where contraction is allowed.

2 *The floating-point mode is per function.* `-fmath-errno` and the `-ffast-math` family set it. Inlining between functions with different modes is refused, as in GCC.

3 *Attributes.*

- (3.1) `always_inline`, `noinline`, `noipa`, `flatten`, `cold` and `hot` steer the inliner and layout. A failed `always_inline` is an error at every level, `-O0` included.
- (3.2) `pure`, `const`, `malloc`, `nonnull`, `returns_nonnull` and `alloc_size` are facts for alias analysis and the simplifier.
- (3.3) `optimize("O0")` runs that function's pipeline at `-O0`. Other `optimize` strings, and `#pragma GCC optimize`, are ignored with a warning, as clang does, under `-Wattributes` ([compat.status]).

## 12 Verification [opt.verify]

1 A *FIR reference interpreter* shall execute self-contained FIR with poison semantics. External calls are limited to a small built-in set. It is the oracle for:

- (1.1) pass tests, where a pass's output must compute the same results as its input on generated inputs;
- (1.2) FIR-level fuzzing, on random valid FIR through any pass list;
- (1.3) the nightly Csmith and YARPGen runs, where Forge's `-O2` output must agree with GCC's.

2 The `-O2` stage check covers large real code ([opt.milestone]). This milestone is the trigger for fuzzing, which the CI design deferred.

3 SMT proofs of the `fir.simplify` rules, as Alive2 does for LLVM, are deferred. Their trigger is the first miscompile traced to a rule.

4 When `-O2` arrives, glibc's `__OPTIMIZE__`-only header code arrives with it: the `__USE_EXTERN_INLINES` bodies and, under Ubuntu's `_FORTIFY_SOURCE=3`, 734 lines of fortify wrappers. They use `__builtin_constant_p`, `__builtin_object_size`, `__builtin_dynamic_object_size` and `__builtin___*_chk` (census Part C, [m1.census]).

## Annex A (informative): Rationale and departures [opt.rationale]

1 *Mirroring GCC's levels.* The user overrode two recommendations, both toward GCC: that the levels mirror GCC 15.2's, and that all of `-O3` is built (vectorization aside). Shrink-wrapping was added to the scope.

2 *Pass manager.* Go's SSA backend (the `passes` table in `compile.go`) and Cranelift work this way. It departs from LLVM's new pass manager, whose adaptors, proxies and public pipeline-string language exist for plugins and out-of-tree pipelines; Forge has a closed set of passes and no plugins. It also departs from GCC's `passes.def`, where the properties each pass requires and provides, and its TODO flags, are implicit contracts between passes.

3 *Analyses.* This departs from LLVM's open, type-erased `AnalysisManager` with proxies and invalidation callbacks, which exists for plugins. It departs from GCC, which keeps dominators and loops current by convention (`loops_state`, TODO flags), a classic source of stale-analysis bugs.

4 *Module scheduling.* LLVM interleaves inlining and simplification the same way, but through a general CGSCC pass manager, which must update the call graph while passes change it; Forge has one hard-coded driver. GCC splits an early inliner from an IPA inliner that works on summaries built for LTO streaming; Forge has no LTO yet.

5 *The simplifier.* GCC's `match.pd` is one DSL that generates both its GIMPLE and GENERIC folders, and Cranelift's mid-end rewrites are written in ISLE. This departs from LLVM's InstCombine, which is tens of thousands of lines of hand-written C++ that Alive2 keeps finding miscompiles in.

6 *Few broad passes.* LLVM's `-O2` runs about 90 pass instances, InstCombine among them several times. GCC's runs more than 200. Forge relies on a few broad passes instead.

7 *Layout.* This departs from LLVM's MachineBlockPlacement, which runs on machine IR after selection.

8 *Floating-point mode per function.* This departs from LLVM's per-instruction fast-math flags. C and C++ set these modes per translation unit, and GCC ignores the block-scoped `#pragma STDC FP_CONTRACT` too. Ignoring `#pragma GCC optimize` follows clang; GCC's own manual says the attribute is meant for debugging.

9 *Type-based alias analysis.* MSVC has never done it.

## Annex B (informative): Provenance [opt.prov]

1 [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12). Inputs it was resolved against: [IR design](https://github.com/jmuratov98/forge/issues/5), [Performance budget and measurement](https://github.com/jmuratov98/forge/issues/7), [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11) and [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10).
