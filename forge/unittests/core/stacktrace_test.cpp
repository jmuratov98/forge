// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/stacktrace.hpp"

#include "forge/core/config.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <limits>
#include <optional>
#include <regex>
#include <span>
#include <string>
#include <vector>

namespace forge::detail {
namespace {

// A capture from a function in forge::detail with a frame of its own, as the helpers of a failed
// check have in MSVC Debug builds. The fence keeps the capture from being a tail call, which would
// replace this frame.
FORGE_NOINLINE std::size_t capture_in_detail(std::span<std::uintptr_t> frames) {
    const std::size_t count = stacktrace::capture(frames);
    std::atomic_signal_fence(std::memory_order_seq_cst);
    return count;
}

} // namespace
} // namespace forge::detail

namespace forge::stacktrace {
namespace {

// Captures twice from one invocation, skipping one frame and then none. FORGE_NOINLINE so that
// the invocation has a frame of its own; neither capture is a tail call, which would replace it.
FORGE_NOINLINE std::array<std::size_t, 2> capture_twice(std::span<std::uintptr_t> skipping_one,
                                                        std::span<std::uintptr_t> skipping_none) {
    const std::size_t first = capture(skipping_one, 1);
    const std::size_t second = capture(skipping_none);
    return {first, second};
}

TEST(stacktrace_capture, fills_a_nonempty_span) {
    std::array<std::uintptr_t, 64> frames{};
    EXPECT_GE(capture(frames), 1U);
}

TEST(stacktrace_capture, writes_nothing_into_an_empty_span) {
    EXPECT_EQ(capture(std::span<std::uintptr_t>()), 0U);
}

TEST(stacktrace_capture, stops_when_the_span_is_full) {
    std::array<std::uintptr_t, 2> frames{};
    EXPECT_EQ(capture(frames), 2U);
}

TEST(stacktrace_capture, skipping_every_frame_leaves_nothing) {
    std::array<std::uintptr_t, 4> frames{};
    EXPECT_EQ(capture(frames, 100'000), 0U);
    // capture also skips its own frame, which must not wrap around.
    EXPECT_EQ(capture(frames, std::numeric_limits<std::size_t>::max()), 0U);
}

TEST(stacktrace_capture, leaves_the_rest_of_the_span_alone) {
    constexpr std::uintptr_t untouched = 0x5a5a;
    std::array<std::uintptr_t, 256> frames{};
    frames.fill(untouched);
    const std::size_t count = capture(frames);
    ASSERT_LT(count, frames.size());
    for (std::size_t i = count; i < frames.size(); ++i) {
        EXPECT_EQ(frames[i], untouched) << "frame " << i;
    }
}

TEST(stacktrace_capture, skip_drops_the_innermost_frames) {
    std::array<std::uintptr_t, 4> skipping_one{};
    std::array<std::uintptr_t, 4> skipping_none{};
    const std::array<std::size_t, 2> counts = capture_twice(skipping_one, skipping_none);
    ASSERT_GE(counts[0], 1U);
    ASSERT_GE(counts[1], 2U);
    // Both are where capture_twice returns to in this test. Frame 0 of either capture is in
    // capture_twice, at a different call each time.
    EXPECT_EQ(skipping_one[0], skipping_none[1]);
}

// Sets an environment variable, or unsets it for nullptr, until the end of the scope.
class scoped_environment_variable {
public:
    scoped_environment_variable(const char* name, const char* value) : m_name(name) {
        if (const char* previous = std::getenv(name); previous != nullptr) {
            m_previous = previous;
        }
        set(value);
    }

    scoped_environment_variable(const scoped_environment_variable&) = delete;
    scoped_environment_variable& operator=(const scoped_environment_variable&) = delete;
    scoped_environment_variable(scoped_environment_variable&&) = delete;
    scoped_environment_variable& operator=(scoped_environment_variable&&) = delete;

    ~scoped_environment_variable() { set(m_previous ? m_previous->c_str() : nullptr); }

private:
    void set(const char* value) const {
#if FORGE_HOST_WINDOWS
        // An empty value removes the variable.
        _putenv_s(m_name, value != nullptr ? value : "");
#else
        if (value != nullptr) {
            setenv(m_name, value, 1);
        } else {
            unsetenv(m_name);
        }
#endif
    }

    const char* m_name;
    std::optional<std::string> m_previous;
};

// What print writes for `frames`.
std::string printed(std::span<const std::uintptr_t> frames, bool truncated) {
    std::FILE* file = std::tmpfile();
    if (file == nullptr) {
        ADD_FAILURE() << "std::tmpfile failed";
        return {};
    }
    print(file, frames, truncated);
    if (std::fseek(file, 0, SEEK_SET) != 0) {
        ADD_FAILURE() << "std::fseek failed";
        std::fclose(file);
        return {};
    }
    std::string text;
    std::array<char, 4096> buffer{};
    std::size_t size = 0;
    while ((size = std::fread(buffer.data(), 1, buffer.size(), file)) != 0) {
        text.append(buffer.data(), size);
    }
    std::fclose(file);
    return text;
}

std::vector<std::string> lines_of(const std::string& text) {
    std::vector<std::string> lines;
    for (std::size_t begin = 0; begin < text.size();) {
        const std::size_t end = std::min(text.find('\n', begin), text.size());
        lines.push_back(text.substr(begin, end - begin));
        begin = end + 1;
    }
    return lines;
}

bool matches(const std::string& line, const std::string& pattern) {
    return std::regex_match(line, std::regex(pattern));
}

TEST(stacktrace_print, without_symbolization_shows_modules_and_offsets) {
    const scoped_environment_variable disabled("FORGE_DISABLE_SYMBOLIZATION", "1");
    std::array<std::uintptr_t, 8> frames{};
    const std::size_t count = capture(frames);
    ASSERT_GE(count, 1U);

    const std::string text = printed(std::span(frames).first(count), false);
    EXPECT_TRUE(text.ends_with('\n'));
    // A frame line has no function or location, and no note follows the frames.
    const std::vector<std::string> lines = lines_of(text);
    ASSERT_EQ(lines.size(), count + 1);
    EXPECT_EQ(lines[0], "  stack trace:");
    for (std::size_t i = 0; i < count; ++i) {
        EXPECT_TRUE(matches(lines[i + 1], std::format(R"(    #{} \S+\+0x[1-9a-f][0-9a-f]*)", i)))
            << lines[i + 1];
    }
    // Frame 0 is this test, in the test executable.
    EXPECT_TRUE(lines[1].starts_with("    #0 forge_core_unittests")) << lines[1];
}

TEST(stacktrace_print, says_when_frames_are_not_shown) {
    const scoped_environment_variable disabled("FORGE_DISABLE_SYMBOLIZATION", "1");
    std::array<std::uintptr_t, 1> frames{};
    ASSERT_EQ(capture(frames), 1U);

    const std::vector<std::string> lines = lines_of(printed(frames, true));
    ASSERT_EQ(lines.size(), 3U);
    EXPECT_EQ(lines[2], "    (more frames not shown)");
}

// MSVC Release links no PDB, the only place where a Windows binary keeps its function names
// ([stacktrace.build] paragraph 5), so there the tests that check names are skipped. Skipped by the
// preprocessor: MSVC warns about the code after an unconditional GTEST_SKIP.
#if FORGE_COMPILER_MSVC && FORGE_RELEASE
#  define FORGE_TEST_FRAMES_HAVE_NAMES 0
#else
#  define FORGE_TEST_FRAMES_HAVE_NAMES 1
#endif

TEST(stacktrace_print, names_functions_with_a_symbolizer) {
#if !FORGE_TEST_FRAMES_HAVE_NAMES
    GTEST_SKIP() << "MSVC Release links no PDB, so frames have no names";
#else
    if (std::getenv("FORGE_SYMBOLIZER_PATH") == nullptr) {
        GTEST_SKIP() << "set FORGE_SYMBOLIZER_PATH to an llvm-symbolizer to run this test";
    }
    const scoped_environment_variable enabled("FORGE_DISABLE_SYMBOLIZATION", nullptr);
    std::array<std::uintptr_t, 1> frames{};
    [[maybe_unused]] const int capture_line = __LINE__ + 1;
    const std::size_t count = capture(frames);
    ASSERT_EQ(count, 1U);

    const std::vector<std::string> lines = lines_of(printed(frames, false));
    ASSERT_EQ(lines.size(), 2U);
    EXPECT_TRUE(matches(
        lines[1],
        R"(    #0 forge_core_unittests\S*\+0x[0-9a-f]+ .*names_functions_with_a_symbolizer_Test::TestBody.*)"))
        << lines[1];
    // The location is the call's line rather than the next one: the address looked up is one
    // before the return address. Release has no debug information.
#  if !FORGE_RELEASE
    EXPECT_TRUE(matches(lines[1], std::format(R"(.*stacktrace_test\.cpp:{}(:\d+)?)", capture_line)))
        << lines[1];
#  endif
#endif
}

// Without names, print cannot tell a forge::detail frame from any other.
TEST(stacktrace_print, leaves_out_leading_forge_detail_frames) {
#if !FORGE_TEST_FRAMES_HAVE_NAMES
    GTEST_SKIP() << "MSVC Release links no PDB, so frames have no names";
#else
    if (std::getenv("FORGE_SYMBOLIZER_PATH") == nullptr) {
        GTEST_SKIP() << "set FORGE_SYMBOLIZER_PATH to an llvm-symbolizer to run this test";
    }
    const scoped_environment_variable enabled("FORGE_DISABLE_SYMBOLIZATION", nullptr);
    std::array<std::uintptr_t, 2> frames{};
    ASSERT_EQ(forge::detail::capture_in_detail(frames), 2U);

    // The forge::detail frame is left out, so this test is #0.
    const std::vector<std::string> lines = lines_of(printed(frames, false));
    ASSERT_EQ(lines.size(), 2U);
    EXPECT_TRUE(matches(
        lines[1],
        R"(    #0 forge_core_unittests\S*\+0x[0-9a-f]+ .*leaves_out_leading_forge_detail_frames_Test::TestBody.*)"))
        << lines[1];
#endif
}

} // namespace
} // namespace forge::stacktrace
