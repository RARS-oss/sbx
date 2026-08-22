# H3 micro-experiment: run-to-run stability of failing output (2026-08-22, WSL2 6.6, K = 10)

Command: `bash bench/scripts/determinism.sh 10`. Each task's buggy version is run 10 times inside
sbx under three profiles; we count distinct values over the 10 runs of (a) the raw stdout+stderr
bytes (sha256), (b) the crash identity used by the Delta (kind + first user frame file:line),
(c) the rendered Verdict JSON (wall_ms removed).

| task | profile | distinct raw outputs | distinct crash identities | distinct verdict texts | wall ms (median) |
|---|---|---|---|---|---|
| c-use-after-free | hermetic | 1 | 1 | 1 | 298 |
| c-use-after-free | ASLR on | 10 | 1 | 10 | 288 |
| c-use-after-free | ASLR on + inherited env | 10 | 1 | 10 | 306 |
| c-heap-overflow | hermetic | 1 | 1 | 1 | 166 |
| c-heap-overflow | ASLR on | 10 | 1 | 10 | 178 |
| c-heap-overflow | ASLR on + inherited env | 10 | 1 | 10 | 197 |
| c-stack-strcpy | hermetic | 1 | 1 | 1 | 300 |
| c-stack-strcpy | ASLR on | 10 | 1 | 10 | 298 |
| c-stack-strcpy | ASLR on + inherited env | 10 | 1 | 10 | 319 |
| c-double-free | hermetic | 1 | 1 | 1 | 218 |
| c-double-free | ASLR on | 10 | 1 | 10 | 209 |
| c-double-free | ASLR on + inherited env | 10 | 1 | 10 | 238 |

Reading.
- Under the hermetic profile the failing output is **byte-identical across all 10 runs on all four
  tasks** (40/40), and so is the verdict. Under ASLR every run differs (sanitizer addresses), so a
  byte-level or text-level "what changed since last run" is impossible: a naive diff would report
  100 % change on an unchanged program.
- Crash *identity* (kind + first user frame ± 3 lines) is stable under ASLR **after** we normalised
  hex addresses out of the UBSan kind string. Before that fix, `c-heap-overflow` showed 10 distinct
  identities under ASLR because UBSan's "load of address 0x… with insufficient space" carried the
  address into the kind — the delta would have reported "crash moved" on every re-run. Two lessons
  the paper states: identity must be address-free by construction, *and* the executor should pin
  ASLR so that everything downstream of identity (messages, shadow dumps, addresses an agent might
  grep) is stable too.
- Inherited environment adds nothing observable here (the tasks do not read env), but it costs ~5–10 %
  wall (larger environment, locale lookups); the fixed profile is also the faster one.
- Wall-clock itself is not deterministic (±10 %); it is excluded from verdict identity.
