# Third-party code only in tests

Forge's shipped tools (`forge`, fas, fold and the rest) link no third-party libraries; everything they run on is written in this repo. Third-party code is allowed only for testing: googletest (pulled in through CMake) for unit tests, and LLVM's lit with the pip `filecheck` port for IR and assembly tests. Forge is a learning project, so the infrastructure a compiler needs (formatting, containers, arenas, diagnostics) is part of the learning; keeping test tooling exempt avoids reinventing what isn't the point.

## Consequences

- Development tooling is exempt too, because it never ships. The dev script (`dev.py`) and the `.venv/` it creates may use pinned pip packages: `requests` and `backports.zstd` for the script itself, and `clang-format`/`clang-tidy` for formatting and linting. `dev.py` and the LLVM tools it downloads run only on developer machines and CI, and no shipped tool links them. (Decided in [The Python wrapper script](https://github.com/jmuratov98/forge/issues/12).)
