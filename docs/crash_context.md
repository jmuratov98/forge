# Crash context [context]

Status: implemented, 2026-11-03. Not yet built on Windows.

## 0 Conventions [context.conventions]

1 This document follows the conventions of [stacktrace.conventions] (`docs/stacktrace.md`).
Clauses 1 to 11 and Annex A are normative; Annexes B and C are informative.

## 1 Scope [context.scope]

1 This document specifies:

- (1.1) *context entries*, objects that describe what forge is doing while they exist;
- (1.2) how a task running on another thread inherits the entries of the thread that started it;
- (1.3) the context, version and bug-report lines of failure reports;
- (1.4) writing the current context on request while forge keeps running (a *live dump*).

2 The following are outside the scope of this document:

- (2.1) creation of entries by forge's pass or query infrastructure, which is expected to use this
  interface;
- (2.2) live dumps on Windows;
- (2.3) handlers for crash signals ([stacktrace.scope] paragraph 2).

3 The facilities are specified for the hosts of [stacktrace.scope] paragraph 3.

## 2 Terms and definitions [context.defs]

**2.1 context entry**: an object of a class derived from `context_node`, other than
`inherited_context`.

**2.2 node**: an object of a class derived from `context_node`.

**2.3 active**: describes a node during its lifetime ([basic.life]).

**2.4 innermost node** of a thread: the active node that the thread constructed most recently.

**2.5 task**: work that runs on a thread other than the thread that created it.

**2.6 context chain** of a thread: the sequence of nodes defined in [context.chain] paragraph 1.

## 3 Header `<forge/core/crash_context.hpp>` synopsis [context.syn]

```cpp
#include "forge/core/config.hpp"

#include <cstddef>
#include <format>
#include <string_view>
#include <type_traits>

namespace forge {

// [context.sink], sinks
class context_sink;

// [context.node], nodes
class context_node;

// [context.entry], entries
template <typename Print>
class context_entry;

// [context.args], program arguments
class program_arguments_entry;

// [context.inherit], inheritance
class context_token;
[[nodiscard]] FORGE_API context_token current_context() noexcept;
class inherited_context;

// [context.dump], live dumps
FORGE_API bool enable_context_dump() noexcept;

} // namespace forge
```

## 4 Sinks [context.sink]

```cpp
class context_sink {
public:
    context_sink(const context_sink&) = delete;
    context_sink& operator=(const context_sink&) = delete;

    void write(std::string_view text) noexcept;

    template <typename... Args>
    void format(std::format_string<Args...> format, Args&&... args) noexcept;
};
```

1 A `context_sink` collects the text of one context entry in storage of fixed capacity, at least
1024 bytes, that it owns. Only the implementation creates `context_sink` objects. Text beyond the
capacity is discarded.

```cpp
void write(std::string_view text) noexcept;
```

2 *Effects*: Appends `text` to the sink's text.

```cpp
template <typename... Args>
void format(std::format_string<Args...> format, Args&&... args) noexcept;
```

3 *Effects*: Appends to the sink's text the characters that
`std::format(format, std::forward<Args>(args)...)` would return.

4 *Remarks*: Neither function allocates storage with an allocation function ([basic.stc.dynamic]),
except where a `std::formatter` specialization for one of `Args` does.

## 5 Nodes [context.node]

```cpp
class context_node {
public:
    context_node(const context_node&) = delete;
    context_node& operator=(const context_node&) = delete;

protected:
    using print_function = void (*)(const context_node& node, context_sink& out) noexcept;

    FORGE_API explicit context_node(print_function print) noexcept;
    FORGE_API ~context_node();
};
```

```cpp
explicit context_node(print_function print) noexcept;
```

1 *Effects*: Makes `*this` the innermost node of the calling thread. Records the node that was
innermost before, as the node *outer* to `*this`, and records `print` as the function that writes
the node's text. Then performs the dump check of [context.dump] paragraph 6.

