# Forge preprocesses C itself, as a token stream between lexer and parser

Forge has its own preprocessor from the first slice. It does not call the host `cpp` or `clang -E`, and it does not require preprocessed input. The preprocessor sits between the lexer and the parser: the parser pulls tokens from the preprocessor, which pulls preprocessing tokens from the lexer, and `-E` prints that same stream. No token is turned back into text and lexed again, so every token keeps its spelling location and, if a macro produced it, its expansion location.

## Considered Options

- **Call the host `cpp` / `clang -E`.** Cheapest to start with, but MSVC hosts have no `cpp`, and the output depends on the host: `clang -E` defines `__clang__`, so a different branch survives than under GCC. Source locations would have to be recovered from linemarkers, which carry no columns inside macro expansions. And the work would be thrown away once Forge replaces `gcc`/`clang`.
- **Accept only preprocessed input.** *Writing a C Compiler*'s tests are vendored unmodified, and 51 of the 314 valid files in chapters 1–10 use `#ifdef`/`#pragma`. The test harness would then need a `cc -E` step, which MSVC hosts don't have.
- **A text-to-text pass that is lexed again.** This is the traditional `cpp` design. It lexes everything twice and needs linemarkers to recover locations, which brings back the location problem of the host `cpp`.

## Consequences

The C and C++ frontends will share the preprocessor. The slice implements only part of it. The deferred directives and macro forms, such as `#include` and function-like macros, get "not yet supported", just as the C subset does for C features.
