cmake_minimum_required(VERSION 3.24)
project(library_fixture LANGUAGES CXX)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeLibrary)

add_library(forge_build_options INTERFACE)

# Each case declares libraries the way a milestone would.
include("${CMAKE_CURRENT_SOURCE_DIR}/cases/${CASE}.cmake")
