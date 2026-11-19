cmake_minimum_required(VERSION 3.24)
project(msvc_flags_fixture LANGUAGES NONE)

# Stands in for an MSVC configure on any host: forge_configure_compiler reads
# only these three variables to take its MSVC branch.
set(CMAKE_CXX_COMPILER_ID MSVC)
set(CMAKE_CXX_COMPILER_VERSION 19.44.35211)
set(CMAKE_CXX_COMPILER_FRONTEND_VARIANT MSVC)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeCompiler)
forge_configure_compiler()

get_directory_property(options COMPILE_OPTIONS)
foreach(option IN LISTS options)
  message(STATUS "option: ${option}")
endforeach()
get_directory_property(definitions COMPILE_DEFINITIONS)
foreach(definition IN LISTS definitions)
  message(STATUS "definition: ${definition}")
endforeach()
