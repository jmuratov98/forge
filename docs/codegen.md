# Machine IR, instruction selection and register allocation

Status: draft, 2026-11-13. Stable-name prefix: `[codegen]`.

## 1 Scope [codegen.scope]

1 This document specifies MIR, how FIR becomes MIR and then the machine-code stream of [pipe.emit], the two register allocators, the per-target ISA description and the generators that turn it into code. The IR levels are introduced in [ir]; the optimizer passes that run on FIR are in [opt].

## 2 MIR [codegen.mir]

1 MIR shall stay in SSA form, with block parameters, until register allocation. Instruction selection defines each virtual register once and keeps FIR's block parameters. Both allocators take that SSA directly and place the edge moves themselves. After allocation, MIR is over physical registers and is no longer SSA.

2 *Tied operands* are allocator constraints. An instruction that overwrites one of its inputs (`MOVK`, `BFI`, NEON accumulates) marks its def "reuse input n's register". There is no two-address pass.

3 *Opcodes.* MIR's opcodes shall be the ISA module's real instructions plus a fixed set of *generic pseudos*: copy, call (with clobbers and register uses), return, spill, reload, frame-slot address, inline asm, and edge arguments for block parameters.

4 A *target pseudo* declares its expansion in the ISA description, and the generator writes the expander. Examples are an `ADRP`+`ADD` address that rematerializes as one unit, and an LL/SC loop that must not take a spill (needed only without outline atomics). After pseudo expansion, every instruction is encodable, so the printer, the encoder and the disassembler share one opcode space.

5 MIR uses FIR's per-function arenas and 32-bit handles ([ir.layout]). Every instruction carries FIR's source-location id. MIR has the printer, round-tripping parser and verifier that [ir.text] requires.

6 Each function goes FIR → MIR → stream, and then its arenas are reset. Globals and data go from the module tables to the stream.

## 3 Instruction selection [codegen.isel]

1 *Rules.* Selection shall be done by declarative rewrite rules, compiled at build time into a C++ matcher. Each target writes its rules in one target-neutral *rules language*.

2 *One pass per function*, walking each block bottom-up. A rule may absorb an operand's instruction (a shift into an add, address arithmetic into a load) only when that value has exactly one use, in the same block. Use counts come from one scan at the start of selection, so FIR still keeps no use-lists.

3 *The generator checks the rules.*

- (3.1) Overlapping rules need an explicit priority.
- (3.2) Every FIR operation and type has a rule (totality), so "cannot select" cannot happen at run time.
- (3.3) Each instruction a rule emits takes its operand kinds and constraints from the ISA description, so a mismatch is a build error.

4 Predicates and helpers used by rules, such as `add_imm12` and logical-immediate encodability, are C++ functions in the target module that the rules file declares.

5 *Legalization lives in the rules.* There is no legalization pass.

- (5.1) `i8` and `i16` live in W registers with unspecified upper bits. A rule extends them only where the bits matter: compares, division, right shifts, conversions and addresses.
- (5.2) Rules emit calls for outline atomics (`__aarch64_ldadd4_acq_rel` and so on).
- (5.3) Rules emit calls for the libgcc routines of `i128` and `f128` ([m1.types]). An `i128` value maps to a pair of virtual registers.
- (5.4) The totality check covers legalization too.

6 *Call lowering.* FIR calls arrive with ABI-classified pieces. The target's call lowering in FIR → MIR shall: assign each piece to `x0`–`x7`, `v0`–`v7` or a stack offset under AAPCS64; put the indirect-result pointer in `x8`; and emit copies to and from those fixed registers around the call pseudo. A FIR call marked `tail` lowers to `b` instead of `bl` ([opt.layout]).

7 *Inline asm.* The inline-asm pseudo's operand constraints (`r`, `w`, `m`, `Q` and the immediate letters) become allocator constraints. Its clobbers join the pseudo's clobber set. The printer substitutes operands, with modifiers such as `%w0`, `%x0`, `%s0` and `%d0`.

## 4 Register allocation [codegen.regalloc]

1 Both allocators shall implement one interface: SSA MIR in, allocated MIR out. The interface is a seam with two adapters ([roadmap.seams]).

2 *The local allocator* is used at `-O0`. It works one block at a time, bottom-up, as LLVM's RegAllocFast has since its 2020 rewrite. Each value that is live across a block boundary gets its own stack slot, spilled after its def and reloaded before its uses. It runs in linear time and needs no global liveness. At `-O0` few values cross blocks, because the shared lowering gives every variable a stack slot ([ir.lowering]).

