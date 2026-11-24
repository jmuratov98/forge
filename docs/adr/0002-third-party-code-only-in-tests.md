# Third-party code only in tests

Forge's shipped tools (`forge`, fas, fold and the rest) link no third-party libraries; everything they run on is written in this repo. Third-party code is allowed only for testing: googletest (pulled in through CMake) for unit tests, and LLVM's lit with the pip `filecheck` port for IR and assembly tests. Forge is a learning project, so the infrastructure a compiler needs (formatting, containers, arenas, diagnostics) is part of the learning; keeping test tooling exempt avoids reinventing what isn't the point.

The C++ standard library is not third-party: shipped tools may use it, `std::format` included. Forge writes its own versions only where a compiler's workload calls for them (small vectors, dense hash maps, arenas, string interning), and only once they're needed. The coding standards (`docs/coding-standards.md`) list the few standard headers that are banned.

## Consequences

- The pip `filecheck` package is AntonLydike/filecheck, pinned at 1.0.6. It lacks `--implicit-check-not` and numeric substitutions (`[[#...]]`, `-D#`), and its upstream CI never runs on Windows. Forge's tests use only the features it supports, and Forge's own Windows CI is the early warning. If a missing feature blocks a test Forge needs, switching to LLVM's FileCheck takes a new ADR. (Decided in [Test strategy](https://github.com/jmuratov98/forge/issues/10).)
- `llvm-objdump` and `llvm-readobj` count as test tools: lit tests use them to read Forge's Mach-O objects on hosts that can't run them.
- Development tooling is exempt too, because it never ships. The dev script (`dev.py`) and the `.venv/` it creates may use pinned pip packages: `requests` and `backports.zstd` for the script itself, and `clang-format`/`clang-tidy` for formatting and linting. `dev.py` and the LLVM tools it downloads run only on developer machines and CI, and no shipped tool links them. (Decided in [The Python wrapper script](https://github.com/jmuratov98/forge/issues/12).)
- Running a host toolchain program as a subprocess is not third-party code, because nothing is linked. Until fas exists, `forge -c` runs the host assembler (ADR 0007). `llvm-mc` counts as a test tool: on hosts with no host assembler for the target, lit tests use it to assemble `forge -S` output. (Decided in [How the slice produces the .o](https://github.com/jmuratov98/forge/issues/14).)
