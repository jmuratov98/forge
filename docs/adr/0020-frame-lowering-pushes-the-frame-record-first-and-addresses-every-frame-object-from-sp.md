# Frame lowering pushes the frame record first and addresses every frame object from sp

The slice's frame lowering builds one frame shape. A function that contains a `bl` pushes its frame record first with `stp x29, x30, [sp, #-16]!`, points `x29` at it, and then lowers `sp` by the rest of the frame in one or two `sub`s. The epilogue undoes this before every `ret`. The rest of the frame is the spill slots, placed upward from the outgoing argument area at `sp` in frame-index order and padded to 16 at the top. Every frame object, including the caller's incoming area, is addressed from `sp`, never from `x29`. A leaf function, one with no `bl`, keeps no frame record and lowers `sp` only for its spill slots. Pushing first means the frame record's store can be encoded whatever the size of the frame. So there is one shape, with clang `-O0`'s instruction count (three in, three out) and two fewer when nothing lies below the record. MIR's `ldp_ui` and `stp_ui` were used only for the frame record, so they become `stp_pre` and `ldp_post`, and ADR 0016's count of 37 opcodes holds. An `sp` offset beyond its form's reach is split into an `add` of its multiple of 4096 and a small remainder, through the load's own destination or a free scratch register (ADR 0019).

## Considered Options

- **Clang `-O0`'s folded shape:** `sub sp, sp, #N`, `stp x29, x30, [sp, #N−16]`, `add x29, sp, #N−16`. It is what clang emits for small frames at `-O0`, and what `docs/mir.md` first showed. But `stp`'s offset reaches only 504, so frames over 520 bytes need a second shape, and that second shape is clang's push-first one anyway.
- **Pushing first with no new opcodes:** `sub sp, sp, #16`, `stp x29, x30, [sp]`, and so on. It keeps one shape and leaves MIR's opcodes unchanged, but costs two extra instructions in every function that makes a call.
- **The frame record at the bottom of the frame**, next to the outgoing area, as GCC places it. Apple's convention, and compact unwind later, expect the record at the top with the saved registers below it.
- **Addressing frame objects from `x29`**, as clang `-O0` does with `ldur w0, [x29, #-4]` for locals and `[x29, #16]` for incoming arguments. It needs negative offsets (`ldur`, `stur`), which MIR doesn't have, and a leaf has no `x29`.
- **The red zone for a leaf's spill slots.** Apple preserves 128 bytes below `sp`, but they too need negative offsets, and clang doesn't use them.

## Consequences

- Spill slots sit as close to `sp` as the outgoing area allows, and the slots that register allocation makes before its walk come first, every block parameter's included. That matters for the one store ADR 0019 leaves without a free register: `str w17` inside a parallel-move cycle, while `x16` holds the saved value. If that slot lies beyond 16,380 bytes from `sp`, which takes a call with about 4,000 arguments or about 4,000 values that cross blocks, it is a limit in Forge stopped by `FORGE_ASSERT` (ADR 0009). So is a frame of 16 MiB or more.
- An allocator that uses callee-saved registers will push its first pair before the frame record and store the record above it, as clang does, which changes the prologue's first instruction.
- There are no stack probes. Clang on Darwin calls `___chkstk_darwin` before it lowers `sp` by 4096 bytes or more, and Forge's frames reach that size only around the sizes above.
- The prologue and the epilogue are fixed patterns, so the `final` verifier checks them as such ([docs/mir.md](../mir.md#verifier)).
