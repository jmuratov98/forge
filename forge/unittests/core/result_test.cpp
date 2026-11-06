// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/result.hpp"

#include "forge/core/config.hpp"

#include <gtest/gtest.h>

#include <cstddef>
#include <format>
#include <initializer_list>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <type_traits>
#include <utility>
#include <vector>

namespace forge {
namespace {

using std::string_view_literals::operator""sv;

// Counts live objects and special member calls, to see that each state is built and destroyed
// exactly once. Its move constructor is noexcept unless told otherwise, so that the assignments
// of a type that cannot move without throwing are testable too.
struct counted {
    static inline int s_alive = 0;
    static inline int s_copies = 0;
    static inline int s_moves = 0;

    int id;

    explicit counted(int i) noexcept : id(i) { ++s_alive; }
    counted(std::initializer_list<int> list, int extra) noexcept : id(extra) {
        for (const int i : list) {
            id += i;
        }
        ++s_alive;
    }
    counted(const counted& other) noexcept : id(other.id) {
        ++s_alive;
        ++s_copies;
    }
    counted(counted&& other) noexcept : id(other.id) {
        ++s_alive;
        ++s_moves;
        other.id = -1;
    }
    counted& operator=(const counted& other) {
        id = other.id;
        ++s_copies;
        return *this;
    }
    counted& operator=(counted&& other) noexcept {
        id = other.id;
        other.id = -1;
        ++s_moves;
        return *this;
    }
    ~counted() { --s_alive; }
};

struct counting : testing::Test {
protected:
    void SetUp() override {
        counted::s_alive = 0;
        counted::s_copies = 0;
        counted::s_moves = 0;
    }
    void TearDown() override { EXPECT_EQ(counted::s_alive, 0); }
};

using result_int = result<int, std::string_view>;

// --- [result.reqs]: how a bare argument is read ---------------------------------------------

constexpr result_int parse_count(int x) noexcept {
    if (x < 0) {
        return "count cannot be negative";
    }
    return x;
}

constexpr result<std::size_t, std::errc> size_zero() {
    return 0;
}

constexpr result<double, std::errc> double_one() {
    return 1;
}

constexpr result<std::string_view, std::string_view> both() {
    return "text";
}

static_assert(parse_count(3).value() == 3);
static_assert(parse_count(-1).error() == "count cannot be negative"sv);
static_assert(*size_zero() == 0);
static_assert(*double_one() == 1.0);
static_assert(both().has_value());
static_assert(result<int, double>(3.5).value() == 3);
static_assert(result<int, std::errc>(std::size_t{3}).value() == 3);

static_assert(!std::is_convertible_v<const char*, result<bool, std::string_view>>);
static_assert(std::is_convertible_v<failure<std::string_view>, result<bool, std::string_view>>);
static_assert(!std::is_convertible_v<std::string_view, result<std::string, std::string_view>>);
static_assert(std::is_constructible_v<result<std::string, std::string_view>, success<std::string>>);
static_assert(!std::is_convertible_v<double, result<int, double>>);
static_assert(!std::is_convertible_v<int, result<double, double>>);
static_assert(std::is_convertible_v<int, result<long, std::errc>>);
static_assert(!std::is_default_constructible_v<result<int, int>>);
static_assert(std::is_default_constructible_v<result<void, int>>);

// A result of a result can be made from the inner one.
static_assert(std::is_convertible_v<result_int, result<result_int, std::string_view>>);

// --- triviality ([result.object.ctor] p42) --------------------------------------------------

static_assert(std::is_trivially_copyable_v<result<int, std::errc>>);
static_assert(std::is_trivially_copyable_v<result<void, std::errc>>);
static_assert(std::is_trivially_copyable_v<result<int&, std::errc>>);
static_assert(!std::is_trivially_copyable_v<result<std::string, std::errc>>);
static_assert(!std::is_trivially_destructible_v<result<void, std::string>>);
static_assert(std::is_copy_constructible_v<result<std::string, int>>);
static_assert(!std::is_copy_constructible_v<result<std::unique_ptr<int>, int>>);
static_assert(std::is_move_constructible_v<result<std::unique_ptr<int>, int>>);
static_assert(!std::is_copy_assignable_v<result<std::unique_ptr<int>, int>>);
static_assert(std::is_nothrow_move_constructible_v<result<int, std::errc>>);

// --- constant evaluation of each class ------------------------------------------------------

constexpr bool object_basics() {
    result<int, int> r(success(4));
    if (r != success(4) || r != 4 || !(r == result<int, int>(4))) {
        return false;
    }
    r = failure(2);
    if (r.has_value() || r.error() != 2 || r != failure(2)) {
        return false;
    }
    r = 5;
    if (*r != 5 || !r) {
        return false;
    }
    result<int, int> q(in_place_failure, 9);
    r.swap(q);
    if (r.error() != 9 || *q != 5) {
        return false;
    }
    swap(r, q);
    if (*r != 5) {
        return false;
    }
    r.emplace(11);
    return *r == 11 && r.value_or(0) == 11 && q.value_or(0) == 0 && r.error_or(3) == 3 &&
           q.error_or(3) == 9;
}
static_assert(object_basics());

constexpr bool object_monadic() {
    result<int, int> value(6);
    const result<int, int> error(in_place_failure, 7);
    return value.transform([](int v) { return v * 2; }).value() == 12 &&
           value.and_then([](int v) -> result<int, int> { return v + 1; }).value() == 7 &&
           error.or_else([](int e) -> result<int, int> { return e + 1; }).value() == 8 &&
           error.transform_error([](int e) { return e * 2.5; }).error() == 17.5 &&
           value.transform([](int) {}).has_value() &&
           error.transform([](int v) { return v; }).error() == 7;
}
static_assert(object_monadic());

constexpr bool void_basics() {
    result<void, int> a;
    result<void, int> b = failure(3);
    if (!a || b) {
        return false;
    }
    a.swap(b);
    if (a || !b) {
        return false;
    }
    a = success();
    b = failure(7);
    if (!a || b.error() != 7) {
        return false;
    }
    const result<void, int> c = b;
    a = c;
    if (a.error() != 7) {
        return false;
    }
    a.emplace();
    return a == success() && b == failure(7) && a == result<void, long>() &&
           *a.transform([] { return 5; }) == 5 && a.error_or(1) == 1;
}
static_assert(void_basics());

constexpr bool reference_basics() {
    int x = 1;
    int y = 2;
    result<int&, int> r(x);
    if (&*r != &x) {
        return false;
    }
    r = y; // rebinds
    if (&*r != &y || x != 1) {
        return false;
    }
    result<int&, int> e(in_place_failure, 4);
    r.swap(e);
    if (r.has_value() || &*e != &y) {
        return false;
    }
    *e = 8;
    return y == 8 && e.value_or(0) == 8 && r.value_or(0) == 0 && e == 8 && e == success(y);
}
static_assert(reference_basics());

// A temporary never binds: ill-formed rather than an error ([result.ref] (1.2)).
static_assert(!std::is_constructible_v<result<const int&, int>, int>);
static_assert(!std::is_assignable_v<result<const int&, int>&, int>);
static_assert(std::is_constructible_v<result<const int&, int>, const int&>);
static_assert(std::is_constructible_v<result<const int&, int>, int&>);

// --- run-time behavior ----------------------------------------------------------------------

TEST(result, holds_a_value_or_an_error) {
    const result_int ok = parse_count(4);
    ASSERT_TRUE(ok.has_value());
    EXPECT_TRUE(static_cast<bool>(ok));
    EXPECT_EQ(*ok, 4);
    EXPECT_EQ(ok.value(), 4);

    const result_int bad = parse_count(-4);
    ASSERT_FALSE(bad.has_value());
    EXPECT_EQ(bad.error(), "count cannot be negative"sv);
}

TEST(result, arrow_reaches_the_value) {
    result<std::string, int> r(in_place, "abc");
    EXPECT_EQ(r->size(), 3U);
    r->push_back('d');
    EXPECT_EQ(*r, "abcd");
}

TEST(result, in_place_forms_pass_their_arguments) {
    const result<std::vector<int>, int> r(in_place, {1, 2, 3});
    EXPECT_EQ(r->size(), 3U);
    const result<int, std::string> e(in_place_failure, 3, 'x');
    EXPECT_EQ(e.error(), "xxx");
    const result<int, std::vector<int>> v(in_place_failure, {4, 5});
    EXPECT_EQ(v.error().size(), 2U);
}

TEST(result, converts_between_result_types) {
    const result<int, std::errc> from(7);
    const result<long, std::errc> widened(from);
    EXPECT_EQ(*widened, 7);
    const result<int, std::errc> failed = failure(std::errc::io_error);
    const result<long, std::errc> failed_widened(failed);
    EXPECT_EQ(failed_widened.error(), std::errc::io_error);

    int n = 3;
    const result<int&, std::errc> reference(n);
    const result<int, std::errc> copied(reference); // explicit: copies the referent
    n = 4;
    EXPECT_EQ(*copied, 3);
    EXPECT_EQ(*reference, 4);
}

TEST(result, a_result_can_hold_a_result) {
    const result<result_int, std::string_view> outer(parse_count(2));
    ASSERT_TRUE(outer.has_value());
    EXPECT_EQ(**outer, 2);
}

TEST(result, value_or_and_error_or_move_from_an_rvalue) {
    result<std::string, std::string> v(in_place, "value");
    EXPECT_EQ(std::move(v).value_or("other"), "value");

    result<std::string, std::string> e(in_place_failure, "error");
    EXPECT_EQ(e.value_or("other"), "other");
    EXPECT_EQ(std::move(e).error_or("other"), "error");
}

TEST(result, monadic_operations_pass_the_value_category) {
    result<std::string, int> r(in_place, "abc");
    EXPECT_EQ(r.transform([](std::string& s) { return s.size(); }).value(), 3U);
    EXPECT_EQ(std::move(r).transform([](std::string&& s) { return s.size(); }).value(), 3U);

    const result<std::string, int> c(in_place, "abcd");
    EXPECT_EQ(c.transform(&std::string::size).value(), 4U);

    // From an lvalue, a reference result refers to the object the function returned.
    result<std::vector<int>, int> vec(in_place, {1, 2});
    auto first = vec.transform([](std::vector<int>& v) -> int& { return v.front(); });
    static_assert(std::is_same_v<decltype(first), result<int&, int>>);
    *first = 9;
    EXPECT_EQ(vec->front(), 9);

    const result<int, int> failed(in_place_failure, 2);
    EXPECT_EQ(failed.transform_error([](int e) { return std::to_string(e); }).error(), "2");
    EXPECT_EQ(failed.and_then([](int v) -> result<int, int> { return v; }).error(), 2);
}

TEST(result, references_copy_in_value_or) {
    std::string s = "kept";
    result<std::string&, int> r(s);
    EXPECT_EQ(std::move(r).value_or("other"), "kept");
    EXPECT_EQ(s, "kept");
}

TEST(result, compares_with_everything_it_can_hold) {
    const result_int ok = 3;
    const result_int bad = failure("e"sv);
    EXPECT_EQ(ok, 3);
    EXPECT_NE(ok, 4);
    EXPECT_EQ(3, ok); // reversed
    EXPECT_NE(bad, 3);
    EXPECT_EQ(ok, success(3));
    EXPECT_NE(bad, success(3));
    EXPECT_EQ(bad, failure("e"sv));
    EXPECT_NE(ok, failure("e"sv));
    EXPECT_EQ(ok, result_int(3));
    EXPECT_NE(ok, bad);
    EXPECT_EQ(bad, result_int(failure("e"sv)));
    EXPECT_EQ(success(1), success(1L));
    EXPECT_EQ(failure(1), failure(1));
    EXPECT_EQ(success(), success());
}

// --- lifetimes: every state is created and destroyed once -----------------------------------

TEST_F(counting, constructs_and_destroys_each_state) {
    {
        const result<counted, counted> value(in_place, 1);
        const result<counted, counted> error(in_place_failure, 2);
        EXPECT_EQ(counted::s_alive, 2);
        EXPECT_EQ(value->id, 1);
        EXPECT_EQ(error.error().id, 2);
    }
    EXPECT_EQ(counted::s_alive, 0);
}

TEST_F(counting, copy_and_move_keep_the_state) {
    result<counted, counted> value(in_place, 1);
    result<counted, counted> error(in_place_failure, 2);
    const auto value_copy = value;
    const auto error_copy = error;
    EXPECT_EQ(value_copy->id, 1);
    EXPECT_EQ(error_copy.error().id, 2);
    const auto value_moved = std::move(value);
    const auto error_moved = std::move(error);
    EXPECT_EQ(value_moved->id, 1);
    EXPECT_EQ(error_moved.error().id, 2);
    EXPECT_EQ(counted::s_alive, 6);
    EXPECT_EQ(counted::s_copies, 2);
    EXPECT_EQ(counted::s_moves, 2);
}

TEST_F(counting, assignment_between_every_pair_of_states) {
    using r = result<counted, counted>;
    const r v1(in_place, 1);
    const r e1(in_place_failure, 2);

    for (const r* from : {&v1, &e1}) {
        for (const bool to_value : {true, false}) {
            r target = to_value ? r(in_place, 10) : r(in_place_failure, 20);
            target = *from;
            EXPECT_EQ(target.has_value(), from->has_value());
            if (from->has_value()) {
                EXPECT_EQ(target->id, 1);
            } else {
                EXPECT_EQ(target.error().id, 2);
            }
            r moved_to = to_value ? r(in_place, 10) : r(in_place_failure, 20);
            r source = *from;
            moved_to = std::move(source);
            EXPECT_EQ(moved_to.has_value(), from->has_value());
        }
    }
    // v1, e1 and nothing else alive after the loop's temporaries.
    EXPECT_EQ(counted::s_alive, 2);
}

TEST_F(counting, assignment_from_values_errors_and_wrappers) {
    result<counted, counted> r(in_place, 1);
    r = failure(counted(2));
    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error().id, 2);
    r = success(counted(3));
    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r->id, 3);
    r = failure(counted(4));
    r = failure(counted(5)); // error over error
    EXPECT_EQ(r.error().id, 5);
    r = success(counted(6));
    r = success(counted(7)); // value over value
    EXPECT_EQ(r->id, 7);
    EXPECT_EQ(counted::s_alive, 1);
}

