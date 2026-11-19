# cmake -DFORGE_ROOT=<repo> -DID=<compiler id> -DVERSION=<version> -P check_compiler.cmake
list(APPEND CMAKE_MODULE_PATH "${FORGE_ROOT}/cmake")
include(ForgeCompiler)
forge_check_compiler("${ID}" "${VERSION}")
message("accepted ${ID} ${VERSION}")
