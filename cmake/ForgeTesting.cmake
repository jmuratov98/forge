# Test harnesses (docs/testing.md, ADR 0009): googletest through CTest, lit for
# file-based tests, and one `check` target that runs both. Building Forge
# without tests (-DFORGE_BUILD_TESTS=OFF) needs neither Python nor the network.

option(FORGE_SYSTEM_GOOGLETEST
  "Use an installed googletest instead of fetching the pinned release" OFF)

# The pinned googletest release.
set(FORGE_GOOGLETEST_URL
  "https://github.com/google/googletest/archive/refs/tags/v1.17.0.tar.gz")
set(FORGE_GOOGLETEST_SHA256
  "65fab701d9829d38cb77c14acdc431d2108bfdbf8979e40eb8ae567edf10b27c")

function(_forge_find_lit)
  find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)
  execute_process(COMMAND "${Python3_EXECUTABLE}" -c "import lit"
    RESULT_VARIABLE lit_missing OUTPUT_QUIET ERROR_QUIET)
  if(lit_missing)
    message(FATAL_ERROR
      "The tests need lit for ${Python3_EXECUTABLE}. Install it with:\n"
      "  ${Python3_EXECUTABLE} -m pip install -r ${CMAKE_SOURCE_DIR}/test/requirements.txt\n"
      "or configure with -DFORGE_BUILD_TESTS=OFF.")
  endif()
  set(FORGE_PYTHON "${Python3_EXECUTABLE}" PARENT_SCOPE)
endfunction()

function(_forge_make_googletest_available)
  # ADR 0003: no exceptions anywhere, googletest included.
  add_compile_definitions(GTEST_HAS_EXCEPTIONS=0)

  if(FORGE_SYSTEM_GOOGLETEST)
    find_package(GTest REQUIRED)
    return()
  endif()

  include(FetchContent)
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  FetchContent_Declare(googletest
    URL "${FORGE_GOOGLETEST_URL}"
    URL_HASH "SHA256=${FORGE_GOOGLETEST_SHA256}"
    DOWNLOAD_EXTRACT_TIMESTAMP ON)
  FetchContent_MakeAvailable(googletest)
endfunction()

# The command line that compiles a C file with the host's C compiler; the
# end-to-end runner's self-test uses it in place of Forge, which can't compile
# yet. {src}, {out} and {obj} are filled in by the runner.
function(_forge_write_selftest_compiler path)
  if(CMAKE_C_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC" OR MSVC)
    set(command "\"@compiler@\", \"/nologo\", \"/Fe:{out}\", \"/Fo:{obj}\", \"{src}\"")
  else()
    set(command "\"@compiler@\", \"-o\", \"{out}\", \"{src}\"")
  endif()
  file(TO_CMAKE_PATH "${CMAKE_C_COMPILER}" compiler)
  string(CONFIGURE "${command}" command @ONLY)
  file(WRITE "${path}" "[${command}]\n")
endfunction()

# Finds lit and makes googletest and gtest_discover_tests available. The root
# file calls it before it adds the libraries, so each library's own test/
# directory can declare its googletest binary. lit is looked for first, so a
# missing lit is reported before anything is downloaded.
#
# A macro, so what GoogleTest and _forge_find_lit set lands in the root
# directory's scope and reaches the libraries' directories below it.
macro(forge_enable_unit_testing)
  _forge_find_lit()
  _forge_make_googletest_available()
  include(GoogleTest)
endmacro()

# Adds the cross-library tests in test/, lit's configuration, and the check
# targets. The root file calls it after the libraries, whose test binaries
# check-unit runs.
function(forge_setup_testing)
  add_subdirectory("${CMAKE_SOURCE_DIR}/test" "${CMAKE_BINARY_DIR}/test")

  file(TO_CMAKE_PATH "${CMAKE_SOURCE_DIR}" FORGE_SOURCE_DIR)
  file(TO_CMAKE_PATH "${CMAKE_BINARY_DIR}" FORGE_BUILD_DIR)
  file(TO_CMAKE_PATH "${CMAKE_COMMAND}" FORGE_CMAKE)
  file(TO_CMAKE_PATH "${CMAKE_MAKE_PROGRAM}" FORGE_NINJA)
  file(TO_CMAKE_PATH "${FORGE_PYTHON}" FORGE_PYTHON_EXE)
  find_program(FORGE_CLANG_TIDY NAMES clang-tidy)
  # A failed search leaves FORGE_CLANG_TIDY-NOTFOUND, which lit would read as a
  # path; an empty string is what turns the clang-tidy tests off.
  if(FORGE_CLANG_TIDY)
    file(TO_CMAKE_PATH "${FORGE_CLANG_TIDY}" FORGE_CLANG_TIDY)
  else()
    set(FORGE_CLANG_TIDY "")
  endif()
  set(FORGE_EXE "${FORGE_BUILD_DIR}/bin/forge${CMAKE_EXECUTABLE_SUFFIX}")
  configure_file("${CMAKE_SOURCE_DIR}/test/lit.site.cfg.py.in"
    "${CMAKE_BINARY_DIR}/test/lit.site.cfg.py" @ONLY)
  _forge_write_selftest_compiler("${CMAKE_BINARY_DIR}/test/e2e_selftest_compiler.json")

  add_custom_target(check-unit
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${CMAKE_BINARY_DIR}" --output-on-failure
    DEPENDS toolchain_contract_tests
    USES_TERMINAL)
  add_custom_target(check-lit
    COMMAND "${FORGE_PYTHON}" -c "from lit.main import main; main()"
      -sv "${CMAKE_BINARY_DIR}/test"
    DEPENDS forge
    USES_TERMINAL
    VERBATIM)
  add_custom_target(check DEPENDS check-unit check-lit)
endfunction()
