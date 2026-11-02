// forge/core/config.hpp rejects a compile that does not get each build macro as 0 or 1, naming the
// first macro that is wrong, and one whose macros contradict each other or the compiler. The
// build passes them all, so this only happens outside it.
//
// DEFINE: %{compile} = %host_cxx_syntax %s
// RUN: %{compile}
// RUN: not %{compile} -UFORGE_ASSERTIONS_ENABLED 2>&1 | FileCheck %s --check-prefix=ASSERTIONS
// RUN: not %{compile} -UFORGE_ASSERTIONS_ENABLED -DFORGE_ASSERTIONS_ENABLED=2 2>&1 | FileCheck %s --check-prefix=ASSERTIONS
// RUN: not %{compile} -UFORGE_EXCEPTIONS_ENABLED 2>&1 | FileCheck %s --check-prefix=EXCEPTIONS
// RUN: not %{compile} -UFORGE_SHARED 2>&1 | FileCheck %s --check-prefix=SHARED
// RUN: not %{compile} -UFORGE_BUILDING_SHARED 2>&1 | FileCheck %s --check-prefix=BUILDING-SHARED
// RUN: not %{compile} -UFORGE_DEBUG 2>&1 | FileCheck %s --check-prefix=DEBUG
// RUN: not %{compile} -UFORGE_RELEASE 2>&1 | FileCheck %s --check-prefix=RELEASE
// RUN: not %{compile} -UFORGE_RELDEB 2>&1 | FileCheck %s --check-prefix=RELDEB
// RUN: not %{compile} -UFORGE_SANITIZE -DFORGE_SANITIZE=2 2>&1 | FileCheck %s --check-prefix=SANITIZE
// RUN: not %{compile} -UFORGE_DEBUG -DFORGE_DEBUG=1 -UFORGE_RELEASE -DFORGE_RELEASE=1 -UFORGE_RELDEB -DFORGE_RELDEB=0 -UFORGE_SANITIZE -DFORGE_SANITIZE=0 2>&1 | FileCheck %s --check-prefix=ONE-CONFIGURATION
// RUN: not %{compile} -UFORGE_DEBUG -DFORGE_DEBUG=0 -UFORGE_RELEASE -DFORGE_RELEASE=0 -UFORGE_RELDEB -DFORGE_RELDEB=0 -UFORGE_SANITIZE -DFORGE_SANITIZE=0 2>&1 | FileCheck %s --check-prefix=ONE-CONFIGURATION
// RUN: not %{compile} -UFORGE_SHARED -DFORGE_SHARED=0 -UFORGE_BUILDING_SHARED -DFORGE_BUILDING_SHARED=1 2>&1 | FileCheck %s --check-prefix=BUILDING-WITHOUT-SHARED
// RUN: not %{compile} -UFORGE_EXCEPTIONS_ENABLED -DFORGE_EXCEPTIONS_ENABLED=%if exceptions %{0%} %else %{1%} 2>&1 | FileCheck %s --check-prefix=EXCEPTIONS-MISMATCH
//
// ASSERTIONS: FORGE_ASSERTIONS_ENABLED must be defined to 0 or 1; the build passes it
// EXCEPTIONS: FORGE_EXCEPTIONS_ENABLED must be defined to 0 or 1; the build passes it
// SHARED: FORGE_SHARED must be defined to 0 or 1; the build passes it
// BUILDING-SHARED: FORGE_BUILDING_SHARED must be defined to 0 or 1; the build passes it
// DEBUG: FORGE_DEBUG must be defined to 0 or 1; the build passes it
// RELEASE: FORGE_RELEASE must be defined to 0 or 1; the build passes it
// RELDEB: FORGE_RELDEB must be defined to 0 or 1; the build passes it
// SANITIZE: FORGE_SANITIZE must be defined to 0 or 1; the build passes it
// ONE-CONFIGURATION: exactly one of FORGE_DEBUG, FORGE_RELEASE, FORGE_RELDEB and FORGE_SANITIZE must be 1
// BUILDING-WITHOUT-SHARED: FORGE_BUILDING_SHARED requires FORGE_SHARED
// EXCEPTIONS-MISMATCH: FORGE_EXCEPTIONS_ENABLED disagrees with whether the compiler has exceptions enabled

#include "forge/core/config.hpp"
