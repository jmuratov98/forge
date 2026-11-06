// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include <cstdint>
#include <type_traits>

namespace forge {

namespace detail {

// std::is_scoped_enum_v is C++23. An unscoped enum is left out because it converts to int: in a
// result<int, error>, returning one would become the value rather than the error. The partial
// specialization keeps std::underlying_type_t away from types that are not enums, for which it is
// a hard error rather than a substitution failure.
template <typename E>
inline constexpr bool g_is_scoped_enum = false;

template <typename E>
    requires std::is_enum_v<E>
inline constexpr bool g_is_scoped_enum<E> = !std::is_convertible_v<E, std::underlying_type_t<E>>;

template <typename E>
inline constexpr bool g_is_error_code_enum =
    g_is_scoped_enum<E> && sizeof(E) <= sizeof(std::uint32_t);

} // namespace detail

// A failure, held as a code alone: there is no default constructor and no value that means
// success, since a result already says whether it succeeded.
class error {
public:
    // Implicit on purpose: `return some_errc::x;` is the error of a result<T, error>.
    template <typename E>
        requires detail::g_is_error_code_enum<E>
    constexpr error(E code) noexcept // NOLINT(misc-explicit-constructor)
        : m_code(static_cast<std::uint32_t>(code)) {}

    [[nodiscard]] constexpr std::uint32_t code() const noexcept { return m_code; }

    friend constexpr bool operator==(error, error) noexcept = default;

private:
    std::uint32_t m_code;
};

static_assert(std::is_trivially_copyable_v<error>);

template <typename E>
    requires detail::g_is_error_code_enum<E>
[[nodiscard]] constexpr error make_error(E code) noexcept {
    return error(code);
}

} // namespace forge
