-- SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

-- The forge project DSL. Description files (forge/premake5.lua) return a list of
-- forge.component and forge.test values; forge.emit turns that list into projects.
-- Keeping descriptions as plain data lets this file alone decide the project shape:
-- one shared libforge (--shared) or one static library per component.

forge = {}

-- The directory that holds the forge/ tree. Build-system tests point it at a fixture tree.
forge.root = _MAIN_SCRIPT_DIR

local known_keys = { dependencies = true }

local function is_name(value)
    return type(value) == "string" and value:match("^[a-z][a-z0-9_]*$") ~= nil
end

-- Level 3 points the error at the description file that called forge.component/test.
local function describe(kind, spec)
    if type(spec) ~= "table" then
        error(string.format("forge.%s expects a table: forge.%s { \"name\", ... }", kind, kind), 3)
    end

    local name = spec[1]
    if not is_name(name) then
        error(string.format("forge.%s: the first entry must be a snake_case name, got '%s'",
            kind, tostring(name)), 3)
    end

    for key in pairs(spec) do
        if type(key) == "number" and key ~= 1 then
            error(string.format("forge.%s '%s': unexpected positional entry %d", kind, name, key), 3)
        elseif type(key) ~= "number" and not known_keys[key] then
            error(string.format("forge.%s '%s': unknown key '%s'", kind, name, tostring(key)), 3)
        end
    end

    local dependencies = spec.dependencies or {}
    local seen = {}
    for _, dependency in ipairs(dependencies) do
        if not is_name(dependency) then
            error(string.format("forge.%s '%s': dependency '%s' is not a snake_case name",
                kind, name, tostring(dependency)), 3)
        end
        if seen[dependency] then
            error(string.format("forge.%s '%s': dependency '%s' is listed twice",
                kind, name, dependency), 3)
        end
        seen[dependency] = true
    end

    return { kind = kind, name = name, dependencies = dependencies }
end

-- Not tail calls: those would drop these frames from the stack, and describe's errors would point
-- past the description file.
function forge.component(spec)
    local description = describe("component", spec)
    return description
end

function forge.test(spec)
    local description = describe("test", spec)
    return description
end

local function fail(format, ...)
    error(string.format(format, ...), 0)
end

-- --cxx-path, --cc-path and --ar-path replace the tool names of the gcc and clang toolsets. The
-- generated build files and the lit site configs both get their tool names from gettoolname.
local tool_paths = { cxx = _OPTIONS["cxx-path"], cc = _OPTIONS["cc-path"], ar = _OPTIONS["ar-path"] }
for _, name in ipairs({ "gcc", "clang" }) do
    premake.override(premake.tools[name], "gettoolname", function(base, cfg, tool)
        return tool_paths[tool] or base(cfg, tool)
    end)
end

-- No binary is stripped, as with premake's Clang toolset and with CMake: premake's GCC toolset
-- strips one whose symbols are "Off" or "Default" (-s, or -Wl,-x on macOS), and a stack trace from
-- a stripped binary names whatever symbol is left nearest to each address, usually the wrong one.
-- The table holds gcc.ldsymbols itself, so overriding that function would change nothing.
premake.tools.gcc.ldflags.symbols.Off = nil
premake.tools.gcc.ldflags.symbols.Default = nil

local function source_dir(name)
    return path.join(forge.root, "forge/source/forge", name)
end

local function component_files(name)
    return {
        path.join(forge.root, "forge/include/forge", name, "**.hpp"),
        path.join(source_dir(name), "**.cpp"),
        path.join(source_dir(name), "**.hpp"),
    }
end

-- A component without .cpp files has nothing to archive; ar and lib.exe reject an
-- empty library, so such components get kind "None" and are never linked.
local function has_sources(name)
    return #os.matchfiles(path.join(source_dir(name), "**.cpp")) > 0
end

