# GCC 15.2 diagnostics: facts for a drop-in replacement

Gathered 2026-11-10. Sources are the GCC 15.2.0 manual, the GCC 13/14/15/16 changes pages, and the source tree at the
`releases/gcc-15.2.0` tag (via the gcc-mirror GitHub repository), plus the named consumers' sources. Facts read from
source code rather than the manual are marked "(source)". Anything not checked against a primary source is marked
**UNVERIFIED**.

URL shorthands used below:

- [MSG] https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Diagnostic-Message-Formatting-Options.html
- [WARN] https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Warning-Options.html
- [DEV] https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Developer-Options.html
- [PRAGMA] https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Diagnostic-Pragmas.html
- [ENV] https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Environment-Variables.html
- [C13] / [C14] / [C15] / [C16] https://gcc.gnu.org/gcc-NN/changes.html
- [SRC:path] https://github.com/gcc-mirror/gcc/blob/releases/gcc-15.2.0/gcc/path

---

## 1. Text format

### 1.1 First line

- The prefix is built as `"%s %s%s%s"` = location text, a space, then the colored kind text. The location text is
  `file:line:col:` (`"%s%s%s:%s"` with `maybe_line_and_column` = `":%d:%d"`, or `":%d"` when there is no column).
  So the line reads `file:line:col: error: message [-Wflag]`. (source) [SRC:diagnostic-format-text.cc] `build_prefix`;
  [SRC:diagnostic.cc] `diagnostic_column_policy::get_location_text`.
- When the file is `<built-in>`, line and column are dropped (`<built-in>: ...`). When there is no file, `progname` is used
  (for example `cc1: warning: ...`). The column is dropped if `-fno-show-column` is given or the computed column is <= 0.
  (source) [SRC:diagnostic.cc] lines ~750-769.
- The kind strings, exactly as written, with the trailing `": "` (source) [SRC:diagnostic.def]: `fatal error: `,
  `internal compiler error: `, `error: `, `sorry, unimplemented: `, `warning: `, `anachronism: `, `note: `, `debug: `,
  `path: `. A warning promoted by -Werror (DK_WERROR) prints `error: `. Pedwarns and permerrors print as warning or error.
- The option tag is printed as `" [" + option + "]"` after the message. With URLs on, the option text is wrapped in a
  hyperlink. (source) [SRC:diagnostic-format-text.cc] `print_option_information`.
- The option name logic (source) [SRC:opts.cc] `compiler_diagnostic_option_manager::make_option_name`:
  - A warning or pedwarn that was turned into an error and has an option prints `-Werror=` followed by the option text
    minus its leading `-W`, giving `[-Werror=foo]`.
  - A warning with an option prints that option, for example `[-Wunused-variable]`.
  - A warning with no option, promoted by plain `-Werror`, prints `[-Werror]`.
  - Otherwise nothing is printed. There is no `[enabled by default]` text in 15.2.
- `-fdiagnostics-show-option` is on by default (`Init(1)`), and `-fno-diagnostics-show-option` suppresses the tag.
  [MSG]; [SRC:common.opt].
- At the end of compilation, if any warning was promoted, GCC prints `PROGNAME: all warnings being treated as errors`
  (plain -Werror) or `PROGNAME: some warnings being treated as errors` (only -Werror=). (source)
  [SRC:diagnostic-format-text.cc] ~lines 134-149.
- Other termination lines (source) [SRC:diagnostic.cc]: `compilation terminated due to -fmax-errors=%u.`,
  `compilation terminated due to -Wfatal-errors.`, `compilation terminated.`

### 1.2 Columns

- `-fdiagnostics-column-unit=` takes `display` (the default) or `byte`. With `display`, a tab is counted as the columns it
  occupies, and a multibyte character as its display width: U+03C0 is 1 column (2 bytes) and U+1F642 is 2 columns
  (4 bytes). `byte` counts raw bytes, which was the behaviour before GCC 11.1. [MSG]
