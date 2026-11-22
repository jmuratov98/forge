# Compiler-construction research relevant to Forge's IR pipeline

Resolves [#4](https://github.com/jmuratov98/forge/issues/4). Feeds [#15 "Does the slice go through every IR layer?"](https://github.com/jmuratov98/forge/issues/15) and the per-IR design tickets.

Pipeline under discussion (see `GLOSSARY.md`): AST → HIR (language-independent, non-SSA) → FIR (SSA) → MIR (target-specific, virtual or physical registers) → MCIR (close to encoded instructions).

Every claim below is tied to a source in [Sources](#sources), cited as [S#]. Numbers are quoted as the source states them; they come from different benchmarks and machines, so they are not comparable with each other.

## TL;DR

- **SSA construction:** build FIR straight from HIR with Braun et al. [S1]. It needs no dominance frontiers, no non-SSA CFG detour, and runs on par with Cytron et al. [S2]. Its output is minimal and pruned for reducible CFGs; C's `goto` can make irreducible CFGs, which need an extra SCC pass to stay minimal (correctness is unaffected).
- **Block arguments vs φ:** use block arguments. MLIR [S3] and Cranelift [S4] chose them, and regalloc2 [S10] consumes them directly. One friction: removing a trivial φ that has become a block argument means editing every predecessor's branch [S1].
- **CFG vs sea of nodes:** use a CFG. V8 dropped sea of nodes after measuring compile time halved and about 3x fewer L1 dcache misses with a CFG [S5]. Its mid-tier Maglev was built as an SSA CFG from the start [S6]. The one part of sea of nodes that pays off (pure ops floating over a skeleton of side-effecting ops) can be had later as a pass, as Cranelift's aegraph shows [S8].
- **E-graphs:** not for the slice. Full equality saturation is too expensive for a fast compiler [S8]. Cranelift's acyclic variant works, but its own 2026 retrospective finds that the e-graph part "may not (yet?) be pulling its weight" next to its sea-of-nodes elaboration [S8].
- **Instruction selection:** lower FIR→MIR one instruction at a time, walking backwards with use counts and tree-matching each instruction's operands (Cranelift [S11]). Skip a SelectionDAG-style intermediate DAG [S13]. A rule DSL (ISLE [S12]) or generated matchers can come later.
- **Register allocation:** for the slice, a simple forward greedy allocator plus a parallel-move resolver (Maglev [S6], TPDE [S15]), with an allocation checker (regalloc2 [S10]). Keep MIR in SSA with block arguments until the allocator, so linear scan on SSA [S17] or SSA-based (chordal) allocation [S18] can replace it later. The allocator is where SSA gets destroyed.
- **Fast compilation:** LLVM's -O0 backend is a low bar. TPDE beats it 8–24x with comparable code by doing one analysis pass and one combined isel/regalloc/encoding pass [S15]. Every extra IR translation has a measurable cost [S1][S15], and memory layout (dense arrays, no linked lists) matters as much as the algorithms [S5][S11][S10].
- **MLIR:** use it as a design reference, not a model to copy (ADR 0001 rules out generator-library generality). Take from it: lower in small steps, drop structure deliberately, keep source locations through every layer, and give each layer a verifier and a textual form [S9]. Clang's own fixed pipeline, AST → LLVM IR → SelectionDAG → MachineInstr → MCInst, also has five levels [S9], so Forge's layer count is not unusual.

---

## 1. SSA construction: Cytron et al. vs Braun et al.; block arguments vs φ-nodes

**What the sources say.**
Cytron et al. [S2] place φ-functions at iterated dominance frontiers of each variable's definition sites. This needs a complete non-SSA CFG, a dominator tree and dominance frontiers, and (for pruned form) liveness. Braun et al. [S1] say the dependence on "several other analyses and transformations" is why many compilers "take a detour through a non-SSA CFG". LLVM's version of that detour is the alloca/load/store form that `mem2reg` rewrites: 25% of the instructions the LLVM front end emits are such memory operations, removed by SSA construction ([S1] §1, Table 1).

Braun et al.'s algorithm builds SSA directly from the AST (or any structured source) during IR construction. Each block keeps a local `currentDef` map. A lookup recurses into predecessors and creates φs on demand. Blocks are **sealed** once no more predecessors can be added, and lookups in unsealed blocks create "incomplete" φs that are completed on sealing. Trivial φs (all operands the same value or the φ itself) are removed as they appear. Results ([S1] §4, §6):

- The output is **pruned** for all programs and **minimal** for reducible CFGs. Irreducible CFGs can leave redundant φ SCCs, and a post-pass (Algorithm 5) removes them.
- Implemented in LLVM 3.1 and compared with LLVM's "highly-tuned" Cytron implementation, it executed 99.72% as many x86 instructions over SPEC CINT2000, so runtime was on par. φ counts were nearly identical (38,674 vs 38,696).
- Because the IR is in SSA form from the start, optimizations such as constant folding and CSE can run while it is built. libFirm has used this approach for years.

On **block arguments**, MLIR's rationale [S3] lists the problems φ-nodes cause: they must sit at the top of a block and passes have to skip past them; function arguments need a separate node kind (with block arguments, the entry block's arguments serve that role); φs in a block take effect atomically, which is confusing and tied to the lost-copy problem in SSA destruction; a φ list is unordered and long in blocks with many predecessors, and passes scan it linearly; and you cannot give a value to only one successor edge. Cranelift IR has "no phi instructions but uses BB parameters instead" [S4]. regalloc2 handles block parameters inside the allocator, which its author calls a fundamental improvement over its predecessor [S10].

**Trade-off.** Cytron is the textbook algorithm and pairs naturally with a dominator tree you will build anyway. But it forces the frontend lowering to emit a non-SSA FIR (or an alloca form) and then rewrite it. Braun produces SSA in a single pass during HIR→FIR lowering, which is exactly the setting it was designed for. It has the same cost and quality, and it is less code. Its price is a sealing discipline in the lowering code (seal a loop header only after its back edge is added) and a post-pass if minimality on irreducible CFGs matters. Block arguments make φ operands explicit on the branches, which keeps block bodies uniform and maps directly onto MIR and onto regalloc2-style allocators. Their cost is that deleting or adding a φ means editing every predecessor terminator. Braun et al. point this out for CPS/parameter form: "it is worthwhile to not introduce unnecessary parameters in the first place" ([S1] §5, using the §3.3 extensions).

**Take for Forge.** FIR uses block arguments, and HIR→FIR lowering builds SSA with Braun's algorithm. Keep incomplete φs as side-table entries until a block is sealed and trivial-φ removal has run, and only then materialise them as block parameters and branch arguments. That avoids rewriting terminators. C `goto` can create irreducible control flow, so the FIR ticket should decide whether non-minimal SSA is acceptable there. It is correct, just not minimal.

## 2. CFG-based IR vs sea of nodes (and V8's move away)

**What the sources say.**
Sea of nodes (Click & Paleczny [S7]) drops the fixed instruction order inside blocks: pure nodes float, ordered only by data dependencies, while control and effect edges order the rest. V8's TurboFan used it for about a decade. In March 2025 V8 published why it was replacing it with Turboshaft, a conventional CFG IR [S5]:

- "compile time got divided by 2 compared to SoN."
- Sea of nodes averaged "about 3 times more L1 dcache misses" than the CFG IR, up to 7x in some phases, because nodes end up scattered in memory as the graph is mutated.
- A rewritten CFG load-elimination pass was "up to 190 times faster".
- In practice most JavaScript nodes sit on effect or control chains anyway: "SoN is just CFG where pure nodes are floating". Managing both chains was error-prone.
- Graphs were hard to read and debug, and the scheduler had to duplicate floating nodes back so they would not run on paths that don't need them. Deadness propagation, new control flow during lowering, and loop identification were all harder.

V8's mid-tier compiler Maglev (2023) [S6] was built as an SSA CFG from the start. It builds the graph in a single forward pass over bytecode (a prepass finds loops and loop-assigned variables, so loop φs are created before the body) and keeps a minimal set of passes. It compiles "roughly 10x slower than Sparkplug, and 10x faster than TurboFan."

Cranelift's 2026 retrospective on its aegraph optimizer [S8] makes a related observation: what pays off is a **CFG skeleton of side-effecting instructions with pure ops floating in a hash-consed "sea"**, rebuilt into the CFG by scoped elaboration. That gives GVN, DCE, LICM and rematerialisation as by-products, but only for the duration of an optimization pass, not as the IR everyone works on.

**Trade-off.** Sea of nodes in theory folds GVN, code motion and combined analyses into one representation. V8's experience is that for real workloads (most nodes effectful, a lowering pipeline that keeps adding control flow) it costs compile time, cache locality, debuggability and engineering effort, and its benefits are available in a CFG through targeted passes. A CFG IR keeps a stable order that matches both source and assembly, which matters for a learning project whose tests compare textual output (ADR 0002: lit + FileCheck).

**Take for Forge.** FIR is an SSA CFG with block arguments. Store instructions in dense arrays addressed by 32-bit indices, not as heap nodes linked by pointers (see §6). If FIR later gets GVN/LICM, consider an aegraph-style "float pure ops, elaborate back" pass. To keep that option cheap, give each FIR opcode a pure/side-effecting flag from the start.

## 3. E-graphs, equality saturation and Cranelift's aegraphs

**What the sources say.**
egg [S19] made e-graphs practical for equality saturation: apply every rewrite non-destructively until saturation (or a limit), then extract the cheapest equivalent program. This solves phase ordering in principle. Its contributions are amortised **rebuilding** of congruence invariants and **e-class analyses**.

Cranelift's RFC [S20] started from phase ordering: its GVN and redundant-load elimination had to be rerun. It rejected full equality saturation in favour of an **acyclic e-graph (aegraph)**: rewrites fire eagerly when a node is created, with no parent pointers or recanonicalisation after merges. Only side-effecting instructions stay pinned in a CFG skeleton, and pure nodes are elaborated back along the dominator tree. Rules are written in ISLE, and Cranelift chose ISLE-generated Rust over egg's engine for control over performance. Prototype results: compile time SpiderMonkey +1%, bz2 −15% (it replaced GVN, LICM, simple_preopt and alias analysis rather than adding to them); runtime −13% and −3%.

The 2026 retrospective [S8] reports, after three years in production:

- The aegraph pipeline gives a "~2% speedup" over the classical pipeline, which repeating the classical passes did not reproduce. Compile time rose about 7–8% as the rule set grew (they were at parity in 2023).
- Average e-class size after rewriting is **1.13 e-nodes**. Keeping several equivalent forms per value bought "~0.1% execution-time improvement, at ~0.005% compile-time cost". The author concludes the multi-value representation "may not (yet?) be pulling its weight", and that the sea-of-nodes-plus-elaboration part is what clearly works.
- Exact extraction with sharing is NP-hard, so Cranelift uses a bottom-up dynamic program that ignores sharing. Full equality saturation is judged too expensive for a fast compiler, because of blowup and data-structure costs.

Research continues on e-graphs as a persistent IR abstraction inside MLIR (Tamagoyaki, 2026 preprint [S21]). That work targets optimization power, not compile speed.

**Trade-off.** E-graphs remove the work of choosing a pass order and give a declarative rule format that can be verified. Full equality saturation costs memory and time that grow badly with rule count, which is incompatible with a gcc/clang-class compile-time budget. The acyclic, eager variant is affordable, but the evidence says most of its value comes from the elaboration framework, not from keeping alternatives.

**Take for Forge.** Out of scope for the slice (no optimizations beyond correctness). Don't shape FIR around e-graphs. If FIR gets an optimizer later, the cheap and proven path is hash-consed pure ops plus scoped elaboration, with eager single-pass rewrites. Equality saturation is a research side-quest, not a backbone.

## 4. Instruction selection: tree/DAG matching, ISLE, GlobalISel

**What the sources say.**
LLVM's **SelectionDAG** [S13] builds a DAG per block, then runs combine, type legalization, combine, op legalization, combine, select (TableGen-generated matcher) and schedule. The DAG is thrown away afterwards, and it cannot match nodes that define multiple values, which is the main reason targets still need hand-written C++. **FastISel** is the fast block-local -O0 path. **GlobalISel** [S14] replaces both: it works on the whole function, directly on (generic) Machine IR rather than a separate DAG. Its pipeline is IRTranslator → Legalizer → RegBankSelect → InstructionSelect, and the fast and optimizing selectors share a core pipeline. Its docs say the fast pipeline is "within 1.5x of FastISel". The TPDE paper reports that on AArch64, where GlobalISel is LLVM's default at -O0, it is much slower than FastISel. TPDE's speedup over LLVM -O0 is larger on AArch64 (geomean 18.96x) than on x86-64 (12.15x) [S15].

**Cranelift** [S11] (2020) moved from a single IR legalized by repeated expansion ("A single IR simply cannot serve both ends of this spectrum properly") to a two-level design. CLIF is lowered into **VCode**, a per-target linear array of machine instructions over virtual registers. Lowering visits instructions **backwards** so that uses are seen before definitions. It emits code only for used or side-effecting results, which builds DCE into lowering, and it tree-matches operands to merge producers (for example, a shift folded into an AArch64 `sub`). A colouring scheme stops merges across side effects, and matching stops at block parameters. **ISLE** [S12] (2023) turns those lowering rules into a typed term-rewriting DSL compiled to Rust. Rules have priorities, an overlap checker rejects overlapping rules at the same priority (which surfaced several fully shadowed rules), and rules can be translated to SMT for verification. The same DSL drives the aegraph rewrites.

**TPDE** [S15] removes a separate selection IR entirely. Instruction semantics are written in C/C++ and compiled by LLVM to post-regalloc Machine IR, from which encoder functions are generated. Constants, addresses and spilled values get folded into immediate and memory operands. Compare-and-branch fusion is hand-written per architecture, and an instruction whose users are all in the same block can be fused into them.

**Trade-off.** DAG-based selection matches across whole blocks but adds a separate IR, several legalize/combine rounds and a scheduler, which is a large share of LLVM backend compile time and complexity. Selecting per instruction with tree matching over operands is linear, simple, and good enough for most of the benefit: most profitable patterns are trees rooted at one instruction (address modes, shifted operands, multiply-add, compare plus branch). GlobalISel shows a different split: translate to a *generic* MIR, legalize there, then select in place. That puts legalization in MIR instead of FIR. A DSL (ISLE, TableGen) pays off once there are many rules and several targets. Before that, hand-written C++ matchers are cheaper to build and debug.

**Take for Forge.** For the slice, FIR→MIR lowering is a backward walk per instruction, with use counts and hand-written operand-tree matchers for a few AArch64 patterns. No intermediate DAG. The MIR ticket must decide where legalization lives: in FIR before selection, as Cranelift does, or as GlobalISel-style generic MIR selected in place. The latter is a design variant #15 should know about. Generated matchers or a DSL are a later option, and ADR 0001 warns against building generality early.

## 5. Register allocation: linear scan, regalloc2, SSA-based/chordal allocation

**What the sources say.**

- **Linear scan** (Poletto & Sarkar [S16]) allocates live intervals in one sweep in linear order. It is fast but spills whole intervals. **Linear scan on SSA** (Wimmer & Franz, CGO 2010 [S17], HotSpot client compiler) uses SSA properties to compute liveness without iterative dataflow, and folds SSA destruction (φ resolution) into the allocator's resolution phase, so no separate pass is needed.
- **LLVM moved off linear scan** in 3.0 [S22]: its virtual-register rewriter accounted for "about half of the linear scan compile time" and fixed only block-local mistakes. The greedy allocator (priority queue by size, eviction by spill weight, split before spill) produces code "1-2% smaller, and up to 10% faster", with an 85-line rewriter instead of about 2,600 lines.
- **regalloc2** [S10] (Cranelift, 2022) is a backtracking allocator derived from IonMonkey's: live ranges merged into bundles, then a priority loop that assigns, evicts or splits. It accepts SSA with **block parameters** and does SSA destruction itself. Operands carry constraints (any register of a class, a fixed register, reuse-an-input, a stack slot), so x86 `mul` and ABI registers become ordinary operands. All moves go through one parallel-move resolver. It improved overall Cranelift compile speed "by 20%-ish" and code on register-pressure-heavy benchmarks by up to 10–20%. It is over 10K lines of dense Rust, and the author says "approximately zero chance for any human to get this correct" without fuzzing and a symbolic checker that verifies the allocation preserves dataflow. regalloc2 now also ships **fastalloc**, a single-pass reverse-linear-scan mode for fast compile times [S23].
- **SSA-based / chordal allocation** (Hack, Grund & Goos, CC 2006 [S18]): SSA interference graphs are chordal, so register pressure equals the colour count. Spill until pressure ≤ k everywhere, then colour greedily in dominance order with **no interference graph built**. Spilling, colouring and coalescing come apart cleanly, although coalescing needs its own algorithms (CC 2007, PLDI 2008). It is implemented in libFirm.
- **Fast-tier allocators:** Maglev [S6] computes live ranges in a prepass, assigns registers in a single forward greedy walk, spills at definition (one slot per value), and uses a parallel move resolver at merges. TPDE [S15] is greedy and local: it spills all non-fixed live values at multi-predecessor or out-of-layout block boundaries, and pins loop-carried values in callee-saved registers. Its code is within ±9% of LLVM -O0, and its .text is about 43–49% larger, mostly from bigger prologues and epilogues.

**Trade-off.** Single-pass greedy allocators cost almost nothing and give -O0-class code. Linear scan (especially on SSA) is the classic middle tier: near-linear time with decent code. Backtracking (LLVM greedy, regalloc2) gives the best code but is large and subtle. SSA-based allocation is elegant, decouples spill and assign, and suits a teaching codebase, but it requires MIR to stay strictly SSA up to allocation and needs careful handling of fixed-register constraints. All the serious designs share three pieces: liveness over SSA, a **parallel-move resolver**, and SSA destruction inside the allocator. The regalloc2 experience says a **checker** is mandatory, not optional.

**Take for Forge.** The slice needs a correct, simple allocator: forward greedy or local, Maglev/TPDE-style. Build the parts every later allocator will reuse now: liveness, operand constraints (fixed ABI registers for `w0`/`w1`), a parallel-move resolver, and an allocation checker. Keep MIR in SSA with block parameters until allocation, so SSA linear scan, chordal or backtracking allocators can be swapped in later. ADR 0002 rules out pulling in regalloc2 or TPDE as dependencies, so these are references, not libraries.

## 6. Techniques for fast compilation

**What the sources say.**

- **TPDE** [S15] (TU Munich; arXiv 2025, CGO 2026) is a back-end framework that adapts to an existing SSA IR through an adapter, without building its own IR. It runs **one analysis pass** (RPO block layout with loops kept contiguous, loop tree, linear-time liveness, use counts) and then **one pass that does instruction selection, register allocation and encoding together**. On SPECint 2017 it compiles LLVM IR "8–24x faster than LLVM -O0", with runtime within ±9%. End to end, its back-end takes about 2% of total compile time versus 15% for LLVM's back-end (a 17% average end-to-end speedup). For Wasm, about 37% of time went to translating into Cranelift IR, so every extra IR translation is a visible cost. Its LLVM back-end is under 8k lines. It targets **ELF only** on x86-64 and AArch64 [S24], so it has no Mach-O reference.
- **Copy-and-patch** [S25] (Xu & Kjolstad, OOPSLA 2021) stitches together precompiled binary "stencils" with holes for values. It is about two orders of magnitude faster than LLVM -O0 on TPC-H, with 14% faster code, and 4.9–6.5x faster than V8's Liftoff. On SPECint, TPDE measured copy-and-patch code as 2.38x slower and 4.44x larger than LLVM -O0 [S15]. It suits JITs and database query compilers that compile tiny templates, not an AOT C compiler.
- **Cranelift's compile-time discipline** [S11][S10]: linear instruction arrays instead of linked lists, no fixpoint loops, compact instructions (16 bytes on AArch64), 32-bit packed operands, sorted arrays instead of searches. Its notes say cutting the number of live ranges or bundles matters more than micro-optimisation. Cranelift with fastalloc still compiles 2.68x slower than TPDE, and Winch (a single-pass Wasm baseline) is 1.74x faster than TPDE [S15][S23].
- **V8:** a CFG IR halved compile time against sea of nodes, mostly through cache behaviour [S5]. Maglev deliberately keeps one IR and few passes [S6].

**Trade-off.** The biggest wins come from (a) fewer full IR translations, (b) fusing passes that walk the same instructions (TPDE's isel+regalloc+encode), and (c) cache-friendly data layout. All three trade against modularity and testability: a fused pass has no intermediate textual form to FileCheck and is harder to read. For an AOT C compiler at -O0, LLVM's back-end is about 15% of total compile time in TPDE's measurements, and the frontend dominates the rest. Matching gcc/clang therefore needs a back-end that is linear and cheap, not one that is heroically fused.

**Take for Forge.** Five layers are affordable if each layer is a dense-array IR and each lowering is a single linear pass. That is a stated constraint for every IR ticket. The cross-cutting "arenas / interning" ticket should fix the data layout: index-based handles, arena allocation, no per-instruction heap nodes. Treat TPDE as evidence that MIR and MCIR *could* be fused for a fast path later, not as the slice's design. The 0.8–1.2x speed target is out of scope for the slice, but choosing layouts now avoids a rewrite later.

## 7. MLIR's multi-level IR as a reference for layered IRs

**What the sources say.** The MLIR paper [S9] (Lattner et al., CGO 2021) lists its design principles:

- **Little builtin, everything customizable:** a few core concepts (operations, types, attributes, regions, blocks).
- **SSA and regions:** nested regions for structured constructs, alongside CFGs.
- **Progressive lowering** in small steps: "Previous compilers have been introducing multiple fixed levels of abstraction… as does the Clang compiler which lowers from ASTs to LLVM IR, to SelectionDAG, to MachineInstr, and to MCInst. Whereas these approaches are done in a rigid way, more flexible designs are required."
- **Maintain higher-level semantics:** "the loss of structure is then conscious and happens only where the structure is no longer needed". Removing loop structure in favour of a CFG means no further transformations at that level.
- **Mix abstraction levels** within one IR.
- **IR validation:** declarative verifiers.
- **Declarative rewrite patterns.**
- **Source location tracking and traceability** of every op through every transformation.

The rationale doc [S3] adds the block-argument reasoning from §1.

**Trade-off.** MLIR's generality (dialects, an open op set, generic pass infrastructure) is what makes it reusable across domains. That is exactly the "compiler-generator library" direction ADR 0001 rejected, and it costs design effort and some compile speed. Its fixed-level counterpart, Clang/LLVM, has the same five-level shape as Forge's pipeline. The difference is that Forge has a language-independent HIR where LLVM has a SelectionDAG level, and Forge's FIR→MIR needs no separate DAG.

**Take for Forge.** Keep fixed, concrete IRs (one C++ type system per layer) and take MLIR's principles, not its machinery:

- Each lowering removes a specific piece of structure, and the ticket for that layer names it. For example, HIR keeps structured control flow and FIR turns it into a CFG.
- Every layer has a verifier and a textual print format for lit/FileCheck tests (ADR 0002).
- Source locations go through every layer to MCIR, which also prepares for later DWARF.
- FIR and MIR use block arguments.

---

## Implications for #15 "Does the slice go through every IR layer?"

The trade-offs the decision has to weigh:

1. **Cost of a layer.** A layer is affordable if it is a dense-array IR and its lowering is one linear pass (Cranelift, Maglev, TPDE). Each translation still has a measurable cost: the 37% CLIF translation share in TPDE's Wasm case, and the 25% alloca overhead in LLVM's SSA detour. So each layer should justify itself by what it makes simpler or testable.
2. **Skipping FIR.** If FIR is skipped, either MIR must be built in SSA (Braun's algorithm works on any IR built from structured input) or MIR is non-SSA. A non-SSA MIR rules out the SSA-based allocator family and SSA destruction inside the allocator. Building FIR with Braun during HIR lowering is cheap, so a thin FIR costs little and keeps those doors open.
3. **Fusing MIR and MCIR.** TPDE (isel+regalloc+encoding in one pass) and Cranelift (VCode emitted straight into a machine-code buffer) show that MIR→MCIR can be very thin. LLVM keeps MachineInstr and MCInst separate. For the slice, a thin MCIR mainly helps testing (FileCheck on assembly text) and isolates the Mach-O writer. That is a reason to keep it, even if it is trivial.
4. **HIR→FIR is where SSA happens; regalloc is where it ends.** The boundary ADRs should say so explicitly.
5. **Worked example.** For `int add(int a, int b) { return a + b; }`, FIR is a single block whose entry-block arguments are the function arguments (block-argument form, §1). MIR is one AArch64 `add w0, w0, w1` after allocation with fixed ABI constraints, plus `ret`.

## Possible new tickets / scope notes

- **Testing strategy for IRs:** per-layer verifiers, textual round-trip, a register-allocation checker, and fuzzing (regalloc2's lesson [S10]). Nothing in the map's "Not yet specified" list covers this yet.
- **Irreducible CFGs from C `goto`:** the FIR/SSA ticket should decide whether non-minimal SSA is acceptable or whether to run Braun's SCC post-pass.
- **Where legalization lives** (FIR vs generic MIR, the GlobalISel model) should be an explicit question in the MIR ticket.
- **Data layout** (index handles, arenas) is cross-cutting and should be decided in the shared-infrastructure ticket before the IR tickets, because §2 and §6 both say it drives compile speed.
- **Baseline note:** on AArch64, LLVM -O0 uses GlobalISel, which TPDE reports as much slower than FastISel [S15]. The clang -O0 baseline for `aarch64-apple-darwin` may be easier to match than on x86-64. Worth keeping in mind when the speed target comes back into scope.

## Sources

Primary sources only (papers, official design docs, authors' own write-ups).

- [S1] M. Braun, S. Buchwald, S. Hack, R. Leißa, C. Mallon, A. Zwinkau. "Simple and Efficient Construction of Static Single Assignment Form." CC 2013, LNCS 7791. https://c9x.me/compile/bib/braun13cc.pdf
- [S2] R. Cytron, J. Ferrante, B. Rosen, M. Wegman, F. K. Zadeck. "Efficiently Computing Static Single Assignment Form and the Control Dependence Graph." ACM TOPLAS 13(4), 1991. https://doi.org/10.1145/115372.115320
- [S3] MLIR Rationale, "Block Arguments vs PHI nodes" and regions. https://mlir.llvm.org/docs/Rationale/Rationale/
- [S4] Cranelift IR reference. https://github.com/bytecodealliance/wasmtime/blob/main/cranelift/docs/ir.md
- [S5] D. Mercadier. "Land ahoy: leaving the Sea of Nodes." V8 blog, 25 Mar 2025. https://v8.dev/blog/leaving-the-sea-of-nodes
- [S6] T. Verwaest et al. "Maglev - V8's Fastest Optimizing JIT." V8 blog, 5 Dec 2023. https://v8.dev/blog/maglev
- [S7] C. Click, M. Paleczny. "A Simple Graph-Based Intermediate Representation." IR '95 (ACM SIGPLAN Notices 30(3)). https://doi.org/10.1145/202529.202534
- [S8] C. Fallin. "The acyclic e-graph: Cranelift's mid-end optimizer." 9 Apr 2026. https://cfallin.org/blog/2026/04/09/aegraph ; EGRAPHS 2023 invited talk: https://pldi23.sigplan.org/details/egraphs-2023-papers/2/-graphs-Acyclic-E-graphs-for-Efficient-Optimization-in-a-Production-Compiler
- [S9] C. Lattner et al. "MLIR: Scaling Compiler Infrastructure for Domain Specific Computation" (CGO 2021); preprint "MLIR: A Compiler Infrastructure for the End of Moore's Law." https://arxiv.org/abs/2002.11054
- [S10] C. Fallin. Blog post on regalloc2, Cranelift's new register allocator. 9 Jun 2022. https://cfallin.org/blog/2022/06/09/cranelift-regalloc2/
- [S11] C. Fallin. "A New Backend for Cranelift, Part 1: Instruction Selection." 18 Sep 2020. https://cfallin.org/blog/2020/09/18/cranelift-isel-1/
- [S12] C. Fallin. "Cranelift's Instruction Selector DSL, ISLE: Term-Rewriting Made Practical." 20 Jan 2023. https://cfallin.org/blog/2023/01/20/cranelift-isle/
- [S13] LLVM Target-Independent Code Generator, SelectionDAG instruction selection. https://llvm.org/docs/CodeGenerator.html
- [S14] LLVM GlobalISel documentation. https://llvm.org/docs/GlobalISel/index.html
- [S15] T. Schwarz, T. Kamm, A. Engelke. "TPDE: A Fast Adaptable Compiler Back-End Framework." arXiv:2505.22610 (2025); CGO 2026. https://arxiv.org/abs/2505.22610
- [S16] M. Poletto, V. Sarkar. "Linear Scan Register Allocation." ACM TOPLAS 21(5), 1999. https://doi.org/10.1145/330249.330250
- [S17] C. Wimmer, M. Franz. "Linear Scan Register Allocation on SSA Form." CGO 2010. https://doi.org/10.1145/1772954.1772979
- [S18] S. Hack, D. Grund, G. Goos. "Register Allocation for Programs in SSA-Form." CC 2006, LNCS 3923. https://doi.org/10.1007/11688839_20 ; project page: https://compilers.cs.uni-saarland.de/projects/ssara/
- [S19] M. Willsey et al. "egg: Fast and Extensible Equality Saturation." POPL 2021. https://arxiv.org/abs/2004.03082
- [S20] Bytecode Alliance RFC "Cranelift: e-graph based mid-end optimizations." https://github.com/bytecodealliance/rfcs/blob/main/accepted/cranelift-egraph.md
- [S21] J. Merckx et al. "E-Graphs as a Persistent Compiler Abstraction." arXiv:2602.16707 (2026). https://arxiv.org/abs/2602.16707
- [S22] J. Stoklund Olesen. "Greedy Register Allocation in LLVM 3.0." LLVM blog, 18 Sep 2011. https://blog.llvm.org/2011/09/greedy-register-allocation-in-llvm-30.html
- [S23] regalloc2 FASTALLOC design doc. https://docs.rs/crate/regalloc2/latest/source/doc/FASTALLOC.md
- [S24] TPDE repository README. https://github.com/tpde2/tpde (docs: https://docs.tpde.org/)
- [S25] H. Xu, F. Kjolstad. "Copy-and-Patch Compilation." OOPSLA 2021 (PACMPL 5). https://arxiv.org/abs/2011.13127
