// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

namespace forge {

// Selects a constructor that builds the held object from the remaining arguments. forge's own
// rather than std::in_place_t, so that it and forge::in_place_failure_t come from forge and name
// the state they select.
struct in_place_t {
    explicit in_place_t() = default;
};
// A tag, spelled like std::in_place rather than as a g_ global.
inline constexpr in_place_t in_place{}; // NOLINT(readability-identifier-naming)

} // namespace forge
