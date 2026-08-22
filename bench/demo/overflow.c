#include <stdio.h>
#include <stdlib.h>

/* Off-by-one write: classic heap-buffer-overflow that ASan reports on the
 * first iteration past the end. The agent should see exactly one frame
 * in user code (fill, line 8) plus the allocation site (main, line 13). */
static void fill(int *a, int n) {
    for (int i = 0; i <= n; i++) {
        a[i] = i;
    }
}

int main(void) {
    int *p = malloc(10 * sizeof(int));
    if (!p) return 1;
    fill(p, 10);
    printf("%d\n", p[3]);
    free(p);
    return 0;
}
