// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "forge/core/config.hpp"

#include <cstdint>

#if FORGE_HOST_POSIX

#  include "forge/core/stacktrace.hpp"
#  include "forge/core/stacktrace_host.hpp"

#  include <algorithm>
#  include <array>
#  include <cerrno>
#  include <chrono>
#  include <climits>
#  include <csignal>
#  include <cstddef>
#  include <cstdlib>
#  include <limits>
#  include <optional>
#  include <span>
#  include <string>
#  include <string_view>
#  include <thread>

#  include <fcntl.h>
#  include <poll.h>
#  include <spawn.h>
#  include <sys/socket.h>
#  include <sys/stat.h>
#  include <sys/wait.h>
#  include <unistd.h>
#  include <unwind.h>

#  if FORGE_HOST_LINUX
#    include <link.h>
#  elif FORGE_HOST_MACOS
#    include <mach-o/dyld.h>
#    include <mach-o/loader.h>

#    include <crt_externs.h>
#    include <dlfcn.h>
#    include <libproc.h>
#  endif

namespace forge::stacktrace {

namespace {

struct capture_state {
    std::uintptr_t* buffer;
    std::size_t remaining;
    std::size_t skip;
};

_Unwind_Reason_Code unwind_cb(_Unwind_Context* ctxt, void* arg) noexcept {
    auto& state = *static_cast<capture_state*>(arg);

    const std::uintptr_t ip{_Unwind_GetIP(ctxt)};

    if (ip == 0) {
        return _URC_END_OF_STACK;
    }

    if (state.skip != 0) {
        --state.skip;
        return _URC_NO_REASON;
    }

    if (state.remaining == 0) {
        return _URC_END_OF_STACK;
    }

    *state.buffer++ = ip;
    --state.remaining;
    return _URC_NO_REASON;
}

} // namespace

std::size_t capture(std::span<std::uintptr_t> frames, std::size_t skip) noexcept {
    if (frames.empty()) [[unlikely]] {
        return 0;
    }

    capture_state state{};
    state.buffer = frames.data();
    state.remaining = frames.size();
    // _Unwind_Backtrace starts at its caller, so the first frame it reports is this function's
    // own, which is not part of the trace. Saturating, so that a huge skip still skips everything.
    state.skip = skip == std::numeric_limits<std::size_t>::max() ? skip : skip + 1;

    _Unwind_Backtrace(&unwind_cb, &state);
    return frames.size() - state.remaining;
}

namespace host {
namespace {

// Copies `text` into `out`, null-terminated, cutting it off if it does not fit.
void copy_path(std::string_view text, std::span<char> out) noexcept {
    if (out.empty()) {
        return;
    }
    const std::size_t size = std::min(text.size(), out.size() - 1);
    std::copy_n(text.begin(), size, out.begin());
    out[size] = '\0';
}

// The main executable's path into `out`, or an empty string if the host cannot tell.
void executable_path_into(std::span<char> out) noexcept {
    copy_path("", out);
#  if FORGE_HOST_LINUX
    const ssize_t size = readlink("/proc/self/exe", out.data(), out.size() - 1);
    if (size > 0) {
        out[static_cast<std::size_t>(size)] = '\0';
    }
#  else
    // dladdr gives the main executable the path it was started with, which may be relative to a
    // directory the process has left since; proc_pidpath's is absolute.
    std::array<char, PROC_PIDPATHINFO_MAXSIZE> buffer{};
    if (proc_pidpath(getpid(), buffer.data(), static_cast<std::uint32_t>(buffer.size())) > 0) {
        copy_path(buffer.data(), out);
    }
#  endif
}

#  if FORGE_HOST_LINUX
struct module_search {
    std::uintptr_t address;
    std::span<char> path;
    std::optional<std::uintptr_t> relative;
};

// The pointer stays non-const: dl_iterate_phdr's callback type takes a dl_phdr_info*.
int find_module(dl_phdr_info* info, // NOLINT(misc-const-correctness)
                std::size_t /*size*/,
                void* data) noexcept {
    auto& search = *static_cast<module_search*>(data);
    for (std::size_t i = 0; i < info->dlpi_phnum; ++i) {
        const ElfW(Phdr) & segment = info->dlpi_phdr[i];
        const std::uintptr_t start = info->dlpi_addr + segment.p_vaddr;
        if (segment.p_type == PT_LOAD && search.address >= start &&
            search.address - start < segment.p_memsz) {
            // The main executable is the object without a name.
            if (info->dlpi_name != nullptr && info->dlpi_name[0] != '\0') {
                copy_path(info->dlpi_name, search.path);
            } else {
                executable_path_into(search.path);
            }
            search.relative = search.address - info->dlpi_addr;
            return 1;
        }
    }
    return 0;
}
#  endif

// Closes a file descriptor when it goes out of scope.
class file_descriptor {
public:
    explicit file_descriptor(int fd) noexcept : m_fd(fd) {}
    file_descriptor(const file_descriptor&) = delete;
    file_descriptor& operator=(const file_descriptor&) = delete;
    file_descriptor(file_descriptor&&) = delete;
    file_descriptor& operator=(file_descriptor&&) = delete;
    ~file_descriptor() { reset(); }

