cmake_minimum_required(VERSION 3.24)
project(version_fixture VERSION 1.2.3 LANGUAGES NONE)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeVersion)
forge_configure_version()
