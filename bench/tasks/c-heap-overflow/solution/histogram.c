#include <stdio.h>
#include <stdlib.h>

/* Reads N, then values; counts how many times each value 0..N-1 occurs. */
int main(void) {
    int n;
    if (scanf("%d", &n) != 1 || n <= 0) {
        fprintf(stderr, "bad N\n");
        return 2;
    }
    int *counts = calloc((size_t)n, sizeof(int));
    if (!counts) return 3;

    int v, total = 0;
    while (scanf("%d", &v) == 1) {
        if (v < 0 || v >= n) {
            fprintf(stderr, "value out of range: %d\n", v);
            continue;
        }
        counts[v]++;
        total++;
    }
    for (int i = 0; i < n; i++) {
        printf("%d: %d\n", i, counts[i]);
    }
    printf("total=%d\n", total);
    free(counts);
    return 0;
}
