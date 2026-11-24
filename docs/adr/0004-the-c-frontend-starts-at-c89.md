# The C frontend starts at C89

Forge's C frontend implements C89 first. Later standards (C99 through C2y) are added on top of it, each one adding, deprecating or removing features, and the frontend takes a C dialect parameter (`-std=`) that selects which of them apply. Most new compilers start from C17, but C17 is mostly C11 plus defect fixes. Starting from ANSI C and walking the standards forward means each change is a deliberate step, rather than something reconstructed backwards from the newest standard.

The default C dialect is the newest GNU dialect Forge fully implements: `gnu89` first, then `gnu99`, `gnu11` and so on as each one is completed. The `c*` dialects, such as `-std=c89`, are strict ISO. What the `gnu*` dialects accept is defined by GCC, so `gnu89` accepts `//` comments and declarations mixed with code but, as in GCC, rejects `for (int i = …)`.
