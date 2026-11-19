forge_add_library(core SOURCES empty.cpp)
forge_add_library(source SOURCES empty.cpp PRIVATE_DEPENDS core)
forge_add_library(billet SOURCES empty.cpp PRIVATE_DEPENDS core source)
# source may not depend on billet, and neither may its tests.
forge_add_unit_tests(source SOURCES empty.cpp PRIVATE_DEPENDS billet)
