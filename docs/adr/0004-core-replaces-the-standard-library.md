# Forge's source uses core, not the C++ standard library

Forge's own source includes only these standard headers: `<cstddef>`, `<cstdint>`, `<climits>`, `<cfloat>`, `<cstdarg>`, `<limits>`, `<version>`, `<new>`, `<initializer_list>`, `<compare>`, `<concepts>`, `<type_traits>`, `<utility>`, `<bit>`, `<atomic>`, `<source_location>`, and `<cstring>` for `mem*` and `strlen` only. Everything else the standard library would provide (containers, strings, algorithms, text formatting, I/O, threads) comes from **core**, whose types live directly in namespace `forge`; every other component nests under it (`forge::c`, `forge::cxx`, …). Other C library headers and OS headers (POSIX, Win32) are included only inside core, so platform `#ifdef`s live there too.

- **Self-hosting.** At M9 Forge's C++ compiler builds Forge against the system libstdc++ or libc++, so every header Forge includes is system code it must parse; at M12 flibc++ must provide every one. The allowlist is close to C++23's freestanding set: a small, well-defined first target.
- **Determinism.** ADR 0005 needs the same behavior on libstdc++, libc++, and the MSVC STL. Hash-container iteration order and where `std::sort` leaves equal elements differ between them.
- **No reliance on `_HAS_EXCEPTIONS=0`.** ADR 0003 would otherwise depend on it across the MSVC STL, where it is undocumented.
- **Speed and checking.** core is tuned for compile speed and checks bounds the same way in every debug build.

Tests may include any standard header, because googletest needs them; self-hosting at M9 and M12 covers the shipped toolchain, not the tests. Code generators that run at build time follow every rule, because their output becomes Forge's source.

## Considered options

- Any header except those that throw or need RTTI: rejected for the reasons above.
- The allowlist plus the non-allocating vocabulary types (`<span>`, `<string_view>`, `<optional>`, `<array>`): rejected. One line is easier to check, and core gives them the same debug checks as its containers.
- No standard headers at all, with Forge's own `move`, `forward`, and type traits over compiler builtins: rejected. It is the only option that lets M9 land before Forge's C++ compiler supports concepts (the system's C++20 headers use them), but not worth re-deriving type traits from each host compiler's builtins.
