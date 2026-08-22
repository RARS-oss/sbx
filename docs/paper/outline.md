# Paper outline — "Facts, not bytes: typed, delta-aware execution feedback for coding agents under a hermetic executor"

Working title alternatives: *"Deltas need determinism"*; *"Token reduction is not turn reduction"*.
Target: 8–10 pages, workshop (DL4Code @ ICML; ICLR/NeurIPS agents workshops; EuroSys/SOSP
workshop for the systems framing) + arXiv + open-source artifact (this repo).

## Abstract (draft)

Tool output dominates the token budget of LLM coding agents (45–84 % of input tokens across
SWE-agent, Terminal-Bench and Claude Code traces), yet every deployed harness shapes it the
same way — byte/line truncation — and byte-level compressors have been independently shown
not to reduce billed cost. We argue the executor, not a post-hoc filter, should own the
feedback: it knows the exit status, the signal, the sanitizer report and the test runner's
summary. We present **sbx**, a 4 ms unprivileged hermetic sandbox (user/pid/mount/net/uts/ipc
namespaces, `pivot_root`, fixed environment, no ASLR) whose result is a typed **Verdict**
(diagnostics, crash object with first user frame and alloc/free sites, test failures by root
cause) and a **Delta** against the previous run ("2 fixed, 1 new; crash moved a.c:9 → b.c:15").
We show that (i) deltas are only sound under the hermetic profile, (ii) across N C/C++/Rust/
Python repair tasks, typed+delta feedback reduces turns-to-fix by X % and billed cost by Y %
relative to raw output and to masking/compression baselines at equal or better success, and
(iii) the effect concentrates in sanitizer-heavy tasks where raw output is largest.

## 1. Introduction
- Problem: observation tokens share (cite Complexity Trap 84 %/turn; CoACT 45.7 %/67.8 %; SWE-Pruner Pro >70 %; Claude Code 31 % of a live context).
- Everyone truncates by bytes (table of harness rules: Claude Code 30k, Codex 10 KiB, Gemini 40k, OpenHands 30k, Terminus 10 KB, mini-SWE-agent 10k).
- The commoditised fix and its negative result (RTK 77k★; JetBrains +7.6 % cost; arXiv 2607.12161 r = 0.15).
- Thesis: feedback is an API, not a byte stream; determinism is what makes diffs of feedback meaningful.
- Contributions: sbx (system), Verdict/Delta contract (interface), evaluation (turns/cost/success across feedback forms), negative/failure-case analysis.

## 2. Background and related work
- Execution feedback for repair: Self-Debugging, Reflexion, LDB, SWE-agent ACI ablations, RustAssistant format ablation, VeriHarness, PGS, FeedbackEval, Fact Selection, Type-Error Ablation, Generative Compilation, "Is Three the Magic Number".
- Observation compression: Complexity Trap (masking), AgentDiet, ACON, SWE-Pruner(/Pro), CoACT, TACO, Squeez, Less Context Better Agents.
- Sanitizer/crash repair: WilliamT, CodeRover-S, DebugHarness, AutoPatchBench, SEC-bench, ChatDBG, TLR.
- Sandboxes and determinism: E2B/Modal/Daytona/Docker Sandboxes, Anthropic srt, Codex sandbox, Sandlock, hakoniwa/nono, Hermit, Antithesis, DeltaBox/Crab snapshots, Bazel/Nix sandboxes, Anthropic infra-noise, Terminal-Bench 2.1 repairs, "Grounded Scaling", COBALT.
- Position sbx in the novelty matrix (research report §4).

## 3. System: sbx
- 3.1 hermit-core: namespaces, pivot_root, ro binds with lock-flag preservation, /dev,/proc,/sys, rlimits, cgroup best-effort, hermetic env, no-ASLR; `Applied` provenance per run; startup latency table (4.15 ms median vs Docker/gVisor/Firecracker published numbers).
- 3.2 feedback: Verdict schema; parsers (ASan/UBSan/LSan/TSan, gcc/clang, rustc, pytest, cargo test, ctest/gtest, Python tracebacks, signals); grouping/normalisation; tail policy; rendering.
- 3.3 Delta: line-shift-tolerant diagnostic identity; crash identity; tests by name; why ASLR/locale/clock must be fixed (examples of deltas corrupted without the profile).
- 3.4 Integration: CLI, Claude Code PostToolUse/PreToolUse hooks, mini-SWE-agent adapter, Harbor backend.

## 4. Experimental design
- Hypotheses H1 (form), H2 (deltas), H3 (determinism) — see research report §7.
- Conditions: (A) raw, (B) head/tail truncation (30k / 10 KiB), (C) RTK-style regex compression, (D) observation masking M=10, (E) structured, (F) structured+delta, (G) structured+delta without hermetic profile.
- Tasks: SEC-bench/ARVO subset (ASan), ComBench (compile errors), CRUST-Bench (rustc loops), Terminal-Bench 2.1 `polyglot-*`, Multi-SWE-bench C/C++/Rust mini, plus 30–50 in-house memory-bug tasks; ~150–250 tasks, pilot 60.
- Models: Claude Opus 5 / Sonnet 5 (API) and open-weight Qwen2.5-Coder 3B/7B (local, Ollama, zero cost, reproducible; also the sensitivity arm — weak models cannot "reason around" a truncated report, so the feedback-form effect should be largest there). Harnesses: our instrumented agent (bench/agent), Claude Code via hook, mini-SWE-agent.
- Metrics: success (pass@1, N≥5 runs, CI), turns-to-solve, billed cost (cache-aware), tokens by type, cache-hit, wall-clock, timeout/step-limit rate, run-to-run variance; by bug class (spatial vs temporal).
- Baseline fidelity: reproduce Complexity-Trap masking numbers on a shared subset before adding our arms.

## 5. Results (to fill)
- Main table: condition × {success, turns, cost, tokens}; per-benchmark breakdown.
- Dose–response: feedback length vs turns (structured variants with k frames / k diagnostics).
- Delta ablation: F vs E; G vs F (determinism off) — expected: deltas degrade without profile.
- Variance: H3 — run-to-run SD with/without profile; infra-error rate.
- Cost decomposition: cache reads vs uncached input vs output; why fewer bytes ≠ fewer dollars; where turns saved.
- Failure cases: deltas hiding information; parser misses; tasks where raw beat structured.

## 6. Discussion
- "Token reduction ≠ cost reduction" reconciled: turn reduction is the lever.
- When structured feedback hurts (temporal memory bugs needing dynamic state — DebugHarness finding; model dependence).
- Generality: the contract vs. the parsers; what other executors (E2B, Harbor) would need to adopt it.
- Threats to validity: cache economics, model dependence, Python bias, plausibility vs correctness, parser coverage.

## 7. Conclusion / artifact
- Open-source sbx + verdict schema + hooks + benchmark runner; reproducibility package (specs, seeds, Applied records).

## Appendix
- Verdict/Delta schema; hermetic profile table; parser fixtures; full per-task tables; prompts.
