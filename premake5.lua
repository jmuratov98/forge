-- SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

-- The forge build. `premake5 --help` lists the forge options; `premake5 gmake` (or
-- ninja, xcode4, vs2022, compilecommands) generates into build/, or into --to=DIR.

require("premake", ">=5.0.0")
require "premake/options"
require "premake/forge"

-- Only the configurations and the output location are workspace-wide. Every other
-- setting lives in the projects: forge.baseline() for what must agree across every
-- linked object file, premake/forge.lua for forge's own flags.
workspace "forge"
    configurations { "Debug", "Release", "RelDeb", "Sanitize" }
    location(_OPTIONS.to or "build")

local third_party = nil
if not _OPTIONS["no-tests"] then
    third_party = include "third_party/premake5.lua"
end

forge.emit(include "forge/premake5.lua", third_party)
