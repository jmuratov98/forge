# Stack traces [stacktrace]

Status: implemented on Linux and macOS, 2026-11-03. The Windows implementation has not been compiled
yet.

## 0 Conventions [stacktrace.conventions]

1 This document follows the conventions of ISO/IEC 14882 [structure.specifications] and
[structure.summary]. A bracketed name such as [stacktrace.capture] is the stable name of a clause of
this document. Unqualified stable names such as [support.signal] or [basic.stc.dynamic] refer to
ISO/IEC 14882.

2 Clauses 1 to 9 and Annex A are normative. Notes and examples in them are informative,
as are Annexes B and C.

3 The words "shall" and "shall not" state requirements on the implementation of forge. "Unspecified"
and "implementation-defined" have the meanings given in ISO/IEC 14882 [intro.defs]; an
implementation-defined property is documented in the source of the implementation.

## 1 Scope [stacktrace.scope]

1 This document specifies the facilities of forge's `core` component that capture the return
addresses of the calling thread's stack and write them in readable form. It also specifies how the
failure report of `forge/core/assert.hpp` uses them.

2 The following are outside the scope of this document:

- (2.1) handlers for signals and for Windows structured exceptions, other than the live-dump handler
  of [context.dump] (`docs/crash_context.md`);
- (2.2) entries that describe what forge was doing when it failed ("crash context"), which
  `docs/crash_context.md` specifies;
- (2.3) types that own a captured trace, for storing it and printing it later;
- (2.4) crash reproducers, build identifiers, and debug information kept for Release builds.

3 The facilities are specified for the hosts for which `forge/core/config.hpp` defines
`FORGE_HOST_LINUX`, `FORGE_HOST_MACOS` or `FORGE_HOST_WINDOWS` to 1.

## 2 Terms and definitions [stacktrace.defs]

**2.1 return address**: the address of the instruction at which execution of a caller resumes when
a function invocation returns.

**2.2 call-site address**: a return address minus one.

[Note 1: A call-site address lies within the call instruction, so it maps to the source location of
the call rather than to the location after it. — end note]

**2.3 module**: an executable or shared-library image loaded in the process: an ELF object on Linux,
a Mach-O image on macOS, a PE image on Windows.

**2.4 main executable**: the module from which the process was started.

**2.5 module-relative address**: for an address *a* within a module *M*, the value that the
symbolizer accepts as the address of *a* in *M*, as given by [stacktrace.module].

**2.6 symbolizer**: the program `llvm-symbolizer`, or any program that provides its command-line
interface and its default ("LLVM") output style.

**2.7 physical frame**: an element of a captured trace.

**2.8 inlined frame**: a function invocation that the symbolizer reports as having been inlined at
the call-site address of a physical frame.

## 3 Header `<forge/core/stacktrace.hpp>` synopsis [stacktrace.syn]

```cpp
#include "forge/core/config.hpp"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <span>

namespace forge::stacktrace {

// [stacktrace.capture], capture
FORGE_NOINLINE FORGE_API std::size_t capture(std::span<std::uintptr_t> frames,
                                             std::size_t skip = 0) noexcept;

// [stacktrace.print], output
FORGE_API void print(std::FILE* file, std::span<const std::uintptr_t> frames,
                     bool truncated) noexcept;

} // namespace forge::stacktrace
```

1 The header declares no other names in namespace `forge::stacktrace`, and none in namespace
`forge`.

[Note 1: The classes `frame` and `stacktrace` that the header used to declare are removed.
— end note]

## 4 Capture [stacktrace.capture]

```cpp
std::size_t stacktrace::capture(std::span<std::uintptr_t> frames, std::size_t skip = 0) noexcept;
```

1 Let *S* be the sequence of return addresses of the function invocations active in the calling
thread, ordered from innermost to outermost, beginning with that of the invocation of
`stacktrace::capture` itself, which lies in its caller. Let *n* be min(`frames.size()`,
max(0, |*S*| − `skip`)).

