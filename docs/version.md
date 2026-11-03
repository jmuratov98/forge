# Version [version]

Status: implemented, 2026-11-03.

## 0 Conventions [version.conventions]

1 This document follows the conventions of [stacktrace.conventions] (`docs/stacktrace.md`).
Clauses 1 to 6 are normative; Annex A is informative.

## 1 Scope [version.scope]

1 This document specifies forge's version identifier: where it is recorded, how the build derives
it, and how a program obtains it at run time. It also specifies the bug-report URL that is built
into forge.

2 The policy for when the version changes is outside the scope of this document.

## 2 Terms and definitions [version.defs]

1 The terms *version core* (`X.Y.Z`), *pre-release version* and *build metadata* have the meanings
given in Semantic Versioning 2.0.0, abbreviated *SemVer* below.

**2.1 base version**: a version core, optionally followed by `-` and a pre-release version.

**2.2 build timestamp**: the time, in UTC, written as `YYYYMMDDTHHMMSSZ`.

## 3 The `VERSION` file [version.file]

1 The repository root shall contain a file named `VERSION`. It shall consist of exactly one line,
terminated by a newline character, containing a base version that conforms to SemVer. The line
contains no build metadata and no whitespace.

[Example 1: `0.1.0-dev` — end example]

2 `./x lint` shall check paragraph 1 in its `files` stage.

## 4 Generation [version.gen]

1 When premake generates the build files, it shall read `VERSION`. If the file does not conform to
[version.file] paragraph 1, premake shall fail with a diagnostic that names the file.

2 Premake shall determine the build timestamp as follows: if the environment variable
`SOURCE_DATE_EPOCH` is set, the time it denotes; otherwise the current time.

3 Premake shall accept the option `--bug-report-url=`*url*. Its default is the empty string. If
*url* contains a control character, premake shall fail with a diagnostic.

[Note 1: The option is in its own category, `Forge packaging`, which `./x` does not mirror as a
build option: it is a packager's setting rather than a build variant, and a URL would make a poor
build-directory name. Packagers pass it to premake directly. — end note]

4 Premake shall write the file `generated/forge/core/version.inc` in the build directory, defining
exactly the following macros, each as a narrow string literal:

- (4.1) `FORGE_DETAIL_VERSION_BASE`, the base version from `VERSION`;
- (4.2) `FORGE_DETAIL_VERSION_BUILD`, the build timestamp;
- (4.3) `FORGE_DETAIL_BUG_REPORT_URL`, the value of `--bug-report-url`.

Each `"` and `\` in a value is escaped. Premake rewrites the file only if its contents would change.

5 Only `forge/source/forge/core/version.cpp` shall include `version.inc`. The directory
`generated` in the build directory is an include directory of the `core` component only (of
`libforge` with `--shared`).

[Note 2: As a result, a new build timestamp recompiles a single translation unit. — end note]

6 Premake shall read `VERSION` and check the option only when it generates build files, not for
`forge-describe` or `clean`. `./x` regenerates the build files when `VERSION` changes.

[Note 3: `./x` needs `forge-describe` for its own help, which an invalid `VERSION` should not break.
The build timestamp is therefore the time premake last generated the build files, which `./x` does
only when one of its inputs changes, not at every build. — end note]

## 5 Header `<forge/core/version.hpp>` synopsis [version.syn]

```cpp
#include "forge/core/config.hpp"

#include <string_view>

namespace forge {

[[nodiscard]] FORGE_API std::string_view version() noexcept;
[[nodiscard]] FORGE_API std::string_view bug_report_url() noexcept;

} // namespace forge
```

## 6 Functions [version.api]

```cpp
std::string_view version() noexcept;
```

1 *Returns*: If `FORGE_RELEASE` is 1, the base version. Otherwise, the base version followed by `+`
and the build timestamp.

[Example 1: `0.1.0-dev` in a Release build; `0.1.0-dev+20261102T143005Z` in Debug, RelDeb and
Sanitize builds. — end example]

```cpp
std::string_view bug_report_url() noexcept;
```

2 *Returns*: The value of `--bug-report-url` ([version.gen] paragraph 3), possibly empty.

3 *Remarks*: The strings that both functions return have static storage duration and are followed
by a null character.

## Annex A (informative) Rationale [version.rationale]

1 SemVer gives build metadata no precedence. Two builds that differ only in their timestamp are
therefore the same version. The timestamp only identifies the build.

2 Release builds contain no timestamp, so that building the same sources twice gives the same
binary. `SOURCE_DATE_EPOCH` serves the same purpose for the other configurations.

3 For comparison: rustc reports `rustc X.Y.Z (<commit> <date>)`, and LLVM builds its version from
CMake variables with an optional VCS revision. forge records when a build was made rather than
which commit it was made from.

4 An empty bug-report URL is the default because the repository has no remote yet. Packagers set
the URL in the same way as LLVM's `BUG_REPORT_URL`.
