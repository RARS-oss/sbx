#include <stdlib.h>
#include <stdio.h>

/* Buffer for the generated stream. */
#define CAP 128
#define RECORDS 60

/* Deterministic PRNG (fixed seed) — so the run is reproducible, but the total size of the
   generated stream is NOT knowable from the source without executing the sequence. */
static unsigned long s = 0x1234567u;
static unsigned rng(void) {
    s = s * 6364136223846793005UL + 1442695040888963407UL;
    return (unsigned)(s >> 33);
}

int main(void) {
    unsigned char buf[CAP];
    int pos = 0;
    unsigned long sum = 0;
    for (int r = 0; r < RECORDS; r++) {
        int len = 1 + (rng() % 12);           /* record length 1..12, decided at runtime */
        for (int k = 0; k < len; k++) {
            unsigned char b = (unsigned char)(rng() & 0xff);
            buf[pos++] = b;                    /* overflows: the total stream is far bigger than CAP */
            sum += b;
        }
    }
    printf("total=%d sum=%lu\n", pos, sum);
    return 0;
}