2 *Effects*: Assigns *S*[`skip` + *i*] to `frames[`*i*`]` for each *i* in [0, *n*).

3 *Postconditions*: The elements `frames[`*i*`]` for *i* ≥ *n* are unchanged.

4 *Returns*: *n*.

5 *Remarks*: The function does not allocate storage with an allocation function
([basic.stc.dynamic]), does not acquire a lock, and does not perform initialization that is
deferred to its first call. On Linux with libgcc 12 or later and glibc 2.35 or later, and on
Windows, a call to the function is a signal-safe evaluation ([support.signal]). On other hosts,
whether it is one is implementation-defined.

6 *Remarks*: An inlined function invocation has no return address of its own and contributes no
element to *S*. If an active invocation has no unwind information, it is unspecified whether *S*
contains its return address and the return addresses of invocations outside it.

[Note 1: The implementation uses `_Unwind_Backtrace` on POSIX hosts and `RtlCaptureStackBackTrace`
on Windows. Neither needs frame pointers, but the former needs unwind tables ([stacktrace.build]
paragraph 1). Both report the frame of the function that calls them first, which is
`stacktrace::capture` itself, so the implementation skips one frame more than `skip`, saturating.
glibc's `backtrace` is not used: its first call loads `libgcc_s` with `dlopen`, which allocates.
— end note]

[Note 2: A caller that needs to know whether its trace was truncated passes a span one element
longer than it intends to print; see [stacktrace.report]. — end note]

## 5 Output [stacktrace.print]

```cpp
void stacktrace::print(std::FILE* file, std::span<const std::uintptr_t> frames, bool truncated) noexcept;
```

1 *Preconditions*: `file` points to a stream open for writing. Each element of `frames` is a
return address that `stacktrace::capture` stored in the current process, and no module containing
one of them has been unloaded since.

2 *Effects*: Resolves each element of `frames` to a module ([stacktrace.module]), symbolizes the
elements unless symbolization is disabled ([stacktrace.symbolize]), writes to `file` the text that
[stacktrace.format] specifies, and flushes `file`.

3 *Synchronization*: Output from concurrent calls that write to the same stream may interleave.

4 *Remarks*: The function may allocate storage. Errors that occur while writing to `file` are
ignored. No failure of symbolization causes the function to terminate the program.

## 6 Module resolution [stacktrace.module]

1 For each element *r* of `frames`, let *a* be the call-site address *r* − 1. The implementation
determines the module *M* that contains *a*, the path of *M*, and the module-relative address of *a*
in *M*, as Table 1 specifies.

**Table 1: Module resolution**

| Host | Module containing *a* | Path of *M* | Module-relative address |
|---|---|---|---|
| Linux | the object, among those reported by `dl_iterate_phdr`, with a `PT_LOAD` segment containing *a* | `dlpi_name`; if empty, the target of `/proc/self/exe` | *a* − `dlpi_addr` |
| macOS | the image whose header is the `dli_fbase` that `dladdr` reports for *a* | `dli_fname`; for the main executable, the path `proc_pidpath` reports | *a* − the image's `_dyld_get_image_vmaddr_slide` |
| Windows | the module that `GetModuleHandleExW` reports for *a* with `GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS` and `GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT` | `GetModuleFileNameW`, converted to UTF-8 | *a* − the module's base address |

2 The *module name* of *M* is the final component of its path.

3 If no module contains *a*, the physical frame is *unresolved*.

4 Module resolution does not allocate storage with an allocation function.

5 The implementation shall not use the `dli_sname` or `dli_saddr` that `dladdr` reports.

[Note 1: `dladdr` considers only exported symbols and reports the nearest exported symbol below
the address. For forge's hidden-visibility and internal-linkage functions, that symbol is usually
some other function. — end note]

[Note 2: `dli_fname` is the path the main executable was started with, which may be relative to a
directory the process has since left. — end note]

