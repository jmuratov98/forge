forge_add_library(core SOURCES empty.cpp)
forge_add_library(source SOURCES empty.cpp PRIVATE_DEPENDS core)
forge_add_library(billet SOURCES empty.cpp PRIVATE_DEPENDS core source)
forge_add_library(blank SOURCES empty.cpp PRIVATE_DEPENDS billet)
forge_add_library(object SOURCES empty.cpp PRIVATE_DEPENDS core source)
# fold depends only on object, besides source and core.
forge_add_library(fold SOURCES empty.cpp PRIVATE_DEPENDS object blank)
