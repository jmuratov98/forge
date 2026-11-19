# Source

How Forge reads its input and keeps track of where everything came from: the file-system interface, the file manager, the source manager, and the locations that point into them. [ADR 0013](adr/0013-source-location-interface-before-encoding.md) records why the interface is fixed and the encoding is not. [ADR 0008](adr/0008-split-frontends-over-a-shared-c-family-layer.md) requires precise locations and a file-system interface that can supply unsaved buffers. [ADR 0007](adr/0007-ir-layers-and-their-boundaries.md) requires a location on every node in every layer. All of this lives in `source` ([layout.md](layout.md)), next to the diagnostics engine ([diagnostics.md](diagnostics.md)).

```
 file-system interface    real disk │ in memory │ overlay
        ▼
 file manager             files by OS identity, with their buffers;
        │                 may be shared by several translation units
        ▼
 source manager           one per translation unit; inclusions,
        │                 expansions, and the locations into them
        ▼
 source_location / source_range    frontends, C-family layer, fas, Ingot
        │  Ingot → Billet
        ▼
 debug location                    Billet, Blank, Stamp
```

## File-system interface

Every file Forge reads goes through one abstract class, with virtual functions, in `source`. That includes the frontends, the preprocessor, fas, fold, and the driver when it classifies its inputs. The interface can:

- look up a path's status and its OS identity (the device and inode, or the Windows file index);
- read a whole file;
- list a directory, for header maps and frameworks later.

`source` provides three implementations:

| Implementation | Behind it                                                                  | Arrives            |
| -------------- | -------------------------------------------------------------------------- | ------------------ |
| real           | The host's files, through core's platform layer                            | M1                 |
| in memory      | Files held in memory, for tests                                            | M1                 |
| overlay        | In-memory buffers laid over another file system: a language server's unsaved files | With a language server |

## File manager

The file manager caches files by OS identity, so two paths to one file give one entry. That identity is what `#pragma once` and include-guard detection key on (M2). Each file is read whole into a buffer the file manager owns, followed by NUL padding, so the lexer can scan without bounds checks. There is no mmap; it can come later behind the same interface if measurements ask for it.

Several source managers can share one file manager, as in `forge a.c b.c` or a language server. Neither one is shared between threads while in use.

## Source manager

There is one source manager per translation unit. It records:

- **Inclusions**: one for the main file and one for each `#include`. A header included twice is two inclusions of one file. Each one records its file and the location of the `#include` that entered it, and from M2 whether it is a user header, a system header (from `-isystem`, or line-marker flag 3), or an implicitly `extern "C"` system header (flag 4).
- **Expansions** (M2): one for each macro use, and one for each token made by `##` or `#`. Each records the range of the macro use and where each token it produced was spelled.
- **Line directives** (M2): each inclusion's `#line` directives and GNU line markers (`# 1 "foo.h" 1 3`).

The diagnostics engine resolves locations against the source manager of the translation unit in progress.

### Locations and ranges

`source_location` is a point and `source_range` is a half-open range `[begin, end)` of characters, where `end` is one past the last character. Both are opaque value types. They are cheap to copy and can be compared only for equality. Each has an invalid value. A location takes at most 8 bytes and a range at most 16.

Only the source manager makes locations: from an inclusion and a byte offset (the lexer), or from an expansion the preprocessor records. Every question about a location is a source-manager query:

| Query                    | Answer                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| spelling position        | The file, line, and column where the text physically is                                         |
| presumed position        | The file and line after `#line` and line markers, with the spelling column                       |
| buffer and offset        | The file's buffer and the byte offset into it, for fix-its and the language server              |
| include stack            | The location of the `#include` that entered this inclusion, and so on out to the main file       |
| expansion chain          | For each expansion the text came through, innermost first: where it was spelled and the range of the macro use |
| order                    | Whether one location comes before another in the translation unit                               |
| text                     | The source text of a range                                                                       |

Locations from different inclusions or expansions can't be ordered by comparing values; ordering is a query.

Diagnostics, `__FILE__`, `__LINE__`, and debug locations use the presumed position. Fix-its and the language server use the spelling position.

AST nodes carry a begin and an end range, and expressions also carry a caret location (ADR 0008). The parser gets each `end` from the length of the last token, so neither the renderers nor the language server re-lex to draw a range.

### Lines and columns

Each file's table of line starts is built the first time anything asks for a line or column in it. LF, CRLF, and a lone CR each count as one line break, so a file with CRLF line endings has the same lines and columns as its LF copy. Lines and columns are 1-based, and columns count bytes ([diagnostics.md](diagnostics.md#gnu-text-default)).

### Encoding

How a location is encoded is open. M1 has one inclusion and no expansions, and encodes a location as a 32-bit inclusion index and a 32-bit byte offset. The encoding the preprocessor needs is chosen by a research effort before M2, which prototypes GCC's line maps, rustc's spans, and new designs behind this interface and measures them on Lua and SQLite translation units against the size budget.

## Below the AST

| Layer                   | Carries            |
| ----------------------- | ------------------ |
| AST, Ingot              | `source_location`  |
| Billet, Blank, Stamp    | debug location     |

Ingot → Billet converts each source location to a **debug location**: a file, a line, and a column, with an inlining scope to come ([billet.md](billet.md#data-on-instructions)). It takes the outermost expansion's location (the macro use the user wrote, which is what a debugger steps through), then that location's presumed position. The file is an index into the Billet module's file table ([What does a Billet module contain?](https://github.com/jmuratov98/forge/issues/27)). Billet → Blank and Blank → Stamp copy debug locations through.

In Stamp:

- Every instruction carries a debug location. The compiler sets it from Blank. fas's `.file` and `.loc` directives set it on the instructions that follow, so compiled code and hand-written assembly carry line information the same way.
- The text printer writes `.file` and `.loc` only under `-g`, and only where the debug location changes.
- When fas parses assembly, each fixup and directive also gets a source location in the `.s` file, so errors found after parsing, such as a fixup out of range during layout, point at the line that caused them. Compiled code leaves this empty.

A diagnostic's position can be a debug location, so the backend reports without a source manager ([diagnostics.md](diagnostics.md#what-a-diagnostic-carries)). How an inline-asm error points back into its C string literal is decided with inline asm.

## Testing

googletest covers the file manager and the source manager over the in-memory file system. Everything a frontend reports is covered by its verify tests ([diagnostics.md](diagnostics.md#testing)).

## Milestones

| Milestone              | Adds                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| M1                     | The real and in-memory file systems; the file manager; the source manager with the whole query interface over one inclusion and no expansions, where the presumed position is the spelling position; the M1 encoding; half-open ranges and lazy line tables; source locations through the AST and Ingot and debug locations through Billet, Blank, and Stamp, with no `.file` or `.loc` printed |
| Before M2              | The encoding, chosen by its own research effort                                                              |
| M2                     | Inclusions for `#include`, expansions, `#line` and line markers, system-header status, and `.file` and `.loc` under `-g` |
| M3                     | Source locations on fas's fixups and directives                                                              |
| With a language server | The overlay file system                                                                                      |