[Note 3: On macOS the module-relative address is the address that the image's own load commands
give, so for a main executable it includes the 4 GiB `__PAGEZERO` segment: `0x100001f3a`, not
`0x1f3a`. That is the address `llvm-symbolizer` and `atos` expect. — end note]

## 7 Symbolization [stacktrace.symbolize]

1 Symbolization is *disabled* if the environment variable `FORGE_DISABLE_SYMBOLIZATION` has the
value `1`.

2 Otherwise, the symbolizer program *P* is the first of the following that names an existing file
other than a directory, which on POSIX hosts the calling process may execute:

- (2.1) the value of the environment variable `FORGE_SYMBOLIZER_PATH`, if that is set and not empty;
- (2.2) a file named `llvm-symbolizer` (`llvm-symbolizer.exe` on Windows) in the directory that
  contains the main executable;
- (2.3) the first file named as in (2.2) found by searching the directories in the environment
  variable `PATH`.

If none exists, symbolization is *unavailable*.

3 The implementation creates a child process that runs *P* with the arguments
`--functions=linkage`, `--inlining` and `--demangle`, plus `--relative-address` on Windows.
The child's standard input and standard output are connected to the calling process, through pipes
except for standard input on POSIX hosts, which is one end of a socket pair. Its standard error is
connected to the null device. The child inherits the environment of the calling process.

[Note 1: A socket lets a write fail with `EPIPE` (`MSG_NOSIGNAL`, `SO_NOSIGPIPE`) when the child has
exited early, where a pipe would raise `SIGPIPE` and end the calling process. On POSIX hosts the
implementation writes requests and reads responses at once, so neither process waits for the other
when a pipe fills; Windows cannot wait on an anonymous pipe, so there each pipe is given a buffer of
1 MiB and all requests are written first. — end note]

4 For each physical frame that is resolved, in order, the implementation writes one line to the
child's standard input: `CODE "`*path*`" 0x`*address*, where *path* is the path of the frame's
module and *address* is its module-relative address in lowercase hexadecimal. A frame whose
module path contains a `"` character or a line break is not written and gets no response. After
the last line, the implementation closes the child's standard input.

5 The *response* for a line written in (4) is a sequence of one or more *entries* followed by an
empty line. Each entry is a function line followed by a location line of the form
*file*`:`*line*`:`*column*. The first entry describes the innermost invocation, and each later entry
describes the invocation that the previous one was inlined into. A function line `??` denotes an
unknown function. A location line `??:0:0` denotes an unknown location. A line or column of `0`
denotes an unknown line or column.

6 Before a response is used, its leading entries whose function line names a function in namespace
`forge::detail` are removed, as long as one entry remains. A function line names such a function if
`forge::detail::` occurs in it before the first `(`, at its start or after a space.

[Note 2: The helpers through which a failed check reaches `report_failure` are always inlined into
the function with the check ([stacktrace.report] paragraph 1). Where there is debug information,
the symbolizer reports them as the innermost entries of frame 0, which would make the function the
reader is looking for `#0.1`. Clang's `nodebug` attribute would keep them out of the debug
information, but GCC has no equivalent, so they are removed here, the same way for every compiler.
— end note]

7 If the child has not produced a response for every line written in (4) within 10 seconds of its
creation, the implementation terminates the child.

8 Symbolization *fails* if the child cannot be created, if it is terminated by (7), if it exits
unsuccessfully, or if its standard output does not match (5). Responses that were read completely
before the failure are used. Frames without a complete response are written without symbol
information.

9 Before `stacktrace::print` returns, the child has terminated and its resources have been released.

10 The implementation shall not determine symbol information in any other way.

[Note 3: There is no in-process fallback, because the only one available without parsing debug
information in-process is the `dladdr` lookup that [stacktrace.module] paragraph 5 forbids.
— end note]

## 8 Output format [stacktrace.format]

1 The text consists of the following lines, in order, each ending with a newline character:

