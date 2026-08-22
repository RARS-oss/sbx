# Raw report 03 — Execution feedback for LLM code agents: does the FORM of feedback matter? (2026-08-22)

Format: **Title** (authors, venue/year, link) — contribution; *feedback-relevant number*.

## 1. Foundational feedback loops and agent scaffolds

- **Teaching LLMs to Self-Debug** (Chen et al.; ICLR 2024; arxiv.org/abs/2304.05128) — execution results + self-explanation fed back. *+2–3% Spider; up to +12% TransCoder/MBPP with unit tests; unit-test feedback is the largest single contributor.*
- **Reflexion** (Shinn et al.; NeurIPS 2023; arxiv.org/abs/2303.11366) — verbal reflection in episodic memory. *HumanEval pass@1 80% → 91%.*
- **Self-Refine** (Madaan et al.; NeurIPS 2023; arxiv.org/abs/2303.17651) — self-critique without execution; later work (FeedbackEval) shows model-only critique is the weakest feedback type.
- **CodeT** (ICLR 2023; arxiv.org/abs/2207.10397) — generated tests + dual execution agreement. *HumanEval pass@1 65.8% (+18.8 abs).*
- **LEVER** (ICML 2023; arxiv.org/abs/2302.08468) — learned verifier over (NL, program, execution result). *+4.6–10.9%.* **CodeRL** (NeurIPS 2022) RL precursor with unit-test rewards.
- **LDB: Debug like a Human** (ACL Findings 2024; arxiv.org/abs/2402.16906) — per-basic-block runtime variable values (structured, distilled trace) instead of raw failure output. *Up to +9.8%; 98.2% HumanEval with GPT-4o + Reflexion seeds.*
- **InterCode** (NeurIPS 2023 D&B; arxiv.org/abs/2306.14898) — code as actions, raw execution output as observations.
- **CodeAct** (ICML 2024; arxiv.org/abs/2402.01030) — executable Python as unified action space. *Up to +20 pp success, up to 30% fewer actions vs JSON/text actions.*
- **SWE-agent: Agent-Computer Interfaces** (NeurIPS 2024; arxiv.org/abs/2405.15793) — interface design drives success. *SWE-bench Lite: 18.0% vs 11.0% shell-only. Ablations: iterative search −6.0 pp; file viewer 30 lines −3.7, full file −5.3; edit without linter −3.0; full observation history vs last-5 −3.0.* Principle: feedback should be "substantive … without unnecessary details."
- **AutoCodeRover** (ISSTA 2024; arxiv.org/abs/2404.05427) — code-search APIs + SBFL. *19% SWE-bench Lite at $0.43/issue.*
- **Agentless** (FSE 2025; arxiv.org/abs/2407.01489) — fixed pipeline; *reproduction tests give the largest gain in patch selection.*
- **OpenHands** (ICLR 2025; arxiv.org/abs/2407.16741) — CodeAct-style platform with sandboxed execution.
- **mini-SWE-agent** (2025; github.com/SWE-agent/mini-swe-agent) — ~100 lines, bash-only. *65% → >74% SWE-bench Verified with Claude 4.x* — with frontier models raw shell output + minimal scaffolding is competitive.

## 2. Compiler/diagnostic feedback

