# Declaring a Forge library (docs/layout.md).
#
# A library <name> gets the static target forge_<name>, the alias forge::<name>,
# and its own include root, so it can include only the headers of libraries it
# links. The dependency rules live in library_edges.json; an edge outside them
# is a configure error.

set(FORGE_LIBRARY_EDGES_FILE "${CMAKE_CURRENT_LIST_DIR}/library_edges.json")

# Sets <out-var> to the libraries <name> may depend on, or "*" for every one.
function(_forge_allowed_dependencies out_var name)
  file(READ "${FORGE_LIBRARY_EDGES_FILE}" edges)
  string(JSON allowed ERROR_VARIABLE error GET "${edges}" "${name}")
  if(error)
    message(FATAL_ERROR
      "Forge: '${name}' is not a library in docs/layout.md. "
      "Add it to cmake/library_edges.json and the layout first.")
  endif()

  set(result "")
  string(JSON count LENGTH "${allowed}")
  math(EXPR last "${count} - 1")
  if(count GREATER 0)
    foreach(index RANGE ${last})
      string(JSON dependency GET "${allowed}" ${index})
      list(APPEND result "${dependency}")
    endforeach()
  endif()
  set(${out_var} "${result}" PARENT_SCOPE)
endfunction()

# forge_add_library(<name>
#   SOURCES <files...>
#   [PUBLIC_DEPENDS <libraries...>]
#   [PRIVATE_DEPENDS <libraries...>])
#
# Dependencies are named without the prefix (`core`, not `forge_core`) and are
# PRIVATE unless listed under PUBLIC_DEPENDS, which is for libraries whose types
# appear in this library's public headers. Public headers live in
# <library dir>/include (forge/<name>/... inside it); private headers and
# sources are in <library dir>/src and are on no other library's include path.
function(forge_add_library name)
  cmake_parse_arguments(PARSE_ARGV 1 ARG "" "" "SOURCES;PUBLIC_DEPENDS;PRIVATE_DEPENDS")
  if(NOT ARG_SOURCES)
    message(FATAL_ERROR "forge_add_library(${name}): SOURCES is required.")
  endif()

  _forge_allowed_dependencies(allowed "${name}")
  foreach(dependency IN LISTS ARG_PUBLIC_DEPENDS ARG_PRIVATE_DEPENDS)
    if(NOT "*" IN_LIST allowed AND NOT dependency IN_LIST allowed)
      string(REPLACE ";" ", " allowed_text "${allowed}")
      message(FATAL_ERROR
        "Forge: ${name} may not depend on ${dependency}.\n"
        "docs/layout.md, Dependency rules. ${name} may depend on:\n"
        "  ${allowed_text}")
    endif()
    if(NOT TARGET forge_${dependency})
      message(FATAL_ERROR
        "Forge: ${name} depends on ${dependency}, which is not declared yet. "
        "Declare ${dependency} first.")
    endif()
  endforeach()

  add_library(forge_${name} STATIC ${ARG_SOURCES})
  add_library(forge::${name} ALIAS forge_${name})
  target_include_directories(forge_${name}
    PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include"
    PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")

  foreach(dependency IN LISTS ARG_PUBLIC_DEPENDS)
    target_link_libraries(forge_${name} PUBLIC forge_${dependency})
  endforeach()
  foreach(dependency IN LISTS ARG_PRIVATE_DEPENDS)
    target_link_libraries(forge_${name} PRIVATE forge_${dependency})
  endforeach()
  target_link_libraries(forge_${name} PRIVATE forge_build_options)
endfunction()
