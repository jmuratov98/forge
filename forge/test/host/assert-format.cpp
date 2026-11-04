// A check's message is checked against its arguments at compile time in every build, although it
// is only formatted when the check fails, so Release cannot break on a format string.
//
// DEFINE: %{compile} = %host_cxx_syntax -UFORGE_ASSERTIONS_ENABLED %s
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=0
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=0
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=1 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=1 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=2 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=2 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=3 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=3 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=4 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=4 2>&1 | FileCheck %s
//
// Every compiler names the format string type in its error.
// CHECK: basic_format_string

#include "forge/core/assert.hpp"

int checked(int value) {
#if CASE == 0
    FORGE_ASSERT(value > 0, "{} and {:x}", value, value);
#elif CASE == 1
    // Too few arguments.
    FORGE_ASSERT(value > 0, "{} and {}", value);
#elif CASE == 2
    // A format specification the argument's type does not have.
    FORGE_ASSERT(value > 0, "{:s}", value);
#elif CASE == 3
    if (value < 0) {
        FORGE_UNREACHABLE("negative {}");
    }
#elif CASE == 4
    if (value < 0) {
        FORGE_TODO("negative {", value);
    }
#endif
    return value;
}
