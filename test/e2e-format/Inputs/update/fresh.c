#include <stdio.h>

int main(void) {
    puts("hello");
    puts("");
    puts("world");
    return 4;
}

// EXPECT-EXIT: 4
// EXPECT-STDOUT: hello
// EXPECT-STDOUT:
// EXPECT-STDOUT: world
