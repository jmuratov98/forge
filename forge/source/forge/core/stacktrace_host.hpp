// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include "forge/core/config.hpp"

#include <chrono>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>

// What posix_stacktrace.cpp and windows_stacktrace.cpp provide to stacktrace.cpp, which holds what
// every host shares: the search for the symbolizer, reading its responses, and the output format
// (docs/stacktrace.md).

namespace forge::stacktrace::host {

// The module that contains the call-site address `address` ([stacktrace.module]): writes its path
// into `path`, null-terminated and cut off if it does not fit, and returns the module-relative
// address. nullopt when no module contains `address`. Allocates nothing.
std::optional<std::uintptr_t> resolve_module(std::uintptr_t address, std::span<char> path) noexcept;

// An environment variable's value in UTF-8, or nullopt when it is not set.
std::optional<std::string> environment_variable(const char* name);

// The path of the main executable, or empty if the host cannot tell.
std::string executable_path();

// Whether `path` names a file the symbolizer could be run from.
bool is_program(const std::string& path);

inline constexpr char g_path_list_separator = FORGE_HOST_WINDOWS ? ';' : ':';
inline constexpr char g_directory_separator = FORGE_HOST_WINDOWS ? '\\' : '/';
// The characters that end a directory in a path: Windows takes either slash.
inline constexpr std::string_view g_directory_separators = FORGE_HOST_WINDOWS ? "\\/" : "/";
inline constexpr std::string_view g_symbolizer_name =
    FORGE_HOST_WINDOWS ? "llvm-symbolizer.exe" : "llvm-symbolizer";

struct symbolizer_output {
    std::string text;
    // The child was created and exited successfully before the timeout.
    bool succeeded = false;
};

// [stacktrace.symbolize] paragraphs 3, 6 and 8: runs `program` with the symbolizer's arguments,
// writes `input` to its standard input and closes it, and collects its standard output until it
// exits. A child still running `timeout` after its creation is terminated. Whatever happens, the
// child has terminated and its resources are released when this returns.
symbolizer_output run_symbolizer(const std::string& program,
                                 std::string_view input,
                                 std::chrono::steady_clock::duration timeout);

} // namespace forge::stacktrace::host