TEST_F(counting, emplace_replaces_whatever_it_held) {
    result<counted, counted> r(in_place_failure, 1);
    EXPECT_EQ(r.emplace(2).id, 2);
    EXPECT_EQ(r.emplace(std::initializer_list<int>{1, 2}, 4).id, 7);
    EXPECT_EQ(counted::s_alive, 1);
}

TEST_F(counting, swap_between_every_pair_of_states) {
    using r = result<counted, counted>;
    {
        r a(in_place, 1);
        r b(in_place, 2);
        a.swap(b);
        EXPECT_EQ(a->id, 2);
        EXPECT_EQ(b->id, 1);
    }
    {
        r a(in_place_failure, 1);
        r b(in_place_failure, 2);
        swap(a, b);
        EXPECT_EQ(a.error().id, 2);
        EXPECT_EQ(b.error().id, 1);
    }
    {
        r a(in_place, 1);
        r b(in_place_failure, 2);
        a.swap(b);
        EXPECT_EQ(a.error().id, 2);
        EXPECT_EQ(b->id, 1);
        b.swap(a);
        EXPECT_EQ(a->id, 1);
        EXPECT_EQ(b.error().id, 2);
    }
    EXPECT_EQ(counted::s_alive, 0);
}

TEST_F(counting, void_results_destroy_their_error) {
    result<void, counted> r = failure(counted(1));
    r = success();
    EXPECT_EQ(counted::s_alive, 0);
    r = failure(counted(2));
    EXPECT_EQ(r.error().id, 2);
    result<void, counted> other;
    r.swap(other);
    EXPECT_TRUE(r);
    EXPECT_EQ(other.error().id, 2);
}