- `-fdiagnostics-column-origin=` defaults to 1. Any non-negative value may be given. [MSG]
- Tabs expand to stops of `-ftabstop` (default 8). `dc.m_tabstop = 8`. Display columns are computed with
  `cpp_char_column_policy(tabstop, cpp_wcwidth)`. (source) [SRC:diagnostic.cc] lines 280 and 701-745; [SRC:common.opt]
  `ftabstop=`.
- Exception: the C++ template context lines (`required from ...`) print `xloc.column` directly through
  `print_location`. That column is the raw expanded column and does not go through the column policy, so it ignores the
  unit and origin options. (source) [SRC:cp/error.cc] `print_location`.
- `-fopt-info` lines also use `LOCATION_COLUMN` directly (see section 7). (source)
- GCC 15 can track column numbers larger than 4096. [C15]

### 1.3 Context lines

- **Include chain** (source) [SRC:diagnostic-format-text.cc] `report_current_module`:
  - The first line is `In file included from FILE:LINE`. Each further line is `,\n                 from FILE:LINE`, so
    continuation lines are indented with 17 spaces before `from`. The chain ends with `:` and a newline.
  - Only the first entry may carry a column, and only when show-column is on and the `#include` location has a column
    greater than 0. Typical output has none: the [C15] example shows `In file included from demo.c:1:`.
  - Module variants: `In module`, `of module`, `In module imported at`, `imported at`.
  - Each include stack is printed only once per file (`includes_seen_p`).
- **Function context**: the C front end prints `FILE: In function 'NAME':`, as shown in [C15]. The C++ front end can
  print `In function %qD`, `In member function %qD`, `In static member function %qD`, `In constructor %qD`,
  `In destructor %qD`, `In copy constructor %qD`, `In lambda function`, and `At global scope:`. (source)
  [SRC:cp/error.cc] ~3753-3864.
- **Macro expansion**: after the diagnostic, GCC adds notes of the form `FILE:L:C: note: in definition of macro 'X'` and
  `FILE:L:C: note: in expansion of macro 'Y'`. (source) [SRC:diagnostic-macro-unwinding.cc] lines 60-70 and 182/199.
- **C++ template context** (source) [SRC:cp/error.cc] ~3880-4075:
  - The header line is `FILE: In instantiation of 'DECL':` or `FILE: In substitution of 'X':`.
  - It is followed by lines of the form `FILE:L:C:   required from 'DECL'`, `...   required from here`,
    `...   recursively required from ...` and `...   required by substitution of ...`. These have three spaces after
    the location and **no severity word**.
  - If the chain is too long, GCC prints
    `[ skipping N instantiation contexts, use -ftemplate-backtrace-limit=0 to disable ]`.
  - Since GCC 14, GCC also quotes the source at the "required from here" location. [C14]

### 1.4 Source quoting, carets, ranges, labels and line numbers

- The caret display is on by default (`-fdiagnostics-show-caret`, `Init(1)`). A `^` marks the caret and `~` marks
  ranges. Labels are drawn with `|` connectors, and `-fno-diagnostics-show-labels` turns them off.
  [MSG]; [SRC:common.opt].
- The quoted source line is truncated to `-fmessage-length=n` columns. On a terminal it is truncated to `COLUMNS` or the
  terminal width. [MSG]
- `-fdiagnostics-show-line-numbers` is on by default (`Init(1)`). It adds a left margin of the form ` NN | `.
  `-fdiagnostics-minimum-margin-width=` defaults to 6. [MSG]; [SRC:common.opt].
- Text art: `-fdiagnostics-text-art-charset=` takes `none`, `ascii`, `unicode` or `emoji`. The default is `emoji`,
  except `ascii` when `LANG=C`. The option was added in GCC 14. [MSG]; [C14].
- `-fdiagnostics-path-format=` takes `none`, `separate-events` or `inline-events` (the default). `separate-events` prints
  one `note: (N) ...` per event. [MSG]
- Since GCC 15, highlight colours (`highlight-a` / `highlight-b`) contrast mismatching things. They are on whenever
  colour is on, and `-fno-diagnostics-show-highlight-colors` turns them off. [MSG]; [C15].