-- Returns `names` plus everything they depend on, dependents before dependencies
-- (reverse post-order). GNU ld resolves static archives left to right, so this is
-- the order the link line needs. Premake does not carry static-library links up to
-- the executable, so the closure is computed here.
local function link_order(components, names)
    local order, state, path_stack = {}, {}, {}

    local function visit(name)
        if state[name] == "done" then
            return
        end
        if state[name] == "active" then
            local cycle = {}
            for i = #path_stack, 1, -1 do
                table.insert(cycle, 1, path_stack[i])
                if path_stack[i] == name then
                    break
                end
            end
            table.insert(cycle, name)
            fail("forge: dependency cycle: %s", table.concat(cycle, " -> "))
        end

        state[name] = "active"
        table.insert(path_stack, name)
        for _, dependency in ipairs(components[name].dependencies) do
            visit(dependency)
        end
        table.remove(path_stack)
        state[name] = "done"
        table.insert(order, name)
    end

    for _, name in ipairs(names) do
        visit(name)
    end

    local reversed = {}
    for i = #order, 1, -1 do
        table.insert(reversed, order[i])
    end
    return reversed
end

local dialects = {
    ["c++20"] = "C++20",
    ["c++23"] = "C++23",
}

local sanitizer_names = {
    address = "Address",
    undefined = "UndefinedBehavior",
    thread = "Thread",
}

-- Parses --sanitizers into premake `sanitize` values. memory and leak are not
-- offered: MSan needs an instrumented standard library to avoid false positives, and
-- LeakSanitizer already runs as part of address where the platform supports it.
local function parse_sanitizers()
    local visual_studio = _ACTION ~= nil and _ACTION:match("^vs") ~= nil
    local list = _OPTIONS.sanitizers or (visual_studio and "address" or "address,undefined")

    local result, chosen = {}, {}
    for name in list:gmatch("[^,]+") do
        if not sanitizer_names[name] then
            fail("--sanitizers: unknown sanitizer '%s' (expected address, undefined or thread)", name)
        end
        chosen[name] = true
        table.insert(result, sanitizer_names[name])
    end

    if #result == 0 then
        fail("--sanitizers: the list is empty")
    end
    if chosen.thread and chosen.address then
        fail("--sanitizers: thread cannot be combined with address")
    end
    if visual_studio and (chosen.undefined or chosen.thread) then
        fail("--sanitizers: Visual Studio only supports address")
    end
    return result, chosen
end

-- Parsed on first use and reused by every project.
local parsed_sanitizers = nil

local function sanitizers()
    if not parsed_sanitizers then
        local list, chosen = parse_sanitizers()
        parsed_sanitizers = { list = list, chosen = chosen }
    end
    return parsed_sanitizers
end

-- Standard library hardening rides on forge's assertion switch, as LLVM does: it
-- bounds-checks operator[] and friends for almost no cost and does not change the ABI.
-- MSVC's _ITERATOR_DEBUG_LEVEL is left alone because it does change the ABI.
local function assertions(enabled)
    if enabled then
        defines {
            "FORGE_ASSERTIONS_ENABLED=1",
            "_GLIBCXX_ASSERTIONS",
            "_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE",
        }
    else
        defines { "FORGE_ASSERTIONS_ENABLED=0" }
    end
end

-- Each configuration defines all of these, 1 for itself and 0 for the others, so code
-- tests them with #if like every other forge macro (forge/core/config.hpp checks this).
local configuration_macros = {
    { "Debug", "FORGE_DEBUG" },
    { "Release", "FORGE_RELEASE" },
    { "RelDeb", "FORGE_RELDEB" },
    { "Sanitize", "FORGE_SANITIZE" },
}

local function configuration_defines(configuration)
    local result = {}
    for _, entry in ipairs(configuration_macros) do
        table.insert(result, entry[2] .. "=" .. (entry[1] == configuration and "1" or "0"))
    end
    return result
end

-- What a configuration turns on. forge.baseline() turns it into flags and the lit site configs
-- turn it into features, so a test's REQUIRES cannot disagree with how the code was built.
local function configuration_settings(configuration)
    return {
        assertions = _OPTIONS.assertions ~= nil
            or configuration == "Debug" or configuration == "Sanitize",
        sanitizers = configuration == "Sanitize" and sanitizers().chosen or {},
    }
