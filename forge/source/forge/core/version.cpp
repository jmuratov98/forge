// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/version.hpp"

// Written by premake into the build directory. No other file includes it, so a new build
// timestamp recompiles this file alone.
#include "forge/core/version.inc"

#include <string_view>

namespace forge {

std::string_view version() noexcept {
#if FORGE_RELEASE
    return FORGE_DETAIL_VERSION_BASE;
#else
    return FORGE_DETAIL_VERSION_BASE "+" FORGE_DETAIL_VERSION_BUILD;
#endif
}

std::string_view bug_report_url() noexcept {
    return FORGE_DETAIL_BUG_REPORT_URL;
}

} // namespace forge
