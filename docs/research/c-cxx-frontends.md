# How production compilers share or split their C and C++ frontends

Research for issue #4. Accessed 2026-11-17. Source code was read on the default branches as of that date: llvm/llvm-project `main` (5f673392019e), gcc-mirror/gcc `master` (b1ab6f77ae53), edgcpp/compiler `main` (9a911cb420f4). Code is cited by file and function, not line, because line numbers drift. Counts marked "grep count" come from a plain text search and are only rough measures of how much code branches on language.

This document reports facts and trade-offs. It does not choose Forge's design; that is #9.

## Summary

| | Clang | GCC | EDG | MSVC |
|---|---|---|---|---|
| Preprocessor + lexer | One (`liblex`), with keywords gated by `LangOptions` | One (`libcpp` plus the shared `c-family/c-lex.cc`) | One, integrated | Shared source; the C++ team's posts say little about it |
| Parser | One recursive-descent parser; C++-only paths branch on `getLangOpts().CPlusPlus` | **Two**: `c/c-parser.cc` (C, ObjC) and `cp/parser.cc` (C++, ObjC++) | One | Shared source built into two binaries, `c1.dll` and `c1xx.dll` |
| Semantic analysis | One `Sema`, with language checks inline | **Two** (`c/c-typeck.cc`, `c-decl.cc` vs `cp/typeck.cc`, `decl.cc`, ...), plus the shared `c-family/` | One, with `C_mode()` checks inline | Shared source, split into variants with `#if` |
| AST / IR | One AST; C++-only node subclasses (`CXXRecordDecl`, ...) | GENERIC trees plus language-specific codes; the C++ form is "largely a superset" of C's | One IL for both languages | IL emitted to the shared back end `c2` |
| Executables | One (`clang`, `clang++`) | `cc1` and `cc1plus` | Library linked into each product | `c1.dll` and `c1xx.dll` |

**Clang** is the only one of the four whose maintainers describe the unified design as a deliberate goal. **GCC** shares everything below the parser (the preprocessor, the keyword table, literal typing, attributes, warnings, format checking, pragmas) and splits parsing and semantic analysis. **EDG** uses one frontend with a dialect variable. **MSVC** shares one source base but builds separate binaries with `#if`, and Microsoft's own architects call the result "ifdef hell".

## Clang: one frontend for every C-family language

**What is shared.** Clang has "a single unified parser for C, Objective C, C++, and Objective C++". The project states its reasons: "We believe that implementing C/C++/ObjC in a single unified parser makes the end result easier to maintain and evolve", and a hand-built recursive-descent parser "makes it straight-forward to implement excellent diagnostics and error recovery" ([Clang features][clang-features]). The libraries are layered as `libbasic` (diagnostics, `SourceLocation`), `liblex` (lexing, preprocessing, macro expansion), then Parse, Sema, AST and CodeGen ([Clang features][clang-features]).

**How the language is selected.** Every language standard Clang supports is one row in `clang/include/clang/Basic/LangStandards.def`. The C rows run c89 to c2y and gnu89 to gnu2y; the C++ rows run c++98 to c++29. All of them feed one `LangOptions` object. The lexer "uses a LangOptions object to know whether trigraphs are enabled, whether C++ or ObjC keywords are recognized, etc." ([Internals Manual, Lexer][clang-internals]). Keywords live in one table, `TokenKinds.def`, with per-language flags. For example, `_Bool` is `KEYNOCXX`; `bool` is `BOOLSUPPORT|KEYC23`; `alignas`, `constexpr` and `nullptr` are `CXX11_KEYWORD(..., KEYC23)`, meaning C++11 keywords that are also C23 keywords.

**How the semantics diverge.** Divergence is handled by inline `getLangOpts().CPlusPlus` checks. By grep count there are about 183 in `SemaDecl.cpp`, about 177 in `SemaExpr.cpp` and about 62 in `ParseDecl.cpp`. A few examples:

- `Parser::isDeclarationStatement` sends C++ to `isCXXDeclarationStatement`, the tentative-parsing disambiguator in `ParseTentative.cpp` (which asserts "Must be called for C++ only."). C makes the same decision by testing `isDeclarationSpecifier`.
- `Sema::CheckSingleAssignmentConstraints` sends C++ through `PerformImplicitConversion`/`TryImplicitConversion`, the same conversion-sequence machinery overload resolution uses. C goes through `CheckAssignmentConstraints`, which cites C99 6.5.16.
- Tag declarations create a `CXXRecordDecl` in C++ and a plain `RecordDecl` in C (`Sema::ActOnTag`).

