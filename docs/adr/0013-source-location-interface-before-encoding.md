# Source locations: a locked interface over an open encoding

Forge fixes how the rest of the toolchain uses a source location, and deliberately leaves open how one is encoded. `source_location`, a point, and `source_range`, a half-open range of characters, are opaque value types. They are cheap to copy and can be compared only for equality. Only the source manager can make one, and only the source manager can answer questions about one: its spelling and presumed positions, its file buffer and byte offset, its include stack, its expansion chain, whether it comes before another location in the translation unit, and the text of a range. A location may take at most 8 bytes and a range at most 16. Since nothing outside `source` sees the representation, the encoding can be replaced without touching any other library. M1 has no preprocessor, so its encoding is the simplest one that meets the interface: a 32-bit inclusion index and a 32-bit byte offset. The encoding the preprocessor needs is chosen by a research effort of its own before M2. The full design is in [docs/source.md](../source.md).

Below the AST there are two kinds of location. Ingot carries source locations, because it is built and freed one function at a time while the source manager is still alive. Ingot → Billet turns each one into a **debug location** (a file, a line, and a column), using the presumed position of the outermost expansion. Billet, Blank, and Stamp carry only debug locations. They therefore never depend on a source manager, the Billet text format round-trips, and a module can outlive its translation unit.

## Considered options

- **Clang's single location space** (one 32-bit offset per location into a space split among every inclusion and expansion, found by binary search): not chosen now. It is the smallest encoding, but it caps a translation unit at 2 GiB of inclusions and expansions, and it hides the structure of a location behind a search.
- **An entry index and an offset in 64 bits** (no shared space; byte offsets in inclusions, token indices in expansions): not chosen now. It fits the budget and needs no search, but costs twice Clang's memory per location.
- **GCC's line maps** (line and column packed into a `location_t`, widened to 64 bits in GCC 15) and **rustc's spans** (a range plus a syntax context, 8 bytes, interned when they don't fit): the models the author leans toward. Neither carries over to C unchanged. rustc has no `#include`, and a C translation unit's macro expansions overflow a 16-bit context.
- **Token indices in the AST** (Zig, Carbon): rejected. Every token would have to be kept, while ADR 0008 says a plain compile pays for no token buffer.
- **Choosing the encoding now**: rejected. M1 cannot tell the options apart, since without a preprocessor every encoding is a file and an offset. The choice would rest on guesses that measurements on Lua and SQLite can settle before M2.
- **One kind of location in every layer**: rejected. Billet would depend on the source manager that produced it, and its text format could not round-trip.

## Consequences

- Locations from different inclusions or expansions can't be ordered by comparing values; ordering is a source-manager query.
- The research effort is bounded by this interface and by the size budget. An encoding that needs more than the interface offers reopens this ADR.
- Diagnostics can be positioned by a debug location too, so the backend can report without a source manager ([docs/diagnostics.md](../diagnostics.md)).
- How an inline-asm error points back into its C string literal is decided with inline asm. It needs a route from Billet back to a source location, and Billet has no generic metadata (ADR 0011).
