
#define FORGE_ASSERTIONS_ENABLED 1
#define FORGE_EXCEPTIONS_ENABLED 1
#define FORGE_SHARED 0
#define FORGE_BUILDING_SHARED 0
#define FORGE_DEBUG 1
#define FORGE_RELEASE 0
#define FORGE_RELDEB 0
#define FORGE_SANITIZE 0

#include <forge/core/assert.hpp>

int main() {
    constexpr static int a{5};
    FORGE_ASSERT(a != 5);
    FORGE_ASSERT(a != 5, "a cannot be 5, recieved {}", a);
    return 0;
}
