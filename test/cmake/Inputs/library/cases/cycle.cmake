forge_add_library(core SOURCES empty.cpp)
forge_add_library(source SOURCES empty.cpp PRIVATE_DEPENDS core)
forge_add_library(billet SOURCES empty.cpp PRIVATE_DEPENDS core source)
forge_add_library(ingot SOURCES empty.cpp PRIVATE_DEPENDS billet)

# Bypassing forge_add_library: billet and ingot depend on each other.
target_link_libraries(forge_billet PRIVATE forge_ingot)