**What the Parser/Sema boundary looks like.** "Historically, the parser used to talk to an abstract Action interface ... When Clang grew C++ support, the parser stopped supporting general Action clients – it now always talks to the Sema library" ([Internals Manual, The Parser Library][clang-internals]). C++ parsing needs semantic information, such as whether a name is a type or a template, so the C++ parser cannot run without Sema.

**Consequence: features cross language modes.** Because one Sema serves every mode, Clang offers features of one language in the other as extensions. Its documentation lists C features usable in C++, among them `_Generic`, VLAs, compound literals, flexible array members, `_Atomic`, `_BitInt` and `_Thread_local`. It also lists C++ features backported to older C++ modes, such as C++20 designated initializers in C++03 ([Language Extensions, "Back-ported to Previous Standards"][clang-langext]). The `overloadable` attribute provides "C++ function overloading in C" ([Attribute Reference][clang-attrref]). The Clang project does not list costs of the unified design on these pages. In a 2021 cfe-dev thread, Richard Smith gave the rule that extensions need a standards proposal as what keeps Clang from turning into its own "Clang C" or "Clang C++" dialect ([cfe-dev][cfe-dev-ext]).

## GCC: shared c-family below the parser, two frontends above it

**The layout.** GCC has one directory per language: `gcc/c` (C), `gcc/cp` (C++), `gcc/objc` and `gcc/objcp` ([GCC Internals, Subdirectories][gccint-subdirs]). C and C++ also share `gcc/c-family`, whose `c-common.cc` header reads "Subroutines shared by all languages that are variants of C". `c-family` holds the bridge to libcpp (`c-lex.cc`: "Mainly the interface between cpplib and the C front ends"), attributes (`c-attribs.cc`), warnings (`c-warn.cc`), format checking (`c-format.cc`), pragmas, OpenMP, built-in macros, pretty printing and spelling suggestions. Shared code tests the language at run time with `c_dialect_cxx()`, which is `(c_language & clk_cxx) != 0` over the enum `clk_c`/`clk_objc`/`clk_cxx`/`clk_objcxx` in `c-common.h`. By grep count: about 33 tests in `c-common.cc`, 18 in `c-opts.cc`, 14 in `c-cppbuiltin.cc` and 8 in `c-lex.cc`.

**Shared below the parser:**

- **Preprocessor.** One libcpp serves both, selected by `enum c_lang` (`CLK_GNUC89` to `CLK_STDC2Y`, `CLK_CXX98` to `CLK_CXX29`) in `libcpp/include/cpplib.h`.
- **Keywords.** One table, `c_common_reswords[]` in `c-common.cc`, uses flags such as `D_CONLY` and `D_CXXONLY`. For example, `_Generic` and `_Bool` are `D_CONLY`; `constexpr` and `nullptr` are `D_C23 | D_CXX11`.
- **Literal typing.** Character-constant typing is shared too. In `c-lex.cc`: "In C, a character constant has type 'int'. In C++ 'char', but multi-char charconsts have type 'int'", followed by `if (!c_dialect_cxx () || chars_seen > 1) type = integer_type_node`. Clang has the same rule in `Sema::ActOnCharacterConstant`.

**Split above the parser.** There are two hand-written recursive-descent parsers, each with its own semantic analysis.

- **C++ parser.** GCC 3.4 replaced "the YACC-derived C++ parser" with a hand-written one, citing "clean separation (where possible) between proper semantics analysis and parsing" ([GCC 3.4 changes][gcc34]). Its overview comment says "Some C++ constructs require arbitrary look ahead to disambiguate ... Therefore, the parser is capable of 'parsing tentatively'": it queues errors, saves tokens, and then commits or rolls back. It also notes "The performance of the parser could probably be improved substantially" (`cp/parser.cc`). To support this, `cp_lexer_new_main` pulls every token of the translation unit from libcpp into one buffer before parsing starts.
- **C parser.** GCC 4.1 replaced "the old Bison-based C and Objective-C parser" with "a new, faster hand-written recursive-descent parser" ([GCC 4.1 changes][gcc41]). Its header says "structure somewhat influenced by and fragments based on the C++ parser". The C parser keeps only `c_token tokens_buf[4]` of lookahead (`struct c_parser` in `c/c-parser.cc`).
- **Name binding.** C keeps its own binding model in `c-decl.cc`, with separate `I_SYMBOL_BINDING`, `I_TAG_BINDING` and `I_LABEL_BINDING` per identifier, which is C's separate tag namespace. C++ uses `cp/name-lookup.cc`.

