// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/assert.hpp"

#include <array>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <mutex>
#include <source_location>
#include <string_view>

namespace forge::detail {
namespace {

// A report's text, kept in a fixed buffer so that reporting does not allocate: the broken
// invariant may be the allocator's. Text that does not fit is dropped.
class report_text {
public:
    // The output iterator std::format writes through. Copies share the position, as with
    // std::back_insert_iterator.
    class inserter {
    public:
        using difference_type = std::ptrdiff_t;

        explicit inserter(report_text& text) : m_text(&text) {}

        inserter& operator*() { return *this; }
        inserter& operator++() { return *this; }
        inserter operator++(int) { return *this; }

        inserter& operator=(char c) {
            m_text->append(c);
            return *this;
        }

    private:
        report_text* m_text;
    };

    void append(char c) {
        if (m_size < m_data.size()) {
            m_data[m_size++] = c;
        }
    }

    void append(std::string_view text) {
        for (const char c : text) {
            append(c);
        }
    }

    inserter out() { return inserter(*this); }

    void write_to(std::FILE* file) const { std::fwrite(m_data.data(), 1, m_size, file); }

private:
    std::array<char, 4096> m_data{};
    std::size_t m_size = 0;
};

} // namespace

void report_failure(failure_kind kind,
                    const char* condition,
                    std::source_location location,
                    std::string_view format,
                    std::format_args args) noexcept {
    // A check that fails while its report is being written, e.g. in the formatter of a message
    // argument, would otherwise recurse until the stack overflows.
    static thread_local bool reporting = false;
    if (reporting) {
        std::fputs("internal error: a check failed while reporting a failed check\n", stderr);
        std::abort();
    }
    reporting = true;

    // Reports from several threads would interleave. The first thread to fail keeps the lock
    // until it aborts the process; the others wait here.
    static std::mutex mutex;
    mutex.lock();

    // No column: inside a macro, Clang gives the column of the invocation's closing parenthesis
    // and GCC that of the macro's name.
    report_text text;
    std::format_to(text.out(), "{}:{}: internal error: ", location.file_name(), location.line());
    switch (kind) {
    case failure_kind::assertion:
        text.append("assertion failed: ");
        text.append(condition);
        break;
    case failure_kind::unreachable:
        text.append("unreachable code reached");
        break;
    case failure_kind::todo:
        text.append("not yet implemented");
        break;
    }
    text.append('\n');
    if (!format.empty()) {
        text.append("  message: ");
        std::vformat_to(text.out(), format, args);
        text.append('\n');
    }
    text.append("  in function: ");
    text.append(location.function_name());
    text.append('\n');

    // TODO: print a backtrace.

    text.write_to(stderr);
    std::abort();
}

} // namespace forge::detail
