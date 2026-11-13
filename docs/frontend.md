# Frontends, dialects and the C-family core

Status: draft, 2026-11-13. Stable-name prefix: `[front]`.

## 1 Scope [front.scope]

1 This document specifies how Forge's C and C++ frontends are built and share code, how a dialect is selected and resolved, the order in which language revisions land, the default dialects, and the AST. The forge language's frontend, Objective-C and Objective-C++ are out of scope ([roadmap.scope.out]).

## 2 Shape [front.shape]

1 Each language shall have its own *frontend*, as in GCC. The lexer and preprocessor are one library. Above it, C and C++ each have their own parser, AST, sema and AST → HIR emitter.

2 `fcc1` shall link only the C frontend, and `fcc1plus` only the C++ frontend. Milestone 1 builds only the C side and needs nothing from the C++ frontend.

3 The preprocessor shall be integrated. The parser pulls tokens from it, and pragmas that affect parsing or sema reach the parser as tokens in the stream. `-E` runs in the compiler executable ([pipe.driver]).

4 The lexer shall have a raw lexing mode that keeps comments and whitespace and skips preprocessing, so the formatter can use the lexer alone.

5 The preprocessor reads the same feature table as the frontends, for its C++-only tokens, digit separators and version macros ([front.dialects]).

## 3 The C-family core [front.core]

1 Both frontends shall build on one library above the preprocessor, the *C-family core*. It holds:

- (1.1) the feature table ([front.dialects]) and the keyword sets;
- (1.2) the builtin, attribute and pragma tables. These also answer `__has_builtin`, `__has_attribute` and the other `__has_*` queries, so the answers can never drift from what is implemented, and headers take their fallbacks for anything missing;
- (1.3) one type system with C record layout, including bitfields, `packed`, `aligned` and `#pragma pack`;
- (1.4) constant arithmetic, built on Forge's software arithmetic;
- (1.5) format-string checking (`-Wformat`);
- (1.6) the one conversion from frontend types to HIR type descriptions.

2 The type system is shared because C and C++ must lay out the same struct identically, and because builtin signatures, `-Wformat` and the HIR type description all need C-level types, such as `long` as distinct from `long long`, and typedef names like `size_t`. The C++ frontend adds the kinds it needs (references, classes, member pointers, dependent types) and puts Itanium layout (bases, vptr, tail-padding reuse) on top of the core's C layout.

3 Anything that can live in the core shall go there. The accepted cost of separate frontends is duplicated sema work:

- (3.1) C23 features that came from C++ are written in each sema: `auto`, `constexpr`, `nullptr`, `typeof`, `[[attributes]]` and `static_assert`;
- (3.2) so are the C features that the C++ frontend accepts as GNU extensions, such as variable-length arrays, designated initializers, compound literals and `_Complex`. [compat.extensions] lists which ones.

## 4 Constant evaluation [front.consteval]

1 Each frontend shall have its own constant evaluator, over the shared arithmetic. C's evaluator covers integer constant expressions, address constants in static initializers, and C23 `constexpr` objects. C++'s evaluator stays in the fog ([roadmap.fog]).

## 5 Dialects [front.dialects]

1 A *dialect* is a language, a revision and a GNU-mode flag, as `-std=` selects them. It shall be resolved once into a *feature table* of named features. For example, `implicit_int` is on in C89 only, and `bool_keyword` is on in C23 and all of C++.

2 Code shall check features by name, never "is this C++" or a revision number. The table also sets `__STDC_VERSION__` and `__cplusplus`, and drives every extension warning.

3 *The table is lenient.* A later revision's feature shall be accepted in an earlier dialect with an extension warning, wherever its syntax cannot mean anything else. `-pedantic-errors` turns the warnings into errors ([compat.warnings]).

4 Removed features follow GCC 15's severity in each mode. Examples are implicit int, implicit function declarations and K&R definitions.

5 Single-entry overrides such as `-fgnu89-inline`, `-trigraphs` and `-fno-char8_t` override one table entry each. [compat.dialect] decides which exist.

