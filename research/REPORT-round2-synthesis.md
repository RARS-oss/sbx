# Round 2 synthesis — how people have done this, and how we do it better

*2026-08-23. Six parallel deep-research agents, ~130 primary sources, briefed with what our own sbx
experiment already proved. Raw reports: `research/round2/01…06`. This is the actionable distillation.*

---

## 0. The one-paragraph verdict

The **principle** we started from — "execution feedback should be a typed API, not a byte stream" — is
**no longer novel**: by mid-2026 it is converging independently across a dozen preprints (VeriHarness,
"AI Coding Agents Need Better Compiler Remarks", RLCSF, Diagnosis-Before-Recovery) and shipping products
(.NET Binlog MCP, pytest `--receptor`, Anthropic's code-execution-with-MCP). That is **good news, not
bad**: the field validated our thesis while we were building it, which de-risks it. What is **still
genuinely ours** are three narrower things the literature does *not* contain: (1) a **deterministic,
executor-side verdict that unifies compiler + sanitizer/crash + tests into one machine-readable object**
(everyone else does one domain, or uses an LLM to distill); (2) **diagnostic-level run-to-run DELTAS fed
back as the agent's primary signal** (unpublished — the closest, RLCSF, uses the delta as an RL *reward*,
never surfaces it); (3) the argument, now backed by named theory, that **determinism is the precondition
for those deltas**. Our experimental finding — strong models bypass feedback by fixing from source — is
also a *documented regime*, not a fluke, and there is a rigorous way to turn it into a contribution.

---

## 1. What the research says about our core claims

**Claim "feedback is a typed API" — CONVERGED, reframe from "nobody does this" to "we do the hard version."**
- Independent arrivals: VeriHarness (2607.14167) typed {location, observed value, admissible alternatives};
  "Better Compiler Remarks" (2604.13927) precise remarks 3.3× success, *ambiguous* remarks actively
  harmful; RLCSF (2510.22907) "compilers already compute the missing signal but expose it for human IDEs
  not learning loops" — our thesis verbatim; MCP spec 2025-06-18 standardized the *envelope*
  (`outputSchema`/`structuredContent`); Anthropic code-exec-with-MCP made typed results house style.
- **Two hard lessons we must absorb:** (a) VeriHarness proved **JSON-vs-prose is a wash — the *fields*
  matter, not the serialization**; so we sell "the right fields + determinism + cross-domain unification",
  never "it's structured." (b) The single most valuable field was **"admissible alternatives"** (what a
  legal fix looks like), not the raw facts — location+value alone ≈ raw baseline.
- **Still unoccupied (verified):** no tool unifies compiler+sanitizer/crash+tests deterministically; no
  cross-tool "run-result" schema standard exists (K8s agent-sandbox and OpenSandbox standardize the *box*,
  not the *verdict*). Sanitizer crash-typing (first-user-frame, alloc/free sites) is the rare part.

**Claim "deltas need determinism" — NOW BACKED BY NAMED THEORY + HARD EVIDENCE. Our strongest section.**
- **Grounded Scaling** (2606.22495): per-step determinism δ<1 → k-step success decays as **δ^k**. This is
  our anchor citation; it turns our assertion into a falsifiable framework (cite it).
- **The Replay Gap** (2608.08239): after any divergence only **3% of replayed states remain valid**; static
  replay predicts patches at 0.00–0.11 similarity. This is the systems-level analogue of *our own* 40/40
  byte-identical (hermetic) vs 0/40 (ASLR) result — you cannot diff two runs unless the substrate is stable.
- **On Randomness in Agentic Evals** (2602.07150): single-run pass@1 swings 2.2–6.0 pp, SD>1.5 pp *even at
  T=0*. Determinism must be won at the harness/environment layer (ours), not by sampling settings.

**Claim "typed+delta helps" — CAPABILITY-GATED, and our bypass finding is a known regime.**
- **To Run or Not to Run** (2606.26978): prohibiting execution costs SOTA agents only **1.25 pp** (n.s.);
  54–66 % single-edit; GPT-5.2 runs code early 1.8 % of the time. Our "12/12 first-run-pass" is this, at
  scale. **Feedback value is a lever at the margin of capability** (Feedback Over Form >4σ at 1–3B; Try
  Again r=0.96 vs capability; Compiler Remarks "capability-gated") — exactly our Sonnet(bypass)/Qwen(gain) split.

