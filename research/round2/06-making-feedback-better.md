# Round2-06 — Making execution feedback more effective for LLM repair (2026-08-23)

29 primary sources fetched. Tags: [PR] peer-reviewed, [pre] preprint.

## (A) Techniques ranked by evidence + number + trade-off
1. **"Location + observed value + admissible alternative" typed feedback (STRONGEST direct evidence)** —
   VeriHarness (2607.14167, paired+ablated, N=50): 14/50→36/50 (Qwen2.5-Coder-14B), 8/50→29/50
   (Llama-3.1-8B). **Admissible-alternative field is THE driver**; without it ≈ raw baseline. **JSON
   structuring added NOTHING** (prose = keyed JSON). Trade-off: must COMPUTE the alternative (needs
   domain knowledge — which a typed executor verdict HAS); format is free.
2. **Combined/multi-source > any single; generic advice worst** — FeedbackEval (2504.06939): Mixed
   63.6 > LLM-Expert 62.9 > Test 57.9 > Minimal 53.1 > Compiler 49.2 > LLM-Skilled(generic) 48.8;
   plateaus after 2–3 rounds.
3. **Runtime-state feedback (variable values at fault), not just crash line** — LDB per-block values
   +9.8% (2402.16906, ACL'24); NExT trace training +26.1% MBPP/+14.3% HumanEval (2404.14662, ICML'24);
   DebugRepair instrumented states +51.3% over vanilla, 5 LLMs (2604.19305); InspectCoder agent drives
   debugger +5.10–60.37%, 1.67–2.24× fewer attempts (2510.18327); ChatDBG (2403.16354, FSE'25).
   Trade-off: instrumentation/re-exec; "print the offending value" (LDB after-block) = most gain at ~0 cost.
4. **Delta-debugged minimal failing input** — ReduceFix: LLM writes a reducer, shrinks input 89.1%,
   Pass@10 +53.8% vs raw / +17.6% vs omitting (2507.15251). Win only when inputs large.
5. **Learned next-action-preserving compression (full-log path)** — CoACT Next-Action-Preservation:
   33% fewer tokens at SWE-bench-V parity (2607.02911); SWE-Pruner 0.6B skimmer 23–54% cut, up to
   14.84× single-turn, IMPROVES success, beats PPL-based LongLLMLingua ("breaks syntax") (2601.16746);
   SWE-Pruner Pro from hidden states (2607.18213). Trade-off: adds a model call, LOSES determinism.
6. **Agent-controlled granularity / progressive disclosure** — "buys context not intelligence":
   redundant when strong agent self-navigates, DECISIVE once corpus too large to read; **one routing
   level is enough — a second deeper level never helps, sometimes breaks** (2607.17598, 3 harnesses).
   Model-controlled compaction (SelfCompact 2606.23525; CAT 2512.22087; Focus 2601.07190) > fixed-interval truncation.
7. **Structured/programmatic tool channel (branch on the verdict object)** — CodeAct code-as-action
   +20% over JSON/text (2402.01030, ICML'24); "Bitter Lesson of Tool Calling" PTC ≥ JSON in 11/14
   models (+10.6% best), **holds under context-rot where JSON degrades**, advantage SCALES with
   capability (2608.06370). Trade-off: helps STRONG models most; weak models mis-script — keep text fallback.
8. **RL "feedback-following"** — RLEF SOTA CodeContests, order-of-magnitude fewer samples (2410.02089);
   multi-turn SWE-RL Qwen2.5-72B 11%→39% (2508.03501); MURPHY feedback-aware GRPO +6% pass@1
   (2511.07833); TaPR per-turn test-pass-ratio dense reward (2608.00494). Needs training, not an
   executor change — but tells you WHICH feedback shape to emit.
9. **Fix-suggestion / counterexample framing** — RustAssistant ~74% real Rust compile errors as diffs
   (2308.05177, ICSE'24); PGS counterexample-on-first-violation → 7× fewer candidates (2605.16142).
   Trade-off: CHECKABLE counterexample helps; SPECULATIVE suggested patch risks over-anchoring.
10. **Physical/structured domain verdict (robotics-transferable)** — Eureka reward reflection (textual
    summary of reward-component stats per checkpoint) beats human on 83% of 29 tasks (2310.12931,
    ICLR'24); RoboFAC failure taxonomy (2505.12224); AHA (2410.00371); PhysReflect-VLA (2606.27146).
    Same recipe as a typed crash verdict: classify failure kind, name violated constraint, report
    offending magnitude. Schema transfers, parser doesn't.

## (B) What combines well with a DETERMINISTIC executor-side verdict
Our deterministic parser is an ASSET: content (location/value/admissible alternative) matters, format
(JSON vs prose) does not. Best combos: typed verdict → admissible-alternatives field; deterministic
value capture ("print offending value", first-frame locals, no LLM); deterministic compression default
+ learned skimmer only on the "full log on request" path; progressive disclosure over the verdict
object (one level) + programmatic/queryable verdict; delta-min input (executor has the failing input);
RL feedback-following consumes typed deltas as dense rewards (executor unchanged).

## (C) Risks
- **Over-anchoring (biggest, best-documented)** — showing a small model its failed attempt → reproduce
  near-identical 33–68% (vs 2–14% blind); blind resampling BEAT execution feedback below 7B at 2.5–5.5×
  fewer tokens (2607.26117, placebo/preregistered). Prefer CHECKABLE counterexamples over PRESCRIBED
  edits; consider feedback WITHOUT re-showing failed code to weak models.
- Self-repair gains evaporate under cost/sample budget (Olausson 2306.09896) — measure at equal budget.
- Lossy compression hurts (LongLLMLingua breaks syntax; only next-action-preserving is safe) — keep raw log retrievable.
- Model-dependence: progressive disclosure redundant for strong agents; PTC/code-as-action favors capable;
  debugger control assumes planning. Weak want terse/prescriptive; strong want queryable. **Adapt verbosity to tier.**
- Feedback-optimization degeneration: optimizing "execution passes" drifts from the goal (2608.05917).

## (D) Prioritized roadmap — 8 improvements to sbx feedback
1. **Admissible-alternatives field per verdict** (CHEAP) — glossary implies the fix class; emit 1–3
   concrete legal alternatives ("index in 0..len; here len==0"). LARGEST single lift (VeriHarness driver).
2. **"Print the offending value" — deterministic first-frame locals at fault** (cheap–medium) —
   +10–25% class at ~0 token cost (LDB/NExT/DebugRepair).
3. **Progressive disclosure: terse line default, agent pulls deeper** (medium) — token savings, no
   accuracy loss for strong agents; ONE level only (deeper hurts).
4. **Verdict as structured object the agent can query/branch on** (medium) — grep failing tests / filter
   in code, prose fallback. +10–20% capable models, robust under context-rot (CodeAct, Bitter-Lesson PTC).
5. **Delta-min the failing input before prompt** (medium) — deterministic reducer on large check inputs;
   +50%-class Pass@k when inputs large (ReduceFix); skip when small.
6. **Learned next-action-preserving skimmer on the "full log on request" path only** (hard) — default
   stays deterministic parser; skimmer compresses raw log when pulled; 23–54% cut at parity (CoACT/SWE-Pruner).
7. **Optional interactive-debug channel for hard logic bugs** (hard) — request breakpoints/state behind
   the hermetic executor; +5–60% complex logic, fewer attempts (InspectCoder/ChatDBG).
8. **Wire typed deltas as dense per-turn rewards for a feedback-following fine-tune** (hard) — run-to-run
   verdict deltas as process reward; order-of-magnitude sample efficiency (RLEF/TaPR/MURPHY/SWE-RL 11→39%).
**Cross-cutting guardrails:** prefer checkable counterexamples over prescribed patches; don't re-show
failed code to weak models (anchoring 2607.26117); adapt verbosity to tier; benchmark repair wins at
equal token/attempt budget (Olausson).
