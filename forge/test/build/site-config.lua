-- Every configuration gets a lit site config whose features say how it is built, from the same
-- settings that set its defines, and whose host compiler command has exactly the flags forge's
-- consumers get: defines unquoted, include paths absolute, no third-party include paths. Without
-- unit tests there is no unittests site config.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t/default --cc=clang --os=linux ninja
-- RUN: FileCheck %s --input-file=%t/default/Debug/test/lit.site.cfg.py --check-prefix=DEBUG --implicit-check-not=third_party
-- RUN: FileCheck %s --input-file=%t/default/Release/test/lit.site.cfg.py --check-prefix=RELEASE
-- RUN: FileCheck %s --input-file=%t/default/Sanitize/unittests/lit.site.cfg.py --check-prefix=UNITTESTS
-- RUN: %premake --file=%s --to=%t/options --cc=gcc --os=linux --assertions --exceptions --shared --std=c++23 --sanitizers=thread ninja
-- RUN: FileCheck %s --input-file=%t/options/Release/test/lit.site.cfg.py --check-prefix=OPTIONS
-- RUN: FileCheck %s --input-file=%t/options/Sanitize/test/lit.site.cfg.py --check-prefix=OPTIONS-SANITIZE
-- RUN: env FIXTURE_TESTS=none %premake --file=%s --to=%t/no-tests --cc=clang --os=linux ninja
-- RUN: cat %t/no-tests/Debug/test/lit.site.cfg.py
-- RUN: not cat %t/no-tests/Debug/unittests/lit.site.cfg.py

-- DEBUG:      config.test_exec_root = "{{.*}}/default/Debug/test"
-- DEBUG:      config.forge_bin_dir = "{{.*}}/default/Debug/bin"
-- DEBUG:      config.forge_configuration = "Debug"
-- DEBUG:      config.forge_features = ["debug", "host-std-c++20", "asserts"]
-- DEBUG:      config.forge_host_cxx = ["clang++", "-O0", "-g", "-Wall", "-Wextra", "-std=c++20", "-fno-exceptions", "-fno-rtti", "-DFORGE_EXCEPTIONS_ENABLED=0", "-DFORGE_DEBUG=1",
-- DEBUG-SAME: "-I{{[^"]*}}/default/tree/forge/include", "-I{{[^"]*}}/default/tree/forge/source", "-Wpedantic",
-- DEBUG-SAME: "-Wundef"]
-- DEBUG:      config.forge_host_cxx_family = "clang"
-- DEBUG:      lit_config.load_config(config, "{{.*}}/default/tree/forge/test/lit.cfg.py")

-- RELEASE: config.forge_features = ["release", "host-std-c++20"]

-- UNITTESTS: config.forge_bin_dir = "{{.*}}/default/Sanitize/bin"
-- UNITTESTS: config.forge_features = ["sanitize", "host-std-c++20", "asserts", "asan", "ubsan"]
-- UNITTESTS: lit_config.load_config(config, "{{.*}}/default/tree/forge/unittests/lit.cfg.py")

-- OPTIONS: config.forge_features = ["release", "host-std-c++23", "asserts", "exceptions", "shared"]
-- OPTIONS: config.forge_host_cxx = ["g++",
-- OPTIONS: config.forge_host_cxx_family = "gcc"

-- OPTIONS-SANITIZE: config.forge_features = ["sanitize", "host-std-c++23", "asserts", "exceptions", "shared", "tsan"]
-- OPTIONS-SANITIZE: config.forge_host_cxx = {{.*}}"-fsanitize=thread"

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core" })
if os.getenv("FIXTURE_TESTS") == "none" then
    third_party = nil
end

forge.emit({
    forge.component { "core" },
    forge.test { "core", dependencies = { "core" } },
}, third_party)
