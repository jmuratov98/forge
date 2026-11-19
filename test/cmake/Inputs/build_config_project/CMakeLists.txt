cmake_minimum_required(VERSION 3.24)
project(build_config_fixture LANGUAGES NONE)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeBuildConfig)
forge_configure_build()
