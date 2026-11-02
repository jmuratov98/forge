// Under forge's flags, a macro that #if tests must be defined, so a misspelled FORGE_ macro or a
// missing include cannot quietly read as 0. MSVC's equivalent, C4668, stays off because the
// Windows SDK headers trigger it.
//
// REQUIRES: host-cxx-clang || host-cxx-gcc
// RUN: %host_cxx_syntax %host_werror -DCASE=0 %s
// RUN: not %host_cxx_syntax %host_werror -DCASE=1 %s 2>&1 | FileCheck %s
//
// Compilers and their versions quote the name and the 0 differently.
// CHECK: FORGE_TYPO{{.}} is not defined, evaluates to {{'?}}0

#include "forge/core/config.hpp"

#if CASE == 0
#  if FORGE_COMPILER_CLANG
#  endif
#else
#  if FORGE_TYPO
#  endif
#endif
