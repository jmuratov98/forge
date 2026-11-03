-- What each configuration and option compiles a forge project with. RelDeb is Release plus debug
-- info at the same optimization level, unlike CMake's RelWithDebInfo. forge's warning policy and
-- --werror reach forge projects only: forge.baseline(), all that a third-party project applies,
-- carries none of it. Unwind tables are in forge.baseline(), so that a stack trace does not stop
-- at the first third-party frame.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t/default --cc=clang --os=linux ninja
-- RUN: FileCheck %s --input-file=%t/default/forge_core.ninja --check-prefix=DEFAULT --implicit-check-not=-Werror --implicit-check-not=-flto
-- RUN: %premake --file=%s --to=%t/options --cc=clang --os=linux --assertions --exceptions --std=c++23 --werror --lto ninja
-- RUN: FileCheck %s --input-file=%t/options/forge_core.ninja --check-prefix=OPTIONS
-- RUN: FileCheck %s --input-file=%t/options/third_party_stub.ninja --check-prefix=THIRD-PARTY --implicit-check-not=-Werror --implicit-check-not=-Wundef --implicit-check-not=-Wpedantic

-- DEFAULT:      cxxflags_forge_core_Debug = -O0 -g -Wall -Wextra -std=c++20 -fno-exceptions -fno-rtti
-- DEFAULT-SAME: -D"FORGE_EXCEPTIONS_ENABLED=0" -D"FORGE_DEBUG=1" -D"FORGE_RELEASE=0" -D"FORGE_RELDEB=0" -D"FORGE_SANITIZE=0" -D"FORGE_ASSERTIONS_ENABLED=1" -D"_GLIBCXX_ASSERTIONS" -D"_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE" -D"FORGE_SHARED=0" -D"FORGE_BUILDING_SHARED=0"
-- DEFAULT-SAME: -fasynchronous-unwind-tables -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Wnon-virtual-dtor -Woverloaded-virtual -Wimplicit-fallthrough -Wold-style-cast -Wundef{{$}}
-- DEFAULT:      cxxflags_forge_core_Release = [[OPT:-O[^ ]+]] -Wall
-- DEFAULT-SAME: -fno-rtti
-- DEFAULT-SAME: -D"FORGE_DEBUG=0" -D"FORGE_RELEASE=1" -D"FORGE_RELDEB=0" -D"FORGE_SANITIZE=0" -D"NDEBUG" -D"FORGE_ASSERTIONS_ENABLED=0" -D"FORGE_SHARED=0"
-- DEFAULT:      cxxflags_forge_core_RelDeb = [[OPT]] -g -Wall
-- DEFAULT-SAME: -D"FORGE_DEBUG=0" -D"FORGE_RELEASE=0" -D"FORGE_RELDEB=1" -D"FORGE_SANITIZE=0" -D"NDEBUG" -D"FORGE_ASSERTIONS_ENABLED=0" -D"FORGE_SHARED=0"
-- DEFAULT:      cxxflags_forge_core_Sanitize = -Og -fsanitize=address -fsanitize=undefined -g -Wall
-- DEFAULT-SAME: -D"FORGE_DEBUG=0" -D"FORGE_RELEASE=0" -D"FORGE_RELDEB=0" -D"FORGE_SANITIZE=1" -D"FORGE_ASSERTIONS_ENABLED=1" -D"_GLIBCXX_ASSERTIONS"
-- DEFAULT-SAME: -fno-omit-frame-pointer -fno-sanitize-recover=all -fno-sanitize=vptr

-- --assertions applies to every configuration; LTO only to Release and RelDeb.
-- OPTIONS:      cxxflags_forge_core_Debug = -Werror -O0 -g -Wall -Wextra -std=c++23 -fno-rtti -D"FORGE_EXCEPTIONS_ENABLED=1"
-- OPTIONS:      cxxflags_forge_core_Release = -Werror -flto -O{{[^ ]+}} -Wall -Wextra -std=c++23 -fno-rtti -D"FORGE_EXCEPTIONS_ENABLED=1"
-- OPTIONS-SAME: -D"NDEBUG" -D"FORGE_ASSERTIONS_ENABLED=1" -D"_GLIBCXX_ASSERTIONS"
-- OPTIONS:      cxxflags_forge_core_RelDeb = -Werror -flto
-- OPTIONS-SAME: -D"FORGE_ASSERTIONS_ENABLED=1"
-- OPTIONS:      cxxflags_forge_core_Sanitize = -Werror -Og

-- THIRD-PARTY:      cxxflags_third_party_stub_Debug = -O0 -g -w -std=c++23 -fno-rtti -D"FORGE_EXCEPTIONS_ENABLED=1" -D"FORGE_DEBUG=1"
-- THIRD-PARTY-SAME: -D"FORGE_ASSERTIONS_ENABLED=1"
-- THIRD-PARTY-SAME: -fasynchronous-unwind-tables

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core" })

forge.emit({ forge.component { "core" } }, third_party)
