// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <format>
#include <string_view>
#include <type_traits>
#include <utility>

#if FORGE_ASSERTIONS_ENABLED
#  include <atomic>
#endif

// Context entries (docs/crash_context.md): objects that say what forge is doing while they exist,
// written into every failure report, outermost first:
//
//   forge::context_entry entry([&](forge::context_sink& out) {
//       out.format("lowering function '{}'", f.name());
//   });
//
// An entry's print function runs only when a report is written, so an entry costs a few pointer
// writes. It runs while a failure is reported, possibly one in the allocator, so it must not
// allocate, which the fixed-size context_sink makes easy.
//
// A task on another thread continues the chain of the thread that started it:
//
//   forge::context_token token = forge::current_context();  // where the task is started
//   pool.run([&token] {
//       forge::inherited_context inherited(token);          // in the task
//       ...
//   });
//   pool.wait();                                            // before token's entry ends
//
// The entry a token refers to must outlive the token; assertion builds check it.

namespace forge {

class context_node;
class context_token;
class inherited_context;

namespace detail {
struct context_access;
} // namespace detail

// The text of one context entry, in storage of fixed size. Text beyond the capacity is dropped.
class context_sink {
public:
    context_sink(const context_sink&) = delete;
    context_sink& operator=(const context_sink&) = delete;
    context_sink(context_sink&&) = delete;
    context_sink& operator=(context_sink&&) = delete;
    ~context_sink() = default;

    void write(std::string_view text) noexcept {
        const std::size_t size = std::min(text.size(), m_data.size() - m_size);
        std::copy_n(text.begin(), size, m_data.begin() + static_cast<std::ptrdiff_t>(m_size));
        m_size += size;
    }

    // The format string is checked against the arguments at compile time, as std::format's is.
    template <typename... Args>
    void format(std::format_string<Args...> format, Args&&... args) noexcept {
        vformat(format.get(), std::make_format_args(args...));
    }

private:
    friend struct detail::context_access;

    context_sink() noexcept = default;

    FORGE_API void vformat(std::string_view format, std::format_args args) noexcept;

    std::array<char, 1024> m_data{};
    std::size_t m_size = 0;
};

// The base of context entries and of inherited_context: constructing a node makes it the calling
// thread's innermost node, destroying it makes the node before it innermost again. Nodes end in
// the reverse order of their construction on each thread, as automatic objects do.
class context_node {
public:
    context_node(const context_node&) = delete;
    context_node& operator=(const context_node&) = delete;
    context_node(context_node&&) = delete;
    context_node& operator=(context_node&&) = delete;

protected:
    using print_function = void (*)(const context_node& node, context_sink& out) noexcept;

    FORGE_API explicit context_node(print_function print) noexcept;
    FORGE_API ~context_node();

private:
    friend struct detail::context_access;
    friend class context_token;
    friend class inherited_context;

    struct inheriting {};

    // An inherited_context, which has no print function: its task continues at `inherited`.
    FORGE_API context_node(inheriting /*unused*/, const context_node* inherited) noexcept;

    print_function m_print;
    const context_node* m_outer;
    const context_node* m_inherited = nullptr;
#if FORGE_ASSERTIONS_ENABLED
    // How many context_tokens refer to this node.
    mutable std::atomic<unsigned> m_tokens{0};
#endif
};

namespace detail {

// A context_entry's print function. A base listed before context_node, rather than a member, so
// that it exists while the context_node constructor and destructor run: both can write the entry,
// for a live dump.
template <typename Print>
struct context_entry_print {
    Print print;
};

// What a program_arguments_entry writes, kept the same way.
struct program_arguments {
    int count;
    const char* const* values;
};

} // namespace detail

// The print function comes in through a base so that it is constructed before context_node: the
// base-from-member idiom.
template <typename Print>
class context_entry // NOLINT(misc-multiple-inheritance)
    : private detail::context_entry_print<Print>,
      public context_node {
    static_assert(std::is_invocable_v<const Print&, context_sink&>,
                  "a context entry's print function takes a forge::context_sink&");

public:
    explicit context_entry(Print print) noexcept(std::is_nothrow_move_constructible_v<Print>)
        : detail::context_entry_print<Print>{std::move(print)}, context_node(&write) {}

private:
    static void write(const context_node& node, context_sink& out) noexcept {
        const auto& entry = static_cast<const context_entry&>(node);
        static_cast<const detail::context_entry_print<Print>&>(entry).print(out);
    }
};

template <typename Print>
context_entry(Print) -> context_entry<Print>;

// "program arguments: forge -c foo.c": the first entry of every forge program, which main
// constructs. `argv` must stay valid and unchanged while the entry exists.
class program_arguments_entry // NOLINT(misc-multiple-inheritance): as context_entry
    : private detail::program_arguments,
      public context_node {
public:
    FORGE_API program_arguments_entry(int argc, const char* const* argv) noexcept;

private:
    static void write(const context_node& node, context_sink& out) noexcept;
};

// Refers to a node for a task to inherit, or to none. Only movable.
class context_token {
public:
    context_token() noexcept = default;
    context_token(context_token&& other) noexcept : m_node(std::exchange(other.m_node, nullptr)) {}

    context_token& operator=(context_token&& other) noexcept {
        if (this != &other) {
            release();
            m_node = std::exchange(other.m_node, nullptr);
        }
        return *this;
    }

    context_token(const context_token&) = delete;
    context_token& operator=(const context_token&) = delete;

    ~context_token() { release(); }

private:
    friend struct detail::context_access;
    friend class inherited_context;

    explicit context_token(const context_node* node) noexcept : m_node(node) {
#if FORGE_ASSERTIONS_ENABLED
        if (m_node != nullptr) {
            m_node->m_tokens.fetch_add(1, std::memory_order_relaxed);
        }
#endif
    }

    void release() noexcept {
#if FORGE_ASSERTIONS_ENABLED
        if (m_node != nullptr) {
            m_node->m_tokens.fetch_sub(1, std::memory_order_release);
        }
#endif
        m_node = nullptr;
    }

    const context_node* m_node = nullptr;
};

// A token that refers to the calling thread's innermost node, or to none if it has none.
[[nodiscard]] FORGE_API context_token current_context() noexcept;

// Marks the start of a task: reports from this thread continue, after this node, with the chain of
// the node `token` refers to. `token` must outlive this node.
class inherited_context : public context_node {
public:
    FORGE_API explicit inherited_context(const context_token& token) noexcept;
};

// Installs the live-dump handler for SIGINFO on macOS (Ctrl-T in a terminal) or SIGUSR1 on Linux,
// when the signal has its default disposition. After the signal, each thread writes its context
// and stack trace to stderr the next time it constructs or destroys a node, and goes on. Returns
// whether the handler is installed; always false on Windows. libforge never calls it itself.
FORGE_API bool enable_context_dump() noexcept;

} // namespace forge
