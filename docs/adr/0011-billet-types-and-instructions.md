# Billet's types and instructions

Billet's types are signless integers `iN`, IEEE and x87 floats, one opaque `ptr`, fixed-length vectors, and aggregates. Aggregates are **not SSA values**. An aggregate type is a layout (size, alignment, and fields at byte offsets) that describes a piece of memory. Calls take aggregates as by-value operands that name the type and an address, and calling-convention lowering decides whether each one travels in registers, on the stack, or behind a hidden pointer. Undefined behavior is modeled with **poison** only, with no `undef`. Instructions have **no generic metadata**: everything attached to an instruction is a field Billet itself defines. Billet may contain **target intrinsics**, which amends ADR 0007's rule that Billet depends on the target only through its data layout. The full inventory is in [docs/billet.md](../billet.md).

Aggregates live in memory because that is where every C and C++ aggregate already lives, and because first-class aggregate values give the optimizer and instruction selection a second way to do everything memory already does. LLVM allows them, advises against using them, and generates poor code for them. A layout is all calling-convention lowering needs. AAPCS64's HFA rule, SysV's eightbyte classification, and RISC-V's struct flattening all read field types at offsets, so the layout keeps them, with overlapping fields for unions and storage-unit integers for bitfields. It also keeps a `complex` marker, because SysV passes `_Complex long double` differently from a struct of two `long double`s.

Poison without `undef` gives C's signed-overflow and shift rules to the M5 optimizer in the form LLVM settled on after a decade of `undef` bugs. Fixed fields instead of open-ended metadata let the verifier check everything an instruction carries, and mean no pass can drop information it doesn't understand.

## Considered options

- **First-class aggregate values** (`extractvalue`, `insertvalue`, aggregate loads and block parameters): rejected for the reasons above.
- **Aggregate types reduced to size and alignment**: rejected. Arguments can't be classified from those two alone on AAPCS64, SysV, or RISC-V.
- **`undef` alongside poison**: rejected. `undef` can take a different value at each use, which makes many intuitive rewrites unsound.
- **Cranelift's trapping semantics** for division and out-of-range conversions: rejected. They don't match C, which treats these as undefined, and they cost a check the optimizer can't remove.
- **LLVM-style generic metadata**: rejected. Source locations, alias classes, flags, alignment, and atomic ordering are all fixed fields.
- **No target intrinsics**, with `arm_neon.h` and `<immintrin.h>` built only from generic vector operations and inline asm: rejected. Some of their operations (AES rounds, dot products, table lookups) have no generic form, and inline asm hides them from instruction selection and scheduling.
- **Typed pointers** and **no pointer type** (pointers as plain integers, as in Cranelift): rejected. Typed pointers add casts without adding information. Without a pointer type, the data layout and alias analysis can't tell which values are addresses.
- **LLVM's typed GEP**: rejected. Ingot has already resolved every offset, so `ptr.add` with a byte offset is enough.

## Consequences

- A module that uses a target intrinsic can be compiled only for a target with that ISA. Each ISA library registers its intrinsics with `billet` through an interface, so `billet` still never names a target (docs/layout.md).
- Every call carries what calling-convention lowering needs and could not recover later: the full signature, the number of fixed parameters (which decides correctness for Apple arm64 variadics), per-parameter extension flags, and a convention selector.
- Frontends build alias classes, because strict aliasing is a language rule. Ingot carries them without reading them.
- Left for later, and each can be added without breaking anything: the alias tree's contents and scoped noalias (M5), strict FP and `FENV_ACCESS`, scalable vectors, guaranteed tail calls, and multiple return values for functions.
