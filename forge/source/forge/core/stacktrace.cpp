// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/stacktrace.hpp"

#include "forge/core/stacktrace_host.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <format>
#include <iterator>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

// print() for every host (docs/stacktrace.md): capture and module resolution are in
// posix_stacktrace.cpp and windows_stacktrace.cpp. Symbol information comes only from
// llvm-symbolizer, run as a child process, never from dladdr or DbgHelp: dladdr names the nearest
// exported symbol, which for forge's hidden and internal functions is usually another function.

namespace forge::stacktrace {
namespace {

constexpr std::chrono::seconds g_symbolizer_timeout{10};

// One invocation that the symbolizer reports at a frame's address; empty or 0 where unknown.
struct entry {
    std::string function;
    std::string file;
    unsigned line = 0;
    unsigned column = 0;
};

struct frame {
    bool resolved = false;
    std::string module_path;
    // Module-relative when resolved, else the call-site address itself.
    std::uintptr_t address = 0;
    // Innermost first. Empty when the frame has no complete response.
    std::vector<entry> entries;
};

enum class symbolization : std::uint8_t { done, disabled, unavailable, failed };

std::vector<frame> resolve(std::span<const std::uintptr_t> return_addresses) {
    std::vector<frame> frames(return_addresses.size());
    std::array<char, 4096> path{};
    for (std::size_t i = 0; i < return_addresses.size(); ++i) {
        // The call-site address lies within the call instruction, so it maps to the line of the
        // call rather than to whatever follows it.
        const std::uintptr_t address = return_addresses[i] - 1;
        if (const std::optional<std::uintptr_t> relative = host::resolve_module(address, path)) {
            frames[i].resolved = true;
            frames[i].module_path = path.data();
            frames[i].address = *relative;
        } else {
            frames[i].address = address;
        }
    }
    return frames;
}

// [stacktrace.symbolize] paragraph 2.
std::string find_symbolizer() {
    const std::optional<std::string> configured =
        host::environment_variable("FORGE_SYMBOLIZER_PATH");
    if (configured && !configured->empty() && host::is_program(*configured)) {
        return *configured;
    }

    if (const std::string executable = host::executable_path(); !executable.empty()) {
        std::string candidate =
            executable.substr(0, executable.find_last_of(host::g_directory_separators) + 1);
        candidate += host::g_symbolizer_name;
        if (host::is_program(candidate)) {
            return candidate;
        }
    }

    const std::optional<std::string> path = host::environment_variable("PATH");
    std::string_view rest = path ? std::string_view(*path) : std::string_view();
    while (!rest.empty()) {
        const std::size_t end = std::min(rest.find(host::g_path_list_separator), rest.size());
        std::string_view directory = rest.substr(0, end);
        rest.remove_prefix(std::min(end + 1, rest.size()));
        // Windows allows quotes around an element; POSIX reads an empty one as the current
        // directory.
        if (directory.size() >= 2 && directory.front() == '"' && directory.back() == '"') {
            directory = directory.substr(1, directory.size() - 2);
        }
        std::string candidate(directory.empty() ? "." : directory);
        candidate += host::g_directory_separator;
        candidate += host::g_symbolizer_name;
        if (host::is_program(candidate)) {
            return candidate;
        }
    }
    return {};
}

// The lines of the symbolizer's output, without their line terminators. A last line without a
// newline is incomplete, since the child may have been stopped in the middle of it.
class line_reader {
public:
    explicit line_reader(std::string_view text) : m_rest(text) {}

