// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

// Every 0/1 macro here exists to be tested by #if, which an enum cannot serve.
// NOLINTBEGIN(modernize-macro-to-enum)

// Host compiler and host platform configuration. Every forge header includes this one,
// directly or not, so it is pure preprocessor: detection, checks on the macros the build
// passes, symbol visibility, and portable spellings of attributes and builtins.
//
// Every FORGE_ configuration macro is defined to 0 or 1 and tested with #if, never #ifdef;
// -Wundef turns a misspelled name or a missing include into a warning. "Host" always means
// the machine forge itself is built for, never a target that forge compiles for.
//
// Deliberately absent, because C++20 already provides them: [[nodiscard]],
// [[maybe_unused]], [[fallthrough]], [[noreturn]], [[deprecated]], [[likely]],
// [[unlikely]], __has_cpp_attribute, constinit, std::endian, std::source_location,
// std::is_constant_evaluated and std::assume_aligned. Assertions are not here either: they
// need a failure handler, which is code.
//
// The compilers' own macros are tested with #ifdef where possible. #elifdef is C++23, so
// `#elif defined(X)` stays, with a NOLINT for when clang-tidy runs as C++23.

// MSVC leaves __cplusplus at 199711L unless /Zc:__cplusplus is passed; _MSVC_LANG is always
// right, and clang-cl defines it too.
#ifdef _MSVC_LANG
#  define FORGE_CXX _MSVC_LANG
#else
#  define FORGE_CXX __cplusplus
#endif

#if FORGE_CXX < 202002L
#  error "forge requires C++20 or later"
#endif

// Exactly one of these is 1. clang-cl and AppleClang count as Clang; FORGE_COMPILER_MSVC
// means cl.exe itself. Clang also defines __GNUC__, so it is tested first.
#ifdef __clang__
#  define FORGE_COMPILER_CLANG 1
#  define FORGE_COMPILER_GCC 0
#  define FORGE_COMPILER_MSVC 0
#elif defined(__GNUC__) // NOLINT(readability-use-concise-preprocessor-directives)
#  define FORGE_COMPILER_CLANG 0
#  define FORGE_COMPILER_GCC 1
#  define FORGE_COMPILER_MSVC 0
#elif defined(_MSC_VER) // NOLINT(readability-use-concise-preprocessor-directives)
#  define FORGE_COMPILER_CLANG 0
#  define FORGE_COMPILER_GCC 0
#  define FORGE_COMPILER_MSVC 1
#else
#  error "forge supports GCC, Clang and MSVC; add this compiler to forge/core/config.hpp"
#endif

// The oldest supported compilers, each with complete C++20 including <format>. AppleClang
// numbers its releases apart from LLVM: AppleClang 16 is roughly LLVM 17. There are no
// version macros for code to test; prefer FORGE_HAS_BUILTIN, __has_cpp_attribute and the
// standard feature-test macros, which also get AppleClang right.
#if FORGE_COMPILER_CLANG
#  ifdef __apple_build_version__
#    if __clang_major__ < 16
#      error "forge requires AppleClang 16 or later"
#    endif
#  elif __clang_major__ < 17
#    error "forge requires Clang 17 or later"
#  endif
#elif FORGE_COMPILER_GCC
#  if __GNUC__ < 13
#    error "forge requires GCC 13 or later"
#  endif
#elif FORGE_COMPILER_MSVC
#  if _MSC_VER < 1944
#    error "forge requires MSVC 19.44 (Visual Studio 2022 17.14) or later"
#  endif
#endif

// forge's macros are written for the standard preprocessor (__VA_OPT__, _Pragma), which
// cl.exe only uses under /Zc:preprocessor. clang-cl always does.
#if FORGE_COMPILER_MSVC
#  if _MSVC_TRADITIONAL
#    error "forge requires the conforming MSVC preprocessor: compile with /Zc:preprocessor"
#  endif
#endif

// Host operating system: exactly one of the first three is 1. Porting forge to another host
// starts here.
#ifdef _WIN32
#  define FORGE_HOST_WINDOWS 1
#  define FORGE_HOST_LINUX 0
#  define FORGE_HOST_MACOS 0
#  define FORGE_HOST_POSIX 0
#elif defined(__linux__) // NOLINT(readability-use-concise-preprocessor-directives)
#  define FORGE_HOST_WINDOWS 0
#  define FORGE_HOST_LINUX 1
#  define FORGE_HOST_MACOS 0
#  define FORGE_HOST_POSIX 1
#elif defined(__APPLE__) && defined(__MACH__)
#  define FORGE_HOST_WINDOWS 0
#  define FORGE_HOST_LINUX 0
#  define FORGE_HOST_MACOS 1
#  define FORGE_HOST_POSIX 1
#else
#  error "unsupported host operating system; add it to forge/core/config.hpp"
#endif

