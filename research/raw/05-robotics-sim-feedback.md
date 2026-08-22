# Raw report 05 — LLM agents writing robot code in closed loop with physics simulators (as of 2026-08-22)

Evidence grades: A = peer-reviewed/official docs; B = arXiv preprint; C = blog/secondary.

## 1. Foundational works (2022–2024)

| Work | URL / year | What LLM writes | Sim & feedback | Grade |
|---|---|---|---|---|
| Code as Policies | arxiv.org/abs/2209.07753 (2022, ICRA'23) | Python policy code over primitives; RoboCodeGen (37 problems) | Real/sim execution, no automatic feedback loop | A |
| ProgPrompt | arxiv.org/abs/2209.11302 (2022) | Program-like plans with assert/precondition checks | VirtualHome; assertion failures trigger recovery | A |
| Language to Rewards | arxiv.org/abs/2306.08647 (CoRL 2023) | Reward code for MuJoCo MPC | 90% of 17 tasks vs 50% CaP; human-in-loop feedback | A |
| Text2Reward | arxiv.org/abs/2309.11489 (ICLR'24) | Dense reward code | ManiSkill2/MetaWorld/MuJoCo; 13/17 ≥ expert | A |
| Eureka | arxiv.org/abs/2310.12931 (ICLR'24) | Reward code, evolutionary search K=16, 5 iters | Isaac Gym, 29 tasks; beats humans on 83%. Reward reflection = scalar reward components at checkpoints + success rate/episode length. Ablation: removing reflection cuts score 28.6% | A |
| DrEureka | arxiv.org/abs/2406.01967 (RSS'24) | Reward + domain randomization | Isaac Gym; reward-aware physics prior; real quadruped | A |
| RoboGen | arxiv.org/abs/2311.01455 | Task proposals, scenes, rewards | propose-generate-learn; weak physical feedback | A |
| GenSim / GenSim2 | arxiv.org/abs/2310.01361; 2410.03645 | Sim task code + expert policies | Code verified by execution | A |
| Gen2Sim | arxiv.org/abs/2310.18308 | Assets, tasks, reward functions | RL success as feedback | B |
| VoxPoser | arxiv.org/abs/2307.05973 | Code composing 3D value maps | Closed-loop replanning from perception | A |
| RoboCodeX | arxiv.org/abs/2402.16117 | Manipulation code | No sim-feedback loop | B |
| RoboScript | arxiv.org/abs/2402.14623 | Manipulation code via ROS | Gazebo validation | B |
| CodeBotler / RoboEval | arxiv.org/abs/2311.11183 (RA-L'24) | Service-robot programs | Symbolic simulator + temporal-logic trace evaluator | A |
| Robo-Instruct | arxiv.org/abs/2405.20179 (COLM'25) | Robot programs | Symbolic sim checks | B |
| REFLECT | arxiv.org/abs/2306.15724 (CoRL'23) | Failure explanation + corrected plan | Hierarchical multisensory summary | A |
| ControlAgent | arxiv.org/abs/2410.19811 | PID/lead-lag params | Python control toolbox; iterative metrics | B |

## 2. 2025–2026 agentic robotics coding
- **CaP-X** (arxiv 2603.22435, Mar 2026) — CaP-Gym (REPL over Robosuite/LIBERO-PRO/BEHAVIOR, 187 tasks), CaP-Bench, CaP-Agent0 (18% on LIBERO-PRO), CaP-RL. Feedback: stdout/stderr from Python sandbox, Visual Differencing Module (NL scene deltas), RGB, privileged poses. GPU mandatory. B.
- **RHO: Your Coding Agent is Secretly a Roboticist** (arxiv 2606.16458, Jun 2026, Berkeley) — coding agent evolves policy repos; "REaaS" sidecar proxy container + whitelisted calls, evaluator artifacts excluded, protected-file integrity checks. Feedback: shaped reward, structured side info, VDM, tracebacks. Cost: 625M input tokens, $2,821, 1,776 REaaS calls for 70% on CaP-Bench Robosuite; RAI/O3DE 23.5%→44.3% with 27% fewer tool calls. **CLOSEST PRIOR WORK.** B.
- **Playful Agentic Robot Learning / RATs** (arxiv 2606.19419, Jun 2026) — per-step verifier (objective, code slice, runtime values, before/after visuals); failure diagnoser returns failure category, first failed step, repair suggestion; static checker rejects unbounded loops. +20.6pp over CaP-Agent0. B.
- **ASPIRE** (arxiv 2607.00272, Jun 2026, NVIDIA/Berkeley/UT) — execution engine exposes fine-grained multimodal traces (perception, contact dynamics, execution state); 31% vs 4% zero-shot. B.
- **FAEA** (arxiv 2601.20334, Jan 2026) — Claude Agent SDK unmodified on LIBERO/ManiSkill3/MetaWorld: 84.9/85.7/96%. B.
- **RDA** (arxiv 2606.01672, RLC'26) — VLM agent evaluates trajectories, revises reward code; argues Eureka scalar reflection hides distinct failure modes. B.
- RF-Agent (2602.23876) MCTS over reward code; LEARN-Opt (2511.19355) Isaac Lab self-derived metrics; Diagnostic-Driven Refinement (2605.28918) failure taxonomy fed to LLM (MiniGrid 2.3→97.6%); IsaacLabEureka (github isaac-sim/IsaacLabEureka).
- Debate2Create (2510.25850) morphology+reward co-design MuJoCo; MLES (2508.05433) multimodal evolutionary search.
- Test-Driven Agentic Framework for Reliable Robot Controller (2603.00455, Feb 2026) — structured tests, dual-tier repair, Webots. ModuLoop (2606.03047, RA-L'25) closed-loop debugger with probes. RoboInspector (2508.21378) failure-code feedback +35%.
- LLM-as-simulator (2512.02002) — text-based sim; contrast point.
- ROS 2: RAI (2505.07532; github RobotecAI/rai), ROS-LLM (2406.19741, NMI 2026), ROSClaw (2603.26997) safety envelope. None generate controller code against physics feedback.
- Assets: Articraft (2605.15187) URDF programs + tests; URDF-Anything+ (2603.14010); ArtiWorld (2511.12977).
- Gemini 3 + MuJoCo WASM demo (Feb 2026, C); Isaac Lab-Arena (2026); SIGA (2606.09774) validation-gated termination; GenSwarm (Nature MI 2025).

## 3. Feedback forms given to the LLM
| Form | Systems |
|---|---|
| Scalar reward-component stats + success/episode length | Eureka, IsaacLabEureka, RF-Agent, LEARN-Opt |
| Feasible physics-parameter ranges | DrEureka |
| stdout/stderr/tracebacks | CaP-X, RHO, RATs, ModuLoop, test-driven |
| NL scene-delta from images (VDM) | CaP-X, RHO |
| VLM judgments of video, failure summaries | RDA, MLES, RATs |
| Structured verdicts: failure category, first failed step, repair hint | RATs; 2605.28918; RoboInspector |
| Multimodal traces incl. contact dynamics | ASPIRE |
| Temporal-logic trace evaluation | RoboEval, RoboGuard |
| Test-suite pass/fail | Test-driven framework, Articraft |

**No robotics paper compares feedback representations on tokens-per-success.** Outside robotics: EffiPair (2604.05137) compact pairwise feedback; CoACT (2607.02911) action-preserving observation compression for coding agents; terminal-observation compression (2604.19572).

## 4. Benchmarks
CaP-Bench/CaP-Gym (GPU), LIBERO-PRO, MolmoSpaces, RoboEval (symbolic, CPU), RoboCodeGen (37), ManiSkill3 (2410.00425; CPU mode exists), RoboCasa/RoboCasa365 (2603.04356), BEHAVIOR-1K (GPU), Isaac Lab (+Arena), MuJoCo Playground (2502.08844, MJX), Gymnasium/MuJoCo + DM Control (CPU), HumanoidBench, Eureka Isaac Gym suite.

## 5. Isolation/safety
Only RHO documents real isolation (sidecar proxy container, whitelisted REaaS). CaP-X says "Python sandbox" w/o details. Guardrails: RoboGuard (2503.07885, RA-L'26) TL specs unsafe 92%→<3%; runtime governance (2604.07833) 96.2%; ROSClaw; AgentSpec (2503.18666); VerifyLLM; Safety Chip. Formal: LLM→certified H∞ (2511.07894), BarrierBench (2511.09363), survey (2602.06971). Threats: AgentRob→Unitree (2602.13591), container sandbox-escape evals (2603.02277). **No work evaluates namespace/seccomp isolation of LLM robot code as a contribution.**

## 6. Simulator practicalities (CPU-only)
- MuJoCo: pip, no GPU; "simulations are deterministic"; humanoid.xml 12,327 steps/s single-thread (81 µs/step) (github mujoco discussions/1522); Python contact iteration halves throughput; headless MUJOCO_GL=egl/osmesa; pin binary + seed, single-thread per env; startup <1 s. MuJoCoUni (2605.24922) batched pool.
- MJX/Playground: JAX, GPU; CPU JIT slow — poor fit.
- PyBullet: CPU DIRECT headless, single-core; lower fidelity contacts.
- Genesis: CPU backend + headless supported but JIT compile, GPU recommended.
- Isaac Lab: GPU ≥16GB VRAM — unsuitable. ManiSkill3: GPU-centric, CPU SAPIEN mode usable.

## GAP ANALYSIS
Partially novel: pieces exist; the combination as reusable CPU-only measured component does not.
Closest: RHO (containerized whitelisted executor, structured side-info, token/cost accounting — but high-level CaP policies on GPU sims, $2.8k, no feedback-representation-vs-tokens study). CaP-X (sandbox+VDM+benchmark, no controller tasks, no token axis). Eureka/RDA/2605.28918 show feedback content matters but never measure tokens. RATs richest verdict schema, no isolation. RoboEval machine-checkable TL verdicts but symbolic sim.
Missing: (1) executor running LLM-written low-level controllers/reward code under namespace isolation with deterministic MuJoCo CPU; (2) typed "physical verdict" schema (success, constraint violations with first-violation time, torque saturation, contact events, stability margins) vs raw traces/plots/VLM captions; (3) controlled comparison of feedback representations on success-per-token and iterations-to-pass; (4) CPU-only reproducibility.

Three experiment task families:
1. Low-level control synthesis — MuJoCo/Gymnasium (InvertedDoublePendulum, Hopper, Reacher; Menagerie arms). Agent writes PD/LQR/MPC controller. Verdict: return, settle time, joint/torque-limit violations + first-violation timestamp, fall/NaN flags; 10-seed deterministic eval. Metrics: pass@k, tokens-to-pass, wall-clock.
2. Primitive-composed manipulation — Robosuite Lift/Stack or ManiSkill3 PickCube CPU; CaP-Bench S-tier subset. Verdict: success, displacement, contact events, collisions, path length; compare stdout-only vs structured verdict vs VDM NL.
3. Reward/cost design with cheap optimizer — Eureka-lite: reward for sampling MPC or short PPO (Ant/HalfCheetah, 5-min CPU). Verdict: component stats compressed to quantiles + failure taxonomy tags. Metric: fitness vs tokens/iteration.