- `-fdiagnostics-escape-format=` takes `unicode` (the default, `<U+XXXX>` and `<XX>`) or `bytes`. It applies only to
  diagnostics flagged as encoding-related. [MSG]

### 1.5 Fix-it hints in text

- An insertion is shown as the new text on a line below the caret or underline. Examples are `;` under `^` [C15 SARIF
  section], `&` [C15], and `%s` [MSG -fno-diagnostics-show-highlight-colors example].
- A replacement is shown as a `-----` underline over the affected range, then the new text on the next line. A deletion
  is the `-----` underline alone. (source) [SRC:diagnostic-show-locus.cc] ~2480-2490, and the self-test at ~5445:
  ```
     foo *f = (foo *)ptr->field;
                     ^~~~~~~~~~
              -------
              (bar *)
  ```
- Fix-its are coloured with `fixit-insert=32` and `fixit-delete=31`. [MSG]

### 1.6 Colour

- `-fdiagnostics-color=` takes `never`, `always` or `auto`. The default is fixed at configure time by
  `--with-diagnostics-color={never,auto,auto-if-env,always}`. If the flag is not given, configure defaults to `auto`
  (`DIAGNOSTICS_COLOR_DEFAULT=DIAGNOSTICS_COLOR_AUTO`). [MSG];
  [SRC:configure.ac] https://github.com/gcc-mirror/gcc/blob/releases/gcc-15.2.0/gcc/configure.ac ~7681-7705.
  - `auto-if-env` means `auto` if `GCC_COLORS` is set and `never` otherwise. (source) [SRC:diagnostic.cc] `color_init`.
- How `auto` is detected on POSIX (source) [SRC:diagnostic-color.cc] `should_colorize`:
  ```c
  char const *t = getenv ("TERM");
  /* emacs M-x shell sets TERM="dumb".  */
  return t && strcmp (t, "dumb") != 0 && isatty (STDERR_FILENO);
  ```
  So `TERM` must be set and not `dumb`, and stderr must be a tty. On MinGW, colour is used when `GetConsoleMode` succeeds
  on the stderr handle, and GCC tries to enable VT processing.
- `GCC_COLORS` is a colon-separated list of `cap=SGR` entries. An empty `GCC_COLORS` disables colour. [MSG]
  - Default:
    `error=01;31:warning=01;35:note=01;36:range1=32:range2=34:locus=01:quote=01:path=01;36:fixit-insert=32:fixit-delete=31:diff-filename=01:diff-hunk=32:diff-delete=31:diff-insert=32:type-diff=01;32:fnname=01;32:targs=35:valid=01;31:invalid=01;32 highlight-a=01;32:highlight-b=01;34`.
    The manual's listing is missing a `:` between `invalid=01;32` and `highlight-a`.
- **NO_COLOR is not honoured.** No occurrence of `NO_COLOR` was found in the 15.2 sources checked: diagnostic-color.cc,
  diagnostic.cc, opts*.cc, gcc.cc and toplev.cc. The manual does not mention it either. [MSG]; (source).
  **UNVERIFIED** for the whole tree, since not every file was grepped.

### 1.7 URLs

- `-fdiagnostics-urls=` takes `never`, `always` or `auto`. The configure default is `auto`
  (`--with-diagnostics-urls`, which also offers `auto-if-env`). [MSG]; [SRC:configure.ac] ~7707-7733.
