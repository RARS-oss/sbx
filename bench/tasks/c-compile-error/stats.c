#include <stdio.h>
#include <stdlib.h>

/* Running statistics over a stream of integers. */
struct stats {
    long count;
    long min;
    long max;
    double sum;
};

static void stats_init(struct stats *s) {
    s->count = 0;
    s->min = 0;
    s->max = 0;
    s->sum = 0.0;
}

static void stats_add(struct stats *s, long v) {
    if (s->count == 0 || v < s->min) s->min = v;
    if (s->count == 0 || v > s->max) s->max = v;
    s->sum += v;
    s->count++;
}

static double stats_mean(const struct stats *s) {
    if (s->count == 0) return 0.0;
    return s->sum / s->count;
}

static char *format_result(const struct stats *s) {
    static char buf[128];
    snprintf(buf, sizeof buf, "min=%ld max=%ld mean=%.2f", s->min, s->max, stats_mean(s));
    return buf;
}

int main(void) {
    struct stats st;
    stats_init(&st);
    long v;
    int unused_counter = 0;
    while (scanf("%ld", &v) == 1) {
        stats_add(&st, v);
    }
    if (st.count == 0) {
        puts("no data");
        return 0;
    }
    int result = format_result(&st);
    puts(resutl);
    return 0;
}