- **RustAssistant** (Microsoft; ICSE 2025; arxiv.org/abs/2308.05177) — rustc error text + ±50-line windows around all cited locations, error-grouping loop, changelog output format. *GPT-4: 92.6% micro-benchmarks, 73.6% real commits. Prompt/format ablation (GPT-3.5): basic 10.7% → +line prefixes 24.1% → +localization 58.2% → +fix-description-first 73.7%; disabling error grouping → ~14%.*
- **Google DIDACT build repair** (2024; research.google/blog/safely-repairing-broken-builds-with-ml/) — *34% of users with a monthly breakage apply an ML fix; no increase in rollbacks/sanitizer failures.*
- **Auto-repair without tests: industrial embedded C** (arxiv.org/abs/2510.13575) — *>40k commits; LLM CI resolves up to 63% of compilation errors.*
- **GradleFixer / AndroidBuildBench** (arxiv.org/abs/2510.08640) — *81.4% pass@1 with domain-specific tools.*
- **ComBench** (arxiv.org/abs/2603.27333) — 200 repo-level C/C++ compilation errors. *GPT-5: 146/200 compile, only 82/200 semantically correct.* **CCrepairBench** (arxiv.org/abs/2509.15690) C++ compile-repair dataset.
- **Type-Error Ablation and AI Coding Agents** (Krishnamurthi & Flatt; 2026; arxiv.org/abs/2606.01522) — first controlled *verbosity* ablation of error messages for agents (2,400 trials, qwen2.5-coder:14b). *Successes/600: test-failure only 201; minimal type error w/o location 97; minimal w/ location 153; conventional 287; full unification stack 317.* Richer diagnostics improve the *first hypothesis*, not convergence.
- **VeriHarness: Structured Feedback Improves Repair** (Ray & Goyal; 2026; arxiv.org/abs/2607.14167) — raw diagnostic vs {location, observed value, admissible alternatives}. *Qwen2.5-Coder-14B 14/50 → 36/50, Llama-3.1-8B 8/50 → 29/50 (+44/+42 pp); same info as prose gives +42 (JSON adds +2/0, n.s.); location+observation without alternatives ≈ raw; typed fields use 10–14% fewer prompt words via fewer calls.* Caveat: TextWorld, not code.
- **PGS: Property-Oriented and Structurally Minimal Feedback** (arxiv.org/abs/2506.18315) — failures as property violations + minimum-token counterexample. *LCB-Hard: I/O feedback 28.1→32.0, property feedback →36.2; minimal-token counterexample +13.2 pp at 4.7k tokens vs +9.1 pp at 5.7k for largest.*
- **FeedbackEval** (arxiv.org/abs/2504.06939) — six feedback modalities, five LLMs. *Repair@1: Mixed 63.6, LLM-Expert 62.9, Test 57.9, Minimal 53.1, Compiler 49.2. Compiler feedback 81.4% HumanEval but 31.2% CoderEval / 34.9% SWE-bench; on SWE-bench subset Mixed (56.4) < Expert (58.4) — long heterogeneous feedback dilutes; gains plateau after 2–3 iterations.*
- **DebugBench** (ACL Findings 2024; arxiv.org/abs/2401.04621) — 4,253 C++/Java/Python bugs; *runtime feedback "not always helpful".*
- **The Fact Selection Problem in LLM Program Repair** (arxiv.org/abs/2404.05520) — 19K prompts, 7 facts. *Non-monotonic: all-facts prompt fixes 12 fewer bugs and 8.2% lower pass@1 than best subset; per-bug selection +17%.*
- **Iterative Feedback Loops** (arxiv.org/abs/2606.17514) — *compile errors fixed 88%, runtime 83%, wrong answers ~35%, TLE ~20%; non-reasoning models plateau after 1–2 rounds.*
- **How Many Tries Does It Take?** (arxiv.org/abs/2604.10508) — *most gain in first two rounds.*
- **Is Three the Magic Number?** (2026; arxiv.org/abs/2607.05197) — *first 3–4 iterations carry nearly all gains; curve shape set more by feedback design than by model.*
- **Compiler-Guided Inference-Time Adaptation (GPT-5 on Idris)** (arxiv.org/abs/2602.11481) — *22/56 → 54/56 with local compiler diagnostics + tests over 20 iterations.*
- **Generative Compilation** (arxiv.org/abs/2607.13921) — rustc feedback on partial programs during decoding. *Compile-error rate 65.9% → 20.7% (post-hoc loop) → 13.1%; error reports shrink 13.8 → 5.5 diagnostics.* Direct evidence that smaller, root-cause-focused diagnostics help.
- **FLARE** (arxiv.org/abs/2606.03852) — line-level suspiciousness added. *50.3 → 54.9 (k=1).* **DebugRepair** (arxiv.org/abs/2604.19305) instrumented runtime states: *Defects4J 224 vs ChatRepair 162.* **ChatRepair** (ISSTA 2024): *162/337 at $0.42/bug.*

## 3. Sanitizer / crash feedback and closed-loop Rust

