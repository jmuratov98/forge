# The driver plans jobs and runs fcc1 in-process or as a subprocess

`forge` is a driver, not the compiler itself. It classifies each input by extension or `-x`, builds a graph of phases per input (preprocess, compile, assemble, link), turns that graph into concrete jobs before anything runs, and runs the jobs in order. The compiler proper is a separate program, fcc1. With `-fintegrated-cc1`, the default, the compile job calls fcc1's entry point inside `forge`. With `-fno-integrated-cc1`, it spawns the fcc1 binary. Both modes run the same library code with the same arguments, so they can't drift apart. The driver follows clang's model because one binary serves every target, and it keeps the option of process isolation that clang gets from `-cc1`.

## Considered Options

- **One process with no internal command line.** This is simpler for the slice, but every later tool boundary (fas, fold, other frontends) would have to be added to a driver that has no notion of jobs, and there would be no way to run the compiler on its own under a debugger or a crash handler.
- **Clang's `forge -cc1` re-exec.** This was rejected in favour of a separately named binary, as in GCC. `fcc1` can't be confused with GCC's `cc1`, and the driver's public flags stay apart from the internal ones.

## Consequences

- fcc1's command line is internal and unstable. The driver resolves every default (target, `-std=`, predefines, `-O` level) into explicit flags, and fcc1 defaults nothing. Tests and users go through `forge`, including for the `-dump-*` and `-emit-*` flags.
- `-v` and `-###` print an in-process fcc1 job as the command line it is equivalent to, so their output is the same in both modes.
- fcc1 is found the way GCC finds `cc1`: in `<prefix>/libexec/forge/<core version>/fcc1`, where `<prefix>` comes from `argv[0]` (searched on PATH, symlinks resolved), with `-B<dir>` and `FORGE_EXEC_PREFIX` taking precedence. `-B` is searched for fcc1 only, never for the assembler.
- Assembling follows clang's model. `-fintegrated-as` will run fas in-process. `-fno-integrated-as` spawns an assembler: the host assembler until fas exists (ADR 0007), then the fas binary. Once fas exists the default flips to `-fintegrated-as`, and with no assembler override flag, the host assembler is no longer used.
