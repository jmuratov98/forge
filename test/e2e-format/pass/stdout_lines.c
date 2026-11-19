#include <stdio.h>

int main(void) {
    puts("hello");
    puts("  indented, with trailing space ");
    puts("");
    puts("last");
    return 0;
}

// EXPECT-EXIT: 0
// EXPECT-STDOUT: hello
// EXPECT-STDOUT:   indented, with trailing space 
// EXPECT-STDOUT:
// EXPECT-STDOUT: last
