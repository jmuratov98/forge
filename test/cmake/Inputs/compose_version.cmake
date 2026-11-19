# cmake -DFORGE_ROOT=<repo> -DVERSION=X.Y.Z [-DSTAGE=..] [-DTIMESTAMP=..] [-DSHA=..] -P compose_version.cmake

# The project's root file sets the policies; a script run with -P has to. Without
# this, CMake before 4.0 warns about CMP0011 on stderr, which the test reads.
cmake_minimum_required(VERSION 3.24)

list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeVersion)
forge_compose_version(version
  VERSION "${VERSION}" STAGE "${STAGE}" TIMESTAMP "${TIMESTAMP}" SHA "${SHA}")
message("${version}")
