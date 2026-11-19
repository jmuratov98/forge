# Every library besides core may depend on core and source.
forge_add_library(core SOURCES empty.cpp)
forge_add_library(source SOURCES empty.cpp PRIVATE_DEPENDS core)
forge_add_library(object SOURCES empty.cpp PUBLIC_DEPENDS source PRIVATE_DEPENDS core)
