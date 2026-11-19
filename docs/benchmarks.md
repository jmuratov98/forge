# Benchmarks

How Forge is measured against the [roadmap](roadmap.md#speed-goals)'s speed goals. Benchmarks are a separate harness, not part of the test suite ([testing.md](testing.md#benchmarks)): timings are noisy and depend on the host, so they never pass or fail a build. The design was decided in [How are compile speed and generated-code quality benchmarked?](https://github.com/jmuratov98/forge/issues/21). Nothing here is built before M5.

## The goals

- **Compile time**: at most 1.25× the baseline's, at the same `-O` level. Measured at `-O0` and `-O2`.
- **Generated code**: at most 1.25× slower than the baseline's, at `-O2`.

The **baseline** for a metric on a host is the best of that host's baseline compilers on that metric: the compiler with the fastest compile times for the compile-time goal, and the one whose code runs fastest for the generated-code goal. The two goals may have different baselines.

| Host OS | Baseline compilers           |
| ------- | ---------------------------- |
| Linux   | gcc, clang                   |
| macOS   | gcc, clang, AppleClang       |

A goal is judged over a whole corpus: the geometric mean of Forge's time divided by the baseline's, across every program in the corpus, must be at most 1.25. Programs whose own ratio is above 1.25 are listed in the report but are not a miss. Being faster than the baseline is never a miss.

## When it runs

| Milestone | What happens                                                                                                  |
| --------- | ------------------------------------------------------------------------------------------------------------- |
| Before M5 | Nothing. M1 through M4 deliver no benchmarking                                                                |
| M5        | The harness is built first, before any optimization pass, and runs on demand as passes land. Meeting the goals on the C corpora is an exit criterion |
| M6–M10    | One run at each milestone's exit, for information. A goal miss is filed as an issue and doesn't block the exit |
| M11       | Runs on demand. Meeting the goals on C++ corpora is an exit criterion                                         |
| M12       | One run at the exit, for information                                                                          |

## Targets and reference machines

At M5 the goals must be met on all three targets: arm64 macOS, arm64 Linux, and x86-64 Linux. A target added later is measured from the milestone that adds it; M11's planning decides which targets its verdict covers.

Every result comes from a **reference machine**: a named, fixed machine that runs nothing else during a run. It may be physical or a VM, so arm64 Linux may run in a VM on the macOS reference machine. GitHub-hosted runners are not reference machines, and CI runs no benchmarks. Results from different machines are never compared with each other. The machines themselves are chosen when M5 is planned.

## Baseline compilers

- **gcc** is FSF gcc and **clang** is upstream LLVM clang, each pinned to an exact version in the harness configuration, the same version on every reference machine.
- **AppleClang** is the one in the Xcode installed on the macOS reference machine. Its version is recorded with every result.
- MSVC is not a baseline. From M6 it may be recorded for information.

Baselines are re-pinned deliberately, about once a year, to the latest stable releases. A re-pin or an Xcode update starts a new **baseline series**. Regressions are only judged within one series.

## What is measured

**The Forge build.** The `Release` configuration, built the way a shipped release is built, including LTO or PGO if releases use them. Until release builds are defined, it is built with the pinned clang.

**Compile time.** One `-c` per translation unit, from source to object file, including any assembler Forge runs. Translation units are compiled one after another; Forge may use threads inside one translation unit. Linking is not measured.

- Wall time is what the goal judges.
- User plus system CPU time and peak RSS are recorded beside it, with no goal.

**Generated code.** Every compiler builds the program at `-O2` for the target's default CPU (no `-march=native`). Every binary is linked with the same linker against the same libc. The metric is the wall time of the program's run.

**Repetitions.** Each compile or run is preceded by one warm-up that is discarded, then repeated at least 5 times for compile time and at least 10 times for generated code. The median is recorded, with the spread. Times and peak RSS come from the child's resource usage (`wait4`).

## Corpora

Corpora are fetched at benchmark time, pinned to a commit, and never vendored, like the copyleft test corpora ([testing.md](testing.md#corpora)).

- **Compile time**: Lua 5.4's translation units, and the sqlite3.c amalgamation once Forge compiles it. Together they cover many small translation units and one huge one.
- **Generated code**: a C benchmark suite of real programs and kernels, all fetchable, with no SPEC. The list is chosen when M5 is planned. Candidates are llvm-test-suite's benchmarks, CoreMark, PolyBench, SQLite's `speedtest1`, and Lua running its own benchmarks.
- **C++**: chosen when M11 is planned.

## The harness

`scripts/bench` is a Python script, like `update-e2e`. It never runs as part of `check`. Its configuration pins the baseline compiler versions and the corpus commits.

Each run writes one JSON file, committed to the `bench-results` branch: an orphan branch that is never merged, which keeps timing noise out of `main`'s history. A run records:

- the Forge commit and version
- the reference machine
- the baseline series and every baseline compiler's version
- for every program, compiler, and `-O` level: the median and spread of each metric

`scripts/bench compare` prints two runs side by side.

## Regressions and goal misses

A **regression** is a run on the same reference machine and baseline series as the previous run that is worse than it by either:

- more than 3% in a corpus's geometric mean, or
- more than 10% for any single program.

A regression is filed as an issue. It never blocks a merge.

A **goal miss** is a geometric-mean ratio above 1.25. It blocks the exit of M5 or M11; at any other milestone it is filed as an issue.

## Open questions

- Tracking regressions in CI by instruction count (cachegrind on Linux runners), which is stable enough for shared runners where wall time is not.
- The reference machines and the generated-code suite, chosen when M5 is planned.
