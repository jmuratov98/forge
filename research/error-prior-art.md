# Prior art: allocation-free error codes without virtual categories

Research for [#5](https://github.com/jmuratov98/forge/issues/5), a child of the map
[#4](https://github.com/jmuratov98/forge/issues/4) ("Design a minimalist allocation-free
`forge::error`"). It feeds the grilling ticket "How does an error name its domain?". It reports
facts and trade-offs. It does not choose between a closed enum of domains and an open set.

**Method.** Every claim cites a paper on open-std.org, upstream source pinned to a tag or commit,
or official documentation. Sizes and `constexpr` behaviour were also checked with compile-only
probes (`static_assert`s, never executed) using Homebrew clang 23.1.4, `-std=c++20`, on arm64
macOS with the SDK's libc++. The probes compiled against the pinned status-code and Boost
sources. They compiled against the Homebrew installs of LLVM 23.1.4 and Abseil 20260817, not the
exact pinned trees. Anything not confirmed from a primary source is listed under
[Unverified](#unverified).

**Versions read.**

| Subject | Pinned to |
|---|---|
| P1028 | [P1028R6][p1028r6] (2023-11-09) |
| P0709 | [P0709R4][p0709r4] (2019-08-04) |
| system_error2 | [ned14/status-code @ `0487928`][sc] (master, 2026) |
| Boost.System | [boostorg/system @ `boost-1.92.0`][bsys] |
| Rust | [rust-lang/rust @ `1.99.1`][rust] |
| Zig | [Language Reference 0.15.2][zigref], [ziglang/zig @ `0.15.2`][zig] |
| LLVM | [llvm/llvm-project @ `llvmorg-23.1.5`][llvm] |
| Abseil | [abseil/abseil-cpp @ `20260817.0`][absl] |

## Baseline: what `std::error_code` does

These are the properties `forge::error` is meant to fix.

- **Domain.** The standard says `error_category` objects "are passed by reference, and two such
  objects are equal if they have the same address" ([syserr.errcat.overview]). A note warns that
  if a program has more than one object of a custom category type, equal-valued objects can
  compare unequal.
- **Layout.** `error_code` holds the exposition-only members `int val_` and
  `const error_category* cat_` ([syserr.errcode.overview]). That is 16 bytes on LP64 (probe), and
  the type is trivially copyable (probe).
- **Message.** `virtual string message(int ev) const = 0;` returns a `std::string`, which
  allocates.
- **`constexpr`.** Only the `error_category` default constructor is `constexpr`. None of the
  `error_code` members are.
- **DSOs.** [P1196R0][p1196] (Dimov) gives the motivation that Boost later acted on: "In the
  presence of dynamic libraries without global symbol visibility, it's hard to guarantee that
  category objects are unique." It adds that address-based comparison "makes it impossible to
  declare category objects `constexpr` and makes it impossible to declare `operator<`
  `constexpr`." [P1197R0][p1197] adds that "`message`, specified to return an `std::string`,
  mandates allocation, which may be prohibited."

---

## 1. P1028 `status_code` and system_error2

[P1028R6][p1028r6] is SG14's `<system_status>`. [ned14/status-code][sc] is its reference
implementation (namespace `system_error2`). **Status:** the [WG21 tracker][p1028-tracker] is
open, labelled `needs-revision`, `C++29` and `outdated-or-needs-champion`. At Sofia
(2025-06-19), LEWG polled "solves an important problem" 9/7/1/1/0 ("strong encouragement") and
asked for volunteers.

1. **Domain identity.** Each code holds a `const status_code_domain*` ([sc-storage]). Domains are
   compared by a **64-bit unique id**, not by address:
   `constexpr bool operator==(const status_code_domain &o) const noexcept { return _id == o._id; }`
   ([sc-domain-eq]). The id is a random number or a UUID string that is parsed at compile time and
   folded to 64 bits by XOR ([sc-domain-id]). The docs say: "Do NOT make up your own value. Do NOT
   use zero." P1028R6 makes `unique_id_type` "implementation defined unsigned, at least 64 bits".
   A footnote says SG14 judged 64 bits sufficient, and that 128 bits would be encouraged once they
   are portable. **The domain is still a polymorphic class.** It has pure virtuals `_do_name`,
   `_do_payload_info`, `_do_failure`, `_do_equivalent`, `_do_generic_code`, `_do_message` and
   `_do_throw_exception`, plus `_do_erased_copy` and `_do_erased_destroy` ([sc-vtable]). The
   vtable is shaped for C-ABI compatibility: simple return types, with results passed back
   through an argument struct ([sc-vtable-why]). So status_code removes the *address comparison*
   but keeps *virtual dispatch*.
2. **Size and layout (64-bit).** `status_code<D>` is the domain pointer plus `D::value_type`
   (plus optional mixin state). `generic_code` (value `errc`) is 16 bytes (probe).
   `system_code = erased_status_code<intptr_t>` is `static_assert`ed to be exactly two pointers
   ([sc-system-code]). `error` is `erased_errored_status_code<intptr_t>`, also two pointers
   ([sc-error]). Empty means `_domain == nullptr` ([sc-empty]). In the probe a domain object was
   16 bytes (vptr plus id). Copy semantics:
   - Typed codes are **not** trivially copyable, because a move nulls the source's domain (probe).
   - Erased codes (`system_code`, `error`) are **move-only**. Copy is deleted, `clone()` goes
     through the virtual `_do_erased_copy`, and the destructor calls `_do_erased_destroy`. The
     class is marked `SYSTEM_ERROR2_TRIVIAL_ABI` ([sc-erased]).
3. **Cross-domain comparison.** `operator==` is always *semantic* ([sc-equivalent]):
   1. `a.domain()._do_equivalent(a, b)`;
   2. `b.domain()._do_equivalent(b, a)`;
   3. map `b` to a `generic_code` (`errc`) through `_do_generic_code` and ask `a`'s domain;
   4. do the same with the roles swapped.

   `generic_code` takes the place of `std::error_condition` as the pivot (P1028R6 goals 6, 7
   and 11). A literal comparison is written by hand by comparing domain and value.
   `operator<` and `std::hash` are deliberately not provided for codes ([sc-no-hash]). Domains
   are ordered by id (`operator<=>` in R6).
4. **Message and allocation.** `message()` returns a `string_ref`: begin/end pointers, three
   `void*` of state, and a thunk function pointer called on copy, move and destroy
   ([sc-string-ref]). The generic domain returns a string literal, so it does not allocate. The
   POSIX domain calls `strerror_r` into a 1024-byte stack buffer and returns an
   `atomic_refcounted_string_ref`, which **`malloc`s** a reference-counted copy ([sc-posix-msg],
   [sc-refcounted]). The Win32 and NT domains do the same. This contradicts the README's feature
   bullet "Never calls `malloc()`" ([sc-readme-malloc]). P1028R6 also specifies
   `atomic_refcounted_string_ref` as shared state that is "deallocated" when its count reaches
   zero.
5. **`constexpr`.** P1028R6 goal 2 is "All constexpr sourcing, construction and destruction".
   The domain is a literal type with `constexpr virtual` members (C++20). R6 corrected
   "trivially copyable" to "literal type", because a type with a vptr cannot be trivially
   copyable. Probe results:
   - In a `static_assert`, these compiled: `constexpr generic_code` construction, `value()`,
     domain equality, and semantic `==` against an `errc` (a virtual `_do_equivalent` call).
   - `message()` did **not** compile in a constant expression: the `string_ref` copy assignment
     modifies a `const` thunk member.
6. **DSOs and hidden visibility.** Domain objects are namespace-scope `constexpr` variables, for
   example `constexpr _generic_code_domain generic_code_domain;` ([sc-generic-var]). Such a
   variable has internal linkage, so every translation unit, and therefore every DSO, has its
   own copy. Correctness rests on the id comparison, not on symbol identity. Both the README and
   P1028R6 goal 3 claim the design is "100% safe to use in header only libraries"
   ([sc-readme-header]). The library uses no `dynamic_cast` or `typeid` (grep). The cost is the
   chance of a collision between two random 64-bit ids.

**Relevance to forge's constraints.** `status_code` has a success state and an empty state
([sc-empty]). Only `errored_status_code` and `error` enforce "always a failure", by checking at
construction. The `error` type is move-only and not trivially copyable.

## 2. P0709 `std::error`

[P0709R4][p0709r4] §4.1.1 states **requirements** for `std::error` and points to Douglas's
`status_code` as the prototype (footnote 3). It does not give wording. **Status:** the
[tracker][p0709-tracker] is open, labelled EWG and `needs-revision`.

1. **Domain identity.** It has a "constexpr 'domain' (usually a pointer or hash value that is used
   only for its type to distinguish the domain)". The domain discriminant should improve on
   `error_category` as [P0824R1] suggests.
2. **Size.** "no greater than two pointers, typically a 'payload' (usually an integer) plus a
   constexpr 'domain'." It must be "type-erased, allocation-free, trivially relocatable,
   constant-time in all operations, ABI-safe".
3. **Comparison.** "weak_equality heterogeneous comparison that performs semantic equivalence
   comparison across domains". The example given: "host unreachable" from Win32 and from POSIX
   compares equal to each other and to `errc::host_unreachable`.
4. **Message.** P0709 specifies no message API. One allocation is allowed for: a wrapped
   `exception_ptr` "can be allocated on the heap" if `exception_ptr` is not trivially
   relocatable.
5. **`constexpr`.** Only the domain is required to be `constexpr`.
6. **DSOs.** It must be "ABI-safe, and safe to use in header-only libraries".

**Success value.** "It always represents a failure (there is no 0 success value). A default
constructor would construct a general or 'other' nonspecific error value."

**Implementation feedback.** [P2170R0][p2170] (Salvia, 2020) is an independent implementation.
It departs from status_code in three ways:
- **128-bit domain ids.** 64 bits approaches a 50% collision chance at about 4 billion domains,
  which matters if errors are serialised across machines.
- **Copyable.** Copy, move and destroy are three function pointers carried by the domain, null
  for trivially copyable payloads. status_code is move-only.
- **Payload of one pointer.** An arbitrary `std::error_code` therefore needs a heap allocation
  to fit, because the value and the category pointer do not fit in one pointer.

## 3. Boost.System

Pinned to [`boost-1.92.0`][bsys]. Ids arrived in **1.69**, with "a constructor that accepts a 64
bit identifier, enabling distinct category objects to compare equal" and "A non-allocating,
nonthrowing overload of `message`" ([changes][bsys-changes]). These implement P1196 and P1197.
**1.78** added source locations to `error_code`. **1.79** threaded them into
`throw_exception_from_error`.

1. **Domain identity.** Each code holds a `const error_category*`. The category has a 64-bit
   `id_` ([bsys-id]). Comparison is `rhs.id_ == 0 ? &lhs == &rhs : lhs.id_ == rhs.id_`
   ([bsys-eq]): by id when the id is nonzero, by address otherwise, which keeps old categories
   working. The generic, system and interop ids are fixed constants (`0xB2AB117A257EDFD0`, +1,
   +2) ([bsys-ids]). The reference says ids "must be randomly chosen (at the time the category is
   implemented, not at runtime)" ([bsys-ref-id]). Categories are still polymorphic (`name`,
   `message`, `equivalent`, `default_error_condition`, `failed`).