- The escapes are **OSC 8**: `ESC ]8;; URL ESC \` ... `ESC ]8;; ESC \` in ST form, or the same terminated with BEL
  (`\a`). BEL is the default. (source) [SRC:pretty-print.cc] ~3069-3096 and the tests at ~3950-3991.
- `GCC_URLS`, with `TERM_URLS` as the fallback, is read even under `always` (source) [SRC:diagnostic-color.cc]
  `parse_env_vars_for_urls`:
  - Unset gives the default (BEL).
  - Empty or `no` turns URLs off.
  - `st` selects ST.
  - `bel` selects BEL.
  - Any other value gives the default.
- How `auto` decides (source) `auto_enable_urls`:
  - It first requires `should_colorize()`.
  - It rejects `COLORTERM=xfce4-terminal` and `COLORTERM=gnome-terminal`.
  - Then, if `GCC_URLS` or `TERM_URLS` is set, URLs are on.
  - Otherwise it rejects `TERM=xterm` and `TERM=linux` when `COLORTERM` is unset.
  - In every other case URLs are on.
- What is linked:
  - The option in the `[-Wfoo]` tag links to `DOCUMENTATION_ROOT_URL` plus a suffix such as
    `gcc/Warning-Options.html#index-Wcpp`. For 15.2.0 the root is `https://gcc.gnu.org/onlinedocs/gcc-15.2.0/`.
    (source) [SRC:opts.cc] `get_option_url_suffix` and tests ~3976; [SRC:configure.ac] ~1099-1112.
  - Since GCC 14, any quoted command-line option in a message is linked. [C14]
  - Since GCC 15, attributes link to their docs. [C15]
  - CWE IDs link to `https://cwe.mitre.org/data/definitions/%i.html`. [SRC:diagnostic.cc] `get_cwe_url`.

### 1.8 Line wrapping and plain output

- `-fmessage-length=n`: n=0 means no wrapping, and 0 is "the default for all front ends". [MSG]
- `-fdiagnostics-plain-output` is equivalent to: `-fno-diagnostics-show-caret -fno-diagnostics-show-line-numbers
  -fdiagnostics-color=never -fdiagnostics-urls=never -fdiagnostics-path-format=separate-events
  -fdiagnostics-text-art-charset=none -fno-diagnostics-show-event-links`. Future default-appearance changes will add
  their opt-outs to this list. [MSG]
  - GCC 16 adds nesting to that set: "The old behavior can be restored via -fno-diagnostics-show-nesting or
    -fdiagnostics-plain-output". [C16]

### 1.9 Experimental nesting (GCC 15)

- Enabled with `-fdiagnostics-set-output=text:experimental-nesting=yes`, marked "experimental ... subject to change".
  [C15]
- Text-sink keys: `color=yes|no`, `experimental-nesting=yes|no`, `experimental-nesting-show-locations=yes|no` and
  `experimental-nesting-show-levels=yes|no`. In nested mode, nested notes drop the `note: ` text and use indentation and
  bullets instead. [MSG]; (source) [SRC:diagnostic-format-text.cc] `build_prefix`; [SRC:opts-diagnostic.cc].
- In GCC 16, nesting is on by default for C++ template-style errors, and `-fno-diagnostics-show-nesting` turns it off.
  [C16]

## 2. Machine-readable output

- `-fdiagnostics-format=` accepts `text` (the default), `sarif-stderr`, `sarif-file`, `json`, `json-stderr` and
  `json-file`. `sarif-file` writes `SOURCE.sarif`. `json-file` writes `SOURCE.gcc.json`. Using this option replaces any
  sinks added by `-fdiagnostics-add-output=` or set by `-fdiagnostics-set-output=`. [MSG]; [SRC:common.opt] ~1466-1523.
- Status of `json`:
  - Added in GCC 9 (**UNVERIFIED** release number).
  - `json-stderr` and `json-file` were added in GCC 13. [C13]
  - **Deprecated in GCC 15**: "may be removed in a future release". [C15]; [MSG]
  - **Removed in GCC 16**. [C16]
  - No deprecation warning is emitted at use. No such diagnostic was found in opts*.cc or diagnostic*.cc. (source)
    **UNVERIFIED** for the whole tree.
- `-fdiagnostics-add-output=SPEC` and `-fdiagnostics-set-output=SPEC` are new in GCC 15. [C15]; [MSG]
  - The grammar is `SCHEME[:KEY=VALUE(,KEY=VALUE)*]`. A key is a string without `=` and a value is a string without `,`.
  - Schemes and keys are `text` (keys listed in 1.9) and `sarif` (`file=FILENAME` with default `SOURCE.sarif`, and
    `version=2.1|2.2-prerelease` with default 2.1).
  - Names prefixed "experimental" may change without notice.
  - `set-output` replaces all existing sinks.
  - GCC 16 adds the `experimental-html` scheme. [C16]
