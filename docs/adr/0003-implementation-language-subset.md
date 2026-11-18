# Forge is written in restricted C++20

Forge's own source is C++20 without RTTI, exceptions, modules, or coroutines. Errors travel as return values. Allocation failure is fatal, and no standard-library call is used where it would report an error by throwing (for example `.at()`). On MSVC that means `/GR- /EHs-c-` and `_HAS_EXCEPTIONS=0`; googletest builds with `GTEST_HAS_EXCEPTIONS=0`. Which standard headers are allowed is a separate decision.

Forge must eventually compile itself, so every language feature it uses is one Forge's C++ compiler and flibc++ must support first. RTTI and exceptions also cost compile time and binary size.

## Considered options

- An opt-in exceptions build, like LLVM's `LLVM_ENABLE_EH`: deferred. It serves programs that embed Forge's libraries and throw through them, and none exist. Exception-safe RAII code keeps it a build-flag change if an embeddable library API is ever published.