    [[nodiscard]] int get() const noexcept { return m_fd; }
    [[nodiscard]] bool is_open() const noexcept { return m_fd >= 0; }

    void reset() noexcept {
        if (m_fd >= 0) {
            close(m_fd);
            m_fd = -1;
        }
    }

private:
    int m_fd;
};

// Marks `fd` close-on-exec, so that no other child, such as one that another thread starts, keeps
// the symbolizer's input open; and nonblocking if asked.
void set_flags(int fd, bool nonblocking) noexcept {
    fcntl(fd, F_SETFD, FD_CLOEXEC);
    if (nonblocking) {
        const auto flags = static_cast<unsigned>(fcntl(fd, F_GETFL));
        fcntl(fd, F_SETFL, static_cast<int>(flags | static_cast<unsigned>(O_NONBLOCK)));
    }
}

char** environment() noexcept {
#  if FORGE_HOST_MACOS
    // A shared library cannot refer to environ on macOS.
    return *_NSGetEnviron();
#  else
    return environ;
#  endif
}

bool would_block(int error) noexcept {
    return error == EAGAIN || error == EWOULDBLOCK || error == EINTR;
}

// Writes what the child can take of `pending` without blocking. Stops writing, by emptying
// `pending`, when the child has closed its input.
void write_some(const file_descriptor& fd, std::string_view& pending) noexcept {
#  ifdef MSG_NOSIGNAL
    constexpr int flags = MSG_NOSIGNAL;
#  else
    constexpr int flags = 0;
#  endif
    const ssize_t written = send(fd.get(), pending.data(), pending.size(), flags);
    if (written >= 0) {
        pending.remove_prefix(static_cast<std::size_t>(written));
    } else if (!would_block(errno)) {
        pending = {};
    }
}

// Appends what the child has written to `text`, and closes `fd` at the end of its output.
void read_some(file_descriptor& fd, std::string& text) {
    std::array<char, 4096> buffer{};
    const ssize_t size = read(fd.get(), buffer.data(), buffer.size());
    if (size > 0) {
        text.append(buffer.data(), static_cast<std::size_t>(size));
    } else if (size == 0 || !would_block(errno)) {
        fd.reset();
    }
}

// Waits for the child until `deadline`, then kills it. Returns whether it exited successfully.
bool wait_for(pid_t pid, std::chrono::steady_clock::time_point deadline) noexcept {
    bool killed = false;
    while (true) {
        int status = 0;
        const pid_t waited = waitpid(pid, &status, killed ? 0 : WNOHANG);
        if (waited == pid) {
            return !killed && WIFEXITED(status) && WEXITSTATUS(status) == 0;
        }
        if (waited < 0 && errno != EINTR) {
            // ECHILD: the process ignores SIGCHLD, so the child was reaped without a status.
            return !killed && errno == ECHILD;
        }
        if (waited == 0) {
            if (std::chrono::steady_clock::now() >= deadline) {
                kill(pid, SIGKILL);
                killed = true;
            } else {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        }
    }
}

} // namespace

std::optional<std::uintptr_t> resolve_module(std::uintptr_t address,
                                             std::span<char> path) noexcept {
    copy_path("", path);
#  if FORGE_HOST_LINUX
    module_search search{.address = address, .path = path, .relative = std::nullopt};
    dl_iterate_phdr(&find_module, &search);
    return search.relative;
#  else
    // dladdr's dli_sname and dli_saddr are never used: they name the nearest exported symbol.
    Dl_info info{};
    // NOLINTNEXTLINE(performance-no-int-to-ptr): dladdr takes the address as a pointer.
    if (dladdr(reinterpret_cast<const void*>(address), &info) == 0 || info.dli_fbase == nullptr) {
        return std::nullopt;
    }
    for (std::uint32_t i = 0, count = _dyld_image_count(); i < count; ++i) {
        if (_dyld_get_image_header(i) != info.dli_fbase) {
            continue;
        }
        if (static_cast<const mach_header*>(info.dli_fbase)->filetype == MH_EXECUTE) {
            executable_path_into(path);
        } else if (info.dli_fname != nullptr) {
            copy_path(info.dli_fname, path);
        }
        // The address the image's own load commands give, which is what llvm-symbolizer expects:
        // for a main executable, 0x100000000 plus the offset in __TEXT.
        return address - static_cast<std::uintptr_t>(_dyld_get_image_vmaddr_slide(i));
    }
    return std::nullopt;
#  endif
}

std::optional<std::string> environment_variable(const char* name) {
    const char* value = std::getenv(name);
    return value != nullptr ? std::optional<std::string>(value) : std::nullopt;
}

std::string executable_path() {
    std::array<char, 4096> buffer{};
    executable_path_into(buffer);
    return buffer.data();
}

bool is_program(const std::string& path) {
    struct stat status{};
    return stat(path.c_str(), &status) == 0 && S_ISREG(status.st_mode) &&
           access(path.c_str(), X_OK) == 0;
}

symbolizer_output run_symbolizer(const std::string& program,
                                 std::string_view input,
                                 std::chrono::steady_clock::duration timeout) {
    symbolizer_output result;

    // The child's standard input is a socket rather than a pipe: writing to it after the child has
    // exited then fails with EPIPE (MSG_NOSIGNAL, SO_NOSIGPIPE), where a pipe would raise SIGPIPE
    // and end this process.
    std::array<int, 2> input_fds{-1, -1};
    std::array<int, 2> output_fds{-1, -1};
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, input_fds.data()) != 0) {
        return result;
    }
    file_descriptor input_parent(input_fds[0]);
    file_descriptor input_child(input_fds[1]);
    if (pipe(output_fds.data()) != 0) {
        return result;
    }
    file_descriptor output_parent(output_fds[0]);
    file_descriptor output_child(output_fds[1]);
    set_flags(input_parent.get(), true);
    set_flags(input_child.get(), false);
    set_flags(output_parent.get(), true);
    set_flags(output_child.get(), false);
#  ifdef SO_NOSIGPIPE
    const int no_sigpipe = 1;
    setsockopt(input_parent.get(), SOL_SOCKET, SO_NOSIGPIPE, &no_sigpipe, sizeof no_sigpipe);
#  endif