```cpp
~context_node();
```

2 *Preconditions*: `*this` is the innermost node of the calling thread. No `context_token` refers
to `*this`.

3 *Effects*: Performs the dump check of [context.dump] paragraph 6. Then makes the node outer to
`*this` the innermost node of the calling thread.

4 *Remarks*: If `FORGE_ASSERTIONS_ENABLED` is 1, the destructor checks both preconditions with
`FORGE_ASSERT`. The message for the second is `context entry destroyed while a task still
inherits it`.

5 *Complexity* (both functions): Constant, when no dump is pending.

6 *Remarks* (both functions): When no dump is pending, neither function allocates storage with an
allocation function or acquires a lock. If `FORGE_ASSERTIONS_ENABLED` is 0, neither performs an
atomic read-modify-write operation.

## 6 Entries [context.entry]

```cpp
template <typename Print>
class context_entry : public context_node {
public:
    explicit context_entry(Print print) noexcept(std::is_nothrow_move_constructible_v<Print>);
};

template <typename Print>
context_entry(Print) -> context_entry<Print>;
```

1 *Mandates*: `std::is_invocable_v<const Print&, context_sink&>` is `true`.

```cpp
explicit context_entry(Print print) noexcept(std::is_nothrow_move_constructible_v<Print>);
```

2 *Preconditions*: While `*this` is active:

- (2.1) invoking `print` allocates no storage with an allocation function and does not exit via an
  exception; and
- (2.2) no other thread modifies an object that invoking `print` accesses.

3 *Effects*: Move-constructs a member from `print`. Then initializes the `context_node` base with a
function that invokes the member with its `context_sink&` argument.

4 *Remarks*: Constructing an entry neither invokes nor formats anything. `print` is invoked only
when the entry's text is written ([context.chain]).

[Example 1:
```cpp
void lower(const function& f) {
    forge::context_entry entry([&](forge::context_sink& out) {
        out.format("lowering function '{}'", f.name());
    });
    // ...
}
```
— end example]

[Note 1: Precondition (2.2) matters for entries that a task inherits ([context.inherit]): another
thread may print them while their own thread keeps running. — end note]

[Note 2: The implementation keeps `print` in a private base class listed before `context_node` (the
base-from-member idiom) rather than in a member: the `context_node` constructor and destructor may
write the entry for a live dump ([context.dump] paragraph 6), and a member would not exist yet, or
any more, while they run. `program_arguments_entry` keeps its arguments the same way. — end note]

## 7 Program arguments [context.args]

```cpp
class program_arguments_entry : public context_node {
public:
    FORGE_API program_arguments_entry(int argc, const char* const* argv) noexcept;
};
```

1 *Preconditions*: `argc` ≥ 0. `argv[0]` to `argv[argc - 1]` point to null-terminated strings, which
remain valid and unmodified while `*this` is active.

2 *Effects*: Constructs a context entry whose text is `program arguments:` followed, for each
argument in order, by a space and the argument, written as follows:

- (2.1) if the argument is not empty and contains none of space, tab, newline, `"` and `\`, as is;
- (2.2) otherwise, between `"` characters, with `\` before each `"` and `\`, and with each newline
  written as `\n`.

[Note 1: The `main` function of each forge program constructs one first, so it becomes entry 0 of
every report ([context.build] paragraph 2). — end note]

## 8 Inheritance [context.inherit]

```cpp
class context_token {
public:
    context_token() noexcept;
    context_token(context_token&& other) noexcept;
    context_token& operator=(context_token&& other) noexcept;
    ~context_token();
};

context_token current_context() noexcept;

