# Round2-01 — Do LLM coding/repair agents actually USE execution feedback, or bypass it? (2026-08-23)

Evidence: ● full text read (primary); ○ abstract/index (primary preprint unless noted). arXiv IDs encode date (YYMM).

## (A) Key papers with the number

**Counterfactual value of execution feedback**
- ● **"To Run or Not to Run" (2606.26978, Jun 2026)** — DIRECT MATCH to our finding. 7,745 SWE-bench traces (avg 8.8 test runs/task) + 3,000 controlled repairs (Claude Code/Sonnet-4.5, Codex/GPT-5.2, OpenCode/Qwen2.5-Coder-32B), execution Prohibited vs Unrestricted. Resolve-rate gap only **1.25 pp (n.s., p>0.05)** for commercial SOTA, ≈0 for OpenCode; prohibiting execution saves **56–62% tokens, 48–54% wall-clock**. **54–66% of commercial cases are a single edit**; localization without execution stays >95%; GPT-5.2 runs code early only **1.8%** of the time; only **49.2%** of instances modify code AFTER an execution. "Current agents apply execution indiscriminately, paying its cost where it provides little benefit." **This is our Sonnet 12/12 first-run-pass at 200-instance scale.**
- ● **Olausson, "Is Self-Repair a Silver Bullet?" (2306.09896, ICLR 2024, peer-reviewed)** — at EQUAL sample budget, self-repair often ties/loses to plain resampling. Self-repair bottlenecked by feedback quality: swapping GPT-4's own explanation for a HUMAN's raises repaired-pass 1.58× (33.3→52.6%).
- ● **"Try Again, Don't Look Back" (2607.26117, Jul 2026)** — placebo-controlled, Qwen2.5-Coder 1.5/3/7B, MBPP+. Arms: resample(blind) / placebo(own failed code + "wrong") / feedback(+test output) / reflect. Feedback info adds +0.000/+0.026/+0.008 over placebo (all n.s.). Showing failed code is HARMFUL via anchoring: placebo−resample = −0.061 (p=0.006) at 1.5B. "Measured against no-repair, feedback gains 12.2 pts; against blind resampling at matched budget it loses. The treatment is unchanged — only the comparison moved." Penalty tracks capability r=0.96.
- ● **"Feedback Over Form" (2604.21950, Apr 2026)** — WEAK-model counterpoint: at 1–3B, execution feedback improves >4σ on HumanEval+MBPP; text-only (no exec) shows no gain. But fixes runtime errors (NameError/Syntax), RARELY logic (Assertion); early stopping load-bearing.
- ○ RLEF (2410.02089); RubricRefine (2605.09730, real exec feedback only 0.75 vs 0.65); "Is Three the Magic Number?" (2607.05197) & "How Many Tries" (2604.10508) — help but DON'T control for matched resampling (the confound).

**Faithfulness / attention**
- ● **"LLM Agents Are Not Always Faithful Self-Evolvers" (2601.22436, Jun 2026)** — experience faithfulness = does perturbing input change behavior. 4 frameworks, 13 backbones, 9 envs: agents use raw trajectories faithfully but DISREGARD condensed/summarized experience (Corrupt/Irrelevant/Filler ≈ baseline) even when it's the only experience — persists at all scales (Qwen3 1.7B–32B, Sonnet-4.6). **Warning for our compressed verdict.**
- ● **"Tool-Induced Myopia (TIM)" (2511.10899, Nov 2025)** — tools raise accuracy +19.3 pp but reasoning degrades; TIM in ~55% of high-risk solutions; "tool outputs as substitutes for reasoning."
- ○ ToolFailBench (2607.04686): "a model that never calls a tool and one that calls it but IGNORES the result look identical under final accuracy." Closing the Reflection Gap (2606.14211); Doing What They Say Not What They Reason (2606.00476).
- **COBALT UNVERIFIED** — no paper matches "learn to follow feedback without reasoning about validity." Use instead: Don't Blindly Trust It, Trust No Tool (2605.17453), ExeCRE (2608.04439). **Correct our REPORT which cited COBALT.**

**Corrupt/remove feedback (ablation & value-inversion)**
- ● **"Don't Blindly Trust It" (2606.21409, Jun 2026)** — matched loop, only observation varied: Clean/No-Feedback/Corrupted. HotpotQA Qwen2.5-7B 44.8→22.3→4.7 F1; GPT-4o 65.8→52.7→2.8; FEVER 84.2→67.1→11.0. **Value inversion**: misleading feedback worse than NO feedback, even GPT-4o. "Hedging is not skepticism." Argues matched no-feedback fallback must be first-class control.
- ○ AgentNoiseBench (2602.11348); "Lost in the Noise"/NoisyBench (2601.07226); Trust No Tool (2605.17453).
- ○ RAG-transferable methods: Attribution Blind Spot (2605.26778); CUE-R (2604.05467); Faithfulness-QA.

