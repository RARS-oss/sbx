
## ollama:qwen2.5-coder:3b  (n=48 episodes, 12 tasks)

| condition | n | success | 95% CI | turns (mean/median) | runs | nudges | infra err | in_tok | out_tok | cost $ | shown/raw | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| raw | 12 | 0/12 (0%) | 0%–24% | 9.9/11 | 4.1 | 1.4 | 0 | 40,756 | 1,445 | 0.0000 | 1.01 | 435 |
| structured | 12 | 2/12 (17%) | 5%–45% | 9.3/8 | 3.7 | 1.4 | 0 | 19,351 | 2,410 | 0.0000 | 0.94 | 306 |
| structured_delta | 12 | 3/12 (25%) | 9%–53% | 9.4/8 | 3.8 | 1.5 | 0 | 17,485 | 1,734 | 0.0000 | 1.27 | 290 |
| truncate10k | 12 | 1/12 (8%) | 1%–35% | 9.6/11 | 4.0 | 1.2 | 0 | 32,928 | 1,427 | 0.0000 | 0.96 | 367 |

Turns-to-solve on successful episodes (mean / median / n):
- raw: — (no successes)
- structured: 8.0 / 8 / 2
- structured_delta: 8.7 / 8 / 3
- truncate10k: 8.0 / 8 / 1

Success by task × condition:

| task | raw | structured | structured_delta | truncate10k |
|---|---|---|---|---|
| c-compile-error | 0/1 | 1/1 (t=8) | 1/1 (t=8) | 0/1 |
| c-double-free | 0/1 | 0/1 | 1/1 (t=10) | 0/1 |
| c-heap-overflow | 0/1 | 0/1 | 0/1 | 0/1 |
| c-null-deref | 0/1 | 0/1 | 0/1 | 0/1 |
| c-signed-overflow | 0/1 | 1/1 (t=8) | 1/1 (t=8) | 1/1 (t=8) |
| c-stack-strcpy | 0/1 | 0/1 | 0/1 | 0/1 |
| c-use-after-free | 0/1 | 0/1 | 0/1 | 0/1 |
| cpp-vector-oob | 0/1 | 0/1 | 0/1 | 0/1 |
| py-cli-args | 0/1 | 0/1 | 0/1 | 0/1 |
| py-unittest-crash | 0/1 | 0/1 | 0/1 | 0/1 |
| py-unittest-logic | 0/1 | 0/1 | 0/1 | 0/1 |
| rust-index-panic | 0/1 | 0/1 | 0/1 | 0/1 |

Outcome bookkeeping:
- raw: done called 2/12; protected-file violations 0; ended without done and failed 10
- structured: done called 3/12; protected-file violations 0; ended without done and failed 9
- structured_delta: done called 3/12; protected-file violations 0; ended without done and failed 9
- truncate10k: done called 3/12; protected-file violations 0; ended without done and failed 9