class inherited_context : public context_node {
public:
    FORGE_API explicit inherited_context(const context_token& token) noexcept;
};
```

1 A `context_token` either refers to a node or refers to no node.

2 *Preconditions* (for each `context_token` object): The node it refers to, if any, is active
while the token exists.

```cpp
context_token() noexcept;
```

3 *Postconditions*: `*this` refers to no node.

```cpp
context_token current_context() noexcept;
```

4 *Returns*: A token that refers to the innermost node of the calling thread, or to no node if the
thread has no active node.

```cpp
context_token(context_token&& other) noexcept;
context_token& operator=(context_token&& other) noexcept;
```

5 *Effects*: `*this` refers to the node that `other` referred to, and `other` to no node. The
assignment operator first ends `*this`'s reference, as the destructor does.

```cpp
~context_token();
```

6 *Effects*: Ends the token's reference to its node, if any.

7 *Remarks* (all members): If `FORGE_ASSERTIONS_ENABLED` is 1, each node counts the tokens that
refer to it, using atomic operations, for [context.node] paragraph 4.

```cpp
explicit inherited_context(const context_token& token) noexcept;
```

8 *Preconditions*: `token` outlives `*this`.

9 *Effects*: Constructs a node that marks the start of a task. Its *inherited node* is the node that
`token` refers to, if any.

[Example 1:
```cpp
forge::context_token token = forge::current_context();  // on the thread that creates the task
pool.run([&token] {
    forge::inherited_context inherited(token);  // on the worker thread
    // ...
});
pool.wait();  // before token's node is destroyed
```
— end example]

[Note 1: Paragraph 2 requires structured concurrency: a task finishes before the entry it inherited
from ends. Assertion builds detect a violation when that entry is destroyed. — end note]

## 9 Context chains [context.chain]

1 The context chain of a thread *T* is the sequence obtained by starting from *T*'s innermost node
and, from each node *n*, continuing as follows:

- (1.1) if *n* is an `inherited_context` with an inherited node, at that inherited node;
- (1.2) if *n* is an `inherited_context` without one, nowhere: the chain ends after *n*;
- (1.3) otherwise, at the node outer to *n*, if any.

[Note 1: A worker thread's own entries outer to an `inherited_context` are not part of the chain.
— end note]

2 Writing the context of *T* to a stream *f* means the following. Let *C* be *T*'s context chain in
reverse order, outermost first. Number the context entries of *C* from 0, in order;
`inherited_context` nodes get no number. If *C* contains no context entry, nothing is written.
Otherwise the following lines are written, in order, each followed by a newline character, and
*f* is flushed after each line:

- (2.1) `  context:`;
- (2.2) for each node of *C*, in order:
  - for a context entry numbered *i*: four spaces, `#`, *i* in decimal, a space, and the text that
    the entry's print function writes into a newly created `context_sink`; each newline character
    in the text is written as a newline character followed by six spaces;
  - for an `inherited_context` that is not the first node of *C*, and does not directly follow
    another `inherited_context`: four spaces and
    `(the entries below run in a task on another thread)`.

3 If *C* contains more than 64 context entries, only entries 0 to 7 and the last 56 are written.
Between them the line `    (`*k*` entries not shown)` is written, where *k* is the number of
entries left out, and the `inherited_context` nodes among them are left out too.

4 *Remarks*: Collecting *C* uses storage of fixed size with automatic storage duration only.

## 10 Failure reports [context.report]

1 In [stacktrace.report] step (2.2), after the lines that step already writes and before flushing,
`report_failure` writes:

- (1.1) `  forge version: ` followed by `forge::version()` ([version.api]);
- (1.2) one banner line, where *url* is `forge::bug_report_url()` ([version.api]):
  - for an assertion or unreachable failure, if *url* is not empty:
    `  PLEASE submit a bug report to `*url*` and include this report and the input that caused it.`;
    if it is empty:
    `  PLEASE report this bug to the forge developers, with this report and the input that caused it.`;
  - for a TODO failure, if *url* is not empty: `  forge does not support this yet; see `*url*` for
    what is planned.`; if it is empty: `  forge does not support this yet.`

