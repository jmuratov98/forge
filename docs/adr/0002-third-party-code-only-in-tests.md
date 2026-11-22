# Third-party code only in tests

Forge's shipped tools (`forge`, fas, fold and the rest) link no third-party libraries; everything they run on is written in this repo. Third-party code is allowed only for testing: googletest (pulled in through CMake) for unit tests, and LLVM's lit with the pip `filecheck` port for IR and assembly tests. Forge is a learning project, so the infrastructure a compiler needs (formatting, containers, arenas, diagnostics) is part of the learning; keeping test tooling exempt avoids reinventing what isn't the point.

## Consequences

- The pip `filecheck` package is AntonLydike/filecheck, pinned at 1.0.6. It lacks `--implicit-check-not` and numeric substitutions (`[[#...]]`, `-D#`), and its upstream CI never runs on Windows. Forge's tests use only the features it supports, and Forge's own Windows CI is the early warning. If a missing feature blocks a test Forge needs, switching to LLVM's FileCheck takes a new ADR. (Decided in [Test strategy](https://github.com/jmuratov98/forge/issues/10).)
- `llvm-objdump` and `llvm-readobj` count as test tools: lit tests use them to read Forge's Mach-O objects on hosts that can't run them.