- SARIF versions:
  - **2.1.0**, with `$schema` set to
    `https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json`.
  - **2.2-prerelease**, a draft dated 2024-08-08. It writes `"version": "2.2"` with the schema
    `.../refs/tags/2.2-prerelease-2024-08-08/sarif-2.2/schema/sarif-2-2.schema.json`.
  - (source) [SRC:diagnostic-format-sarif.cc] ~2918-2967; [C15].
- SARIF output **includes fix-its**: `result.fixes[]` holds `fix` objects with `artifactChanges` and `replacements`
  (SARIF §3.27.30 and §3.55.3). (source) [SRC:diagnostic-format-sarif.cc] ~1961-1967 and ~3333.
  - `sarif-replay` (GCC 15) replays fix-it hints. [C15]
  - GCC 16 adds `description` to fix objects. [C16]
- Other GCC 15 SARIF additions [C15]:
  - All locations and labelled ranges.
  - Include chains as `locationRelationship`.
  - Embedded URLs in messages.
  - Command-line arguments, start and end timestamps, and the working directory.
  - `rendered` for encoding-sensitive snippets.
  - A crash backtrace in a property bag.
- `-fno-diagnostics-json-formatting` drops the newlines and indentation (added in GCC 14). It "must be passed before the
  option it is to affect". [MSG]; [C14]
- `-fdiagnostics-parseable-fixits` [MSG]:
  - Format: one line per fix-it, after the diagnostic: `fix-it:"FILE":{L1:C1-L2:C2}:"REPLACEMENT"`.
  - The range is half-open, in bytes, with column 1 as the first byte.
  - In the strings, `\\` is a backslash, `\t` a tab, `\n` a newline and `\"` a quote, and other non-printables are
    octal (`\013`).
  - An empty replacement is a deletion. An empty range is an insertion.
  - The env var `GCC_EXTRA_DIAGNOSTIC_OUTPUT=fixits-v1` gives the same byte columns. `fixits-v2` uses display columns.
    The command-line flags take precedence over the env var. [ENV]
- Clang uses the **same textual shape**: `OS << "fix-it:\""; write_escaped(filename); "\":{" BL ':' BC '-' EL ':' EC
  "}:\""; write_escaped(text); "\"\n"`. The end column is one past the end, so the range is half-open, and the columns
  are 1-based bytes from `SM.getColumnNumber`.
  - Clang emits nothing if any hint touches a macro location.
  - Escaping uses LLVM `write_escaped`, which also does `\\`, `\t`, `\n`, `\"` and octal for non-printables.
    **UNVERIFIED**: byte-for-byte equality with GCC's escaping for every character was not checked.
  - https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/clang/lib/Frontend/TextDiagnostic.cpp ~1507-1546.
- `-fdiagnostics-generate-patch` prints fix-its to stderr as a unified diff (`--- f` / `+++ f` / `@@ -42,5 +42,5 @@`).
  It is printed "after any diagnostics are printed" and is coloured by the same rules (`diff-*` caps). [MSG]

## 3. Clang 20/21

- `-fdiagnostics-format=` (cc1) accepts `clang`, `msvc`, `vi`, `sarif` and `SARIF`. Both 20.1.8 and 21.1.0 still emit
  `warning: diagnostic formatting in SARIF mode is currently unstable [-Wsarif-format-unstable]`.
  - https://github.com/llvm/llvm-project/blob/llvmorg-21.1.0/clang/include/clang/Driver/Options.td ~7997-8001.
  - https://github.com/llvm/llvm-project/blob/llvmorg-21.1.0/clang/include/clang/Basic/DiagnosticDriverKinds.td ~818-820
    (same text at llvmorg-20.1.8 ~796).
- `-serialize-diagnostics <file>` / `--serialize-diagnostics` ("Serialize compiler diagnostics to a file") writes a
  bitstream `.dia` file. Options.td at llvmorg-21.1.0, ~6346.
  - Consumer: libclang `clang_loadDiagnostics()` returns a `CXDiagnosticSet`.
    https://github.com/llvm/llvm-project/blob/llvmorg-21.1.0/clang/include/clang-c/CXDiagnostic.h ~93-135.
  - Xcode and the Swift build system consuming `.dia`: **UNVERIFIED** (widely reported, no primary source checked).

