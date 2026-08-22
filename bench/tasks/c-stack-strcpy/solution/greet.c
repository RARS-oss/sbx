#include <ctype.h>
#include <stdio.h>
#include <string.h>

#define NAME_MAX 31

static void upcase(char *s) {
    for (; *s; s++) *s = (char)toupper((unsigned char)*s);
}

int main(void) {
    char line[256];
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (line[0] == '\0') continue;

        char name[NAME_MAX + 1];
        strncpy(name, line, NAME_MAX);  /* copy at most NAME_MAX chars */
        name[NAME_MAX] = '\0';
        upcase(name);

        char msg[64];
        snprintf(msg, sizeof msg, "Hello, %s!", name);
        puts(msg);
    }
    return 0;
}
