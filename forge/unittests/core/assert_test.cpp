// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/assert.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <format>
#include <type_traits>

namespace forge {
namespace {

// Its formatter fails a check, so a report whose message formats it fails while reporting.
struct fails_when_formatted {};

} // namespace
} // namespace forge

template <>
struct std::formatter<forge::fails_when_formatted> {
    static constexpr auto parse(std::format_parse_context& context) { return context.begin(); }

    static auto format(forge::fails_when_formatted /*unused*/, std::format_context& context) {
        FORGE_ASSERT(false, "inside a formatter");
        return context.out();
    }
};

namespace forge {
namespace {

constexpr int halve(int value) {
    FORGE_ASSERT(value % 2 == 0, "{} is odd", value);
    return value / 2;
}

// A call is a constant expression exactly when its checks pass, in every build: a failing check is
// never skipped during constant evaluation. forge/test/host/assert-constexpr.cpp checks what the
// compiler says when one fails.
template <int Value>
concept halve_is_constant = requires { typename std::integral_constant<int, halve(Value)>; };

static_assert(halve(8) == 4);
static_assert(!halve_is_constant<3>);

enum class shape : std::uint8_t { circle, square };

// No return after FORGE_UNREACHABLE: it never returns in any build, so -Wreturn-type is quiet.
constexpr int corners(shape s) {
    switch (s) {
    case shape::circle:
        return 0;
    case shape::square:
        return 4;
    }
    FORGE_UNREACHABLE("invalid shape {}", static_cast<int>(s));
}

template <shape Shape>
concept corners_is_constant = requires { typename std::integral_constant<int, corners(Shape)>; };

static_assert(corners(shape::square) == 4);
static_assert(!corners_is_constant<static_cast<shape>(7)>);

int not_written_yet() {
    FORGE_TODO();
}

int g_evaluations = 0;

bool counted(bool value) {
    ++g_evaluations;
    return value;
}

TEST(assertions, condition_is_evaluated_only_when_enabled) {
    g_evaluations = 0;
    FORGE_ASSERT(counted(true));
    FORGE_ASSERT(counted(true), "{}", counted(true));
    // The message arguments are evaluated only when the check fails.
    EXPECT_EQ(g_evaluations, FORGE_ASSERTIONS_ENABLED ? 2 : 0);
}

TEST(assertions, passing_checks) {
    EXPECT_EQ(halve(6), 3);
    EXPECT_EQ(corners(shape::circle), 0);
}

// ThreadSanitizer does not support the fork that death tests use. The regular expressions stay
// within what gtest supports on Windows: no brackets, and `.` does not match a newline.
#if GTEST_HAS_DEATH_TEST && !FORGE_TSAN_ENABLED

#  if FORGE_ASSERTIONS_ENABLED
#    define FORGE_TEST_ZERO 0

TEST(assertions, failure_reports_location_and_condition_as_written) {
    EXPECT_DEATH(FORGE_ASSERT(FORGE_TEST_ZERO == 1),
                 "assert_test.cpp:.*: internal error: assertion failed: FORGE_TEST_ZERO == 1");
}

TEST(assertions, failure_reports_message) {
    const int value = 5;
    EXPECT_DEATH(FORGE_ASSERT(value != 5, "value cannot be {}", value),
                 "message: value cannot be 5");
}

TEST(assertions, failure_reports_function) {
    EXPECT_DEATH(static_cast<void>(halve(3)), "in function: .*halve");
}

TEST(assertions, failure_while_reporting_aborts) {
    EXPECT_DEATH(FORGE_ASSERT(false, "{}", fails_when_formatted{}),
                 "internal error: a check failed while reporting a failed check");
}

TEST(assertions, unreachable_reports) {
    EXPECT_DEATH(static_cast<void>(corners(static_cast<shape>(7))),
                 "internal error: unreachable code reached");
    EXPECT_DEATH(static_cast<void>(corners(static_cast<shape>(7))), "message: invalid shape 7");
}
#  else
TEST(assertions, unreachable_traps) {
    EXPECT_DEATH(static_cast<void>(corners(static_cast<shape>(7))), "");
}
#  endif

TEST(assertions, todo_reports_in_every_build) {
    EXPECT_DEATH(static_cast<void>(not_written_yet()), "internal error: not yet implemented");
    EXPECT_DEATH(FORGE_TODO("lowering {}", "switch"), "message: lowering switch");
}
#endif

} // namespace
} // namespace forge
