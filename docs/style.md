# Style

The rules for Forge's own source. The reasons live in the linked ADRs.

## Naming

| Kind                                                         | Style                | Example                      |
| ------------------------------------------------------------ | -------------------- | ---------------------------- |
| Variables, types, functions, concepts, enumerators, `constexpr` constants | `snake_case`         | `source_location`, `max_align` |
| Template parameters                                          | `CamelCase`          | `template <typename ValueType>` |
| Globals                                                      | `g_` prefix          | `g_crash_handler`            |
| Private member variables                                     | `m_` prefix          | `m_size`                     |
| Private static member variables                              | `s_` prefix          | `s_instance_count`           |
| Public struct members                                        | no prefix            | `error.code`                 |
| Macros                                                       | `FORGE_UPPER_SNAKE`  | `FORGE_ASSERT`               |
| Files                                                        | `snake_case.hpp` / `.cpp` | `string_view.hpp`       |

core's types live directly in namespace `forge`; every other component nests under it (`forge::c`, `forge::cxx`, `forge::fas`, `forge::fold`, …).

## Language

- C++20 without RTTI, exceptions, modules, or coroutines ([ADR 0003](adr/0003-implementation-language-subset.md)).
- A feature is allowed if every supported host compiler implements it, or if a wrapper hides the difference: `FORGE_NO_UNIQUE_ADDRESS` stands in for `[[no_unique_address]]`, which MSVC ignores.
- No global or static objects with non-trivial constructors or destructors; make them `constinit` or `constexpr`. Function-local statics are fine.
- `char` is for text. Byte values are `std::uint8_t` or `unsigned char`. `char8_t` and `wchar_t` are allowed.
- All built-in integer types are allowed; prefer the fixed-width `<cstdint>` types, and never let the width of a `long` reach the output ([ADR 0005](adr/0005-byte-identical-output-across-hosts.md)).
- No `float` or `double` outside core's software floating point and its timing utilities (ADR 0005).
- Nothing that reaches the output depends on hash-container iteration order, pointer values, or where an unstable sort leaves equal elements (ADR 0005).

## Headers

Only these standard headers ([ADR 0004](adr/0004-core-replaces-the-standard-library.md)):

`<cstddef>` `<cstdint>` `<climits>` `<cfloat>` `<cstdarg>` `<limits>` `<version>` `<new>` `<initializer_list>` `<compare>` `<concepts>` `<type_traits>` `<utility>` `<bit>` `<atomic>` `<source_location>`, and `<cstring>` for `mem*` and `strlen` only.

- Everything else comes from core.
- Other C library headers and OS headers (POSIX, Win32) only inside core. `<cctype>`, `<clocale>`, and `<cmath>` never on a path that affects output.
- Tests may include any standard header. Build-time code generators follow every rule.

## Failures and assertions

See [ADR 0006](adr/0006-failures-and-assertions.md).

- Report anything the user must hear about as a diagnostic, at the first caller that can blame a source location or an input.
- Carry failures to that caller as `expected<T, E>`; platform failures use `forge::error`.
- Check internal invariants with `FORGE_ASSERT(condition)`; mark impossible paths with `FORGE_UNREACHABLE()`. Never put side effects in an assertion: builds without assertions do not evaluate it.