**Representation.** "The C++ representation is largely a superset of the representation used in the C front end. There is only one construct used in C that does not appear in the C++ front end and that is the GNU 'nested function' extension" ([GCC Internals, C and C++ Trees][gcc-cctrees]). Both frontends emit GENERIC plus language-specific tree codes, then gimplify ([GCC Internals, Parsing pass][gcc-parsing]).

**Cost visible in the source.** A feature both standards share is implemented once per parser. `RID_CONSTEXPR`, `RID_STATIC_ASSERT` and `RID_TYPEOF` each appear in both `c/c-parser.cc` and `cp/parser.cc`. GCC 13 lists C23 `constexpr`, `nullptr`, `auto` and related features as C front-end work in their own right ([GCC 13 changes][gcc13]). Diagnostic quality also lands per frontend. GCC 9 says "The C++ front end now preserves source locations for literals, id-expression, and mem-initializer for longer" ([GCC 9 changes][gcc9]), which is a C++-only change.

## EDG: one frontend, one IL, many dialects (open source since 2026-09-30)

**New since the last survey.** EDG's front end went open source on 2026-09-30, with The C++ Alliance as its nonprofit home ([edg.com][edg-home], [edgcpp.org][edgcpp]). The source is public at github.com/edgcpp/compiler, and its files carry `SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception`. The README calls it "The EDG C/C++ front end", known for "parsing compatibility and bug emulation, to make sure source that compiles with Clang, GCC, and MSVC compiles with EDG" ([README][edg-readme]).

**One frontend for both languages.**

- **Command line.** C is a mode of the C++ front end: `--c` means "Enable compilation of C rather than C++". Separate flags select `--c89`, `--c99`, `--c11`, `--c17`/`--c18` and `--c23`, and these "cannot be combined with options enabling or requiring a C++ mode". The C++ side runs through `--c++26` ([EDG External Interface, §1.1.1][edg-pdf]). The documentation lists no C2y option.
- **Dialect variable.** In the source, `basics.h` defines `enum a_C_dialect { C_dialect_ANSI, C_dialect_pcc, C_dialect_cplusplus }` and `#define C_mode() (C_dialect != C_dialect_cplusplus)`. A comment says the variable is global "because it's convenient to allow 'back end' pieces to use C_mode()".
- **Inline checks.** By grep count `C_mode()` appears about 98 times in `expr.c`, 75 in `decls.c` and 14 in `lexical.c`.
- **Compiler emulation.** Emulation of gcc, clang and Microsoft is layered on top through `gcc_mode`, `clang_mode` and `microsoft_mode`, and macros such as `msc_version_is` and `clangc_version_is` combine emulation with `C_mode()` (`lang_feat.h`). "The front end extensively emulates the C modes of the Microsoft, GNU, and clang compilers" ([EDG External Interface, §1.10][edg-pdf]).

**One IL for both languages.** The front end "translates source programs into a high-level, tree-structured, in-memory intermediate language", which "preserves a great deal of source information (e.g., line numbers, column numbers, original types, original names)". In it, "Implicit and overloaded operations ... are made explicit ... but constructs are not otherwise added, removed, or reordered" ([EDG C++ Front End page][edg-c]). Lowering is optional (`DO_IL_LOWERING`) and branches on language: `lower_any_expr` dispatches to `lower_c99_expr` in C mode or `lower_expr` in C++ mode (`lower_c99.h`). The distribution also includes a C-generating back end and a C++-generating back end.

## MSVC: shared source, separate binaries, and a separate IDE frontend

**The structure.** "Although the compiler has two different binaries (c1.dll and c1xx.dll) for C and C++, there is a lot of source code that is shared between them." C++ support was added in C/C++ 7.0 (1992), and "It shared much of the same code as the C compiler and that is still true today" (Jim Springfield, [Rejuvenating the Microsoft C/C++ Compiler][msvc-rejuv], 2015).

