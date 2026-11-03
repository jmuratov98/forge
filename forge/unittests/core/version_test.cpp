// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/version.hpp"

#include "forge/core/config.hpp"

#include <gtest/gtest.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <memory>
#include <regex>
#include <string>
#include <string_view>

namespace forge {
namespace {

TEST(version, begins_with_the_version_file) {
    // forge/unittests/lit.cfg.py sets it; run directly, the test has no way to find VERSION.
    const char* root = std::getenv("FORGE_SOURCE_ROOT");
    if (root == nullptr) {
        GTEST_SKIP() << "set FORGE_SOURCE_ROOT to the repository to run this test";
    }
    std::ifstream file(std::filesystem::path(root) / "VERSION");
    std::string base;
    ASSERT_TRUE(std::getline(file, base)) << "cannot read VERSION in " << root;
    EXPECT_TRUE(version().starts_with(base)) << version();
}

TEST(version, has_a_build_timestamp_except_in_release) {
    const std::string version_text(version());
    const std::string::size_type plus = version_text.find('+');
#if FORGE_RELEASE
    EXPECT_EQ(plus, std::string::npos) << version_text;
#else
    ASSERT_NE(plus, std::string::npos) << version_text;
    EXPECT_TRUE(std::regex_match(version_text.substr(plus), std::regex(R"(\+\d{8}T\d{6}Z)")))
        << version_text;
#endif
}

TEST(version, strings_are_null_terminated) {
    for (const std::string_view text : {version(), bug_report_url()}) {
        EXPECT_EQ(text.find('\0'), std::string_view::npos);
        EXPECT_EQ(*std::to_address(text.end()), '\0');
    }
}

} // namespace
} // namespace forge
