# Host APIs for an error message without allocating

Research for [#6](https://github.com/jmuratov98/forge/issues/6), a child of the map
[#4](https://github.com/jmuratov98/forge/issues/4) ("Design a minimalist allocation-free
`forge::error`"). Gathered 2026-11-05. This file reports facts and trade-offs. It does not choose
the message API; the grilling ticket "What is the error's message API?" does.

## Question

Can every host produce the message for a native error code (an `errno` value on POSIX, a Win32
error code on Windows) without allocating, into a bounded buffer? If so, what is the bound?

## Short answer

Yes on every host, but each host gives a different guarantee, and the bound depends on whether the
message is localized.

- **glibc.** `strerrordesc_np` (glibc 2.32 or later) returns a pointer to a static, untranslated
  English string, or `NULL` for an unknown code. The glibc manual marks it MT-Safe, AS-Safe and
  AC-Safe. `strerror_r` translates the message through gettext. The manual marks it AS-Unsafe for
  that reason, and gettext may take locks and call `malloc`.
- **musl.** `strerror_r` copies a string from a static table into the caller's buffer. It neither
  allocates nor locks (read from the source).
- **macOS.** Apple Libc's `strerror_r` copies from the static `sys_errlist`, or formats
  `Unknown error: N` on the stack. It neither allocates nor locks: the source shows this, and a
  measurement on macOS 15.6 confirms it.
- **Windows.** `FormatMessageW` without `FORMAT_MESSAGE_ALLOCATE_BUFFER` writes into the caller's
  buffer. A buffer that is too small makes the call fail; it does not truncate. Microsoft does not
  document whether the call allocates internally, takes locks, or is thread-safe. Converting
  UTF-16 to UTF-8 is easy to do in forge's own code with no allocation.

**Bounds** are in bytes of UTF-8 and exclude the terminating NUL:

| Host | Untranslated (English) maximum | Unknown code | Localized maximum |
| --- | --- | --- | --- |
| glibc 2.44 | 49 (`EILSEQ`) | `Unknown error -2147483648`: 25 | 148 in glibc's own catalogs (Georgian, `ELIBEXEC`); unknown codes 52. Distributions' catalogs are not bounded by glibc. |
| musl 1.2.6 | 40 (`EAFNOSUPPORT`) | `No error information`: 20, with return value 0 | Comes from whatever catalog `MUSL_LOCPATH` names, so there is no bound. |
| Apple Libc 1752 | 47 (`EAFNOSUPPORT`) | `Unknown error: -2147483648`: 26 | Never translated, because the build does not define `NLS`. |
| Windows, Win32 codes | 460 UTF-16 code units, all ASCII, line breaks included (`ERROR_CLUSTER_UPGRADE_FIX_QUORUM_NOT_SUPPORTED`, 5974) | No text; the call fails | Not measured. At most 3 UTF-8 bytes per UTF-16 unit. The output buffer is documented to be at most 64 KB. |
| Windows UCRT `strerror_s` (`errno`) | 35 (`Inappropriate I/O control operation`); the UCRT's own constant is 38 with the NUL | `Unknown error`: 13 | Never translated. |

So 64 bytes holds every untranslated POSIX message, and 512 bytes holds every English Win32
message in the current SDK. No host gives a bound once localized text is allowed. Windows offers
no "English only" mode that is guaranteed to work (see 2.1.2).

## 1 POSIX

### 1.1 The two `strerror_r` functions

- **POSIX (XSI) form:** `int strerror_r(int errnum, char *strerrbuf, size_t buflen)`.
  - It returns 0 on success.
  - It returns `ERANGE` if the buffer is too small. POSIX.1-2024 made `ERANGE` a "shall fail"
    error (Austin Group Defect 398).
  - It returns `EINVAL` for an unknown code. In that case the buffer should still hold a message
    that "shall indicate that an unknown error occurred".
  - POSIX only encourages implementations to NUL-terminate the buffer on `ERANGE`.
  - Source: [POSIX.1-2024 `strerror`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/strerror.html).
- **GNU form:** `char *strerror_r(int errnum, char *buf, size_t buflen)`.
  - It returns either a pointer to an immutable static string, leaving `buf` unused, or `buf`.
  - Source: [glibc `string/string.h`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/string.h;hb=glibc-2.44)
    lines 453–478 and the
    [glibc manual](https://sourceware.org/git/?p=glibc.git;a=blob;f=manual/errno.texi;hb=glibc-2.44)
    lines 1197–1218.

**Which form you get.**

- glibc declares the XSI form, as an alias of `__xpg_strerror_r`, when
  `__USE_XOPEN2K && !__USE_GNU`; otherwise it declares the GNU form (`string.h` lines 460–478).
  The [man page](https://man7.org/linux/man-pages/man3/strerror.3.html) states the condition as
  `(_POSIX_C_SOURCE >= 200112L) && ! _GNU_SOURCE`.
- **C++ on Linux always gets the GNU form.** g++ always predefines `_GNU_SOURCE` on GNU/Linux
  ([libstdc++ FAQ 4.3](https://gcc.gnu.org/onlinedocs/libstdc++/faq.html#faq.predefined)), and so
  does Clang for any C++ Linux target
  ([`OSTargets.h` L380–381 at llvmorg-23.1.5](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/clang/lib/Basic/Targets/OSTargets.h#L380-L381)).
- musl declares only the XSI form
  ([`include/string.h`](https://git.musl-libc.org/cgit/musl/tree/include/string.h?h=v1.2.6)
  line 66), and so does macOS (`_string.h` in the SDK).

**Telling which form you got.** Both libc++ and libstdc++ overload a helper on the return type:
one overload takes `int`, the other `char*`, and overload resolution picks the right one at compile
time.

- libc++: `handle_strerror_r_return`,
  [system_error.cpp L162–208](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/libcxx/src/system_error.cpp#L162-L208).
- libstdc++: `use_strerror_result`,
  [system_error.cc L49–92](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libstdc%2B%2B-v3/src/c%2B%2B11/system_error.cc#L49-L92).
- glibc also exports the XSI function under the name `__xpg_strerror_r` (symbol version
  GLIBC_2.3.4, [`string/Versions`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/Versions;hb=glibc-2.44)).
  The name is reserved to the implementation.

**What POSIX says about signals.** POSIX.1-2024 §2.4.3
([V2_chap02 `tag_16_04_03`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/V2_chap02.html#tag_16_04_03))
lists the functions that are async-signal-safe.

- Not in the list: `strerror`, `strerror_l`, `strerror_r` and `snprintf`.
- In the list: `memcpy`, `strlen`, `strnlen`, `stpcpy`, `strlcpy` and `strlcat`.

POSIX also requires `strerror_l` to be thread-safe, but `strerror` need not be.

### 1.2 glibc

All glibc references are to tag `glibc-2.44` (commit `c3a3a9808ad3`).

**`strerror_r`, GNU form** ([`string/_strerror.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/_strerror.c;hb=glibc-2.44)):

- For a known code it returns `_(err)`, which is `dcgettext` on the static English string. It never
  copies into `buf`, so the caller must copy.
- For an unknown code it runs `__snprintf(buf, buflen, "%s%d", _("Unknown error "), errnum)`, which
  truncates, and returns `buf`.

**`strerror_r`, XSI form** ([`string/xpg-strerror.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/xpg-strerror.c;hb=glibc-2.44)):

- It calls the GNU form.
- If that returned `buf`, the code is unknown, and the function returns `EINVAL` with
  `Unknown error N` already in `buf`.
- Otherwise it copies `min(buflen-1, len)` bytes, NUL-terminates, and returns `ERANGE` if the
  message was truncated.

**`strerror` and `strerror_l`** ([`string/strerror_l.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/strerror_l.c;hb=glibc-2.44)):

- For an unknown code they call `free` and then `__asprintf` into a per-thread buffer, so they
  allocate.
- The man page notes that `strerror` was not MT-Safe before glibc 2.32.

**`strerrordesc_np` and `strerrorname_np`** ([`string/strerrordesc_np.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/strerrordesc_np.c;hb=glibc-2.44),
[`stdio-common/errlist.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=stdio-common/errlist.c;hb=glibc-2.44)):

- They are a bounds-checked index into `_sys_errlist_internal`, and return `NULL` when the code is
  out of range.
- Added in GLIBC_2.32 (`string/Versions`), declared under `_GNU_SOURCE`.
- The manual says (`errno.texi` L1287–1310):
  - `strerrordesc_np` returns a string that "is not translated, and the returned string does not
    change for the remaining execution of the program".
  - Both functions are marked `@mtsafe @assafe @acsafe`.
  - The man page adds: "strerrorname_np() and strerrordesc_np() are thread-safe and
    async-signal-safe."
- The longest name is 15 bytes (`ENOTRECOVERABLE`, `EPROTONOSUPPORT`, `ESOCKTNOSUPPORT`).

**Safety notes in the glibc manual** (`errno.texi` L1156–1222, `intro.texi` L429–436):

- `strerror_r` (both forms) is `MT-Safe | AS-Unsafe i18n | AC-Unsafe`.
- `strerror` and `strerror_l` are `AS-Unsafe heap i18n`.
- The `i18n` note means "may call internationalization functions of the gettext family". It is
  defined as equivalent to `AS-Unsafe corrupt heap dlopen`.
- In [`intl/dcigettext.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=intl/dcigettext.c;hb=glibc-2.44),
  `dcgettext` always takes `__libc_setlocale_lock`, `_nl_state_lock` and `tree_lock` as read
  locks (L450–487), even in the C locale. It `malloc`s on a cache miss (L557, L567, L664).

**Longest message.** These figures come from
[`sysdeps/gnu/errlist.h`](https://sourceware.org/git/?p=glibc.git;a=blob;f=sysdeps/gnu/errlist.h;hb=glibc-2.44)
(153 entries) and the 40 `po/*.po` catalogs in glibc 2.44, ignoring fuzzy entries.

- English: 49 bytes, `Invalid or incomplete multibyte or wide character` (`EILSEQ`). Next come
  `ELIBMAX` (47) and `EBACKGROUND` (46, Hurd only).
- Translated: at most 148 bytes, which is 52 characters of Georgian (`po/ka.po`, `ELIBEXEC`),
  followed by Ukrainian at 145 bytes.
- The translated `Unknown error ` prefix is at most 41 bytes (`ka`). With `-2147483648` appended,
  that makes 52 bytes.
- These numbers bound only glibc's own catalogs. Distributions ship their own language packs, and a
  program can bind any catalog.

`strerrordesc_np` needs glibc 2.32, which was released in 2020. `docs/stacktrace.md` already names
glibc 2.35 as the version from which stack capture is signal-safe. I did not check the glibc
version of each CI image (Ubuntu 24.04/26.04 runners, the `gcc:16.2` container).

### 1.3 musl

All musl references are to tag `v1.2.6` (commit `9fa28ece75d8`).

- [`src/string/strerror_r.c`](https://git.musl-libc.org/cgit/musl/tree/src/string/strerror_r.c?h=v1.2.6)
  calls `strerror` and then `memcpy`s the result. On truncation it NUL-terminates and returns
  `ERANGE`. It never returns `EINVAL`. It is also exported as `__xpg_strerror_r`.
- [`src/errno/strerror.c`](https://git.musl-libc.org/cgit/musl/tree/src/errno/strerror.c?h=v1.2.6)
  looks the code up in a static table of offsets.
  - Any code outside the table, negative codes included because the comparison is unsigned, maps
    to entry 0, `No error information`.
  - It then calls `LCTRANS(s, LC_MESSAGES, loc)`.
- [`src/locale/locale_map.c`](https://git.musl-libc.org/cgit/musl/tree/src/locale/locale_map.c?h=v1.2.6)
  L15–20 and
  [`__mo_lookup.c`](https://git.musl-libc.org/cgit/musl/tree/src/locale/__mo_lookup.c?h=v1.2.6)
  show that translation is a binary search over a `.mo` file that `setlocale` mapped earlier. It
  takes no lock and does not allocate. Without a catalog the English string is returned.
- Longest English message: 40 bytes, `Address family not supported by protocol`
  ([`src/errno/__strerror.h`](https://git.musl-libc.org/cgit/musl/tree/src/errno/__strerror.h?h=v1.2.6),
  95 entries).
- musl does not document thread-safety or AS-safety for these functions. Reading the source, they
  have no mutable shared state and call only `strlen` and `memcpy`.

### 1.4 macOS (Apple Libc)

All references are to tag `Libc-1752.120.2`.

**Source.**
[`string/FreeBSD/strerror.c`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/string/FreeBSD/strerror.c):

- `strerror_r` does `strlcpy(strerrbuf, sys_errlist[errnum], buflen)` and returns `ERANGE` if the
  message was truncated.
- For `errnum < 0 || errnum >= sys_nerr` it builds `Unknown error: N` in a stack array of 35
  bytes (`EBUFSIZE`), copies it with `strlcpy`/`strlcat`, and returns `EINVAL`.
- The catalog path (`catopen`/`catgets`) is compiled only `#if defined(NLS)`.
  [`xcodescripts/libc.xcconfig`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/xcodescripts/libc.xcconfig)
  L65–70 do not define `NLS`, and no other xcconfig or the project file does either. So
  `strerror_r` never translates.
- `strerror` (not `strerror_r`) `calloc`s a shared `NL_TEXTMAX` buffer the first time it sees an
  unknown code. That buffer is process-wide, so `strerror` is not thread-safe for unknown codes.

**Table.**
[`gen/errlst.c`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/gen/errlst.c):

- 108 entries (0–107). The longest is `Address family not supported by protocol family`
  (`EAFNOSUPPORT`), 47 bytes.
- Entry 0 is `Undefined error: 0`.
- `sys_errlist`/`sys_nerr` are still declared in the SDK's `_stdio.h` (lines 468–469), and the
  man page calls them deprecated.

**Signal safety.** Apple's
[`sigaction(2)`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/bsd/man/man2/sigaction.2)
L430–441 lists `strcpy`, `strcat`, `strncpy`, `strncat`, `strlcpy` and `strlcat` as
async-signal-safe. `strerror_r` is not listed.

**Measured** on macOS 15.6 (24G84) with Apple clang 17.0.0
(probe sources in the session scratchpad; not committed):

- `strerror_r(-1, …)` gives `EINVAL` and `Unknown error: -1`. `INT_MIN` gives `EINVAL` and
  `Unknown error: -2147483648` (26 bytes). `ENOENT` into 8 bytes gives `ERANGE` and `No such`,
  NUL-terminated.
- Codes 0–107 are known. The longest is 47 bytes.
- 7,001 calls (codes −2000 to 4999, then `INT_MIN`) left `malloc_zone_statistics`
  `blocks_in_use`/`size_in_use` unchanged (188 / 9248).

## 2 Windows

### 2.1 `FormatMessageW` into a fixed buffer

The call is `FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, nullptr,
code, lang, buf, n, nullptr)`. Source:
[FormatMessageW, Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-formatmessagew).

- Without `FORMAT_MESSAGE_ALLOCATE_BUFFER`, *nSize* is "the size of the output buffer, in
  TCHARs".
- "The output buffer cannot be larger than 64K bytes", which is at most 32,768 `WCHAR`s.
- On success it returns the number of `TCHAR`s stored, not counting the NUL. On failure it returns
  0 and sets `GetLastError`.
- Security remark: "it is unsafe to take an arbitrary system error code returned from an API and
  use FORMAT_MESSAGE_FROM_SYSTEM without FORMAT_MESSAGE_IGNORE_INSERTS".

#### 2.1.1 When the buffer is too small

The Learn page does not say. Microsoft's own code treats it as a failure with
`ERROR_INSUFFICIENT_BUFFER`. In .NET's
[`Interop.FormatMessage.cs`](https://github.com/dotnet/runtime/blob/v10.0.0/src/libraries/Common/src/Interop/Windows/Kernel32/Interop.FormatMessage.cs#L42-L71)
(v10.0.0), the runtime first formats into a 256-`char` stack buffer. If `GetLastError` is
`ERROR_INSUFFICIENT_BUFFER`, it calls again with `FORMAT_MESSAGE_ALLOCATE_BUFFER`. There is no
documented truncate-and-succeed mode. A caller that must not allocate therefore has to supply a
buffer at least as large as the longest message it can meet. Whether a partial string is left in
the buffer on failure is undocumented.

#### 2.1.2 Language

*dwLanguageId* works as follows:

- With a specific LANGID, "FormatMessage will return a message for that LANGID only". If none
  exists, the call fails with `ERROR_RESOURCE_LANG_NOT_FOUND`.
- With 0, it searches in this order: language neutral, the thread LANGID, the user default, the
  system default, US English, and then "any language message string that is present".
- `MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT)` (= `LANG_USER_DEFAULT`, 0x0400) means "User default
  language"
  ([MAKELANGID, Learn](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-makelangid)).
  Learn does not say whether FormatMessage treats it as a specific LANGID or applies the fallback
  chain that 0 gets.
- Learn also says that LANGID constants "are deprecated and their use is discouraged".

The MSVC STL shows what goes wrong in practice:

- [STL#3254](https://github.com/microsoft/STL/issues/3254): passing the *system default* LANGID
  made `system_category().message()` return `unknown error` on machines whose system locale had no
  installed message table (en-GB, ar-EG).
- [STL#2451](https://github.com/microsoft/STL/issues/2451): `FormatMessageA` converts to the ANSI
  code page, so a user language that the system code page cannot encode came out as `???`.
- STL 17.14 now tries en-US (0x0409), then the system default language, then 0 (see 3.3).

So "English if possible" takes more than one call, and the fallback returns localized text.

#### 2.1.3 Trailing CRLF and period

- With the low-order byte of *dwFlags* at 0, "the function stores line breaks that are in the
  message definition text into the output buffer". Message-compiler text ends at a line holding
  only `.`, and `%0` "terminate[s] the message itself without a trailing new line character"
  ([Message Text Files, Learn](https://learn.microsoft.com/en-us/windows/win32/eventlog/message-text-files)).
  So a system message normally ends in CRLF.
- `FORMAT_MESSAGE_MAX_WIDTH_MASK` (0xFF) "ignores regular line breaks". Learn does not say what
  replaces them.
- In SDK 10.0.28000's `winerror.h`:
  - no Win32 message ends in `%0`;
  - 3,073 of 3,194 end with a period;
  - 132 span more than one line, so a message can contain CRLFs in the middle, not only at the
    end.
- What the standard libraries strip from the end:
  - The MSVC STL strips trailing space, `\t`, `\r`, `\n` and `\0`, but keeps the period.
  - libc++ (Win32) strips trailing space, `\r` and `\n`.
  - libstdc++ (MinGW, GCC 16) strips `\r\n` and then one `.`.
  - .NET strips every trailing character `<= 0x20`.

#### 2.1.4 Whether FormatMessage allocates internally

Undocumented. The Learn page mentions `LocalAlloc` only for `FORMAT_MESSAGE_ALLOCATE_BUFFER`. It
says nothing about heap use, locks, loader activity or thread-safety when the caller supplies the
buffer. System message tables are resources, and Learn calls FormatMessage MUI-aware. Nothing
primary says whether loading them allocates or takes the loader lock. **Not verified.**

#### 2.1.5 Unknown codes

The Learn page names no error code for a message ID that has no text; it names only
`ERROR_RESOURCE_LANG_NOT_FOUND` for the language case. `winerror.h` defines
`ERROR_MR_MID_NOT_FOUND` (317), "The system cannot find message text for message number 0x%1 in the
message file for %2.", which is presumably what callers see. **Not verified.**

#### 2.1.6 Longest system message

Measured over the `// MessageText:` comments of
[`winerror.h`](https://www.nuget.org/packages/Microsoft.Windows.SDK.CPP/10.0.28000.2957) in the
Windows SDK 10.0.28000.2957 NuGet package (`c/Include/10.0.28000.0/shared/winerror.h`). Learn
states that the message compiler puts the same text into the message binary and into the header's
comment block.

- **Win32 codes** (3,194 entries, all ASCII):
  - The longest is `ERROR_CLUSTER_UPGRADE_FIX_QUORUM_NOT_SUPPORTED` (5974): 450 characters on 5
    lines, so 460 UTF-16 units with CRLFs.
  - Next comes `ERROR_TRANSACTIONMANAGER_NOT_ONLINE` (6719): 416 characters on one line, 418 with
    CRLF.
  - Median 63, 99th percentile 277; 39 messages are longer than 256 units and none longer than 512.
  - 45 messages contain `%N` inserts, which pass through unchanged with `IGNORE_INSERTS`.
- **HRESULT and other codes** in the same file (4,012): the longest is
  `TBS_E_PROVISIONING_NOT_ALLOWED`, 671 units.
- **Localized message tables were not measured**, because that needs a Windows machine with
  language packs. Learn's System Error Codes pages
  ([MicrosoftDocs/win32 `51c9b7c`](https://github.com/MicrosoftDocs/win32/tree/51c9b7cc54ef393b6406c8320a7840fdd88209d5/desktop-src/Debug))
  sometimes add a second paragraph that is not part of the message; for example, entry 1290 runs
  to 614 characters there but is 378 in `winerror.h`. Use `winerror.h`, not the web pages.
- An embedded English table for all Win32 codes would hold about 235 KB of text.

### 2.2 UTF-16 to UTF-8 without allocating

[WideCharToMultiByte, Learn](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte):

- **Flags.** With `CP_UTF8`, *dwFlags* must be 0 or `WC_ERR_INVALID_CHARS`, and
  *lpDefaultChar*/*lpUsedDefaultChar* must be `NULL`.
- **Sizing.** `cbMultiByte = 0` returns the required size and writes nothing. A buffer that is too
  small gives 0 and `ERROR_INSUFFICIENT_BUFFER`.
- **Partial writes.** The Remarks say that if *cbMultiByte* is less than *cchWideChar*, the
  function writes *cbMultiByte* characters anyway, so a failed call can leave a partial sequence
  in the buffer.
- **Invalid input.** Without `WC_ERR_INVALID_CHARS`, unpaired surrogates become U+FFFD.
- **Safety.** Learn says nothing about allocation or thread-safety.

The conversion also needs no Windows API at all. UTF-8 uses at most 3 bytes for a BMP code point
(1 UTF-16 unit) and 4 bytes for a supplementary one (2 units)
([Unicode Standard ch. 3, D92](https://www.unicode.org/versions/latest/core-spec/chapter-3/)). So a
UTF-8 result takes at most 3 bytes per UTF-16 unit, and a hand-written encoder over a fixed buffer
is a short loop with no state, locale or allocation.

Using `FormatMessageA` instead depends on the process code page. It is UTF-8 only when the manifest
sets `activeCodePage` to UTF-8, on Windows 1903 or later
([Use UTF-8 code pages, Learn](https://learn.microsoft.com/en-us/windows/apps/design/globalizing/use-utf8-code-page)).
Otherwise characters can be lost (STL#2451).

### 2.3 `errno` values on Windows (UCRT)

The UCRT source ships in the same SDK package.

- `c/Source/10.0.28000.0/ucrt/misc/strerror.cpp`:
  - `strerror_s` copies from a static English table with `strncpy_s(..., _TRUNCATE)` and reports
    truncation as success: `STRUNCATE` maps to 0.
  - `strerror` `calloc`s a per-thread buffer the first time it runs.
- `ucrt/misc/syserr.cpp`: the table is `_sys_errlist` (0–43) plus `_sys_posix_errlist` (100–141).
  An unknown code gives `Unknown error`.
- `ucrt/inc/corecrt_internal.h` L155: `max_system_error_message_count = 38` (with the NUL). The
  longest message is `Inappropriate I/O control operation` (35).
- [Learn](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/strerror-s-strerror-s-wcserror-s-wcserror-s):
  "The **strerror_s** function is thread-safe". A null buffer or a size of 0 invokes the invalid
  parameter handler.

## 3 Standard libraries

Every implementation below returns `std::string`, so every one of them allocates for a message
longer than its small-string buffer. Their buffer sizes, fallbacks and stripping rules are the
data points for forge.

### 3.1 libstdc++

Files:
[`src/c++11/system_error.cc` at gcc-16.2.0](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libstdc%2B%2B-v3/src/c%2B%2B11/system_error.cc#L95-L186),
and [at gcc-13.1.0](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.1.0/libstdc%2B%2B-v3/src/c%2B%2B11/system_error.cc#L68-L119).

**GCC 13.3 and later (including 13.5, 14 and 16):**

- `generic_category()` and `system_category()` (POSIX) both call `strerror_string`.
- `strerror_string` uses `__resize_and_overwrite`, starting at 60 bytes, and calls `strerror_r`.
- On a GNU-form result that is longer than the buffer, it retries at that length. On an XSI
  `ERANGE`, it retries at double the size.
- An XSI `EINVAL` with an empty buffer becomes `Unknown error`.
- This is [PR 110133](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=110133). The change landed on
  trunk on 2023-11-04 and was backported to the 13 branch on 2023-12-06, per the gcc-13.5.0
  `libstdc++-v3/ChangeLog`.

**GCC 13.1:** both categories return `string(strerror(i))`, with the comment
`XXX locale issues`.

**Windows (MinGW)**, which forge does not target:

- `system_category()` uses `FormatMessageA(FROM_SYSTEM | ALLOCATE_BUFFER [| IGNORE_INSERTS in
  16.2], …, LANG_USER_DEFAULT, …)` and then strips `\r\n` and one `.`.
- If the call fails, it returns `Unknown error code`.

### 3.2 libc++

File:
[`src/system_error.cpp` at llvmorg-23.1.5](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/libcxx/src/system_error.cpp#L144-L304).
The same logic is in llvmorg-17.0.1.

- **POSIX path:**
  - `do_strerror_r` calls `strerror_r` into a 1024-byte stack buffer (`strerror_buff_size`).
  - It saves and restores `errno`.
  - It maps an XSI `EINVAL` to `""` and then formats `Unknown error %d` with `snprintf`. On macOS,
    this replaces libc's `Unknown error: N` with `Unknown error N`.
  - On `ERANGE` it calls `std::abort()`.
  - Without threads it uses `strerror`.
- **ELAST cap.** `generic_category` and `system_category` return
  `unspecified generic_category error` / `unspecified system_category error` for
  `ev > _LIBCPP_ELAST`
  ([`config_elast.h`](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/libcxx/src/include/config_elast.h)).
  `_LIBCPP_ELAST` is `ELAST` (106 in the macOS SDK), 4095 on Linux/musl, and `_sys_nerr - 1` for
  MSVCRT-like libcs.
  - On macOS 15.6 this means code 107 (`ENOTCAPABLE`, which libc knows) and `INT_MAX` both give
    the "unspecified" text, while −1 gives `Unknown error -1`. All three were measured.
- **Win32 path:**
  - `FormatMessageA(ALLOCATE_BUFFER | FROM_SYSTEM | IGNORE_INSERTS, …, lang 0, …)`, with trailing
    space, `\r` and `\n` stripped.
  - If the call fails, it returns `Unknown error`.
  - The MSVCRT-like generic path uses `strerror_s` into 1024 bytes, else `unknown error %d`.

### 3.3 MSVC STL

All references are to tag `vs-2022-17.14`, the release of MSVC 19.44, which is forge's floor.
`syserror_import_lib.cpp` is unchanged on `main` at `e1ed302`.

- **`generic_category().message()`**
  ([`stl/inc/system_error` L534–545](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/inc/system_error#L534-L545)):
  - It returns `_Syserror_map(code)`
    ([`stl/src/syserror.cpp` L236–244](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/src/syserror.cpp#L236-L244)).
  - That is a linear search of a static table of 78 lower-case `errc` names, such as
    `no such file or directory`, falling back to `unknown error`.
  - The longest entry is 34 bytes (`inappropriate io control operation`).
  - The only allocation is the `std::string`.
- **`system_category().message()`**
  ([`stl/inc/system_error` L566–585](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/inc/system_error#L566-L585),
  [`stl/src/syserror_import_lib.cpp` L38–72](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/src/syserror_import_lib.cpp#L38-L72)):
  - It calls `FormatMessageA(ALLOCATE_BUFFER | FROM_SYSTEM | IGNORE_INSERTS)` up to three times:
    first with LANGID 0x0409 (en-US), then with the system default language from
    `GetLocaleInfoEx(LOCALE_NAME_SYSTEM_DEFAULT, LOCALE_ILANGUAGE | LOCALE_RETURN_NUMBER)`, then
    with 0.
  - It then strips trailing whitespace and `\0`, and frees the buffer with `LocalFree`. If every
    attempt fails, it returns `unknown error`.
  - The source comment gives the reason for asking for en-US first: "This is consistent with
    generic_category(), which uses a table of US English strings in the STL." The history is in
    STL#2451, STL#3254 and the fix that closed #3254,
    [STL#5104](https://github.com/microsoft/STL/pull/5104).

## 4 Safety

forge's specs show where a message could be needed in signal context:

- `docs/crash_context.md` [context.dump]: the dump handler only increments a lock-free atomic
  counter, and "no printing or symbolization runs in signal context".
- `docs/stacktrace.md` [stacktrace.scope] (2.1) leaves signal and SEH handlers out of scope.
- [stacktrace.report] p3 requires that nothing is allocated before the first report lines are
  written.

So a future crash handler that wants to print an error message from inside the handler needs one
of the AS-safe paths below.

| Call | Thread-safe | Async-signal-safe | Basis |
| --- | --- | --- | --- |
| glibc `strerrordesc_np`, `strerrorname_np` | Yes | **Yes** | Documented: glibc manual and man page. |
| glibc `strerror_r` (GNU or XSI) | Yes | No: gettext takes locks, may `malloc`/`dlopen` | Documented: glibc manual `AS-Unsafe i18n`; source. |
| glibc `strerror`, `strerror_l` | Yes (`strerror` since 2.32) | No (heap, i18n) | Documented: glibc manual. |
| musl `strerror_r` | Yes, by inspection | Yes, by inspection: no lock, no allocation; `memcpy`/`strlen` only | Source only; musl documents neither. |
| Apple `strerror_r` | Yes, by inspection | Yes, by inspection: `strlcpy`/`strlcat` (which Apple's `sigaction(2)` lists as safe) and a stack buffer | Source and measurement; not in Apple's AS-safe list. |
| Apple `sys_errlist[e]` for `0 <= e < sys_nerr` | Yes (read-only) | Yes (a load) | Source; deprecated interface. |
| POSIX `strerror_r` in general | Not required | Not in the POSIX.1-2024 AS-safe list | POSIX §2.4.3. |
| `FormatMessageW` | Undocumented | Undocumented; may load resources | Learn says nothing. |
| `WideCharToMultiByte` | Undocumented | Undocumented | Learn says nothing. |
| A hand-written UTF-16→UTF-8 encoder | Yes | Yes | By construction. |
| UCRT `strerror_s` | Yes (documented) | Undocumented; the source is a table lookup plus `strncpy_s` | Learn; UCRT source. |

Windows has no POSIX asynchronous signals. A crash handler there is an SEH filter running on the
faulting thread, which may hold the heap lock or the loader lock. Nothing primary says whether
`FormatMessageW(FROM_SYSTEM)` needs either.

## 5 Per-host table

| Host | API | Buffer bound (UTF-8 bytes, no NUL) | Thread-safe | Signal-safe | Notes |
| --- | --- | --- | --- | --- | --- |
| Linux, glibc ≥ 2.32 | `strerrordesc_np` | 49 English; `NULL` for unknown codes (the caller formats the number: `Unknown error -2147483648` is 25) | Yes (doc) | Yes (doc) | Static storage, never translated; declared under `_GNU_SOURCE`, which C++ always has. |
| Linux, glibc | `strerror_r` (GNU form in C++) | 49 English; 148 in glibc 2.44's own catalogs; otherwise unbounded | Yes (doc) | No (doc) | Known codes return a static pointer and leave `buf` alone; unknown codes write a truncated `Unknown error N` into `buf`. |
| Linux, musl | `strerror_r` (XSI) | 40 English; unknown codes give `No error information` (20) and return 0; translated text unbounded | Yes (source) | Yes (source) | Truncates with `ERANGE` and a NUL. Not a forge CI target. |
| macOS | `strerror_r` (XSI) | 47; unknown codes give `Unknown error: N` (≤ 26) and `EINVAL` | Yes (source) | Yes (source, measured) | Never translated; truncates with `ERANGE` and a NUL. |
| Windows | `FormatMessageW(FROM_SYSTEM \| IGNORE_INSERTS)` + UTF-16→UTF-8 | 460 for English Win32 codes (SDK 10.0.28000), CRLFs included; localized text not measured, ≤ 3 × UTF-16 units; hard ceiling 64 KB | Undocumented | Undocumented | Fails, does not truncate, when the buffer is small; the language fallback is needed; ends with `.\r\n` almost always; a few messages have CRLFs in the middle; unknown codes give no text. |
| Windows (`errno`) | UCRT `strerror_s` | 35; unknown codes give `Unknown error` | Yes (doc) | Undocumented | Static English table; truncates silently. |

## 6 Open trade-offs for the message-API decision

1. **Static `string_view`.**
   - Only glibc ≥ 2.32 (`strerrordesc_np`) offers static, untranslated, AS-safe storage for every
     known code. musl `strerror` and Apple `sys_errlist` give static storage in practice, but
     POSIX does not promise it, and Apple marks `sys_errlist` deprecated. The UCRT's
     `_sys_errlist` is static.
   - Windows Win32 codes have no static `char` storage. forge would have to ship its own table
     (about 235 KB of English for 3,194 codes) or parse the UTF-16 `RT_MESSAGETABLE` itself.
   - Unknown codes cannot carry their number in a static string.
2. **A buffer the caller provides.**
   - This works on every host. On POSIX, XSI `strerror_r` truncates with `ERANGE` and NUL on all
     three libcs, so any size yields a usable prefix.
   - On Windows, `FormatMessageW` fails rather than truncates. forge would need an internal UTF-16
     scratch buffer as large as the longest message: about 1 KB covers every English Win32 code
     today, and 64 KB is the documented maximum. If the message does not fit, forge would have to
     report an error, fall back to a number-only message, or allocate, which forge forbids.
   - The API must say what truncation means, and whether the size is fixed (for example 64, 256 or
     512 bytes) or chosen by the caller.
3. **A `std::formatter` only.**
   - The formatter can keep the host-specific scratch buffer on its own stack and write to any
     output iterator. Whether anything allocates then depends on the output: `format_to_n` into an
     array or `std::format` into a `std::string`.
   - No standard library documents the `std::format` machinery as allocation-free or
     async-signal-safe, so a crash handler would still need a lower-level path.
   - It composes with `result<T, E>`, whose formatter formats `E` with `E`'s own formatter
     (`docs/result.md`).
4. **Localization.**
   - Untranslated English is reachable everywhere except Windows: glibc `strerrordesc_np`, Apple
     always, musl in the C locale, UCRT always.
   - On Windows, asking for en-US alone can fail on machines without that message table
     (STL#3254), and the fallback chain returns localized UTF-16 of unknown length.
   - Choosing "English, else whatever exists" (as the MSVC STL does) keeps a bound only for the
     English case.
5. **Formatting rules.** These must be specified rather than inherited:
   - the trailing period and CRLF on Windows;
   - CRLFs in the middle of a Windows message;
   - the different spellings of "unknown" (`Unknown error N`, `Unknown error: N`,
     `No error information`, `unknown error`, `unspecified … error`);
   - glibc's untranslated text being capitalized with no period, while MSVC STL's `generic`
     strings are lower-case.
6. **Two message sources per host.** POSIX codes and Windows codes overlap numerically: `errno` 2
   and `ERROR_FILE_NOT_FOUND` 2 have different texts. So the domain decides which table is used.
   This interacts with the "Layout and size" question in #4.

## 7 Not verified from a primary source

- Whether `FormatMessageW` (`FROM_SYSTEM`, caller buffer) allocates, takes the loader or heap lock,
  or is thread-safe.
- What `FormatMessageW` leaves in the buffer when it fails for lack of space. The error code
  `ERROR_INSUFFICIENT_BUFFER` is attested only by Microsoft's .NET code, not by the FormatMessage
  page.
- The error code `FormatMessageW` sets for an ID with no message text (presumably
  `ERROR_MR_MID_NOT_FOUND`).
- What `FORMAT_MESSAGE_MAX_WIDTH_MASK` puts in place of ignored line breaks.
- Whether `MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT)` gets FormatMessage's fallback chain or is
  treated as one specific LANGID.
- The length of localized Windows system messages. That the installed en-US message table matches
  the SDK's `winerror.h` exactly is inferred from Learn's statement that the message compiler
  writes the same text to both.
- The thread-safety and AS-safety of musl and Apple `strerror_r`. Both are read from source only;
  neither project documents them.
- The glibc and Windows behaviour was read from source and documentation only. Only macOS was run.

## Sources

- POSIX.1-2024: [`strerror`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/strerror.html),
  [§2.4.3 Signal Actions](https://pubs.opengroup.org/onlinepubs/9799919799/functions/V2_chap02.html#tag_16_04_03).
- glibc `glibc-2.44`:
  - [`string/_strerror.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/_strerror.c;hb=glibc-2.44)
  - [`string/xpg-strerror.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/xpg-strerror.c;hb=glibc-2.44)
  - [`string/strerror_l.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/strerror_l.c;hb=glibc-2.44)
  - [`string/strerrordesc_np.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/strerrordesc_np.c;hb=glibc-2.44)
  - [`stdio-common/errlist.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=stdio-common/errlist.c;hb=glibc-2.44)
  - [`sysdeps/gnu/errlist.h`](https://sourceware.org/git/?p=glibc.git;a=blob;f=sysdeps/gnu/errlist.h;hb=glibc-2.44)
  - [`string/string.h`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/string.h;hb=glibc-2.44)
  - [`string/Versions`](https://sourceware.org/git/?p=glibc.git;a=blob;f=string/Versions;hb=glibc-2.44)
  - [`manual/errno.texi`](https://sourceware.org/git/?p=glibc.git;a=blob;f=manual/errno.texi;hb=glibc-2.44)
  - [`manual/intro.texi`](https://sourceware.org/git/?p=glibc.git;a=blob;f=manual/intro.texi;hb=glibc-2.44)
  - [`intl/dcigettext.c`](https://sourceware.org/git/?p=glibc.git;a=blob;f=intl/dcigettext.c;hb=glibc-2.44)
  - [`po/`](https://sourceware.org/git/?p=glibc.git;a=tree;f=po;hb=glibc-2.44)
- Linux man-pages 6.19: [`strerror(3)`](https://man7.org/linux/man-pages/man3/strerror.3.html).
- musl `v1.2.6`:
  - [`src/string/strerror_r.c`](https://git.musl-libc.org/cgit/musl/tree/src/string/strerror_r.c?h=v1.2.6)
  - [`src/errno/strerror.c`](https://git.musl-libc.org/cgit/musl/tree/src/errno/strerror.c?h=v1.2.6)
  - [`src/errno/__strerror.h`](https://git.musl-libc.org/cgit/musl/tree/src/errno/__strerror.h?h=v1.2.6)
  - [`src/locale/locale_map.c`](https://git.musl-libc.org/cgit/musl/tree/src/locale/locale_map.c?h=v1.2.6)
  - [`src/locale/__mo_lookup.c`](https://git.musl-libc.org/cgit/musl/tree/src/locale/__mo_lookup.c?h=v1.2.6)
- Apple Libc `Libc-1752.120.2`:
  - [`string/FreeBSD/strerror.c`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/string/FreeBSD/strerror.c)
  - [`string/FreeBSD/strerror.3`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/string/FreeBSD/strerror.3)
  - [`gen/errlst.c`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/gen/errlst.c)
  - [`xcodescripts/libc.xcconfig`](https://github.com/apple-oss-distributions/Libc/blob/Libc-1752.120.2/xcodescripts/libc.xcconfig)
- xnu `xnu-12377.121.6`:
  [`bsd/man/man2/sigaction.2`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/bsd/man/man2/sigaction.2).
- Microsoft Learn:
  - [FormatMessageW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-formatmessagew)
  - [MAKELANGID](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-makelangid)
  - [Language Identifier Constants and Strings](https://learn.microsoft.com/en-us/windows/win32/intl/language-identifier-constants-and-strings)
  - [Message Text Files](https://learn.microsoft.com/en-us/windows/win32/eventlog/message-text-files)
  - [WideCharToMultiByte](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte)
  - [Use UTF-8 code pages](https://learn.microsoft.com/en-us/windows/apps/design/globalizing/use-utf8-code-page)
  - [strerror_s](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/strerror-s-strerror-s-wcserror-s-wcserror-s)
  - [System Error Codes source, MicrosoftDocs/win32 `51c9b7c`](https://github.com/MicrosoftDocs/win32/tree/51c9b7cc54ef393b6406c8320a7840fdd88209d5/desktop-src/Debug)
- Windows SDK [Microsoft.Windows.SDK.CPP 10.0.28000.2957](https://www.nuget.org/packages/Microsoft.Windows.SDK.CPP/10.0.28000.2957):
  - `c/Include/10.0.28000.0/shared/winerror.h`
  - `c/Include/10.0.28000.0/um/winnt.h` (`MESSAGE_RESOURCE_*`)
  - `c/Source/10.0.28000.0/ucrt/misc/{strerror,syserr}.cpp`
  - `c/Source/10.0.28000.0/ucrt/inc/corecrt_internal.h`
- .NET `v10.0.0`:
  [`Interop.FormatMessage.cs`](https://github.com/dotnet/runtime/blob/v10.0.0/src/libraries/Common/src/Interop/Windows/Kernel32/Interop.FormatMessage.cs).
- libstdc++:
  - [`system_error.cc` @ gcc-16.2.0](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libstdc%2B%2B-v3/src/c%2B%2B11/system_error.cc)
  - [`system_error.cc` @ gcc-13.1.0](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.1.0/libstdc%2B%2B-v3/src/c%2B%2B11/system_error.cc)
  - [`ChangeLog` @ gcc-13.5.0](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.5.0/libstdc%2B%2B-v3/ChangeLog)
  - [PR 110133](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=110133)
  - [FAQ 4.3](https://gcc.gnu.org/onlinedocs/libstdc++/faq.html#faq.predefined)
- libc++ and Clang `llvmorg-23.1.5`:
  - [`libcxx/src/system_error.cpp`](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/libcxx/src/system_error.cpp)
  - [`libcxx/src/include/config_elast.h`](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/libcxx/src/include/config_elast.h)
  - [`clang/lib/Basic/Targets/OSTargets.h`](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/clang/lib/Basic/Targets/OSTargets.h)
- MSVC STL `vs-2022-17.14`:
  - [`stl/inc/system_error`](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/inc/system_error)
  - [`stl/src/syserror.cpp`](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/src/syserror.cpp)
  - [`stl/src/syserror_import_lib.cpp`](https://github.com/microsoft/STL/blob/vs-2022-17.14/stl/src/syserror_import_lib.cpp)
  - Issues [#2451](https://github.com/microsoft/STL/issues/2451),
    [#3254](https://github.com/microsoft/STL/issues/3254); PR
    [#5104](https://github.com/microsoft/STL/pull/5104)
- Unicode Standard, [chapter 3, D92](https://www.unicode.org/versions/latest/core-spec/chapter-3/).
