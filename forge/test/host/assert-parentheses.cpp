// FORGE_ASSERT keeps the compiler's warning for an assignment used as a condition, in every build:
// it tests `if (cond)`, not `if (!(cond))`, whose parentheses would hide FORGE_ASSERT(x = 0).
//
// DEFINE: %{compile} = %host_cxx_syntax %host_werror -UFORGE_ASSERTIONS_ENABLED %s
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=0
// RUN: %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=0
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=0 -DCASE=1 2>&1 | FileCheck %s
// RUN: not %{compile} -DFORGE_ASSERTIONS_ENABLED=1 -DCASE=1 2>&1 | FileCheck %s
//
// GCC ends the warning with [-Werror=parentheses], Clang with [-Werror,-Wparentheses]; MSVC calls
// it C4706.
// CHECK: {{parentheses\]|C4706}}

#include "forge/core/assert.hpp"

int reset(int value) {
#if CASE == 0
    FORGE_ASSERT((value = 0) == 0);
#else
    FORGE_ASSERT(value = 0);
#endif
    return value;
}
