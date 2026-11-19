# What a Billet module holds

A Billet module is one translation unit's functions, globals, aliases, and ifuncs, plus the module-level tables they refer to. Its header makes it self-contained. It states the target triple, the resolved data layout, a baseline CPU and feature set, and the code generation settings that change what correct output is: the relocation model, the code model, and the frame-pointer policy. A `.billet` file therefore compiles the same way whatever command line reads it. There is no open "module flags" bag, for the same reason ADR 0011 rejected generic metadata. Pipeline settings such as the `-O` level stay out of the module. The full inventory is in [docs/billet.md](../billet.md#modules).

A global's initializer is a **byte image plus relocations**, not a tree of typed constant expressions. Ingot has already resolved every offset and byte order, and an object file holds exactly this: bytes, and relocations at offsets. Each relocation has an offset, a width, and a target, which is `@sym + addend` or a block address, optionally minus a second symbol. The optimizer folds a load from a constant global by reading bytes and checking that no relocation overlaps them, and float bytes were already produced by core's software floating point (ADR 0005).

Whether an access to a symbol goes through the GOT is not stored on the symbol. Symbols carry linkage, visibility, DLL storage, and `unnamed_addr`. One helper in `billet` computes whether a symbol is resolved within the linkage unit from those fields, the relocation model, and the module's semantic-interposition setting, and both lowering and the optimizer ask it. This is ADR 0007's argument about calling conventions again: a decision every frontend would otherwise repeat lives in one place that can be tested.

The address of a thread-local variable is taken with its own instruction, `tls.addr`, never with `symbol.addr`. `symbol.addr` is a link-time constant that may be hoisted anywhere. A thread-local address depends on the current thread, and stops being valid when a coroutine resumes on another thread.

## Considered options

- **Data layout only, with the triple and CPU supplied at lowering**: rejected. A single pass couldn't be tested from a file alone. The verifier also couldn't reject a target intrinsic the module's ISA lacks, and Mach-O's `.build_version` needs the OS version from the triple.
- **LLVM's module flags**: rejected. An open bag can't be verified, and passes would drop entries they don't understand.
- **LLVM's typed constant expressions** for initializers: rejected. They are a second expression language beside instructions, LLVM has been removing most of them since LLVM 15, and Ingot has already computed everything they would express.
- **A `dso_local` flag set by each frontend**, as Clang does: rejected. Every frontend would reimplement the interposition rules for `-fPIC`, `-fPIE`, visibility, and `-fno-semantic-interposition`.
- **`symbol.addr` on thread-locals**: rejected. LLVM had to add `llvm.threadlocal.address` after optimizations broke coroutines that resume on another thread.
- **Linkage as separate axes** (binding × ODR × discardable): rejected in favor of one enum. Separate axes allow combinations that make no sense.
- **A string-literal kind of global**: rejected. Lowering infers mergeable C strings from a global's properties.
- **Requiring a direct call's signature to match the callee's declaration**: rejected. A C call through an unprototyped declaration would become an indirect call that the optimizer has to turn back into a direct one.

## Consequences

- The Billet → Blank lowering maps linkage, visibility, COMDAT, sections, TLS models, and constructor tables onto each object format. docs/billet.md records that mapping once.
- How a triple produces a data layout is decided with the target description. The module just prints the resolved layout.
- Left for later, and each can be added without breaking anything: `common` and `available_externally` linkage, attributes the optimizer infers, stack-protector levels, the personality function, and debug-info tables beyond line tables.
