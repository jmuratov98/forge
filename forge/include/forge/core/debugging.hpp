// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

namespace forge {

FORGE_ALWAYS_INLINE void breakpoint() {
    FORGE_BUILTIN_BREAKPOINT();
}

} // namespace forge
