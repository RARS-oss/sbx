# Round2-03 — Differential / "what-changed-since-last-run" feedback for LLM repair (2026-08-23)

**BLUF:** No tool/paper computes a semantic, line-shift-tolerant diagnostic delta between consecutive
agent runs and hands it back as NL ("2 fixed, 1 new, 3 unchanged; crash same → your edit didn't
affect it"). Ingredients exist separately; the CONJUNCTION fed to the agent is a genuine white space.
Caveat: WebSearch budget-blocked; rests on arXiv index + direct fetches; most 2025–26 items are
unrefereed preprints — verify IDs before formal citation.

## (A) Closest prior art, ranked
1. **RLCSF — RL from Compiler & Language Server Feedback** (2510.22907, Oct 2025) — CLOSEST. Shaped
   process reward from "deterministic changes in diagnostics"; componentwise-improving transitions
   rewarded = a diagnostic delta between states. GAP: consumed as RL training reward (Lanser-CLI),
   never surfaced to the agent at inference; no crash identity; no "same-as-last-run".
2. **Conversational APR** (2301.13246, 2023) — prompt combines previous patches + validation to
   "avoid previously incorrect patches". GAP: raw-text history accumulation, not a computed semantic
   delta; no fixed/new/unchanged classification.
3. **Warning cascading / warning-evolution tracking** (2305.02515, 2023; 2210.02651; 2103.13548) —
   CLOSEST to sbx's compiler-side delta: match warnings between two versions via program differencing
   (textual/GumTree AST/CFG) → old/new/persistent, surface only new. GAP: for human CI triage, never
   fed to an LLM, not turn-to-turn in a loop. (Infer differential, SonarQube "new code", reviewdog.)
4. **Security-regression-per-iteration in LLM repair** (2608.13404, Aug 2026) — studies "a previously
   passing check that fails after a repair iteration"; cumulative-best metrics are non-decreasing by
   construction so per-iteration trajectory is never examined. EMPIRICAL PROOF that sbx's per-run
   delta (a new error your edit introduced) carries info cumulative feedback hides. GAP: eval finding,
   not fed back.
5. **VeriHarness** (2607.14167) — {location, observed value, admissible alternatives} lifts 14/50→36/50
   vs raw. Validates structured framing. GAP: single-shot, not run-to-run.
6. **DiDPO — Diff-in-Diff Policy Optimization** (2608.07147, Aug 2026) — per-sub-diff credit (+10% Qwen2.5-7B). Delta over code but for RL credit within one action.
7. **Generative Compilation** (2607.13921) — compiler feedback on partial programs mid-decoding; NO run-to-run delta (confirmed). Complementary.
- Also-rans: FLARE (2606.03852), TokenRepair (2511.18001), Process-Supervision line rewards (2410.17621), CoCoGen (2403.16792), Graph2Diff (1911.01205); incremental typing (1808.00225); incremental verification delta (DeltaSpec 2301.12403, Invariant Diffs 1911.07988) — none wire the delta into an LLM loop.

## (B) Crash-identity / dedup to borrow (make crash-delta robust)
sbx uses (kind + first user frame). Fuzzing/triage toolbox:
- **CASR crash accumulation** (2405.18174, 2024) — DIRECT ANALOG: distinguishes new from old across
  runs; stack-trace signature, dist=1−similarity pseudometric, hierarchical clustering + crashline
  refinement (same location); new crashes bucketed duplicate/inner/outer/new WITHOUT re-clustering.
  Borrow crashline to complement first-frame key.
- Signature spectrum: pure stack-hash imprecise (Magma 2009.01120 warns crash-count "inaccurate");
  stronger: fault signatures (FuzzerAid 2209.01244); learned similarity TraceSim (2009.12590), S3M
  (2103.10526), DeepLSH (2310.06703), dedupT (2508.19449), **GPTrace LLM-embedding** (2512.01609,
  Dec 2025, beats hand-crafted on 300k+ inputs).
- **Recommended for sbx:** keep (kind+first user frame) as fast key; add (a) crashline/2nd-frame
  tie-break; (b) identity as DISTANCE-with-threshold not exact (one-frame shift after edit still
  "SAME"); (c) LLM-embedding fallback only when frames ambiguous. NO crash-dedup paper feeds
  "same-vs-new" to an LLM — carrying "crash SAME → your edit did not affect it" into context is novel.

## (C) No-progress / stuck-loop detection — deltas as convergence aid (strong support)
- **The Mirror Loop** (2510.21861, Oct 2025) — self-critique WITHOUT external feedback decays: info
  gain ΔI fell 55% (0.193→0.087) toward "epistemic stasis"; one grounding step rebounds ΔI +28%.
  External feedback is "dissipative coupling" — theoretical case for sbx's delta.
- **Progress mirage** (2607.25152) — self-grading agents "accept plausible changes as progress while
  outcomes stagnate"; only a world-state oracle grounds the loop. sbx's delta IS that oracle signal.
- **Self-correction as feedback control** (2604.22273) — stability threshold: iterate only when
  ECR/EIR > Acc/(1−Acc). A run-to-run delta estimates ECR vs EIR → principled stop/continue rule.
- Repetition/stuck detection to reuse for "you already tried this": RRR (2605.29463), semantic cycle
  detection (2511.10650), Infinite Agentic Loops (2607.01641), LoopBench (2601.05693), loop/drift
  monitors (2608.02464, 2604.13759, 2608.06701, 2509.02360), Wink (2602.17037), Fail-Fast/Restart-Smart (2608.03222).
- Regression-aware gating: GRASP net-improvement-on-held-out (2605.29668); Contrastive Reflection
  (2606.30840); BSG-VA roles (2607.28871); Beyond-Binary dense reward (2601.03525); potential-based
  shaping = difference of potentials (Shaping Advice 2202.09489; Bootstrapped 2501.00989) = classical
  justification for a Δ-diagnostics potential.
- Memory siblings (squeez/token-optimizer/AgentDiet NOT in literature): Blast Radius "Recurring Dead
  Matter" (2608.07440), PROJECTMEM records failed debug attempts (2606.12329), MERIT dual-polarity
  (2608.05906), Ledger (2608.00808) — all dedup TEXT; none compute a semantic diagnostic delta.

## (D) Novelty verdict + six upgrades
**Verdict (frank):** primitives known individually (diagnostic deltas as RL reward; warning
classification in CI; crash new-vs-known; no-progress detection; avoid repeating patches). NOVEL &
unpublished: packaging a semantic, line-shift-tolerant, cross-run diagnostic+crash+test delta as
INFERENCE-TIME NL feedback — the conjunction of (i) matched fixed/new/unchanged diagnostics,
(ii) crash-identity movement ("moved a.c:9→b.c:15" vs "SAME → edit didn't affect it"), (iii) tests
fixed/broken/still-failing — on the feedback channel, not a gradient or human CI report. Frame as
"first to close the loop by feeding a grounded run-to-run STATE delta back to the agent as its
primary feedback." Do NOT claim novelty on "diagnostic deltas exist."

**Six upgrades:**
1. **Semantic (AST) diagnostic matching** (GumTree 2403.05939; SoliDiffy 2411.07718; AST-edit-distance
   2404.08817) — a diagnostic anchored to a moved/renamed node still matches after reformatting; kills
   false new/fixed churn from cosmetic edits. (Warning-cascading found AST/CFG beats textual.)
2. **Root-cause deltas, not symptom deltas** (DebugRepair 2604.19305; DynaFix 2512.24635; TraceCoder
   2602.06875; CausalRepair 2608.10613) — diff the root cause; say "same symptom, different cause."
3. **Explicit "you already tried this / no-op edit" verdict** — fuse crash-SAME + zero-diagnostic-delta
   + high code-diff → "your edit changed code but not the failure; you are repeating a class of
   attempt." Detect via RRR (2605.29463)/cycle detection (2511.10650); store failed direction (MERIT).
4. **Delta as potential-based progress reward AND stop rule** — expose Δ(errors, failing-tests) as a
   potential (2202.09489); gate iteration on ECR/EIR threshold (2604.22273); stop/replan when delta
   non-positive for k turns (ReflexGrad 2511.14584).
5. **Regression-vs-progress accounting + flaky guards** — report roles like BSG-VA (bug-discriminating
   / regression-only / misleading); confirm a "new" failure REPRODUCES before charging it to the edit
   (flaky-vs-fault 2302.10594, 2401.15788; FlakiMe 1912.03197).
6. **Tiered crash identity + LLM-embedding fallback** — (kind+first frame) → distance-thresholded
   signature + crashline tie-break (CASR) + learned/embedding fallback (TraceSim, GPTrace) for
   ambiguous frames, stable under one-frame shifts/inlining.
