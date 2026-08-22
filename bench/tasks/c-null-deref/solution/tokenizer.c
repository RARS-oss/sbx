#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct tok {
    char *text;
    struct tok *next;
};

/* Append a token to the end of the list (head may be NULL). Returns the head. */
static struct tok *append(struct tok *head, const char *s, size_t len) {
    struct tok *t = malloc(sizeof *t);
    if (!t) exit(3);
    t->text = malloc(len + 1);
    if (!t->text) exit(3);
    memcpy(t->text, s, len);
    t->text[len] = '\0';
    t->next = NULL;
    if (!head) return t;
    struct tok *cur = head;
    while (cur->next) cur = cur->next;
    cur->next = t;
    return head;
}

static struct tok *tokenize(const char *line) {
    struct tok *head = NULL;
    const char *p = line;
    while (*p) {
        while (*p && isspace((unsigned char)*p)) p++;
        if (!*p) break;
        const char *start = p;
        while (*p && !isspace((unsigned char)*p)) p++;
        head = append(head, start, (size_t)(p - start));
    }
    return head;
}

static void print_and_free(struct tok *head) {
    int n = 0;
    for (struct tok *t = head; t; t = t->next) n++;
    printf("%d:", n);
    int first = 1;
    for (struct tok *t = head; t;) {
        printf("%s%s", first ? " " : "|", t->text);
        first = 0;
        struct tok *next = t->next;
        free(t->text);
        free(t);
        t = next;
    }
    printf("\n");
}

int main(void) {
    char line[1024];
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        print_and_free(tokenize(line));
    }
    return 0;
}
