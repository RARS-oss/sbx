
## ollama:qwen2.5-coder:7b  (n=44 episodes, 11 tasks)

| condition | n | success | 95% CI | turns (mean/median) | runs | nudges | infra err | in_tok | out_tok | cost $ | shown/raw | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| raw | 11 | 2/11 (18%) | 5%–48% | 7.6/8 | 2.7 | 1.9 | 0 | 25,563 | 1,655 | 0.0000 | 1.01 | 528 |
| structured | 11 | 2/11 (18%) | 5%–48% | 9.4/8 | 3.5 | 1.8 | 0 | 21,621 | 2,459 | 0.0000 | 0.41 | 719 |
| structured_delta | 11 | 1/11 (9%) | 2%–38% | 8.7/9 | 3.0 | 1.9 | 1 | 18,966 | 2,399 | 0.0000 | 0.41 | 839 |
| truncate10k | 11 | 2/11 (18%) | 5%–48% | 7.5/8 | 2.8 | 1.7 | 0 | 19,495 | 2,127 | 0.0000 | 1.01 | 639 |

Turns-to-solve on successful episodes (mean / median / n):
- raw: 8.0 / 8 / 2
- structured: 7.5 / 8 / 2
- structured_delta: 7.0 / 7 / 1
- truncate10k: 8.0 / 8 / 2

Success by task × condition:

| task | raw | structured | structured_delta | truncate10k |
|---|---|---|---|---|
| c-compile-error | 1/1 (t=7) | 1/1 (t=7) | 1/1 (t=7) | 1/1 (t=7) |
| c-double-free | 0/1 | 0/1 | 0/1 | 0/1 |
| c-heap-overflow | 0/1 | 0/1 | 0/1 | 0/1 |
| c-null-deref | 1/1 (t=9) | 1/1 (t=8) | 0/1 | 1/1 (t=9) |
| c-signed-overflow | 0/1 | 0/1 | 0/1 | 0/1 |
| c-stack-strcpy | 0/1 | 0/1 | 0/1 | 0/1 |
| c-use-after-free | 0/1 | 0/1 | 0/1 | 0/1 |
| cpp-vector-oob | 0/1 | 0/1 | 0/1 | 0/1 |
| py-cli-args | 0/1 | 0/1 | 0/1 | 0/1 |
| py-unittest-crash | 0/1 | 0/1 | 0/1 | 0/1 |
| py-unittest-logic | 0/1 | 0/1 | 0/1 | 0/1 |

Outcome bookkeeping:
- raw: done called 2/11; protected-file violations 0; ended without done and failed 9
- structured: done called 2/11; protected-file violations 0; ended without done and failed 9
- structured_delta: done called 1/11; protected-file violations 0; ended without done and failed 10
- truncate10k: done called 3/11; protected-file violations 0; ended without done and failed 8
