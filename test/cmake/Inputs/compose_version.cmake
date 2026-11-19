# cmake -DFORGE_ROOT=<repo> -DVERSION=X.Y.Z [-DSTAGE=..] [-DTIMESTAMP=..] [-DSHA=..] -P compose_version.cmake
list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeVersion)
forge_compose_version(version
  VERSION "${VERSION}" STAGE "${STAGE}" TIMESTAMP "${TIMESTAMP}" SHA "${SHA}")
message("${version}")
