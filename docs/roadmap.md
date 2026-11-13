# Forge toolchain architecture roadmap

Status: draft, 2026-11-13. Stable-name prefix: `[roadmap]`.

This document is the index of Forge's architecture specifications. It was assembled from the closed decision tickets of the wayfinder map [Forge toolchain architecture roadmap](https://github.com/jmuratov98/forge/issues/1). It records decisions; it adds none. Where a later ticket refined an earlier one, this document set states the refined rule (see [roadmap.supersede]).

## 1 Scope [roadmap.scope]

1 This document set specifies the architecture of the Forge toolchain, down to the first buildable vertical slice (milestone 1, [m1]). It contains the component inventory, the boundaries and interfaces between components, the cross-cutting decisions (IR, diagnostics, target and platform model, ABI strategy, performance budget) and an ordered milestone plan.

2 No compiler code is written under this roadmap. A requirement stated with "shall" binds the implementation that follows; a requirement tied to a milestone binds from that milestone.

3 Terms in *italics on first use* are defined in `GLOSSARY.md` at the repository root. The stable-name prefix of each document is given in [roadmap.index].

4 Clauses and annexes marked *(informative)* carry rationale, prior art and provenance. They bind no one.

## 2 Goals [roadmap.goals]

1 Forge is a C++20 toolchain: a C compiler and a C++ compiler, an assembler (`fas`), a linker (`fold`), binary utilities, a C library (`flibc`), a C++ library (`flibc++`), the `fcc` and `f++` drivers, a debugger, a debug server, a formatter and a linter.

2 Forge shall:

- (2.1) compile itself (bootstrap);
- (2.2) be a drop-in replacement for GCC 15.2 ([compat]), and understand GCC's extensions;
- (2.3) run on Windows, macOS and Linux, in the order the target rollout sets ([roadmap.fog]);
- (2.4) stay within the performance budget of [perf.budget]: a geometric-mean cost ratio of at most 1.2 against the reference compilers, with no benchmark above 1.5.

3 Design rule. Forge does not copy LLVM, GCC or Rust blindly. Each decision modelled on one of them shall say whether it copies or departs, and a departure shall give its reason. The *(informative)* rationale annex of each specification records this.

4 MSVC compatibility, the forge language, the debugger, the formatter, the linter and the C and C++ libraries are outside this roadmap ([roadmap.scope.out]).

## 3 Milestones [roadmap.milestones]

1 The milestones are ordered. A milestone needs only the subset of each language revision and each component that its own gates require ([front.order]).

### 3.1 Milestone 1: the C vertical slice [roadmap.m1]

1 `fcc` and `fcc1`, built by GCC or clang, compile C for `aarch64-unknown-linux-gnu`. Codegen writes assembly through the assembly printer; GNU `as` assembles it and GNU `ld` links it.

2 Milestone 1 is done when every gate of [m1.gates] is green on `main` and the milestone-end runtime check of [perf.measure.runtime] passes. The full definition is [m1].

### 3.2 Milestone 2: the bootstrap [roadmap.m2]

1 Forge, built by clang or GCC as *stage0*, compiles itself to *stage1* with `fcc1plus`. Stage1 compiles itself to *stage2*. Stage1 and stage2 shall be byte-identical: every object file and every linked executable, built from identical source paths.

2 Stage0 is built twice, once by GCC 15.2 and once by the image's clang. The two stage1s shall be byte-identical.

3 Milestone 2 covers one host platform and the C++ subset Forge itself uses. That subset is C++98 to C++20 features, built with `-fno-exceptions` and `-fno-rtti`. `thread_local` is allowed only on trivially constructed and destroyed types. It brings:

- (3.1) the Itanium C++ ABI with ARM's AArch64 deviations, libstdc++ and the C++20 header surface of [targets.m2];
- (3.2) the `-O0` compile-time budget for Forge's own source with `fcc1plus` against g++ ([perf.when]);
- (3.3) the C++ template context and the speculative capture scope of [diag].

