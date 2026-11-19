#include <stdio.h>

// A program that writes \r\n counts as writing \n, so the case passes on Windows too.
int main(void) {
    fputs("a\r\nb\n", stdout);
    return 0;
}

// EXPECT-EXIT: 0
// EXPECT-STDOUT: a
// EXPECT-STDOUT: b