3 *The decoupled allocator* is used at every level above `-O0` and ships with milestone 3 ([roadmap.m3]). It is SSA-based, in three phases:

- (3.1) *Spill*, with Braun and Hack's spiller ("Register Spilling and Live-Range Splitting for SSA-Form Programs", CC 2009): Belady-style eviction by global next-use distance, until pressure is at most k in every register class. Reloads define new SSA values, which the spiller repairs.
- (3.2) *Assign* registers in dominance order. In SSA the interference graph is chordal, so assignment never fails once pressure fits. There is no eviction, no backtracking and no interference graph.
- (3.3) *Coalesce* by preference-guided assignment (Braun, Mallon and Hack, "Preference-Guided Register Assignment", CC 2010).

4 Constraints (call clobbers, ABI registers, tied operands) are met by splitting live ranges with parallel copies. Values live across calls go to the callee-saved `x19`–`x28` and `d8`–`d15`. For the FP/SIMD registers, AAPCS64 preserves only the low 64 bits.

5 *Allocation checking.* A symbolic checker shall prove each allocation correct against its SSA input. It tracks, by abstract interpretation, which virtual register each physical register and spill slot holds at every point, and flags any use that reads the wrong one. It checks both allocators, in assertion-enabled builds and under fuzzing, never in release builds.

6 The MIR verifier runs after every MIR pass in assertion-enabled builds.

## 5 The MIR pipeline [codegen.pipeline]

1 Each function runs one fixed list:

- (1.1) instruction selection;
- (1.2) register allocation, local at `-O0` and decoupled above;
- (1.3) at `-O3`, a redundant-load pass after allocation and before frame lowering ([opt.levels]);
- (1.4) frame lowering ([codegen.frame]);
- (1.5) at `-O1` and above, `LDP`/`STP` pairing and peepholes;
- (1.6) pseudo expansion;
- (1.7) branch relaxation ([codegen.relax]);
- (1.8) emission to the machine-code stream.

2 The MIR pipeline uses the optimizer's pass tables and analysis cache ([opt.manager]), because shrink-wrapping needs MIR dominators.

3 There is no instruction scheduler. One shall be added only when a benchmark shows that the out-of-order cores need it.

4 Block order comes from FIR ([opt.layout]). MIR keeps that order, and only branch relaxation adds blocks.

### 5.1 Frame lowering [codegen.frame]

1 Frame lowering shall:

- (1.1) write the `x29`/`x30` frame record: in every function at `-O0`, and from `-O1` on only on the paths that need a frame (whole-prologue shrink-wrapping, `-fshrink-wrap`, [opt.layout]);
- (1.2) save and restore callee-saved registers with `STP`/`LDP`;
- (1.3) lay out stack slots;
- (1.4) build the `va_list` register save area for variadic functions.

2 Milestone 1 emits no `.cfi_*` directives ([m1.types]).

### 5.2 Branch relaxation [codegen.relax]

1 Forge shall relax branches itself. GNU `as` never relaxes AArch64 conditional branches: when a locally resolved branch is out of range, `gas` reports "conditional branch out of range". The ranges are ±1 MiB for `b.cond` and `cbz`/`cbnz`, and ±32 KiB for `tbz`/`tbnz`.

2 Every A64 instruction is 4 bytes, and inline asm is sized conservatively by counting its statements. An out-of-range branch becomes the inverted branch around an unconditional `b`. `-S` output is therefore always in range. The object writer reuses the same relaxation once `fas` lands.

## 6 ISA description and generation [codegen.isa]

1 *The description language.* The ISA description shall be written in a Forge-specific declarative language with a fixed schema: registers and register classes, operand kinds, encodings as bit layouts, assembly syntax templates, operand constraints and pseudo expansions. The generator knows what each construct means, so it checks them: encodings cover all 32 bits with no overlap, every syntax template prints and parses unambiguously, and every operand has a constraint.

2 *Two files per target*, in one rules language: `<target>.isa` feeds the ISA module that codegen, `fas`, `fold` and the disassembler share, and `<target>.isel` feeds only codegen, so `fas` and the binary utilities never carry selection tables.

### 6.1 The aarch64 import [codegen.isa.aarch64]

1 aarch64 shall be imported from Arm's machine-readable specification, AARCHMRS. A C++ importer turns a pinned release of the AARCHMRS open-source package (BSD-3-Clause) into the description language. That covers all 4,429 A64 encodings, the assembly syntax, the 633 aliases with Arm's preferred-disassembly predicates, and `FEAT_` gating (counts from the 2026-09 release).

