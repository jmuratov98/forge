# Forge

Forge is a compiler toolchain written in C++20, built as a learning project. It aims to be a drop-in replacement for gcc, clang and MSVC, made up of:

- `forge`: the compiler driver, for C (ANSI C to C2y), C++ (C++98 to C++26) and the Forge Language
- `fas`: the assembler
- `fold`: the linker
- `fls`, `fdb`, `ffmt`, `flint`: the language server, debugger, formatter and linter

Terms are defined in [GLOSSARY.md](GLOSSARY.md); decisions are recorded in [docs/adr/](docs/adr/). Code follows [docs/coding-standards.md](docs/coding-standards.md). Planning happens on the [first vertical slice map](https://github.com/jmuratov98/forge/issues/1).

## Setting up a checkout

Forge is worked on as a bare repo with one worktree per branch:

```sh
git clone --bare https://github.com/jmuratov98/forge ~/dev/forge/.git
cd ~/dev/forge
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch origin
git worktree add main main
```

Each other worktree sits beside `main/`, named after its branch with `/` replaced by `-`:

```sh
git worktree add -b feat/lexer feat-lexer origin/main
```

## License

Apache License 2.0 with LLVM Exceptions. See [LICENSE](LICENSE).