**The original design.** The front end was built for 1980s memory limits: "convert statements and expressions to IL ... as quickly as possible ... without ever having an entire function in memory at one time ... the compiler will start emitting IL for an expression before even seeing the end of the expression". Templates were stored as token strings and replayed, which is "the fundamental reason why our compiler has never implemented two phase lookup" ([Rejuvenating][msvc-rejuv]).

**Costs Microsoft reported in its own words:**

- **`/analyze`.** It was built into the same source "under #if blocks" as separate binaries (`c1ast.dll`, `c1xxast.dll`), which grew to "more than 6,000 #if preprocessor blocks", and "most [new features] had to be implemented twice". In VS 2015 the 6,000+ `#if` blocks were replaced by "less than 200 runtime checks". A full per-function tree now serves code generation, static analysis and constexpr evaluation ([Rejuvenating][msvc-rejuv]).
- **IntelliSense.** Mark Hall describes deriving the old IntelliSense compiler, FEACP, from C1XX "through the liberal use of ifdefs". He continues: "The lesson here is that supporting two different compilers in the same source base is only slightly smarter than supporting two completely separate compilers ... (actually it was three compilers, since ANSI-C was another set of ifdefs – and truth be told it was actually four if we include the /analyze compiler)". Also: "Parsing and semantic analysis were completely intertwined. A good architecture for intellisense separates parsing from semantic analysis" ([Dev10 Is Just The Beginning][msvc-dev10], 2009).

**The IDE runs a different frontend.** For VS 2010, Microsoft licensed EDG's front end for IntelliSense because it "provides a high-level representation chock-full of the information we wanted" ([Rebuilding Intellisense][msvc-rebuild]). EDG confirms Microsoft's primary compiler is not EDG-based, "but Intellisense uses our front end" ([EDG FAQ][edg-faqcust]). Microsoft therefore keeps two independent C/C++ frontends, one for code generation and one for the IDE.

**C support has lagged.** "For many years Visual Studio has only supported C to the extent of it being required for C++." C11 and C17 arrived in VS 2019 16.8 and needed the new token-based conforming preprocessor. Microsoft states "we intend not to support VLAs" ([C11 and C17 Standard Support Arriving in MSVC][msvc-c11], 2020).

## Which C/C++ differences drive the split

**C++ Annex C [diff.iso].** In the current draft this is §C.8, "C++ and C". It has 39 "Affected subclause" entries, ordered by C++ clause (lex, basic, expr, stmt, dcl, class, cpp) ([eel.is/c++draft/diff.iso][diff-iso]). The C++ draft's normative reference for C is ISO/IEC 9899:2024 ([intro.refs][intro-refs]). Annex C only covers constructs both languages have. It does not list C-only features such as VLAs, `_Generic`, `restrict`, `_Complex`, compound literals or flexible array members.

**P2735R0 / N3065, "C xor C++ Programming".** Aaron Ballman's paper for SG22 lists 26 named cases where "the same source code has different meaning when compiled with C and C++ implementations". It likewise "explicitly does not cover situations where one language has a feature that the other language does not have" ([P2735R0][p2735]).

**The differences fall into three groups by what they cost a frontend:**

1. **One-line rule switches inside otherwise shared code.** Every frontend studied puts these in shared code behind a language test.
   - Character-literal type, [diff.lex] / [type.char-literal]: shared GCC `c-lex.cc` and Clang `ActOnCharacterConstant`.
   - Tentative definitions, [diff.basic] / [decl.tentative]: Clang `VarDecl::isThisDeclarationADefinition` returns `TentativeDefinition` only `if (!C.getLangOpts().CPlusPlus && isFileVarDecl() ...)`.
   - Keywords, [diff.lex]: one table with per-language flags in both Clang and GCC.
   - Others: `const` objects requiring an initializer, the `bool` decrement ban, an empty parameter list meaning `(void)`, string literals being `const`.
2. **Different lookup and scoping models.** This is where GCC keeps separate code.
   - Tag namespace / class-name injection, [diff.class] `class.name`, and "a struct is a scope in C++", [diff.basic]: Clang folds this into one lookup function, `getIDNS` in `SemaLookup.cpp`, which ORs `IDNS_Tag | IDNS_Member | IDNS_Namespace` into ordinary lookup only when `CPlusPlus`. GCC C keeps a separate tag binding per identifier (`I_TAG_BINDING`).
   - Nested-class name scope, [diff.class] `class.nest`.
