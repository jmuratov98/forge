# Compiler minimums, language flags, and warnings for Forge's own source
# (ADR 0003, docs/style.md).

# The oldest version of each compiler that implements every language feature
# and header on ADR 0004's allowlist: concepts, consteval, constinit,
# <source_location>, <bit>, <compare>, <concepts>, <version>. CI builds with
# these wherever the runner images can supply them; see docs/building.md.
set(FORGE_MIN_GNU_VERSION 11.0)
set(FORGE_MIN_CLANG_VERSION 16.0)
set(FORGE_MIN_APPLECLANG_VERSION 15.0)
set(FORGE_MIN_MSVC_VERSION 19.30)

# forge_check_compiler(<compiler-id> <compiler-version>)
function(forge_check_compiler id version)
  if(id STREQUAL "GNU")
    set(minimum ${FORGE_MIN_GNU_VERSION})
  elseif(id STREQUAL "Clang")
    set(minimum ${FORGE_MIN_CLANG_VERSION})
  elseif(id STREQUAL "AppleClang")
    set(minimum ${FORGE_MIN_APPLECLANG_VERSION})
  elseif(id STREQUAL "MSVC")
    set(minimum ${FORGE_MIN_MSVC_VERSION})
  else()
    message(FATAL_ERROR
      "Forge does not support the ${id} C++ compiler. "
      "Supported: GNU, Clang, AppleClang, MSVC.")
  endif()

  if(version VERSION_LESS minimum)
    message(FATAL_ERROR
      "Forge needs ${id} ${minimum} or newer; this is ${id} ${version}.")
  endif()
endfunction()

# Checks the compiler, then sets the language flags every target and every
# dependency built here (googletest included) is compiled with.
function(forge_configure_compiler)
  forge_check_compiler("${CMAKE_CXX_COMPILER_ID}" "${CMAKE_CXX_COMPILER_VERSION}")

  set(CMAKE_CXX_STANDARD 20 PARENT_SCOPE)
  set(CMAKE_CXX_STANDARD_REQUIRED ON PARENT_SCOPE)
  set(CMAKE_CXX_EXTENSIONS OFF PARENT_SCOPE)

  option(FORGE_WARNINGS_AS_ERRORS "Treat warnings in Forge's own targets as errors" OFF)

  if(CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC" OR MSVC)
    # CMake's defaults say /EHsc and /GR; drop them rather than override them.
    string(REGEX REPLACE "[/-]EH[a-z-]*" "" flags "${CMAKE_CXX_FLAGS}")
    string(REGEX REPLACE "[/-]GR-?( |$)" "" flags "${flags}")
    set(CMAKE_CXX_FLAGS "${flags}" PARENT_SCOPE)
    add_compile_options(
      "$<$<COMPILE_LANGUAGE:CXX>:/GR->"
      "$<$<COMPILE_LANGUAGE:CXX>:/EHs-c->"
      "$<$<COMPILE_LANGUAGE:CXX>:/Zc:__cplusplus>"
      "$<$<COMPILE_LANGUAGE:CXX>:/permissive->"
      "$<$<COMPILE_LANGUAGE:CXX>:/utf-8>")
    add_compile_definitions("$<$<COMPILE_LANGUAGE:CXX>:_HAS_EXCEPTIONS=0>")
    # C4577 says `noexcept` is used with no exception handling mode, which is
    # what ADR 0003 asks for. /external:W0 silences system headers, googletest's.
    set(warnings /W4 /wd4577 /external:W0)
    set(warnings_as_errors /WX)
  else()
    add_compile_options(
      "$<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>"
      "$<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions>")
    if(MINGW)
      # A MinGW binary should run without the toolchain's DLLs on PATH.
      add_link_options(-static)
    endif()
    set(warnings -Wall -Wextra -Wpedantic)
    set(warnings_as_errors -Werror)
  endif()

  # Warnings apply to Forge's own targets only, not to googletest.
  add_library(forge_build_options INTERFACE)
  target_compile_options(forge_build_options INTERFACE
    "$<$<COMPILE_LANGUAGE:CXX>:${warnings}>")
  if(FORGE_WARNINGS_AS_ERRORS)
    target_compile_options(forge_build_options INTERFACE
      "$<$<COMPILE_LANGUAGE:CXX>:${warnings_as_errors}>")
  endif()
endfunction()
