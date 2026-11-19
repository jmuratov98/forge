// What forge/compiler.hpp promises on every host compiler.

#include "forge/compiler.hpp"

#include <gtest/gtest.h>

namespace {

struct empty {};

struct int_with_empty {
    int value;
    FORGE_NO_UNIQUE_ADDRESS empty tag;
};

// A compile-time check, so every host that builds core_tests has run it, MSVC
// (which ignores a plain [[no_unique_address]]) included.
static_assert(sizeof(int_with_empty) == sizeof(int),
              "FORGE_NO_UNIQUE_ADDRESS should let an empty member take no space");

// The static_assert already does the check; this test exists so CTest has one
// to discover and core_tests shows up in ctest -N and the IDE.
TEST(no_unique_address, empty_member_takes_no_space) {
    EXPECT_EQ(sizeof(int_with_empty), sizeof(int));
}

} // namespace