end

-- Settings every project applies in its own scope, third_party included: anything
-- that must agree across every object file linked together (standard, RTTI,
-- exceptions, configuration, sanitizers, LTO), unwind tables, plus the output layout.
function forge.baseline()
    targetdir "%{wks.location}/%{cfg.buildcfg}/bin"
    objdir "%{wks.location}/%{cfg.buildcfg}/obj/%{prj.name}"

    language "C++"
    cppdialect(dialects[_OPTIONS.std])
    rtti "Off"

    if _OPTIONS.exceptions then
        exceptionhandling "On"
        defines { "FORGE_EXCEPTIONS_ENABLED=1" }
    else
        -- Premake also defines _HAS_EXCEPTIONS=0 for MSVC's standard library.
        exceptionhandling "Off"
        defines { "FORGE_EXCEPTIONS_ENABLED=0" }
    end

    -- Stack traces (docs/stacktrace.md) unwind with these tables, which Clang leaves out on
    -- arm64 macOS when exceptions are off; a trace stops at the first frame without them, so
    -- third_party needs them too. MSVC always has them on x64 and arm64.
    filter "toolset:not msc*"
        buildoptions { "-fasynchronous-unwind-tables" }
    filter {}

    -- One C runtime for the whole program (/MD), as CMake and LLVM default to: with cl.exe's own
    -- default, /MT, a --shared libforge has a CRT of its own, so a FILE* or a heap block from the
    -- program is invalid in it. The release CRT in every configuration, as before; the debug CRT
    -- would also change _ITERATOR_DEBUG_LEVEL.
    staticruntime "Off"
    runtime "Release"

    -- RelDeb is exactly Release plus debug info, unlike CMake's RelWithDebInfo, which
    -- drops to -O2 and so often fails to reproduce what Release does.
    filter "configurations:Debug"
        defines(configuration_defines("Debug"))
        optimize "Off"
        symbols "On"

    -- Release has no debug information but keeps its symbol table; see the end of this file.
    filter "configurations:Release"
        defines(configuration_defines("Release"))
        defines { "NDEBUG" }
        optimize "Speed"
        symbols "Off"

    filter "configurations:RelDeb"
        defines(configuration_defines("RelDeb"))
        defines { "NDEBUG" }
        optimize "Speed"
        symbols "On"

    filter "configurations:Sanitize"
        defines(configuration_defines("Sanitize"))
        optimize "Debug"
        symbols "On"

    filter {}

    for _, entry in ipairs(configuration_macros) do
        filter("configurations:" .. entry[1])
            assertions(configuration_settings(entry[1]).assertions)
    end
    filter {}

    filter "configurations:Sanitize"
        sanitize(sanitizers().list)
    filter { "configurations:Sanitize", "toolset:not msc*" }
        buildoptions { "-fno-omit-frame-pointer", "-fno-sanitize-recover=all" }
        -- The vptr check needs RTTI, which forge never has.
        if sanitizers().chosen.undefined then
            buildoptions { "-fno-sanitize=vptr" }
        end
    filter {}

    if _OPTIONS.lto then
        filter "configurations:Release or RelDeb"
            linktimeoptimization "On"
        filter {}
    end
end

-- The version (docs/version.md). VERSION holds the base version; premake adds the build timestamp
-- and the bug-report URL, and writes all three to <location>/generated/forge/core/version.inc.
-- Only forge/source/forge/core/version.cpp includes it, so a new timestamp recompiles one file.
-- ./x lint checks VERSION with the same rules (utils/xtool/lints.py), before a build needs it.

-- A SemVer numeric identifier: digits, without a leading zero.
local function is_numeric_identifier(text)
    return text:match("^%d+$") ~= nil and (text == "0" or text:sub(1, 1) ~= "0")
end