3. **Different conversion and initialization machinery.**
   - Implicit `void*` to `T*`, [diff.expr] `conv.ptr`: C accepts it; C++ requires a cast. Clang uses `CheckAssignmentConstraints` for C and implicit-conversion sequences for C++.
   - Enum arithmetic and the usual arithmetic conversions, [diff.expr].
   - Designated initializers, [diff.dcl] `dcl.init.aggr`: C++ restricts them. Clang parses the C99 superset in both modes, then emits C++-mode extension warnings for nested, array, mixed and reordered designators (`Sema::ActOnInitList`, `InitListChecker`).

**C-only features.** The superset approach is visible in how C-only features behave in C++ mode:
- **VLAs.** Clang accepts them in C++ with `ext_vla_cxx` (an error under SFINAE) (`SemaType.cpp`, `BuildArrayType` path); MSVC does not support them in C at all.
- **`_Generic`.** Clang parses it in every mode (`ParseGenericSelectionExpression` calls `diagnoseUseOfC11Keyword`); GCC marks it `D_CONLY`.

**Declaration-versus-expression ambiguity.** This parsing problem exists only in C++ and drives parser architecture more than any semantic rule. GCC's C++ parser buffers the whole token stream to parse tentatively, while its C parser needs 4 tokens of lookahead. Clang uses a C++-only disambiguator (`ParseTentative.cpp`).

## Tooling: error recovery, source locations, tokens and comments

**Error recovery.**
- **Clang.** "Clang produces an AST even when the code contains errors ... Clang-based tools also depend on such ASTs, and IDEs in particular benefit". It corrects errors with FixIts, marks invalid Decls, and uses `RecoveryExpr`, "a placeholder to maintain the rough structure of the parsing tree, preserve locations and children, but have no language semantics". To type it, "we generalize the concept of dependence from C++ templates to mean dependence on ... how an error is repaired". A broken C expression is therefore "type-dependent, value-dependent, contains-errors", which means **C's recovery reuses C++ template-dependence machinery** ([Internals Manual, Error Handling / Recovery AST][clang-internals]).
- **GCC.** The C++ parser queues errors during tentative parsing (`cp/parser.cc` overview). The C parser has a per-parser `error` flag "set ... when a syntax error is being recovered from" (`struct c_parser`).
- **MSVC.** IntelliSense is EDG; its separate tag parser was "designed to be extremely resilient ... handle ambiguous code, mismatched braces or parentheses" ([IntelliSense Part 2][msvc-isense2]).

**Source locations.**
- **Clang.** `SourceLocation` is 32 bits and encodes the include stack and macro expansion. Each location has a "spelling location" and an "expansion location". Ranges are token-based `[first, last]`, with `CharSourceRange` where characters matter ([Internals Manual][clang-internals]).
- **GCC.** Since GCC 6, `location_t` holds caret, start and finish ([GCC 6 changes][gcc6], [GCC Internals, Guidelines for Diagnostics][gccint-diag]). The C++ front end added location wrappers for literals and id-expressions in GCC 9.
- **EDG.** `a_source_position` is a sequence number plus column. With `FULLY_RESOLVED_MACRO_POSITIONS`, separate `orig_seq`/`orig_column` record where macro-expanded text came from (`basics.h`).
- **MSVC.** Full column tracking for all constructs arrived in VS 2015 ([Rejuvenating][msvc-rejuv]).