## 4. Consumers that parse GCC text

| Consumer | Pattern (verbatim) | `error[some-id]:` | trailing ` [x]` |
|---|---|---|---|
| **VS Code `$gcc`**: *not* in VS Code core. It ships with the C/C++ extension (microsoft/vscode-cpptools `Extension/package.json`, matcher `"name": "gcc"`, owner `cpptools`). VS Code core `problemMatcher.ts` registers only msCompile, gulp-tsc, cpp (MSVC style), csc, vb, lessCompile, jshint*, eslint*, go. | `^(.*?):(\d+):(\d*):?\s+(?:fatal\s+)?(warning\|error):\s+(.*)$` | **No match.** `(warning\|error):` needs the colon right after the word, so the line is ignored. Notes never match either. | Harmless: `(.*)$` absorbs it into the message. |
| **GitHub Actions** ammaraskar/gcc-problem-matcher `gcc_matcher.json` | identical regex to cpptools | **No match** | Harmless |
| **Vim** `runtime/compiler/gcc.vim` (master, which has used `%v` since 2026-05-28) | `%f:%l:%v:\ %trror:\ %m`, `%f:%l:%v:\ %tarning:\ %m`, `%f:%l:%v:\ %m`, `%f:%l:\ %trror:\ %m`, `%f:%l:\ %tarning:\ %m`, `%f:%l:\ %m`, plus `"%f"` forms, make-directory tracking, `make: *** [%f:%l: %m` | `%trror:` fails because a literal `rror:` is required. The line falls through to `%f:%l:%v:\ %m`, so it is still a quickfix entry with the location parsed, but **without type E**, and the message text becomes `error[id]: ...`. | Harmless |
| **Emacs** `compile.el` `gnu` entry | rx: `bol [PROG:] FILE ":" [" "] LINE [("-" ENDLINE ["." ENDCOL]) \| ([.:] COL ["-" [ENDLINE "."] ENDCOL])] ":"`, then `(* " ")` followed by group 6 `FutureWarning\|RuntimeWarning\|Warning\|warning\|W:` (warning), or group 7 `Info\|info\|Information\|information\|Informational\|informational\|I:\|instantiated from\|required from\|Note\|note\|"[ skipping " … " ]"` (info), or `Error\|error`, or a non-digit. Nothing is anchored after the keyword. Separately, `gcc-include` matches `^(In file included \|                 \|\t)from FILE:LINE[:COL][:,]`. | **Still matches.** The keyword is a prefix match, so `error[id]` is an error and `warning[id]` is still a warning. | Harmless |

Sources:

- https://github.com/microsoft/vscode-cpptools/blob/main/Extension/package.json (~line 894)
- https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/tasks/common/problemMatcher.ts (~1516-1626)
- https://github.com/ammaraskar/gcc-problem-matcher/blob/master/gcc_matcher.json
- https://github.com/vim/vim/blob/master/runtime/compiler/gcc.vim
- https://github.com/emacs-mirror/emacs/blob/master/lisp/progmodes/compile.el (~412-416 and ~540-609)

Additional consumer-relevant facts:

- Vim `%v` is a virtual (screen) column, which matches GCC's default `display` column unit. Before 2026-05-28 Vim used
  `%c`. See the gcc.vim header.
- Emacs explicitly treats `required from` and `[ skipping … ]` as info lines. It also skips GCC `-fanalyzer`'s indentation
  of the form `(+ " ") (? "|")`.

## 5. CMake flag-check FAIL_REGEX

