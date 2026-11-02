// A check that fails during constant evaluation is a compile error in every build, and the
// compiler's error names the kind of check through the function the macro calls.
//
// DEFINE: %{compile} = %host_cxx_syntax -UFORGE_ASSERTIONS_ENABLED %s
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=0
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=0
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=1 2>&1 | FileCheck %s --check-prefix=ASSERT
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=1 2>&1 | FileCheck %s --check-prefix=ASSERT
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=2 2>&1 | FileCheck %s --check-prefix=UNREACHABLE
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=2 2>&1 | FileCheck %s --check-prefix=UNREACHABLE
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=3 2>&1 | FileCheck %s --check-prefix=TODO
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=3 2>&1 | FileCheck %s --check-prefix=TODO

#include "forge/core/assert.hpp"

#include <cstdint>

constexpr int halve(int value) {
    FORGE_ASSERT(value % 2 == 0, "{} is odd", value);
    return value / 2;
}

enum class shape : std::uint8_t { circle, square };

constexpr int corners(shape s) {
    switch (s) {
    case shape::circle:
        return 0;
    case shape::square:
        return 4;
    }
    FORGE_UNREACHABLE("invalid shape {}", static_cast<int>(s));
}

constexpr int fold(int value) {
    if (value < 0) {
        FORGE_TODO("folding {}", value);
    }
    return value;
}

#if CASE == 0
static_assert(halve(8) == 4);
static_assert(corners(shape::square) == 4);
static_assert(fold(1) == 1);
#elif CASE == 1
// ASSERT: assertion_failed
static_assert(halve(3) == 1);
#elif CASE == 2
// UNREACHABLE: unreachable_reached
static_assert(corners(static_cast<shape>(7)) == 0);
#elif CASE == 3
// TODO: todo_reached
static_assert(fold(-1) == -1);
#endif
