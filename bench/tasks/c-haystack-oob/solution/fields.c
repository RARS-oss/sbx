#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 24 fields; each value is copied into its own 16-byte heap slot behind a length guard. */
static char *slot[24];

static int put(int i, const char *s) {
    size_t n = strlen(s);
    if (i ==  0) { if (n < 16) { memcpy(slot[ 0], s, n + 1); return 0; } return -1; }
    if (i ==  1) { if (n < 16) { memcpy(slot[ 1], s, n + 1); return 0; } return -1; }
    if (i ==  2) { if (n < 16) { memcpy(slot[ 2], s, n + 1); return 0; } return -1; }
    if (i ==  3) { if (n < 16) { memcpy(slot[ 3], s, n + 1); return 0; } return -1; }
    if (i ==  4) { if (n < 16) { memcpy(slot[ 4], s, n + 1); return 0; } return -1; }
    if (i ==  5) { if (n < 16) { memcpy(slot[ 5], s, n + 1); return 0; } return -1; }
    if (i ==  6) { if (n < 16) { memcpy(slot[ 6], s, n + 1); return 0; } return -1; }
    if (i ==  7) { if (n < 16) { memcpy(slot[ 7], s, n + 1); return 0; } return -1; }
    if (i ==  8) { if (n < 16) { memcpy(slot[ 8], s, n + 1); return 0; } return -1; }
    if (i ==  9) { if (n < 16) { memcpy(slot[ 9], s, n + 1); return 0; } return -1; }
    if (i == 10) { if (n < 16) { memcpy(slot[10], s, n + 1); return 0; } return -1; }
    if (i == 11) { if (n < 16) { memcpy(slot[11], s, n + 1); return 0; } return -1; }
    if (i == 12) { if (n < 16) { memcpy(slot[12], s, n + 1); return 0; } return -1; }
    if (i == 13) { if (n < 16) { memcpy(slot[13], s, n + 1); return 0; } return -1; }
    if (i == 14) { if (n < 16) { memcpy(slot[14], s, n + 1); return 0; } return -1; }
    if (i == 15) { if (n < 16) { memcpy(slot[15], s, n + 1); return 0; } return -1; }
    if (i == 16) { if (n < 16) { memcpy(slot[16], s, n + 1); return 0; } return -1; }
    if (i == 17) { if (n < 16) { memcpy(slot[17], s, n + 1); return 0; } return -1; }
    if (i == 18) { if (n < 16) { memcpy(slot[18], s, n + 1); return 0; } return -1; }
    if (i == 19) { if (n < 16) { memcpy(slot[19], s, n + 1); return 0; } return -1; }
    if (i == 20) { if (n < 16) { memcpy(slot[20], s, n + 1); return 0; } return -1; }
    if (i == 21) { if (n < 16) { memcpy(slot[21], s, n + 1); return 0; } return -1; }
    if (i == 22) { if (n < 16) { memcpy(slot[22], s, n + 1); return 0; } return -1; }
    if (i == 23) { if (n < 16) { memcpy(slot[23], s, n + 1); return 0; } return -1; }
    return -1;
}

int main(void) {
    for (int j = 0; j < 24; j++) { slot[j] = malloc(16); if (!slot[j]) return 3; }
    int i; char buf[256];
    while (scanf("%d %255s", &i, buf) == 2) {
        if (i < 0 || i >= 24) { fprintf(stderr, "bad field %d\n", i); continue; }
        if (put(i, buf) == 0) printf("ok %d\n", i);
        else printf("reject %d\n", i);
    }
    return 0;
}