- (1.1) the header line `  stack trace:`;
- (1.2) the frame lines (paragraph 2), for each physical frame in order;
- (1.3) if `truncated` is `true`, the line `    (more frames not shown)`;
- (1.4) if symbolization is unavailable, the line
  `  note: no llvm-symbolizer found; set FORGE_SYMBOLIZER_PATH to show function names and lines`;
  if symbolization failed, the line `  note: llvm-symbolizer failed; frames are shown without names`.

2 Physical frame *i* (counting from 0) has one frame line for each entry *k* of its response
(counting from 0), or a single frame line with *k* = 0 if it has no response. A frame line consists
of:

- (2.1) four spaces, `#`, and *i* in decimal; if *k* > 0, then `.` and *k* in decimal;
- (2.2) a space, then, for a resolved frame, the module name, `+0x`, and the module-relative address
  in lowercase hexadecimal without leading zeros; for an unresolved frame, `0x` and the call-site
  address in lowercase hexadecimal without leading zeros;
- (2.3) if the entry's function is known, a space and the function line;
- (2.4) if the entry's file is known, a space and the file; if the line is also known, `:` and the
  line; if the column is also known, `:` and the column.

3 The text contains no absolute address except for an unresolved frame, and no build identifier.

[Example 1: A failure in `halve`, inlined into `quarter`, with a symbolizer available:
```
  stack trace:
    #0 forge_core_unittests+0x1f3a3 forge::(anonymous namespace)::halve(int) /src/forge/unittests/core/assert_test.cpp:34:5
    #0.1 forge_core_unittests+0x1f3a3 forge::(anonymous namespace)::quarter(int) /src/forge/unittests/core/assert_test.cpp:40:12
    #1 forge_core_unittests+0x1f8bf forge::(anonymous namespace)::assertions_failure_Test::TestBody() /src/forge/unittests/core/assert_test.cpp:109:5
    #2 libsystem_c.dylib+0x7a1b
    (more frames not shown)
```
— end example]

[Note 1: Because the printed address is module-relative and a call-site address, running
`llvm-symbolizer --obj=`*module* *address* (with `--relative-address` on Windows) on a frame copied
from a report gives the location of the call. — end note]

## 9 Failure reports [stacktrace.report]

1 `forge::detail::report_failure` (`forge/core/assert.hpp`) shall be declared `FORGE_NOINLINE`.
`forge::detail::assertion_failed`, `unreachable_reached` and `todo_reached` shall be declared
`FORGE_ALWAYS_INLINE`.

2 *Effects*: `report_failure` performs the following steps, in order:

- (2.1) Before any other effect, calls `stacktrace::capture(frames, 1)`, where `frames` is an object
  of type `std::array<std::uintptr_t, 33>` with automatic storage duration. Let *n* be the result.
- (2.2) Writes the first lines of the report (location and kind of failure, message if there is
  one, function), followed by the version and banner lines of [context.report] paragraph 1, to
  `stderr`, and flushes `stderr`.
- (2.3) Writes the context of the calling thread, as [context.report] paragraph 2 specifies.
- (2.4) Calls `stacktrace::print(stderr, std::span(frames).first(std::min(`*n*`, 32)), `*n*` == 33)`.
- (2.5) Calls `std::abort()`.

3 *Remarks*: No storage is allocated with an allocation function before step (2.2) completes.
Steps (2.2) to (2.5) happen while the reporting lock and the reentrancy guard of `report_failure`
are held.

4 *Remarks*: Physical frame 0 is the invocation of the function that contains the failed check,
and by [stacktrace.symbolize] paragraph 6 its first frame line names that function. However, when
`FORGE_ALWAYS_INLINE` has no effect, frame 0 may instead be the invocation of the helper named in
paragraph 1.

[Note 1: MSVC ignores `__forceinline` when inlining is disabled (`/Od`), as in Debug builds.
`report_failure` is `FORGE_NOINLINE` so that link-time optimization cannot inline it into its
caller and cause step (2.1) to skip the wrong frame. — end note]

## Annex A (normative) Build and tooling requirements [stacktrace.build]

