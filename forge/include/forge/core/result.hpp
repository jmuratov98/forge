// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/assert.hpp"
#include "forge/core/config.hpp"
#include "forge/core/in_place.hpp"

#include <concepts>
#include <format>
#include <functional>
#include <initializer_list>
#include <memory>
#include <type_traits>
#include <utility>

// Specified by docs/result.md; [result.*] comments name its stable names.

// result(U&&) and assignment initialize the value with the argument as written, so a conversion
// that -Wconversion would flag is the caller's choice (`return 0;` for a std::size_t value is
// well-formed by [result.reqs]); the warning would otherwise point into this header.
FORGE_WARNINGS_PUSH
FORGE_WARNING_IGNORE_CLANG("-Wconversion")
FORGE_WARNING_IGNORE_CLANG("-Wsign-conversion")
FORGE_WARNING_IGNORE_CLANG("-Wfloat-conversion")
FORGE_WARNING_IGNORE_GCC("-Wconversion")
FORGE_WARNING_IGNORE_GCC("-Wsign-conversion")
FORGE_WARNING_IGNORE_GCC("-Wfloat-conversion")

namespace forge {

// [result.tags], construction tags
struct in_place_failure_t {
    explicit in_place_failure_t() = default;
};
// A tag, spelled like std::unexpect rather than as a g_ global.
inline constexpr in_place_failure_t in_place_failure{}; // NOLINT(readability-identifier-naming)

template <typename T = void>
class success;
template <typename E>
class failure;
template <typename T, typename E>
class result;

namespace detail {

struct value_tag {};
struct error_tag {};

template <typename T, template <typename...> class Template>
inline constexpr bool g_is_specialization_of = false;
template <template <typename...> class Template, typename... Args>
inline constexpr bool g_is_specialization_of<Template<Args...>, Template> = true;

template <typename T>
inline constexpr bool g_is_tag =
    std::is_same_v<T, in_place_t> || std::is_same_v<T, in_place_failure_t>;

template <typename T>
inline constexpr bool g_is_wrapper =
    g_is_specialization_of<T, success> || g_is_specialization_of<T, failure>;

// Names that a result can neither hold nor be built from implicitly ([result.defs] 2.3, 2.4).
template <typename T>
inline constexpr bool g_is_reserved = g_is_tag<T> || g_is_wrapper<T>;

template <typename T>
inline constexpr bool g_is_plain_object =
    std::is_object_v<T> && !std::is_array_v<T> && !std::is_const_v<T> && !std::is_volatile_v<T>;

template <typename T>
inline constexpr bool g_is_valid_value_type =
    std::is_void_v<T> && !std::is_const_v<T> && !std::is_volatile_v<T>;

template <typename T>
    requires g_is_plain_object<T>
inline constexpr bool g_is_valid_value_type<T> = !g_is_reserved<T>;

template <typename T>
inline constexpr bool g_is_valid_value_type<T&> =
    std::is_object_v<T> && !std::is_array_v<T> && !std::is_volatile_v<T> &&
    !g_is_reserved<std::remove_cv_t<T>>;

template <typename E>
inline constexpr bool g_is_valid_error_type =
    g_is_plain_object<E> && !g_is_reserved<E> && !g_is_specialization_of<E, result>;

// [result.reqs] p2. The probe takes its parameter by value, so the argument is copy-list-
// initialized into it, which is what makes narrowing ill-formed.
template <typename X>
void narrowing_probe(X) noexcept;

template <typename U, typename X>
concept narrowing = std::is_object_v<X> && std::is_convertible_v<U, X> &&
                    !requires { narrowing_probe<X>({std::declval<U>()}); };

// Binding R to U needs neither a temporary nor a user-defined conversion.
template <typename U, typename R>
concept binds_directly =
    std::is_lvalue_reference_v<U> &&
    std::is_convertible_v<std::remove_reference_t<U>*, std::remove_reference_t<R>*>;

// [result.reqs] p3 and p4.
template <typename U, typename T, typename E>
inline constexpr bool g_value_implicit = false; // void: there is no value to convert to
template <typename U, typename T, typename E>
    requires std::is_reference_v<T>
inline constexpr bool g_value_implicit<U, T, E> = binds_directly<U, T>;
template <typename U, typename T, typename E>
    requires g_is_plain_object<T>
inline constexpr bool g_value_implicit<U, T, E> =
    std::is_convertible_v<U, T> && (!narrowing<U, T> || !std::is_convertible_v<U, E>);

template <typename G, typename T, typename E>
inline constexpr bool g_error_implicit =
    std::is_convertible_v<G, E> && (std::is_void_v<T> || !std::is_constructible_v<T, G>);

// What the converting constructors forward from a result<U, G> that is const or not, an lvalue or
// not: U& when U is a reference, otherwise const U& for a copy and U for a move.
template <typename U, bool Copy>
using value_forward_t =
    std::conditional_t<std::is_reference_v<U>,
                       U,
                       std::conditional_t<Copy, std::add_lvalue_reference_t<const U>, U>>;
template <typename G, bool Copy>
using error_forward_t = std::conditional_t<Copy, const G&, G>;

// [expected.object.cons] converts-from-any-cvref
template <typename T, typename W>
inline constexpr bool g_converts_from_any_cvref =
    std::is_constructible_v<T, W&> || std::is_constructible_v<T, W> ||
    std::is_constructible_v<T, const W&> || std::is_constructible_v<T, const W> ||
    std::is_convertible_v<W&, T> || std::is_convertible_v<W, T> ||
    std::is_convertible_v<const W&, T> || std::is_convertible_v<const W, T>;

template <typename E, typename W>
inline constexpr bool g_failure_constructible_from =
    std::is_constructible_v<failure<E>, W&> || std::is_constructible_v<failure<E>, W> ||
    std::is_constructible_v<failure<E>, const W&> || std::is_constructible_v<failure<E>, const W>;

// Runs body; if it throws, runs cleanup and rethrows. Without exceptions, nothing can throw.
template <typename Body, typename Cleanup>
constexpr void with_rollback(Body&& body, [[maybe_unused]] Cleanup&& cleanup) {
#if FORGE_EXCEPTIONS_ENABLED
    try {
        body();
    } catch (...) {
        cleanup();
        throw;
    }
#else
    body();
#endif
}

// [result.object.assign] p1, reinit(newval, oldval, args...)
template <typename New, typename Old, typename... Args>
constexpr void reinit(New* newval, Old* oldval, Args&&... args) {
#if FORGE_EXCEPTIONS_ENABLED
    if constexpr (std::is_nothrow_constructible_v<New, Args...>) {
        std::destroy_at(oldval);
        std::construct_at(newval, std::forward<Args>(args)...);
    } else if constexpr (std::is_nothrow_move_constructible_v<New>) {
        New temporary(std::forward<Args>(args)...);
        std::destroy_at(oldval);
        std::construct_at(newval, std::move(temporary));
    } else {
        Old backup(std::move(*oldval));
        std::destroy_at(oldval);
        with_rollback([&] { std::construct_at(newval, std::forward<Args>(args)...); },
                      [&] { std::construct_at(oldval, std::move(backup)); });
    }
#else
    std::destroy_at(oldval);
    std::construct_at(newval, std::forward<Args>(args)...);
#endif
}

// [result.object.monadic]. Self is the result with its cv and ref qualifiers, so that VAL is
// *std::forward<Self>(self) and ERR is std::forward<Self>(self).error().
template <typename Self>
using self_error_t = decltype(std::declval<Self>().error());

template <typename Self, typename F>
struct value_invoke {};
template <typename Self, typename F>
    requires(std::is_void_v<typename std::remove_cvref_t<Self>::value_type> &&
             std::is_invocable_v<F>)
struct value_invoke<Self, F> {
    using type = std::invoke_result_t<F>;
};
template <typename Self, typename F>
    requires(!std::is_void_v<typename std::remove_cvref_t<Self>::value_type> &&
             std::is_invocable_v<F, decltype(*std::declval<Self>())>)
struct value_invoke<Self, F> {
    using type = std::invoke_result_t<F, decltype(*std::declval<Self>())>;
};

template <typename Self, typename F>
struct error_invoke {};
template <typename Self, typename F>
    requires std::is_invocable_v<F, self_error_t<Self>>
struct error_invoke<Self, F> {
    using type = std::invoke_result_t<F, self_error_t<Self>>;
};

template <typename Self,
          bool IsVoid = std::is_void_v<typename std::remove_cvref_t<Self>::value_type>>
inline constexpr bool g_value_constructible = true;
template <typename Self>
inline constexpr bool g_value_constructible<Self, false> =
    std::is_constructible_v<typename std::remove_cvref_t<Self>::value_type,
                            decltype(*std::declval<Self>())>;

template <typename Self, typename F>
concept value_mapper_ok = requires {
    typename value_invoke<Self, F>::type;
} && std::is_constructible_v<typename std::remove_cvref_t<Self>::error_type, self_error_t<Self>>;

template <typename Self, typename F>
concept error_mapper_ok =
    requires { typename error_invoke<Self, F>::type; } && g_value_constructible<Self>;

template <typename F, typename Self>
constexpr decltype(auto) call_with_value(F&& f, Self&& self) {
    if constexpr (std::is_void_v<typename std::remove_cvref_t<Self>::value_type>) {
        return std::invoke(std::forward<F>(f));
    } else {
        return std::invoke(std::forward<F>(f), *std::forward<Self>(self));
    }
}

template <typename Self, typename F>
constexpr auto and_then_impl(Self&& self, F&& f) {
    using value_result = std::remove_cvref_t<typename value_invoke<Self, F>::type>;
    static_assert(g_is_specialization_of<value_result, result> &&
                      std::is_same_v<typename value_result::error_type,
                                     typename std::remove_cvref_t<Self>::error_type>,
                  "and_then: f must return a result with the same error type");
    if (self.has_value()) {
        return value_result(call_with_value(std::forward<F>(f), std::forward<Self>(self)));
    }
    return value_result(in_place_failure, std::forward<Self>(self).error());
}

template <typename Self, typename F>
constexpr auto or_else_impl(Self&& self, F&& f) {
    using value_type = std::remove_cvref_t<Self>::value_type;
    using error_result = std::remove_cvref_t<typename error_invoke<Self, F>::type>;
    static_assert(g_is_specialization_of<error_result, result> &&
                      std::is_same_v<typename error_result::value_type, value_type>,
                  "or_else: f must return a result with the same value type");
    if (self.has_value()) {
        if constexpr (std::is_void_v<value_type>) {
            return error_result(in_place);
        } else {
            return error_result(in_place, *std::forward<Self>(self));
        }
    }
    return error_result(std::invoke(std::forward<F>(f), std::forward<Self>(self).error()));
}

template <typename Self, typename F>
constexpr auto transform_impl(Self&& self, F&& f) {
    using error_type = std::remove_cvref_t<Self>::error_type;
    using mapped = std::remove_cv_t<typename value_invoke<Self, F>::type>;
    static_assert(g_is_valid_value_type<mapped>,
                  "transform: f must return a valid result value type");
    static_assert(std::is_lvalue_reference_v<Self> || !std::is_reference_v<mapped>,
                  "transform: f cannot return a reference from an rvalue result");
    if (!self.has_value()) {
        return result<mapped, error_type>(in_place_failure, std::forward<Self>(self).error());
    }
    if constexpr (std::is_void_v<mapped>) {
        call_with_value(std::forward<F>(f), std::forward<Self>(self));
        return result<void, error_type>();
    } else {
        return result<mapped, error_type>(
            in_place, call_with_value(std::forward<F>(f), std::forward<Self>(self)));
    }
}

template <typename Self, typename F>
constexpr auto transform_error_impl(Self&& self, F&& f) {
    using value_type = std::remove_cvref_t<Self>::value_type;
    using mapped = std::remove_cv_t<typename error_invoke<Self, F>::type>;
    static_assert(g_is_valid_error_type<mapped>,
                  "transform_error: f must return a valid result error type");
    if (self.has_value()) {
        if constexpr (std::is_void_v<value_type>) {
            return result<void, mapped>(in_place);
        } else {
            return result<value_type, mapped>(in_place, *std::forward<Self>(self));
        }
    }
    return result<value_type, mapped>(
        in_place_failure, std::invoke(std::forward<F>(f), std::forward<Self>(self).error()));
}

} // namespace detail

// [result.success], class template success
template <typename T>
class [[nodiscard]] success {
    static_assert(detail::g_is_valid_value_type<T>, "success<T>: T is not a valid value type");

public:
    constexpr success(const success&) = default;
    constexpr success(success&&) = default;