-- A SemVer base version: X.Y.Z, then optionally "-" and dot-separated pre-release identifiers of
-- letters, digits and "-", the all-digit ones without a leading zero. No build metadata.
local function is_base_version(text)
    local core, prerelease = text, nil
    local dash = text:find("-", 1, true)
    if dash then
        core, prerelease = text:sub(1, dash - 1), text:sub(dash + 1)
    end
    local major, minor, patch = core:match("^(%d+)%.(%d+)%.(%d+)$")
    if not (major and is_numeric_identifier(major) and is_numeric_identifier(minor)
            and is_numeric_identifier(patch)) then
        return false
    end
    if prerelease then
        for identifier in (prerelease .. "."):gmatch("([^.]*)%.") do
            if identifier == "" or identifier:find("[^%w%-]")
                    or (identifier:match("^%d+$") and not is_numeric_identifier(identifier)) then
                return false
            end
        end
    end
    return true
end

local function base_version()
    local file = path.join(forge.root, "VERSION")
    local text = io.readfile(file)
    local line = text and text:match("^([^\n]*)\n$")
    if not line or not is_base_version(line) then
        fail("forge: %s must hold one line with a SemVer base version, such as 0.1.0-dev, and a "
            .. "newline (docs/version.md)", file)
    end
    return line
end

-- UTC, from SOURCE_DATE_EPOCH when it is set, so that a build can be reproduced.
local function build_timestamp()
    local epoch = os.getenv("SOURCE_DATE_EPOCH")
    if epoch then
        if not epoch:match("^%d+$") then
            fail("forge: SOURCE_DATE_EPOCH must be a whole number of seconds, not '%s'", epoch)
        end
        return os.date("!%Y%m%dT%H%M%SZ", tonumber(epoch))
    end
    return os.date("!%Y%m%dT%H%M%SZ")
end

local function bug_report_url()
    local url = _OPTIONS["bug-report-url"] or ""
    if url:find("%c") then
        fail("--bug-report-url: the URL contains a control character")
    end
    return url
end

local function c_string(value)
    return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function version_inc()
    return table.concat({
        "// Generated by premake/forge.lua from VERSION (docs/version.md); regenerate instead of editing.",
        "#define FORGE_DETAIL_VERSION_BASE " .. c_string(base_version()),
        "#define FORGE_DETAIL_VERSION_BUILD " .. c_string(build_timestamp()),
        "#define FORGE_DETAIL_BUG_REPORT_URL " .. c_string(bug_report_url()),
        "",
    }, "\n")
end

-- Settings shared by every forge project (libraries and tests), never third_party.
-- `building_shared` is true only for libforge itself, which exports the FORGE_API symbols
-- that everything else imports.
local function common(building_shared)
    forge.baseline()
    includedirs { path.join(forge.root, "forge/include"), path.join(forge.root, "forge/source") }
    defines {
        "FORGE_SHARED=" .. (_OPTIONS.shared and "1" or "0"),
        "FORGE_BUILDING_SHARED=" .. (building_shared and "1" or "0"),
    }

    warnings "Extra"
    filter "toolset:not msc*"
        buildoptions {
            "-Wpedantic",
            "-Wshadow",
            "-Wconversion",
            "-Wsign-conversion",
            "-Wnon-virtual-dtor",
            "-Woverloaded-virtual",
            "-Wimplicit-fallthrough",
            "-Wold-style-cast",
            "-Wundef",
        }
    -- C4668, MSVC's -Wundef, stays off: the Windows SDK headers trigger it. forge/core/
    -- config.hpp requires the conforming preprocessor. The _CRT_ macros silence C4996 on
    -- std::getenv, std::tmpfile and the like: they are standard, and the _s replacements it asks
    -- for are not portable. LLVM defines the same macros.
    filter "toolset:msc*"
        buildoptions { "/permissive-", "/Zc:preprocessor" }
        defines { "_CRT_SECURE_NO_WARNINGS", "_CRT_NONSTDC_NO_WARNINGS" }
    filter {}

    if _OPTIONS.werror then
        fatalwarnings { "All" }
    end
end