// Host architecture, for code with per-architecture fast paths. Other architectures leave
// both at 0 and take the portable path.
#if defined(__x86_64__) || defined(_M_X64)
#  define FORGE_HOST_X86_64 1
#  define FORGE_HOST_AARCH64 0
#elif defined(__aarch64__) || defined(_M_ARM64)
#  define FORGE_HOST_X86_64 0
#  define FORGE_HOST_AARCH64 1
#else
#  define FORGE_HOST_X86_64 0
#  define FORGE_HOST_AARCH64 0
#endif

// The build passes these (premake/forge.lua), so a missing one means this file is being
// compiled outside the build, e.g. from a stale compile_commands.json; only the first problem
// is reported, to keep that case readable. Code should test what it depends on rather than a
// configuration name: --assertions turns assertions on in Release, and the Sanitize
// configuration need not include AddressSanitizer.
#define FORGE_DETAIL_IS_0_OR_1(x) ((x) == 0 || (x) == 1)

#if !defined(FORGE_ASSERTIONS_ENABLED) || !FORGE_DETAIL_IS_0_OR_1(FORGE_ASSERTIONS_ENABLED)
#  error "FORGE_ASSERTIONS_ENABLED must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_EXCEPTIONS_ENABLED) || !FORGE_DETAIL_IS_0_OR_1(FORGE_EXCEPTIONS_ENABLED)
#  error "FORGE_EXCEPTIONS_ENABLED must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_SHARED) || !FORGE_DETAIL_IS_0_OR_1(FORGE_SHARED)
#  error "FORGE_SHARED must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_BUILDING_SHARED) || !FORGE_DETAIL_IS_0_OR_1(FORGE_BUILDING_SHARED)
#  error "FORGE_BUILDING_SHARED must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_DEBUG) || !FORGE_DETAIL_IS_0_OR_1(FORGE_DEBUG)
#  error "FORGE_DEBUG must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_RELEASE) || !FORGE_DETAIL_IS_0_OR_1(FORGE_RELEASE)
#  error "FORGE_RELEASE must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_RELDEB) || !FORGE_DETAIL_IS_0_OR_1(FORGE_RELDEB)
#  error "FORGE_RELDEB must be defined to 0 or 1; the build passes it"
#elif !defined(FORGE_SANITIZE) || !FORGE_DETAIL_IS_0_OR_1(FORGE_SANITIZE)
#  error "FORGE_SANITIZE must be defined to 0 or 1; the build passes it"
#elif FORGE_DEBUG + FORGE_RELEASE + FORGE_RELDEB + FORGE_SANITIZE != 1
#  error "exactly one of FORGE_DEBUG, FORGE_RELEASE, FORGE_RELDEB and FORGE_SANITIZE must be 1"
#elif FORGE_BUILDING_SHARED && !FORGE_SHARED
#  error "FORGE_BUILDING_SHARED requires FORGE_SHARED"
#elif FORGE_EXCEPTIONS_ENABLED != (defined(__cpp_exceptions) || defined(_CPPUNWIND))
#  error "FORGE_EXCEPTIONS_ENABLED disagrees with whether the compiler has exceptions enabled"
#endif

#undef FORGE_DETAIL_IS_0_OR_1

// 0 where the compiler has no __has_builtin or __has_feature. There is no
// FORGE_HAS_CPP_ATTRIBUTE: __has_cpp_attribute is standard.
#ifdef __has_builtin
#  define FORGE_HAS_BUILTIN(x) __has_builtin(x)
#else
#  define FORGE_HAS_BUILTIN(x) 0
#endif

#ifdef __has_feature
#  define FORGE_HAS_FEATURE(x) __has_feature(x)
#else
#  define FORGE_HAS_FEATURE(x) 0
#endif

// FORGE_STRINGIFY and FORGE_CONCAT expand their arguments first, so
// FORGE_STRINGIFY(FORGE_SHARED) is "0" or "1", not "FORGE_SHARED".
#define FORGE_DETAIL_STRINGIFY(x) #x
#define FORGE_STRINGIFY(x) FORGE_DETAIL_STRINGIFY(x)
#define FORGE_DETAIL_CONCAT(a, b) a##b
#define FORGE_CONCAT(a, b) FORGE_DETAIL_CONCAT(a, b)

