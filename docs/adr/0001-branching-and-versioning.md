# Branching and versioning

The repo is a bare clone with one worktree per branch.

**Branches.** `main` is trunk: protected, changes land by PR, CI must pass once CI exists.
`feature/*` branches off `main` and merges back by PR. `release/X.Y` is cut from `main`
once per minor line; prerelease and release tags live on it, and `main` immediately bumps
to `X.(Y+1).0`. `hotfix/*` branches off `release/X.Y`, merges back into it by PR, and is
forward-ported to `main`. `research/*` holds wayfinder research findings: pushed, never merged.

**Versions** follow SemVer 2.0.0, single source of truth `project(forge VERSION …)`, starting at 0.1.0.

- Release: `X.Y.Z`, tagged `vX.Y.Z`.
- Prerelease: `X.Y.Z-{alpha|beta|rc}[.{n}]`. The first of each channel has no number
  (`-alpha`), then `-alpha.1`, `-alpha.2`, … The bare form sorts below `.1`.
- Dev build: `X.Y.Z[-{ch}[.{n}]]+dev.{YYYYMMDDHHMMSS}.g{shortsha}`.
  - On `main`: the stage the next version is in, set in CMake: `-alpha`, `-beta`, `-rc`, or
    none (`X.Y.Z+dev…`).
  - On `release/X.Y`: the latest prerelease tag on the branch, e.g. `-rc.2+dev…`.
  - Local builds: `+dev.local`, with no timestamp or SHA, so reconfiguring causes no rebuild.

  Build metadata does not take part in SemVer precedence, so a dev build compares equal to
  the version it carries.

**Version header.** The public, handwritten `forge/version.hpp` declares
`[[nodiscard]] std::string_view version() noexcept;`. CMake generates the private
`version.inc.hpp` into the build tree at configure time; only `version.cpp` includes it, so a
version change recompiles one file. CI passes the timestamp as `FORGE_BUILD_TIMESTAMP`.

## Considered options

- `git describe` as the version source: rejected, tags are absent from source tarballs.
- `-dev` as a prerelease channel: rejected, `dev` sorts between `beta` and `rc`.
- Timestamp regenerated on every build: rejected, it breaks no-op builds.