    // Parentheses, not braces, here and below: braces would reject narrowing conversions that
    // is_constructible accepts, and would prefer T's initializer_list constructor.
    template <typename U = T>
        requires(!std::same_as<std::remove_cvref_t<U>, success> &&
                 !std::same_as<std::remove_cvref_t<U>, in_place_t> && std::is_constructible_v<T, U>)
    constexpr explicit success(U&& v) noexcept(std::is_nothrow_constructible_v<T, U>)
        : m_value(std::forward<U>(v)) {}

    template <typename... Args>
        requires(std::is_constructible_v<T, Args...>)
    constexpr explicit success(in_place_t /*tag*/,
                               Args&&... args) noexcept(std::is_nothrow_constructible_v<T, Args...>)
        : m_value(std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<T, std::initializer_list<U>&, Args...>)
    constexpr explicit success(
        in_place_t /*tag*/,
        std::initializer_list<U> list,
        Args&&... args) noexcept(std::is_nothrow_constructible_v<T,
                                                                 std::initializer_list<U>&,
                                                                 Args...>)
        : m_value(list, std::forward<Args>(args)...) {}

    constexpr success& operator=(const success&) = default;
    constexpr success& operator=(success&&) = default;

    constexpr ~success() = default;

    [[nodiscard]] constexpr const T& value() const& noexcept { return m_value; }
    [[nodiscard]] constexpr T& value() & noexcept { return m_value; }
    [[nodiscard]] constexpr const T&& value() const&& noexcept { return std::move(m_value); }
    [[nodiscard]] constexpr T&& value() && noexcept { return std::move(m_value); }

    constexpr void swap(success& other) noexcept(std::is_nothrow_swappable_v<T>)
        requires std::is_swappable_v<T>
    {
        using std::swap;
        swap(m_value, other.m_value);
    }

    friend constexpr void swap(success& x, success& y) noexcept(noexcept(x.swap(y)))
        requires std::is_swappable_v<T>
    {
        x.swap(y);
    }

    // Through value(): the members of success<T2> are private to it.
    template <typename T2>
    friend constexpr bool operator==(const success& x, const success<T2>& y) {
        return x.value() == y.value();
    }

private:
    T m_value;
};

template <typename T>
class [[nodiscard]] success<T&> {
    static_assert(detail::g_is_valid_value_type<T&>, "success<T&>: T& is not a valid value type");

public:
    template <typename U>
        requires detail::binds_directly<U, T&>
    constexpr explicit success(U&& v) noexcept : m_value(std::addressof(v)) {}

    [[nodiscard]] constexpr T& value() const noexcept { return *m_value; }

    template <typename T2>
    friend constexpr bool operator==(const success& x, const success<T2>& y) {
        return x.value() == y.value();
    }

private:
    T* m_value;
};

template <>
class [[nodiscard]] success<void> {
public:
    constexpr success() noexcept = default;

    friend constexpr bool operator==(success /*x*/, success /*y*/) noexcept { return true; }
};

template <typename T>
success(T) -> success<T>;

success() -> success<void>;

// [result.failure], class template failure
template <typename E>
class [[nodiscard]] failure {
    static_assert(detail::g_is_valid_error_type<E>, "failure<E>: E is not a valid error type");

public:
    constexpr failure(const failure&) = default;
    constexpr failure(failure&&) = default;

    template <typename G = E>
        requires(!std::same_as<std::remove_cvref_t<G>, failure> &&
                 !std::same_as<std::remove_cvref_t<G>, in_place_t> && std::is_constructible_v<E, G>)
    constexpr explicit failure(G&& e) noexcept(std::is_nothrow_constructible_v<E, G>)
        : m_error(std::forward<G>(e)) {}

