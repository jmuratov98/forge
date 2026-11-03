// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/crash_context.hpp"

#include "forge/core/assert.hpp"
#include "forge/core/report.hpp"
#include "forge/core/stacktrace.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <format>
#include <iterator>
#include <span>
#include <string_view>

#if FORGE_HOST_POSIX
#  include <csignal>

#  include <pthread.h>
#  include <unistd.h>
#endif

namespace forge {

namespace detail {

// Everything that reads the private parts of nodes, sinks and tokens.
struct context_access {
    static bool is_entry(const context_node& node) noexcept { return node.m_print != nullptr; }

    // The node after `node` in a context chain ([context.chain] paragraph 1): an inherited_context
    // continues where its task was started, or ends the chain.
    static const context_node* next_in_chain(const context_node& node) noexcept {
        return is_entry(node) ? node.m_outer : node.m_inherited;
    }

    static context_token token(const context_node* node) noexcept { return context_token(node); }

    // Writes "    #<number> <text>", continuing each line of the text with six spaces.
    static void
    write_entry(std::FILE* file, const context_node& node, std::size_t number) noexcept {
        context_sink sink;
        node.m_print(node, sink);
        std::fprintf(file, "    #%zu ", number);
        const std::string_view text(sink.m_data.data(), sink.m_size);
        for (const char c : text) {
            std::fputc(c, file);
            if (c == '\n') {
                std::fputs("      ", file);
            }
        }
        std::fputc('\n', file);
        std::fflush(file);
    }
};

} // namespace detail

namespace {

using detail::context_access;

// The calling thread's innermost node. Code outside libforge reaches it only through the exported
// functions here, because Windows cannot export a thread_local object from a DLL.
constinit thread_local const context_node* g_innermost = nullptr;

// Live dumps. The signal handler counts requests; each thread remembers the count it last saw,
// and dumps when the count has moved on. 0 means the thread has not looked yet: its first look
// only records the count, so that a thread does not dump for a request made before it ran.
std::atomic<unsigned> g_dump_requests{1};
static_assert(std::atomic<unsigned>::is_always_lock_free,
              "the signal handler may only touch a lock-free atomic");
constinit thread_local unsigned g_dumps_seen = 0;

void write_line(std::FILE* file, std::string_view text) noexcept {
    std::fwrite(text.data(), 1, text.size(), file);
    std::fputc('\n', file);
    std::fflush(file);
}

// The thread's id as debuggers show it: the kernel's thread id on Linux, as gdb's LWP;
// pthread_threadid_np on macOS, as lldb's tid. Windows has no live dumps.
std::uint64_t thread_id() noexcept {
#if FORGE_HOST_LINUX
    return static_cast<std::uint64_t>(gettid());
#elif FORGE_HOST_MACOS
    std::uint64_t id = 0;
    pthread_threadid_np(nullptr, &id);
    return id;
#else
    return 0;
#endif
}

// Never inlined, so that skipping its frame makes frame 0 of the trace the node constructor or
// destructor that found the request.
FORGE_NOINLINE void dump_context() noexcept {
    std::array<std::uintptr_t, detail::g_report_frames + 1> frames{};
    const std::size_t frame_count = stacktrace::capture(frames, 1);

    const detail::report_lock lock;
    std::fprintf(stderr,
                 "forge: context of thread %llu, on request:\n",
                 static_cast<unsigned long long>(thread_id()));
    std::fflush(stderr);
    detail::write_context(stderr);
    stacktrace::print(stderr,
                      std::span(frames).first(std::min(frame_count, detail::g_report_frames)),
                      frame_count > detail::g_report_frames);
}

// [context.dump] paragraph 6. Inlined into the node constructors and destructor, so that a dump's
// frame 0 is one of them; with no request pending it is one relaxed load and a compare.
FORGE_ALWAYS_INLINE void check_dump() noexcept {
    const unsigned requests = g_dump_requests.load(std::memory_order_relaxed);
    if (requests != g_dumps_seen) [[unlikely]] {
        const bool first_look = g_dumps_seen == 0;
        g_dumps_seen = requests;
        // A thread that is writing a report or a dump already reaches here only from a print
        // function that constructs a node; it does not start another.
        if (!first_look && !detail::report_lock::held()) {
            dump_context();
        }
    }
}

#if FORGE_HOST_POSIX
// A lock-free atomic increment is all it does, which is safe in a signal handler.
void request_dump(int /*signal*/) noexcept {
    g_dump_requests.fetch_add(1, std::memory_order_relaxed);
}
#endif

// What context_sink::format writes through.
class sink_inserter {
public:
    using difference_type = std::ptrdiff_t;

    explicit sink_inserter(context_sink& sink) noexcept : m_sink(&sink) {}

    sink_inserter& operator*() noexcept { return *this; }
    sink_inserter& operator++() noexcept { return *this; }
    sink_inserter operator++(int) noexcept { return *this; }

