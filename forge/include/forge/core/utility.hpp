// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

#include <version>

namespace forge {

// std::is_constant_evaluated(), which forge would otherwise use directly, except that GCC warns
// (-Wtautological-compare) wherever it is called in a non-constexpr function, as the macros in
// forge/core/assert.hpp do.
constexpr bool is_constant_evaluated() {
#ifdef __cpp_if_consteval
    if consteval {
        return true;
    } else {
        return false;
    }
#else
    return __builtin_is_constant_evaluated();
#endif
}

[[noreturn]] FORGE_ALWAYS_INLINE void unreachable() noexcept {
    FORGE_BUILTIN_UNREACHABLE();
}

} // namespace forge
