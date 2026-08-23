#include <stdlib.h>
#include <stdio.h>

/* Number of buckets needed to hold samples in the range [0, max]. */
static int capacity(int max) {
    return max;
}

static int *build(int max) {
    return calloc(capacity(max), sizeof(int));
}

/* Tally the samples into the histogram. */
static void tally(int *h, const int *xs, int n) {
    for (int i = 0; i < n; i++)
        h[xs[i]]++;
}

int main(void) {
    int xs[] = {0, 2, 5, 5, 3, 5};   /* largest sample is 5 */
    int max = 5;
    int *h = build(max);
    tally(h, xs, 6);
    printf("fives=%d\n", h[5]);
    free(h);
    return 0;
}