2. **Size and layout.** An `error_code` is **24 bytes** and trivially copyable (probe). The layout
   is a union of `{int val_; const error_category* cat_;}` and raw storage for a
   `std::error_code`, plus `uintptr_t lc_flags_` ([bsys-ec-layout]). `lc_flags_` encodes:
   - 0: default-constructed;
   - 1: holds a `std::error_code`;
   - 2 or 3: `failed()` cached in bit 0;
   - 4 or more: a pointer to a `boost::source_location`.

   An `error_category` object is 56 bytes (probe): vptr, id, a four-pointer buffer for a lazily
   built `std::error_category` bridge, and an `atomic<unsigned>`.
3. **Cross-domain comparison.**
   - `error_code == error_code` is literal: value plus category, by id ([bsys-ec-eq]).
   - `error_code == error_condition` asks both categories' virtual `equivalent`, as the standard
     does ([bsys-ec-cond]).
   - **Bridge to `std::error_code`.** Generic and system map to `std::generic_category()` and
     `std::system_category()`. Any other category builds a `std_category` in its own buffer,
     under a mutex. Recovering the Boost category in `equivalent` uses
     `dynamic_cast<std_category const*>`, which is compiled out under `BOOST_NO_RTTI`
     ([bsys-rtti]).
4. **Message and allocation.** `message()` returns `std::string`, which allocates. Since 1.69
   there is `char const* message(char* buffer, size_t len) noexcept`. Its model is glibc
   `strerror_r`: it may return a literal, or write into the buffer ([bsys-ref-msg]). The
   **default** implementation calls the allocating `message(ev)` and copies the result
   ([bsys-msg-default]). Only categories that override it avoid allocation. Generic and system
   override it with `strerror_r`.