4 Forge's own source uses neither exceptions, RTTI, DWARF nor non-trivial `thread_local`. Bootstrap stages build without `-g`. Every function keeps an `x29`/`x30` frame record, so backtraces work without unwind tables. A stage1 miscompile is found by swapping stage0 and stage1 objects and bisecting.

### 3.3 Milestone 3: the optimizer [roadmap.m3]

1 Milestone 3 follows the bootstrap and precedes the second target and `fas`/`fold`. It brings the `-O1`, `-O2`, `-O3`, `-Os`, `-Oz`, `-Og` and `-Ofast` pipelines ([opt]), the decoupled register allocator ([codegen.regalloc]), and the `-O2` compile-time and runtime gates, together with stage1's own speed ([perf.when]).

2 The stage check runs again at `-O2`: stage2 and stage3, each built by Forge at `-O2`, shall be byte-identical.

3 Milestone 3 also brings:

- (3.1) the hardening defaults of [compat.hardening];
- (3.2) optimization remarks (`-fopt-info`) and inlined-call-site pragma checks ([diag]);
- (3.3) fuzzing, which the CI design had deferred ([opt.verify]);
- (3.4) shrink-wrapping and the other machine-level additions of [opt.layout].

4 The optimizer is built and tuned on aarch64 alone; it works on FIR, which does not depend on the target.

### 3.4 After milestone 3 [roadmap.later]

1 The order of later work is in the fog ([roadmap.fog]): the second target, `fas` with the object writer, `fold`, the binary utilities, `flibc` and `flibc++`.

## 4 Components [roadmap.components]

1 *Executables* ([pipe.exe]):

| Executable | Role | Arrives |
|---|---|---|
| `fcc`, `f++` | The *driver*: one binary, two names. Plans and spawns *jobs*. | Milestone 1 |
| `fcc1` | C *compiler executable*. Links only the C frontend. | Milestone 1 |
| `fcc1plus` | C++ compiler executable. Links only the C++ frontend. | Milestone 2 |
| `fas` | Assembler. | Fully-self-hosted ordering |
| `fold` | Linker. One linking core per object format. | Fully-self-hosted ordering |
| `ar`, `nm`, `objdump`, `objcopy`, `strip`, a readelf equivalent, a symbolizer | Binary utilities: thin executables over the *object readers* and the *ISA module*. | Fully-self-hosted ordering |

2 *Libraries.* Every component below is a library under a thin `main`, and holds no mutable global state ([roadmap.rules]):

| Library | Specified in |
|---|---|
| Source manager; diagnostics engine | [diag] |
| Lexer and preprocessor (one library, with a raw lexing mode) | [front.shape] |
| C-family core | [front.core] |
| C frontend; C++ frontend (parser, AST, sema, AST → HIR emitter each) | [front] |
| HIR; shared HIR → FIR lowering; FIR | [ir] |
| Optimizer: pass manager, analyses, simplifier, FIR interpreter | [opt] |
| Target modules: ABI interface, ISA module, selection rules, MIR, allocators, frame lowering | [targets], [codegen] |
| Machine-code stream, assembly printer, object writer | [pipe.emit] |
| Object readers (per format) | [pipe.objects] |
| Build-time generator tool (ISA description, rules compiler, option parser, tables) | [codegen.isa.gen], [compat.tracking] |
| Resource headers | [pipe.resource] |

## 5 Seams [roadmap.seams]

1 A seam is real once a second adapter exists behind it. More callers give a module leverage; they do not make its seam real.

2 The seams, with the interface behind each and the milestone at which it becomes real:

| Seam | Interface | Adapters | Becomes real |
|---|---|---|---|
| Driver → compiler job | Resolved command line, exit status | `fcc1`, then `fcc1plus` | Milestone 2 |
| Frontend → IR | HIR builder API, plus HIR text | C, then C++ | Milestone 2 |
| Target interface | One per target | aarch64, then the second target | Second target |
| ABI interface | Type description in, classification out; called by the shared lowering | aarch64 | Second target |
| Register allocator | SSA MIR in, allocated MIR out | Local (`-O0`), decoupled | Milestone 3 |
| Machine-code stream | Sections, labels, instructions, data, directives | Assembly printer, then object writer | When `fas` lands |
| Object writer → serializer | Format-neutral sections, fixups, symbols | ELF | First non-ELF target |
| Object readers | Zero-copy per-format views | ELF | First non-ELF target (shared by `fold`, the utilities and the debugger) |
| ISA module | Encode, decode, print, parse | aarch64 | Second target (shared by codegen, `fas`, `fold` and the disassembler) |
| Linker input | ELF `.o` and `.a` on disk, `ld` command line | GNU ld, then `fold` | When `fold` lands |
| Host layout table | One entry per target and distro layout | Ubuntu 26.04 aarch64 | Second layout |