2 Written by hand, because the package leaves it out: an operand-kind table mapping each of Arm's ~2,500 assembly rules to a Forge operand kind with its value transform (scaling, bitmask immediates), register classes, constraints and pseudos. An Arm rule with no mapping fails the import, so coverage gaps are explicit.

3 Codegen emits only what the `FEAT_` gating allows for the selected architecture. Milestone 1 is ARMv8.0-A.

4 The import is a committed source, `aarch64-arm.isa`, with Arm's BSD-3-Clause notice in its SPDX header. Only an `./x` command (name not decided) downloads the 117 MB JSON, checks its digest and regenerates the file, and only in the pull request that bumps the pinned release. Normal builds never read the JSON.

### 6.2 Generators [codegen.isa.gen]

1 The description generator and the rules compiler shall be one C++ host tool, a premake project, built first and run by ninja. Its output goes in the build directory, is never committed, and shall be byte-deterministic. Each bootstrap stage builds its own copy of the tool with that stage's compiler.

## 7 Milestone-1 work [codegen.m1]

1 Milestone 1 generates the printer, the encoder and the decoder. `fcc1` emits only through the printer ([pipe.emit]).

2 *Oracle test.* For every instruction Forge prints, GNU `as` assembles the text. Forge's encoding shall match GNU `as`'s bytes, and Forge's decoder shall decode those bytes back to the same MIR instruction. `fas` inherits an ISA module that has already been tested. The ISA module's assembler parser arrives with `fas`.

3 The machine-code stream shall support common symbols (`.comm`) for tentative definitions under `-fcommon`: 8 programs in the gated suite pass that flag, CTMark's lencod among them. Milestone 1 emits no `.cfi_*` directives and no debug sections ([m1.types]).

4 The work list is [m1.deliver].

5 The decoupled allocator, `LDP`/`STP` pairing, shrink-wrapping, sibling calls and the redundant-load pass are milestone 3.

## Annex A (informative): Rationale and departures [codegen.rationale]

1 *MIR in SSA.* This departs from LLVM. Its MachineIR leaves SSA before allocation (PHIElimination, TwoAddressInstruction) and then runs RegisterCoalescer to delete the copies those passes inserted. regalloc2 has accepted only SSA input since 0.7.0.

2 *Target pseudos.* This departs from LLVM's target pseudos with hand-written expansion passes (`AArch64ExpandPseudoInsts`).

3 *Selection rules.* Cranelift's ISLE is the model, narrowed to selection. SelectionDAG builds a DAG per block, which is slow and cannot see across blocks. GlobalISel walks every instruction four times (IRTranslator, Legalizer, RegBankSelect, InstructionSelect). GCC expands through `define_expand` and then re-recognises RTL with combine and recog, so its patterns live apart from binutils' encodings. LLVM's "Cannot select" is a fatal error at run time; Forge's totality check makes it a build error.

4 *Decoupled allocation.* libFirm ships this approach, and no mainstream compiler does. LLVM's Greedy and regalloc2's Ion are backtracking allocators over live-range bundles, with eviction and splitting heuristics, and Greedy is one of LLVM's slowest codegen passes. The accepted risk is that the decoupled approach has not been tuned in a production compiler; the `-O2` runtime budget measures it.

5 *Allocation checking.* regalloc2 has the same kind of checker. LLVM's MachineVerifier checks structure but not that allocation preserved values, so allocator bugs surface only as miscompiles.

6 *No scheduler.* This departs from LLVM's pre- and post-RA machine schedulers with per-CPU models, and from GCC's scheduling passes.

7 *Branch relaxation.* An inverted branch around `b` is what GCC's `far_branch` and LLVM's BranchRelaxation do.

8 *ISA description.* This departs from TableGen, a general record language whose meaning lives in each backend's C++ emitter, and from GCC, which maintains its `.md` patterns apart from binutils' opcode tables. LLVM attaches selection patterns to instruction records; Forge keeps them in a separate `.isel` file. LLVM and binutils hand-write their AArch64 tables; arm64jit and VirtualBox already generate code from Arm's data.

9 *Later targets.* Each later target's ISA source is in the fog. Intel XED's datafiles are Apache-2.0, and Go already generates its AVX encoder tables from them, so they are a candidate for x86-64's import ([roadmap.fog]).

## Annex B (informative): Provenance [codegen.prov]

1 [Machine IR, instruction selection and register allocation](https://github.com/jmuratov98/forge/issues/11), refined by [Optimizer pipeline and pass manager](https://github.com/jmuratov98/forge/issues/12) (shrink-wrapping, sibling calls, the `-O3` redundant-load pass, shared pass tables) and [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10) (`i128`, `f128`, no CFI, `-fcommon`).