    posix_spawn_file_actions_t actions{};
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_adddup2(&actions, input_child.get(), STDIN_FILENO);
    posix_spawn_file_actions_adddup2(&actions, output_child.get(), STDOUT_FILENO);
    posix_spawn_file_actions_addopen(&actions, STDERR_FILENO, "/dev/null", O_WRONLY, 0);
    std::array<std::string, 4> arguments{
        program,
        "--functions=linkage",
        "--inlining",
        "--demangle",
    };
    std::array<char*, 5> argv{
        arguments[0].data(),
        arguments[1].data(),
        arguments[2].data(),
        arguments[3].data(),
        nullptr,
    };

    pid_t pid = 0;
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    const int spawned =
        posix_spawn(&pid, program.c_str(), &actions, nullptr, argv.data(), environment());
    posix_spawn_file_actions_destroy(&actions);
    input_child.reset();
    output_child.reset();
    if (spawned != 0) {
        return result;
    }

    // Writing and reading at once: a child that answers before it has read every request would
    // otherwise block on a full pipe while this process blocks writing to it.
    std::string_view pending = input;
    bool timed_out = false;
    while (output_parent.is_open()) {
        if (pending.empty()) {
            input_parent.reset();
        }
        std::array<pollfd, 2> fds{};
        fds[0] = {.fd = output_parent.get(), .events = POLLIN, .revents = 0};
        fds[1] = {.fd = input_parent.get(), .events = POLLOUT, .revents = 0};
        const auto remaining = std::chrono::ceil<std::chrono::milliseconds>(
            deadline - std::chrono::steady_clock::now());
        if (remaining.count() <= 0) {
            timed_out = true;
            break;
        }
        // poll ignores the negative descriptor of a closed input.
        const int ready =
            poll(fds.data(),
                 fds.size(),
                 static_cast<int>(std::min<std::int64_t>(remaining.count(), INT_MAX)));
        if (ready < 0 && errno != EINTR) {
            timed_out = true;
            break;
        }
        if (fds[1].revents != 0) {
            write_some(input_parent, pending);
        }
        if (fds[0].revents != 0) {
            read_some(output_parent, result.text);
        }
    }
    input_parent.reset();
    output_parent.reset();

    result.succeeded =
        wait_for(pid, timed_out ? std::chrono::steady_clock::now() : deadline) && !timed_out;
    return result;
}

} // namespace host
} // namespace forge::stacktrace

#endif
