-- SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

-- Command-line options for the forge build. premake5.lua applies them; options are
-- read at generation time, so regenerate after changing one.

-- Premake 5.0 no longer has a built-in --to. A separate directory per option set keeps
-- builds apart (e.g. build/ and build-shared/), since options are fixed at generation.
newoption {
    trigger         = "to",
    value           = "DIR",
    description     = "Directory for generated project files and build output (default: build)",
    category        = "Forge"
}

newoption {
    trigger         = "std",
    value           = "STD",
    description     = "The C++ standard version to use",
    category        = "Forge",
    default         = "c++20",
    allowed         = {
        { "c++20", "ISO C++20 (default)" },
        { "c++23", "ISO C++23" }
    }
}

newoption {
    trigger         = "assertions",
    description     = "Enable FORGE_ASSERTIONS_ENABLED in every configuration (default: Debug and Sanitize only)",
    category        = "Forge"
}

newoption {
    trigger         = "exceptions",
    description     = "Compile with C++ exceptions enabled",
    category        = "Forge"
}

newoption {
    trigger         = "shared",
    description     = "Build forge as one shared library (libforge) instead of one static library per component",
    category        = "Forge"
}

newoption {
    trigger         = "sanitizers",
    value           = "LIST",
    description     = "Comma-separated sanitizers for the Sanitize configuration: address, undefined, thread (default: address,undefined; address on Visual Studio)",
    category        = "Forge"
}

newoption {
    trigger         = "werror",
    description     = "Treat compiler warnings in forge projects as errors (third_party is never affected)",
    category        = "Forge"
}

newoption {
    trigger         = "lto",
    description     = "Enable link-time optimization in Release and RelDeb",
    category        = "Forge"
}

newoption {
    trigger         = "no-tests",
    description     = "Skip the unit tests and googletest",
    category        = "Forge"
}

-- Exact tool binaries, for choosing one compiler among several installed versions: ./x build --cxx
-- derives all three from the C++ compiler. They replace the tool names of the gcc and clang
-- toolsets. A category of their own keeps them out of the options ./x mirrors as build options.
newoption {
    trigger         = "cxx-path",
    value           = "PATH",
    description     = "C++ compiler (and linker) to run instead of the toolset's g++ or clang++",
    category        = "Forge toolchain"
}

newoption {
    trigger         = "cc-path",
    value           = "PATH",
    description     = "C compiler to run instead of the toolset's gcc or clang",
    category        = "Forge toolchain"
}

newoption {
    trigger         = "ar-path",
    value           = "PATH",
    description     = "Archiver to run instead of the toolset's ar (gcc-ar with --lto on gcc)",
    category        = "Forge toolchain"
}

-- docs/version.md. A category of its own, so ./x does not mirror it: it is a packager's setting
-- rather than a build variant, and a URL would make a poor build-directory name. Packagers pass
-- it to premake directly, as LLVM's take BUG_REPORT_URL.
newoption {
    trigger         = "bug-report-url",
    value           = "URL",
    description     = "Where failure reports ask users to report bugs (default: none)",
    category        = "Forge packaging"
}
