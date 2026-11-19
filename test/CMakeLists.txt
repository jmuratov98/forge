# The toolchain contract checks the build's flags, not a library, so it lives
# here and not in a library's test/ directory. It is recorded with the
# libraries' googletest binaries so check-unit builds it before running CTest.
add_executable(toolchain_contract_tests toolchain_contract_test.cpp)
target_link_libraries(toolchain_contract_tests PRIVATE
  GTest::gtest_main forge_build_options)
gtest_discover_tests(toolchain_contract_tests DISCOVERY_MODE PRE_TEST)
set_property(GLOBAL APPEND PROPERTY FORGE_UNIT_TEST_TARGETS toolchain_contract_tests)
