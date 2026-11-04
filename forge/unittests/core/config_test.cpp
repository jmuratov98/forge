// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/config.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

// Declared but never defined: only checks that FORGE_API is accepted where forge puts it.
// Internal linkage would make the visibility attribute meaningless, so these stay outside the
// anonymous namespace.
namespace forge::config_test {

[[nodiscard]] FORGE_API int exported_function();

class FORGE_API exported_class { // NOLINT(misc-use-internal-linkage): needs external linkage
public:
    [[nodiscard]] int value() const;
};

} // namespace forge::config_test

namespace forge {
namespace {

static_assert(FORGE_COMPILER_CLANG + FORGE_COMPILER_GCC + FORGE_COMPILER_MSVC == 1);
static_assert(FORGE_HOST_WINDOWS + FORGE_HOST_LINUX + FORGE_HOST_MACOS == 1);
static_assert(FORGE_HOST_POSIX == FORGE_HOST_LINUX + FORGE_HOST_MACOS);
static_assert(FORGE_HOST_X86_64 + FORGE_HOST_AARCH64 <= 1);
static_assert(FORGE_DEBUG + FORGE_RELEASE + FORGE_RELDEB + FORGE_SANITIZE == 1);

#define FORGE_TEST_SUFFIX suffix

static_assert(std::string_view(FORGE_STRINGIFY(FORGE_TEST_SUFFIX)) == "suffix");
static_assert(std::string_view(FORGE_STRINGIFY(FORGE_SHARED)) == (FORGE_SHARED ? "1" : "0"));

constexpr int FORGE_CONCAT(g_concat_, FORGE_TEST_SUFFIX) = 1;
static_assert(g_concat_suffix == 1);

FORGE_ALWAYS_INLINE int always_inline_add(int a, int b) {
    return a + b;
}

FORGE_NOINLINE int noinline_add(int a, int b) {
    return a + b;
}

FORGE_COLD int cold_add(int a, int b) {
    return a + b;
}

FORGE_RETURNS_NONNULL FORGE_RETURNS_NOALIAS void* checked_allocate(std::size_t size) {
    void* result = std::malloc(size);
    if (result == nullptr) {
        std::abort();
    }
    return result;
}

std::string_view first_word(const std::string& text FORGE_LIFETIMEBOUND) {
    return std::string_view(text).substr(0, text.find(' '));
}

class node {
public:
    explicit node(int value) : m_value(value) {}

    FORGE_DUMP_METHOD void dump(std::string& out) const {
        out += "node ";
        out += std::to_string(m_value);
    }

private:
    int m_value;
};

struct empty {};

struct holder {
    FORGE_NO_UNIQUE_ADDRESS empty tag;
    int value;
};

// clang-cl before 18 has no [[msvc::no_unique_address]], and the MSVC ABI ignores the
// standard spelling.
#if !defined(_MSC_VER) || __has_cpp_attribute(msvc::no_unique_address)
static_assert(sizeof(holder) == sizeof(int));
#endif

// Without the IGNORE lines, the inner `value` shadowing the parameter fails a --werror build.
int shadowing_increment(int value) {
    int result = value;
    FORGE_WARNINGS_PUSH
    FORGE_WARNING_IGNORE_CLANG("-Wshadow")
    FORGE_WARNING_IGNORE_GCC("-Wshadow")
    FORGE_WARNING_IGNORE_MSVC(4457)
    {
        const int value = result + 1;
        result = value;
    }
    FORGE_WARNINGS_POP
    return result;
}

enum class color : std::uint8_t { red, green };

int color_index(color c) {
    switch (c) {
    case color::red:
        return 0;
    case color::green:
        return 1;
    }
    FORGE_BUILTIN_UNREACHABLE();
}

TEST(config, attributes) {
    EXPECT_EQ(always_inline_add(1, 2), 3);
    EXPECT_EQ(noinline_add(1, 2), 3);
    EXPECT_EQ(cold_add(1, 2), 3);

    const std::string text = "hello world";
    EXPECT_EQ(first_word(text), "hello");

    std::string out;
    node(7).dump(out);
    EXPECT_EQ(out, "node 7");

    const holder h{.tag = {}, .value = 5};
    EXPECT_EQ(h.value, 5);
}

TEST(config, warnings) {
    EXPECT_EQ(shadowing_increment(1), 2);
}

TEST(config, builtin_unreachable) {
    EXPECT_EQ(color_index(color::red), 0);
    EXPECT_EQ(color_index(color::green), 1);
}

// ThreadSanitizer does not support the fork that death tests use.
#if GTEST_HAS_DEATH_TEST && !FORGE_TSAN_ENABLED
TEST(config, builtin_trap) {
    EXPECT_DEATH(FORGE_BUILTIN_TRAP(), "");
}
#endif

TEST(config, asan_poison) {
    auto* block = static_cast<unsigned char*>(checked_allocate(64));
    FORGE_ASAN_POISON(block, 64);
#if FORGE_ASAN_ENABLED
    EXPECT_TRUE(__asan_address_is_poisoned(block));
#endif
    FORGE_ASAN_UNPOISON(block, 64);
    block[63] = 1;
    EXPECT_EQ(block[63], 1);
    std::free(block);
}

} // namespace
} // namespace forge