5. **`constexpr`.** These are `constexpr` from C++14 (`BOOST_SYSTEM_CONSTEXPR`): the `error_code`
   constructors, `value()`, `category()`, `==` and `failed()`. `generic_category()` returns a
   `static constexpr` member of a template holder ([bsys-generic]). The virtual `equivalent` and
   `failed` are `constexpr` from C++20. The probe confirmed that construction, `==`, `value()` and
   `failed()` work in a `static_assert`. `message` is not `constexpr`.
6. **DSOs and hidden visibility.** The ids exist because of the DSO problem described in P1196.
   The category classes and holders are marked `BOOST_SYMBOL_VISIBLE`. **Inference from the
   source:** the `std::error_category` bridge lives inside each Boost category *object*. Two Boost
   category objects with equal ids would therefore convert to two `std` categories at different
   addresses, and on the `std` side comparison is by address again.

## 4. Rust `std::io::Error`

Pinned to [`1.99.1`][rust]. In this release `io::Error` lives in `core` (unstable `core_io`) and
is re-exported by `std`. The bit-packed representation arrived in
[rust-lang/rust#87869][rust-pr] (merged 2022-02-07).

1. **Domain identity.** There is no domain object. The 2 low bits are a tag that selects one of
   four representations ([rust-bitpacked]):

   | Tag | Variant | Holds |
   |---|---|---|
   | `0b00` | SimpleMessage | `&'static {kind, &'static str}` |
   | `0b01` | Custom | `Box<Custom>`, holding a kind and a boxed `dyn Error` |
   | `0b10` | Os | raw OS error code (`i32`) in the high 32 bits |
   | `0b11` | Simple | `ErrorKind` in the high 32 bits |

   The only numeric domain is the platform's raw OS error (`errno` or `GetLastError`). `core`
   cannot call the OS, so it reads OS codes through `OsFunctions`, a `&'static` struct of three
   **plain function pointers** (`format_os_error`, `decode_error_kind`, `is_interrupted`)
   ([rust-osfn]). `std` passes its table when it creates an OS error, and `core` stores it in a
   global `AtomicPtr` ([rust-osfn-atomic], [rust-std-from-raw]).
2. **Size.** **8 bytes** on 64-bit targets other than UEFI. The source `static_assert`s
   `size_of::<Repr>() == 8`, `Result<(), Repr>` == 8 and `Result<usize, Repr>` == 16, using the
   `NonNull` niche ([rust-asserts]). 32-bit targets and UEFI, where codes are 64-bit, use an
   unpacked enum ([rust-cfg]).
3. **Comparison.** `io::Error` implements neither `PartialEq` nor `Clone` (no impl in the `core`,
   `alloc` or `std` io error sources). Portable comparison goes through
   `kind() -> ErrorKind` ([rust-kind]). `ErrorKind` is a `#[non_exhaustive]` enum deriving
   `Copy`, `Eq`, `Hash` and `Ord` ([rust-errorkind]). OS codes map to it through
   `decode_error_kind`. `raw_os_error()` gives the literal code.
4. **Message and allocation.** `Display` writes into a caller-supplied `Formatter`
   ([rust-display]):
   - Simple and SimpleMessage write a `&'static str` and do not allocate.
   - Os calls `format_os_error`. `std` implements that as
     `fmt.write_str(&error_string(code))` ([rust-std-from-raw]), and `error_string` returns a
     `String` built from a 128-byte `strerror_r` buffer ([rust-error-string]). So **OS messages
     allocate**.
   - Creating a Custom error allocates (a `Box`).
5. **`const`.** `const_error!(kind, "msg")` and `from_static_message` build an error in `const`
   context without allocating (unstable `io_const_error`, [issue 133448][rust-const-issue])
   ([rust-const]). The SimpleMessage tag is `0b00` precisely so that a `const fn` does not need
   to tag a pointer. `from_raw_os_error` is not `const`.
6. **DSOs.** The sources say nothing about this. Domain identity is a tag inside the value, so no
   symbol needs to be unique. The `OsFunctions` pointer is a static in `core`. See
   [Unverified](#unverified).

## 5. Zig error sets

From [Language Reference 0.15.2 §Errors][zig-errors] and [`lib/std/posix.zig`][zig-posix].

1. **Domain identity.** There are no domains at runtime. "Each error name across the entire
   compilation gets assigned an unsigned integer greater than 0. You are allowed to declare the
   same error name more than once, and if you do, it gets assigned the same integer value."
   Error sets are compile-time subsets of the global set `anyerror`.
2. **Size.** "The error set type defaults to a u16". With `--error-limit [num]`, the compiler
   uses the minimum number of bits that holds all the values.
3. **Comparison.** Integer equality, where identity is the *name*. Coercion from a subset to a
   superset is implicit. A cast from superset to subset is safety-checked. There is no
   cross-domain equivalence because there are no domains. In `std.posix`, each call site turns
   `errno` into named errors with a `switch`. An unlisted value becomes `error.Unexpected`, and
   the raw `errno` is lost: it is only printed when tracing is enabled ([zig-unexpected]).
4. **Message.** `@errorName(err) [:0]const u8` returns the name from a table that the compiler
   emits. "If there are no calls to @errorName in an entire application, or all calls have a
   compile-time known value for err, then no error name table will be generated"
   ([zig-errorname]). It returns names only, never prose, and does not allocate.
5. **comptime.** Errors are ordinary comptime-known values. `@errorName` on a comptime-known
   value is resolved at compile time.
6. **DSOs.** Numbering is per compilation, and `@intFromError` and `@errorFromInt` warn that "the
   integer representation of an error is not stable across source code changes"
   ([zig-intfromerror]). See [Unverified](#unverified).

## 6. LLVM: `std::error_code`, `ErrorOr` and `llvm::Error`

Pinned to [`llvmorg-23.1.5`][llvm].

**`std::error_code` in LLVM.** Support APIs such as `sys::fs` return `std::error_code`. LLVM's
own categories are `std::error_category` subclasses. Each is a **function-local static in one
`.cpp`**, returned by an out-of-line accessor annotated `LLVM_ABI`. Examples are
`object::object_category()` ([llvm-objcat], declared `LLVM_ABI` in [llvm-objcat-h]) and the
`ErrorErrorCategory` in `Support/Error.cpp` ([llvm-errcat]). So there is one object in one
library, and address comparison holds as long as the accessor is exported. `llvm::errc` mirrors
`std::errc` but makes codes in `std::generic_category()`. Its header says the reason: comparing
against `std::errc` (a condition enum) "take[s] 4 virtual calls instead of two comparisons"
([llvm-errc]). `ErrorOr<T>` is a union of `T` and `std::error_code` plus a 1-bit `HasError`
([llvm-erroror]). `ErrorOr<int>` is 24 bytes (probe).

**`llvm::Error`.**

1. **Domain identity.** The dynamic type of a heap-allocated `ErrorInfoBase` subclass. A class is
   identified by the **address of its `static char ID`**, through `classID()`,
   `dynamicClassID()` and `isA()` ([llvm-errorinfo]).
2. **Size.** 8 bytes, one pointer ([llvm-payload]). Success is null. In
   `LLVM_ENABLE_ABI_BREAKING_CHECKS` builds, the low bit is the "unchecked" flag. `Expected<int>`
   is 16 bytes (probe). `Error` is move-only.
3. **Comparison.** There is no `operator==`. Errors are matched by type with `isA` and
   `handleErrors`. Interop goes through the virtual `convertToErrorCode()`, plus
   `errorCodeToError` and `errorToErrorCode`. `ECError` wraps a `std::error_code`, and
   `inconvertibleErrorCode()` covers errors that have no code
   ([manual §Interoperability][llvm-manual-interop]).
4. **Message and allocation.** Every failure is heap-allocated (`make_error<T>` creates a
   `unique_ptr`, and so does `errorCodeToError`). Messages come from the virtual
   `log(raw_ostream&)`, which writes to a caller's stream, or from `message()`, which returns a
   `std::string` ([llvm-errorinfo]). The manual explains that `Error` exists to attach "arbitrary
   information", which is the opposite of forge's code-only rule ([llvm-manual-error]).
5. **`constexpr`.** No.
6. **DSOs and hidden visibility.** `LLVM_BUILD_LLVM_DYLIB_VIS=On` builds ELF and Mach-O libraries
   with default-hidden visibility. `LLVM_ABI` then expands to `visibility("default")`, or to
   `dllexport`/`dllimport` on Windows ([llvm-export]). Classes with exported virtual methods must
   be annotated at class level so that the vtable is exported ([llvm-export-class]).
   `ErrorInfoBase` and `ECError` are `class LLVM_ABI`. **Inference:** address-based `ID`s and
   category singletons stay unique because each is *defined once, out of line, and exported*,
   which is the opposite of the header-only approach of status_code and Boost.

## 7. Abseil `Status`

Pinned to [`20260817.0`][absl].

1. **Domain identity.** There is one closed, canonical code space: `absl::StatusCode`
   (`enum class : int`, kept in sync with `google.rpc.Code`) ([absl-code]). There is no domain
   id. Other sources are mapped into this space, for example `ErrnoToStatusCode(int)`
   ([absl-errno]). `raw_code()` can hold values outside the enum, and `code()` maps unknown
   values to `kUnknown`.
2. **Size.** **8 bytes**, a single `uintptr_t rep_` ([absl-rep]):
   - **Low bit 1:** an inlined code, with `code = rep >> 2` and bit 1 meaning "moved from"
     ([absl-inline]).
   - **Low bit 0:** a pointer to a heap `StatusRep`, which holds a refcount, the code, a
     `std::string` message, payloads and source locations.

   The type is not trivially copyable (probe), because copies adjust the refcount. It is marked
   `ABSL_ATTRIBUTE_TRIVIAL_ABI`.
3. **Comparison.** `operator==` first compares `rep_`, then compares the reps in depth: code,
   message and payloads ([absl-eq]). There is no cross-domain equivalence because there is only
   one space.
4. **Message and allocation.** `message()` returns a `string_view` without allocating
   ([absl-msg]). A **non-empty message allocates a `StatusRep` at construction**. A status with
   no message stays inlined and allocation-free ([absl-make-rep]). `StatusCodeToStringView`
   returns static names ([absl-code-name]). `ToString()` allocates. `ErrnoToStatus` builds its
   message with `StrCat` and `StrError`, so it allocates ([absl-errno-cc]).
5. **`constexpr`.** No. `Status` is not a literal type ("no constexpr constructors", probe). Only
   internal helpers such as `CodeToInlinedRep` are `constexpr`.
6. **DSOs.** No object identity is involved: inlined codes are plain integers. Heap reps are
   reference-counted and freed by whichever DSO drops the last reference. See
   [Unverified](#unverified).

---

## Comparison table

64-bit, from the sections above. "Probe" marks sizes measured by `static_assert`.

| | Domain identified by | Size (64-bit) | Cross-domain comparison | Message: how / allocates? | `constexpr` | DSOs, hidden visibility |
|---|---|---|---|---|---|---|
| `std::error_code` (baseline) | address of a virtual `error_category` singleton | 16 B (probe) | virtual `equivalent` against `error_condition` | `std::string`: **yes** | no (only the category constructor) | breaks if singletons are duplicated (P1196) |
| **P1028 / status-code** | **random 64-bit id** inside a still-virtual domain object, reached through a pointer | 16 B for `generic_code`, `system_code` and `error` (probe and `static_assert`) | always semantic: two-way `do_equivalent`, then through `generic_code` (`errc`) | `string_ref`: literal for generic; **`malloc`ed copy** for POSIX, Win32 and NT | construction, compare and `==` yes (C++20 probe); `message()` no | per-TU `constexpr` copies, compared by id: designed to be header-only safe |
| **P0709 `std::error`** | "pointer or hash value" (requirement only) | ≤ 2 pointers | semantic, `weak_equality` (requirement) | not specified; must be allocation-free | domain must be `constexpr` | must be "ABI-safe … header-only safe" |
| **Boost.System ≥ 1.69** | 64-bit id if nonzero, else address, inside a virtual category | 24 B (probe; includes source-location bits) | literal code==code; virtual code==condition; RTTI for the std bridge | `std::string` **allocates**; `message(buf, len)` noexcept, non-allocating only if overridden | constructor, `==`, `failed` (C++14); virtuals in C++20 | ids fix it; the std bridge is per category object |
| **Rust `io::Error`** | **2-bit tag**: OS, Simple, static message, boxed custom; OS interpretation through a `&'static` table of fn pointers | **8 B** (`static_assert`) | no `==`; through `kind() -> ErrorKind` | writes to a `Formatter`; static `str` for kinds; **OS message allocates a `String`**; custom allocates | `const_error!` yes (unstable); OS constructor no | no symbol identity in the value; not addressed by the sources |
| **Zig error sets** | none: one global name → `u16` per compilation | 2 B (`u16` default) | integer equality by name; subset/superset coercion | `@errorName`: compiler table, no allocation, names only | fully comptime | numbering is per compilation; not addressed by the sources |
| **LLVM `std::error_code`** | address of a function-local static in one `.cpp`, exported | 16 B; `ErrorOr<int>` 24 B (probe) | standard virtual `equivalent` | `std::string`: **yes** | no | relies on one exported definition (`LLVM_ABI`) |
| **`llvm::Error`** | dynamic type; address of `static char ID` | 8 B (probe) | type matching (`isA`), no `==` | `log(raw_ostream&)` or `std::string`; **every failure is heap-allocated** | no | exported class and `ID` (`LLVM_ABI`) |
| **Abseil `Status`** | none: one closed canonical space | **8 B** (probe) | `==` on code, message and payloads; single space | `string_view`; **a non-empty message allocates at construction**; code names static | no | no identity objects; refcounted heap reps |

## Open trade-offs for "How does an error name its domain?"

These are trade-offs, not recommendations.

1. **The comparison key: address or value.** Every design that targets header-only use or DSOs
   moved from comparing addresses to comparing values: P1028's id, Boost's id, Rust's tag, Zig's
   name integer, and Abseil's single space. LLVM keeps addresses and makes them safe by defining
   each identity object once, out of line, and exporting it. The forge equivalent would be a
   `FORGE_API` definition in libforge. forge's `--shared` build sets both `visibility "Hidden"`
   and `inlinesvisibility "Hidden"` (`premake/forge.lua`). The GCC manual says
   `-fvisibility-inlines-hidden` "declares that the user does not attempt to compare pointers to
   inline functions or methods where the addresses of the two functions are taken in different
   shared objects" ([gcc-vis]). **Inference:** a pointer to an `inline constexpr` descriptor in a
   header would have one address inside libforge and another in each consumer. So address
   comparison would need an out-of-line, exported descriptor, while id comparison would not.
2. **Where the name and message live.**
   - **Closed enum.** Core can map every `(domain, value)` to a static string with a `switch` or
     table. But core then has to enumerate, and hold the messages of, domains that belong to
     higher components, such as forge's own number-parsing errors. That runs against the
     component graph that the layering lint enforces. Zig does this only because the *compiler*
     builds the global name table.
   - **Bare numeric id.** An id alone cannot find a message without a lookup. P1028 and Boost
     always pair the id with a pointer to the domain object, and use the id only for equality.
     The only registry-like precedent found is Rust's single global `AtomicPtr<OsFunctions>`,
     and it serves one domain.
   - **Pointer to a non-virtual descriptor.** This carries name and message functions with the
     value. Precedents: Rust's `OsFunctions` (a `&'static` struct of plain fn pointers); P2170's
     three-function-pointer resource table; P1028's comment that its vtable is laid out to be
     C-compatible.
3. **Size: 8 or 16 bytes.** A closed tag with a 32-bit value fits in 8 bytes (Rust packs an
   `i32` plus a 2-bit tag; Abseil packs its code into `uintptr_t`; Zig uses 2 bytes). A pointer
   plus a value is 16 bytes (`std::error_code`, status_code, and P0709's ceiling of "≤ 2
   pointers"). Boost spends 24 bytes to carry a source location. Rust quotes the knock-on effect
   on result types: `io::Result<()>` is 8 bytes and `io::Result<usize>` is 16.
4. **Equality cost and `constexpr`.** Comparing ids stored in a descriptor costs a dereference.
   P1196 therefore compares values first: "comparing the values is cheaper than comparing the
   categories (requiring an identifier to be fetched through the category pointer)". Id-based
   designs were `constexpr`-comparable in the probes (Boost, status-code). P1196 says that
   address-based categories cannot be declared `constexpr` and neither can their `operator<`.
5. **The cross-domain pivot.** Every design that has more than one domain routes portable
   comparison through one pivot vocabulary: `generic_code`/`errc` in P1028, `generic_category`
   conditions in Boost, `ErrorKind` in Rust, and mapping into the canonical codes in Abseil.
   Zig has no pivot and no domains. forge's `docs/fs.md` `[fsys.error]` Table 1 already maps
   native codes to `std::errc`. One open question is whether the pivot is stored in bits, or
   computed by a descriptor function or a closed table.
6. **Platform messages without allocation.** `strerror_r` and `FormatMessage` need a buffer.
   status-code and Rust allocate a copy. Abseil allocates when the error is constructed. Boost
   offers a caller-supplied buffer, modelled on glibc `strerror_r`, which may return a static
   string. Rust's `Display` and LLVM's `log(raw_ostream&)` write into a caller-supplied sink;
   that matches `docs/result.md`, where `result`'s formatter formats `E` with `E`'s own
   formatter. Static name tables (Zig, Abseil code names, P1028's generic domain) never
   allocate, but they give names, not OS prose.
7. **Success and default state.** P0709 has no success value, and its default constructor gives a
   nonspecific "other" error. status_code has success and empty states, and only
   `errored_status_code` enforces failure. Rust's and Zig's errors carry no success value, since
   `Result` or the error union does that (Zig's error integers are > 0). `llvm::Error` and
   Abseil have a success state (null, or `kOk`).
8. **Trivially copyable.** `std::error_code` and Boost `error_code` are trivially copyable. Typed
   status_codes are not, and erased ones are move-only. P2170 deliberately made its `std::error`
   copyable. Abseil `Status` and `llvm::Error` are not trivially copyable, and Rust's `io::Error`
   is not `Clone`.
9. **Id collisions in an open set.** Random 64-bit ids (P1028, Boost) are generated by hand from
   random.org, as both projects' docs instruct. P2170 argues for 128 bits. A closed enum has no
   collision risk, and neither has a set where forge assigns every id.

## Unverified

- **Zig across shared objects.** I found no primary source on passing error values between
  separately compiled Zig shared libraries. The langref only says that values are assigned per
  compilation.
- **Rust across `dylib`/`cdylib` boundaries.** I found no primary source on `io::Error` here, or
  on how the per-copy `OS_FUNCTIONS` static in `core` behaves with several copies of `std`. The
  section 4 notes are inference.
- **Abseil `Status` across DSOs.** Freeing heap reps in another DSO, and the matching allocators
  this needs, is inference. The Abseil sources I read do not discuss it.
- **Boost's bridge for equal ids.** That two equal-id Boost categories yield distinct
  `std::error_category` bridges is inferred from reading the source. I did not test it.
- **Hidden-visibility behaviour.** For status-code, Boost and LLVM this comes from their own
  claims and from reading the code. I did not build a two-DSO, `-fvisibility=hidden` test.
- **Platforms and toolchains.** Sizes were measured only on arm64 macOS with libc++. LLVM and
  Abseil were probed through Homebrew builds (LLVM 23.1.4, Abseil 20260817), not the exact pinned
  trees. The status-code `message()` `constexpr` failure was seen only with clang 23. GCC and MSVC
  were not tried.
- **Which standard libraries P1196 meant.** P1196 says implementations "are already known" to make
  copies of the generic and system categories compare equal. I did not check which ones.
- **The standard-text excerpts.** These come from [eel.is/c++draft][syserr.errcat.overview], a
  rendering of the current working draft, not from a published IS.

<!-- Sources -->

[p1028r6]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p1028r6.pdf
[p1028-tracker]: https://github.com/cplusplus/papers/issues/405
[p0709r4]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2019/p0709r4.pdf
[p0709-tracker]: https://github.com/cplusplus/papers/issues/310
[P0824R1]: https://wg21.link/P0824R1
[p2170]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2020/p2170r0.html
[p1196]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1196r0.html
[p1197]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p1197r0.html
[syserr.errcat.overview]: https://eel.is/c++draft/syserr.errcat.overview
[syserr.errcode.overview]: https://eel.is/c++draft/syserr.errcode.overview
[gcc-vis]: https://gcc.gnu.org/onlinedocs/gcc/C_002b_002b-Dialect-Options.html#index-fvisibility-inlines-hidden

[sc]: https://github.com/ned14/status-code/tree/0487928a24321dd78af740a0fbf5ca509f216889
[sc-storage]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code.hpp#L278
[sc-empty]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code.hpp#L307-L328
[sc-domain-eq]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L510-L518
[sc-domain-id]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L428-L456
[sc-vtable]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L557-L599
[sc-vtable-why]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L536-L556
[sc-string-ref]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L157-L215
[sc-refcounted]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L403-L424
[sc-posix-msg]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/posix_code.hpp#L85-L105
[sc-generic-var]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/generic_code.hpp#L377-L381
[sc-equivalent]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/generic_code.hpp#L436-L469
[sc-no-hash]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code_domain.hpp#L44-L50
[sc-erased]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/status_code.hpp#L632-L680
[sc-system-code]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/system_code.hpp#L55-L60
[sc-error]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/include/status-code/error.hpp#L50-L55
[sc-readme-malloc]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/Readme.md?plain=1#L43
[sc-readme-header]: https://github.com/ned14/status-code/blob/0487928a24321dd78af740a0fbf5ca509f216889/Readme.md?plain=1#L233-L236

[bsys]: https://github.com/boostorg/system/tree/boost-1.92.0
[bsys-changes]: https://github.com/boostorg/system/blob/boost-1.92.0/doc/system/changes.adoc?plain=1#L84-L152
[bsys-id]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_category.hpp#L71-L90
[bsys-eq]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_category.hpp#L111-L114
[bsys-ids]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_category.hpp#L161-L163
[bsys-ref-id]: https://github.com/boostorg/system/blob/boost-1.92.0/doc/system/reference.adoc?plain=1#L372-L383
[bsys-ref-msg]: https://github.com/boostorg/system/blob/boost-1.92.0/doc/system/reference.adoc?plain=1#L434-L470
[bsys-ec-layout]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_code.hpp#L66-L83
[bsys-ec-eq]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_code.hpp#L350-L368
[bsys-ec-cond]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_code.hpp#L591-L601
[bsys-msg-default]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/error_category_impl.hpp#L44-L70
[bsys-generic]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/generic_category.hpp#L72-L92
[bsys-rtti]: https://github.com/boostorg/system/blob/boost-1.92.0/include/boost/system/detail/std_category_impl.hpp#L29-L80

[rust]: https://github.com/rust-lang/rust/tree/1.99.1
[rust-pr]: https://github.com/rust-lang/rust/pull/87869
[rust-bitpacked]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error/repr_bitpacked.rs#L1-L100
[rust-asserts]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error/repr_bitpacked.rs#L348-L351
[rust-cfg]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L3-L18
[rust-osfn]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L565-L577
[rust-osfn-atomic]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error/os_functions_atomic.rs
[rust-std-from-raw]: https://github.com/rust-lang/rust/blob/1.99.1/library/std/src/io/error.rs#L72-L85
[rust-error-string]: https://github.com/rust-lang/rust/blob/1.99.1/library/std/src/sys/io/error/unix.rs#L194-L228
[rust-kind]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L473-L480
[rust-errorkind]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L765-L770
[rust-display]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L521-L534
[rust-const]: https://github.com/rust-lang/rust/blob/1.99.1/library/core/src/io/error.rs#L164-L198
[rust-const-issue]: https://github.com/rust-lang/rust/issues/133448

[zigref]: https://ziglang.org/documentation/0.15.2/
[zig]: https://github.com/ziglang/zig/tree/0.15.2
[zig-errors]: https://ziglang.org/documentation/0.15.2/#Errors
[zig-errorname]: https://ziglang.org/documentation/0.15.2/#errorName
[zig-intfromerror]: https://ziglang.org/documentation/0.15.2/#intFromError
[zig-posix]: https://github.com/ziglang/zig/blob/0.15.2/lib/std/posix.zig#L1689
[zig-unexpected]: https://github.com/ziglang/zig/blob/0.15.2/lib/std/posix.zig#L7341-L7347

[llvm]: https://github.com/llvm/llvm-project/tree/llvmorg-23.1.5
[llvm-errorinfo]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/include/llvm/Support/Error.h#L44-L86
[llvm-payload]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/include/llvm/Support/Error.h#L275-L328
[llvm-erroror]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/include/llvm/Support/ErrorOr.h#L255-L259
[llvm-errc]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/include/llvm/Support/Errc.h#L9-L27
[llvm-errcat]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/lib/Support/Error.cpp#L26-L59
[llvm-objcat]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/lib/Object/Error.cpp#L77-L80
[llvm-objcat-h]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/include/llvm/Object/Error.h#L26
[llvm-export]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/docs/InterfaceExportAnnotations.rst?plain=1#L1-L72
[llvm-export-class]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/docs/InterfaceExportAnnotations.rst?plain=1#L249-L263
[llvm-manual-error]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/docs/ProgrammersManual.md?plain=1#L439-L456
[llvm-manual-interop]: https://github.com/llvm/llvm-project/blob/llvmorg-23.1.5/llvm/docs/ProgrammersManual.md?plain=1#L701-L720

[absl]: https://github.com/abseil/abseil-cpp/tree/20260817.0
[absl-code]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L78-L107
[absl-rep]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L813-L821
[absl-inline]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L1089-L1104
[absl-eq]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L1030-L1035
[absl-msg]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L1023-L1028
[absl-errno]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.h#L932-L944
[absl-make-rep]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.cc#L108-L125
[absl-code-name]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.cc#L45-L50
[absl-errno-cc]: https://github.com/abseil/abseil-cpp/blob/20260817.0/absl/status/status.cc#L402-L413
