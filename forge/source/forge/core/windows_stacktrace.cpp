// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/config.hpp"

#include <cstdint>

#if FORGE_HOST_WINDOWS

#  include "forge/core/stacktrace.hpp"
#  include "forge/core/stacktrace_host.hpp"

#  include <algorithm>
#  include <array>
#  include <chrono>
#  include <cstddef>
#  include <limits>
#  include <optional>
#  include <span>
#  include <string>
#  include <string_view>

// windows.h's min and max macros would break std::min; the rest of it is not needed.
#  ifndef NOMINMAX
#    define NOMINMAX // NOLINT(readability-identifier-naming)
#  endif
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN // NOLINT(readability-identifier-naming)
#  endif
#  include <windows.h>

namespace forge::stacktrace {

std::size_t capture(std::span<std::uintptr_t> frames, std::size_t skip) noexcept {
    // RtlCaptureStackBackTrace counts its caller, this function, as frame 0, and fills an array of
    // pointers, so it captures a chunk at a time into one and copies. Each call walks from the top
    // again; traces are short enough for that not to matter.
    constexpr std::size_t max_skip = std::numeric_limits<ULONG>::max();
    std::array<PVOID, 64> chunk{};
    std::size_t captured = 0;
    while (captured < frames.size() && skip < max_skip - 1 - captured) {
        const auto wanted = static_cast<ULONG>(std::min(chunk.size(), frames.size() - captured));
        const USHORT got = RtlCaptureStackBackTrace(
            static_cast<ULONG>(skip + 1 + captured), wanted, chunk.data(), nullptr);
        for (std::size_t i = 0; i < got; ++i) {
            frames[captured + i] = reinterpret_cast<std::uintptr_t>(chunk[i]);
        }
        captured += got;
        if (got < wanted) {
            break;
        }
    }
    return captured;
}

namespace host {
namespace {

// Closes a handle when it goes out of scope.
class handle {
public:
    explicit handle(HANDLE value = nullptr) noexcept : m_value(value) {}
    handle(const handle&) = delete;
    handle& operator=(const handle&) = delete;
    handle(handle&&) = delete;
    handle& operator=(handle&&) = delete;
    ~handle() { reset(); }

    [[nodiscard]] HANDLE get() const noexcept { return m_value; }
    HANDLE* out() noexcept { return &m_value; }

    void reset() noexcept {
        if (m_value != nullptr && m_value != INVALID_HANDLE_VALUE) {
            CloseHandle(m_value);
        }
        m_value = nullptr;
    }

private:
    HANDLE m_value;
};

std::wstring widen(std::string_view text) {
    if (text.empty()) {
        return {};
    }
    const int size =
        MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    std::wstring result(static_cast<std::size_t>(size), L'\0');
    MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), result.data(), size);
    return result;
}

std::string narrow(std::wstring_view text) {
    if (text.empty()) {
        return {};
    }
    const int size = WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string result(static_cast<std::size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8,
                        0,
                        text.data(),
                        static_cast<int>(text.size()),
                        result.data(),
                        size,
                        nullptr,
                        nullptr);
    return result;
}

// A module's path in UTF-8 into `out`, null-terminated; empty when it does not fit.
void module_path_into(HMODULE module, std::span<char> out) noexcept {
    out[0] = '\0';
    std::array<wchar_t, 4096> wide{};
    const DWORD size = GetModuleFileNameW(module, wide.data(), static_cast<DWORD>(wide.size()));
    if (size == 0 || size >= wide.size()) {
        return;
    }
    const int written = WideCharToMultiByte(CP_UTF8,
                                            0,
                                            wide.data(),
                                            static_cast<int>(size),
                                            out.data(),
                                            static_cast<int>(out.size() - 1),
                                            nullptr,
                                            nullptr);
    out[static_cast<std::size_t>(std::max(written, 0))] = '\0';
}

} // namespace

std::optional<std::uintptr_t> resolve_module(std::uintptr_t address,
                                             std::span<char> path) noexcept {
    if (path.empty()) {
        return std::nullopt;
    }
    path[0] = '\0';
    HMODULE module = nullptr;
    if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                               GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(address),
                           &module) == 0) {
        return std::nullopt;
    }
    module_path_into(module, path);
    // llvm-symbolizer takes it with --relative-address, as an offset from the image base.
    return address - reinterpret_cast<std::uintptr_t>(module);
}