    template <typename... Args>
        requires(std::is_constructible_v<E, Args...>)
    constexpr explicit failure(in_place_t /*tag*/,
                               Args&&... args) noexcept(std::is_nothrow_constructible_v<E, Args...>)
        : m_error(std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<E, std::initializer_list<U>&, Args...>)
    constexpr explicit failure(
        in_place_t /*tag*/,
        std::initializer_list<U> list,
        Args&&... args) noexcept(std::is_nothrow_constructible_v<E,
                                                                 std::initializer_list<U>&,
                                                                 Args...>)
        : m_error(list, std::forward<Args>(args)...) {}

    constexpr failure& operator=(const failure&) = default;
    constexpr failure& operator=(failure&&) = default;

    constexpr ~failure() = default;

    [[nodiscard]] constexpr const E& error() const& noexcept { return m_error; }
    [[nodiscard]] constexpr E& error() & noexcept { return m_error; }
    [[nodiscard]] constexpr const E&& error() const&& noexcept { return std::move(m_error); }
    [[nodiscard]] constexpr E&& error() && noexcept { return std::move(m_error); }

    constexpr void swap(failure& other) noexcept(std::is_nothrow_swappable_v<E>)
        requires std::is_swappable_v<E>
    {
        using std::swap;
        swap(m_error, other.m_error);
    }

    friend constexpr void swap(failure& x, failure& y) noexcept(noexcept(x.swap(y)))
        requires std::is_swappable_v<E>
    {
        x.swap(y);
    }

    template <typename E2>
    friend constexpr bool operator==(const failure& x, const failure<E2>& y) {
        return x.error() == y.error();
    }

private:
    E m_error;
};

template <typename E>
failure(E) -> failure<E>;

// [result.object], class template result. [[nodiscard]] goes on the definitions: on a declaration
// of a specialization that is not a definition, GCC ignores it with a warning.
//
// The special members come in pairs: a defaulted one for when T and E make it trivial, and one
// that is user-provided for when they do not (P0848, conditionally trivial special members), each
// constrained so that exactly one is eligible.
template <typename T, typename E>
class [[nodiscard]] result {
    static_assert(detail::g_is_valid_value_type<T> && !std::is_void_v<T> && !std::is_reference_v<T>,
                  "result<T, E>: T is not a valid value type");
    static_assert(detail::g_is_valid_error_type<E>, "result<T, E>: E is not a valid error type");

    template <typename U>
    static constexpr bool g_value_arg =
        !detail::g_is_reserved<std::remove_cvref_t<U>> &&
        !std::is_same_v<std::remove_cvref_t<U>, result> &&
        (!std::is_same_v<T, bool> ||
         !detail::g_is_specialization_of<std::remove_cvref_t<U>, forge::result>) &&
        std::is_constructible_v<T, U>;

    template <typename G>
    static constexpr bool g_error_arg =
        !detail::g_is_reserved<std::remove_cvref_t<G>> &&
        !detail::g_is_specialization_of<std::remove_cvref_t<G>, forge::result> &&
        detail::g_error_implicit<G, T, E>;

    template <typename W, typename UF, typename GF>
    static constexpr bool g_converting_arg =
        !std::is_void_v<typename W::value_type> && std::is_constructible_v<T, UF> &&
        std::is_constructible_v<E, GF> &&
        (std::is_same_v<T, bool> || !detail::g_converts_from_any_cvref<T, W>) &&
        !detail::g_failure_constructible_from<E, W>;

    static constexpr bool g_trivially_destructible =
        std::is_trivially_destructible_v<T> && std::is_trivially_destructible_v<E>;
    static constexpr bool g_trivially_copy_constructible =
        std::is_trivially_copy_constructible_v<T> && std::is_trivially_copy_constructible_v<E>;
    static constexpr bool g_trivially_move_constructible =
        std::is_trivially_move_constructible_v<T> && std::is_trivially_move_constructible_v<E>;
    static constexpr bool g_trivially_copy_assignable =
        g_trivially_copy_constructible && g_trivially_destructible &&
        std::is_trivially_copy_assignable_v<T> && std::is_trivially_copy_assignable_v<E>;
    static constexpr bool g_trivially_move_assignable =
        g_trivially_move_constructible && g_trivially_destructible &&
        std::is_trivially_move_assignable_v<T> && std::is_trivially_move_assignable_v<E>;

    // [result.object.assign] p2
    static constexpr bool g_may_reinit = FORGE_EXCEPTIONS_ENABLED == 0 ||
                                         std::is_nothrow_move_constructible_v<T> ||
                                         std::is_nothrow_move_constructible_v<E>;

    // The two states are created in the member initializers, so that a constant evaluation sees
    // the union member become active in the constructor.
    template <typename... Args>
    constexpr explicit result(detail::value_tag /*tag*/, Args&&... args)
        : m_has_value(true), m_value(std::forward<Args>(args)...) {}

    template <typename... Args>
    constexpr explicit result(detail::error_tag /*tag*/, Args&&... args)
        : m_has_value(false), m_error(std::forward<Args>(args)...) {}

public:
    using value_type = T;
    using error_type = E;

    template <typename U>
    using rebind = result<U, error_type>;

    // [result.object.ctor], constructors
    constexpr result(const result& other)
        requires g_trivially_copy_constructible
    = default;

    constexpr result(const result& other)
        requires(std::is_copy_constructible_v<T> && std::is_copy_constructible_v<E> &&
                 !g_trivially_copy_constructible)
        : m_has_value(other.m_has_value) {
        if (m_has_value) {
            std::construct_at(std::addressof(m_value), other.m_value);
        } else {
            std::construct_at(std::addressof(m_error), other.m_error);
        }
    }

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<T> &&
                                              std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_constructible
    = default;

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<T> &&
                                              std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<T> && std::is_move_constructible_v<E> &&
                 !g_trivially_move_constructible)
        : m_has_value(other.m_has_value) {
        if (m_has_value) {
            std::construct_at(std::addressof(m_value), std::move(other.m_value));
        } else {
            std::construct_at(std::addressof(m_error), std::move(other.m_error));
        }
    }

    template <typename U>
        requires g_value_arg<U>
    constexpr explicit(!detail::g_value_implicit<U, T, E>) result(U&& v)
        : result(detail::value_tag{}, std::forward<U>(v)) {}

    // Implicit on purpose: `return "message";` is an error ([result.reqs] p4).
    template <typename G>
        requires g_error_arg<G>
    constexpr result(G&& e) // NOLINT(misc-explicit-constructor)
        : result(detail::error_tag{}, std::forward<G>(e)) {}

    template <typename U, typename G>
        requires g_converting_arg<forge::result<U, G>,
                                  detail::value_forward_t<U, true>,
                                  detail::error_forward_t<G, true>>
    constexpr explicit(std::is_reference_v<U> ||
                       !std::is_convertible_v<detail::value_forward_t<U, true>, T> ||
                       !std::is_convertible_v<detail::error_forward_t<G, true>, E>)
        result(const forge::result<U, G>& other)
        : m_has_value(other.has_value()) {
        construct_from(other);
    }

    template <typename U, typename G>
        requires g_converting_arg<forge::result<U, G>,
                                  detail::value_forward_t<U, false>,
                                  detail::error_forward_t<G, false>>
    constexpr explicit(std::is_reference_v<U> ||
                       !std::is_convertible_v<detail::value_forward_t<U, false>, T> ||
                       !std::is_convertible_v<detail::error_forward_t<G, false>, E>)
        result(forge::result<U, G>&& other)
        : m_has_value(other.has_value()) {
        construct_from(std::move(other));
    }

    template <typename U>
        requires(!std::is_void_v<U> && std::is_constructible_v<T, detail::value_forward_t<U, true>>)
    constexpr explicit(std::is_reference_v<U> ||
                       !std::is_convertible_v<detail::value_forward_t<U, true>, T>)
        result(const success<U>& s)
        : result(detail::value_tag{}, s.value()) {}

    template <typename U>
        requires(!std::is_void_v<U> &&
                 std::is_constructible_v<T, detail::value_forward_t<U, false>>)
    constexpr explicit(std::is_reference_v<U> ||
                       !std::is_convertible_v<detail::value_forward_t<U, false>, T>)
        result(success<U>&& s)
        : result(detail::value_tag{}, std::move(s).value()) {}

    template <typename G>
        requires(std::is_constructible_v<E, const G&>)
    constexpr explicit(!std::is_convertible_v<const G&, E>) result(const failure<G>& f)
        : result(detail::error_tag{}, f.error()) {}

