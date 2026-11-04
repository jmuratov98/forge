-- What stack traces need from the build (docs/stacktrace.md): no binary is stripped, Release
-- included, with any toolset, so that llvm-symbolizer finds the right function names; and on
-- macOS, where debug information stays in the object files, dsymutil makes a .dSYM next to each
-- linked binary in every configuration with debug information, test executables and the shared
-- libforge alike.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t/gcc-linux --cc=gcc --os=linux ninja
-- RUN: FileCheck %s --input-file=%t/gcc-linux/forge_core_unittests.ninja --check-prefix=UNSTRIPPED --implicit-check-not=dsymutil
-- RUN: %premake --file=%s --to=%t/gcc-macos --cc=gcc --os=macosx ninja
-- RUN: FileCheck %s --input-file=%t/gcc-macos/forge_core_unittests.ninja --check-prefixes=UNSTRIPPED,DSYM
-- RUN: %premake --file=%s --to=%t/clang-macos --cc=clang --os=macosx --shared ninja
-- RUN: FileCheck %s --input-file=%t/clang-macos/forge.ninja --check-prefix=DSYM-SHARED

-- UNSTRIPPED-NOT: {{^}}ldflags_forge_core_unittests_Release = {{(.* )?}}-s{{( |$)}}
-- UNSTRIPPED-NOT: -Wl,-x

-- DSYM: postbuildcommands = {{.*}}dsymutil {{[^ ]*}}Debug/bin/forge_core_unittests
-- DSYM-NOT: dsymutil {{[^ ]*}}Release/
-- DSYM: postbuildcommands = {{.*}}dsymutil {{[^ ]*}}RelDeb/bin/forge_core_unittests
-- DSYM: postbuildcommands = {{.*}}dsymutil {{[^ ]*}}Sanitize/bin/forge_core_unittests

-- DSYM-SHARED: postbuildcommands = {{.*}}dsymutil {{[^ ]*}}Debug/bin/libforge.dylib

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core" })

-- premake links a binary only from object files, so the unit test needs a source of its own.
local test_dir = path.join(forge.root, "forge/unittests/core")
os.mkdir(test_dir)
io.writefile(path.join(test_dir, "core_test.cpp"), "")

forge.emit({
    forge.component { "core" },
    forge.test { "core", dependencies = { "core" } },
}, third_party)
