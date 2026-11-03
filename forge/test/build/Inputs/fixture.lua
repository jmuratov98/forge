-- For the build tests that generate projects: a workspace in --to with all four configurations, a
-- forge tree under it, and a third-party library set up the way third_party/premake5.lua sets up
-- googletest, which is to say with forge.baseline() alone.

require "premake/options"
require "premake/forge"

fixture = {}

-- `sources` names the components that get a .cpp file; any other component is header-only. Returns
-- the table forge.emit takes for third_party.
function fixture.workspace(sources)
    forge.root = path.join(_OPTIONS.to, "tree")
    os.mkdir(forge.root)
    io.writefile(path.join(forge.root, "VERSION"), "1.2.3-fixture\n")
    for _, name in ipairs(sources) do
        local dir = path.join(forge.root, "forge/source/forge", name)
        os.mkdir(dir)
        io.writefile(path.join(dir, name .. ".cpp"), "")
    end

    local third_party_source = path.join(_OPTIONS.to, "third_party/stub.cpp")
    os.mkdir(path.getdirectory(third_party_source))
    io.writefile(third_party_source, "")

    workspace "fixture"
        configurations { "Debug", "Release", "RelDeb", "Sanitize" }
        location(_OPTIONS.to)

    group "third_party"
    project "third_party_stub"
        kind "StaticLib"
        forge.baseline()
        warnings "Off"
        files { third_party_source }
    group ""

    return {
        googletest = {
            includedirs = { path.join(_OPTIONS.to, "third_party/include") },
            links = { "third_party_stub" },
        },
    }
end