**Capability-dependence** — gains concentrate in WEAK models/hard tasks: Feedback Over Form (>4σ at 1–3B); Olausson (feedback-quality bottleneck; +34% GPT-3.5 competition tier); Try Again (r=0.96, closes by 7B); "Compile, Then Page" (2607.11346, "runtime guidance is capability-gated"); "Harness Updating Is Not Harness Benefit" (2605.30621).

## (B) The bypass phenomenon IS documented — our result is a known regime
1. Trace audits show strong models skip execution (To Run or Not to Run: 1.25pp gap, 1.8% early exec, 54–66% single-edit).
2. Ablations prove the "gain" is the extra attempt, not the feedback (Olausson, Try Again: +0.00/0.03/0.01 vs matched control; can be NEGATIVE via anchoring).
3. Validation-adequacy audits: even when agents run tests, evidence usually doesn't bear on the bug. ● BSG-VA / "Validation Evidence in LLM Repair Agents" (2607.28871, Jul 2026): 3,730 events/110 tasks: **46.0% of positive checks are regression-only or misleading**; 23.8% of runs close on non-discriminating evidence. "Understanding APR Agents Through Traceability" (2605.xxxx, 5 agents × 500): fail to reproduce 40–60% of time, regression-test selection 4%→100%, "primitive bash tooling, no debuggers."
- Named failure modes as prior art: Lucky Pass (AgentLens 2605.12925: 10.7% pass by chance); Coherence Collapse/TRAJEVAL (2603.24631: 60–69% of capable-model failures reach+edit correct functions yet wrong patch); Premature Commitment/ECLoop (2607.28815); All Smoke No Alarm (2606.18168).
- Internal probes: ○ "Latent Programming Horizons" (2607.xxxx): decode "passes tests / introduces regression" from hidden states AUC up to 0.83 — model internally represents exec state whether or not it ran.

## (C) How to measure feedback-use rigorously (interventional, not correlational)
1. **Matched no-feedback / blind-resampling control at equal budget** (Olausson, Try Again, To Run or Not to Run) — the delta over THIS, not single-shot, is feedback value. The field's headline demand.
2. **Withhold-vs-corrupt-vs-clean matched loop** (Don't Blindly Trust It): fix prompt/actions/decoding, vary only observation. corrupted≈clean ⇒ not reading; corrupted<no-feedback ⇒ over-trust (value inversion).
3. **Perturbation faithfulness** (Faithful Self-Evolvers): Empty/Shuffle/Corrupt/Irrelevant/Filler observation.
4. **Post-observation action rate** (patch changes after feedback: 49.2%), single-edit ratio, first-run-pass — cheap bypass metrics.
5. **Evidence-adequacy replay** (BSG-VA): replay each check on buggy/candidate/gold to label discriminating power.
6. **Process/latent probes** (TRAJEVAL stage decomposition; hidden-state probes AUC 0.83).

## (D) Five implications for sbx
1. **Report "feedback unused" against a MATCHED control** (typed vs raw vs no-feedback, matched turns/tokens), or reviewers discount it. Our 12/12 first-run-pass is a bypass metric (good); the value claim needs the no-feedback denominator. This IS the contribution.
2. **Force feedback into the causal path**: cross-file/repo bugs, hidden/withheld/large source (debug-gym 2503.21557), run-before-edit/tool-only, silent logic bugs where diagnostics don't name the fault. Then typed verdict has room to matter.
3. **Measure use by CORRUPTING the verdict** (flip first-user-frame, swap crash type, blank delta). Patches unchanged under corruption ⇒ unused — stronger claim than flat pass rate. Watch for value inversion.
4. **Stratify by capability / margin-of-solvability; predict the crossover.** Plot sbx gain vs first-run-pass rate. Our Sonnet(bypass)/Qwen-3B(benefits) split is the EXPECTED shape: "typed feedback pays off in the capability band where the model can't fix from source." Quantify the band, don't average.
5. **Position DELTA + typed verdict against the two mechanisms that make raw feedback fail**: (a) anchoring (Try Again) — a delta that abstracts away the raw failed attempt may dodge the anchoring penalty (testable: typed-delta vs raw-stdout regeneration similarity); (b) evidence-inadequate closure (BSG-VA 46%) — typed verdict encoding root-cause + first-user-frame + delta is a signal about whether the change bears on the defect → benchmark on reduction in evidence-inadequate/lucky-pass closure (AgentLens, BSG-VA), not just resolve rate.

**Top reads:** 2606.26978, 2607.26117, 2606.21409, 2607.28871, 2306.09896, 2601.22436.
