// Proves the googletest harness runs and that the build applied the flags the
// ADR 0003 subset depends on. Per-library test binaries replace this as
// libraries arrive (docs/testing.md).

#include <gtest/gtest.h>

TEST(toolchain_contract, language_level_is_cxx20) {
    // /Zc:__cplusplus makes MSVC report the real level.
    EXPECT_GE(__cplusplus, 202002L);
}

TEST(toolchain_contract, rtti_is_off) {
#if defined(__GXX_RTTI) || defined(__cpp_rtti) || defined(_CPPRTTI)
    ADD_FAILURE() << "RTTI is on; the build must pass -fno-rtti or /GR-";
#endif
}

TEST(toolchain_contract, exceptions_are_off) {
#if defined(__EXCEPTIONS) || defined(__cpp_exceptions) || defined(_CPPUNWIND)
    ADD_FAILURE() << "exceptions are on; the build must pass -fno-exceptions or /EHs-c-";
#endif
#if defined(_MSC_VER)
    EXPECT_EQ(_HAS_EXCEPTIONS, 0);
#endif
    EXPECT_EQ(GTEST_HAS_EXCEPTIONS, 0);
}