// A type whose move constructor can throw. With exceptions, assignment and swap of a result
// of it are absent unless the other type moves without throwing; without them, they exist.
struct may_throw {
    may_throw() = default;
    // User-provided on purpose: the copy operations must not be trivial.
    may_throw(const may_throw& /*other*/) {} // NOLINT(modernize-use-equals-default)
    may_throw(may_throw&& /*other*/) noexcept(false) {}
    may_throw& operator=(const may_throw& /*other*/) { // NOLINT(modernize-use-equals-default)
        return *this;
    }
    may_throw& operator=(may_throw&& /*other*/) noexcept(false) { return *this; }
    ~may_throw() = default;
};

static_assert(std::is_copy_assignable_v<result<may_throw, int>>); // int moves without throwing
static_assert(std::is_copy_assignable_v<result<may_throw, may_throw>> ==
              (FORGE_EXCEPTIONS_ENABLED == 0));
static_assert(std::is_move_assignable_v<result<may_throw, may_throw>> ==
              (FORGE_EXCEPTIONS_ENABLED == 0));

#if FORGE_EXCEPTIONS_ENABLED

struct throws_on_copy {
    int id;
    explicit throws_on_copy(int i) : id(i) {}
    throws_on_copy(const throws_on_copy& other) : id(other.id) {
        if (other.id < 0) {
            throw std::runtime_error("copy");
        }
    }
    throws_on_copy(throws_on_copy&& other) noexcept : id(other.id) {}
    throws_on_copy& operator=(const throws_on_copy&) = default;
    throws_on_copy& operator=(throws_on_copy&&) = default;
    ~throws_on_copy() = default;
};