---

## 2. How to make the EXPERIMENT bulletproof (the methodological upgrade)

Our current experiment has one hole the literature will attack, and one it now hands us the fix for.

1. **Add a matched no-feedback control.** The field's headline demand (Olausson ICLR'24; Try Again 2607.26117;
   To Run or Not to Run): feedback value = delta over **blind resampling at equal turn/token budget**, not
   over single-shot. Otherwise "typed gains 12 points" flips to "loses" under the honest denominator. Add a
   `--no-feedback` arm (return only exit code) at matched budget.
2. **Measure use by CORRUPTING the verdict, not just adding it.** Run the matched loop (Don't Blindly Trust
   It 2606.21409) + perturbation set (Faithful Self-Evolvers 2601.22436): flip the first-user-frame, swap the
   crash kind, blank the delta. Patch unchanged under corruption ⇒ feedback unused — a *stronger* claim than
   flat pass-rate. Watch for **value inversion** (a wrong verdict that *harms* — proof the channel is read).
3. **Switch to source-insufficient tasks so feedback is exercised.** Single-file bugs are fixed from source →
   feedback never touched. Move to: AutoPatchBench / ARVO memory-safety (oracle = PoC stops crashing), SEC-bench
   (best agent 18% PoC/34% patch — huge headroom), Multi-SWE-bench C/C++/Rust, or our own tasks under
   **run-before-edit (done) + progressive source masking** (AutoExperiment 2506.19724). Pick instances with a
   frontier ceiling < ~50%.
4. **Primary metrics = turns-to-resolve + cache-aware billed cost, not tokens.** Tokens are the wrong unit
   (PointFive: compression tops out ~5%, can raise cost; HAL: accuracy gains ≠ token cuts). State up front:
   *typed+delta lowers turns and $/resolved even if it adds per-turn tokens.* Add a **localization sub-metric**
   (turns/tokens-to-correct-file) — where the win concentrates before the first edit.
5. **Statistical rigor:** paired design (same task+seed, raw vs typed) + paired BCa bootstrap; ≥10–20 seeds
   (SD>1.5 pp at T=0); report pass^k reliability and CIs; separate *submit* from *test-verified resolve*; never
   report a single-run delta. Avoid contaminated substrates (28.5% of SWE-bench Verified has weak tests; prefer
   fresh ARVO N-days / Live-kBench where the oracle is a crash).
6. **Ablate the typed fields.** raw / +location / +delta / +admissible-alternative — because the *added
   information*, not the JSON, is what moves the needle (VeriHarness). This tells us *which* component to keep.

**The honest framing that survives all of this:** "Typed+delta feedback is a lever at the margin of
capability. It lifts weak models over the fix-from-source threshold (Qwen-3B 0→3/12), and on strong models,
when the feedback channel is actually used, it delivers the same outcome in 7–20× less context — the
'same result, far less context' that byte-compression provably fails to give (RTK, r=0.15). Whether it also
cuts *turns* on a frontier model is an open question we test on source-insufficient benchmarks."

---

## 3. How to make the SYSTEM better — prioritized roadmap (merged across all six agents)

Ranked by (evidence strength × ease). Cheap wins first.

**Tier 1 — cheap, high-evidence, do next**
1. **Admissible-alternatives field per verdict.** Our crash-kind glossary already implies the fix class; emit
   1–3 *concrete legal* alternatives ("index must be in 0..len; here len==0"). This was *the* driver in
   VeriHarness (14/50→36/50) and Self-Reflective APIs (+37–40 pp). Prefer **checkable counterexamples over
   prescribed patches** (over-anchoring risk, 2607.26117). ~cheap.
2. **"Print the offending value" — deterministic first-frame locals at the fault.** The value that indexed,
   the null pointer, expected-vs-got operands — captured deterministically by the executor, no LLM. LDB +9.8%,
   NExT +26%/+14%, DebugRepair +51%. ~cheap–medium.
3. **Canonicalize residual nondeterminism in the delta layer** (sorted readdir, PID-ns-stable PIDs, temp-path
   normalization) so cosmetic churn never shows as "new/fixed." ~cheap.

**Tier 2 — medium, high-value**
4. **Semantic (AST) diagnostic matching** instead of ±3-line tolerance (GumTree/refactoring-aware) — a
   diagnostic on a moved/renamed node still matches after reformatting; kills false new/fixed churn.
