# C++ coding standards

How Forge's own C++ is written. `.clang-format` and `.clang-tidy` at the repo root enforce most of it; the rest is enforced in review. Terms follow [GLOSSARY.md](../GLOSSARY.md); the reasoning behind the hard-to-reverse choices lives in [docs/adr/](adr/).

## Language level

- **Strict C++20.** Nothing from C++23 or later, even where a host compiler offers it behind a feature-test macro. Every cell of the CI matrix (MSVC, MinGW, CLANGARM64, Linux gcc and clang, Apple clang) has to build the same code.
- **Exceptions and RTTI are off** in shipped code ([ADR 0003](adr/0003-exceptions-and-rtti-are-off.md)). Tests build with exceptions on because googletest needs them.

### C++20 features

| Feature | Policy |
|---|---|
| Modules | Banned: CMake can't scan them for AppleClang, and MinGW gcc modules are fragile. |
| Coroutines | Banned: no compiler stage needs them, and their frames allocate on the heap. |
| Concepts | Welcome. Use them instead of SFINAE and `enable_if` for every constrained template. |
| Ranges | Algorithms (`std::ranges::sort`, `find_if`) are welcome. View pipelines may appear in function bodies, never in API signatures or return types. |
| Designated initializers, `consteval`/`constexpr`, `std::span`, `std::string_view`, `<bit>`, `[[nodiscard]]`, `[[likely]]`, `<=>`, `using enum` | Welcome. |

### The standard library

The standard library isn't third-party ([ADR 0002](adr/0002-third-party-code-only-in-tests.md)), and shipped tools may use it, `std::format` included. Forge writes its own small vectors, dense hash maps, arenas and string interning when a compiler's workload calls for them, not before.

- `<iostream>` is banned in shipped code because of static initialization and speed. `<coroutine>` is banned along with coroutines.
- `std::` APIs that report failure only by throwing (`std::vector::at`, `std::stoi`) are off-limits, because with exceptions off a throw terminates the process.

## Naming

Everything is `snake_case`, like std. The two exceptions are template parameters and googletest names.

| Entity | Style | Example |
|---|---|---|
| Types, type aliases, concepts | `snake_case` | `basic_block`, `small_thing` |
| Functions, variables, parameters | `snake_case` | `lower_to_hir`, `block_count` |
| Template parameters | `PascalCase` | `T`, `Allocator` |
| Enumerators (always `enum class`) | `snake_case` | `opcode::add` |
| Namespace-scope variables and constants | `g_` prefix | `g_max_operands` |
| Static data members, class `static constexpr`, function-local `static` | `s_` prefix | `s_capacity`, `s_next_id` |
| Private and protected data members | `m_` prefix | `m_blocks` |
| Public data members, function-local `constexpr` | no prefix | `lhs`, `local_limit` |
| Macros | `FORGE_SCREAMING_CASE` | `FORGE_ASSERT` |
| Namespaces | `snake_case`, under `forge::` | `forge::fir` |
| googletest suites and tests | `PascalCase` (googletest forbids `_`) | `TEST(Lexer, LexesIntegerLiteral)` |

When a type and a variable would share a name, rename the variable (`basic_block block;`, not `basic_block basic_block;`). Test fixtures and helpers outside the `TEST` names follow the normal rules.

## Files and headers

- Headers are `.hpp` and sources are `.cpp`, named in `snake_case` after their main type (`basic_block.hpp`). `.h` is for C, which Forge compiles.
- Headers use `#pragma once` and are self-contained: each compiles on its own, includes what it uses (`misc-include-cleaner`), and has no `using namespace` at file scope.
- Include order, grouped by clang-format: the file's own header, then Forge headers (`"..."`), then std headers (`<...>`).
- Which headers are public and how include directories are laid out is decided with the source tree.

## Comments

- Every public declaration in a header gets a Doxygen block: `/** @brief ... */`. Add `@param`, `@return` and `@pre` only where the name and type don't already say it.
- `//` is for implementation comments in `.cpp` files and private sections. `///` isn't used.
- Comments explain why, not what. Doxygen isn't run in CI; the syntax is a convention.

## Errors

Failures fall into three channels that never mix:

1. **Diagnostics are the only channel the user sees.** A missing `#include`, a missing input file (`forge missing.c`), a bad flag and a type error are all diagnostics. Each carries a source location where one exists (the `#include` line) and points at the command line otherwise. Compilation continues where it can.
2. **`forge::expected<T, E = forge::error>`** is how lower layers that know nothing about the user (file system, object writer) report failure. It is a C++20 copy of `std::expected`'s interface, so moving to C++23 is a find-and-replace, and it is `[[nodiscard]]`. `forge::error` holds a code and a message and is never printed directly. The layer that knows the context, such as the preprocessor at an `#include` directive or the driver for a command-line input, turns it into a diagnostic.
3. **`FORGE_ASSERT(cond, msg)` and `FORGE_UNREACHABLE(msg)`** are for Forge bugs. They print the location and abort, and they stay on in release builds. Expensive checks such as IR verifiers go behind `FORGE_DEBUG_ASSERT` or a flag.

## Ownership and memory

- No owning raw pointers. `new` and `delete` appear only inside allocator and container code.
- `std::unique_ptr` for single ownership. `std::shared_ptr` is banned in shipped code, since nothing in a compile pipeline has shared lifetimes (enforced in review).
- Non-owning access uses `T&` (never null), `T *` (may be null), `std::span` and `std::string_view`. A function doesn't keep a `span` or `string_view` beyond the call unless its name or docs say so.
- No dynamically initialized globals: a global is `constexpr` or `constinit`. Mutable globals also trip `cppcoreguidelines-avoid-non-const-global-variables` and need a `NOLINT` with a reason.
- Arenas, handles and the index-vs-pointer question belong to the IR data layout, which builds on these rules.

## Integer types

- No `long`, `unsigned long`, `short` or `long long` (`google-runtime-int`): `long` is 32 bits on Windows and 64 on Linux and macOS. Use `std::int32_t`, `std::uint64_t` and similar, and `std::size_t` for sizes and std-facing indices.
- `char` is for text only, never arithmetic: its signedness differs between hosts.
- Never model a target C type with a host type. Target sizes, alignment and signedness come from the target description, and constant folding uses fixed-width arithmetic sized by it.

## Everyday style

- `auto` only when the type is spelled on the right (`auto p = std::make_unique<x>()`), for iterators and lambdas, and in structured bindings. Otherwise spell the type out.
- `const` on locals that don't change and on every non-mutating member function. No `const` on by-value parameters in declarations.

## Tooling

- **clang-format 23.1.4**, pinned through the pip `clang-format` wheel. Google style with 4-space indent, 100 columns, `int *p`, braces on every `if` and loop, and no single-line `if` or loops. Authors run it locally through the wrapper's `format` command; CI doesn't check formatting.
- **clang-tidy 23.1.4**, pinned through the pip `clang-tidy` wheel. It's a required check on one Linux CI job, using `compile_commands.json`, with every warning treated as an error. The root `.clang-tidy` lists each disabled check and its reason; `tests/.clang-tidy` relaxes only what googletest's macros trip.
- A `NOLINT` must name its check and give a reason: `// NOLINT(check-name): reason`.
- Disabling a check takes a PR that adds a one-line reason to `.clang-tidy`.
- These configurations stand in until ffmt and flint exist.
