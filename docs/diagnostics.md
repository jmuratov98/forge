# Diagnostics model, formats and fix-its

Status: draft, 2026-11-13. Stable-name prefix: `[diag]`.

## 1 Scope [diag.scope]

1 This document specifies Forge's first-class diagnostics support: the model (stable IDs, levels, ranges, notes, backtraces, fix-its), the engine and its sinks, the text styles, machine-readable output, control flags and pragmas, optimization remarks, and how diagnostics are documented and reused by other tools. It also says how much of this milestone 1 ships ([diag.m1]).

2 Testing uses `-verify`, which matches diagnostics by stable kebab-case ID and exact line and column ([roadmap.rules]). Every diagnostic therefore needs a stable ID and a precise column.

## 2 Catalog [diag.catalog]

1 Diagnostics shall be declared in *per-component tables*, one per library or tool. The list covers the lexer and preprocessor, the C-family core, each language's sema, the driver, HIR lowering and codegen. `fas`, `fold`, the binary utilities and the linter get theirs when they arrive.

2 The tables use the fixed-schema format of the compatibility tables ([compat.tracking]). Each row holds:

- (2.1) the ID and default level;
- (2.2) the controlling flag row, from the flags table;
- (2.3) a message template with typed arguments;
- (2.4) an explanation and an example.

3 A build-time merge shall generate the enum, the `catalog.test` of the testing strategy, one docs page per ID and the `--explain` text. The merged catalog is the single source for tests, docs and explain, so they cannot drift. No message strings are written inline.

## 3 IDs [diag.ids]

1 IDs shall be global, unprefixed and kebab-case, such as `unused-variable`.

2 The merge shall reject: two rows with the same ID; a row naming a flag that does not exist; and a warning or pedwarn row with no flag.

3 Moving a check between components (sema to linter, say) keeps its ID.

## 4 Engine [diag.engine]

1 The engine is one library that depends only on the source manager and holds no compiler state. Each invocation owns an engine object, with no globals ([roadmap.rules]).

2 It takes structured diagnostics: the ID, a primary location, ranges with labels, typed arguments, child notes and fix-its. It hands them to pluggable *sinks*: GCC text, forge text, SARIF, `-verify`, and later an in-memory IDE sink. Text is rendered only in a sink.

3 Every Forge executable shall use the engine: `fcc`/`f++`, `fcc1`, `fcc1plus`, and later `fas`, `fold`, the binary utilities and the linter.

4 Milestone 2 adds a capture scope for C++ speculative contexts (SFINAE).

## 5 Levels [diag.levels]

1 The levels are fatal, error, warning, note and remark, plus GCC's two classes:

