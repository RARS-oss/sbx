#include <stdint.h>
#include <stdio.h>

/* Rolling checksum: h = h*31 + byte, modulo 2^32. Printed as 8 lowercase hex digits. */
static uint32_t update(uint32_t h, unsigned char b) {
    return h * 31u + b;
}

int main(void) {
    uint32_t h = 0;
    int c;
    while ((c = getchar()) != EOF) {
        h = update(h, (unsigned char)c);
    }
    printf("%08x\n", (unsigned)h);
    return 0;
}
