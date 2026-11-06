// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/error.hpp"

#include "forge/core/result.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <limits>
#include <type_traits>

namespace forge {
namespace {

enum class math_errc : std::uint8_t { divide_by_zero = 1, overflow };
enum class wide_errc : std::uint64_t { too_wide = 1 }; // NOLINT(performance-enum-size)
enum unscoped_errc : std::uint8_t { unscoped_failure = 1 };

result<int, error> divide(int a, int b) noexcept {
    if (b == 0) {
        return math_errc::divide_by_zero;
    }
    return a / b;
}

result<int, error> negate(int a) noexcept {
    if (a == std::numeric_limits<int>::min()) {
        return make_error(math_errc::overflow);
    }
    return -a;
}

result<void, error> check(bool ok) noexcept {
    if (!ok) {
        return math_errc::overflow;
    }
    return success();
}

// --- construction ------------------------------------------------------------------------------

static_assert(error(math_errc::divide_by_zero).code() == 1);
static_assert(error(math_errc::divide_by_zero) == error(math_errc::divide_by_zero));
static_assert(error(math_errc::divide_by_zero) != error(math_errc::overflow));
static_assert(make_error(math_errc::overflow) == error(math_errc::overflow));
static_assert(std::is_nothrow_convertible_v<math_errc, error>);

// No value means success, so nothing default-constructs an error.
static_assert(!std::is_default_constructible_v<error>);
static_assert(!std::is_constructible_v<error, int>);
static_assert(!std::is_constructible_v<error, unscoped_errc>);
static_assert(!std::is_constructible_v<error, wide_errc>);

// --- in a result -------------------------------------------------------------------------------

static_assert(std::is_convertible_v<math_errc, result<int, error>>);
static_assert(!std::is_convertible_v<unscoped_errc, result<void, error>>);

TEST(error, a_returned_enum_is_the_error) {
    const result<int, error> ok = divide(6, 3);
    ASSERT_TRUE(ok.has_value());
    EXPECT_EQ(*ok, 2);

    const result<int, error> bad = divide(1, 0);
    ASSERT_FALSE(bad.has_value());
    EXPECT_EQ(bad.error(), math_errc::divide_by_zero);
    EXPECT_EQ(bad.error().code(), 1U);
}

TEST(error, make_error_is_the_error) {
    const result<int, error> bad = negate(std::numeric_limits<int>::min());
    ASSERT_FALSE(bad.has_value());
    EXPECT_EQ(bad.error(), make_error(math_errc::overflow));
}

TEST(error, a_void_result_succeeds_without_an_error) {
    EXPECT_TRUE(check(true).has_value());

    const result<void, error> bad = check(false);
    ASSERT_FALSE(bad.has_value());
    EXPECT_EQ(bad.error(), math_errc::overflow);
}

} // namespace
} // namespace forge
