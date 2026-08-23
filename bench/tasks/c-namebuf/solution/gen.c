#include <stdlib.h>
#include <stdio.h>
#define CAP 64
#define RECORDS 50
struct rec { char name[CAP]; int len; };
static unsigned long s = 0x1234567UL;
static unsigned rng(void){ s = s*6364136223846793005UL + 1442695040888963407UL; return (unsigned)(s>>33); }
int main(void){
    struct rec recs[RECORDS];
    unsigned long tot = 0;
    for (int r = 0; r < RECORDS; r++){
        int len = 33 + (rng() % 24);
        for (int k = 0; k < len; k++) recs[r].name[k] = 'a' + (rng() % 26);
        recs[r].name[len] = 0;
        recs[r].len = len;
        tot += len;
    }
    printf("records=%d totlen=%lu\n", RECORDS, tot);
    return 0;
}
