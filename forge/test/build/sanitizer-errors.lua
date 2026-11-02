-- --sanitizers accepts only combinations that the compiler can build and that need no instrumented
-- standard library.
--
-- RUN: not %premake --file=%s --to=%t --sanitizers=memory ninja 2>&1 | FileCheck %s --check-prefix=UNKNOWN
-- RUN: not %premake --file=%s --to=%t --sanitizers=, ninja 2>&1 | FileCheck %s --check-prefix=EMPTY
-- RUN: not %premake --file=%s --to=%t --sanitizers=thread,address ninja 2>&1 | FileCheck %s --check-prefix=THREAD-ADDRESS
-- RUN: not %premake --file=%s --to=%t --sanitizers=address,undefined vs2022 2>&1 | FileCheck %s --check-prefix=VISUAL-STUDIO
-- RUN: %premake --file=%s --to=%t --sanitizers=address vs2022
-- RUN: %premake --file=%s --to=%t --sanitizers=thread,undefined ninja

-- UNKNOWN: --sanitizers: unknown sanitizer 'memory' (expected address, undefined or thread)
-- EMPTY: --sanitizers: the list is empty
-- THREAD-ADDRESS: --sanitizers: thread cannot be combined with address
-- VISUAL-STUDIO: --sanitizers: Visual Studio only supports address

require "premake/options"
require "premake/forge"

workspace "fixture"
    configurations { "Debug", "Sanitize" }
    location(_OPTIONS.to)

forge.emit({ forge.component { "core" } }, nil)