#if FORGE_COMPILER_MSVC
#  define FORGE_PRAGMA(x) __pragma(x)
#else
#  define FORGE_PRAGMA(x) _Pragma(#x)
#endif

// Silencing a host-compiler warning for a few lines. Each compiler has its own IGNORE macro,
// which is empty elsewhere, because GCC and Clang warn about each other's unknown flags:
//
//   FORGE_WARNINGS_PUSH
//   FORGE_WARNING_IGNORE_GCC("-Wshadow")
//   FORGE_WARNING_IGNORE_MSVC(4457)
//   ...
//   FORGE_WARNINGS_POP
//
// These are named after warnings, not diagnostics, because diagnostics are what forge
// itself reports.
#if FORGE_COMPILER_CLANG
#  define FORGE_WARNINGS_PUSH FORGE_PRAGMA(clang diagnostic push)
#  define FORGE_WARNINGS_POP FORGE_PRAGMA(clang diagnostic pop)
#  define FORGE_WARNING_IGNORE_CLANG(flag) FORGE_PRAGMA(clang diagnostic ignored flag)
#  define FORGE_WARNING_IGNORE_GCC(flag)
#  define FORGE_WARNING_IGNORE_MSVC(number)
#elif FORGE_COMPILER_GCC
#  define FORGE_WARNINGS_PUSH FORGE_PRAGMA(GCC diagnostic push)
#  define FORGE_WARNINGS_POP FORGE_PRAGMA(GCC diagnostic pop)
#  define FORGE_WARNING_IGNORE_CLANG(flag)
#  define FORGE_WARNING_IGNORE_GCC(flag) FORGE_PRAGMA(GCC diagnostic ignored flag)
#  define FORGE_WARNING_IGNORE_MSVC(number)
#else
#  define FORGE_WARNINGS_PUSH FORGE_PRAGMA(warning(push))
#  define FORGE_WARNINGS_POP FORGE_PRAGMA(warning(pop))
#  define FORGE_WARNING_IGNORE_CLANG(flag)
#  define FORGE_WARNING_IGNORE_GCC(flag)
#  define FORGE_WARNING_IGNORE_MSVC(number) FORGE_PRAGMA(warning(disable : number))
#endif

// FORGE_API marks what libforge exports when it is built as one shared library (--shared),
// where every other symbol is hidden; in the static build it is empty. It goes after any
// attributes, FORGE_ ones included: `class FORGE_API foo`, `[[nodiscard]] FORGE_API int f();`.
#if FORGE_SHARED && FORGE_HOST_WINDOWS
#  if FORGE_BUILDING_SHARED
#    define FORGE_API __declspec(dllexport)
#  else
#    define FORGE_API __declspec(dllimport)
#  endif
#elif FORGE_SHARED
#  define FORGE_API __attribute__((visibility("default")))
#else
#  define FORGE_API
#endif

// Attributes the standard does not spell. Each goes at the start of a declaration.
//
// FORGE_ALWAYS_INLINE      inline, and inlined even when the optimizer would decline
// FORGE_NOINLINE           never inlined
// FORGE_COLD               rarely called, e.g. error reporting: optimized for size and laid
//                          out away from hot code
// FORGE_DUMP_METHOD        for dump() and similar debugging aids: never inlined or discarded,
//                          so a debugger can call it in every build
// FORGE_RETURNS_NONNULL    the returned pointer is never null
// FORGE_RETURNS_NOALIAS    the returned pointer aliases nothing else, e.g. fresh memory from
//                          an allocator
#if FORGE_COMPILER_MSVC
#  define FORGE_ALWAYS_INLINE [[msvc::forceinline]] inline
#  define FORGE_NOINLINE [[msvc::noinline]]
#  define FORGE_COLD
#  define FORGE_HOT
#  define FORGE_DUMP_METHOD [[msvc::noinline]]
#  define FORGE_NONNULL(...)
#  define FORGE_RETURNS_NONNULL
#  define FORGE_RETURNS_NOALIAS __declspec(restrict)
#else
#  define FORGE_ALWAYS_INLINE [[gnu::always_inline]] inline
#  define FORGE_NOINLINE [[gnu::noinline]]
#  define FORGE_COLD [[gnu::cold]]
#  define FORGE_HOT [[gnu::hot]]
#  define FORGE_DUMP_METHOD [[gnu::noinline, gnu::used, gnu::cold]]
#  define FORGE_NONNULL(...) [[gnu::nonnull __VA_OPT__((__VA_ARGS__))]]
#  define FORGE_RETURNS_NONNULL [[gnu::returns_nonnull]]
#  define FORGE_RETURNS_NOALIAS [[gnu::malloc]]
#endif

