# Round2-05 — Determinism, replay & snapshot-fork for LLM agents (2026-08-23)

Tags: [preprint] arXiv not peer-reviewed; [repo] OSS; [eng] vendor blog. WebSearch budget-exhausted;
from Firecrawl research/dev index + direct fetches; dates/numbers confirmed by fetching.

## (A) Newest deterministic/hermetic/replayable execution for agents
- **"Grounded Scaling: Why Agentic AI Needs Deterministic Environments"** (2606.22495, Jun 2026) —
  MOST ON-POINT. Formalizes our thesis: per-step determinism δ<1 → k-step success degrades as **δ^k**;
  "environments designed for human tolerance" fail exponentially for long chains. Supply Certainty
  Index (5 properties), Determinism Maturity Model (5 levels). **Our anchor citation — turns "deltas
  need determinism" into a named falsifiable framework.**
- Record-replay is now a subfield: **agrepl** (2607.16200, MITM transport-layer replay; names LLM
  sampling variance, external API state, CDN headers, exec-env noise); **LOOP Skill Engine** (2605.14237,
  99% success/99% token reduction); **DFAH/DFAH-Bench** (2601.15322, 2607.20491, 4,700+ runs T=0:
  decision-determinism ≠ accuracy — determinism is an independent audit axis). Lineage: Confining
  Nondeterminism (2607.10508), execution-lineage DAGs (2605.06365), ESAA (2602.23193), R-LAM (2601.09749).
