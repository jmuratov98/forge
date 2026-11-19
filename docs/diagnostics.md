# Diagnostics

How Forge tells the user about their input: how diagnostics are defined, how their severity is decided, how they are rendered, and how they are tested. [ADR 0012](adr/0012-one-diagnostics-engine.md) records why it is shaped this way. [ADR 0006](adr/0006-failures-and-assertions.md) says every failure reaches the user as a diagnostic and core never emits one. [ADR 0008](adr/0008-split-frontends-over-a-shared-c-family-layer.md) says frontends never write to stdout or stderr. The engine lives in `source` ([layout.md](layout.md)). Source locations and debug locations are described in [source.md](source.md); here a location is an opaque value. How the flags below are spelled on each command line belongs to the driver's options model.

## Pipeline

```
 producers: frontends, backend, driver, fas, fold
        │  report(id, position, args…) + notes, fix-its, labels
        ▼
 diagnostics engine     one per compilation; severity mapping,
        │               error count and limit, fatal, formatting
        ▼
 diagnostic consumer    GNU text │ MSVC text │ forge text │ SARIF
                        │ verify │ language server │ …
```

- The engine is created by whoever runs the compilation, usually the driver. It holds no global state and is not shared between threads.
- The engine receives the set of definition tables in the binary, and the formatters for opaque arguments, when it is created.
- The consumer is an abstract class with virtual functions. It receives each finished diagnostic whole, and is told when each translation unit begins and ends.

## Definitions

Each library that reports diagnostics defines them in its own X-macro file, `diagnostics.inc.hpp`, next to its sources. A build-time generator may replace these files later ([layout.md](layout.md)). `constexpr` checks reject duplicate names, unknown groups, and templates that don't match their arguments.

| Field            | Meaning                                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| name             | Stable kebab-case name, unique across Forge: `expected-semicolon`. SARIF `ruleId`, verify key, `--explain` topic |
| default severity | note, remark, warning, error, or fatal. A warning may be off by default                                   |
| group            | Exactly one warning group for every warning and remark, including a warning that is an error by default. None for errors, notes, and fatals |
| arguments        | The kind of each argument (see below)                                                                     |
| template         | The message, in the syntax below                                                                          |
| MSVC number      | Optional, warnings only: the number and level that `/wd`, `/we`, `/W0`–`/W4`, and `#pragma warning` act on (M6) |
| explanation      | Optional longer text for `--explain`                                                                      |

An illustrative entry (the macro's exact shape is the implementer's choice):

```cpp
FORGE_DIAGNOSTIC(unused_variable, "unused-variable", warning, unused_variable,
                 (name), "unused variable '{0}'")
```

### Warning groups

Groups are one table in `source`. A group has a name, which is its flag (`unused-variable` is `-Wunused-variable`), and the groups it contains. `all` contains `unused`, which contains `unused-variable`. A flag acts on every diagnostic in its group's subtree. Remark groups are flagged with `-R`.

### Severities

| Severity | Meaning                                                                                       |
| -------- | --------------------------------------------------------------------------------------------- |
| ignored  | The result of mapping only. Never emitted                                                     |
| note     | Belongs to another diagnostic. Never reported on its own                                      |
| remark   | Opt-in information, such as optimization remarks (`-Rpass`)                                   |
| warning  |                                                                                               |
| error    | Fails the compilation                                                                         |
| fatal    | Fails the compilation and silences every later diagnostic                                     |

## What a diagnostic carries

- **Position**: a source location, a **debug location** (a file, line, and column from Billet or below, so the backend can report without a source manager; the renderer shows the source line only if the current translation unit has that file loaded), an **input** (a path, or an object or archive member, such as `missing.c` or `main.o`), or nothing (`no input files`).
- **Ranges**: highlighted source ranges, one of which may be primary. Each range may carry a short **label** ("expected 'int', found 'char *'"). The GNU and MSVC renderers ignore labels; the forge renderer and SARIF show them.
- **Notes**: each with its own position, message, ranges, and fix-its. Notes are suppressed with their diagnostic.
- **Fix-its**: replace a source range with text. An insertion is an empty range and a removal is empty text. The engine drops a fix-it that is not one edit to one file's spelled text, such as one inside a macro expansion.

## Arguments and messages

An argument's kind is one of:

| Kind      | Rendered as                                                                     |
| --------- | ------------------------------------------------------------------------------- |
| integer   | Decimal                                                                         |
| string    | As given                                                                        |
| name      | An identifier or other name, as given                                           |
| range     | Nothing in the message; adds a highlighted range                                |
| opaque    | A value with a kind tag, rendered by the formatter its producer registered: a C type, later a C++ type with template diffing, a Billet value |

The `report` call is checked at compile time against the declared kinds. The engine maps the severity first and formats the message only if the diagnostic is not ignored.

Templates use positional arguments:

| Form                        | Meaning                                                  |
| --------------------------- | -------------------------------------------------------- |
| `{0}`                       | Argument 0, rendered for its kind                        |
| `{0:select:function\|variable}` | The alternative chosen by integer argument 0, from 0     |
| `{0:plural:argument\|arguments}` | The first form if integer argument 0 is 1, otherwise the second |
| `{{` `}}`                   | Literal braces                                           |

Messages are English only. They follow Clang's style: they start in lowercase, have no trailing period, and quote names with ASCII `'x'`, so that the text is the same on every host and in every locale.

## Severity

A diagnostic's final severity is a function of the diagnostic and its location:

1. Start from the definition's default severity.
2. Apply the command line's group flags in order. Each one sets every diagnostic in its group's subtree, so `-Wno-unused -Wunused-variable` leaves `unused-variable` on, and the reverse order turns it off.
   - `-W<group>` and `-Wno-<group>` turn a subtree on and off.
   - `-Werror=<group>` makes a subtree's warnings errors, and `-Wno-error=<group>` exempts it from `-Werror`.
