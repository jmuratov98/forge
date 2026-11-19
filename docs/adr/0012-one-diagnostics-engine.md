# One diagnostics engine, with definitions owned by each library

Every part of Forge that reports to the user (the frontends, the backend, the driver, fas, and fold) reports to one **diagnostics engine**. There is one engine per compilation and no global state. The engine decides each diagnostic's final severity from its warning group, the command line, and later the pragmas in effect at its location. It counts errors, applies the error limit, and stops everything after a fatal error. It then hands each diagnostic that survives, whole, to one **diagnostic consumer**: a text renderer, a SARIF writer, a language server, or the verify consumer that tests use. ADR 0008's "consumer interface" is this consumer, and producers reach it only through the engine, so no consumer reimplements `-Werror` or the error limit. The full design is in [docs/diagnostics.md](../diagnostics.md).

Each library defines its own diagnostics in its own table. The warning groups behind `-W` flags are one central table in `source`, because a group such as `all` spans libraries and every library already depends on `source`. The driver hands the engine the set of tables in the binary, just as it alone knows the list of targets. This keeps the C-family layer's vocabulary out of `source`, which the Forge language's frontend will use too. Every diagnostic has a stable name that is unique across Forge and serves as its SARIF `ruleId`, its key in tests, and its `--explain` topic.

A diagnostic is one value that carries its notes, its fix-its, and its labeled ranges, rather than a message followed by separate note diagnostics as in Clang. That shape maps directly onto SARIF's related locations and fixes, onto the language server's related information, and onto a Rust-style layout with labeled spans. Arguments have kinds declared in the definition and checked at compile time. Values from a frontend, such as C types, are opaque to the engine and are formatted by a hook the frontend registers, and only once the engine knows the diagnostic is not ignored. Message templates have their own syntax with choice and plural forms, defined here rather than borrowed from core's text formatting.

The default text output is laid out like Clang's, with 1-based byte columns, so that tools which parse Clang's output also parse Forge's. Frontend diagnostics are tested by a verify consumer that reads Clang-style `expected-error {{…}}` comments, not by matching rendered text.

## Considered options

- **Notes as separate diagnostics that follow their parent** (Clang): rejected. Suppression has to track the parent by position, and SARIF and the language server have to stitch notes back on.
- **One table of every diagnostic in `source`** (Clang's `Basic` holds every component's `.td` files): rejected. It puts C-family and linker vocabulary in the library at the bottom of the graph.
- **A build-time generator from the start**: deferred. X-macro tables with `constexpr` checks are enough until generated flag documentation or explanations need one. docs/layout.md already allows a generator.
- **Arguments formatted into strings by the producer**: rejected. Diagnostics that are off by default would still pay to format types, and C++ template diffing needs the types themselves.
- **Message templates in core's formatting syntax**: rejected. Diagnostics need `select` and `plural`, and their templates are table data read at run time, not format strings checked against call sites.
- **GCC's display columns in the header**: rejected for byte columns. They match Clang, cost nothing to compute, and MSBuild's GCC-style matcher accepts them. The caret line is still laid out by display width.
- **`ruleId` as the `-W` flag** (GCC) or as an MSVC number (MSVC): rejected. Errors have neither, and a flag names a group, not a diagnostic.
- **Matching rendered text with a FileCheck-style matcher**: rejected for frontend tests. Every layout change would break them, and they would wait on the IR pattern matcher. The renderers get a few golden-output tests of their own.
- **A Rust-style layout as the default**: rejected for drop-in compatibility (see the glossary). It is an opt-in format.

## Consequences

- Error recovery stays the frontends' job (ADR 0008). The engine adds only the error limit, `-Wfatal-errors`, and silence after a fatal error.
- Producers check whether the engine has stopped, since without exceptions (ADR 0003) a fatal error cannot unwind.
- Parallel phases inside one compilation buffer their diagnostics and hand them over in a fixed order, so output is deterministic (ADR 0005).
- A tool that explains other compilers' diagnostics is outside Forge. It could consume Forge's SARIF and `--explain` text.