- Common patterns, quoted from
  https://github.com/Kitware/CMake/blob/master/Modules/CMakeCheckCompilerFlagCommonPatterns.cmake. The ones relevant to
  GNU are marked "# GNU" in the file:
  - `"[Uu]nrecogni[sz]ed [^\n]*option"` (GNU, NAG, Fujitsu)
  - `"switch [^\n]* is no longer supported"` (GNU)
  - Also in the list: `"unknown [^\n]*option"`, `"optimization flag [^\n]* not supported"`,
    `"unknown argument ignored"`, `"ignoring unknown option"`, `"warning D9002"`, `"option[^\n]*not supported"`,
    `"invalid argument [^\n]*option"`, `"ignoring option [^\n]*argument required"`,
    `"ignoring option [^\n]*argument is of wrong type"`, `"[Uu]nknown option"`, `"[Ww]arning: [Oo]ption"`,
    `"command option [^\n]* is not recognized"`, `"command option [^\n]* contains an incorrect subargument"`,
    `"Option [^\n]* is not recognized.  Option will be ignored."`, `"not supported in this configuration. ignored"`,
    `"File with unknown suffix passed to linker"`, `"[Uu]nknown switch"`, `"WARNING: unknown flag:"`,
    `"Incorrect command line option:"`, `"Warning: illegal option"`, `"[Ww]arning: Invalid suboption"`,
    `"An invalid option [^\n]* appears on the command line"` and `"WARNING: invalid compiler option"`.
- Per-language patterns, quoted from https://github.com/Kitware/CMake/blob/master/Modules/Internal/CheckFlagCommonConfig.cmake:
  - C: `"command[ -]line option [^\n]* is valid for [^\n]* but not for C"` and
    `"-Werror=[^\n]* argument [^\n]* is not valid for C"`.
  - CXX: the same, ending `for C\\+\\+`.
  - OBJC, OBJCXX and Fortran have analogous patterns.
- The GCC 15.2 wordings these regexes target (source):
  - `unrecognized command-line option %qs` [SRC:opts-common.cc] 1618/1650; [SRC:gcc.cc] 3967.
  - `switch %qs is no longer supported` [SRC:opts-common.cc] 1629.
  - `command-line option %qs is valid for %s but not for %s` (a warning) and
    `%<-Werror=%> argument %qs is not valid for %s` [SRC:opts-global.cc] 111-117.
- Note: CMake's check normally also fails on a non-zero exit status. That logic was **UNVERIFIED** here; only the regexes
  were read.

## 6. `#pragma GCC diagnostic` in 15.2

- Kinds are `error`, `warning`, `ignored`, `push`, `pop` and `ignored_attributes`. [PRAGMA]
  - "Not all diagnostics are modifiable; at the moment only warnings (normally controlled by '-W…') can be controlled,
    and not all of them."
  - Pragmas override command-line options.
  - A `pop` with no matching `push` restores the command-line state.
  - `ignored_attributes "vendor::attr"` or `"vendor::"` works like `-Wno-attributes=`, and takes a comma-separated list.
    (source) [SRC:c-family/c-pragma.cc] ~903-935.
- Location semantics: "GCC keeps track of the location of each pragma, and issues diagnostics according to the state as
  of that point in the source file. Thus, pragmas occurring after a line do not affect diagnostics caused by that line."
  [PRAGMA]
  - Implementation: `update_effective_level_from_pragmas` walks the classification history in reverse. It applies the
    latest change whose location is `linemap_location_before_p` the diagnostic's location, skipping popped regions. It
    checks every location in the diagnostic's inlining chain (`m_iinfo.m_ilocs`), so middle-end warnings in inlined code
    honour pragmas at the inlined call sites. (source) [SRC:diagnostic.cc] ~1206-1245.
  - `linemap_compare_locations` resolves macro locations to the **expansion point**. When two tokens come from the same
    expansion, it compares their order within that expansion. So a `_Pragma` inside a macro takes effect at its position
    in the expanded token stream, keyed by the expansion point. (source)
    https://github.com/gcc-mirror/gcc/blob/releases/gcc-15.2.0/libcpp/line-map.cc ~1517-1562.
  - Pragmas inside function bodies are positional by the same mechanism: there is no function-scope special case, only
    a location comparison.
  - The pragma's own recorded location is `input_location`, which has a FIXME: "isn't the best location here".
    [SRC:c-family/c-pragma.cc] ~1016-1020.
  - **UNVERIFIED**: there are historic PRs about `_Pragma` in macros for C++ (for example PR69543 and PR69558), and
    whether any edge cases remain in 15.2 was not checked.
  - The C++ front end also processes the pragma "early", in the preprocessor, for preprocessor-emitted diagnostics such
    as `-Wunknown-pragmas`. (source) c-pragma.cc ~868-876 and ~966.
