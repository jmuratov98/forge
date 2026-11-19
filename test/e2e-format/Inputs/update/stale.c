#include <stdio.h>

int main(void) {
    puts("hello");
    puts("");
    puts("world");
    return 4;
}

// EXPECT-EXIT: 99
// EXPECT-STDOUT: out of date