**Preserved tokens and comments.**
- **Clang.** The lexer can "capture and return comments as tokens", and has a raw mode used for `#if 0` regions ([Internals Manual, Lexer][clang-internals]). The AST attaches doc comments as `RawComment`; `-fparse-all-comments` treats ordinary comments as doc comments (`CommentOptions.h`). For tools, `clang::syntax::TokenBuffer` records both "spelled" tokens (what the user wrote) and "expanded" tokens (what the parser consumed), and maps between them (`clang/Tooling/Syntax/Tokens.h`). clang-format does not use Sema: `FormatTokenLexer` wraps `clang::Lexer`, and `UnwrappedLineParser` "turns a stream of tokens into UnwrappedLines" (`clang/lib/Format/`).
- **GCC.** libcpp provides a `comment` callback and a `CPP_COMMENT` token kind ("Only if output comments") (`cpplib.h`). GCC ships no frontend-as-library API. Richard Stallman's 2014 position on the gcc list was that GCC must not become "a platform for nonfree compilers" ([gcc@ 2014-01][rms-2014]).
- **EDG.** "Source sequence lists" (`src_seq.c`, `GENERATE_SOURCE_SEQUENCE_LISTS`) record IL entities in source order for source-to-source back ends. Optional cross-reference output (`--xref`) supports browsers ([EDG External Interface][edg-pdf], [EDG C++ Front End page][edg-c]).

## Trade-offs the sources report

- **Unified (Clang, EDG).**
  - *Benefits:* one place to implement each rule. Shared infrastructure flows into C: recovery reuses template dependence, assignment uses the conversion machinery. Clang says it is "easier to maintain and evolve" ([Clang features][clang-features]).
  - *Costs:* language checks spread through Sema and Parse (hundreds per large file by grep count), and each language's features become available in the other's mode, so the project must police the boundary with policy rather than structure ([cfe-dev][cfe-dev-ext]). One global dialect variable in EDG is visible even to back-end pieces (`basics.h` comment).