6 ISO modes keep reserved-namespace extensions. As in GCC, a strict ISO mode (`-std=c99` rather than `gnu99`) turns off only the GNU extensions that conflict with ISO, such as the `typeof` and `asm` keywords. Spellings in the reserved namespace stay accepted: `__attribute__`, `__typeof__` and `__builtin_*`.

## 6 Range and order [front.order]

1 The range is C89 to C23 and C++98 to C++26. Working drafts (C2y, C++29) are out of scope until they are published.

2 The order is chronological and gated by milestone. Features land oldest revision first: C89's, then C99's, through C23's, and then C++98's through C++26's. C comes entirely before C++. Revisions are declared complete in the same order.

3 Each milestone needs only its own subset. The bootstrap needs the C++98 to C++20 features that Forge's own source uses, without exceptions or RTTI ([targets.m2]). The rest of each revision is filled in after the bootstrap, still oldest first.

4 Milestone 1 is cut as [m1.dialect] says. It pulls a few C23 rules ahead of this order, so that a default compile works.

## 7 Defaults [front.defaults]

1 With no `-std`, the defaults shall be GCC 15's from the start: `gnu23` for C and `gnu++17` for C++. They never move as features land, so a build never changes meaning under its user.

2 A feature the dialect enables but Forge has not implemented shall raise one *not-yet-supported error*, naming the feature and its revision. There is never a silent fallback.

3 A default C compile reports `__STDC_VERSION__` as `202311L`, so glibc's headers take their C23 paths. Milestone 1 implements the C23 baseline that makes this work ([m1.dialect]).

## 8 The AST [front.ast]

1 Each frontend shall build a tooling-grade AST. It is annotated by sema: implicit conversions are explicit nodes, and every token's location is kept. The linter, and later an IDE server, read the same AST the compiler checked.

2 The AST is laid out in dense arenas with 32-bit handles ([ir.layout]). Declarations live in a per-TU arena. Each function body has its own *body arena*, freed once its HIR is emitted unless a tool keeps it. Which C++ bodies must stay alive (templates, `constexpr` and inline functions) is in the fog ([roadmap.fog]).

3 The AST has a dump printer for tests, but no parser. HIR text stays the parseable seam ([ir.text]).

## 9 Tools [front.tools]

1 Because the ASTs are separate, the linter needs a C adapter and a C++ adapter. The debugger's expression evaluator uses the frontend of the program's language.

## Annex A (informative): Rationale and departures [front.rationale]

1 *Separate frontends.* The user chose GCC-style separate parsers and sema over a shared frontend. This departs from clang's single frontend, in which C is a mode of the C++ code and `LangOpts.CPlusPlus` checks are spread through it. Here the C frontend stays small for milestone 1. GCC likewise shares its type trees between `c/` and `cp/`; GCC's history of building C23 `constexpr`, `auto` and `nullptr` a second time in its C frontend, and of keeping OpenMP parsing in both `c-parser.cc` and `cp/parser.cc`, shows what the core is for.

2 *Feature table.* This departs from clang and GCC, which both test the language or revision directly wherever behaviour differs. The lenient table follows clang; GCC rejects more.

3 *Defaults.* GCC 15 moved its C default from `gnu17` to `gnu23` ([Porting to GCC 15](https://gcc.gnu.org/gcc-15/porting_to.html)). Clang still defaults to `gnu17` and `gnu++17`. Matching the pinned host's GCC is the drop-in choice.

4 *Chronological order.* The user chose chronological order over C17 first.

5 *AST.* This departs from clang's pointer-linked AST, which costs hundreds of MB on large C++ translation units. Carbon's SemIR and Zig's AST use dense tables.

## Annex B (informative): Provenance [front.prov]

1 [Frontend strategy](https://github.com/jmuratov98/forge/issues/6), refined by [Milestone-1 C slice definition](https://github.com/jmuratov98/forge/issues/10) (the C23 baseline supersedes "tests pass `-std` explicitly") and [Drop-in compatibility surface](https://github.com/jmuratov98/forge/issues/8) (`-std=` spellings, overrides, extension warnings).