- Pragma errors are warnings under `-Wpragmas` (source) c-pragma.cc:
  - `unknown option after '#pragma GCC diagnostic' kind`, plus a note `did you mean '-X'?`
  - `'%s' is not an option that controls warnings`
  - `option '%s' is valid for %s but not for %s`
  - `missing option after '#pragma GCC diagnostic' kind`
  - `expected 'error', 'warning', 'ignored', 'push', 'pop', 'ignored_attributes' after '#pragma GCC diagnostic'`
- `#pragma message` prints `FILE:LINE: note: #pragma message: TEXT`, per the manual's example
  `/tmp/file.c:4: note: #pragma message: TODO - Remember to fix this`. `#pragma GCC warning` and `#pragma GCC error` are
  also available. [PRAGMA]
- Unknown `-Wno-X` [WARN]: "no diagnostic is produced for -Wno-unknown-warning unless other diagnostics are being
  produced". An unknown `-WX` is an error.
  - Implementation: unknown `-Wno-*` options are buffered (`postpone_unknown_option_warning`).
    `if (warningcount || errorcount || werrorcount) print_ignored_options ();` then emits, through `inform` (so it is
    never promoted to an error), `note: unrecognized command-line option '-Wno-X' may have been intended to silence
    earlier diagnostics`, at UNKNOWN_LOCATION, so the line is prefixed with `cc1:` or `cc1plus:`. (source)
    [SRC:opts-global.cc] 131-169; [SRC:toplev.cc] 2382-2383.
- `-Werror=foo` implies `-Wfoo`, and `-Wno-error=foo` implies nothing. [WARN]
  - An unknown `-Werror=X` is an error: `'-Werror=X': no option '-WX'`, with an optional `; did you mean '-WY'?`.
    (source) [SRC:opts.cc] ~3705-3719.

## 7. `-fopt-info` and `-fsave-optimization-record`

- The syntax is `-fopt-info`, `-fopt-info-OPTIONS` or `-fopt-info-OPTIONS=FILENAME`, where OPTIONS are `-`-separated
  keywords in any order. [DEV]
  - Kinds: `optimized`, `missed`, `note`, `all`.
  - Verbosity: `internals`.
  - Groups: `ipa`, `loop`, `inline`, `omp`, `vec`, `optall`.
  - The default is `optimized-optall`.
  - Only one `-fopt-info` may name a file. Later ones are ignored, and the file is overwritten for each translation unit.
  - An unknown keyword gives `unrecognized command-line option '-fopt-info-…'`. (source) [SRC:opts-global.cc] 415.
- Output line format: `FILE:LINE:COL: KIND: ` + indentation by dump scope depth + the message. KIND is `optimized`,
  `missed` or `note`. The column is the raw `LOCATION_COLUMN`, and the function decl's location is used when the
  statement location is unknown. (source) [SRC:dumpfile.cc] 454-490. Example: `foo.c:5:3: optimized: loop vectorized ...`
  (the message wording is illustrative and **UNVERIFIED**).
- `-fsave-optimization-record` writes `SRCFILE.opt-record.json.gz` (gzip-compressed JSON). It is "experimental and the
  format ... is subject to change", and roughly a machine-readable `-fopt-info-all`. [DEV]
  - Structure (source) [SRC:optinfo-emit-json.cc]: a top-level array of three elements.
    1. Metadata `{"format":"1","generator":{"name","pkgversion","version","target"}}`.
    2. A pass array (`id`, `type`, `name`, `optgroups`, `num`, `children`).
    3. A records array.
  - Each record has `kind`, `message` (strings and items `{expr|stmt|symtab_node, location}`), `pass`, `count`
    (`{value, quality}`), `location` (`{file, line, column}`), `function`, `inlining_chain` (`{fndecl, site}`),
    `impl_location` (GCC's own source location) and `children` for nested records.