- **Google AI-powered patching** (2024) — Gemini on sanitizer bugs. *15% of sanitizer bugs fixed.*
- **CodeRover-S / OSS-Fuzz** (ICSE-SEIP 2026; arxiv.org/abs/2411.03346) — executes exploit input to extract fix-relevant code. *61.1% → 71.8% of ARVO vulns.*
- **WilliamT: Fixing 7,400 Bugs for $1 — Crash-Site Repair** (2025; arxiv.org/abs/2505.13103) — regex-distills the ASan report to bug class + last user frame + ±2 lines. *358 ARVO bugs; 47.5% plausible; all 358 for $0.68; pipelined with CodeRover-S: +29.6% fixes at −45.9% tokens.* **Closest existing instance of distilled sanitizer feedback, but no ablation against the full report.**
- **AutoPatchBench** (Meta, 2025) — 136 ARVO C/C++ fuzz crashes; *~60% patches build & stop crash, only 5–11% survive differential testing.*
- **SEC-bench** (NeurIPS 2025; arxiv.org/abs/2506.11791) — real C/C++ vulns with `secb` reproduce-and-sanitize; *SOTA agents ≤18% PoC, ≤34% patching.*
- **DebugHarness** (arxiv.org/abs/2604.03610) — parses sanitizer signature to inject bug-class-specific guidance, LLM drives GDB/rr. *SEC-bench: 89.5% vs SWE-agent 37.5%, at $0.09/vuln. Ablation: GDB-only 82.0%, sanitizer report + static only 77.0%; heap UAF 86.7→70.6%; compiler optimizations corrupt debugger feedback.*
- **TLR** (FSE 2026) — typestate-guided error-propagation trace for C memory errors; outperforms crash-log-only.
- **ChatDBG** (FSE 2025; arxiv.org/abs/2403.16354) — LLM drives gdb/lldb/pdb. *Actionable fixes 91% of C/C++ memory errors.*
- **Crash Report Enhancement** (arxiv.org/abs/2509.13535) — *Top-1 localization 10.6% → 40.2–43.1% by restructuring stack-trace evidence.*
- **Live-kBench** (arxiv.org/abs/2602.02690) — 534 syzbot kernel crashes. *Exposing crash-resolution feedback raises CRR by 25–29%.*
- **C-to-Rust compiler-feedback loops**: SACTOR, SafeTrans, C2SaferRust, Syzygy, SmartC2Rust, EvoC2Rust, ACToR, AdaTrans. **Bosch Feedback Loops** (SANER 2026; arxiv.org/abs/2512.02567) — *first rustc/diff-fuzzing loop up to +24 pp; model differences vanish once feedback is on.* **CRUST-Bench** (arxiv.org/abs/2504.15254) — *3 rounds compiler repair: build 32→69, tests 15→28; adding test failures: tests →37 but build −5 to −20 pp.*

## 4. Feedback minimization / observation compression (2025–2026)

- **The Complexity Trap** (JetBrains; NeurIPS 2025 DL4Code; arxiv.org/abs/2508.21433) — masking halves cost vs raw and matches/exceeds summarization; summaries hid failure signals.
- **ACON** (arxiv.org/abs/2510.00615) −26–54% peak tokens. **AgentFold** (2510.24699). **MEM1** (2506.15841).
- **SWE-Pruner** (2601.16746) 23–54% reduction while improving success. **SWE-Pruner Pro** (2607.18213). **Squeez** (2604.04979) — task-conditioned tool-output pruning benchmark (11,477 examples incl. stack traces/build logs); 0.86 recall at 92% removal; no end-to-end effect.
- **Less Context, Better Agents** (Microsoft; arxiv.org/abs/2606.10209) — GPT-5 on verbose MCP outputs. *Full history 71.0% at 1.48M tokens; last-5 pruning 79.0% at 535K; +summary 91.6% at 553K; stale-state errors 47% → 11%.*
- **ReduceFix** (arxiv.org/abs/2507.15251) delta-debugs failure-inducing inputs. *89.1% input shrinkage; pass@10 +53.8% vs raw tests.*
- **What Makes a Good Bug Report for an AI Agent?** (arxiv.org/abs/2607.07593) — 433 issues × 87 agents. *Longer reports → OR 0.49 per SD; fix suggestion OR 3.61, reproduction script 2.52, file localization 2.33; stack trace OR 0.93 (n.s.); removing localization −29–40 pp.* **How Do LLMs Read Bug Reports?** (2607.25873).

## 5. Determinism / flakiness / evaluation noise

