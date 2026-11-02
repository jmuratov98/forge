-- --cxx-path, --cc-path and --ar-path replace the tool names of the gcc and clang toolsets wherever a
-- tool runs: the ninja rules, including the archiver that --lto would otherwise switch to gcc-ar, and
-- the host compiler of the lit site config. A tool without a path keeps the toolset's name.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t/gcc --cc=gcc --os=linux --lto --cxx-path=/opt/gcc/bin/g++-16 --cc-path=/opt/gcc/bin/gcc-16 --ar-path=/opt/gcc/bin/gcc-ar-16 ninja
-- RUN: FileCheck %s --input-file=%t/gcc/forge_core.ninja --check-prefix=GCC
-- RUN: FileCheck %s --input-file=%t/gcc/Debug/test/lit.site.cfg.py --check-prefix=SITE
-- RUN: %premake --file=%s --to=%t/clang --cc=clang --os=linux --cxx-path=/opt/llvm/bin/clang++ ninja
-- RUN: FileCheck %s --input-file=%t/clang/forge_core.ninja --check-prefix=CLANG
--
-- GCC:      command = /opt/gcc/bin/gcc-16 $cflags -c
-- GCC:      command = /opt/gcc/bin/g++-16 $cxxflags -c
-- GCC:      command = /opt/gcc/bin/gcc-ar-16 -rcs
-- GCC:      command = /opt/gcc/bin/g++-16 -o $out
-- SITE:     config.forge_host_cxx = ["/opt/gcc/bin/g++-16", "-O0"
-- CLANG:    command = clang $cflags -c
-- CLANG:    command = /opt/llvm/bin/clang++ $cxxflags -c
-- CLANG:    command = ar -rcs
-- CLANG:    command = /opt/llvm/bin/clang++ -o $out

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core" })

forge.emit({
    forge.component { "core" },
}, third_party)
