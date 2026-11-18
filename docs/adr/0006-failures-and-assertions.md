# How Forge reports failures and checks invariants

The user hears about every failure through a diagnostic, whatever caused it: a syntax error, `#include <missing.hpp>`, or `forge missing.c`. Between functions a failure travels as `expected<T, E>` (core's own; `std::expected` is C++23) until it reaches the first caller that can blame a source location or an input, and that caller turns it into a diagnostic. core never emits diagnostics. Platform failures use `forge::error`, a small value type from core that never allocates; a component defines its own `E` only when its callers branch on cases `forge::error` cannot express. Allocation failure is fatal (ADR 0003).

A broken internal invariant is an assertion failure. The build configuration decides whether `FORGE_ASSERT` is checked:

| Configuration    | Debug info | Assertions                                                   |
| ---------------- | ---------- | ------------------------------------------------------------ |
| `Debug`          | yes        | always on                                                    |
| `RelWithDebInfo` | yes        | off; on with `-DFORGE_ENABLE_ASSERTIONS=ON`                  |
| `Release`        | no         | compiled out; configuring with `FORGE_ENABLE_ASSERTIONS=ON` fails |

`MinSizeRel` fails at configure time. A failed assertion prints its message, the expression, Forge's `file:line` and function, a symbolized stack trace, and the pretty stack trace: the "while lowering `foo` (`x.c:12:3`)" entries each phase pushes. A disabled `FORGE_ASSERT(e)` does not evaluate `e`. Without assertions, `FORGE_UNREACHABLE()` is `__builtin_unreachable()` (`__assume(0)` on MSVC). In every configuration a crash handler prints the pretty stack trace and the stack trace.

## Considered options

- Assertions in every build, with a debug-only tier for expensive checks: rejected in favor of one assertion macro whose behavior the build configuration decides.
- An LLVM-style `Error` that aborts in debug builds when left unchecked: rejected for a `[[nodiscard]]` `expected`, which maps mechanically onto `std::expected` if Forge ever moves to C++23.
