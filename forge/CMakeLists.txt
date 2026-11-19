# Libraries are declared with forge_add_library as their milestones arrive
# (docs/layout.md); add_subdirectory(<name>) goes here.

add_executable(forge main.cpp)
target_link_libraries(forge PRIVATE forge_build_options)