- (1.1) *permerror*: an error unless `-fpermissive` or `-Wno-error=X` is given (GCC 14's C permerrors);
- (1.2) *pedwarn*: a warning that `-pedantic-errors` turns into an error.

2 A diagnostic's level is resolved from the row, then the command-line flags, then the pragmas.

3 Not-yet-supported and not-planned diagnostics shall print as `error:`, not as GCC's `sorry, unimplemented:`, so that editor and CI parsers matching only `warning|error` catch them.

## 6 Every warning is controllable [diag.controllable]

1 Where GCC has a warning with no `-W` option, Forge shall add a Forge-only flag row (status implemented, tier P3). Pragmas and `-Wno-X` then work for every warning. In GCC style those warnings still print no option tag, as in GCC, unless `-fdiagnostics-show-id` is given.

## 7 Crashes [diag.crash]

1 The crash report's first line shall use GCC's shape: `file:line:col: internal compiler error: <assert or signal>`, located at the innermost crash-context entry that has a location; or `fcc1: internal compiler error: …` when no entry has one. The crash context, stack trace and reproducer path ([pipe.crash]) follow it.

## 8 Text styles [diag.styles]

1 There are two styles. The default is *GCC 15.2's layout*: the `file:line:col: severity: message [-Wflag]` line, with `[-Werror=foo]` and `[-Werror]` tags; the caret block with labels and the line-number gutter; fix-it display; and the closing "all/some warnings being treated as errors" line.

2 The Forge-only flag `-fdiagnostics-style=gcc|forge` shall pick the style. The last one given wins, and it is independent of `-fdiagnostics-format=` and colour.

3 The *forge* style is rustc-like: `error[id]: message`, a `--> path:line:col` line, the code block with labels, and `= note:`/`= help:` lines.

4 [Note 1: GCC's layout keeps VS Code's `$gcc`, GitHub problem matchers, Vim and Emacs working, since `error[id]:` breaks the first two. The forge style is the better read when no parser is involved. — end note]

## 9 IDs in GCC style [diag.show-id]

1 In GCC style the ID shall be hidden by default, so stderr keeps GCC's shape. `-fdiagnostics-show-id` (Forge-only) appends ` [id]`, which the research found harmless to all four parsers it checked. The ID always appears in the forge style and as SARIF's `ruleId`.

## 10 Wording [diag.wording]

1 Messages use Forge's own text. The exception is messages that build systems grep for, which shall copy GCC 15.2's wording exactly:

- (1.1) `unrecognized command-line option '…'`;
- (1.2) `command-line option '…' is valid for … but not for …`;
- (1.3) `switch '…' is no longer supported`;
- (1.4) the unknown `-Wno-X` note.

A test pins them against CMake's `FAIL_REGEX` patterns.

2 The style follows GCC: messages start lowercase and have no trailing period. They are English only, with no NLS; the catalog keeps translation possible later. Quotes are always ASCII `'x'`, in every locale.

## 11 Colour and URLs [diag.color]

1 Colour and URLs follow GCC 15.2's rules: `auto` means `TERM` is set and is not `dumb`, and stderr is a tty; `GCC_COLORS`, `GCC_URLS`/`TERM_URLS`, OSC 8 links, and the same terminal exclusions.

2 Two departures: `NO_COLOR` turns colour off under `auto` only (`=always`, which CMake and Meson pass, still wins); and URLs point at Forge's docs page for the ID or flag, not at gcc.gnu.org.

## 12 Columns [diag.columns]

1 Forge uses GCC's defaults, with GCC's options to change them (`-fdiagnostics-column-unit=`, `-fdiagnostics-column-origin=`, `-ftabstop=`): display columns, with origin 1 and tab stops of 8; raw columns on `required from` and `-fopt-info` lines, as in GCC.

2 `-verify`'s `line:column` is the column the default text sink prints. SARIF columns follow GCC's SARIF output.

## 13 Backtraces [diag.backtrace]

1 Include chains and macro definition and expansion notes follow GCC, including `-ftrack-macro-expansion=0|1|2` (default 2) and its elision.

2 C++ `required from` template context arrives in milestone 2. The GCC style uses GCC 15.2's flat form and ignores GCC 15's `experimental-nesting` keys; the forge style nests it, as GCC 16 does.

## 14 SARIF [diag.sarif]

1 SARIF 2.1.0 shall be the only machine-readable format, using GCC 15.2's spellings: `-fdiagnostics-format=text|sarif-stderr|sarif-file`, and `-fdiagnostics-add-output=`/`-fdiagnostics-set-output=` with the `text` and `sarif` schemes. In the output, `ruleId` is the Forge ID, each rule carries its help URI, and fix-its go in `result.fixes`.

2 Not-planned rows: the `json`, `json-stderr` and `json-file` values (deprecated in GCC 15, removed in GCC 16), `version=2.2-prerelease`, and clang's `-serialize-diagnostics`.

## 15 Fix-its [diag.fixits]

1 `-fdiagnostics-parseable-fixits` shall use the line shape GCC and clang share, `fix-it:"FILE":{L1:C1-L2:C2}:"TEXT"`. `-fdiagnostics-generate-patch` writes a unified diff after the diagnostics.

## 16 Control [diag.control]

1 Control shall copy GCC 15.2's semantics: `-Werror`, `-Werror=X`, `-Wfatal-errors`, `-fmax-errors=`, `-w` and `-Wsystem-headers` (no warnings inside system headers by default). An unknown `-WX` is an error; an unknown `-Wno-X` is silent unless other diagnostics occur ([compat.status]).

2 `#pragma GCC diagnostic` with `push`, `pop`, `error`, `warning`, `ignored` and `ignored_attributes` controls flagged diagnostics only. Pragmas apply by source position: the latest pragma before the diagnostic wins, and for `_Pragma` inside a macro the expansion point counts. From milestone 3, middle-end warnings are also checked against the pragmas at each inlined call site.

3 `#pragma clang diagnostic` stays an unknown pragma (`-Wunknown-pragmas`), because Forge never defines `__clang__`.

## 17 Determinism [diag.determinism]

1 Diagnostic output is covered by the repeatability gate of [m1.gates]. With the same inputs, flags and spelled paths, stderr and SARIF shall be byte-identical across runs, working directories, temp directories and hosts:

- (1.1) paths print as the user spelled them, never made absolute;
- (1.2) no temp-file paths leak into the output;
- (1.3) emission order follows the emitting pass's source order, with no dependence on hashes or threads;
- (1.4) SARIF carries no timestamps;
- (1.5) colour and URLs are off when stderr is not a tty.

## 18 Optimization remarks [diag.remarks]

1 Remarks arrive with the optimizer in milestone 3, in GCC's syntax: `-fopt-info[-kinds-groups][=file]` with GCC's kinds and groups, and its `FILE:LINE:COL: optimized|missed|note: msg` lines. Each remark is a remark-level row with an ID, sent through the same engine, so SARIF and the forge style show it too. The groups map to the pass-table names of [opt.manager]. `-fsave-optimization-record` is not-planned for now; GCC itself marks it experimental.

## 19 Docs and `--explain` [diag.docs]

1 The generator shall write one page per ID, with the explanation, an example and the controlling flag. That page is the URL target. The text is reviewed in the same pull request as the row.

2 Every Forge executable shall take `--explain=<id>`, which prints the same text from the binary for any ID in the merged catalog. An unknown ID exits with an error.

## 20 Reuse [diag.reuse]

1 Linter rule rows live in the linter's own component table. They share the global ID namespace and docs, and the same flags and pragmas control them, so there is no separate `NOLINT` scheme. The formatter reports lexer diagnostics only.

2 A later IDE server is another in-memory sink plus re-runs. Its protocol belongs to its own map, so the engine only promises a stable structured sink API.

## 21 Milestone 1 [diag.m1]

1 Milestone 1 ships every item above except: C++ template context (milestone 2); the speculative capture scope (milestone 2); `-fopt-info` (milestone 3); and inlined-call-site pragma checks (milestone 3).

2 That covers the engine and tables, both styles, `-fdiagnostics-show-id`, carets and labels, include and macro notes, text fix-its, parseable fix-its, `-fdiagnostics-generate-patch`, SARIF 2.1.0, colour and URLs, all the control flags and pragmas, the column options, `--explain`, generated docs and the determinism gate. Each is a milestone-1 row in the flags table. `fas` and `fold` diagnostics follow the GNU tools' message shapes when those tools arrive; their internals stay in the fog.

## Annex A (informative): Rationale and departures [diag.rationale]

1 The user overrode three recommendations: per-component diagnostic tables instead of one table; a rustc-like forge style as well as GCC's layout; and `--explain=<id>` as well as the generated docs pages. Every other recommendation was accepted.

2 *Catalog.* This departs from clang, in that the merged catalog is the single source for tests, docs and explain, so they cannot drift; and from GCC, which writes message strings inline.

3 *Not-yet-supported prints as `error:`* so that editor and CI parsers that match only `warning|error` still catch it.

4 *ASCII quotes.* GCC switches to curly quotes under UTF-8 locales; Forge never does, so output stays byte-identical across hosts.

5 *`NO_COLOR`.* Forge honours it under `auto` only, so that `=always` from CMake and Meson still wins.

## Annex B (informative): Provenance [diag.prov]

1 [Diagnostics model, formats and fix-its](https://github.com/jmuratov98/forge/issues/14). The facts on GCC 15.2's formats, consumer regexes, CMake's patterns, pragma semantics and `-fopt-info` are on `research/gcc-diagnostics` (d68e11c, never merged).