2 In [stacktrace.report] step (2.3), `report_failure` writes the context of the calling thread to
`stderr` ([context.chain] paragraph 2).

3 *Remarks*: Given [context.entry] paragraph 2, step (2.3) allocates no storage with an allocation
function. If a print function fails a check, the reentrancy guard of `report_failure` reports
that a check failed while reporting a failed check and aborts, and no stack trace is written.

[Example 1: A report from a worker thread of a Debug build, with an empty bug-report URL:
```
forge/source/forge/lower/call.cpp:88: internal error: assertion failed: callee != nullptr
  in function: void forge::lower_call(const forge::call_expr&)
  forge version: 0.1.0-dev+20261102T143005Z
  PLEASE report this bug to the forge developers, with this report and the input that caused it.
  context:
    #0 program arguments: forge -c foo.c -o foo.o
    #1 compiling 'foo.c'
    (the entries below run in a task on another thread)
    #2 lowering function 'main'
  stack trace:
    #0 forge+0x4a1f3 forge::lower_call(forge::call_expr const&) /src/forge/source/forge/lower/call.cpp:88:5
    ...
```
— end example]

## 11 Live dumps [context.dump]

```cpp
bool enable_context_dump() noexcept;
```

1 *Preconditions*: No other call to `enable_context_dump` runs concurrently.

2 *Effects*: On macOS, if the disposition of `SIGINFO` is `SIG_DFL`, installs the dump handler
for it. On Linux, the same for `SIGUSR1`. On Windows, has no effect.

3 *Returns*: `true` if the dump handler is installed for the signal when the function returns;
otherwise `false`.

4 *Remarks*: libforge never calls this function itself. Programs call it ([context.build]
paragraph 2).

5 The dump handler increments a counter of type `std::atomic<unsigned>`, for which
`is_always_lock_free` is `true`, and has no other effect.

[Note 1: A call to the handler is therefore a signal-safe evaluation ([support.signal]).
— end note]

6 The *dump check* on a thread *T* does nothing while *T* is writing a failure report or a dump.
Otherwise, the first dump check on *T* records the counter's value and writes nothing. A later one,
if the counter differs from the value *T* recorded last, records the counter's value and then,
holding the reporting lock of `report_failure`, writes to `stderr`:

- (6.1) the line `forge: context of thread `*id*`, on request:`, where *id* is an
  implementation-defined identifier of *T*;
- (6.2) the context of *T* ([context.chain] paragraph 2), including the node being constructed or
  destroyed;
- (6.3) the stack trace of *T*, as [stacktrace.report] steps (2.1) and (2.4) write it, with frame 0
  being the invocation that constructs or destroys the node.

7 *Remarks*: Writing a dump may allocate storage, and it does not end the program. A thread that
constructs and destroys no node after the signal writes no dump.

[Note 2: The handler only sets a flag. Each thread prints its own context at its next entry, so no
printing or symbolization runs in signal context. — end note]

[Note 3: Recording the counter at a thread's first check keeps a thread that starts after a request
from answering it. LLVM gets the same effect by having threads opt in, with
`EnablePrettyStackTraceOnSigInfoForThisThread`; here every thread takes part. — end note]

## Annex A (normative) Build requirements [context.build]

1 The interface is declared in `forge/include/forge/core/crash_context.hpp` and implemented in
`forge/source/forge/core/crash_context.cpp`, which shares the reporting lock and the writing of the
context with `assert.cpp` through the private header `forge/source/forge/core/report.hpp`. The innermost node and the recorded dump counter are
`thread_local` objects defined in that file. They are accessed only through functions exported
with `FORGE_API`.

[Note 1: On Windows, a `thread_local` variable cannot be exported from a DLL, so pushing a node is an
out-of-line call. — end note]

2 The `main` function of every forge program other than the unit tests shall begin with:

```cpp
forge::program_arguments_entry arguments(argc, argv);
forge::enable_context_dump();
```