5. **Progressive disclosure of the verdict** — terse line by default, agent *pulls* deeper fields (frame
   locals, full log) on demand. **One level only** (a second level never helps, sometimes breaks — 2607.17598).
6. **Emit the verdict as MCP `structuredContent` behind a versioned `outputSchema` (`sbx.run-result`)** so the
   agent can *query/branch on the object in code* (programmatic tool calling) rather than read prose — CodeAct
   +20%, Bitter-Lesson PTC holds under context-rot. Doubles as the missing cross-tool standard (land-grab).
7. **"You already tried this / no-op edit" verdict** — fuse crash-SAME + zero-diagnostic-delta + nonzero
   code-diff into an explicit signal, with a stop/replan rule (ECR/EIR threshold, 2604.22273). Attacks
   looping-without-progress (Mirror Loop ΔI −55%; progress-mirage).
8. **Delta-min the failing input** (deterministic reducer) when check-script inputs are large — ReduceFix
   +53.8% Pass@10; skip when small.

**Tier 3 — hard, research-grade (each is a follow-on paper)**
9. **Root-cause deltas, not symptom deltas** — diff *why* (which failing assertion / def-use / contact
   changed), so we can say "same symptom, different cause" (the case that most misleads agents).
10. **COW snapshot-fork for delta-native tree search** — DeltaBox-style layered-COW on the pivot_root rootfs +
    frozen template (target 14 ms/5 ms), then **BPO-style branch-and-diff**: fork K repairs, emit inter-fork
    deltas as the signal (+3.6–6.1 pp, 38 % fewer updates). Turns our determinism from "clean" into "productive."
    Crab lesson: eBPF-classify effectful turns, snapshot only those.
11. **Optional interactive-debug channel** (breakpoints/state-inspection behind the hermetic executor) for hard
    logic bugs — InspectCoder +5–60 %, 1.7–2.2× fewer attempts.
12. **Wire typed deltas as dense per-turn rewards for a feedback-following fine-tune** (RLEF/TaPR/MURPHY;
    SWE-RL 11→39 %) — teaches a model to *use* the verdict instead of resampling. Executor unchanged.

**Determinism upgrades (support Tier-3 and the paper's spine):** seeded `getrandom` via seccomp-notify
(Sandlock does exactly this), `CLONE_NEWTIME` + frozen clock, CPU pinning / single-core replay, `--isolation=microvm`
escalation tier (libkrun local / Firecracker Linux) for untrusted code.

---

## 4. Novelty, stated for a skeptical reviewer

- **Do NOT claim:** "feedback as a typed API is new" (converged); "JSON structuring helps" (VeriHarness: wash);
  "diagnostic deltas exist for the first time" (RLCSF has them as a reward; CI warning-cascading has version
  diffs).
- **DO claim, defensibly:** (1) the first **deterministic, executor-side verdict unifying compiler + sanitizer/
  crash + tests** into one object, with sanitizer crash-typing; (2) the first to feed a **run-to-run diagnostic
  +crash+test DELTA back to the agent as its primary inference-time feedback** (the conjunction, on the feedback
  channel, not a gradient or human CI report); (3) determinism as a **measured precondition** for that delta
  (our 40/40 vs 0/40, framed by Grounded Scaling δ^k and the Replay Gap's 3%); (4) a **capability-stratified**
  measurement showing feedback form is a lever at the margin of capability — with the honest "strong models
  bypass feedback" regime reported against a matched control.
- **Venue fit:** the metrics/rigor push (matched control, turns/cost, corrupt-the-verdict) is what recent
  traction papers (To Run or Not to Run, Try Again, Don't Blindly Trust It) have in common — lead with the
  rigor, not the artifact. FSE/ICSE/ASE, DL4Code @ ICML, or a systems-flavored EuroSys/SOSP workshop for the
  determinism+fork angle.

---

## 5. Corrections to our own docs (found by the research)
- The "COBALT" citation ("models learn to follow feedback without reasoning about validity") is **unverified —
  no such paper**. Replaced in REPORT.md with "Don't Blindly Trust It" (2606.21409, value inversion). ✅ done.
- Our survey's "NO harness/sandbox does typed feedback" is **out of date at the principle level** — update the
  related-work framing to "converging principle, but no deterministic cross-domain executor verdict + no
  run-to-run delta." (to apply)
