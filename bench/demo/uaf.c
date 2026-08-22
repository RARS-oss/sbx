#include <stdio.h>
#include <stdlib.h>

/* Heap use-after-free: the interesting case for delta feedback — a naive
 * "fix" of overflow.c often produces a *different* crash kind at a
 * *different* frame; the delta line should say "crash: moved ... -> ...". */
struct node {
    int value;
    struct node *next;
};

static int sum(struct node *head) {
    int s = 0;
    for (struct node *n = head; n; n = n->next) {
        s += n->value;
    }
    return s;
}

int main(void) {
    struct node *a = malloc(sizeof *a);
    struct node *b = malloc(sizeof *b);
    if (!a || !b) return 1;
    a->value = 1; a->next = b;
    b->value = 2; b->next = NULL;
    free(b);
    printf("%d\n", sum(a));
    free(a);
    return 0;
}
