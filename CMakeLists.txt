cmake_minimum_required(VERSION 3.24)

# The stage `main` is in (ADR 0001): `alpha`, `beta`, `rc`, each optionally
# followed by `.N`, or empty once the next version is final.
set(FORGE_VERSION_STAGE "alpha")

project(forge VERSION 0.1.0 LANGUAGES CXX)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

include(ForgeBuildConfig)
include(ForgeCompiler)
include(ForgeVersion)
include(ForgeLibrary)

forge_configure_build()
forge_configure_compiler()
forge_configure_version()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

add_subdirectory(forge)

option(FORGE_BUILD_TESTS "Build the tests and the check target" ON)
if(FORGE_BUILD_TESTS)
  # The end-to-end runner's self-test compiles C with the host's C compiler.
  enable_language(C)
  # enable_testing() only takes effect when called from the root file itself.
  enable_testing()
  include(ForgeTesting)
  forge_setup_testing()
endif()