    template <typename G>
        requires(std::is_constructible_v<E, G>)
    constexpr explicit(!std::is_convertible_v<G, E>) result(failure<G>&& f)
        : result(detail::error_tag{}, std::move(f).error()) {}

    template <typename... Args>
        requires(std::is_constructible_v<T, Args...>)
    constexpr explicit result(in_place_t /*tag*/, Args&&... args)
        : result(detail::value_tag{}, std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<T, std::initializer_list<U>&, Args...>)
    constexpr explicit result(in_place_t /*tag*/, std::initializer_list<U> list, Args&&... args)
        : result(detail::value_tag{}, list, std::forward<Args>(args)...) {}

    template <typename... Args>
        requires(std::is_constructible_v<E, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/, Args&&... args)
        : result(detail::error_tag{}, std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<E, std::initializer_list<U>&, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/,
                              std::initializer_list<U> list,
                              Args&&... args)
        : result(detail::error_tag{}, list, std::forward<Args>(args)...) {}

    constexpr ~result()
        requires g_trivially_destructible
    = default;

    constexpr ~result()
        requires(!g_trivially_destructible)
    {
        if (m_has_value) {
            std::destroy_at(std::addressof(m_value));
        } else {
            std::destroy_at(std::addressof(m_error));
        }
    }

    // [result.object.assign], assignment
    constexpr result& operator=(const result& other)
        requires g_trivially_copy_assignable
    = default;

