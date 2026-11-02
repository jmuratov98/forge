-- With --shared, every component's sources build one libforge with hidden visibility, the only
-- project that exports (FORGE_BUILDING_SHARED); unit tests and the host tests import from it. With
-- no sources at all there is no library, and nothing links one.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t/sources --cc=clang --os=linux --shared ninja
-- RUN: FileCheck %s --input-file=%t/sources/forge.ninja --check-prefix=LIBRARY
-- RUN: FileCheck %s --input-file=%t/sources/forge_core_unittests.ninja --check-prefix=TEST --implicit-check-not=-fvisibility
-- RUN: FileCheck %s --input-file=%t/sources/Debug/test/lit.site.cfg.py --check-prefix=HOST --implicit-check-not=-fvisibility
-- RUN: env FIXTURE_SOURCES=none %premake --file=%s --to=%t/headers --cc=clang --os=linux --shared ninja
-- RUN: FileCheck %s --input-file=%t/headers/forge_core_unittests.ninja --check-prefix=HEADERS

-- LIBRARY:      cxxflags_forge_Debug = {{.*}}-fvisibility=hidden{{.*}}-fvisibility-inlines-hidden
-- LIBRARY-SAME: -D"FORGE_SHARED=1" -D"FORGE_BUILDING_SHARED=1"
-- LIBRARY:      build Debug/bin/libforge.so: link_clang Debug/obj/forge/core.o Debug/obj/forge/support.o{{$}}

-- TEST: cxxflags_forge_core_unittests_Debug = {{.*}}-D"FORGE_SHARED=1" -D"FORGE_BUILDING_SHARED=0"
-- TEST: links_forge_core_unittests_Debug = Debug/bin/libforge.so Debug/bin/libthird_party_stub.a -lpthread{{$}}

-- HOST: config.forge_host_cxx = {{.*}}"-DFORGE_SHARED=1", "-DFORGE_BUILDING_SHARED=0"

-- HEADERS: links_forge_core_unittests_Debug = Debug/bin/libthird_party_stub.a -lpthread{{$}}

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local sources = os.getenv("FIXTURE_SOURCES") == "none" and {} or { "core", "support" }
local third_party = fixture.workspace(sources)

forge.emit({
    forge.component { "support" },
    forge.component { "core", dependencies = { "support" } },
    forge.test { "core", dependencies = { "core" } },
}, third_party)
