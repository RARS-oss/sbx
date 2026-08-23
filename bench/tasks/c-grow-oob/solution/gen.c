#include <stdlib.h>
#include <stdio.h>

#define RECORDS 60

static unsigned long s = 0x1234567u;
static unsigned rng(void) {
    s = s * 6364136223846793005UL + 1442695040888963407UL;
    return (unsigned)(s >> 33);
}

int main(void) {
    int cap = 16;
    unsigned char *buf = malloc(cap);
    int pos = 0;
    unsigned long sum = 0;
    for (int r = 0; r < RECORDS; r++) {
        int len = 1 + (rng() % 12);
        for (int k = 0; k < len; k++) {
            unsigned char b = (unsigned char)(rng() & 0xff);
            if (pos == cap) { cap *= 2; buf = realloc(buf, cap); }
            buf[pos++] = b;
            sum += b;
        }
    }
    printf("total=%d sum=%lu\n", pos, sum);
    free(buf);
    return 0;
}
