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
        strcpy(name, line);            /* copy the name */
        upcase(name);

        char msg[64];
        strcpy(msg, "Hello, ");
        strcat(msg, name);
        strcat(msg, "!");
        puts(msg);
    }
    return 0;
}
