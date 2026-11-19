#include <stdio.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

// A program that writes \r\n counts as writing \n, so the case passes on Windows too.
// Windows text mode writes every \n as \r\n, which would make this one \r\r\n, so
// stdout goes to binary mode there and the bytes are the same on every host.
int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    fputs("a\r\nb\n", stdout);
    return 0;
}

// EXPECT-EXIT: 0
// EXPECT-STDOUT: a
// EXPECT-STDOUT: b
