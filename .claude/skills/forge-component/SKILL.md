---
name: forge-component
description: Add a new forge component (library) with its unit-test binary, or change which components depend on which. Use when creating a new library under forge/ such as lexer, preprocessor, sema or driver, or when an include fails the layering lint.
---

# Adding a forge component

A component is three directories plus two entries in `forge/premake5.lua`:

| What               | Where                                      |
| ------------------ | ------------------------------------------ |
| public headers     | `forge/include/forge/<name>/*.hpp`         |
| sources, private headers | `forge/source/forge/<name>/*.{cpp,hpp}` |
| GoogleTest tests   | `forge/unittests/<name>/*_test.cpp` → `forge_<name>_unittests` |
| graph              | `forge.component { "<name>", dependencies = {...} }` and `forge.test { "<name>", dependencies = { "<name>" } }` |

`premake/forge.lua` turns these into one static library per component (or one `libforge` with
`--shared`), works out link order, and rejects unknown dependencies and cycles. `./x lint`'s
`layering` stage enforces that a component includes only `forge/<dep>/` headers of its declared
dependency closure, that a test includes only its dependencies, and that public headers never
include private ones. So the graph in `forge/premake5.lua` is the architecture: decide it
deliberately.

## Steps

1. **Decide the dependencies.** List only direct ones; `core` is not implied. If the right
   layering is unclear (e.g. should `lexer` know about `diagnostics`?), ask the user and propose a
   graph; layering is hard to undo later.
2. **Scaffold** (`-n` first to preview):
   ```sh
   python3 .claude/skills/forge-component/scripts/new_component.py <name> --deps core[,other] [--header-only] [-n]
   ```
   It writes SPDX-headed stubs that already pass format, lint and clang-tidy, and appends both
   entries to `forge/premake5.lua`. `--header-only` skips the `.cpp`; such a component gets premake
   kind `None` and is never linked. If the script refuses (name taken, unknown dependency, cycle),
   fix the cause rather than editing around it.
3. **Write the code.** Namespace `forge` (no per-component namespace has been established; ask
   before introducing one). Exported functions of a component are `FORGE_API` so `--shared` works.
   Prefer one header per facility over a `<name>.hpp` catch-all; rename the stub if needed.
4. **Write at least one test** in `forge/unittests/<name>/`. A test binary with no `TEST` makes
   `./x test forge/unittests/<name>` fail with "filter did not match any tests".
5. **Verify**, in this order:
   ```sh
   ./x format forge/include/forge/<name> forge/source/forge/<name> forge/unittests/<name>
   ./x lint forge/include/forge/<name> forge/source/forge/<name> forge/unittests/<name>
   ./x test forge/unittests/<name>
   ./x build --shared            # the FORGE_API exports, in build-shared/
   ```
   In zsh, pass the paths literally: an unquoted `$PATHS` variable is one argument, not three.

## Changing the graph

- Add the dependency to the `forge.component` entry, not just the `#include`. The lint error
  names the entry to change.
- A cycle means the two components need a third one below them, or one of them should not exist
  separately. Propose the split to the user instead of merging components silently.
- Removing a component: delete the three directories and both entries, then `./x clean` the build
  directories you use (stale `forge_<name>.ninja` files remain otherwise).
