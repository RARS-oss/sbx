# Round2-04 — Metrics (turns/cost not tokens) + tasks that discriminate feedback quality (2026-08-23)

Anchored to fetched primary sources. IDs ≥2511 post-date cutoff. Discarded synthetic leaderboard
pages (fictional model names) surfaced by the index.

## (A) The right metric set — token count is the WRONG unit
- **PointFive** (2,908 coding sessions): RTK-ML cut 38.4% tokens but RAISED billed cost 6.8%; cost
  dominated by framework overhead (~75%: system prompts/tool defs resent every turn) + reasoning
  (~19%), only ~6% (3.3% practical) reachable by compression → "even perfect compression tops out
  ~5%." Measure **cost per completed task from the bill, not tokens removed.**
- **HAL** (2510.11977): 21,730 rollouts × 9 models × 9 benchmarks, ~$40k; accuracy gains NOT
  accompanied by token reductions; higher reasoning effort REDUCED accuracy in majority of runs.
Report first-class: (1) **turns/iterations-to-fix** (most gains in first few iterations — Is Three the
Magic Number 2607.05197; How Many Tries 2604.10508); (2) **billed cache-aware cost** (Cost-of-Pass
2504.13359; SWE-Effi 2509.09853; token-inflation 2608.13571 workflow cost >2× single-call);
(3) **tokens-by-type** (cache-read ~10× cheaper, dominates); (4) **wall-clock**; (5) **reliability**.
What reduces ITERATIONS: richer content (typed errors, deltas, fault location, admissible next-states)
+ pre-run localization; NOT compression (backfires via re-reads).

## (B) Benchmarks that discriminate feedback quality on STRONG models
Criterion: strong model can't one-shot from source → must run/read/iterate.
| # | Benchmark | Why feedback load-bearing | Ceiling | Effort |
|---|---|---|---|---|
| 1 | **AutoPatchBench** (Meta) | 136 ARVO C/C++ fuzz memory bugs; correctness = PoC no longer crashes → must execute | low | Medium (Docker/PurpleLlama) |
| 2 | **SEC-bench** | real vuln PoC-reproduction+patch; runtime mandatory | **PoC 18% / patch 34%** best — huge headroom | Medium (~$0.87/instance) |
| 3 | **ARVO** | 5,000+ reproducible OSS-Fuzz vulns; oracle=sanitizer | dataset | Med-high |
| 4 | Kernel crash repair | crash artifact only, no NL report → must iterate | very low | High |
| 5 | **Multi-SWE-bench** C/C++/Rust | compiled → build/type/test feedback load-bearing | low | Low-med |
| 6 | SWE-bench Pro | 1,865 long-horizon, 41 repos, multi-file | far below Verified | Low (contamination caveat) |
| 7 | Terminal-Bench 2.0 / LH-Terminal-Bench | long-horizon CLI, dense-reward progress | <65% | Low-med |
Cites: AutoPatchBench (engineering.fb.com Apr 2025); SEC-bench 2506.11791 (18%/34%); ARVO 2408.02153;
Live-kBench 2602.02690 (fresh syzkaller crashes, anti-contamination); kAgent 2504.20412; Multi-SWE-bench
2504.02605; Terminal-Bench 2.0 2601.11868; LH-TB 2607.08964.
**Contamination caveat:** ~28.5% SWE-bench Verified sample has tests weak enough to pass an incorrect
patch, Pass@1 +14pp on "hackable" tasks (2606.16062); ~60% of unsolved Verified flawed tests (2608.09802).
Prefer FRESH/decontaminated (Live-kBench, ARVO N-days) where oracle is a crash not a shipped unit test.

## (C) Experimental designs that isolate feedback value
Core move: counterfactual on feedback FORM (hold task/model/seed/budget, vary only feedback).
- **VeriHarness** (2607.14167) — code-controlled loop, raw diagnostics vs {location, observed value,
  admissible alternatives}, 50 paired games, 4-call cap: 14/50→36/50, 8/50→29/50. **Most gain from
  admissible alternatives; prose ≈ JSON.** Directly informs our raw-vs-typed+delta: isolate the
  delta/next-state CONTENT, not serialization.
- **Type-error ablation** (2606.01522) — strip error detail through a hierarchy; type signal helps
  more than test-suite failure alone.
- **Progressive source masking** (AutoExperiment 2506.19724) — interpolate reproduction↔replication by
  masking graduated code → knob to STARVE the agent of source, force reliance on run output.
- Run-before-edit/execution-guided (kAgent, DebugHarness). Oracle vs realistic (RubricRefine 2605.09730:
  real exec feedback only 0.65→0.75, many silent contract violations). Counterfactual attribution
  (CausalFlow 2605.25338). Separate submit from resolve ("Confident and Wrong" 2603.25764: GPT-5 submits
  100% resolves 44%).
- **Feedback-as-localizer** (multi-file): agent must locate before it can read. FlexFL 2411.10714; T2L
  2510.02389; SBFL+reflexion 2409.13642; hierarchical runtime pruning 2605.13491. Big-context
  degradation (Context-Rot 2605.23170) makes selective reading necessary → localizing typed+delta cuts
  turns/tokens-to-correct-file.

## (D) Statistical-rigor checklist
1. Single-run numbers are noise: On Randomness (2602.07150) 60k trajectories, pass@1 swings 2.2–6.0pp,
   SD>1.5pp even at T=0 → +2–3pp can be noise.
2. Power-analyze seed count (How Many Random Seeds 1806.08295).
3. **Paired design**: same task+seed for raw vs typed → paired BCa bootstrap (2511.19794), variance
   reduction when outcomes positively correlated.
4. Report **reliability not just mean**: pass^k (τ-bench 2406.12045); pass@k with n=independent rollouts
   not test count; consistency collapses 60%(1-run)→25%(8-run) (2511.14136).
5. Effect sizes + CIs; separate submit vs resolve; pre-register expected turn/cost delta.

## (E) Six recommendations for our next experiment (to show a TURN/COST effect on a frontier model)
1. **Switch to source-insufficient tasks** — AutoPatchBench/ARVO memory-safety or multi-file repo bugs
   with frontier ceiling <~50%; oracle = runtime crash/sanitizer/test not shippable unit test.
2. **Information-hiding to force reliance** — run-before-edit + progressive source masking; cap readable
   context in large repos so selective reading is forced.
3. **VeriHarness-style counterfactual rig** — fix task/model/seed/cap, vary only feedback: raw vs
   typed+delta; then ABLATE typed fields (type / delta / location / admissible next-state) — added
   INFORMATION drives gain, not JSON-vs-prose.
4. **Turns + billed cost primary** — turns-to-first-pass, turns-to-final-resolve, cache-aware
   $/resolved-task decomposed by token type, wall-clock. Raw token count secondary. State up front:
   typed+delta lowers turns/cost even if it adds per-turn tokens.
5. **Power + pair** — ≥10–20 seeds (SD>1.5pp), paired bootstrap on shared seeds, pass^k + CIs, submit vs
   resolve separated. No single-run deltas.
6. **Localization sub-metric** — turns/tokens-to-correct-file + FL accuracy on multi-file bugs as an
   INTERMEDIATE signal; typed+delta compresses search before first edit (where turn/cost win concentrates).
**Expected:** on source-insufficient iteration-heavy tasks, typed+delta cuts turns-to-resolve and
$/resolved with gains where raw signals are ambiguous (memory-safety, silent contract violations) —
mirroring VeriHarness (14/50→36/50). Keep easy single-file tasks or full source → expect a null.
