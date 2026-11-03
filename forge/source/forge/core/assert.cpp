// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/assert.hpp"

#include "forge/core/report.hpp"
#include "forge/core/stacktrace.hpp"
#include "forge/core/version.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <mutex>
#include <source_location>
#include <span>
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

constinit thread_local bool g_holding_report_lock = false;

// A function's static, so that it is initialized before any check can fail, even one in the
// initializer of another static.
std::mutex& report_mutex() noexcept {
    static std::mutex mutex;
    return mutex;
}

// [context.report] paragraph 1: missing features are not bugs, so FORGE_TODO asks for no report.
void append_banner(report_text& text, failure_kind kind) {
    const std::string_view url = bug_report_url();
    if (kind == failure_kind::todo) {
        if (url.empty()) {
            text.append("  forge does not support this yet.\n");
        } else {
            std::format_to(text.out(),
                           "  forge does not support this yet; see {} for what is planned.\n",
                           url);
        }
    } else if (url.empty()) {
        text.append(
            "  PLEASE report this bug to the forge developers, with this report and the input "
            "that caused it.\n");
    } else {
        std::format_to(
            text.out(),
            "  PLEASE submit a bug report to {} and include this report and the input that "
            "caused it.\n",
            url);
    }
}

} // namespace

report_lock::report_lock() noexcept {
    // A check that fails while this thread writes a report, e.g. in the formatter of a message
    // argument or in a context entry's print function.
    if (g_holding_report_lock) {
        std::fputs("internal error: a check failed while reporting a failed check\n", stderr);
        std::abort();
    }
    report_mutex().lock();
    g_holding_report_lock = true;
}

report_lock::~report_lock() {
    g_holding_report_lock = false;
    report_mutex().unlock();
}

bool report_lock::held() noexcept {
    return g_holding_report_lock;
}

void report_failure(failure_kind kind,
                    const char* condition,
                    std::source_location location,
                    std::string_view format,
                    std::format_args args) noexcept {
    // The trace comes first, before anything allocates or locks. Skipping one frame, this
    // function's, makes frame 0 the function with the failed check, since the helpers that
    // call this one are inlined into it.
    std::array<std::uintptr_t, g_report_frames + 1> frames{};
    const std::size_t frame_count = stacktrace::capture(frames, 1);

    // The first thread to fail keeps the lock until it aborts the process; others wait here.
    const report_lock lock;

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
    text.append("  forge version: ");
    text.append(version());
    text.append('\n');
    append_banner(text, kind);

    // From the most certain to the least: the text allocates nothing; the context runs print
    // functions; the trace allocates and runs llvm-symbolizer. Each part is out before the next
    // starts, so whatever fails, what came before has been reported.
    text.write_to(stderr);
    std::fflush(stderr);
    write_context(stderr);
    stacktrace::print(stderr,
                      std::span(frames).first(std::min(frame_count, g_report_frames)),
                      frame_count > g_report_frames);
    std::abort();
}

} // namespace forge::detail