    std::optional<std::string_view> next() {
        const std::size_t end = m_rest.find('\n');
        if (end == std::string_view::npos) {
            return std::nullopt;
        }
        std::string_view line = m_rest.substr(0, end);
        m_rest.remove_prefix(end + 1);
        if (line.ends_with('\r')) {
            line.remove_suffix(1);
        }
        return line;
    }

private:
    std::string_view m_rest;
};

bool parse_number(std::string_view text, unsigned& value) {
    const char* begin = std::to_address(text.begin());
    const char* end = std::to_address(text.end());
    const auto [stop, error] = std::from_chars(begin, end, value);
    return !text.empty() && error == std::errc() && stop == end;
}

// An entry from its function line and its location line, file:line:column. The location is split
// from the right: a Windows file name has a colon of its own.
std::optional<entry> parse_entry(std::string_view function, std::string_view location) {
    const std::size_t column_colon = location.rfind(':');
    if (column_colon == std::string_view::npos || column_colon == 0) {
        return std::nullopt;
    }
    const std::size_t line_colon = location.rfind(':', column_colon - 1);
    if (line_colon == std::string_view::npos) {
        return std::nullopt;
    }
    entry result;
    if (!parse_number(location.substr(line_colon + 1, column_colon - line_colon - 1),
                      result.line) ||
        !parse_number(location.substr(column_colon + 1), result.column)) {
        return std::nullopt;
    }
    if (function != "??") {
        result.function = function;
    }
    if (const std::string_view file = location.substr(0, line_colon); file != "??") {
        result.file = file;
    }
    return result;
}

// Whether a function line names a function in forge::detail, possibly after a return type
// ("void forge::detail::f<int>(...)") or, on Windows, a calling convention.
bool in_forge_detail(std::string_view function) {
    const std::size_t at = function.find("forge::detail::");
    return at != std::string_view::npos && at < function.find('(') &&
           (at == 0 || function[at - 1] == ' ');
}

// A failed check goes through helpers in forge::detail that are always inlined into the function
// with the check, so where there is debug information the symbolizer reports them as the
// innermost entries of frame 0, and the function the reader is looking for as #0.1. GCC has no
// attribute that keeps an inlined function out of the debug information, so they are dropped
// here, from the front, as long as one entry is left: a frame in a forge::detail function that is
// not inlined anywhere keeps its name.
void drop_detail_entries(std::vector<entry>& entries) {
    const auto first_kept =
        std::find_if_not(entries.begin(), std::prev(entries.end()), [](const entry& e) {
            return in_forge_detail(e.function);
        });
    entries.erase(entries.begin(), first_kept);
}

// Reads the responses to the frames in `requested`, in order ([stacktrace.symbolize] paragraph 5),
// up to the first that is incomplete or does not match, and returns how many it read.
std::size_t read_responses(std::string_view output,
                           std::span<const std::size_t> requested,
                           std::vector<frame>& frames) {
    line_reader lines(output);
    std::size_t read = 0;
    for (const std::size_t index : requested) {
        std::vector<entry> entries;
        while (true) {
            const std::optional<std::string_view> function = lines.next();
            if (!function) {
                return read;
            }
            if (function->empty()) {
                break;
            }
            const std::optional<std::string_view> location = lines.next();
            std::optional<entry> parsed =
                location ? parse_entry(*function, *location) : std::nullopt;
            if (!parsed) {
                return read;
            }
            entries.push_back(std::move(*parsed));
        }
        if (entries.empty()) {
            return read;
        }
        drop_detail_entries(entries);
        frames[index].entries = std::move(entries);
        ++read;
    }
    return read;
}

// A path that cannot go between the quotes of a request line gets no request.
bool can_request(const std::string& path) {
    return path.find_first_of("\"\n\r") == std::string::npos;
}

symbolization symbolize(std::vector<frame>& frames) {
    if (host::environment_variable("FORGE_DISABLE_SYMBOLIZATION") == "1") {
        return symbolization::disabled;
    }
    const std::string program = find_symbolizer();
    if (program.empty()) {
        return symbolization::unavailable;
    }

    std::string input;
    std::vector<std::size_t> requested;
    for (std::size_t i = 0; i < frames.size(); ++i) {
        if (frames[i].resolved && can_request(frames[i].module_path)) {
            std::format_to(std::back_inserter(input),
                           "CODE \"{}\" 0x{:x}\n",
                           frames[i].module_path,
                           frames[i].address);
            requested.push_back(i);
        }
    }
    if (requested.empty()) {
        return symbolization::done;
    }

    const host::symbolizer_output output =
        host::run_symbolizer(program, input, g_symbolizer_timeout);
    // Responses read completely before a failure are used all the same.
    const std::size_t read = read_responses(output.text, requested, frames);
    return output.succeeded && read == requested.size() ? symbolization::done
                                                        : symbolization::failed;
}

void write_line(std::FILE* file, std::string_view text) {
    std::fwrite(text.data(), 1, text.size(), file);
    std::fputc('\n', file);
}

// [stacktrace.format] paragraph 2, for entry `k` of frame `index`; `e` is null for a frame without
// a response.
std::string frame_line(std::size_t index, std::size_t k, const frame& f, const entry* e) {
    std::string line = std::format("    #{}", index);
    const auto out = std::back_inserter(line);
    if (k > 0) {
        std::format_to(out, ".{}", k);
    }
    if (f.resolved) {
        const std::string_view path = f.module_path;
        const std::string_view name =
            path.substr(path.find_last_of(host::g_directory_separators) + 1);
        std::format_to(out, " {}+0x{:x}", name, f.address);
    } else {
        std::format_to(out, " 0x{:x}", f.address);
    }
    if (e == nullptr) {
        return line;
    }
    if (!e->function.empty()) {
        std::format_to(out, " {}", e->function);
    }
    if (!e->file.empty()) {
        std::format_to(out, " {}", e->file);
        if (e->line != 0) {
            std::format_to(out, ":{}", e->line);
            if (e->column != 0) {
                std::format_to(out, ":{}", e->column);
            }
        }
    }
    return line;
}

} // namespace

void print(std::FILE* file, std::span<const std::uintptr_t> frames, bool truncated) noexcept {
    std::vector<frame> resolved = resolve(frames);
    const symbolization result = symbolize(resolved);

    write_line(file, "  stack trace:");
    for (std::size_t i = 0; i < resolved.size(); ++i) {
        const frame& f = resolved[i];
        if (f.entries.empty()) {
            write_line(file, frame_line(i, 0, f, nullptr));
        }
        for (std::size_t k = 0; k < f.entries.size(); ++k) {
            write_line(file, frame_line(i, k, f, &f.entries[k]));
        }
    }
    if (truncated) {
        write_line(file, "    (more frames not shown)");
    }
    if (result == symbolization::unavailable) {
        write_line(file,
                   "  note: no llvm-symbolizer found; set FORGE_SYMBOLIZER_PATH to show "
                   "function names and lines");
    } else if (result == symbolization::failed) {
        write_line(file, "  note: llvm-symbolizer failed; frames are shown without names");
    }
    std::fflush(file);
}

} // namespace forge::stacktrace