std::optional<std::string> environment_variable(const char* name) {
    const std::wstring wide_name = widen(name);
    const DWORD size = GetEnvironmentVariableW(wide_name.c_str(), nullptr, 0);
    if (size == 0) {
        return std::nullopt;
    }
    std::wstring value(size, L'\0');
    const DWORD length = GetEnvironmentVariableW(wide_name.c_str(), value.data(), size);
    value.resize(std::min<std::size_t>(length, value.size()));
    return narrow(value);
}

std::string executable_path() {
    std::array<char, 4096> path{};
    module_path_into(nullptr, path);
    return path.data();
}

bool is_program(const std::string& path) {
    const DWORD attributes = GetFileAttributesW(widen(path).c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

symbolizer_output run_symbolizer(const std::string& program,
                                 std::string_view input,
                                 std::chrono::steady_clock::duration timeout) {
    symbolizer_output result;

    // Windows cannot wait on an anonymous pipe, so each pipe gets a buffer meant to hold every
    // request and every response: this process writes all of its input before it reads, and the
    // child can exit without waiting for this process to read.
    constexpr DWORD pipe_size = 1 << 20;
    SECURITY_ATTRIBUTES inheritable{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    handle input_read;
    handle input_write;
    handle output_read;
    handle output_write;
    if (CreatePipe(input_read.out(), input_write.out(), &inheritable, pipe_size) == 0 ||
        CreatePipe(output_read.out(), output_write.out(), &inheritable, pipe_size) == 0) {
        return result;
    }
    // Only the child's ends are inherited.
    SetHandleInformation(input_write.get(), HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(output_read.get(), HANDLE_FLAG_INHERIT, 0);
    handle null_device(CreateFileW(L"NUL",
                                   GENERIC_WRITE,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE,
                                   &inheritable,
                                   OPEN_EXISTING,
                                   0,
                                   nullptr));

    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input_read.get();
    startup.hStdOutput = output_write.get();
    startup.hStdError = null_device.get();

    const std::wstring application = widen(program);
    std::wstring command_line =
        L"\"" + application + L"\" --functions=linkage --inlining --demangle --relative-address";
    PROCESS_INFORMATION process{};
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    const BOOL created = CreateProcessW(application.c_str(),
                                        command_line.data(),
                                        nullptr,
                                        nullptr,
                                        TRUE,
                                        CREATE_NO_WINDOW,
                                        nullptr,
                                        nullptr,
                                        &startup,
                                        &process);
    input_read.reset();
    output_write.reset();
    null_device.reset();
    if (created == 0) {
        return result;
    }
    const handle thread(process.hThread);
    const handle child(process.hProcess);

    DWORD written = 0;
    WriteFile(input_write.get(), input.data(), static_cast<DWORD>(input.size()), &written, nullptr);
    input_write.reset();

    const auto remaining =
        std::chrono::ceil<std::chrono::milliseconds>(deadline - std::chrono::steady_clock::now());
    const auto wait =
        static_cast<DWORD>(std::clamp<std::int64_t>(remaining.count(), 0, INFINITE - 1));
    const bool exited = WaitForSingleObject(child.get(), wait) == WAIT_OBJECT_0;
    if (!exited) {
        TerminateProcess(child.get(), 1);
        WaitForSingleObject(child.get(), INFINITE);
    }
    DWORD exit_code = 1;
    GetExitCodeProcess(child.get(), &exit_code);

    // The child has exited and this process holds no write end, so reading ends at what is left.
    std::array<char, 4096> buffer{};
    DWORD size = 0;
    while (
        ReadFile(
            output_read.get(), buffer.data(), static_cast<DWORD>(buffer.size()), &size, nullptr) !=
            0 &&
        size > 0) {
        result.text.append(buffer.data(), size);
    }
    result.succeeded = exited && exit_code == 0;
    return result;
}

} // namespace host
} // namespace forge::stacktrace

#endif
