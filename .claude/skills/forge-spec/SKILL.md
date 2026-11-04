---
name: forge-spec
description: Write, revise or check a forge design spec under docs/ in ISO C++ standardese (stable names, numbered paragraphs, Effects/Returns elements, informative annexes), or implement code against one. Use when asked to design, spec, draft or document a forge facility, or to check a docs/*.md spec.
---

# forge design specs

forge designs a facility in `docs/<name>.md` before implementing it. Specs are written in the
style of ISO/IEC 14882. `docs/stacktrace.md` is the reference example; read it before writing a new
spec, and read any spec the new one interacts with (`crash_context.md`, `version.md`, ...).

## Process

1. **Research prior art first**: how LLVM, GCC and rustc (or whoever is relevant) do it, with
   source paths. forge does not copy them blindly: for each borrowed idea, decide whether to copy or
   improve it, and record why in the rationale annex.
2. **Ask before deciding** anything that is a policy or taste call (API shape trade-offs, which
   hosts, build-time vs run-time, what goes in Release). Use AskUserQuestion with concrete options;
   recommend one. Mechanical consequences of a decision need no question.
3. **Draft** from `template.md` in this skill's directory. Keep `Status: draft, <today>.`
4. **Check** the mechanics, then fix everything it reports:
   ```sh
   python3 .claude/skills/forge-spec/scripts/check_spec.py            # every docs/*.md
   python3 .claude/skills/forge-spec/scripts/check_spec.py docs/x.md  # one spec
   ```
   It checks stable names (prefix, uniqueness across docs/), paragraph and `(N.M)` item numbering,
   `[Note N: … — end note]` numbering and closing, the order of *Effects*-style elements, and that
   references to other forge specs resolve. It cannot judge wording; reread for that.

## Form

- Title `# Title [prefix]`, every heading `## N Title [prefix.name]`; annexes
  `## Annex A (normative|informative) Title [prefix.name]`, subclauses `### C.1 … [prefix.x.y]`.
  Stable names never change once written; renumbering clauses is fine.
- Clause 0 *Conventions* (copy from the template), 1 *Scope* (including what is out of scope and
  which spec covers it), 2 *Terms and definitions*, 3 *Header synopsis* when there is an API, then
  one clause per facility.
- Paragraphs are numbered from 1 in each clause, each starting a block: `1 The function ...`.
  List items are `- (2.1) ...`, nested `- (2.1.1) ...`.
- A function spec is a `cpp` block with the declaration, then paragraphs with elements in the
  order *Constraints, Mandates, Preconditions, Effects, Synchronization, Postconditions, Result,
  Returns, Throws, Complexity, Remarks*. An element may repeat; it may not go back.
- "shall"/"shall not" for requirements on forge; "unspecified" and "implementation-defined" as in
  [intro.defs]. Names use forge's conventions: snake_case, `FORGE_` macros as 0/1.
- `[Note 1: … — end note]` and `[Example 1: … — end example]` are informative and numbered
  within each clause.
- Bare `[stable.name]` refers to ISO C++ ([support.signal], [basic.stc.dynamic]); a forge name
  from another spec also names its file the first time: `[context.dump] (docs/crash_context.md)`.
- Normative annex for build/tooling requirements (premake options, macros, CI rows, tools in
  tools.json). Informative annexes: *Tests* (which test file checks which paragraph, in which
  suite: `forge/unittests/<c>/`, `forge/test/host/`, `forge/test/build/`), *Rationale* with
  *Prior art*, *Departures from LLVM* and *Relationship to later documents*.

## Implementing a spec

- Implement clause by clause and cite the stable name in a comment only where the code would
  otherwise look arbitrary (`// [stacktrace.capture] p5: no allocation, no lock`).
- The *Tests* annex is the test plan: write those tests (use the `forge-lit-test` skill for lit
  ones). When the implementation forces a change of design, change the spec in the same change
  and tell the user; do not let code and spec drift.
- When a spec is fully implemented, update its `Status:` line, and ask the user whether to keep
  it as documentation.