local function index(descriptions)
    if type(descriptions) ~= "table" then
        fail("forge: forge/premake5.lua must return a list of forge.component and forge.test values")
    end

    local components, component_names, tests = {}, {}, {}
    local test_names = {}
    for _, description in ipairs(descriptions) do
        local kind = type(description) == "table" and description.kind or nil
        if kind == "component" then
            if components[description.name] then
                fail("forge: component '%s' is declared twice", description.name)
            end
            components[description.name] = description
            table.insert(component_names, description.name)
        elseif kind == "test" then
            if test_names[description.name] then
                fail("forge: test '%s' is declared twice", description.name)
            end
            test_names[description.name] = true
            table.insert(tests, description)
        else
            fail("forge: forge/premake5.lua returned something that is not a forge.component or forge.test")
        end
    end

    local function check(description)
        for _, dependency in ipairs(description.dependencies) do
            if not components[dependency] then
                fail("forge: %s '%s' depends on '%s', which is not a declared component",
                    description.kind, description.name, dependency)
            end
        end
    end
    for _, name in ipairs(component_names) do
        check(components[name])
    end
    for _, test in ipairs(tests) do
        check(test)
    end

    -- Check the whole graph for cycles even in --shared mode, so going back to static
    -- libraries never turns up a cycle that the single shared library was hiding.
    link_order(components, component_names)

    return components, component_names, tests
end

-- For the projects that link a binary. On macOS the debug information stays in the object files,
-- where llvm-symbolizer does not look: it reads a .dSYM bundle next to the binary, which dsymutil
-- makes in every configuration that has debug information.
local function debug_information_bundle()
    filter { "system:macosx", "configurations:not Release" }
        postbuildcommands { "dsymutil %{cfg.buildtarget.abspath}" }
    filter {}
end

-- <location>/generated holds what premake writes for core (version.inc). Only core gets it as an
-- include directory, so nothing else can come to depend on generated code.
local function generated_includes(name)
    if name == "core" then
        includedirs { "%{wks.location}/generated" }
    end
end

local function emit_static(component_names)
    local linkable = {}
    for _, name in ipairs(component_names) do
        local sources = has_sources(name)
        linkable[name] = sources

        project("forge_" .. name)
            kind(sources and "StaticLib" or "None")
            files(component_files(name))
            common()
            generated_includes(name)
    end
    return linkable
end

local function emit_shared(component_names)
    local sources = false
    project "forge"
        for _, name in ipairs(component_names) do
            files(component_files(name))
            sources = sources or has_sources(name)
            generated_includes(name)
        end
        kind(sources and "SharedLib" or "None")
        common(true)
        debug_information_bundle()
        visibility "Hidden"
        inlinesvisibility "Hidden"
    return sources
end

local function emit_test(test, libraries, third_party)
    group "unittests"
    project("forge_" .. test.name .. "_unittests")
        kind "ConsoleApp"
        files {
            path.join(forge.root, "forge/unittests", test.name, "**.cpp"),
            path.join(forge.root, "forge/unittests", test.name, "**.hpp"),
        }
        common()
        externalincludedirs(third_party.googletest.includedirs)
        links(libraries)
        links(third_party.googletest.links)

        -- main is gtest_main's, in googletest's library. Without /SUBSYSTEM, which premake's msc
        -- toolset leaves out for a ConsoleApp, MSVC's linker looks for main only in the objects to
        -- pick the entry point, and fails with LNK1561.
        filter "toolset:msc*"
            linkoptions { "/SUBSYSTEM:CONSOLE" }
        filter "system:linux"
            links { "pthread" }
        filter {}
        debug_information_bundle()
    group ""
end

-- Never built. The lit host tests (forge/test/host) compile forge's headers with this project's
-- flags, which are exactly what code outside libforge gets, in static and --shared builds alike.
local function emit_host_tests()
    group "test"
    project "forge_host_tests"
        kind "None"
        common()
    group ""
end

-- lit site configs. Once the action has written the projects, every configuration gets
-- <location>/<configuration>/test/lit.site.cfg.py, and unittests/lit.site.cfg.py when the unit
-- tests are built. Each records that configuration's paths, features and host compiler, then loads
-- the lit.cfg.py of the source tree.

-- Whether forge.emit created unit-test projects; read after the action.
local emitted_unittests = false