TEST(result, a_throwing_creation_restores_the_old_state) {
    result<throws_on_copy, int> target(in_place_failure, 5);
    const result<throws_on_copy, int> poisoned(in_place, -1);
    EXPECT_THROW(target = poisoned, std::runtime_error);
    ASSERT_FALSE(target.has_value());
    EXPECT_EQ(target.error(), 5);

    result<throws_on_copy, int> holding(in_place, 1);
    const result<throws_on_copy, int> error(in_place_failure, 2);
    holding = error;
    EXPECT_EQ(holding.error(), 2);
}

#endif

// --- formatting -----------------------------------------------------------------------------

TEST(result, formats_each_kind) {
    EXPECT_EQ(std::format("{}", result_int(42)), "success(42)");
    EXPECT_EQ(std::format("{}", result_int(failure("count cannot be negative"sv))),
              "failure(count cannot be negative)");
    EXPECT_EQ(std::format("{}", result<void, int>()), "success()");
    EXPECT_EQ(std::format("{}", result<void, int>(failure(3))), "failure(3)");
    int n = 5;
    EXPECT_EQ(std::format("{}", result<int&, int>(n)), "success(5)");
    EXPECT_EQ(std::format("{}", success(7)), "success(7)");
    EXPECT_EQ(std::format("{}", success()), "success()");
    EXPECT_EQ(std::format("{}", failure("x"sv)), "failure(x)");
}

