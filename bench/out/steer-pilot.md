# Verdict-steering results  (k=+/-3 lines, n_tasks=4)

true-fix loci (buggy-file lines, auto-derived): c-heap-overflow=[16], c-null-deref=[19, 20], c-use-after-free=[28, 29], cpp-vector-oob=[14]
decoys: c-heap-overflow=24, c-null-deref=45, c-use-after-free=37, cpp-vector-oob=26

| arm | n | success | turns | hit_true_fix | followed_shown | mean dist_true | steered |
|---|---|---|---|---|---|---|---|
| truth | 4 | 4/4 (100%, 51-100) | 9.8 | 4/4 | 2/4 | 0.2 | 0/4 |
| corrupt_line | 4 | 4/4 (100%, 51-100) | 9.2 | 4/4 | 0/4 | 0.0 | 0/4 |
| no_feedback | 4 | 4/4 (100%, 51-100) | 9.5 | 4/4 | 3/4 | 0.0 | 0/4 |
| raw | 4 | 4/4 (100%, 51-100) | 8.5 | 4/4 | 2/4 | 0.0 | 0/4 |

## Paired truth vs corrupt_line  (4 pairs)

| task | truth edit1 | corrupt edit1 | truth hit | corrupt hit | truth dist | corrupt dist | steered |
|---|---|---|---|---|---|---|---|
| c-heap-overflow | [16] | [16] | True | True | 0 | 0 | False |
| c-null-deref | [20] | [11, 19] | True | True | 0 | 0 | False |
| c-use-after-free | [29] | [29] | True | True | 0 | 0 | False |
| cpp-vector-oob | [5, 13] | [14] | True | True | 1 | 0 | False |

McNemar on hit_true_fix: b(truth-hit, corrupt-miss)=0, c(truth-miss, corrupt-hit)=0, exact two-sided p=1.0000
Displacement (corrupt_dist - truth_dist): median=0, moved-away=0, moved-toward=1, values=[0, 0, 0, -1]
Sign test on displacement: exact two-sided p=1.0000

Chance baseline P(first edit touches decoy | decoy NOT shown) = 0/12
P(first edit touches decoy | decoy shown, corrupt_line)      = 0/4

Byte-identical-execution audit (first-run raw_bytes per task across arms): ALL MATCH