- **On Randomness in Agentic Evals** (2026; arxiv.org/abs/2602.07150) — 60k SWE-bench Verified trajectories. *Single-run pass@1 varies 2.2–6.0 pp; SD >1.5 pp even at temperature 0; ~9 runs to detect a 2 pp effect.*
- **The Replay Gap** (arxiv.org/abs/2608.08239) — *same-model control forks: 6–35% action divergence; FP8 serving diverges >90% vs AWQ near-identical.*
- **UTBoost** (ACL 2025; 2506.09289) — *36 SWE-bench instances with insufficient tests; 40.9%/24.4% leaderboard rank changes.* **SWE-Bench+** (2410.06992).
- **Terminal-Bench 2.0/2.1** — 2.1 repaired 28/89 tasks for dependency drift, resource mismatches.
- Flaky-test LLM work: FlakyDoctor, FlakyGuard ("too little vs too much context"), C++/Rust flakiness studies. **No paper measures how flaky sanitizer/crash output degrades repair agents.**

## 6. Benchmarks usable as C/C++/Rust crash-feedback testbeds

| Benchmark | Lang / size | Crash/sanitizer signal | Notes |
|---|---|---|---|
| ARVO (2408.02153) | C/C++, 5,000+ OSS-Fuzz bugs | ASan reports + PoC + Docker | Ground-truth, reproducible |
| AutoPatchBench (Meta 2025) | C/C++, 136 | stack trace + input | Differential-test oracle |
| SEC-bench (NeurIPS 2025) | C/C++ vulns, 16 CWEs | `secb` sanitizer PoC | DebugHarness 89.5% |
| Live-kBench | Linux kernel, 534 | KASAN crash reports | Self-evolving |
| Defects4C (2510.11059) | C/C++, 248 + 102 fns | tests | Defects4J-style |
| BugsC++ (ASE 2023) | C/C++, 209 bugs | tests | |
| Codeflaws / ManyBugs+IntroClass | C, 3,902 / 1,183 | tests | Older, small |
| ComBench (2603.27333) | C/C++, 200 compile errors | compiler logs | Repo-level |
| Multi-SWE-bench (2504.02605) | C 128, C++ 129, Rust 239 | tests | Claude-3.7: C 8.6%, C++ 14.7%, Rust 15.9% |
| SWE-bench Multilingual | 300; ~42 C/C++, ~43 Rust | tests | C/C++ 28.6%, Rust 58.1% |
| CRUST-Bench, RustEvo² | C→Rust 100; 588 | rustc + tests | Closed-loop rustc |

For memory-safety-crash feedback experiments: ARVO/AutoPatchBench/SEC-bench (reproducible ASan + PoC, cheap re-execution) are the natural substrate; Multi-SWE-bench C/C++/Rust for issue-level realism; CRUST-Bench for rustc loops.

## 7. Established vs. open

**Well supported**
1. Execution feedback beats none by large margins.
2. Returns diminish sharply after 2–4 repair iterations.
3. The *form* of feedback changes outcomes by several to tens of pp at fixed model (SWE-agent ±3–8; RustAssistant 10.7→73.7%; VeriHarness +42–44; PGS; Generative Compilation).
4. More input is not monotonically better (Fact Selection −8.2%; SWE-agent full file −5.3; bug-report length OR 0.49; summaries hiding failure signals). Relevance/structure, not raw length, is the driver.
5. Masking/pruning cuts cost ~50% with no loss — validated mostly on Python SWE-bench.
6. For memory-safety bugs, sanitizer report alone suffices for spatial bugs (stack-BOF) but temporal bugs need dynamic state; crash-site plausibility overstates correctness (60% → 5–11%).
7. Single-run agent evaluations carry 2–6 pp noise; temperature 0 doesn't remove it.

**Open**
1. **No controlled study of raw vs. distilled/structured sanitizer output (ASan/UBSan/MSan/TSan) on both success and token cost**; WilliamT/DebugHarness distillation never ablated against the full report.
2. **No dose–response curve of feedback length/verbosity for compiler or crash output** in agent loops; only verbosity ablation uses HM type errors + 14B model.
3. **"Delta feedback" (what changed between consecutive runs) and test-output compression for C/C++/Rust build/test logs are unstudied.**
4. **No measurement of how nondeterministic crash artifacts (ASLR addresses, thread interleavings, flaky reproduction) confuse repair agents.**
5. Structured vs prose unresolved (VeriHarness: no JSON advantage for equal content; bug-report headers matter 10–30 pp).
6. C/C++/Rust issue resolution <16% on Multi-SWE-bench with no analysis isolating feedback effects; UBSan/MSan/Valgrind-specific feedback essentially unstudied.
7. Few papers report tokens alongside success for feedback variants; most lack cost accounting and multi-run CIs.