    sink_inserter& operator=(char c) noexcept {
        m_sink->write(std::string_view(&c, 1));
        return *this;
    }

private:
    context_sink* m_sink;
};

// [context.args] paragraph 2.
void write_argument(context_sink& out, std::string_view argument) noexcept {
    if (!argument.empty() && argument.find_first_of(" \t\n\"\\") == std::string_view::npos) {
        out.write(argument);
        return;
    }
    out.write("\"");
    for (const char c : argument) {
        if (c == '\n') {
            out.write("\\n");
        } else {
            if (c == '"' || c == '\\') {
                out.write("\\");
            }
            out.write(std::string_view(&c, 1));
        }
    }
    out.write("\"");
}

} // namespace

void context_sink::vformat(std::string_view format, std::format_args args) noexcept {
    std::vformat_to(sink_inserter(*this), format, args);
}

context_node::context_node(print_function print) noexcept : m_print(print), m_outer(g_innermost) {
    g_innermost = this;
    check_dump();
}

context_node::context_node(inheriting /*unused*/, const context_node* inherited) noexcept
    : m_print(nullptr), m_outer(g_innermost), m_inherited(inherited) {
    g_innermost = this;
    check_dump();
}

context_node::~context_node() {
    check_dump();
    FORGE_ASSERT(g_innermost == this,
                 "context entries end in the reverse order of their construction");
#if FORGE_ASSERTIONS_ENABLED
    FORGE_ASSERT(m_tokens.load(std::memory_order_acquire) == 0,
                 "context entry destroyed while a task still inherits it");
#endif
    g_innermost = m_outer;
}

program_arguments_entry::program_arguments_entry(int argc, const char* const* argv) noexcept
    : detail::program_arguments{.count = argc, .values = argv}, context_node(&write) {}

void program_arguments_entry::write(const context_node& node, context_sink& out) noexcept {
    const auto& arguments = static_cast<const detail::program_arguments&>(
        static_cast<const program_arguments_entry&>(node));
    out.write("program arguments:");
    for (const char* argument :
         std::span(arguments.values, static_cast<std::size_t>(arguments.count))) {
        out.write(" ");
        write_argument(out, argument);
    }
}

context_token current_context() noexcept {
    return context_access::token(g_innermost);
}

inherited_context::inherited_context(const context_token& token) noexcept
    : context_node(inheriting{}, token.m_node) {}

bool enable_context_dump() noexcept {
#if FORGE_HOST_POSIX
#  if FORGE_HOST_MACOS
    // Ctrl-T in a terminal sends SIGINFO; Linux has no such signal.
    constexpr int signal_number = SIGINFO;
#  else
    constexpr int signal_number = SIGUSR1;
#  endif
    struct sigaction current{};
    if (sigaction(signal_number, nullptr, &current) != 0) {
        return false;
    }
    const bool plain =
        (static_cast<unsigned>(current.sa_flags) & static_cast<unsigned>(SA_SIGINFO)) == 0;
    if (plain && current.sa_handler == &request_dump) {
        return true;
    }
    if (!plain || current.sa_handler != SIG_DFL) {
        return false;
    }
    struct sigaction action{};
    action.sa_handler = &request_dump;
    sigemptyset(&action.sa_mask);
    action.sa_flags = SA_RESTART;
    return sigaction(signal_number, &action, nullptr) == 0;
#else
    return false;
#endif
}

void detail::write_context(std::FILE* file) noexcept {
    std::size_t entries = 0;
    const context_node* outermost = nullptr;
    for (const context_node* node = g_innermost; node != nullptr;
         node = context_access::next_in_chain(*node)) {
        if (context_access::is_entry(*node)) {
            ++entries;
        }
        outermost = node;
    }
    if (entries == 0) {
        return;
    }

    // Past 64 entries, the outermost 8 and the innermost 56 are written ([context.chain]
    // paragraph 3): what the program was doing, and what it was doing when it failed.
    constexpr std::size_t max_entries = 64;
    constexpr std::size_t head = 8;
    constexpr std::size_t tail = max_entries - head;
    const bool cut = entries > max_entries;
    const auto written = [&](std::size_t number) {
        return !cut || number < head || number >= entries - tail;
    };

    // What is written, collected innermost first, since that is the direction the chain is walked
    // in, and written in reverse. A task line is left out when it is the chain's first node, when
    // the entry after it is left out, and when it would repeat the line after it: a task started
    // by a task that has no entries of its own adds nothing to read. So there is at most one task
    // line per entry, plus one after the innermost.
    struct item {
        const context_node* node;
        std::size_t number;
    };
    std::array<item, (2 * max_entries) + 1> items{};
    std::size_t count = 0;
    std::size_t number = entries;
    bool inner_written = true;
    for (const context_node* node = g_innermost; node != nullptr;
         node = context_access::next_in_chain(*node)) {
        if (context_access::is_entry(*node)) {
            --number;
            inner_written = written(number);
            if (inner_written) {
                items[count++] = {.node = node, .number = number};
            }
        } else if (inner_written && node != outermost &&
                   (count == 0 || context_access::is_entry(*items[count - 1].node))) {
            items[count++] = {.node = node, .number = 0};
        }
    }

    write_line(file, "  context:");
    for (std::size_t i = count; i-- > 0;) {
        const item& current = items[i];
        if (!context_access::is_entry(*current.node)) {
            write_line(file, "    (the entries below run in a task on another thread)");
            continue;
        }
        context_access::write_entry(file, *current.node, current.number);
        if (cut && current.number == head - 1) {
            std::fprintf(file, "    (%zu entries not shown)\n", entries - max_entries);
            std::fflush(file);
        }
    }
}

} // namespace forge
