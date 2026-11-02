-- SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

-- Third-party libraries built inside the forge workspace. They apply forge.baseline()
-- (standard, RTTI, exceptions, sanitizers) so every object file linked together
-- agrees on it, but never forge's warning flags. The returned
-- table says what a forge project needs in order to use each library.

local googletest = path.join(_SCRIPT_DIR, "googletest/googletest")

if not os.isdir(googletest) then
    error("googletest not found at third_party/googletest: check it out there, or pass --no-tests", 0)
end

group "third_party"

project "googletest"
    kind "StaticLib"
    forge.baseline()
    warnings "Off"
    includedirs { path.join(googletest, "include"), googletest }
    -- In an archive, gtest_main.o is only pulled in when a test does not define main.
    files {
        path.join(googletest, "src/gtest-all.cc"),
        path.join(googletest, "src/gtest_main.cc"),
    }

group ""

return {
    googletest = {
        includedirs = { path.join(googletest, "include") },
        links = { "googletest" },
    },
}
