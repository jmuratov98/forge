// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/crash_context.hpp"

#include "report_matchers.hpp"

#include "forge/core/assert.hpp"
#include "forge/core/config.hpp"

#include <gtest/gtest.h>

#include <array>
#include <csignal>
#include <string>
#include <thread>
#include <utility>

namespace forge {
namespace {

using test::has_lines;
using test::has_no_line;

// A failure inside `depth` nested entries, "level 0" outermost.
[[noreturn]] void fail_inside(int depth, int level = 0) {
    if (level == depth) {
        FORGE_TODO("at the innermost entry");
    }
    const context_entry entry([level](context_sink& out) { out.format("level {}", level); });
    fail_inside(depth, level + 1);
}

TEST(context_token, released_before_its_entry_ends) {
    const context_entry entry([](context_sink& out) { out.write("entry"); });
    context_token token = current_context();
    context_token moved = std::move(token);
    token = std::move(moved);
    token = context_token();
}

TEST(context_token, refers_to_nothing_without_entries) {
    const context_token token = current_context();
    std::thread worker([&token] {
        const inherited_context inherited(token);
        const context_entry entry([](context_sink& out) { out.write("in a task"); });
    });
    worker.join();
}

// ThreadSanitizer does not support the fork that death tests use.
#if GTEST_HAS_DEATH_TEST && !FORGE_TSAN_ENABLED

TEST(context_report, entries_outermost_first) {
    EXPECT_DEATH(fail_inside(2),
                 has_lines({"  context:", "    #0 level 0", "    #1 level 1", "  stack trace:"}));
}

TEST(context_report, nothing_without_entries) {
    EXPECT_DEATH(FORGE_TODO(), has_no_line("  context:"));
}

TEST(context_report, past_64_entries_the_first_8_and_the_last_56) {
    EXPECT_DEATH(
        fail_inside(70),
        has_lines({"    #7 level 7", "    \\(6 entries not shown\\)", "    #14 level 14"}));
    EXPECT_DEATH(fail_inside(70), has_lines({"    #69 level 69", "  stack trace:"}));
}

TEST(context_report, multiline_text_is_indented) {
    EXPECT_DEATH(
        {
            const context_entry entry([](context_sink& out) { out.write("first\nsecond"); });
            FORGE_TODO();
        },
        has_lines({"    #0 first", "      second"}));
}

TEST(context_report, text_beyond_the_capacity_is_dropped) {
    EXPECT_DEATH(
        {
            const context_entry entry([](context_sink& out) {
                const std::string text(2000, 'x');
                out.write(text);
                out.format("{}", text);
            });
            FORGE_TODO();
        },
        has_lines({"    #0 x{1024}"}));
}

TEST(context_report, a_task_continues_the_chain_it_inherits) {
    EXPECT_DEATH(
        {
            const context_entry outer([](context_sink& out) { out.write("compiling 'foo.c'"); });
            const context_token token = current_context();
            std::thread worker([&token] {
                const inherited_context inherited(token);
                const context_entry inner(
                    [](context_sink& out) { out.write("lowering function 'main'"); });
                FORGE_TODO();
            });
            worker.join();
        },
        has_lines({"  context:",
                   "    #0 compiling 'foo.c'",
                   "    \\(the entries below run in a task on another thread\\)",
                   "    #1 lowering function 'main'",
                   "  stack trace:"}));
}

TEST(context_report, a_task_that_inherits_nothing_starts_the_chain) {
    EXPECT_DEATH(
        {
            const context_token token;
            std::thread worker([&token] {
                const inherited_context inherited(token);
                const context_entry entry([](context_sink& out) { out.write("in a task"); });
                FORGE_TODO();
            });
            worker.join();
        },
        has_lines({"  context:", "    #0 in a task"}));
}

TEST(context_report, program_arguments_quoted_where_needed) {
    // forge -c "a b.c" "" "say \"hi\"\\" "two\nlines"
    static constexpr std::array argv{"forge", "-c", "a b.c", "", R"(say "hi"\)", "two\nlines"};
    EXPECT_DEATH(
        {
            const program_arguments_entry arguments(static_cast<int>(argv.size()), argv.data());
            FORGE_TODO();
        },
        has_lines(
            {R"(    #0 program arguments: forge -c "a b\.c" "" "say \\"hi\\"\\\\" "two\\nlines")"}));
}

TEST(context_report, version_and_banner) {
    EXPECT_DEATH(FORGE_TODO(),
                 has_lines({R"(  forge version: \d+\.\d+\.\d+\S*)",
                            "  forge does not support this yet\\."}));
#  if FORGE_ASSERTIONS_ENABLED
    const std::string banner = "  PLEASE report this bug to the forge developers, with this "
                               "report and the input that caused it\\.";
    EXPECT_DEATH(FORGE_ASSERT(false), has_lines({R"(  forge version: .*)", banner}));
    EXPECT_DEATH(FORGE_UNREACHABLE(), has_lines({R"(  forge version: .*)", banner}));
#  endif
}

#  if FORGE_ASSERTIONS_ENABLED
TEST(context_report, entry_ending_while_a_task_inherits_it) {
    EXPECT_DEATH(
        {
            context_token token;
            {
                const context_entry entry([](context_sink& out) { out.write("entry"); });
                token = current_context();
            }
        },
        "context entry destroyed while a task still inherits it");
}
#  endif

#endif

#if FORGE_HOST_POSIX
TEST(context_dump, written_at_the_next_entry_after_the_signal) {
#  if FORGE_HOST_MACOS
    constexpr int signal_number = SIGINFO;
#  else
    constexpr int signal_number = SIGUSR1;
#  endif
    // enable_context_dump takes over only the default disposition, and a test may inherit
    // another: GitHub's macOS runners start processes with SIGINFO not at SIG_DFL.
    ASSERT_NE(std::signal(signal_number, SIG_DFL), SIG_ERR);
    ASSERT_TRUE(enable_context_dump());
    // A thread's first entry only records the dump requests it has seen.
    const context_entry outer([](context_sink& out) { out.write("waiting for a dump"); });
    std::raise(signal_number);
    testing::internal::CaptureStderr();
    {
        const context_entry inner([](context_sink& out) { out.write("after the request"); });
    }
    const std::string output = testing::internal::GetCapturedStderr();
    EXPECT_TRUE(has_lines({R"(forge: context of thread \d+, on request:)",
                           "  context:",
                           R"(    #\d+ waiting for a dump)",
                           R"(    #\d+ after the request)",
                           "  stack trace:"})
                    .Matches(output))
        << output;
}
#endif

} // namespace
} // namespace forge