// The result may refer to the argument, so the compiler can warn when it outlives it. It
// goes after a parameter, or after a member function's parameter list for `this`:
//
//   std::string_view name(const std::string& text FORGE_LIFETIMEBOUND);
//   std::string_view text() const FORGE_LIFETIMEBOUND;
#if __has_cpp_attribute(clang::lifetimebound)
#  define FORGE_LIFETIMEBOUND [[clang::lifetimebound]]
#elif __has_cpp_attribute(msvc::lifetimebound)
#  define FORGE_LIFETIMEBOUND [[msvc::lifetimebound]]
#else
#  define FORGE_LIFETIMEBOUND
#endif

// Under the MSVC ABI (cl.exe and clang-cl), [[no_unique_address]] is accepted but ignored,
// to keep layouts compatible; [[msvc::no_unique_address]] is the one that is honored.
#if defined(_MSC_VER) && __has_cpp_attribute(msvc::no_unique_address)
#  define FORGE_NO_UNIQUE_ADDRESS [[msvc::no_unique_address]]
#else
#  define FORGE_NO_UNIQUE_ADDRESS [[no_unique_address]]
#endif

#if FORGE_COMPILER_MSVC
#  define FORGE_BUILTIN_UNREACHABLE() __assume(false)
#else
#  define FORGE_BUILTIN_UNREACHABLE() __builtin_unreachable()
#endif

// Ends the program at once, without running any handler. Unlike FORGE_BUILTIN_UNREACHABLE,
// reaching it is defined behaviour, so the optimizer cannot assume the path away. cl.exe
// declares __fastfail, and __debugbreak below, in <intrin.h>; 7 is FAST_FAIL_FATAL_APP_EXIT.
#if FORGE_COMPILER_MSVC
#  include <intrin.h>
#  define FORGE_BUILTIN_TRAP() __fastfail(7)
#else
#  define FORGE_BUILTIN_TRAP() __builtin_trap()
#endif

#if FORGE_COMPILER_MSVC
#  define FORGE_BUILTIN_BREAKPOINT() __debugbreak()
#elif FORGE_COMPILER_CLANG
#  define FORGE_BUILTIN_BREAKPOINT() __builtin_debugtrap()
#else // FORGE_COMPILER_GCC
#  if FORGE_HOST_X86_64
#    define FORGE_BUILTIN_BREAKPOINT() __asm__ volatile("int3")
#  elif FORGE_HOST_AARCH64
#    define FORGE_BUILTIN_BREAKPOINT() __asm__ volatile("brk #0xf000")
#  else
#    define FORGE_BUILTIN_BREAKPOINT() __builtin_trap()
#  endif
#endif

// Sanitizers the code is being compiled with. GCC has no macro for UndefinedBehaviorSanitizer,
// so it cannot be detected here.
#if defined(__SANITIZE_ADDRESS__) || FORGE_HAS_FEATURE(address_sanitizer)
#  define FORGE_ASAN_ENABLED 1
#else
#  define FORGE_ASAN_ENABLED 0
#endif

#if defined(__SANITIZE_THREAD__) || FORGE_HAS_FEATURE(thread_sanitizer)
#  define FORGE_TSAN_ENABLED 1
#else
#  define FORGE_TSAN_ENABLED 0
#endif

#if FORGE_CXX >= 202302L && __has_cpp_attribute(assume)
#  define FORGE_ASSUME(cond) [[assume(cond)]]
#else
#  if FORGE_COMPILER_MSVC
#    define FORGE_ASSUME(cond) __assume(cond)
#  elif FORGE_COMPILER_CLANG
#    define FORGE_ASSUME(cond) __builtin_assume(cond)
#  else
#    define FORGE_ASSUME(cond) [[gnu::assume(cond)]]
#  endif
#endif

// Lets allocators that carve up their own memory (arenas, pools) tell AddressSanitizer which
// bytes are not live, so a use of them is reported. Without ASan both still evaluate their
// arguments, so side effects do not depend on the build.
#if FORGE_ASAN_ENABLED
#  include <sanitizer/asan_interface.h>
#  define FORGE_ASAN_POISON(addr, size) __asan_poison_memory_region((addr), (size))
#  define FORGE_ASAN_UNPOISON(addr, size) __asan_unpoison_memory_region((addr), (size))
#else
#  define FORGE_ASAN_POISON(addr, size) ((void)(addr), (void)(size))
#  define FORGE_ASAN_UNPOISON(addr, size) ((void)(addr), (void)(size))
#endif

// NOLINTEND(modernize-macro-to-enum)