- **Shared lower layers, split parser and Sema (GCC).**
  - *Benefits:* each parser fits its language's lookahead needs (4 tokens vs whole-TU buffering). C name binding stays C-shaped.
  - *Costs:* features common to both standards (C23 `constexpr`, `nullptr`, `typeof`, attributes, `static_assert`) are parsed and checked twice, and diagnostic improvements land per frontend (GCC 9's C++-only location work).
- **Shared source, variants by `#if` (MSVC, historically).** Microsoft's architects report the worst outcome of the four: "ifdef hell", features "implemented twice", test coverage that did not carry across variants, and a "language gap" ([Dev10][msvc-dev10], [Rejuvenating][msvc-rejuv]). Their remedy was one full tree used by every consumer, with runtime checks instead of compile-time variants.
- **Tools.** Where the compiler's frontend could not serve IDE needs, both Microsoft (EDG for IntelliSense) and Clang (the separate clang-format lexer and parser) built or licensed another component. Clang instead invested in recovery ASTs and token buffers so that clangd and clang-tidy run the real frontend.

## Questions this raises for #9 (not answered here)

- ADR 0002 already makes the C frontend and the C++ frontend separate component libraries. Which layers below them are shared libraries? In GCC the shared layer is the preprocessor, the keyword table, literal typing, attributes, warnings and format checking.
- If C and C++ semantic analysis are separate, is error-recovery infrastructure (an equivalent of `RecoveryExpr` and "contains-errors") written twice or shared? Clang's version depends on C++'s dependence model.
- Does either frontend accept the other language's features as extensions, as Clang and EDG do, or do they reject them?
- Do tools (formatter, LSP) consume the full frontends, or a lighter token or syntax layer, as clang-format and MSVC's tag parser do?
- Should Forge borrow anything from EDG now that it is public under Apache-2.0 WITH LLVM-exception: its IL design, its dialect tables, its tests? Forge is built from scratch, so the answer may simply be no.

## Sources

[clang-features]: https://clang.llvm.org/features.html
[clang-internals]: https://clang.llvm.org/docs/InternalsManual.html
[clang-langext]: https://clang.llvm.org/docs/LanguageExtensions.html
[clang-attrref]: https://clang.llvm.org/docs/AttributeReference.html#overloadable
[cfe-dev-ext]: https://lists.llvm.org/pipermail/cfe-dev/2021-December/069559.html
[gccint-subdirs]: https://gcc.gnu.org/onlinedocs/gccint/Subdirectories.html
[gcc-cctrees]: https://gcc.gnu.org/onlinedocs/gccint/C-and-C_002b_002b-Trees.html
[gcc-parsing]: https://gcc.gnu.org/onlinedocs/gccint/Parsing-pass.html
[gccint-diag]: https://gcc.gnu.org/onlinedocs/gccint/Guidelines-for-Diagnostics.html
[gcc34]: https://gcc.gnu.org/gcc-3.4/changes.html
[gcc41]: https://gcc.gnu.org/gcc-4.1/changes.html
[gcc6]: https://gcc.gnu.org/gcc-6/changes.html
[gcc9]: https://gcc.gnu.org/gcc-9/changes.html
[gcc13]: https://gcc.gnu.org/gcc-13/changes.html
[rms-2014]: https://gcc.gnu.org/legacy-ml/gcc/2014-01/msg00247.html
[edg-home]: https://www.edg.com/
[edgcpp]: https://edgcpp.org/
[edg-readme]: https://github.com/edgcpp/compiler
[edg-c]: https://www.edg.com/c
[edg-faqcust]: https://edg.com/faq/customers
[edg-pdf]: https://www.edg.com/docs/edg_cpp.pdf
[msvc-rejuv]: https://devblogs.microsoft.com/cppblog/rejuvenating-the-microsoft-cc-compiler/
[msvc-dev10]: https://devblogs.microsoft.com/cppblog/?p=4653
[msvc-rebuild]: https://devblogs.microsoft.com/cppblog/rebuilding-intellisense/
[msvc-isense2]: https://devblogs.microsoft.com/cppblog/intellisense-part-2-the-future/
[msvc-c11]: https://devblogs.microsoft.com/cppblog/c11-and-c17-standard-support-arriving-in-msvc/
[diff-iso]: https://eel.is/c++draft/diff.iso
[intro-refs]: https://eel.is/c++draft/intro.refs
[p2735]: https://isocpp.org/files/papers/P2735R0.pdf

**Documentation and design writing**
- Clang: [Features and Goals][clang-features]; [Internals Manual][clang-internals]; [Language Extensions][clang-langext]; [Attribute Reference: overloadable][clang-attrref]; [cfe-dev, Richard Smith, 2021-12][cfe-dev-ext]
- GCC Internals: [Subdirectories][gccint-subdirs], [C and C++ Trees][gcc-cctrees], [Parsing pass][gcc-parsing], [Guidelines for Diagnostics][gccint-diag]
- GCC release notes: [3.4][gcc34], [4.1][gcc41], [6][gcc6], [9][gcc9], [13][gcc13]; [Stallman, gcc@ 2014-01][rms-2014]
- EDG: [edg.com][edg-home]; [edgcpp.org][edgcpp]; [github.com/edgcpp/compiler][edg-readme]; [C++ Front End][edg-c]; [Customer FAQ][edg-faqcust]; [External Interface, v6.8, 2025-11-21][edg-pdf]
- Microsoft C++ Team Blog: [Rejuvenating the Microsoft C/C++ Compiler (2015)][msvc-rejuv]; [Dev10 Is Just The Beginning (2009)][msvc-dev10]; [Rebuilding Intellisense (2009)][msvc-rebuild]; [IntelliSense, Part 2 (2008)][msvc-isense2]; [C11 and C17 Standard Support Arriving in MSVC (2020)][msvc-c11]
- Standards: [C++ draft, Annex C, [diff.iso]][diff-iso]; [C++ draft, [intro.refs]][intro-refs]; [P2735R0 / N3065, C xor C++ Programming][p2735]

**Source files read**
- Clang (llvm/llvm-project `main`): `clang/include/clang/Basic/{LangStandards.def,TokenKinds.def,CommentOptions.h}`, `clang/include/clang/Parse/Parser.h`, `clang/lib/Parse/{ParseExpr,ParseTentative}.cpp`, `clang/lib/Sema/{SemaExpr,SemaDecl,SemaInit,SemaLookup,SemaType}.cpp`, `clang/lib/AST/Decl.cpp`, `clang/include/clang/Tooling/Syntax/Tokens.h`, `clang/include/clang/AST/RawCommentList.h`, `clang/lib/Format/{FormatTokenLexer,UnwrappedLineParser}.h`
- GCC (gcc-mirror/gcc `master`): `gcc/c-family/{c-common.h,c-common.cc,c-lex.cc,c-opts.cc,c-cppbuiltin.cc}`, `gcc/c/{c-parser.cc,c-decl.cc,c-typeck.cc}`, `gcc/cp/{parser.cc,typeck.cc}`, `libcpp/include/cpplib.h`, `gcc/tree.h`
- EDG (edgcpp/compiler `main`): `src/{basics.h,lang_feat.h,lower_c99.h,src_seq.h,expr.c,decls.c,lexical.c}`
