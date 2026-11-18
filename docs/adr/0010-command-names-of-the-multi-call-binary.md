# Command names of the multi-call binary

Bare `forge` is a gcc/clang-style driver that picks the language from the file extension, so `CC=forge` works in an existing build. The other modes are aliases of the same binary: `forge++`, `forge-cl`, `fas`, and fold's flavor names `ld.fold`, `ld64.fold`, and `fold-link`, plus `fld` for fold in the host's native flavor. The binary picks its mode from the basename of `argv[0]`, and `--driver-mode=<mode>` overrides it. The full table is in [docs/layout.md](../layout.md).

There is no `fold` command. coreutils already ships `fold(1)`, the POSIX line-wrapping utility, and installing Forge's linker under that name would shadow it. fold remains the linker's name in prose, in the glossary, and in the namespace `forge::fold`. The flavor names follow LLD's (`ld.lld`, `ld64.lld`, `lld-link`), and `ld.fold` is what a compiler driver looks for under `-fuse-ld=fold`.

This settles what ADR 0002 left open: `fas` and fold's names are aliases of the one binary, not thin standalone executables. The aliases are symlinks on Unix and hardlinks on Windows, in the build tree as well as in an install.

## Considered options

- **Zig-style subcommands** (`forge cc`, `forge c++`, `forge as`, `forge ld`): rejected. It leaves `forge` free for the Forge language's own CLI, but `CC=forge` stops working, which undercuts the drop-in replacement. The Forge language's planning can choose another command name.
- **A bare `fold` command**: rejected, because it would shadow coreutils.
- **lld's model, where the bare name refuses to run and demands a flavor**: rejected for `fld`. Running the host's native flavor makes `fld` useful on its own, and the flavor names remain for cross-linking.
- **Thin standalone `fas` and `fold` executables**: rejected. They would mean more build products for no gain, because every mode already runs in-process from the one binary.

## Consequences

- `forge` collides with other tools of the same name, notably Foundry's `forge` for Solidity. Forge accepts that collision for the name of the project.
- A target-triple prefix on `argv[0]` (`aarch64-linux-gnu-forge`) is reserved for cross-compiling. How it is parsed is decided with the target description.