## Annex B (informative) Tests [context.tests]

1 `forge/unittests/core/crash_context_test.cpp` checks the following with death tests:

- (1.1) a failure inside two nested entries reports `#0 ` and `#1 ` with their texts, in order;
- (1.2) a failure with no entries reports no `context:` line;
- (1.3) a failure inside 70 nested entries reports entries 0 to 7, `(6 entries not shown)`, and
  entries 14 to 69 ([context.chain] paragraph 3);
- (1.4) a newline in an entry's text continues on a line indented by six spaces;
- (1.5) the text of an entry longer than the sink's capacity is cut off at 1024 characters, without a
  crash;
- (1.6) a failure in a `std::thread` that inherits from the test's entry reports the test's entry,
  the task line, and then the thread's entry; a task that inherits no node reports no task line;
- (1.7) `program_arguments_entry` quotes an argument containing a space, an empty one, and one with
  `"`, `\` and a newline;
- (1.8) the version line matches `forge version: \d+\.\d+\.\d+\S*`, and each kind of failure has its
  banner line, with the URL empty;
- (1.9) in assertion builds, destroying an entry while a token refers to it reports
  `context entry destroyed while a task still inherits it`.

2 On POSIX hosts, a test calls `enable_context_dump`, raises the signal, constructs an entry, and
checks with GoogleTest's stderr capture that the dump contains `on request:`, the context including
the new entry, and a stack trace. Tests that do not die check that tokens can be moved and released
before their entry ends.

3 `forge/unittests/core/version_test.cpp` checks that `version()` begins with the contents of
`VERSION`, that it has a `+` and a build timestamp exactly when `FORGE_RELEASE` is 0, and that both
strings are null-terminated.

## Annex C (informative) Rationale [context.rationale]

### C.1 Prior art [context.rationale.prior]

| Project | Mechanism | Remarks |
|---|---|---|
| LLVM `PrettyStackTraceEntry` | RAII objects in a thread-local list; virtual `print(raw_ostream&)` runs during the crash; outermost first (`0. Program arguments: …`) | `PrettyStackTraceFormat` formats eagerly. Only the crashing thread is printed. On SIGINFO a generation counter makes each thread print its entries at its next push or pop. |
| GCC | The pass manager reports `during GIMPLE pass: vrp` automatically, along with `internal compiler error: in f, at file:line` | Followed by "Please submit a full bug report, with preprocessed source". |
| rustc | The query system prints a "query stack during panic" automatically | Its report includes the compiler version, commit and date, and a bug-report URL. |

### C.2 Departures from LLVM [context.rationale.llvm]

| This document | LLVM | Reason |
|---|---|---|
| Print functions write into a fixed-capacity `context_sink` and shall not allocate | `print(raw_ostream&)` may do anything | The failure may be the allocator's. |
| Tasks inherit their creator's chain ([context.inherit]) | Only the crashing thread | A failure on a worker thread still shows the whole context. |
| Lifetime checked in assertion builds | Not applicable | Makes the structured-concurrency rule enforceable. |
| Banner text per kind of failure | One banner | `FORGE_TODO` is a missing feature, not a bug. |
| Deferred live dump | Same | Copied: nothing runs in signal context. |
| Every thread answers dump requests made after its first entry | Threads opt in | No thread is left out of a dump by forgetting a call. |
| The node being constructed or destroyed is part of the dump | Left out, being half constructed | It is what the thread is starting or finishing; the base-from-member idiom makes it safe to print. |

### C.3 Relationship to later documents [context.rationale.future]

1 Entries are expected to come mostly from infrastructure, as in GCC and rustc: the driver for each
input, the pass manager for each pass and function. Those documents are expected to use
`context_entry` rather than adding a second mechanism.

2 Once forge has a source manager, an entry can print a location in the user's program, such as
`foo.c:12:3: while parsing this declaration`, through the same `context_sink`.
