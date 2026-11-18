# Forge's output is byte-identical across hosts

Given identical logical source inputs, transitive dependencies, compiler version, configuration, command-line options, target triple, target features, and ABI, Forge shall produce byte-identical object files regardless of the host operating system, host architecture (where supported), or host compiler used to build Forge.

This is stronger than the stage-2/stage-3 comparison, which only needs the same output on one host.

## Consequences

- No `float` or `double` outside core's software floating point and its timing utilities. Target floating point is folded in software and float literals are parsed by core: host libms, `strtod`, and floating-point contraction differ between hosts and host compilers.
- Nothing that reaches the output depends on hash-container iteration order, pointer values, or where an unstable sort leaves equal elements. core's hash containers and sort must be designed for this, which is one reason Forge does not use the standard library's (ADR 0004).
- A value whose width can reach the output does not use `long`, which is 32-bit on Windows and 64-bit elsewhere. Fixed-width types are preferred everywhere.
- `<cctype>`, `<clocale>`, and `<cmath>` are never used on a path that affects output: the first two depend on the locale, the last on the host libm.
