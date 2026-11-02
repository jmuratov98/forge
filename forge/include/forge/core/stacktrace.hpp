#pragma once

#include <compare>
#include <cstddef>
#include <vector>

namespace forge {

class frame {
public:
    using native_handle_type = std::uintptr_t;

    // [stacktrace.entry.cons], constructors
    constexpr frame() noexcept = default;
    constexpr frame(const frame& other) noexcept = default;
    constexpr frame& operator=(const frame& other) noexcept = default;
    constexpr frame(frame&& other) noexcept = default;
    constexpr frame& operator=(frame&& other) noexcept = default;

    ~frame() = default;

    // [stacktrace.entry.obs], observers
    [[nodiscard]] constexpr native_handle_type native_handle() const noexcept;
    constexpr explicit operator bool() const noexcept {
        return m_handle != static_cast<native_handle_type>(-1);
    }

    // [stacktrace.entry.query], query
    [[nodiscard]] std::string description() const;
    [[nodiscard]] std::string source_file() const;
    [[nodiscard]] std::uint_least32_t source_line() const;

    // [stacktrace.entry.cmp], comparison
    friend constexpr bool operator==(const frame& x, const frame& y) noexcept;
    friend constexpr std::strong_ordering operator<=>(const frame& x, const frame& y) noexcept;

private:
    native_handle_type m_handle{static_cast<native_handle_type>(-1)};
};

class stacktrace {
public:
    using value_type = frame;
    using const_reference = const value_type&;
    using reference = value_type&;
    using const_iterator = std::vector<frame>::const_iterator;
    using iterator = const_iterator;
    using reverse_iterator = std::reverse_iterator<iterator>;
    using const_reverse_iterator = std::reverse_iterator<const_iterator>;
    using difference_type = std::ptrdiff_t;
    using size_type = std::size_t;

    // creation and assignment
    static stacktrace current() noexcept;
    static stacktrace current(size_type skip) noexcept;
    static stacktrace current(size_type skip, size_type max_depth) noexcept;

    stacktrace() noexcept = default;

    stacktrace(const stacktrace& other) = default;
    stacktrace(stacktrace&& other) noexcept = default;
    stacktrace& operator=(const stacktrace& other) = default;
    stacktrace& operator=(stacktrace&& other) noexcept = default;

    ~stacktrace() = default;

    [[nodiscard]] const_iterator begin() const noexcept { return m_frames.begin(); }
    [[nodiscard]] const_iterator end() const noexcept { return m_frames.end(); }
    [[nodiscard]] const_reverse_iterator rbegin() const noexcept { return m_frames.rbegin(); }
    [[nodiscard]] const_reverse_iterator rend() const noexcept { return m_frames.rend(); }

    [[nodiscard]] const_iterator cbegin() const noexcept { return m_frames.cbegin(); }
    [[nodiscard]] const_iterator cend() const noexcept { return m_frames.cend(); }
    [[nodiscard]] const_reverse_iterator crbegin() const noexcept { return m_frames.crbegin(); }
    [[nodiscard]] const_reverse_iterator crend() const noexcept { return m_frames.crend(); }

    [[nodiscard]] bool empty() const noexcept { return m_frames.empty(); }
    [[nodiscard]] size_type size() const noexcept { return m_frames.size(); }
    [[nodiscard]] size_type max_size() const noexcept { return m_frames.max_size(); }

    const_reference operator[](size_type i) const { return m_frames[i]; }
    [[nodiscard]] const_reference at(size_type i) const { return m_frames.at(i); }

    // comparisons
    friend bool operator==(const stacktrace& x, const stacktrace& y) noexcept;
    friend std::strong_ordering operator<=>(const stacktrace& x, const stacktrace& y) noexcept;

    // modifiers
    void swap(stacktrace& other) noexcept;

private:
    // TODO: Remove dependence on std::vector
    std::vector<frame> m_frames;
};

} // namespace forge
