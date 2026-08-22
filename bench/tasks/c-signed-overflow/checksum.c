#include <stdio.h>

/* Rolling checksum: h = h*31 + byte, modulo 2^32. Printed as 8 lowercase hex digits. */
static int update(int h, unsigned char b) {
    return h * 31 + b;
}

int main(void) {
    int h = 0;
    int c;
    while ((c = getchar()) != EOF) {
        h = update(h, (unsigned char)c);
    }
    printf("%08x\n", (unsigned)h);
    return 0;
}