3 [Note 1: The preprocessor and the C-family core each have one implementation and two callers. By paragraph 1 they have leverage but no seam. The optimizer's pass tables and analyses are closed sets with one implementation each, and are not seams either. — end note]

## 6 Cross-cutting rules [roadmap.rules]

1 *No mutable globals.* Every library holds all state in a per-compile context: no global options and no mutable static registries. The toolchain still runs as separate processes, so the libraries stay reusable by the linter, formatter, debugger and later in-process use.

2 *One option language.* A compile job's command line uses the driver's own flag spellings, fully resolved. One option table defines both sides ([pipe.driver], [compat.tracking]).

3 *Missing features are reported, never skipped.* A feature that a dialect enables, or a flag or extension that a table lists, but that is not yet implemented, raises one *not-yet-supported error* naming the feature. A silent fallback is ill-formed ([front.defaults], [compat.status]).

4 *Determinism.* Compiler output and diagnostic output shall be byte-identical for identical inputs, flags and spelled paths, across runs, working directories, temp directories and host compilers. No temp-file path reaches an object file. No pass iterates in an order that depends on a pointer value, a hash or a thread ([m1.gates], [diag.determinism], [opt.milestone]).

5 *Dense arenas.* AST, HIR, FIR and MIR store entities in per-function dense tables addressed by 32-bit *handles*. Types and constants are interned once per module in append-only tables. There are no persistent use-lists ([ir.layout], [front.ast]).

6 *Build-time generation.* Generated C++ is never committed. Generators are one host tool, run at build time, with byte-deterministic output. Committed sources of generation are fixed-schema text tables ([codegen.isa.gen], [compat.tracking]).

7 *Tests.* Tests use lit, FileCheck and GoogleTest. Diagnostics are tested with `-verify`, matching a stable kebab-case ID and an exact line and column. A test skip names the missing feature, and the harness checks that the compiler stops with the not-yet-supported error that names it ([m1.skips]).

8 *No Python tooling.* The generators of paragraph 6 are one in-tree C++ host tool ([compat.tracking]).

## 7 Document index [roadmap.index]

| Document | Prefix | Contents |
|---|---|---|
| [m1](milestone-1.md) | `[m1]` | The milestone-1 handoff: dialect, gates, skips, CI tiers, definition of done |
| [pipe](pipeline.md) | `[pipe]` | Executables, driver and jobs, resource headers, emission, object-file code, linking |
| [targets](targets.md) | `[targets]` | Target matrix, ABI strategy, bootstrap host |
| [ir](ir.md) | `[ir]` | HIR, FIR, the shared lowering, layout and text forms |
| [front](frontend.md) | `[front]` | Frontends, the C-family core, dialects, order, AST |
| [codegen](codegen.md) | `[codegen]` | MIR, instruction selection, register allocation, ISA description |
| [opt](optimizer.md) | `[opt]` | Pass manager, analyses, pipelines, flag map, verification |
| [compat](compat.md) | `[compat]` | The drop-in surface: identity, flag and extension tables, tiers |
| [diag](diagnostics.md) | `[diag]` | The diagnostics model, engine, styles, SARIF, fix-its |
| [perf](performance.md) | `[perf]` | The budget, reference compilers, measurement, suite, gates |

2 Reading order for an implementation session starting milestone 1: [m1], [pipe], [targets], [ir], [front], [codegen], [compat], [diag], [perf]. [opt] binds from milestone 3.

## 8 Not yet specified [roadmap.fog]

1 These are in scope but not yet sharp enough to decide. Each becomes a decision ticket when the frontier reaches it.

- (1.1) Linker (`fold`) internals, relocation and symbol resolution.
- (1.2) In-memory handoff to `fold`, and incremental relinking.
- (1.3) Debug-info (DWARF and CodeView) emission, including which passes `-Og` keeps ([opt.levels]).
- (1.4) LTO, including a binary FIR format.
- (1.5) Exception unwinding and coroutines in HIR and FIR, once they arrive after the bootstrap.
- (1.6) Templates and constexpr evaluation, including which C++ function bodies outlive HIR emission.
- (1.7) C++ modules and precompiled headers (both need AST serialization).
- (1.8) Vectorization: FIR vector types, the loop and SLP vectorizers, NEON and later SVE selection, `-fvect-cost-model` and `-fversion-loops-for-strides`, and which milestone brings them. Until then the `-O2` runtime gate runs the reference compilers with vectorization off ([perf.reference]).
- (1.9) Type-based alias analysis, once a budget benchmark misses without it.
- (1.10) Profile-guided optimization (`-fprofile-generate`, `-fprofile-use`, AutoFDO), including hot/cold splitting into `.text.unlikely`.
- (1.11) Fully self-hosted toolchain ordering: when `fas` with the object writer, `fold`, the binary utilities, `flibc` and `flibc++` arrive.
- (1.12) Target rollout after the optimizer: which target comes second (x86-64 Linux, arm64 macOS, ...) and the order of the rest. This includes each new host's performance budget (its reference compiler, Apple clang, MSVC or clang-cl, and where its gate runs) and each new target's ISA source. Intel XED's Apache-2.0 datafiles are the candidate import for x86-64.
- (1.13) How Forge consumes the separate C/C++ standards repository.

## 9 Out of scope [roadmap.scope.out]

1 Each of these gets its own map later, or lies beyond this roadmap's destination. None returns here except by redrawing the destination.

- (1.1) `flibc` and `flibc++`.
- (1.2) The debugger and the debug server.
- (1.3) The formatter and the linter.
- (1.4) MSVC-compat mode.
- (1.5) Nova OS support.
- (1.6) The standards repository itself (a separate repository).
- (1.7) The forge language's frontend. It emits HIR and reuses the source manager and diagnostics, but not the C-family lexer or preprocessor.
- (1.8) Objective-C and Objective-C++ (Apple's SDK headers guard their Objective-C parts with `__OBJC__`).
- (1.9) Working-draft revisions (C2y, C++29): only once published. The revision range ends at C23 and C++26.

## 10 Prior specifications not in this checkout [roadmap.prior]

1 These documents are referenced by the decisions assembled here, but are not in this checkout, so an implementation session meets the gap. They are not recreated by this roadmap and shall be re-landed or re-derived before the component that depends on them:

- (1.1) stack traces and crash context (the crash report of [diag.crash] follows them);
- (1.2) the version specification (`VERSION`, timestamp, SemVer; the source of `__forge_major__` and the banner of [compat.identity]);
- (1.3) the file-system layer (`sys::fs`, `sys::path`, memory buffers with 64 bytes of padding, for SIMD lexing);
- (1.4) the error model (`forge::error`, which replaces `std::error_code` everywhere);
- (1.5) the testing strategy (`-verify` and the `catalog.test` of [diag.catalog]);
- (1.6) the CI design ([m1.ci], [perf.ci] add to it);
- (1.7) the `./x` tooling and the code-style decisions.

## Annex A (informative): Supersession record [roadmap.supersede]

1 Several decisions were refined by later tickets. This table lists each earlier statement, the rule now in force, and where it is specified. A reader of the ticket history should consult it.

| Earlier statement | Now | Specified in |
|---|---|---|
| Milestone 2 adds the second target (target matrix) | The optimizer is milestone 3; the second target follows it; order beyond that is fog | [roadmap.m3] |
| Milestone 1 is the C++ bootstrap (map before 2026-11-09) | Milestone 1 is a C slice; the bootstrap is milestone 2 | [roadmap.milestones] |
| No `long double`, no `__int128` (target matrix, from Forge's own source) | `long double` is IEEE binary128 and `__int128` is complete, in milestone 1 | [m1.types] |
| No `-fPIC` codegen; no symbol visibility; no symbol preemption (target matrix, C slice) | `-fPIC` and `-fpic` codegen is in milestone 1: preemptible definitions go through the GOT and TLS uses descriptors. `-fvisibility` is ignored, because going through the GOT is always correct. `-shared` is still not-yet-supported | [compat.pic], [compat.status] |
| The stage0 gcc/clang identity check belongs to the bootstrap | A `.s` identity check between a GCC-built and a clang-built `fcc` runs from milestone 1; the stage1 identity check remains in milestone 2 | [m1.gates], [roadmap.m2] |
| Every frontend calls the ABI interface (pipeline) | The shared HIR → FIR lowering calls it; frontends describe types in HIR | [ir.lowering] |
| `-O0` runs no passes (IR design) | `-O0` runs one pass: the `always_inline` inliner | [opt.module] |
| Every function has an `x29`/`x30` frame record (machine IR) | At `-O0`, every function. At `-O1` and above, the frame record is shrink-wrapped to the paths that need a frame | [opt.layout] |
| `-O2` runtime compared with the faster of GCC and clang (budget) | The reference compilers run with vectorization off until Forge vectorizes | [perf.reference] |
| `__signed__` is ignorable (C++ header inventory) | Must be implemented, in both languages; `__inline` too, in C | [compat.extensions] |
| "Machine IR" and "IR design" each define MIR | One definition: the ISA module's instructions plus generic pseudos, in SSA until allocation | [codegen.mir], GLOSSARY.md |
| Stack protector, stack-clash protection and `-mbranch-protection=standard` are Ubuntu defaults | Not Forge's defaults; the opt-out forms are no-ops, the enabling forms are not-yet-supported until milestone 3 | [compat.hardening] |

## Annex B (informative): Provenance [roadmap.prov]

1 Source tickets (each resolution comment is the record of its decision):

- [Milestone-1 target matrix](https://github.com/jmuratov98/forge/issues/2)
- [ABI and object-format inventory](https://github.com/jmuratov98/forge/issues/3)
- [Pipeline shape and component boundaries](https://github.com/jmuratov98/forge/issues/4)
- [IR design](https://github.com/jmuratov98/forge/issues/5)
- [Frontend strategy](https://github.com/jmuratov98/forge/issues/6)
- [Performance budget and measurement](https://github.com/jmuratov98/forge/issues/7)
- [Drop-in compatibility surface](https://github.com/jmuratov98/forge/issues/8)
- [Host header extension inventory](https://github.com/jmuratov98/forge/issues/9)
- [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10)
- [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11)
- [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12)
- [C-mode host header extension inventory](https://github.com/jmuratov98/forge/issues/13)
- [Diagnostics model, formats and fix-its](https://github.com/jmuratov98/forge/issues/14)

2 Research findings live on throwaway branches that are never merged. Cite a branch with its commit:

| Branch | Commit | Contents |
|---|---|---|
| `research/abi-format-inventory` | 40790c6 | Per-spec compiler, assembler and linker demands for SysV x86-64, AAPCS64, Apple arm64, Itanium, ELF, Mach-O, PE/COFF and DWARF; no Microsoft C++ ABI specification exists |
| `research/host-header-extensions` | 7c6166f | C++20 header extension inventory (670 names). GCC was not run |
| `research/c-budget-suite-census` | 3fbb812 | llvm-test-suite at `2ecf20c2`, GCC's `releases/gcc-15` torture tests at `7b7cd17e`, libc6-dev 2.43-2ubuntu2.4 |
| `research/c-host-header-extensions` | 300bbd7 | C-mode header extension inventory (165 names), run on real GCC 15.2 |
| `research/gcc-diagnostics` | d68e11c | GCC 15.2 diagnostic formats, consumer regexes, pragma semantics, `-fopt-info` |

3 [Note 1: The C++ header inventory was produced without running GCC. A `g++ -E` and `clang++ -E` re-check in the pinned Ubuntu 26.04 bootstrap image, once it exists, would close its first known unknowns. — end note]
