# How production compilers layer their IRs

Research for issue #3. It feeds the decision on Forge's IR layers. The candidate stack
HIR → FIR → SelectionDAG → MIR → MCIR is still an open hypothesis. This file reports facts and
trade-offs. It does not make the decision.

Forge's targets set the context: compile time ≤1.25× gcc/clang, generated code ≤1.25× slower
at -O2, and an HIR that is language-independent (C, C++, the Forge language).

Each section below cites its sources. Measurements marked **[measured]** were taken for this
note on an Apple M4 (macOS 15) with Homebrew clang 23.1.4 and Homebrew gcc 16.1.0, compiling the
SQLite 3.50.4 amalgamation (`sqlite3.c`, 9.3 MB of C). They cover one input on one machine, so
treat them as indicative only. Raw `-ftime-report` output was not committed.

---

## 1. Summary table

| System | Layers, frontend → object | Where SSA starts / ends | Instruction selection | Register allocation | Machine code out |
|---|---|---|---|---|---|
| **LLVM / clang** | Clang AST → LLVM IR → (SelectionDAG \| FastISel \| GlobalISel gMIR) → MIR → MC (MCInst/MCStreamer) | LLVM IR is SSA. MIR is SSA until regalloc. SelectionDAG is a per-block DAG. | SelectionDAG: a separate per-basic-block DAG IR. GlobalISel: in place on MIR, whole function. | On MIR (Greedy at -O2, Fast at -O0) | MC layer, shared with the integrated assembler |
| **GCC** | Frontend trees (GENERIC) → GIMPLE (high → low → SSA) → RTL → assembly text | GIMPLE SSA through the tree passes. RTL is not SSA (pseudo-registers), with an optional "RTL-SSA" view on the side. | Spread across RTL: `expand` picks named `.md` patterns, `combine` re-matches against the machine description | IRA + LRA, on RTL | `final` prints `.s` text, then an external `as` assembles it |
| **Cranelift** | CLIF → (e-graph mid-end, still CLIF) → VCode → bytes via MachBuffer | CLIF is SSA (block params). VCode vregs are SSA for regalloc2. | ISLE rules lower CLIF → VCode in one pass. There is no DAG. | regalloc2 (backtracking "Ion", or "Fastalloc") over VCode | Direct binary emission, no assembler IR |
| **Go (gc)** | syntax AST → types2 → IR (unified IR) → walk → SSA (generic) → SSA (lowered) → obj.Prog → object | One SSA IR from building through regalloc | The `lower` pass rewrites generic ops to machine ops on the **same** SSA IR, using `.rules` rewrite rules | Linear-scan-style greedy allocator on the SSA IR | `cmd/internal/obj` (also Go's assembler backend) |
| **Rust (rustc)** | AST → HIR → THIR → MIR → LLVM IR (or CLIF, or GCC GIMPLE via `rustc_codegen_gcc`) | MIR is **not** SSA (mutable locals and places). SSA starts in the backend IR. | Delegated to the backend | Delegated to the backend | Delegated to the backend |
| **MLIR** | Any number of dialects, progressively lowered → LLVM dialect → LLVM IR → LLVM codegen | SSA with regions and block arguments (no phi) | None of its own for CPUs. It reuses LLVM codegen. | LLVM | LLVM |
| **QBE** | One IL for the whole pipeline: parse → SSA build → opts → isel → spill → regalloc → emit | Accepts non-SSA input and builds SSA itself | `T.isel` pass, in place on the same IL | `spill` + `rega` (linear, with hinting) on the same IL | Assembly text only, needing an external `as` |
| **Zig (self-hosted)** | AST → ZIR (per file, untyped) → AIR (per function, typed) → backend MIR (per arch, 1:1 with machine instructions) → bytes | ZIR and AIR are value-numbered instruction lists with structured control flow (`block`/`loop`/`br`), no phi | Done while walking AIR in `CodeGen.zig`, emitting MIR directly | On the fly in the same walk (`RegisterManager` + AIR `Liveness`) | `Emit.zig`/`Lower.zig` encode MIR. The LLVM backend is used for release builds. |

---

## 2. LLVM (clang)

**Layers and purposes**

- **LLVM IR** is the language-independent, target-independent SSA IR on which the middle end
  (`opt` pipeline) runs.
- **Instruction selection** turns LLVM IR into target instructions on virtual registers in SSA
  form. The Code Generator doc gives the order: instruction selection → scheduling and formation →
  SSA-based machine-code optimisations → register allocation → prolog/epilog insertion → late
  machine-code optimisations → code emission.
  [LLVM Code Generator](https://llvm.org/docs/CodeGenerator.html)
- **SelectionDAG** is its own IR: a DAG of `SDNode`s with value edges and chain edges. Its
  sub-phases are: build the initial DAG → combine → legalize types → combine → legalize ops →
  combine → select (patterns generated from TableGen `.td` files) → schedule and form
  MachineInstrs. [LLVM Code Generator](https://llvm.org/docs/CodeGenerator.html)
- **MIR** (MachineInstr / MachineBasicBlock / MachineFunction): "MachineInstr's are initially
  selected in SSA-form, and are maintained in SSA-form until register allocation happens."
  [LLVM Code Generator](https://llvm.org/docs/CodeGenerator.html)
- **MC layer** (`MCInst`, `MCStreamer`, `MCContext`, `MCSection`): the object-level
  representation. `MCInst` is shared by encoding, printing, *and* the assembly parser, so the
  compiler and the integrated assembler share one layer.
  [LLVM Code Generator](https://llvm.org/docs/CodeGenerator.html)

**Three instruction selectors**

- **SelectionDAG**: the default at -O1 and above on most targets. It works on one basic block at a
  time.
- **FastISel**: the -O0 path on x86. It falls back to SelectionDAG for anything it cannot handle.
- **GlobalISel**: translates LLVM IR straight to *generic* MIR (gMIR). Its pipeline is
  IRTranslator → Legalizer → RegBankSelect → InstructionSelect, with combiners in between. It is
  the AArch64 -O0 default (since 2018 per Apple) and is being brought up for optimised builds. Its
  stated motivation is: "SelectionDAG introduces a dedicated intermediate representation, which has
  a compile-time cost." GlobalISel instead "directly operates on the post-isel representation used
  by the rest of the code generator, MIR". Second, "SelectionDAG and FastISel operate on
  individual basic blocks, losing some global optimization opportunities". Third, SelectionDAG and
  FastISel "share very little code". Its compile-time goal against FastISel at -O0 was "within
  1.5x", with "1.1/1.2x" as the optimistic target.
  [GlobalISel](https://llvm.org/docs/GlobalISel/index.html)

**Compile-time cost of each layer**

- Apple (LLVM Dev Mtg 2021) measured GlobalISel against SelectionDAG on AArch64. Overall compile
  time was 6.1% better (geomean, CTMark -Os). Isolating instruction selection on sqlite3 -Os,
  SelectionDAG took 0.864 s and GlobalISel 0.314 s ("2.7x faster"), with DAGCombine the largest
  SelectionDAG component. The runtime cost was a geomean regression against SelectionDAG of 0.2%
  (SPEC2006 INT) and 0.76% (FP) on trunk at the time.
  [Apple, "Bringing up GlobalISel for optimized AArch64 codegen"](https://llvm.org/devmtg/2021-11/slides/2021-BringingupGlobalISelForOptimizedaarch64codegen.pdf)
- **[measured]** `clang -O2 -c sqlite3.c`, using `-ftime-report` top-level buckets:

  | Target | Front end | LLVM IR gen | Optimizer | Machine code gen | Wall (no `-ftime-report`) |
  |---|---|---|---|---|---|
  | AArch64 -O2 | 2.1% | 1.1% | 45.1% | 51.8% | 5.1 s |
  | x86-64 -O2 | 2.1% | 1.0% | 46.3% | 50.6% | 5.0 s |
  | AArch64 -O0 | 16.3% | 6.9% | 1.5% | 75.2% | 0.47 s |
  | x86-64 -O0 | 20.1% | 7.6% | 2.0% | 70.3% | 0.35 s |

  The heaviest individual pass at -O2 is SelectionDAG instruction selection: 18.4% of all pass
  time on AArch64 and 19.9% on x86-64. That is more than InstCombine (about 8%) or Greedy RA (7–9%).
  At AArch64 -O0, the GlobalISel passes (IRTranslator, Legalizer, RegBankSelect,
  InstructionSelect, Localizer, and the two combiners) together take about 53% of pass time. At
  x86-64 -O0, FastISel plus its SelectionDAG fallback ("X86 DAG->DAG Instruction Selection") takes
  about 31%.
- For C, the frontend is a small share of an -O2 build (about 2% here). The backend and the
  middle end split the rest roughly in half. C++ will shift weight toward the frontend. That was
  not measured here.

---

## 3. GCC

**Layers and purposes**

- **GENERIC**: "a language-independent way of representing an entire function in trees."
  [gccint: GENERIC](https://gcc.gnu.org/onlinedocs/gccint/GENERIC.html) In practice, "The C and C++
  front ends currently convert directly from front end trees to GIMPLE … rather than first
  converting to GENERIC." Their gimplifier hooks understand the frontend `_STMT` nodes.
  [gccint: GIMPLE](https://gcc.gnu.org/onlinedocs/gccint/GIMPLE.html)
- **GIMPLE**: "a three-address representation derived from GENERIC by breaking down GENERIC
  expressions into tuples of no more than 3 operands". Control structures are lowered to
  conditional jumps, and EH becomes an on-the-side region tree. **High GIMPLE** (before
  `pass_lower_cf`) keeps `GIMPLE_BIND`/`GIMPLE_TRY` containers. **Low GIMPLE** exposes all
  implicit jumps. [gccint: GIMPLE](https://gcc.gnu.org/onlinedocs/gccint/GIMPLE.html) GIMPLE serves
  "target and language independent optimizations".
  [gccint: Tree SSA](https://gcc.gnu.org/onlinedocs/gccint/Tree-SSA.html) The "Enter static single
  assignment form" pass (`pass_build_ssa`) runs right after CFG construction. About 40 tree-SSA
  passes follow it.
  [gccint: Tree SSA passes](https://gcc.gnu.org/onlinedocs/gccint/Tree-SSA-passes.html)
- **RTL**: "a low-level intermediate representation called Register Transfer Language", using
  pseudo-registers and not SSA. There is an opt-in "On-the-Side SSA Form for RTL" (`rtl-ssa/`)
  that individual passes can use. [gccint: RTL](https://gcc.gnu.org/onlinedocs/gccint/RTL.html),
  [gccint: RTL SSA](https://gcc.gnu.org/onlinedocs/gccint/RTL-SSA.html)

**Instruction selection and register allocation.** GCC has no single instruction-selection pass.
The machine-description overview describes three conversions: "The parse tree is used to
generate an RTL insn list based on named instruction patterns" (`expand`, which uses
`define_expand`/`define_insn` names). "Various optimization passes convert, replace, and rearrange
the insns". Then "the insn list's RTL is matched up with the RTL templates" to produce assembler.
[gccint: MD overview](https://gcc.gnu.org/onlinedocs/gccint/Overview.html) `combine` merges
2–3 insns and "match[es] the result against the machine description". Register allocation is IRA
(regional, integrated coalescing and splitting), followed by LRA, which replaces reload.
`final` writes assembly. [gccint: RTL passes](https://gcc.gnu.org/onlinedocs/gccint/RTL-passes.html)
The driver then runs an external `as` on the `.s` file. **[measured]** `gcc-16 -###` shows
`cc1 … ; as -arch arm64 … ccXXXX.s`.

**Compile-time cost (measured).** Times are `gcc-16 -ftime-report` on `sqlite3.c` (AArch64).

- -O2: 14.1 s wall, against clang's 5.1 s on the same file and machine. Parsing is 1% and
  "opt and generate" is 98%. The largest single items are IRA 6%, dominator opts 5%, df live
  regs 4%, and VRP, CSE, combine and jump threading at about 3% each. `expand` (GIMPLE → RTL) is 2%.
- -O0: 2.2 s wall, against clang's 0.47 s. IRA is 21% and LRA 9%. Together, register allocation
  is about 30% of cc1 time at -O0. `final` is 9%, `expand` 7% and gimplify 3%.
- Caveat: this is the Homebrew/iains Darwin port of GCC with Apple's external assembler. Linux
  x86-64 GCC may compare differently against clang.

---

## 4. Cranelift

**Layers**, quoting `cranelift/codegen/src/machinst/mod.rs`:
`ir::Function (SSA IR, machine-independent opcodes)` → `[lower]` → `VCode<arch::Inst>`
("mostly virtual registers", two-target branches, all edges split) → `[regalloc → regalloc2::Output;
VCode is unchanged]` → `[binary emission via MachBuffer]` → `Vec<u8>`. Prologues and epilogues are
"built and emitted directly during emission". Branches are resolved by "streaming branch
resolution/simplification".
[machinst/mod.rs](https://github.com/bytecodealliance/wasmtime/blob/main/cranelift/codegen/src/machinst/mod.rs)

- **CLIF** is SSA, with block parameters instead of phi. A mid-end e-graph optimiser runs
  CLIF → CLIF. Compared with the legacy passes, it gave "~16% runtime speedups on SpiderMonkey.wasm"
  with "compile times about the same".
  [Cranelift progress 2022](https://bytecodealliance.org/articles/cranelift-progress-2022)
- **Lowering / instruction selection** is "a _single pass_ over the CLIF instructions" into VCode.
  The 2020 redesign rejected a single IR for both levels in favour of "a two-level representation,
  connected by an explicit instruction selector". It favours arrays and single passes, for
  example 16-byte AArch64 `MachInst`s.
  [cfallin, "Cranelift ISel part 1"](https://cfallin.org/blog/2020/09/18/cranelift-isel-1/)
- **ISLE** is a DSL compiled to Rust. It expresses both the per-target lowering rules and the
  mid-end rewrites. It matches through value → defining-instruction links on SSA values, only
  where merging the producer is legal. No DAG or tree is reified.
  [cfallin, "ISLE"](https://cfallin.org/blog/2023/01/20/cranelift-isle/)
- **VCode SSA status**: the 2020 post says "VCode is _not_ SSA-based". The current regalloc2 API,
  however, states "A virtual register ('vreg') corresponds to an SSA value". It has an `SSA`
  validation error and two algorithms: Ion (backtracking) and Fastalloc.
  [regalloc2 lib.rs](https://github.com/bytecodealliance/regalloc2/blob/main/src/lib.rs)

**Compile-time cost**

- Cranelift compile time "was and is dominated by regalloc time". regalloc2 improved overall
  compile speed by about 20% and runtime by up to 10–20% in Wasmtime.
  [cfallin, "regalloc2"](https://cfallin.org/blog/2022/06/09/cranelift-regalloc2/)
- Against LLVM, in Rust debug builds of Cranelift itself, the backend took 125 CPU-s against
  LLVM's 211 (−40%), and wall time was 29.6 s against 37.5 s.
  [LWN, 2024](https://lwn.net/Articles/964735/) The Rust project goal for 2026 reports
  incremental Zed builds 5% faster (no debuginfo) or 12% faster (line tables). Across the rustc
  benchmark suite the gain averages 10–15%. The goal targets a further 2× inside the backend.
  [Rust project goal: improve cg_clif performance](https://goals.rust-lang.org/2026/improve-cg_clif-performance.html)
  End-to-end gains are small because rustc's frontend and MIR work dominate debug builds.
- LWN cites a 2020 paper finding Cranelift "an order of magnitude faster than LLVM" with code
  "approximately twice as slow on some benchmarks". This is secondary, via
  [LWN](https://lwn.net/Articles/964735/). The paper is
  [Xu & Kjolstad, Copy-and-Patch (OOPSLA 2021)](https://arxiv.org/abs/2011.13127).

---

## 5. Go (gc)

**Layers**, from [cmd/compile/README.md](https://github.com/golang/go/blob/master/src/cmd/compile/README.md):

1. syntax trees, then `types2` type checking.
2. "noding" into the middle end's own IR (`ir`, unified IR). The middle end runs inlining,
   devirtualisation and escape analysis on that IR.
3. `walk` "desugars higher-level Go constructs into more primitive ones".
4. SSA: "IR is converted into Static Single Assignment (SSA) form". Machine-independent passes run
   first. Then "the `lower` pass … converts the SSA representation from being machine-independent
   to being machine-dependent", replacing generic ops with arch ops through rewrite rules in
   `_gen/*.rules`. [ssa/README.md](https://github.com/golang/go/blob/master/src/cmd/compile/internal/ssa/README.md)
5. More passes, then register allocation, both still on the SSA IR. Then `obj.Prog` lists go to
   `cmd/internal/obj`, which "turns them into machine code and writes out the final object file".

Instruction selection is therefore a **rewrite pass on the same SSA data structure**. There is no
separate selection IR and no separate machine IR. The register allocator is "a version of a
linear scan register allocator. We treat the whole function as a single long basic block and run
through it using a greedy register allocator", with fix-up shuffles on merge edges and
farthest-next-use spilling.
[ssa/regalloc.go](https://github.com/golang/go/blob/master/src/cmd/compile/internal/ssa/regalloc.go)
The `obj` layer is shared with the Go assembler. That is the same sharing as LLVM's MC layer
between codegen and its integrated assembler.

---

## 6. Rust (rustc)

From the [rustc-dev-guide overview](https://rustc-dev-guide.rust-lang.org/overview.html):
token stream → **AST** ("pretty much exactly what the user wrote") → **HIR** (desugared AST,
"amenable to type checking") → **THIR** (fully typed and further desugared: method calls and
autoderef made explicit, bodies only, "only stored temporarily", freed after unsafety checking to
cap peak memory) [THIR](https://rustc-dev-guide.rust-lang.org/thir.html) → **MIR** → backend IR.

- **MIR** is a CFG of basic blocks with no nested expressions and fully explicit types. It is used
  for borrow checking, dataflow checks, optimisation, CTFE and codegen.
  [MIR](https://rustc-dev-guide.rust-lang.org/mir/index.html) MIR is one data structure with several
  dialects (Built → Analysis → Runtime) and phases. Each step "is technically a lowering from one
  IR to another" on the same `Body` type.
  [rustc_middle/src/mir/syntax.rs `MirPhase`](https://github.com/rust-lang/rust/blob/master/compiler/rustc_middle/src/mir/syntax.rs)
- MIR is **not SSA**. Locals are assigned through places. An analysis (`SsaLocals`) finds the
  locals that are "only assigned-to once" with the assignment dominating all uses.
  [rustc_mir_transform/src/ssa.rs](https://github.com/rust-lang/rust/blob/master/compiler/rustc_mir_transform/src/ssa.rs)
- Monomorphisation is collected at MIR level. MIR optimisations run *before* monomorphisation, so
  they run once per generic rather than once per instance. The guide notes that analyses on
  generic MIR are cheaper than after monomorphisation.
  [overview](https://rustc-dev-guide.rust-lang.org/overview.html)
- **Backend abstraction**: `rustc_codegen_ssa` lowers MIR generically through traits
  (`BuilderMethods`, …). About 4,400 lines are backend-agnostic, and LLVM, Cranelift and GCC
  implement the traits. "The traits offer an API which is very similar to the API of LLVM."
  [Backend-agnostic codegen](https://rustc-dev-guide.rust-lang.org/backend/backend-agnostic.html)
- Codegen is the only part of rustc that runs in parallel by default.
  [overview](https://rustc-dev-guide.rust-lang.org/overview.html)

Vocabulary caution: rustc's HIR is Rust-specific, not language-independent, and rustc's MIR is a
*mid-level* IR, unrelated to LLVM's *machine* IR.

---

## 7. MLIR (and the MLIR-based C/C++ and Fortran front ends)

- MLIR is a framework of **dialects** with "progressive lowering to target-specific forms". It is
  SSA with nested regions and **block arguments instead of phi**. Phi lists "can cause long compile
  time problems because transformations have to linearly scan this list". Types and attributes are
  uniqued and immortal in the context. Passes are cloned per thread so that functions can be
  compiled in parallel, which LLVM's global constant uniquing prevented.
  [MLIR Rationale](https://mlir.llvm.org/docs/Rationale/Rationale/),
  [Lattner et al., MLIR paper](https://arxiv.org/abs/2002.11054)
- MLIR has **no CPU instruction selector or register allocator**. CPU code goes through the LLVM
  dialect → LLVM IR → LLVM codegen, so each MLIR level adds a layer *above* LLVM IR.
- **Flang**: parse tree → **HLFIR** → **FIR** ("Fortran IR", an MLIR dialect) → LLVM dialect →
  LLVM IR. HLFIR was added above FIR because lowering expressions straight to FIR's buffered
  array ops grew too complex.
  [Flang HLFIR](https://flang.llvm.org/docs/HighLevelFIR.html)
- **ClangIR (CIR)** is an MLIR dialect for C/C++ that sits between the Clang AST and LLVM IR. It is
  being upstreamed (about 27% upstreamed as of June 2025).
  [ClangIR](https://llvm.github.io/clangir/) Its compile-time report (June 2025) measured
  slowdowns against classic clang codegen. At -O2, of 57 MultiSource files taking more than 0.5 s,
  30 were 20–30% slower, 20 were 10–20% slower and 7 were more than 30% slower. On CTMark the
  slowdown was +9–60% at -O2 and +89–192% at -O0. In one case (`clamr_cpuonly.cpp` -O0), classic
  CodeGen took 15 ms and the CIR pipeline 333 ms, with 289 ms of that in CIRGen
  `applyReplacements`. The author calls this "low hanging fruit".
  [ClangIR compile-time page](https://llvm.github.io/clangir/Development/compile-time.html),
  [slides](https://llvm.github.io/clangir/Files/asiallvm-brunolopes-25-cir-compile-time.pdf)

---

## 8. QBE

- The goal is "70% of the performance of industrial optimizing compilers in 10% of the code".
  QBE uses the "Same IL used at all compilation stages". Its optimisations are copy elimination,
  SCCP, dead-instruction elimination and registerisation of small stack slots, plus amd64
  addressing-mode matching and a "Linear register allocator with hinting". It claims "Super quick
  compile times". [QBE home](https://c9x.me/compile/)
- The IL is SSA, but "phi instructions are NOT necessary when writing a frontend to QBE … QBE is
  able to fixup programs not in SSA form". [QBE IL](https://c9x.me/compile/doc/il.html)
- The pass pipeline in `main.c` runs per function, all on one `Fn` structure:
  `abi0 → fillcfg → promote → ssa → ssacheck → fillalias → loadopt → coalesce → gvn → simplcfg → gcm
  → [ifconvert] → abi1 → simpl → isel → filllive/fillloop/fillcost → spill → rega → simpljmp → emitfn`.
  It then calls `freeall()` after each function.
  [qbe main.c](https://c9x.me/git/qbe.git/tree/main.c) The output is assembly text, so it needs an
  external assembler.

---

## 9. Zig (self-hosted backends)

- **ZIR**: "Astgen.zig converts AST nodes to these untyped IR instructions. Next, Sema.zig
  processes these into AIR". There is one ZIR per source file, enough to generate AIR "without any
  memory access into the AST tree token list, node list, or source bytes".
  [lib/std/zig/Zir.zig](https://github.com/ziglang/zig/blob/master/lib/std/zig/Zir.zig)
- **AIR**: "Analyzed Intermediate Representation … produced by Sema and consumed by codegen.
  Unlike ZIR where there is one instance for an entire source file, each function gets its own
  `Air` instance." It is stored as a `MultiArrayList` of instructions plus a `u32` extra array.
  Control flow is structured (`block`, `loop`/`repeat`, `br` with a result), with no phi.
  `Air/Legalize.zig` rewrites AIR to remove constructs that a backend's feature set cannot handle.
  `Air/Liveness.zig` feeds codegen. [src/Air.zig](https://github.com/ziglang/zig/blob/master/src/Air.zig)
- **Backend MIR** (x86_64): "These instructions have a 1:1 correspondence with machine code
  instructions … The main purpose of MIR is to postpone the assignment of offsets", for example to
  allow short jumps. `CodeGen.zig` walks AIR and allocates registers on the fly with a
  `RegisterManager` and AIR liveness while it emits MIR. `Lower.zig`/`Emit.zig` encode the
  result. [src/codegen/x86_64/Mir.zig](https://github.com/ziglang/zig/blob/master/src/codegen/x86_64/Mir.zig)
  The new aarch64 backend generates MIR in reverse after a two-pass liveness. That removes "the
  incredibly complex deferred value tracking from the x86_64 backend" and stores encodings in MIR
  so that encoding runs on the parallel codegen threads.
  [Zig devlog 2025](https://ziglang.org/devlog/2025/)
- **Compile-time cost**: Zig 0.15 makes the x86_64 backend the Debug default, giving "around a 5x
  decrease compared to LLVM in most cases". It passes 1984 of 2008 behaviour tests, against 1977
  for LLVM. [0.15.1 release notes](https://ziglang.org/download/0.15.1/release-notes.html) Building
  the Zig compiler dropped from 75 s to 20 s, and hello.zig from 918 ms to 275 ms. Parallel codegen
  (one Sema thread, N codegen threads) gave a further 5–50% wall-clock reduction. The LLVM backend
  "relies on shared state" and stays single-threaded.
  [Zig devlog 2025](https://ziglang.org/devlog/2025/) The self-hosted backends do not optimise.
  ReleaseFast and ReleaseSmall builds still use LLVM.

---

## 10. Adjacent data point: single-pass backends from an SSA IR

TPDE (Schwarz, Kamm, Engelke; CGO 2026) runs one analysis pass, then "instruction selection,
register allocation, and encoding" in a single pass straight from an existing SSA IR, with no
backend IR. Its LLVM-IR backend compiles "8–24x faster than LLVM -O0" with run-time performance
on par with -O0 on SPECint 2017. The authors argue that LLVM's extra IR translation step (IR →
SelectionDAG/MIR) is itself a source of latency.
[TPDE, arXiv:2505.22610](https://arxiv.org/abs/2505.22610) This matches -O0 code quality only. It
is not evidence about -O2.

---

## 11. Cross-cutting facts relevant to Forge's decision

These are observations, not recommendations.

1. **A language-independent, target-independent SSA mid-level IR is common to every optimising
   system here**: LLVM IR, GIMPLE-SSA, CLIF, Go SSA, QBE IL. Above it, most systems keep at least
   one **language-specific** IR: Clang AST, GCC frontend trees, Rust HIR/THIR/MIR, Go IR, Zig
   ZIR/AIR, Flang HLFIR, ClangIR. GCC's GENERIC is the one design that is explicitly a
   language-independent tree IR above the SSA IR. Even there, the C and C++ front ends bypass it
   and gimplify their own trees. Rust's language-specific MIR is where its borrow checking and
   pre-monomorphisation optimisation happen.
2. **Where instruction selection lives varies widely**:
   - LLVM SelectionDAG: a *separate per-block DAG IR*.
   - LLVM GlobalISel: in place on generic MIR, whole function.
   - GCC: spread across `expand` and `combine` on RTL.
   - Cranelift: a single ISLE-driven pass, CLIF → VCode.
   - Go and QBE: a rewrite pass on the *same* SSA IR.
   - Zig: fused with register allocation in one walk.

   Only LLVM's SelectionDAG uses a dedicated selection IR. LLVM's own GlobalISel docs cite that
   IR's "compile-time cost" and per-block scope as reasons to replace it.
3. **Where instruction selection costs the most**: SelectionDAG is the single most expensive pass
   in clang -O2 here (18–20% of pass time). In Apple's isolated measurement, GlobalISel was 2.7×
   faster at the selection step alone, but only 6% faster end to end, with small runtime
   regressions while it matured.
4. **Register allocation is the other big backend cost** in every system with data: Cranelift
   ("dominated by regalloc time"), GCC -O0 (IRA+LRA about 30% of cc1), clang -O2 (Greedy 7–9% of
   pass time). Faster systems (Go, QBE, Zig, TPDE) use linear-scan or on-the-fly allocators. LLVM
   (Greedy), GCC (IRA/LRA) and Cranelift (regalloc2 Ion) use more expensive allocators to produce
   better -O2 code.
5. **Machine IR → object**: LLVM (MC) and Go (`obj`) share one object-level layer between the
   compiler and the assembler. Cranelift and Zig encode bytes directly from their machine IR. GCC
   and QBE emit text and pay for an external assembler process. Forge owns its assembler (fas),
   so the LLVM/Go sharing pattern is available to it.
6. **The cost of an extra layer can be measured**: ClangIR, an extra MLIR layer between the C/C++
   AST and LLVM IR, cost 10–30% or more at -O2 in its June 2025 early state. That is the same
   order as Forge's whole 25% compile-time budget. The cost was partly due to immaturity.
7. **Fewer layers trade code quality for compile speed in every data point here**: Zig
   self-hosted (5× faster, Debug only), Cranelift (about 40% less backend CPU, with code reported up
   to about 2× slower on some benchmarks), TPDE (8–24× faster than LLVM -O0, at -O0 quality), QBE
   (targets 70% of the performance). No system found here reaches LLVM/GCC -O2 code quality with
   fewer backend layers than LLVM-with-GlobalISel (IR → gMIR/MIR → MC).
8. **Mapping onto Forge's hypothesis**: HIR → FIR → SelectionDAG → MIR → MCIR is structurally
   LLVM's *SelectionDAG* path (IR → SDAG → MIR → MC) with a language-independent HIR on top. That
   is the path LLVM is moving away from for compile-time and scope reasons. The GlobalISel-shaped
   alternative drops the SelectionDAG layer. The Go/QBE/Cranelift-shaped alternatives select
   directly from the SSA IR into a machine IR.

**Name collisions to watch for in GLOSSARY.md**:
- "FIR" is already Flang's Fortran IR.
- "HIR" is Rust-specific in rustc.
- "MIR" means *mid-level* IR in rustc and *machine* IR in LLVM and Zig.
