# CI runners and host toolchains for 3 OSes x 2 architectures

Research for [#3](https://github.com/jmuratov98/forge/issues/3) (map: [#1](https://github.com/jmuratov98/forge/issues/1)).
Gathered 2026-11-21. Version numbers come from the `actions/runner-images` per-image READMEs at commit
`0e63d4f9` (2026-11-20), image builds of 2026-11-15..18 unless noted. Images are rebuilt weekly, so
treat patch versions as a snapshot: the build system should *detect* versions, not assume them.

## Answer in brief

- **Every cell of {Windows, macOS, Linux} x {x86_64, arm64} has a free, standard GitHub-hosted runner
  for a public repo.** No self-hosted or paid runner is needed.
- **Recommended labels** (pin versions, do not use `-latest`; three `-latest` labels moved in 2026):

  | Cell | Label | Compilers worth testing | CMake | Ninja | Python |
  |---|---|---|---|---|---|
  | Linux x86_64 | `ubuntu-24.04` (or `ubuntu-26.04`) | GCC 12/13/14, Clang 16/17/18 (26.04: GCC 13/14/15, Clang 20/21/22) | 3.31.6 (26.04: 4.5.0) | 1.13.2 | 3.12.3 (26.04: 3.14.4) |
  | Linux arm64 | `ubuntu-24.04-arm` (or `ubuntu-26.04-arm`) | same as x86_64 | same | 1.13.2 | same |
  | macOS arm64 | `macos-15` or `macos-26` | Apple clang (Xcode 16.4 / 26.6 default), Homebrew LLVM 18 / 20, GCC 13/14/15 | 4.5.0 | 1.13.2 | 3.15.2 |
  | macOS x86_64 | `macos-15-intel` or `macos-26-intel` | same as arm64 counterpart | 4.4.2 | 1.13.2 | 3.14.7 |
  | Windows x86_64 (MSVC) | `windows-2025` | MSVC (VS 2026 18.12 today, VS 2027 rolling in), LLVM 20.1.8, clang-cl from VS | 4.5.0 | 1.13.2 | 3.12.10 |
  | Windows arm64 (MSVC) | `windows-11-arm` | MSVC ARM64 (VS 2026 18.12, VS 2027 rolling in), native LLVM 22.1.8 | 4.5.0 | 1.13.2 | 3.13.17 |
  | Windows x86_64 (MinGW) | `windows-2025` + `msys2/setup-msys2` `UCRT64` (GCC) and/or `CLANG64` | MSYS2 packages | MSYS2 pkg | MSYS2 pkg | MSYS2 pkg |
  | Windows arm64 (MinGW) | `windows-11-arm` + `msys2/setup-msys2` `CLANGARM64` | **clang/libc++ only; no native arm64 GCC** | MSYS2 pkg | MSYS2 pkg | MSYS2 pkg |

- **Cost:** standard runners are free and unlimited on public repos. The macOS `-large` (Intel, 12 CPU)
  and `-xlarge` (M2, 5 CPU) labels are *larger runners* and are billed even on public repos; avoid them.
- **Biggest pitfalls:**
  1. The Windows `gcc` on PATH (`C:\mingw64\bin`) is an x86_64 niXman MinGW-builds toolchain on *both*
     Windows images, so on `windows-11-arm` it is emulated and emits x86_64 code. Use MSYS2 instead.
  2. MSYS2 on arm64 runs its Unix tools (bash etc.) under x64 emulation; only `CLANGARM64` binaries are native.
  3. CMake differs across images (3.31.6 on `ubuntu-24.04`/`windows-2022`, 4.4.2-4.5.0 elsewhere).
     Either keep `cmake_minimum_required` at <= 3.31 and avoid 4.x-only features, or install a pinned
     CMake in CI.
  4. Git for Windows on the runners uses the installer's default line-ending option (autocrlf), so
     checked-out test files may become CRLF. Commit a `.gitattributes` that forces LF for tests.
  5. `macos-15-intel` is GitHub's announced *last* x86_64 macOS image, supported "until August 2027".
     The macOS x86_64 cell has a sunset date.

## 1. Runner inventory (labels, availability, cost)

From the runner-images [Available Images table](https://github.com/actions/runner-images/blob/main/README.md#available-images)
and GitHub's [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners):

| Image | Arch | YAML labels | Status (2026-11-21) |
|---|---|---|---|
| Ubuntu 26.04 | x64 | `ubuntu-26.04`, now also `ubuntu-latest` | GA; `ubuntu-latest` migration Oct 19 - Nov 19 2026 ([#14748](https://github.com/actions/runner-images/issues/14748)) |
| Ubuntu 26.04 Arm64 | arm64 | `ubuntu-26.04-arm` | GA ([#14747](https://github.com/actions/runner-images/issues/14747)) |
| Ubuntu 24.04 | x64 | `ubuntu-24.04` | GA |
| Ubuntu 24.04 Arm64 | arm64 | `ubuntu-24.04-arm` | GA |
| Ubuntu 22.04 (+Arm64) | both | `ubuntu-22.04`, `ubuntu-22.04-arm` | deprecating; unsupported by April 2027 ([#14254](https://github.com/actions/runner-images/issues/14254)) |
| macOS 26 Arm64 | arm64 | `macos-latest`, `macos-26`, `macos-26-xlarge` (billed) | GA |
| macOS 26 | x64 | `macos-26-intel`, `macos-26-large`/`macos-latest-large` (billed) | GA ([#13739](https://github.com/actions/runner-images/issues/13739)) |
| macOS 15 Arm64 | arm64 | `macos-15`, `macos-15-xlarge` (billed) | GA |
| macOS 15 | x64 | `macos-15-intel`, `macos-15-large` (billed) | GA; "available from now until August 2027. This will be the last available x86_64 image from Actions" ([#13045](https://github.com/actions/runner-images/issues/13045)) |
| macOS 14 | both | `macos-14` | retired from Actions 2026-11-02 ([#15226](https://github.com/actions/runner-images/issues/15226)) |
| Xcode 27 | arm64 | `xcode-27`, `xcode-27-xlarge` | preview ([#14404](https://github.com/actions/runner-images/issues/14404)) |
| Windows Server 2025 | x64 | `windows-latest`, `windows-2025`, `windows-2025-vs2026` | GA; moving to VS 2027, see below |
| Windows Server 2022 | x64 | `windows-2022` | GA (VS 2022 17.14) |
| Windows 11 Arm64 | arm64 | `windows-11-arm`, `windows-11-vs2026-arm` | GA ([#14592](https://github.com/actions/runner-images/issues/14592)); moving to VS 2027 |

**VS 2027 transition (in flight).** [#15373](https://github.com/actions/runner-images/issues/15373)
(2026-11-20): "Windows Server 2025 and Windows 11 Arm64 images have been upgraded to Visual Studio 2027
and are now available", and the version-specific labels `windows-2025-vs2026` and `windows-11-vs2026-arm`
"will begin deprecation on December 1, 2026". The generic labels `windows-latest`, `windows-2025` and
`windows-11-arm` carry on (now meaning VS 2027). At the snapshot commit the repo has no VS 2027 READMEs yet,
so the MSVC version on those labels is not yet documented. Forge should not depend on an exact MSVC version.

**Specs for public repos** (GitHub docs): Linux and Windows x64/arm64 runners have 4 CPU / 16 GB RAM /
14 GB SSD; macOS Intel has 4 CPU / 14 GB; macOS arm64 has 3 CPU (M1) / 7 GB. Private repos get 2 CPU / 8 GB
on Linux and Windows. The arm64 Linux and Windows runners appear in both the public and private tables.

**Cost.** GitHub docs: "Use of the standard GitHub-hosted runners is free and unlimited on public
repositories." [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions):
"Larger runners are billed for public repositories." The
[larger-runners reference](https://docs.github.com/en/actions/reference/runners/larger-runners) lists the macOS
`-large` (Intel, 12 CPU, 30 GB) and `-xlarge` (M2, 5 CPU, 14 GB) labels as larger runners, and they need a card on file.
For private repos, the per-minute rates are Linux 2-core $0.006 (arm64 $0.005), Windows $0.010, macOS $0.062.

**Other operational notes.**
- Arm64 images are now built and maintained by GitHub instead of Arm Ltd. ([#14100](https://github.com/actions/runner-images/issues/14100)).
- On `windows-11-arm`, the workspace moves to `D:` from 2026-11-30 ([#15314](https://github.com/actions/runner-images/issues/15314)).
  Also, from 2026-11-30 the Windows `D:` drive uses ReFS instead of NTFS ([#15315](https://github.com/actions/runner-images/issues/15315)).
  Use `${{ github.workspace }}` and never hard-code paths.
- The `macos-15` and `macos-26` **Intel** READMEs have not been updated since image build 20260824 (no
  `macos-15/` or `macos-26/` x64 releases since 2026-08-24, while arm64 images update weekly). Toolchain
  versions on Intel macOS lag arm64 (for example CMake 4.4.2 vs 4.5.0, Python 3.14.7 vs 3.15.2).

## 2. Toolchains per image

Exact strings from each image's README (links in the [runner-images README](https://github.com/actions/runner-images/blob/main/README.md#available-images)).

### Linux ([Ubuntu2404](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md), [Ubuntu2404-Arm64](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Arm64-Readme.md), [Ubuntu2604](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2604-Readme.md), [Ubuntu2604-Arm64](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2604-Arm64-Readme.md))

| | 24.04 x64 / arm64 | 26.04 x64 / arm64 |
|---|---|---|
| Clang | 16.0.6, 17.0.6, 18.1.3 | 20.1.8, 21.1.8, 22.1.2 |
| GNU C++ | 12.4.0, 13.3.0, 14.2.0 (default `g++` = 13) | 13.4.0, 14.3.0, 15.2.0 (default `g++` = 15) |
| CMake | 3.31.6 | 4.5.0 |
| Ninja | 1.13.2 | 1.13.2 |
| System Python | 3.12.3 | 3.14.4 |
| Cached Python (setup-python) | 3.11-3.15 | 3.11-3.15 |

The x64 and arm64 images have the same compiler set. The policy is "3 latest major versions" of GCC and Clang
([support policy](https://github.com/actions/runner-images/blob/main/README.md#software-and-image-support)).

### macOS ([macos-15-arm64](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md), [macos-15](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md), [macos-26-arm64](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md), [macos-26](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md))

| | macOS 15 (arm64 / Intel) | macOS 26 (arm64 / Intel) |
|---|---|---|
| Default Xcode | 16.4 (also 16.0-16.4 and 26.0.1-26.3 installed) | 26.6 (also 26.0.1-26.5) |
| Clang/LLVM (Xcode default) | 17.0.0 | 21.0.0 |
| Homebrew LLVM | 18.1.8 (`$(brew --prefix llvm@18)/bin/clang`) | 20.1.8 (`$(brew --prefix llvm@20)/bin/clang`) |
| Homebrew GCC | `gcc-13` 13.4.0, `gcc-14` 14.4.0, `gcc-15` 15.3.0 | same |
| CMake | 4.5.0 (Intel 4.4.2) | 4.5.0 (Intel 4.4.2) |
| Ninja | 1.13.2 | 1.13.2 |
| Python3 | 3.15.2 (Intel 3.14.7) | 3.15.2 (Intel 3.14.7) |

Policy: one Xcode major per macOS version, with all of its minors installed. Select one with
`sudo xcode-select -s /Applications/Xcode_<v>.app` or `DEVELOPER_DIR`.
For Forge's milestone 1 (link and run `aarch64-apple-darwin` objects), `macos-15` or `macos-26` arm64 is the
native execution host.

### Windows ([Windows2025-VS2026](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-VS2026-Readme.md), [Windows11-VS2026-Arm64](https://github.com/actions/runner-images/blob/main/images/windows/Windows11-VS2026-Arm64-Readme.md), [Windows2022](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md))

| | `windows-2025` (VS2026 image) | `windows-11-arm` (VS2026 image) | `windows-2022` |
|---|---|---|---|
| Visual Studio | Enterprise 2026 18.12.12405.243 | Enterprise 2026 18.12.12405.243 | Enterprise 2022 17.14.37906.3 |
| MSVC toolsets | default VS 18.12 toolset (VC++ runtime 14.52.37029); extra `VC.14.44.17.14.x86.x64`, `VC.14.29.16.11` | default (ARM64 + x86.x64 + ARM64EC); extra `VC.14.44.17.14.ARM64` | 14.44 (VS 17.14) |
| Clang in VS | `VC.Llvm.Clang` + `ClangToolset` (clang-cl) | same | same |
| Standalone LLVM | 20.1.8 (Chocolatey) | 22.1.8, **native** `aarch64-pc-windows-msvc` build from llvm-project releases ([Install-LLVM.ps1](https://github.com/actions/runner-images/blob/main/images/windows/scripts/build/Install-LLVM.ps1)) | 20.1.8 |
| `gcc` on PATH | 15.2.0 (niXman x86_64 UCRT) | 14.2.0 (niXman **x86_64** UCRT, emulated) | 14.2.0 |
| CMake | 4.5.0 | 4.5.0 | 3.31.6 |
| Ninja | 1.13.2 | 1.13.2 | 1.13.2 |
| Python | 3.12.10 (cached 3.11-3.15) | 3.13.17 (cached 3.12-3.15) | 3.12.10 |
| Windows SDK | 10.0.26100.0 | 10.0.22621.0, 10.0.26100.0 | 10.0.22621.0, 10.0.26100.0 |
| MSYS2 | `C:\msys64`, not on PATH | `C:\msys64`, not on PATH | `C:\msys64`, not on PATH |

The MSVC compiler version is inferred, not quoted: the READMEs list VS component and redistributable
versions, not `cl.exe` (for VS 18.12 the runtime is 14.52, so `cl` is presumably 19.52). The build should
read `CMAKE_CXX_COMPILER_VERSION` instead. Use `ilammy/msvc-dev-cmd` or `vcvarsall.bat` to put `cl` on
PATH for Ninja builds (with arch `arm64` on `windows-11-arm`).

## 3. MinGW-w64 on Windows runners

**What is preinstalled.** [Install-Mingw64.ps1](https://github.com/actions/runner-images/blob/main/images/windows/scripts/build/Install-Mingw64.ps1)
downloads `niXman/mingw-builds-binaries` for i686 and **x86_64** (posix threads, SEH, `ucrt` runtime per the
toolset) and adds `C:\mingw64\bin` to the machine PATH. The arm64 Packer template
([build.windows-11-vs2026-arm64.pkr.hcl](https://github.com/actions/runner-images/blob/main/images/windows/templates/build.windows-11-vs2026-arm64.pkr.hcl))
runs the same script, so `windows-11-arm` gets an x86_64 toolchain (toolset `"mingw": {"version": "14.*", "runtime": "ucrt"}`).
That toolchain is fine for x86_64. On arm64 it is emulated and builds x86_64 binaries. It also conflicts on PATH
with MSVC and LLVM, so a "MinGW" job should pick its compiler explicitly.

**MSYS2 environments** ([msys2.org/docs/environments](https://www.msys2.org/docs/environments/)):

| Env | Toolchain | Arch | CRT | C++ lib | Status |
|---|---|---|---|---|---|
| UCRT64 | gcc | x86_64 | ucrt | libstdc++ | current; **the recommended default** |
| CLANG64 | llvm | x86_64 | ucrt | libc++ | current |
| CLANGARM64 | llvm | aarch64 | ucrt | libc++ | current |
| MINGW64 | gcc | x86_64 | msvcrt | libstdc++ | deprecated 2026-03-15 |
| CLANG32 / MINGW32 | - | i686 | - | - | removed / being phased out |

**arm64** ([msys2.org/docs/arm64](https://www.msys2.org/docs/arm64/)): support is "preliminary".
"All unixy tools, like bash, will go through x64 emulation, so they might run slower than expected."
`CLANGARM64` is the native environment (e.g. `pacman -S mingw-w64-clang-aarch64-clang`). "Not all packages
in the repo have native builds yet", and ARM64EC is not supported. The docs name no arm64 GCC, so a
"MinGW arm64" cell means clang + libc++ + the mingw-w64 CRT, not GCC.

**Recommended action:** [`msys2/setup-msys2@v2`](https://github.com/msys2/setup-msys2) (latest v2.34.0,
2026-11-21). `msystem:` accepts `MSYS | MINGW64 | MINGW32 | UCRT64 | CLANG64 | CLANGARM64`. The default is
`MINGW64`, which is deprecated and prints a warning, so **always set `msystem` explicitly**. Use
`install`/`pacboy` (e.g. `pacboy: toolchain:p cmake:p ninja:p python:p`) and a `shell: msys2 {0}` step
default. `release: false` reuses the preinstalled `C:\msys64` (faster but stale); the default `true` installs
fresh. `path-type: minimal` (the default) keeps the runner PATH (and its `C:\mingw64\bin`) out. The image
installer itself uses the native `msys2-arm64` installer on arm64
([Install-Msys2.ps1](https://github.com/actions/runner-images/blob/main/images/windows/scripts/build/Install-Msys2.ps1)).

setup-msys2 lists a known problem: if `.gitattributes` does not control line endings, `actions/checkout` may
produce CRLF files that break MSYS2 tools.

## 4. `lit` and pip `filecheck` on Windows

**Packages.** PyPI [`lit`](https://pypi.org/project/lit/) is 23.1.6 (2026-11-17), the same code as
`llvm/utils/lit`. PyPI [`filecheck`](https://pypi.org/project/filecheck/) is 1.0.6 (2026-09-03), requires
Python >= 3.10, and is now [AntonLydike/filecheck](https://github.com/AntonLydike/filecheck), "the successor of
mull-project/FileCheck.py". It passes 95.8% of LLVM's MLIR FileCheck tests. Unimplemented today:
`--implicit-check-not`, `--ignore-case`, `--allow-unused-prefixes`, numeric substitution `[[#...]]`,
`-D#`, `-v/-vv`. Open bugs touch `CHECK-NOT`, `CHECK-LABEL`, `--strict-whitespace` and captures. All Python
versions on the runners satisfy the >= 3.10 requirement.

**Does it work on Windows?** Yes, with caveats; nothing in the sources rules it out:
- **Use lit's internal shell.** `lit.formats.ShTest(execute_external=False)` is the default, and
  `execute_external=True` "is deprected as of LLVM-23 and the option will be removed in LLVM-24"
  ([shtest.py](https://github.com/llvm/llvm-project/blob/main/llvm/utils/lit/lit/formats/shtest.py)). The internal
  shell handles `cd export echo mkdir popd pushd rm ulimit umask :` in-process, `cat`/`diff` as Python
  builtins, and `not`/`env` specially, and it quotes Windows command lines itself
  ([TestRunner.py](https://github.com/llvm/llvm-project/blob/main/llvm/utils/lit/lit/TestRunner.py)). So no bash is needed.
  Other Unix tools (`grep`, `sed`, ...) must be on PATH. The runner installs Git for Windows with
  `/o:PathOption=CmdTools` ([Install-Git.ps1](https://github.com/actions/runner-images/blob/main/images/windows/scripts/build/Install-Git.ps1)),
  which in Git's installer means "Git and optional Unix tools" on PATH, so they are probably present. Still,
  RUN lines should stick to `forge ... | filecheck %s` plus builtins.
- **Executable lookup** honors `PATHEXT` (`lit.util.which`), so `forge` resolves to `forge.exe`.
  Point `config.environment['PATH']` at the build dir, and remember that multi-config generators (VS) put
  binaries in `Release/` or `Debug/` subdirectories.
- **Paths.** `%s`, `%t` etc. expand to backslash paths on Windows. When a path appears in output that
  FileCheck matches, use lit's `%/s`, `%/t` (forward slashes), `%{fs-sep}`, `%{pathsep}`, `%:s` substitutions
  ([lit docs](https://github.com/llvm/llvm-project/blob/main/llvm/docs/CommandGuide/lit.md)), or regex
  `{{[/\\]}}` in check lines. Diagnostics that print source paths are the usual victim. lit also has
  `MAX_PATH` (260) handling in `lit.util`, so keep build dirs shallow.
- **Exit codes.** Windows reports crashes as large or negative codes; lit prints them in hex. `not --crash`
  semantics apply.
- **Parallelism.** lit caps each Windows process pool at 60 workers and uses several pools beyond that
  (`WINDOWS_MAX_WORKERS_PER_POOL = 60`, [run.py](https://github.com/llvm/llvm-project/blob/main/llvm/utils/lit/lit/run.py)).
  This doesn't matter on 4-CPU runners.
- **Line endings.** `filecheck` once failed `CHECK-EMPTY` on `\r\n` input
  ([AntonLydike/filecheck#27](https://github.com/AntonLydike/filecheck/issues/27), closed as fixed 2024-07-30).
  That project's own CI runs only on `ubuntu-latest` with Python 3.10-3.12, so **Windows is untested upstream**.
  Mitigations: (a) a `.gitattributes` with `* text=auto eol=lf` (or `-text` for golden files) so test inputs stay LF
  on Windows checkouts; (b) have `forge` write text output in binary mode (`\n`, not `\r\n`) on all hosts so
  output is byte-identical across hosts. That matters anyway for assembler and textual IR checks.

## 5. Implications for the "Build system" and "CI pipeline shape" decisions

1. **Matrix of 8 jobs, all free:** `ubuntu-24.04` / `ubuntu-24.04-arm` (GCC + Clang), `macos-15` or
   `macos-26` (arm64, Apple clang; the only job that links and runs Mach-O), `macos-15-intel` (until Aug 2027),
   `windows-2025` MSVC, `windows-11-arm` MSVC, `windows-2025` MSYS2 UCRT64, `windows-11-arm` MSYS2 CLANGARM64.
2. **Lowest common toolchain floor** across the default compilers: GCC 13 (24.04 default) / GCC 14 (Windows niXman
   on arm), Clang 16 (oldest on 24.04), Apple clang 17 (Xcode 16.4), MSVC 14.44+ (VS 17.14+). All have
   usable C++20 language support. C++20 *library* gaps (for example in Apple's libc++) should be checked
   when the source tree is designed. That is not verified here.
3. **CMake floor:** 3.31 if Forge relies on the preinstalled CMake (`ubuntu-24.04` and `windows-2022` ship
   3.31.6); everything else has 4.4+. Ninja 1.13.2 is everywhere (except MSYS2, which has its own).
4. **Python:** >= 3.12 is everywhere natively (3.13 on Win arm64). `pip install lit filecheck` works without
   pinning a Python version.
5. **Pin image labels** and plan for churn: `ubuntu-latest` moved to 26.04 (Nov 2026), `windows-latest` and
   `windows-11-arm` are moving to VS 2027 (labels `*-vs2026*` deprecated from 2026-12-01), and `macos-latest`
   moved to 26 (June 2026).
