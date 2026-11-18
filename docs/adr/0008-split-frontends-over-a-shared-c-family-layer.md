# Split C and C++ frontends over a shared C-family layer

Forge's C compiler and Forge's C++ compiler have separate frontends: each has its own parser, its own semantic analysis, its own AST, and its own lowering to Ingot. Underneath both sits the **C-family layer**, one library holding what the languages genuinely share. This is GCC's shape, not Clang's or EDG's. The features C and C++ now share by name diverge in meaning (C23 `constexpr` covers objects only, C's `auto` deduces nothing like C++'s, `nullptr` has different conversion rules), so a shared Sema would still branch per language on each of them. C++ does not arrive until M9, so a split lets eight milestones of C work be shaped by C alone and lets the C++ frontend be designed around tentative parsing and templates from the start. It also keeps C++'s complexity (templates, dependence, overloading, value categories) out of the C frontend entirely.

```
           C source                       C++ source
               │                               │
   ┌───────────┴───────────┐       ┌───────────┴───────────┐
   │ C frontend            │       │ C++ frontend          │
   │ parser, Sema, C AST   │       │ parser, Sema, C++ AST │
   │ C AST → Ingot         │       │ C++ AST → Ingot       │
   └───────────┬───────────┘       └───────────┬───────────┘
               └───────────────┬───────────────┘
                        C-family layer
```

## The C-family layer

Something belongs here only if it is language-neutral, or if it must be bit-identical between C and C++. Nothing in it may name a C++-only concept. It is its own library from M1, although the C frontend is its only user until M9, and it never depends on either frontend.

- The preprocessor and the lexer, with keyword tables chosen by language mode. The preprocessor yields a plain `token_stream`, one token per pull. A `buffered_token_stream` wraps it with `peek(n)`, `mark()`, and `rewind(mark)`, and keeps tokens only while a mark is outstanding. Both parsers use it: the C parser never marks, so its buffer stays a few tokens long, while C++'s tentative parsing backtracks through the same class. Consumers of raw tokens (the formatter, `-E`, fas's `.S` files) skip the buffering.
- Language options: the language, the standard version, and the GNU and MS extensions.
- Parsing and typing of literals, with the rules that differ (the type of `'a'`) as switches.
- Target type information: sizes, alignments, and the signedness of `char`.
- Layout of C-compatible records (structs, unions, bitfields), which must match between C and `extern "C"` C++. Each frontend hands it a neutral field list; C++ adds vptrs and bases on top.
- The builtin and arithmetic type nodes (integers with their rank, `_BitInt(N)`, floating, complex, `bool`, and character types) and qualifiers, used by both ASTs, with the rules over them: integer promotions, the usual arithmetic conversions, and conversion warnings. Their lowering to Ingot is shared too. Pointer, array, function, record, and enum types stay per-frontend, because C++ needs dependent variants of them.
- Constant arithmetic, the builtin and attribute tables, and format-string checking.

## What every frontend guarantees

Both frontends meet these from their first milestone (M1 for C, M9 for C++), so the linter, the language server, and the debugger can run on them instead of on a second frontend built for the IDE:

- **Error recovery.** The AST has error nodes (a recovery expression that keeps its subexpressions, invalid declarations) and a contains-errors bit that propagates upward. Sema suppresses cascading diagnostics on nodes with errors, and the parser resyncs at statement and declaration boundaries. Both frontends follow this one model, each with its own nodes.
- **Precise locations.** Every node carries a begin and end range, and expressions also carry a caret location. A location records both the spelling position and the macro-expansion chain.
- **Tokens and comments on request.** The AST is semantic, not lossless. A tool that needs tokens asks for a token buffer that maps spelled tokens to expanded ones, and a tool that needs comments turns on capture in the lexer. A plain compile pays for neither.
- **Usable as a library.** There is no mutable global state, so translation units can compile on separate threads in one process. A frontend never exits the process or writes to stdout or stderr; diagnostics go to a consumer interface. All file access goes through a file-system interface, so a language server can supply unsaved buffers. Long operations can be cancelled.

## Which tool uses which layer

- **Formatter**: the C-family lexer only, keeping comments and whitespace, plus its own structural parser over the unpreprocessed source, so that it formats every `#if` branch.
- **Linter and language server**: a full frontend as a library. The frontends provide no common view over the two ASTs; tools use each AST directly, and share work across languages through the C-family layer.
- **Debugger expression evaluator**: the frontend named by each frame's `DW_AT_language`, with a hook that resolves names from debug info.

## Considered options

- **One frontend with C as a mode** (Clang, EDG): rejected. It is easier to maintain features the languages share, but C would carry C++'s machinery, and the C frontend built for M1–M8 would have to anticipate a C++ frontend that is eight milestones away.
- **One parser and AST with separate Semas**: rejected. The shared AST would have to carry value categories and dependence for C++, which brings C++'s complexity into C anyway.
- **One AST in which C's nodes are a subset of C++'s**: rejected for the same reason. Sharing stops at the builtin types, the one place where C++ adds nothing C must carry.
- **Variant builds of shared source** (MSVC's `c1` and `c1xx`): rejected. Microsoft's own architects call it "ifdef hell".
- **Extracting the shared layer at M9**: rejected. By then the preprocessor and record layout would hold eight milestones of C assumptions.

## Consequences

- Error recovery, lowering to Ingot, and every AST-level tool check are written once per frontend, and C++ reimplements most of C's expression semantics apart from arithmetic. These are the accepted costs of the split.
- ADR 0002 already names the C frontend and the C++ frontend as separate component libraries; the C-family layer joins them.
- The Forge language may later use the C-family preprocessor and lexer. That is for its own planning to decide; if it does, the layer may need a name that is not "C-family".
- The source manager and the encoding of locations, and the diagnostics engine with its renderers, are designed separately.
