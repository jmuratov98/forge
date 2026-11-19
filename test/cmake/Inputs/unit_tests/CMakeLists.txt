cmake_minimum_required(VERSION 3.24)
project(unit_tests_fixture LANGUAGES CXX)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeLibrary)

add_library(forge_build_options INTERFACE)

# An empty target stands in for googletest, so configuring needs neither the
# network nor a googletest build. Nothing here is built.
add_library(GTest::gtest_main INTERFACE IMPORTED)
enable_testing()
include(GoogleTest)

# Each case declares libraries and their tests the way a milestone would.
include("${CMAKE_CURRENT_SOURCE_DIR}/cases/${CASE}.cmake")
message(STATUS "unit tests fixture ok")
