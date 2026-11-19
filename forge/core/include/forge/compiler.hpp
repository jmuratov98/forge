#pragma once

// Wrappers that hide where the host compilers differ, so Forge's source can use
// a feature every supported compiler has in some spelling (docs/style.md).

// [[no_unique_address]]: an empty member takes no space. MSVC accepts the
// standard spelling but ignores it, for ABI compatibility, and honors only its
// own.
#if defined(_MSC_VER)
#define FORGE_NO_UNIQUE_ADDRESS [[msvc::no_unique_address]]
#else
#define FORGE_NO_UNIQUE_ADDRESS [[no_unique_address]]
#endif
