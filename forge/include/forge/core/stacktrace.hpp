// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <span>

namespace forge::stacktrace {

// [stacktrace.capture], capture
FORGE_NOINLINE FORGE_API std::size_t capture(std::span<std::uintptr_t> frames,
                                             std::size_t skip = 0) noexcept;

// [stacktrace.print], output
FORGE_API void
print(std::FILE* file, std::span<const std::uintptr_t> frames, bool truncated) noexcept;

} // namespace forge::stacktrace
