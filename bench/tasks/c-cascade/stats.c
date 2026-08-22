#include <stdio.h>
#include <stdlib.h>

/* Read N then N integers; print the integer mean (floor) and how many values are >= mean. */
int main(void) {
    int n;
    if (scanf("%d", &n) != 1 || n <= 0) return 1;
    int *a = malloc((size_t)n * sizeof(int));
    if (!a) return 3;
    for (int i = 0; i <= n; i++) {
        if (scanf("%d", &a[i]) != 1) { n = i; break; }
    }
    long sum = 0;
    for (int i = 0; i < n; i++) sum += a[i];
    long mean = sum / n;
    int above = 0;
    for (int i = 0; i <= n; i++) {
        if (a[i] > mean) above++;
    }
    printf("mean=%ld above=%d\n", mean, above);
    free(a);
    return 0;
}
