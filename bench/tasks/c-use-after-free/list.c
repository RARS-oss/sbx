#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct node {
    int value;
    struct node *next;
};

static struct node *push_front(struct node *head, int value) {
    struct node *n = malloc(sizeof *n);
    if (!n) exit(3);
    n->value = value;
    n->next = head;
    return n;
}

/* Remove the first node whose value == value. Returns the (possibly new) head. */
static struct node *remove_value(struct node *head, int value) {
    struct node *prev = NULL;
    for (struct node *cur = head; cur; cur = cur->next) {
        if (cur->value == value) {
            if (prev) {
                prev->next = cur->next;
            } else {
                head = cur->next;
            }
            free(cur);
        }
        prev = cur;
    }
    return head;
}

static long sum(const struct node *head) {
    long s = 0;
    for (const struct node *n = head; n; n = n->next) s += n->value;
    return s;
}

static void print_list(const struct node *head) {
    printf("[");
    for (const struct node *n = head; n; n = n->next) {
        printf("%d%s", n->value, n->next ? " " : "");
    }
    printf("]\n");
}

static void free_list(struct node *head) {
    while (head) {
        struct node *next = head->next;
        free(head);
        head = next;
    }
}

int main(void) {
    struct node *head = NULL;
    char cmd[16];
    int v;
    while (scanf("%15s", cmd) == 1) {
        if (strcmp(cmd, "push") == 0 && scanf("%d", &v) == 1) {
            head = push_front(head, v);
        } else if (strcmp(cmd, "remove") == 0 && scanf("%d", &v) == 1) {
            head = remove_value(head, v);
        } else if (strcmp(cmd, "sum") == 0) {
            printf("sum=%ld\n", sum(head));
        } else if (strcmp(cmd, "print") == 0) {
            print_list(head);
        } else {
            fprintf(stderr, "unknown command: %s\n", cmd);
            free_list(head);
            return 2;
        }
    }
    free_list(head);
    return 0;
}
