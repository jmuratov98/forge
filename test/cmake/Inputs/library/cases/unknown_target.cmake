forge_add_library(core SOURCES empty.cpp)
# Bypassing forge_add_library with a library docs/layout.md does not list.
add_library(forge_widgets STATIC empty.cpp)
target_link_libraries(forge_widgets PRIVATE forge_core)
