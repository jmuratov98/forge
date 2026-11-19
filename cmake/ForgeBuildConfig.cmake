# Build configurations and the assertion switch (ADR 0006).
#
#   Debug           assertions always on
#   RelWithDebInfo  assertions off; on with -DFORGE_ENABLE_ASSERTIONS=ON
#   Release         assertions compiled out; FORGE_ENABLE_ASSERTIONS=ON is an error
#   MinSizeRel      not supported
#
# Ninja is the only supported generator, so the configuration is known at
# configure time.

set(FORGE_BUILD_TYPES Debug RelWithDebInfo Release)

# Validates the generator and build type, then sets FORGE_ASSERTIONS_ENABLED to
# ON or OFF. The compile definition that carries it into C++ is added with
# FORGE_ASSERT.
function(forge_configure_build)
  get_property(multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
  if(multi_config)
    message(FATAL_ERROR
      "Forge supports single-configuration generators only, because the build "
      "type decides whether assertions are compiled. Use Ninja: "
      "cmake -G Ninja, or one of the presets in CMakePresets.json.")
  endif()

  if("${CMAKE_BUILD_TYPE}" STREQUAL "")
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "The build configuration" FORCE)
    message(STATUS "No CMAKE_BUILD_TYPE given; using Debug.")
  endif()
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS ${FORGE_BUILD_TYPES})

  if(NOT CMAKE_BUILD_TYPE IN_LIST FORGE_BUILD_TYPES)
    string(REPLACE ";" ", " supported "${FORGE_BUILD_TYPES}")
    message(FATAL_ERROR
      "Forge does not support CMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}. "
      "The supported configurations are ${supported}.")
  endif()

  option(FORGE_ENABLE_ASSERTIONS
    "Check FORGE_ASSERT in RelWithDebInfo builds (always on in Debug)" OFF)

  if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(assertions ON)
  elseif(CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo")
    set(assertions ${FORGE_ENABLE_ASSERTIONS})
  else()
    if(FORGE_ENABLE_ASSERTIONS)
      message(FATAL_ERROR
        "FORGE_ENABLE_ASSERTIONS=ON is not allowed in a Release build: "
        "assertions are compiled out of Release. Use RelWithDebInfo.")
    endif()
    set(assertions OFF)
  endif()

  message(STATUS "Forge build type: ${CMAKE_BUILD_TYPE}; assertions: ${assertions}")
  set(FORGE_ASSERTIONS_ENABLED ${assertions} PARENT_SCOPE)
endfunction()
