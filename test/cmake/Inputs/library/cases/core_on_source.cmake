# core is at the bottom: it depends on nothing, source included.
forge_add_library(core SOURCES empty.cpp PRIVATE_DEPENDS source)
