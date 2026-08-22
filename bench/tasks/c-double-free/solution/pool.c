#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define POOL_MAX 64

struct pool {
    char *items[POOL_MAX];
    int n;
};

static int pool_add(struct pool *p, const char *s) {
    if (p->n >= POOL_MAX) return -1;
    char *copy = malloc(strlen(s) + 1);
    if (!copy) return -1;
    strcpy(copy, s);
    p->items[p->n++] = copy;
    return 0;
}

static int pool_find(const struct pool *p, const char *s) {
    for (int i = 0; i < p->n; i++) {
        if (strcmp(p->items[i], s) == 0) return i;
    }
    return -1;
}

static void pool_free(struct pool *p) {
    for (int i = 0; i < p->n; i++) {
        free(p->items[i]);
        p->items[i] = NULL;
    }
    p->n = 0;
}

/* Reset drops everything and frees the storage. */
static void pool_reset(struct pool *p) {
    pool_free(p);
}

static void pool_dump(const struct pool *p) {
    printf("%d:", p->n);
    for (int i = 0; i < p->n; i++) printf(" %s", p->items[i]);
    printf("\n");
}

int main(void) {
    struct pool p = {{0}, 0};
    char cmd[16], arg[128];
    while (scanf("%15s", cmd) == 1) {
        if (strcmp(cmd, "add") == 0 && scanf("%127s", arg) == 1) {
            if (pool_add(&p, arg) != 0) puts("full");
        } else if (strcmp(cmd, "find") == 0 && scanf("%127s", arg) == 1) {
            printf("%d\n", pool_find(&p, arg));
        } else if (strcmp(cmd, "reset") == 0) {
            pool_reset(&p);
        } else if (strcmp(cmd, "dump") == 0) {
            pool_dump(&p);
        } else {
            fprintf(stderr, "unknown command: %s\n", cmd);
            pool_free(&p);
            return 2;
        }
    }
    pool_free(&p);
    return 0;
}