1 For GCC and Clang, the build shall compile every project, third-party ones included, with
`-fasynchronous-unwind-tables` (`forge.baseline()` in `premake/forge.lua`).

[Note 1: Clang leaves the tables out on arm64 macOS when exceptions are disabled, as they are by
default, and `_Unwind_Backtrace` then finds no frame at all. A trace stops at the first frame
without them, so third-party code such as googletest needs them as much as forge's own. — end note]

2 The implementation shall consist of `forge/source/forge/core/stacktrace.cpp` (the parts common to
all hosts), `posix_stacktrace.cpp` and `windows_stacktrace.cpp` in the same directory, and the
private header `stacktrace_host.hpp` through which they connect. Each of the two host files is
wrapped in `#if FORGE_HOST_POSIX` or `#if FORGE_HOST_WINDOWS`. The build shall link no additional
library.

3 `./x` shall provide `tools.find_symbolizer()` in `utils/xtool/tools.py`, which searches, in order:
`FORGE_SYMBOLIZER_PATH`, `PATH`, the Homebrew `llvm` prefix, and `/usr/lib/llvm-*`, newest first.
The symbolizer shall not be downloaded. When it is found, `./x test` and `./x run` shall set
`FORGE_SYMBOLIZER_PATH` in the environment of the programs they run, and `./x run llvm-symbolizer`
runs it. `./x setup` and `./x doctor`
shall report whether it was found. Its absence is a warning.

4 CI shall install the `llvm-symbolizer` of the LLVM version that `.github/ci/llvm-tools.json`
pins, together with FileCheck, with `.github/ci/install-llvm-tools.sh`, and set
`FORGE_SYMBOLIZER_PATH` to it (`.github/actions/setup/action.yml`).

5 No binary shall be stripped of its symbol table, in any configuration and with any toolset.

[Note 2: Premake's GCC toolset links with `-s` (`-Wl,-x` on macOS) when symbols are `Off` or
`Default`, as in Release; `premake/forge.lua` removes those flags. The symbolizer names a function
of a stripped binary after whatever symbol is left nearest to its address, which is usually another
function. Premake's Clang toolset and CMake do not strip. — end note]

6 On macOS, the build shall run `dsymutil` on each binary it links, in every configuration that has
debug information.

[Note 3: There the debug information stays in the object files, and `llvm-symbolizer` reads it only
from a `.dSYM` bundle next to the binary: without one, function names come from the symbol table,
and file and line are unknown. — end note]

## Annex B (informative) Tests [stacktrace.tests]

1 `forge/unittests/core/stacktrace_test.cpp` checks the following:

- (1.1) a capture into a non-empty span returns at least 1;
- (1.2) a capture into an empty span returns 0;
- (1.3) a capture into a span of 2 elements returns 2;
- (1.4) a capture with a `skip` larger than the stack depth returns 0, and so does one with the
  largest `std::size_t`;
- (1.5) within one `FORGE_NOINLINE` helper, element 0 of a capture with `skip` 1 equals element 1 of
  a capture with `skip` 0;
- (1.6) the elements past the result are unchanged;
- (1.7) with `FORGE_DISABLE_SYMBOLIZATION=1`, `print` writes the header line and one frame line per
  frame in the form of [stacktrace.format] paragraph 2, without function or location, and nothing
  else, and frame 0 is in the test executable;
- (1.8) `print` with `truncated` writes `    (more frames not shown)` last;
- (1.9) when `FORGE_SYMBOLIZER_PATH` is set, and skipped otherwise: frame 0 of a capture in a test
  names the test's function and, except in Release, which has no debug information, its file and
  the line of the call.

2 The death tests in `forge/unittests/core/assert_test.cpp` check the following:

- (2.1) in every configuration, that a `FORGE_TODO` report contains `  stack trace:` followed by a
  line `    #0 ` and the executable's module name;
- (2.2) when `FORGE_SYMBOLIZER_PATH` is set, and skipped otherwise, that the same report's frame 0
  names the function with the check. That function is `FORGE_NOINLINE`, so that its name is in the
  symbol table in every configuration.

3 The death tests match whole lines with `std::regex` (`forge/unittests/core/report_matchers.hpp`):
GoogleTest's regular expressions are POSIX ones on Linux and macOS, where `.` also matches a newline,
so a pattern such as `#0 .*halve` would also match a report whose frame 0 is wrong. As before, rows
that use ThreadSanitizer skip the death tests.

4 The build tests check Annex A: `forge/test/build/configurations.lua` and `site-config.lua`
paragraph 1, and `symbols.lua` paragraphs 5 and 6. `utils/xtool/test/tools_test.py` checks where
`./x` finds `llvm-symbolizer`.

## Annex C (informative) Rationale [stacktrace.rationale]

### C.1 Prior art [stacktrace.rationale.prior]

| Project | Capture | Symbol information | Remarks |
|---|---|---|---|
| `std::stacktrace` | — | — | libc++ has no implementation; libstdc++ needs `-lstdc++exp` and misses symbols in shared libraries (GCC bug 112263); MSVC STL uses DbgEng, which is not thread-safe and needs its DLLs shipped. Not usable at forge's compiler floor. |
| LLVM `Signals` | `_Unwind_Backtrace` or `backtrace` | Spawns `llvm-symbolizer` (`LLVM_SYMBOLIZER_PATH`, then next to the binary, then `PATH`); otherwise `dladdr` or DbgHelp | `LLVM_DISABLE_SYMBOLIZATION`; an optional symbolizer markup mode with build IDs. |
| Abseil, glog, Chromium | Own unwinder | Own ELF `.symtab` reader using only stack memory | Signal-safe; names without lines; ELF only. |
| cpptrace | Raw trace, then object trace, then resolved trace | libdwarf or DbgHelp | Its signal-safe interface fills a caller buffer and resolves in another process. |
| Rust `std::backtrace` | Program counters | Resolved lazily when printed | Disabled unless `RUST_BACKTRACE` is set. |
| Boost.Stacktrace | `safe_dump_to` writes raw addresses | Resolved in a later run | |

1 All of these separate capture, which must be cheap and safe, from symbolization, which is
expensive and may fail. This document does the same: [stacktrace.capture] against
[stacktrace.symbolize].

### C.2 Departures from LLVM [stacktrace.rationale.llvm]

| This document | LLVM | Reason |
|---|---|---|
| No in-process symbol information ([stacktrace.symbolize] paragraph 10) | Falls back to `dladdr` or DbgHelp | `dladdr` reports wrong names for hidden and internal functions. |
| Inlined `forge::detail` entries are left out ([stacktrace.symbolize] paragraph 6) | Writes every entry the symbolizer reports | Frame 0 of a failure report names the function with the check, with every compiler. |
| Call-site addresses ([stacktrace.defs] 2.2) | Raw return addresses | A frame copied from a report symbolizes to the line of the call. |
| Module-relative addresses only ([stacktrace.format] paragraph 3) | Absolute and module-relative | Absolute addresses differ between runs. |
| Capture into a buffer the caller provides | `backtrace` into a fixed array | The same function serves signal handlers and stored traces. |
| Symbolizer search order | Same | Copied. |
| No build identifiers | Only in the markup mode | Same as clang, by choice. |

### C.3 Relationship to later documents [stacktrace.rationale.future]

1 The interface leaves room for the items that [stacktrace.scope] paragraph 2 excludes:

- (1.1) A signal handler can call `stacktrace::capture` without change. Its frame 0 is a faulting
  instruction rather than a return address, so converting it to a call-site address would be
  wrong; that document has to address this.
- (1.2) A type that owns a trace can consist of a fixed-capacity array and a size, built on these
  two functions.
- (1.3) Crash-context entries are written in [stacktrace.report] step (2.3) (`docs/crash_context.md`).
- (1.4) The code that creates processes is expected to move to a shared process facility once the
  driver needs one.