- **Snapshot/microVM fork = where industry moved** (all confirm deterministic-resumable-from-intermediate
  as enabling): **E2B fork** (POST /sandboxes/{id}/fork, SDK 2.34/2.35); **forkd** (Firecracker+MAP_PRIVATE
  COW: 100 microVMs in 101 ms, branch live VM 56 ms); **Morph** (<250 ms), **mitos**, Fly Sprites, Vercel
  Sandbox; **libkrun displacing Firecracker for local agents** (iii.dev May 2026: Claude Code/Codex on
  MacBooks can't boot Firecracker → libkrun cross-platform, warm boot few-hundred-ms).

## (B) Determinism ↔ feedback-quality (STRONGEST section — direct backing for "deltas need determinism")
1. **"On Randomness in Agentic Evals"** (2602.07150, Feb 2026) — 60,000 SWE-bench-Verified trajectories:
   single-run pass@1 varies **2.2–6.0 pp**, std **>1.5 pp even at T=0**, "trajectories diverge early."
   Reported 2–3 pp gains may be pure noise. Proof: without a pinned substrate the signal is noise-dominated.
2. **"The Replay Gap"** (2608.08239, Aug 2026) — forks live SWE-bench trajectories: after any divergence
   **only 3% of replayed states remain valid**; all 5 outcome-flips in swap arms, 0/359 control forks;
   static replay predicts patches 0.00–0.11 similarity; swaps rewrite 61–94% of post-fork actions.
   **Systems-level analogue of our 40/40 vs 0/40 ASLR result**: can't cheaply diff two runs unless the
   substrate is byte-stable, else the delta is contaminated within a few steps.
3. **"Necessary but Not Sufficient"** (2606.26185) — T=0 does NOT make an LLM-judge deterministic
   (providers default temp=1.0); determinism must be enforced at harness/env layer, not sampling. (Our layer.)
4. Flaky feedback measured: Snyk VulnBench JS (2606.15762, 80/161 findings in only 1 of 5 identical reps);
   AgentLens Lucky Pass (2605.12925, 10.7%); Benchmarking the Benchmarks (2607.02577, 18.5% misalignment,
   "brittle state matching"); perf-opt benchmarks conflate runtime instability with skill (2607.01211).
5. Compression angle: verifiable envs carry rich textual feedback scalar rewards discard (SDPO 2601.20802,
   LLM-as-a-Coach 2607.18110); reward compression improves learning (2509.06810). Our delta = compression
   of a byte-stable trace → only well-defined if baseline is deterministic.
- **Paper spine:** (B1) noise exists even at T=0 → (Grounded Scaling) compounds as δ^k → (Replay Gap) must
  re-execute in a fixed substrate not replay logs → hermetic executor is the precondition for a meaningful delta.

## (C) Snapshot/fork for tree-search + speculative repair (concrete sbx extension)
- **Branching Policy Optimization (BPO)** (2607.14171, Jul 2026) — snapshots sandbox at high-entropy
  decision points, forks K actions, computes **per-step advantages from sibling returns (delta between
  forks)**: +3.6–6.1 pp success, halved gradient variance, 38% fewer updates. Working "fork the env, try
  N, compare delta" — REQUIRES determinism.
- **DeltaBox** (2605.22781) — 14 ms checkpoint / 5 ms rollback (DeltaFS layered COW + fork-from-frozen-template).
- **Crab** (2604.28138) — eBPF semantics-aware C/R; recovery 8%→100%, traffic −87%, overhead <1.9% because
  **>75% of agent turns produce no recovery-relevant state**. Lesson: snapshot only effectful turns.
- **"Systems Foundations for Agentic Exploration"** (2510.05556) — generic CRIU/container-commit too slow
  and broken once agents share files/sockets/cloud APIs; 3 open problems: fork semantics, external
  side-effects, native forking.
- SpecBox (2607.23933); MCTS-over-edits: CodePilot (2602.00129), PhoenixRepair (2607.18859), MARS (2607.29055),
  ARIADNE (2605.02431); Fault-Tolerant Sandboxing (2512.12806).
- **Extension:** sbx's 4.6 ms hermetic start already beats CRIU-class C/R; add DeltaBox-style COW fork of
  pivot_root rootfs + frozen template → branch mid-trajectory, emit inter-fork deltas (BPO-style) as the
  RL/repair signal. Natural next paper.

## (D) Perf & security frontier to position against
- Startup: **Sandlock** (2605.26298, ~5 ms vs ~200 ms container / ~100 ms microVM, unprivileged
  Landlock+seccomp+notify) — CLOSEST PEER, benchmark head-to-head. **youki** (111.5 ms create→delete vs
  runc 224.6, crun 47.3; but **CVE-2025-62161** — Rust ≠ safe). **hakoniwa** (Rust ns, TOML). nsjail/minijail
  = C baseline. forkd/E2B/Morph microVM fork 56–250 ms. **"Rollout Infrastructure Tax in Coding-Agent RL"**
  (2607.01415): up to **110× cold-start variation** across substrates — why 4.6 ms matters at RL scale.
- Security: **"AI Code Sandboxes: Comparative Security Study Part 1"** (2606.08433, Jun 2026): engine class
  (microVM/userspace-kernel/OCI) separates on attack-surface/CVE; patch lag 0 to 471+ days; "pin policy
  dominant." Frame sbx honestly as **OCI-container-class isolation**. **SandboxEscapeBench** (2603.02277):
  frontier LLMs exploit misconfigs/kernel flaws — class a user-ns sandbox can't fully contain. **Page-cache
  side channel** (2607.17518): host page cache observable across containers AND gVisor/Kata when tenants
  share host-backed FS. Threat corpus: JAWS-Bench, LITMUS, SafeClawBench, Skill-Inject, GitInject.
  Escalate to microVM for untrusted/networked/model-generated code.

## (E) Six upgrades
1. **Seeded getrandom via seccomp-notify (highest determinism ROI)** — Sandlock does exactly this
   ("getrandom → Deterministic PRNG injection"). Intercept getrandom/`/dev/urandom`/RDRAND → fixed-seed
   PRNG. Removes a source no-ASLR doesn't cover; extends 40/40.
2. **Time namespace (CLONE_NEWTIME) + frozen clock** — pin MONOTONIC/BOOTTIME; intercept
   clock_gettime/gettimeofday/time (vDSO-aware). Caveat: NEWTIME doesn't virtualize REALTIME → still needs
   seccomp/LD interposition. (Timestamps #1 reproducibility-breaker: Docker study 2602.17678, only 2.7%
   bitwise-reproducible without config; SOURCE_DATE_EPOCH standard fix.)
3. **CPU pinning + isolcpus/single-core replay** — remove scheduling/interrupt jitter (2511.03533, 2509.03855).
4. **COW snapshot-fork for delta-native tree search (biggest capability jump)** — DeltaBox-style layered-COW
   on pivot_root + frozen template; then BPO-style branch-and-diff; Crab lesson: eBPF-classify effectful turns.
5. **Canonicalize residual nondeterminism in the delta layer** — strip/normalize PIDs, temp paths,
   hostnames, inode/readdir order before diffing; sorted readdir, LC_ALL=C, TZ=UTC, SOURCE_DATE_EPOCH
   (Docker 2602.17678, Nix 2501.15919). Cheaper than eliminating every source; shrinks delta noise.
6. **Explicit microVM escalation tier + side-channel hardening** — keep 4.6 ms user-ns default; add
   `--isolation=microvm` (libkrun local/macOS, Firecracker Linux) for untrusted/networked code (2606.08433,
   2603.02277); private overlay pages per sandbox to avoid shared page cache (2607.17518) — COW in (4) gives it free.

**Positioning:** sbx in the ~5 ms unprivileged-ns class (Sandlock/hakoniwa), 10–20× faster than
youki/microVMs; hermetic determinism now backed by named theory (Grounded Scaling δ^k) + hard evidence
(On Randomness T=0; Replay Gap 3%-valid). Growth path: fork-and-diff feedback for tree-search/speculative repair.
