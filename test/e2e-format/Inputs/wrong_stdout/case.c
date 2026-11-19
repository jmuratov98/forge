#include <stdio.h>

int main(void) {
    puts("one");
    puts("three");
    return 0;
}

// EXPECT-EXIT: 0
// EXPECT-STDOUT: one
// EXPECT-STDOUT: two
