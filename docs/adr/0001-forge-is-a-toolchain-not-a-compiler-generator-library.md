# Forge is a toolchain, not a compiler-generator library

Forge started out as a library for generating compilers. We dropped that goal: Forge is a concrete toolchain for C, C++ and the Forge Language. Its internal layers (frontends, IRs, backends) are still separate libraries linked into the tools, but they promise no public or stable API. A generator library would push every layer toward generic, table-driven designs and API stability, which costs more design than a learning project can justify and slows the path to a working compiler.
