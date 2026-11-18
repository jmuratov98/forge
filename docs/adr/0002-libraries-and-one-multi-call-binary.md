# Component libraries and one multi-call binary

Each component (the C frontend, the C++ frontend, the middle-end, fas, fold) is a library. They ship as one multi-call `forge` binary that picks its mode from the name it was invoked under, the way clang, clang++, and clang-cl do; `fas` and `fold`/`ld.fold` are names for that binary or thin standalone binaries over the same libraries. Compilation runs in-process and writes object files directly.

We considered the gcc model (a driver spawning `cc1`, `cc1plus`, `as`, and `ld` as separate processes). Its two attractions, keeping C and C++ errors apart and keeping C and C++ semantic analysis apart, come from the library boundary, not the process boundary. The process split costs a spawn per translation unit (slow on Windows), temporary files or pipes between stages, and a round trip through text assembly, all of which work against the compile-speed goal.