3. Apply the pragmas in effect at the location, in source order (M2):
   - `#pragma GCC diagnostic`, `#pragma clang diagnostic`, and `#pragma forge diagnostic` are equivalent and share one grammar: `push`, `pop`, `ignored`, `warning`, and `error "-W<group>"`.
   - `#pragma warning(push | pop | disable: N | error: N | default: N)` acts on MSVC numbers.
4. Apply the global modifiers:
   - `-w` ignores everything that maps to a warning.
   - `-Werror` turns every warning into an error, except groups with `-Wno-error=`.
   - Warnings in system headers are ignored unless `-Wsystem-headers` is given (M2).
   - Remarks are never affected by `-w` or `-Werror`.

## Stopping

- **Fatal**: after a fatal error the engine silences every later diagnostic and reports that it has stopped. Producers check at natural points, for example the lexer returning end-of-file, so the compilation winds down without an unwind (ADR 0003).
- **Error limit**: with limit N, the engine shows N errors. The error that would be number N + 1 is replaced by `fatal error: too many errors emitted, stopping now`. The default is 20, and 0 means no limit.
- **`-Wfatal-errors`**: the first error becomes fatal.
- **Errors stop lowering**: once a phase ends with any error, nothing lowers past it. A translation unit with errors never reaches Ingot.
- The engine's error count, after `-Werror`, decides the driver's exit status.

## Renderers

Every renderer prefixes a diagnostic that has no position with the name Forge was invoked under, without its extension: `forge: error: no input files`, `fld: error: undefined symbol: _foo`.

### GNU text (default)

Laid out like Clang's:

```
t.c:3:13: error: expected ';' after return statement
    3 |     return x
      |             ^
      |             ;
t.c:5:22: error: call to undeclared function 'h'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
    5 | int g(void) { return h(1); }
      |                      ^
2 errors generated.
```

- The header is `file:line:col: severity: message`, followed by `[-W<group>]` for a warning or a warning that is an error by default (as above), or `[-Werror,-W<group>]` for a warning the user made an error.
- Columns are 1-based **bytes**. A tab counts as one.
- The caret line is laid out by display width, with tabs expanded to 8. `~` underlines ranges, and any fix-it insertion goes on the line below.
- Notes follow their diagnostic in the same layout.
- From M2: "In file included from" stacks and "expanded from macro" backtraces.
- At the end of each translation unit: `N warnings and M errors generated.`, with singular forms, omitted when both are zero.
- Color only when the driver says the output is a terminal or the user asks for it. The renderer never asks the OS.

### MSVC text (M6)

What `forge-cl` uses, laid out like clang-cl's: `t.c(3,13): error: expected ';' after return statement`. A warning with an MSVC number shows it: `warning C4996: …`. MSBuild parses both forms. The caret line follows `/diagnostics:caret`.

### forge text (unscheduled, opt-in)

A Rust-style layout with labeled spans, never the default:

```
error[int-conversion]: incompatible pointer to integer conversion
 --> t.c:4:13
  |
4 |     int n = p;
  |     ---     ^ expected 'int', found 'char *'
  |     |
  |     expected because of this type
  = help: for more information, try 'forge --explain int-conversion'
```

### SARIF (unscheduled)

SARIF 2.1.0. `ruleId` is the diagnostic's name, and the group's flag goes in the rule's `properties`. Notes and labeled ranges go in `relatedLocations`, fix-its in `fixes`. `columnKind` is `unicodeCodePoints`. It needs a JSON writer in core.

## `--explain`

`forge --explain <name>` prints a diagnostic's explanation: what it means and how to fix it. Unscheduled.

## Testing

Frontend diagnostics are tested by the **verify consumer**, which checks diagnostics against comments in the source instead of rendering them. It reads the comments through the lexer's comment capture. The syntax is a subset of Clang's `-verify`:

```c
int f(void) {
    int unused; // expected-warning {{unused variable 'unused'}}
    // expected-note@+1 {{previous definition is here}}
    int x = 1;
    int x = 2;  // expected-error {{redefinition of 'x'}}
    return x    // expected-error {{expected ';' after return statement}}
}
```

- `expected-error`, `-warning`, `-note`, and `-remark`, optionally with `-re`, which makes each inner `{{…}}` a regular expression.
- `@+N`, `@-N`, and `@N` place the expectation on another line.
- `-verify=<prefix>` replaces `expected`.
- `expected-no-diagnostics` asserts none.
- Text is a substring match. Any unexpected or missing diagnostic fails the test.

The renderers have a few golden-output tests of their own ([testing.md](testing.md)).

## Threads and order

One engine serves one compilation on one thread. A phase that runs in parallel inside a compilation, such as per-function code generation, buffers each worker's diagnostics and hands them to the engine in function order. The same input gives the same diagnostics in the same order on every run and every host (ADR 0005).

## Milestones

| Milestone   | Adds                                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------------------------ |
| M1          | The engine and the consumer interface; per-library tables and the group table; all severities; notes, fix-its, and labels; argument kinds, the C frontend's type formatter, and templates; fatal errors, the error limit, and `-Wfatal-errors`; `-w`, `-W`, `-Wno-`, `-Werror`, `-Werror=`, `-Wno-error=`; the GNU renderer with color and the summary; the verify consumer |
| M2          | Pragmas, system-header suppression, include stacks, and macro backtraces                                     |
| M5          | Remarks from the optimizer; buffering for parallel code generation                                           |
| M6          | The MSVC renderer and MSVC numbers                                                                           |
| Unscheduled | SARIF, the forge renderer, `--explain`                                                                       |
