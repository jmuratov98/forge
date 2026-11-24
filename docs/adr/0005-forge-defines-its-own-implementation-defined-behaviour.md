# Forge defines its own implementation-defined behaviour

Forge follows a target's ABI wherever the ABI fixes an implementation-defined choice, such as type sizes, the signedness of plain `char`, alignment and the calling convention, because objects have to link with the platform's libraries. Every other implementation-defined choice is Forge's own and is documented by Forge. These include how `>>` treats negative values, out-of-range signed conversions, the rounding of `/` and `%` in C89, and identifier significance. Forge doesn't copy clang or GCC on these, so its behaviour on a free choice can legitimately differ from theirs.

This covers implementation-defined behaviour, not which language a C dialect accepts: GCC defines what the `gnu*` dialects accept (ADR 0004), while Forge makes its own documented choices in every dialect.
