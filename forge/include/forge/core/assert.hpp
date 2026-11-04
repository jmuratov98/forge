// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"
#include "forge/core/utility.hpp" // IWYU pragma: keep (the macros use is_constant_evaluated)

#include <cstdint>
#include <format>
#include <source_location>
#include <string_view>

// Checks on forge's own invariants. A failed check is always a bug in forge, never in the
// program being compiled: problems in that program are diagnostics.
//
//   FORGE_ASSERT(cond)                    checked when FORGE_ASSERTIONS_ENABLED is 1
//   FORGE_ASSERT(cond, "{} != {}", a, b)  with a message, formatted only if the check fails
//   FORGE_UNREACHABLE("why")              reports when FORGE_ASSERTIONS_ENABLED is 1, traps
//                                         otherwise; it never returns
//   FORGE_TODO("what")                    code not written yet; reports in every build
//
// Messages are optional and use std::format syntax; the format string must be a literal, so it
// is checked against the arguments at compile time. A runtime string goes through "{}".
//
// When FORGE_ASSERTIONS_ENABLED is 0, FORGE_ASSERT neither evaluates its condition nor lets the
// optimizer assume it, so a broken invariant cannot turn into wrong code. The condition is still
// compiled, so a variable used only by an assertion does not need a (void) cast. Every check
// still fails during constant evaluation, so a constexpr evaluation that breaks one is a compile
// error in every build.
//
// A condition with a comma outside parentheses, such as std::is_same_v<T, int>, needs its own
// parentheses.

#if FORGE_ASSERTIONS_ENABLED
#  define FORGE_ASSERT(cond, ...)                                                                  \
      do {                                                                                         \
          FORGE_DETAIL_ASSERT(cond, #cond __VA_OPT__(, ) __VA_ARGS__);                             \
      } while (false)

#  define FORGE_UNREACHABLE(...)                                                                   \
      ::forge::detail::unreachable_reached(::std::source_location::current() __VA_OPT__(, )        \
                                               __VA_ARGS__)
#else
#  define FORGE_ASSERT(cond, ...)                                                                  \
      do {                                                                                         \
          if (::forge::is_constant_evaluated()) {                                                  \
              FORGE_DETAIL_ASSERT(cond, #cond __VA_OPT__(, ) __VA_ARGS__);                         \
          }                                                                                        \
      } while (false)

// A trap, not FORGE_BUILTIN_UNREACHABLE: reaching it ends the program instead of being
// undefined behaviour. An expression in both builds, so code that compiles in one compiles in
// the other. FORGE_BUILTIN_UNREACHABLE follows the trap only to say that it does not return:
// MSVC's code generator does not know that of __fastfail, and warns (C4715) that a function
// ending in FORGE_UNREACHABLE does not return a value on every path.
#  define FORGE_UNREACHABLE(...)                                                                   \
      (::forge::is_constant_evaluated()                                                            \
           ? ::forge::detail::unreachable_reached(::std::source_location::current() __VA_OPT__(, ) \
                                                      __VA_ARGS__)                                 \
           : (FORGE_BUILTIN_TRAP(), FORGE_BUILTIN_UNREACHABLE()))
#endif

#define FORGE_TODO(...)                                                                            \
    ::forge::detail::todo_reached(::std::source_location::current() __VA_OPT__(, ) __VA_ARGS__)

// An assertion's condition is often constant: a sizeof check, a configuration macro, a template
// argument. That is no mistake, so MSVC's C4127 "conditional expression is constant" is silenced
// around the check's `if`, and stays on everywhere else. Only MSVC gets pragmas here: GCC and
// Clang have no such warning in forge's set, and GCC has mishandled _Pragma in macro arguments,
// which is where tests put FORGE_ASSERT (EXPECT_DEATH).
#if FORGE_COMPILER_MSVC
#  define FORGE_DETAIL_CONSTANT_CONDITION_BEGIN                                                    \
      FORGE_WARNINGS_PUSH                                                                          \
      FORGE_WARNING_IGNORE_MSVC(4127)
#  define FORGE_DETAIL_CONSTANT_CONDITION_END FORGE_WARNINGS_POP
#else
#  define FORGE_DETAIL_CONSTANT_CONDITION_BEGIN
#  define FORGE_DETAIL_CONSTANT_CONDITION_END
#endif

// FORGE_ASSERT stringizes cond itself, because by the time an argument reaches this macro its
// macros are expanded. `if (cond) {} else` rather than `if (!(cond))`, whose parentheses would
// hide -Wparentheses on a mistyped FORGE_ASSERT(x = 0).
#define FORGE_DETAIL_ASSERT(cond, text, ...)                                                       \
    FORGE_DETAIL_CONSTANT_CONDITION_BEGIN                                                          \
    if (cond) [[likely]] {                                                                         \
    } else {                                                                                       \
        ::forge::detail::assertion_failed(                                                         \
            text, ::std::source_location::current() __VA_OPT__(, ) __VA_ARGS__);                   \
    }                                                                                              \
    FORGE_DETAIL_CONSTANT_CONDITION_END

namespace forge::detail {

enum class failure_kind : std::uint8_t { assertion, unreachable, todo };

// Prints the report for a failed check, with a stack trace, and aborts. `condition` is the
// assertion's text, and null for the other kinds; `format` is empty when the check has no
// message. The trace skips exactly one frame, this function's own, so it is never inlined,
// not even by link-time optimization.
[[noreturn]] FORGE_COLD FORGE_NOINLINE FORGE_API void
report_failure(failure_kind kind,
               const char* condition,
               std::source_location location,
               std::string_view format,
               std::format_args args) noexcept;

// One function per kind of check, so that a check failing during constant evaluation is named
// in the compiler's error: "non-constexpr function 'assertion_failed' cannot be used in a
// constant expression". Always inlined, so that the first frame of the report's stack trace is
// the function with the failed check rather than one of these. MSVC does not inline in Debug
// builds whatever it is told; there, the first frame is one of these.
template <typename... Args>
[[noreturn]] FORGE_COLD FORGE_ALWAYS_INLINE void
assertion_failed(const char* condition,
                 std::source_location location,
                 std::format_string<Args...> format = "",
                 Args&&... args) noexcept {
    report_failure(
        failure_kind::assertion, condition, location, format.get(), std::make_format_args(args...));
}

template <typename... Args>
[[noreturn]] FORGE_COLD FORGE_ALWAYS_INLINE void
unreachable_reached(std::source_location location,
                    std::format_string<Args...> format = "",
                    Args&&... args) noexcept {
    report_failure(
        failure_kind::unreachable, nullptr, location, format.get(), std::make_format_args(args...));
}

template <typename... Args>
[[noreturn]] FORGE_COLD FORGE_ALWAYS_INLINE void
todo_reached(std::source_location location,
             std::format_string<Args...> format = "",
             Args&&... args) noexcept {
    report_failure(
        failure_kind::todo, nullptr, location, format.get(), std::make_format_args(args...));
}

} // namespace forge::detail