    constexpr result& operator=(const result& other)
        requires(std::is_copy_assignable_v<T> && std::is_copy_constructible_v<T> &&
                 std::is_copy_assignable_v<E> && std::is_copy_constructible_v<E> && g_may_reinit &&
                 !g_trivially_copy_assignable)
    {
        assign_from(other);
        return *this;
    }

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<T> &&
                                                         std::is_nothrow_move_constructible_v<T> &&
                                                         std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_assignable
    = default;

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<T> &&
                                                         std::is_nothrow_move_constructible_v<T> &&
                                                         std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<T> && std::is_move_assignable_v<T> &&
                 std::is_move_constructible_v<E> && std::is_move_assignable_v<E> && g_may_reinit &&
                 !g_trivially_move_assignable)
    {
        assign_from(std::move(other));
        return *this;
    }

    template <typename U>
        requires(g_value_arg<U> && detail::g_value_implicit<U, T, E> &&
                 std::is_assignable_v<T&, U> &&
                 (std::is_nothrow_constructible_v<T, U> || g_may_reinit))
    constexpr result& operator=(U&& v) {
        assign_value(std::forward<U>(v));
        return *this;
    }

    template <typename G>
        requires(g_error_arg<G> && std::is_assignable_v<E&, G> &&
                 (std::is_nothrow_constructible_v<E, G> || g_may_reinit))
    constexpr result& operator=(G&& e) {
        assign_error(std::forward<G>(e));
        return *this;
    }

    template <typename U>
        requires(!std::is_void_v<U> &&
                 std::is_constructible_v<T, detail::value_forward_t<U, true>> &&
                 std::is_assignable_v<T&, detail::value_forward_t<U, true>> &&
                 (std::is_nothrow_constructible_v<T, detail::value_forward_t<U, true>> ||
                  g_may_reinit))
    constexpr result& operator=(const success<U>& s) {
        assign_value(s.value());
        return *this;
    }

    template <typename U>
        requires(!std::is_void_v<U> &&
                 std::is_constructible_v<T, detail::value_forward_t<U, false>> &&
                 std::is_assignable_v<T&, detail::value_forward_t<U, false>> &&
                 (std::is_nothrow_constructible_v<T, detail::value_forward_t<U, false>> ||
                  g_may_reinit))
    constexpr result& operator=(success<U>&& s) {
        assign_value(std::move(s).value());
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, const G&> && std::is_assignable_v<E&, const G&> &&
                 (std::is_nothrow_constructible_v<E, const G&> || g_may_reinit))
    constexpr result& operator=(const failure<G>& f) {
        assign_error(f.error());
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, G> && std::is_assignable_v<E&, G> &&
                 (std::is_nothrow_constructible_v<E, G> || g_may_reinit))
    constexpr result& operator=(failure<G>&& f) {
        assign_error(std::move(f).error());
        return *this;
    }

    template <typename... Args>
        requires(std::is_constructible_v<T, Args...> &&
                 (FORGE_EXCEPTIONS_ENABLED == 0 || std::is_nothrow_constructible_v<T, Args...>))
    constexpr T& emplace(Args&&... args) noexcept {
        destroy();
        std::construct_at(std::addressof(m_value), std::forward<Args>(args)...);
        m_has_value = true;
        return m_value;
    }

    template <typename U, typename... Args>
        requires(std::is_constructible_v<T, std::initializer_list<U>&, Args...> &&
                 (FORGE_EXCEPTIONS_ENABLED == 0 ||
                  std::is_nothrow_constructible_v<T, std::initializer_list<U>&, Args...>))
    constexpr T& emplace(std::initializer_list<U> list, Args&&... args) noexcept {
        destroy();
        std::construct_at(std::addressof(m_value), list, std::forward<Args>(args)...);
        m_has_value = true;
        return m_value;
    }

    // [result.object.swap], swap
    constexpr void swap(result& other) noexcept(std::is_nothrow_move_constructible_v<T> &&
                                                std::is_nothrow_swappable_v<T> &&
                                                std::is_nothrow_move_constructible_v<E> &&
                                                std::is_nothrow_swappable_v<E>)
        requires(std::is_swappable_v<T> && std::is_swappable_v<E> &&
                 std::is_move_constructible_v<T> && std::is_move_constructible_v<E> && g_may_reinit)
    {
        using std::swap;
        if (m_has_value && other.m_has_value) {
            swap(m_value, other.m_value);
        } else if (!m_has_value && !other.m_has_value) {
            swap(m_error, other.m_error);
        } else if (m_has_value) {
            exchange_with_error(other);
        } else {
            other.exchange_with_error(*this);
        }
    }

    friend constexpr void swap(result& x, result& y) noexcept(noexcept(x.swap(y)))
        requires requires { x.swap(y); }
    {
        x.swap(y);
    }

    // [result.object.obs], observers
    [[nodiscard]] constexpr const T* operator->() const noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::addressof(m_value);
    }

    [[nodiscard]] constexpr T* operator->() noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::addressof(m_value);
    }

    [[nodiscard]] constexpr const T& operator*() const& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return m_value;
    }

    [[nodiscard]] constexpr T& operator*() & noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return m_value;
    }

    [[nodiscard]] constexpr const T&& operator*() const&& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::move(m_value);
    }

    [[nodiscard]] constexpr T&& operator*() && noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::move(m_value);
    }

    [[nodiscard]] constexpr explicit operator bool() const noexcept { return m_has_value; }
    [[nodiscard]] constexpr bool has_value() const noexcept { return m_has_value; }

    [[nodiscard]] constexpr const T& value() const& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return m_value;
    }

    [[nodiscard]] constexpr T& value() & noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return m_value;
    }

    [[nodiscard]] constexpr const T&& value() const&& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::move(m_value);
    }

    [[nodiscard]] constexpr T&& value() && noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return std::move(m_value);
    }

    [[nodiscard]] constexpr const E& error() const& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr E& error() & noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr const E&& error() const&& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    [[nodiscard]] constexpr E&& error() && noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    template <typename U>
    [[nodiscard]] constexpr T value_or(U&& fallback) const& {
        static_assert(std::is_convertible_v<U, T> && std::is_copy_constructible_v<T>,
                      "value_or: U must convert to T, and T must be copy constructible");
        if (m_has_value) {
            return m_value;
        }
        return static_cast<T>(std::forward<U>(fallback));
    }

    template <typename U>
    [[nodiscard]] constexpr T value_or(U&& fallback) && {
        static_assert(std::is_convertible_v<U, T> && std::is_move_constructible_v<T>,
                      "value_or: U must convert to T, and T must be move constructible");
        if (m_has_value) {
            return std::move(m_value);
        }
        return static_cast<T>(std::forward<U>(fallback));
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) const& {
        static_assert(std::is_convertible_v<G, E> && std::is_copy_constructible_v<E>,
                      "error_or: G must convert to E, and E must be copy constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return m_error;
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) && {
        static_assert(std::is_convertible_v<G, E> && std::is_move_constructible_v<E>,
                      "error_or: G must convert to E, and E must be move constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return std::move(m_error);
    }

    // [result.object.monadic], monadic operations
    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto and_then(F&& f) & {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto and_then(F&& f) && {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto and_then(F&& f) const& {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto and_then(F&& f) const&& {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto or_else(F&& f) & {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto or_else(F&& f) && {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto or_else(F&& f) const& {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto or_else(F&& f) const&& {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto transform(F&& f) & {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto transform(F&& f) && {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto transform(F&& f) const& {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto transform(F&& f) const&& {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto transform_error(F&& f) & {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto transform_error(F&& f) && {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto transform_error(F&& f) const& {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto transform_error(F&& f) const&& {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    // [result.object.eq], equality operators
    template <typename T2, typename E2>
        requires(!std::is_void_v<T2> &&
                 requires(const result& a, const forge::result<T2, E2>& b) {
                     { *a == *b } -> std::convertible_to<bool>;
                     { a.error() == b.error() } -> std::convertible_to<bool>;
                 })
    friend constexpr bool operator==(const result& x, const forge::result<T2, E2>& y) {
        if (x.has_value() != y.has_value()) {
            return false;
        }
        return x.has_value() ? static_cast<bool>(*x == *y)
                             : static_cast<bool>(x.error() == y.error());
    }

    template <typename T2>
        requires(!detail::g_is_specialization_of<T2, forge::result> && !detail::g_is_wrapper<T2> &&
                 requires(const result& a, const T2& b) {
                     { *a == b } -> std::convertible_to<bool>;
                 })
    friend constexpr bool operator==(const result& x, const T2& v) {
        return x.has_value() && static_cast<bool>(*x == v);
    }

    template <typename T2>
        requires requires(const result& a, const success<T2>& b) {
            { *a == b.value() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const success<T2>& s) {
        return x.has_value() && static_cast<bool>(*x == s.value());
    }

    template <typename E2>
        requires requires(const result& a, const failure<E2>& b) {
            { a.error() == b.error() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const failure<E2>& f) {
        return !x.has_value() && static_cast<bool>(x.error() == f.error());
    }

private:
    constexpr void destroy() noexcept {
        if (m_has_value) {
            std::destroy_at(std::addressof(m_value));
        } else {
            std::destroy_at(std::addressof(m_error));
        }
    }

    // Builds the state of a result<U, G> that holds the same alternative as *this has recorded.
    template <typename W>
    constexpr void construct_from(W&& other) {
        if (m_has_value) {
            std::construct_at(std::addressof(m_value), *std::forward<W>(other));
        } else {
            std::construct_at(std::addressof(m_error), std::forward<W>(other).error());
        }
    }

    template <typename W>
    constexpr void assign_from(W&& other) {
        if (m_has_value && other.m_has_value) {
            m_value = *std::forward<W>(other);
        } else if (m_has_value) {
            detail::reinit(
                std::addressof(m_error), std::addressof(m_value), std::forward<W>(other).m_error);
            m_has_value = false;
        } else if (other.m_has_value) {
            detail::reinit(
                std::addressof(m_value), std::addressof(m_error), std::forward<W>(other).m_value);
            m_has_value = true;
        } else {
            m_error = std::forward<W>(other).m_error;
        }
    }

    template <typename V>
    constexpr void assign_value(V&& v) {
        if (m_has_value) {
            m_value = std::forward<V>(v);
        } else {
            detail::reinit(std::addressof(m_value), std::addressof(m_error), std::forward<V>(v));
            m_has_value = true;
        }
    }

    template <typename G>
    constexpr void assign_error(G&& e) {
        if (!m_has_value) {
            m_error = std::forward<G>(e);
        } else {
            detail::reinit(std::addressof(m_error), std::addressof(m_value), std::forward<G>(e));
            m_has_value = false;
        }
    }

    // [expected.object.swap]: *this holds a value and `rhs` an error; afterwards the other way
    // round. If a move throws, both are left as they were.
    constexpr void exchange_with_error(result& rhs) {
        if constexpr (std::is_nothrow_move_constructible_v<E>) {
            E temporary(std::move(rhs.m_error));
            std::destroy_at(std::addressof(rhs.m_error));
            detail::with_rollback(
                [&] {
                    std::construct_at(std::addressof(rhs.m_value), std::move(m_value));
                    std::destroy_at(std::addressof(m_value));
                    std::construct_at(std::addressof(m_error), std::move(temporary));
                },
                [&] { std::construct_at(std::addressof(rhs.m_error), std::move(temporary)); });
        } else {
            T temporary(std::move(m_value));
            std::destroy_at(std::addressof(m_value));
            detail::with_rollback(
                [&] {
                    std::construct_at(std::addressof(m_error), std::move(rhs.m_error));
                    std::destroy_at(std::addressof(rhs.m_error));
                    std::construct_at(std::addressof(rhs.m_value), std::move(temporary));
                },
                [&] { std::construct_at(std::addressof(m_value), std::move(temporary)); });
        }
        m_has_value = false;
        rhs.m_has_value = true;
    }

    bool m_has_value;
    union {
        T m_value;
        E m_error;
    };
};

// [result.void], partial specialization for void values. Every condition on T of [result.object]
// holds, so everything depends on E alone.
template <typename E>
class [[nodiscard]] result<void, E> {
    static_assert(detail::g_is_valid_error_type<E>, "result<void, E>: E is not a valid error type");

    template <typename G>
    static constexpr bool g_error_arg =
        !detail::g_is_reserved<std::remove_cvref_t<G>> &&
        !detail::g_is_specialization_of<std::remove_cvref_t<G>, forge::result> &&
        std::is_convertible_v<G, E>;

    template <typename W, typename GF>
    static constexpr bool g_converting_arg =
        std::is_void_v<typename W::value_type> && std::is_constructible_v<E, GF> &&
        !detail::g_failure_constructible_from<E, W>;

    static constexpr bool g_trivially_destructible = std::is_trivially_destructible_v<E>;
    static constexpr bool g_trivially_copy_constructible =
        std::is_trivially_copy_constructible_v<E>;
    static constexpr bool g_trivially_move_constructible =
        std::is_trivially_move_constructible_v<E>;
    static constexpr bool g_trivially_copy_assignable = g_trivially_copy_constructible &&
                                                        g_trivially_destructible &&
                                                        std::is_trivially_copy_assignable_v<E>;
    static constexpr bool g_trivially_move_assignable = g_trivially_move_constructible &&
                                                        g_trivially_destructible &&
                                                        std::is_trivially_move_assignable_v<E>;

    template <typename... Args>
    constexpr explicit result(detail::error_tag /*tag*/, Args&&... args)
        : m_has_value(false), m_error(std::forward<Args>(args)...) {}

public:
    using value_type = void;
    using error_type = E;

    template <typename U>
    using rebind = result<U, error_type>;

    // [result.object.ctor], constructors
    constexpr result() noexcept : m_has_value(true) {}

    constexpr result(const result& other)
        requires g_trivially_copy_constructible
    = default;

    constexpr result(const result& other)
        requires(std::is_copy_constructible_v<E> && !g_trivially_copy_constructible)
        : m_has_value(other.m_has_value) {
        if (!m_has_value) {
            std::construct_at(std::addressof(m_error), other.m_error);
        }
    }

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_constructible
    = default;

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<E> && !g_trivially_move_constructible)
        : m_has_value(other.m_has_value) {
        if (!m_has_value) {
            std::construct_at(std::addressof(m_error), std::move(other.m_error));
        }
    }

    // Implicit on purpose: `return "message";` is an error ([result.reqs] p4).
    template <typename G>
        requires g_error_arg<G>
    constexpr result(G&& e) // NOLINT(misc-explicit-constructor)
        : result(detail::error_tag{}, std::forward<G>(e)) {}

    template <typename U, typename G>
        requires g_converting_arg<forge::result<U, G>, detail::error_forward_t<G, true>>
    constexpr explicit(!std::is_convertible_v<detail::error_forward_t<G, true>, E>)
        result(const forge::result<U, G>& other)
        : m_has_value(other.has_value()) {
        if (!m_has_value) {
            std::construct_at(std::addressof(m_error), other.error());
        }
    }

    template <typename U, typename G>
        requires g_converting_arg<forge::result<U, G>, detail::error_forward_t<G, false>>
    constexpr explicit(!std::is_convertible_v<detail::error_forward_t<G, false>, E>)
        result(forge::result<U, G>&& other)
        : m_has_value(other.has_value()) {
        if (!m_has_value) {
            std::construct_at(std::addressof(m_error), std::move(other).error());
        }
    }

    constexpr result(success<void> /*s*/) noexcept // NOLINT(misc-explicit-constructor)
        : m_has_value(true) {}

    template <typename G>
        requires(std::is_constructible_v<E, const G&>)
    constexpr explicit(!std::is_convertible_v<const G&, E>) result(const failure<G>& f)
        : result(detail::error_tag{}, f.error()) {}

    template <typename G>
        requires(std::is_constructible_v<E, G>)
    constexpr explicit(!std::is_convertible_v<G, E>) result(failure<G>&& f)
        : result(detail::error_tag{}, std::move(f).error()) {}

    constexpr explicit result(in_place_t /*tag*/) noexcept : m_has_value(true) {}

    template <typename... Args>
        requires(std::is_constructible_v<E, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/, Args&&... args)
        : result(detail::error_tag{}, std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<E, std::initializer_list<U>&, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/,
                              std::initializer_list<U> list,
                              Args&&... args)
        : result(detail::error_tag{}, list, std::forward<Args>(args)...) {}

    constexpr ~result()
        requires g_trivially_destructible
    = default;

    constexpr ~result()
        requires(!g_trivially_destructible)
    {
        if (!m_has_value) {
            std::destroy_at(std::addressof(m_error));
        }
    }

    // [result.object.assign], assignment
    constexpr result& operator=(const result& other)
        requires g_trivially_copy_assignable
    = default;

    constexpr result& operator=(const result& other)
        requires(std::is_copy_assignable_v<E> && std::is_copy_constructible_v<E> &&
                 !g_trivially_copy_assignable)
    {
        assign_from(other);
        return *this;
    }

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_assignable
    = default;

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<E> && std::is_move_assignable_v<E> &&
                 !g_trivially_move_assignable)
    {
        assign_from(std::move(other));
        return *this;
    }

    template <typename G>
        requires g_error_arg<G> && std::is_assignable_v<E&, G> && std::is_constructible_v<E, G>
    constexpr result& operator=(G&& e) {
        assign_error(std::forward<G>(e));
        return *this;
    }

    constexpr result& operator=(success<void> /*s*/) noexcept {
        emplace();
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, const G&> && std::is_assignable_v<E&, const G&>)
    constexpr result& operator=(const failure<G>& f) {
        assign_error(f.error());
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, G> && std::is_assignable_v<E&, G>)
    constexpr result& operator=(failure<G>&& f) {
        assign_error(std::move(f).error());
        return *this;
    }

    constexpr void emplace() noexcept {
        if (!m_has_value) {
            std::destroy_at(std::addressof(m_error));
            m_has_value = true;
        }
    }

    // [result.object.swap], swap
    constexpr void swap(result& other) noexcept(std::is_nothrow_move_constructible_v<E> &&
                                                std::is_nothrow_swappable_v<E>)
        requires(std::is_swappable_v<E> && std::is_move_constructible_v<E>)
    {
        using std::swap;
        if (m_has_value && other.m_has_value) {
            return;
        }
        if (!m_has_value && !other.m_has_value) {
            swap(m_error, other.m_error);
        } else if (m_has_value) {
            std::construct_at(std::addressof(m_error), std::move(other.m_error));
            std::destroy_at(std::addressof(other.m_error));
            m_has_value = false;
            other.m_has_value = true;
        } else {
            other.swap(*this);
        }
    }

    friend constexpr void swap(result& x, result& y) noexcept(noexcept(x.swap(y)))
        requires requires { x.swap(y); }
    {
        x.swap(y);
    }

    // [result.object.obs], observers
    constexpr void operator*() const noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
    }

    [[nodiscard]] constexpr explicit operator bool() const noexcept { return m_has_value; }
    [[nodiscard]] constexpr bool has_value() const noexcept { return m_has_value; }

    constexpr void value() const noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
    }

    [[nodiscard]] constexpr const E& error() const& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr E& error() & noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr const E&& error() const&& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    [[nodiscard]] constexpr E&& error() && noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) const& {
        static_assert(std::is_convertible_v<G, E> && std::is_copy_constructible_v<E>,
                      "error_or: G must convert to E, and E must be copy constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return m_error;
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) && {
        static_assert(std::is_convertible_v<G, E> && std::is_move_constructible_v<E>,
                      "error_or: G must convert to E, and E must be move constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return std::move(m_error);
    }

    // [result.object.monadic], monadic operations
    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto and_then(F&& f) & {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto and_then(F&& f) && {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto and_then(F&& f) const& {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto and_then(F&& f) const&& {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto or_else(F&& f) & {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto or_else(F&& f) && {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto or_else(F&& f) const& {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto or_else(F&& f) const&& {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto transform(F&& f) & {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto transform(F&& f) && {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto transform(F&& f) const& {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto transform(F&& f) const&& {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto transform_error(F&& f) & {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto transform_error(F&& f) && {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto transform_error(F&& f) const& {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto transform_error(F&& f) const&& {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    // [result.object.eq], equality operators
    template <typename E2>
        requires requires(const result& a, const forge::result<void, E2>& b) {
            { a.error() == b.error() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const forge::result<void, E2>& y) {
        if (x.has_value() != y.has_value()) {
            return false;
        }
        return x.has_value() || static_cast<bool>(x.error() == y.error());
    }

    friend constexpr bool operator==(const result& x, success<void> /*s*/) noexcept {
        return x.has_value();
    }

    template <typename E2>
        requires requires(const result& a, const failure<E2>& b) {
            { a.error() == b.error() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const failure<E2>& f) {
        return !x.has_value() && static_cast<bool>(x.error() == f.error());
    }

private:
    template <typename W>
    constexpr void assign_from(W&& other) {
        if (m_has_value && other.m_has_value) {
            return;
        }
        if (m_has_value) {
            std::construct_at(std::addressof(m_error), std::forward<W>(other).m_error);
            m_has_value = false;
        } else if (other.m_has_value) {
            std::destroy_at(std::addressof(m_error));
            m_has_value = true;
        } else {
            m_error = std::forward<W>(other).m_error;
        }
    }

    template <typename G>
    constexpr void assign_error(G&& e) {
        if (m_has_value) {
            std::construct_at(std::addressof(m_error), std::forward<G>(e));
            m_has_value = false;
        } else {
            m_error = std::forward<G>(e);
        }
    }

    bool m_has_value;
    union {
        E m_error;
    };
};

// [result.ref], partial specialization for reference values. The value is a pointer; the
// conditions on it are those of a trivially copyable, nothrow movable type.
template <typename T, typename E>
class [[nodiscard]] result<T&, E> {
    static_assert(detail::g_is_valid_value_type<T&>, "result<T&, E>: T& is not a valid value type");
    static_assert(detail::g_is_valid_error_type<E>, "result<T&, E>: E is not a valid error type");

    template <typename U>
    static constexpr bool g_value_arg =
        !detail::g_is_reserved<std::remove_cvref_t<U>> &&
        !std::is_same_v<std::remove_cvref_t<U>, result> && detail::binds_directly<U, T&>;

    // Would bind a temporary (or convert): ill-formed instead of an error ([result.ref] (1.2)).
    template <typename U>
    static constexpr bool g_dangling_arg =
        !detail::g_is_reserved<std::remove_cvref_t<U>> &&
        !detail::g_is_specialization_of<std::remove_cvref_t<U>, forge::result> &&
        std::is_constructible_v<T&, U> && !detail::binds_directly<U, T&>;

    template <typename G>
    static constexpr bool g_error_arg =
        !detail::g_is_reserved<std::remove_cvref_t<G>> &&
        !detail::g_is_specialization_of<std::remove_cvref_t<G>, forge::result> &&
        detail::g_error_implicit<G, T&, E>;

    template <typename W, typename GF>
    static constexpr bool g_converting_arg =
        std::is_convertible_v<typename W::value_type, T&> && std::is_constructible_v<E, GF> &&
        !detail::g_failure_constructible_from<E, W>;

    static constexpr bool g_trivially_destructible = std::is_trivially_destructible_v<E>;
    static constexpr bool g_trivially_copy_constructible =
        std::is_trivially_copy_constructible_v<E>;
    static constexpr bool g_trivially_move_constructible =
        std::is_trivially_move_constructible_v<E>;
    static constexpr bool g_trivially_copy_assignable = g_trivially_copy_constructible &&
                                                        g_trivially_destructible &&
                                                        std::is_trivially_copy_assignable_v<E>;
    static constexpr bool g_trivially_move_assignable = g_trivially_move_constructible &&
                                                        g_trivially_destructible &&
                                                        std::is_trivially_move_assignable_v<E>;

    constexpr explicit result(detail::value_tag /*tag*/, T* pointer) noexcept
        : m_has_value(true), m_value(pointer) {}

    template <typename... Args>
    constexpr explicit result(detail::error_tag /*tag*/, Args&&... args)
        : m_has_value(false), m_error(std::forward<Args>(args)...) {}

public:
    using value_type = T&;
    using error_type = E;

    template <typename U>
    using rebind = result<U, error_type>;

    // [result.object.ctor], constructors
    constexpr result(const result& other)
        requires g_trivially_copy_constructible
    = default;

    constexpr result(const result& other)
        requires(std::is_copy_constructible_v<E> && !g_trivially_copy_constructible)
        : m_has_value(other.m_has_value) {
        if (m_has_value) {
            m_value = other.m_value;
        } else {
            std::construct_at(std::addressof(m_error), other.m_error);
        }
    }

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_constructible
    = default;

    constexpr result(result&& other) noexcept(std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<E> && !g_trivially_move_constructible)
        : m_has_value(other.m_has_value) {
        if (m_has_value) {
            m_value = other.m_value;
        } else {
            std::construct_at(std::addressof(m_error), std::move(other.m_error));
        }
    }

    template <typename U>
        requires g_value_arg<U>
    constexpr result(U&& v) noexcept // NOLINT(misc-explicit-constructor)
        : result(detail::value_tag{}, std::addressof(v)) {}

    template <typename U>
        requires g_dangling_arg<U>
    result(U&& v) = delete;

    // Implicit on purpose: `return "message";` is an error ([result.reqs] p4).
    template <typename G>
        requires g_error_arg<G>
    constexpr result(G&& e) // NOLINT(misc-explicit-constructor)
        : result(detail::error_tag{}, std::forward<G>(e)) {}

    template <typename U, typename G>
        requires(std::is_reference_v<U> &&
                 g_converting_arg<forge::result<U, G>, detail::error_forward_t<G, true>>)
    constexpr explicit(!std::is_convertible_v<detail::error_forward_t<G, true>, E>)
        result(const forge::result<U, G>& other)
        : m_has_value(other.has_value()) {
        construct_from(other);
    }

    template <typename U, typename G>
        requires(std::is_reference_v<U> &&
                 g_converting_arg<forge::result<U, G>, detail::error_forward_t<G, false>>)
    constexpr explicit(!std::is_convertible_v<detail::error_forward_t<G, false>, E>)
        result(forge::result<U, G>&& other)
        : m_has_value(other.has_value()) {
        construct_from(std::move(other));
    }

    template <typename U>
        requires(std::is_reference_v<U> && std::is_convertible_v<U, T&>)
    constexpr result(const success<U>& s) noexcept // NOLINT(misc-explicit-constructor)
        : result(detail::value_tag{}, std::addressof(s.value())) {}

    template <typename G>
        requires(std::is_constructible_v<E, const G&>)
    constexpr explicit(!std::is_convertible_v<const G&, E>) result(const failure<G>& f)
        : result(detail::error_tag{}, f.error()) {}

    template <typename G>
        requires(std::is_constructible_v<E, G>)
    constexpr explicit(!std::is_convertible_v<G, E>) result(failure<G>&& f)
        : result(detail::error_tag{}, std::move(f).error()) {}

    template <typename U>
        requires(detail::binds_directly<U, T&>)
    constexpr explicit result(in_place_t /*tag*/, U&& v) noexcept
        : result(detail::value_tag{}, std::addressof(v)) {}

    template <typename... Args>
        requires(std::is_constructible_v<E, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/, Args&&... args)
        : result(detail::error_tag{}, std::forward<Args>(args)...) {}

    template <typename U, typename... Args>
        requires(std::is_constructible_v<E, std::initializer_list<U>&, Args...>)
    constexpr explicit result(in_place_failure_t /*tag*/,
                              std::initializer_list<U> list,
                              Args&&... args)
        : result(detail::error_tag{}, list, std::forward<Args>(args)...) {}

    constexpr ~result()
        requires g_trivially_destructible
    = default;

    constexpr ~result()
        requires(!g_trivially_destructible)
    {
        if (!m_has_value) {
            std::destroy_at(std::addressof(m_error));
        }
    }

    // [result.object.assign], assignment. Every assignment that gives a value rebinds.
    constexpr result& operator=(const result& other)
        requires g_trivially_copy_assignable
    = default;

    constexpr result& operator=(const result& other)
        requires(std::is_copy_assignable_v<E> && std::is_copy_constructible_v<E> &&
                 !g_trivially_copy_assignable)
    {
        assign_from(other);
        return *this;
    }

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires g_trivially_move_assignable
    = default;

    constexpr result& operator=(result&& other) noexcept(std::is_nothrow_move_assignable_v<E> &&
                                                         std::is_nothrow_move_constructible_v<E>)
        requires(std::is_move_constructible_v<E> && std::is_move_assignable_v<E> &&
                 !g_trivially_move_assignable)
    {
        assign_from(std::move(other));
        return *this;
    }

    template <typename U>
        requires g_value_arg<U>
    constexpr result& operator=(U&& v) noexcept {
        assign_value(std::addressof(v));
        return *this;
    }

    template <typename U>
        requires g_dangling_arg<U>
    result& operator=(U&& v) = delete;

    template <typename G>
        requires g_error_arg<G> && std::is_assignable_v<E&, G>
    constexpr result& operator=(G&& e) {
        assign_error(std::forward<G>(e));
        return *this;
    }

    template <typename U>
        requires(std::is_reference_v<U> && std::is_convertible_v<U, T&>)
    constexpr result& operator=(const success<U>& s) noexcept {
        assign_value(std::addressof(s.value()));
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, const G&> && std::is_assignable_v<E&, const G&>)
    constexpr result& operator=(const failure<G>& f) {
        assign_error(f.error());
        return *this;
    }

    template <typename G>
        requires(std::is_constructible_v<E, G> && std::is_assignable_v<E&, G>)
    constexpr result& operator=(failure<G>&& f) {
        assign_error(std::move(f).error());
        return *this;
    }

    template <typename U>
        requires(detail::binds_directly<U, T&>)
    constexpr T& emplace(U&& v) noexcept {
        assign_value(std::addressof(v));
        return *m_value;
    }

    // [result.object.swap], swap
    constexpr void swap(result& other) noexcept(std::is_nothrow_move_constructible_v<E> &&
                                                std::is_nothrow_swappable_v<E>)
        requires(std::is_swappable_v<E> && std::is_move_constructible_v<E>)
    {
        using std::swap;
        if (m_has_value && other.m_has_value) {
            swap(m_value, other.m_value);
        } else if (!m_has_value && !other.m_has_value) {
            swap(m_error, other.m_error);
        } else if (m_has_value) {
            T* pointer = m_value;
            std::construct_at(std::addressof(m_error), std::move(other.m_error));
            std::destroy_at(std::addressof(other.m_error));
            other.m_value = pointer;
            m_has_value = false;
            other.m_has_value = true;
        } else {
            other.swap(*this);
        }
    }

    friend constexpr void swap(result& x, result& y) noexcept(noexcept(x.swap(y)))
        requires requires { x.swap(y); }
    {
        x.swap(y);
    }

    // [result.object.obs], observers. The constness of the result does not apply to the referent.
    [[nodiscard]] constexpr T* operator->() const noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return m_value;
    }

    [[nodiscard]] constexpr T& operator*() const& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& operator*() & noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& operator*() const&& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& operator*() && noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr explicit operator bool() const noexcept { return m_has_value; }
    [[nodiscard]] constexpr bool has_value() const noexcept { return m_has_value; }

    [[nodiscard]] constexpr T& value() const& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& value() & noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& value() const&& noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr T& value() && noexcept {
        FORGE_ASSERT(m_has_value, "result holds an error, not a value");
        return *m_value;
    }

    [[nodiscard]] constexpr const E& error() const& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr E& error() & noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return m_error;
    }

    [[nodiscard]] constexpr const E&& error() const&& noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    [[nodiscard]] constexpr E&& error() && noexcept {
        FORGE_ASSERT(!m_has_value, "result holds a value, not an error");
        return std::move(m_error);
    }

    // An rvalue result does not own its referent, so both overloads copy.
    template <typename U>
    [[nodiscard]] constexpr std::remove_cv_t<T> value_or(U&& fallback) const& {
        return value_or_impl(std::forward<U>(fallback));
    }

    template <typename U>
    [[nodiscard]] constexpr std::remove_cv_t<T> value_or(U&& fallback) && {
        return value_or_impl(std::forward<U>(fallback));
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) const& {
        static_assert(std::is_convertible_v<G, E> && std::is_copy_constructible_v<E>,
                      "error_or: G must convert to E, and E must be copy constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return m_error;
    }

    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) && {
        static_assert(std::is_convertible_v<G, E> && std::is_move_constructible_v<E>,
                      "error_or: G must convert to E, and E must be move constructible");
        if (m_has_value) {
            return static_cast<E>(std::forward<G>(fallback));
        }
        return std::move(m_error);
    }

    // [result.object.monadic], monadic operations. VAL is the referent for every overload.
    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto and_then(F&& f) & {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto and_then(F&& f) && {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto and_then(F&& f) const& {
        return detail::and_then_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto and_then(F&& f) const&& {
        return detail::and_then_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto or_else(F&& f) & {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto or_else(F&& f) && {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto or_else(F&& f) const& {
        return detail::or_else_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto or_else(F&& f) const&& {
        return detail::or_else_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result&, F>
    constexpr auto transform(F&& f) & {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<result, F>
    constexpr auto transform(F&& f) && {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result&, F>
    constexpr auto transform(F&& f) const& {
        return detail::transform_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::value_mapper_ok<const result, F>
    constexpr auto transform(F&& f) const&& {
        return detail::transform_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result&, F>
    constexpr auto transform_error(F&& f) & {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<result, F>
    constexpr auto transform_error(F&& f) && {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result&, F>
    constexpr auto transform_error(F&& f) const& {
        return detail::transform_error_impl(*this, std::forward<F>(f));
    }

    template <typename F>
        requires detail::error_mapper_ok<const result, F>
    constexpr auto transform_error(F&& f) const&& {
        return detail::transform_error_impl(std::move(*this), std::forward<F>(f));
    }

    // [result.object.eq], equality operators; referents are compared, never addresses.
    template <typename T2, typename E2>
        requires(!std::is_void_v<T2> &&
                 requires(const result& a, const forge::result<T2, E2>& b) {
                     { *a == *b } -> std::convertible_to<bool>;
                     { a.error() == b.error() } -> std::convertible_to<bool>;
                 })
    friend constexpr bool operator==(const result& x, const forge::result<T2, E2>& y) {
        if (x.has_value() != y.has_value()) {
            return false;
        }
        return x.has_value() ? static_cast<bool>(*x == *y)
                             : static_cast<bool>(x.error() == y.error());
    }

    template <typename T2>
        requires(!detail::g_is_specialization_of<T2, forge::result> && !detail::g_is_wrapper<T2> &&
                 requires(const result& a, const T2& b) {
                     { *a == b } -> std::convertible_to<bool>;
                 })
    friend constexpr bool operator==(const result& x, const T2& v) {
        return x.has_value() && static_cast<bool>(*x == v);
    }

    template <typename T2>
        requires requires(const result& a, const success<T2>& b) {
            { *a == b.value() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const success<T2>& s) {
        return x.has_value() && static_cast<bool>(*x == s.value());
    }

    template <typename E2>
        requires requires(const result& a, const failure<E2>& b) {
            { a.error() == b.error() } -> std::convertible_to<bool>;
        }
    friend constexpr bool operator==(const result& x, const failure<E2>& f) {
        return !x.has_value() && static_cast<bool>(x.error() == f.error());
    }

private:
    template <typename U>
    [[nodiscard]] constexpr std::remove_cv_t<T> value_or_impl(U&& fallback) const {
        static_assert(std::is_convertible_v<U, std::remove_cv_t<T>> &&
                          std::is_copy_constructible_v<std::remove_cv_t<T>>,
                      "value_or: U must convert to the referent, which must be copy constructible");
        if (m_has_value) {
            return *m_value;
        }
        return static_cast<std::remove_cv_t<T>>(std::forward<U>(fallback));
    }

    template <typename W>
    constexpr void construct_from(W&& other) {
        if (m_has_value) {
            m_value = std::addressof(*std::forward<W>(other));
        } else {
            std::construct_at(std::addressof(m_error), std::forward<W>(other).error());
        }
    }

    template <typename W>
    constexpr void assign_from(W&& other) {
        if (other.m_has_value) {
            assign_value(other.m_value);
        } else {
            assign_error(std::forward<W>(other).m_error);
        }
    }

    constexpr void assign_value(T* pointer) noexcept {
        if (!m_has_value) {
            std::destroy_at(std::addressof(m_error));
            m_has_value = true;
        }
        m_value = pointer;
    }

    template <typename G>
    constexpr void assign_error(G&& e) {
        if (m_has_value) {
            std::construct_at(std::addressof(m_error), std::forward<G>(e));
            m_has_value = false;
        } else {
            m_error = std::forward<G>(e);
        }
    }

    bool m_has_value;
    union {
        T* m_value;
        E m_error;
    };
};

} // namespace forge

FORGE_WARNINGS_POP

// [result.format], formatting
namespace forge::detail {

// A formatter is enabled when its specialization is default constructible ([result.format] p1).
template <typename X>
inline constexpr bool g_formattable = std::is_default_constructible_v<std::formatter<X, char>>;

// Shared by the three formatters: no format-spec is accepted. Throwing, or reaching the
// unreachable, also makes constant evaluation (the compile-time format-string check) fail.
struct format_without_spec {
    static constexpr std::format_parse_context::iterator parse(std::format_parse_context& ctx) {
        const auto* const it = ctx.begin();
        if (it != ctx.end() && *it != '}') {
#if FORGE_EXCEPTIONS_ENABLED
            throw std::format_error("result, success and failure take no format-spec");
#else
            FORGE_UNREACHABLE("result, success and failure take no format-spec");
#endif
        }
        return it;
    }
};

} // namespace forge::detail

template <typename T, typename E>
    requires(forge::detail::g_formattable<E> &&
             (std::is_void_v<T> || forge::detail::g_formattable<std::remove_cvref_t<T>>))
struct std::formatter<forge::result<T, E>, char> : forge::detail::format_without_spec {
    template <typename FormatContext>
    auto format(const forge::result<T, E>& r, FormatContext& ctx) const {
        if (!r.has_value()) {
            return std::format_to(ctx.out(), "failure({})", r.error());
        }
        if constexpr (std::is_void_v<T>) {
            return std::format_to(ctx.out(), "success()");
        } else {
            return std::format_to(ctx.out(), "success({})", *r);
        }
    }
};

template <typename T>
    requires(std::is_void_v<T> || forge::detail::g_formattable<std::remove_cvref_t<T>>)
struct std::formatter<forge::success<T>, char> : forge::detail::format_without_spec {
    template <typename FormatContext>
    auto format(const forge::success<T>& s, FormatContext& ctx) const {
        if constexpr (std::is_void_v<T>) {
            return std::format_to(ctx.out(), "success()");
        } else {
            return std::format_to(ctx.out(), "success({})", s.value());
        }
    }
};

template <typename E>
    requires(forge::detail::g_formattable<E>)
struct std::formatter<forge::failure<E>, char> : forge::detail::format_without_spec {
    template <typename FormatContext>
    auto format(const forge::failure<E>& f, FormatContext& ctx) const {
        return std::format_to(ctx.out(), "failure({})", f.error());
    }
};
