# The toolchain contract checks the build's flags, not a library, so it lives
# here and not in a library's test/ directory.
_forge_add_googletest_binary(toolchain_contract_tests
  SOURCES toolchain_contract_test.cpp)
