# Third-party code only in tests

Forge's shipped tools (`forge`, fas, fold and the rest) link no third-party libraries; everything they run on is written in this repo. Third-party code is allowed only for testing: googletest (pulled in through CMake) for unit tests, and LLVM's lit with the pip `filecheck` port for IR and assembly tests. Forge is a learning project, so the infrastructure a compiler needs (formatting, containers, arenas, diagnostics) is part of the learning; keeping test tooling exempt avoids reinventing what isn't the point.
