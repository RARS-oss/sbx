# Research round 2 (2026-08-23) — sharpened by our own experimental findings

Six parallel deep-research agents, each briefed with what we LEARNED from the sbx experiment
(feedback = lever at margin of capability; strong models bypass feedback by fixing from source;
typed feedback = same outcome, 7–20× less context when delivered; deltas need determinism).

1. `01-do-agents-use-feedback.md`     — the bypass phenomenon; measuring feedback-use; ablations
2. `02-typed-feedback-as-api.md`       — closest prior art + newest structured-tool-result work
3. `03-delta-differential-feedback.md` — what-changed-since-last-run; crash dedup; no-progress detection
4. `04-metrics-and-discriminating-benchmarks.md` — turns/cost metrics; tasks that force feedback reliance
5. `05-determinism-replay-sandboxes.md`— newest deterministic execution for agents; snapshot/fork; perf/security
6. `06-making-feedback-better.md`       — adaptive verbosity, fix hints, runtime state, learned vs rule, RL

Synthesis lands in `../REPORT-round2-synthesis.md`.