struct not_formattable {};

static_assert(std::is_default_constructible_v<std::formatter<result_int, char>>);
static_assert(!std::is_default_constructible_v<std::formatter<result<not_formattable, int>, char>>);
static_assert(!std::is_default_constructible_v<std::formatter<result<int, not_formattable>, char>>);
static_assert(!std::is_default_constructible_v<std::formatter<success<not_formattable>, char>>);
static_assert(!std::is_default_constructible_v<std::formatter<failure<not_formattable>, char>>);
static_assert(std::is_default_constructible_v<std::formatter<result<void, int>, char>>);

// --- wrong-state access is a failed assertion -----------------------------------------------

#if GTEST_HAS_DEATH_TEST && !FORGE_TSAN_ENABLED && FORGE_ASSERTIONS_ENABLED

TEST(result_death, value_of_an_error_reports) {
    const result_int bad = failure("e"sv);
    EXPECT_DEATH(static_cast<void>(bad.value()), "assertion failed: m_has_value");
    EXPECT_DEATH(static_cast<void>(*bad), "assertion failed: m_has_value");
}

TEST(result_death, arrow_of_an_error_reports) {
    const result<std::string, int> bad = failure(1);
    EXPECT_DEATH(static_cast<void>(bad.operator->()), "assertion failed: m_has_value");
}

TEST(result_death, error_of_a_value_reports) {
    const result_int ok = 1;
    EXPECT_DEATH(static_cast<void>(ok.error()), "assertion failed: !m_has_value");
}

TEST(result_death, void_and_reference_results_report_too) {
    const result<void, int> bad = failure(1);
    EXPECT_DEATH(bad.value(), "assertion failed: m_has_value");
    int n = 0;
    const result<int&, int> ok(n);
    EXPECT_DEATH(static_cast<void>(ok.error()), "assertion failed: !m_has_value");
}

#endif

} // namespace
} // namespace forge
