// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

#include <string_view>

// forge's version and bug-report URL (docs/version.md). Both strings have static storage duration
// and are followed by a null character.

namespace forge {

// The base version from the VERSION file, such as 0.1.0-dev, and in every configuration but
// Release, SemVer build metadata with the time the build files were generated:
// 0.1.0-dev+20261102T143005Z. Release has no timestamp, so that building the same sources twice
// gives the same binary.
[[nodiscard]] FORGE_API std::string_view version() noexcept;

// Where failure reports ask users to report bugs, from premake's --bug-report-url; empty when the
// build sets none.
[[nodiscard]] FORGE_API std::string_view bug_report_url() noexcept;

} // namespace forge
