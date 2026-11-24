# Exceptions and RTTI are off

Forge's shipped code builds with exceptions and RTTI disabled (`-fno-exceptions -fno-rtti`, `/EHs-c- /GR-`). Failures are values: lower layers return `forge::expected<T, forge::error>`, and the layer that knows the user's context turns them into diagnostics; Forge bugs abort through `FORGE_ASSERT` and `FORGE_UNREACHABLE`. Type dispatch over IR and AST nodes uses a hand-rolled kind tag rather than `dynamic_cast` or `typeid`. A compiler has no use for unwinding past a failed compile, and kind-tagged nodes fit the dense-array IRs Forge is built on, so the cost of unwind tables and RTTI buys nothing. Tests are the exception: googletest builds with exceptions on, while the Forge code under test still builds with them off.

## Consequences

Turning either back on later means rewriting every error path and every node hierarchy, so this is effectively permanent. `std::` APIs that report failure only by throwing (`std::vector::at`, `std::stoi`) are off-limits, because with exceptions off a throw terminates the process.