local sanitizer_features = { address = "asan", undefined = "ubsan", thread = "tsan" }

-- lit features describing how a configuration is built; forge/test/lit.cfg.py adds the ones that
-- describe the host.
local function features(configuration)
    local settings = configuration_settings(configuration)
    local result = { configuration:lower(), "host-std-" .. _OPTIONS.std }
    if settings.assertions then
        table.insert(result, "asserts")
    end
    if _OPTIONS.exceptions then
        table.insert(result, "exceptions")
    end
    if _OPTIONS.shared then
        table.insert(result, "shared")
    end
    for _, name in ipairs({ "address", "undefined", "thread" }) do
        if settings.sanitizers[name] then
            table.insert(result, sanitizer_features[name])
        end
    end
    return result
end

-- The command line that compiles a file with `cfg`'s flags, as an argument list, and the host
-- compiler family. The exporters quote defines and make paths relative to the build directory; lit
-- passes each argument as it is and runs each test in its own directory, so neither is done here.
local function host_compiler(cfg)
    local toolset = premake.tools.canonical(cfg.toolset or premake.action.current().toolset)
    local msc = toolset == premake.tools.msc
    local family = msc and "msvc" or (toolset == premake.tools.clang and "clang" or "gcc")

    local argv = { toolset.gettoolname(cfg, "cxx") }
    for _, flag in ipairs(toolset.getcxxflags(cfg)) do
        table.insert(argv, flag)
    end
    for _, define in ipairs(cfg.defines) do
        table.insert(argv, (msc and "/D" or "-D") .. define)
    end
    for _, dir in ipairs(cfg.includedirs) do
        table.insert(argv, (msc and "/I" or "-I") .. dir)
    end
    for _, option in ipairs(cfg.buildoptions) do
        table.insert(argv, option)
    end
    return argv, family
end

-- Escapes backslashes too, for Windows paths.
local function python_string(value)
    return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function python_list(values)
    local quoted = {}
    for _, value in ipairs(values) do
        table.insert(quoted, python_string(value))
    end
    return "[" .. table.concat(quoted, ", ") .. "]"
end

-- Appends to `site_configs` the site configs of one configuration, given as forge_host_tests in
-- that configuration.
local function add_configuration_site_configs(site_configs, wks, cfg)
    local function add(dir, lines)
        table.insert(site_configs, { dir = dir, text = table.concat(lines, "\n") .. "\n" })
    end

    local configuration = cfg.buildcfg
    -- The layout forge.baseline() gives every configuration's output.
    local base = path.join(wks.location, configuration)
    local header = string.format(
        "# Generated by premake/forge.lua for the %s configuration; regenerate instead of editing.",
        configuration)
    local argv, family = host_compiler(cfg)

    add(path.join(base, "test"), {
        header,
        "config.test_exec_root = " .. python_string(path.join(base, "test")),
        "config.forge_source_root = " .. python_string(forge.root),
        "config.forge_bin_dir = " .. python_string(cfg.targetdir),
        "config.forge_configuration = " .. python_string(configuration),
        "config.forge_features = " .. python_list(features(configuration)),
        "config.forge_host_cxx = " .. python_list(argv),
        "config.forge_host_cxx_family = " .. python_string(family),
        "config.forge_premake = " .. python_string(_PREMAKE_COMMAND),
        "lit_config.load_config(config, "
            .. python_string(path.join(forge.root, "forge/test/lit.cfg.py")) .. ")",
    })

    if emitted_unittests then
        add(path.join(base, "unittests"), {
            header,
            "config.forge_source_root = " .. python_string(forge.root),
            "config.forge_bin_dir = " .. python_string(cfg.targetdir),
            "config.forge_features = " .. python_list(features(configuration)),
            "lit_config.load_config(config, "
                .. python_string(path.join(forge.root, "forge/unittests/lit.cfg.py")) .. ")",
        })
    end
end

local function site_configs()
    local result = {}
    for wks in premake.global.eachWorkspace() do
        local host_tests = premake.workspace.findproject(wks, "forge_host_tests")
        if host_tests then
            for cfg in premake.project.eachconfig(host_tests) do
                add_configuration_site_configs(result, wks, cfg)
            end
        end
    end
    return result
end

-- What premake writes besides the action's own files, as { dir, name, text }: every
-- configuration's lit site configs, and version.inc.
local function generated_files()
    local result = {}
    for _, site_config in ipairs(site_configs()) do
        table.insert(result, { dir = site_config.dir, name = "lit.site.cfg.py", text = site_config.text })
    end
    local text = version_inc()
    for wks in premake.global.eachWorkspace() do
        table.insert(result, { dir = path.join(wks.location, "generated/forge/core"), name = "version.inc",
                               text = text })
    end
    return result
end

-- premake.action.call runs the action, after every project is baked. The generated files are
-- worked out before it runs, because the ninja action deletes "None" projects such as
-- forge_host_tests from the workspace, and so that an invalid VERSION stops premake before it
-- writes anything; they are written after it succeeds. clean and forge-describe get none. An
-- unchanged file is left alone, so that lit, editors and ninja do not see it as new.
premake.override(premake.action, "call", function(base, name)
    local pending = (name ~= "clean" and name ~= "forge-describe") and generated_files() or {}
    base(name)
    for _, generated in ipairs(pending) do
        os.mkdir(generated.dir)
        local file = path.join(generated.dir, generated.name)
        if os.writefile_ifnotequal(generated.text, file) < 0 then
            fail("forge: cannot write %s", file)
        end
    end
end)

-- What forge.emit was given, for forge-describe.
local described = nil

-- `premake5 --no-tests forge-describe` prints one line of JSON: the configurations, the Forge
-- options and the component graph. ./x builds its command line and its layering lint from it, so
-- that neither repeats what premake/options.lua and forge/premake5.lua say.
newaction {
    trigger = "forge-describe",
    description = "Print forge's configurations, options and components as JSON (for ./x)",
    execute = function()
        -- wks.configurations also maps each name to itself; only the list goes out.
        local configurations = {}
        for wks in premake.global.eachWorkspace() do
            for _, name in ipairs(wks.configurations) do
                table.insert(configurations, name)
            end
            break
        end

        local options = {}
        for trigger, option in pairs(premake.option.list) do
            if option.category == "Forge" then
                local allowed = {}
                for _, entry in ipairs(option.allowed or {}) do
                    table.insert(allowed, entry[1])
                end
                table.insert(options, {
                    trigger = trigger,
                    value = option.value,
                    description = option.description,
                    default = option.default,
                    allowed = allowed,
                })
            end
        end
        table.sort(options, function(a, b) return a.trigger < b.trigger end)

        local components, tests = {}, {}
        if described then
            for _, name in ipairs(described.component_names) do
                table.insert(components, {
                    name = name,
                    dependencies = described.components[name].dependencies,
                })
            end
            for _, test in ipairs(described.tests) do
                table.insert(tests, { name = test.name, dependencies = test.dependencies })
            end
        end

        print(json.encode({
            configurations = configurations,
            options = options,
            components = components,
            tests = tests,
        }))
    end,
}

-- `third_party` is the table returned by third_party/premake5.lua, or nil with --no-tests.
function forge.emit(descriptions, third_party)
    local components, component_names, tests = index(descriptions)
    described = { components = components, component_names = component_names, tests = tests }
    emitted_unittests = third_party ~= nil and #tests > 0

    emit_host_tests()

    if _OPTIONS.shared then
        local linkable = emit_shared(component_names)
        if third_party then
            for _, test in ipairs(tests) do
                emit_test(test, linkable and { "forge" } or {}, third_party)
            end
        end
    else
        local linkable = emit_static(component_names)
        if third_party then
            for _, test in ipairs(tests) do
                local libraries = {}
                for _, name in ipairs(link_order(components, test.dependencies)) do
                    if linkable[name] then
                        table.insert(libraries, "forge_" .. name)
                    end
                end
                emit_test(test, libraries, third_party)
            end
        end
    end
end

return forge
