# Raw report 06 — Prior-art / novelty check: "hermetic Rust sandbox returning distilled, delta'd machine feedback to coding agents" (2026-08-22)

Evidence: P = primary (source/docs/paper), S = secondary, SR = self-reported by vendor.

## 1. Token-saving output filters for agents (the crowded part)

| Tool | What | Claims | Adoption / dates | Notes |
|---|---|---|---|---|
| **RTK – Rust Token Killer** (github.com/rtk-ai/rtk) | Rust CLI proxy; Claude Code `PreToolUse` hook rewrites `cargo test`, `pytest`, `go test`, `tsc`, `git`, `kubectl`… into `rtk <cmd>` which filters/compresses output. Parses JSON where available. | "60–90% less bash output"; 89.2% over 2,927 commands (SR, tokens≈bytes/4). No delta feature. | Created 2026-01-22; Show HN 2026-01-23; **76,959 stars, 4,837 forks** as of 2026-08-21 (P). Apache-2.0. | **Independent benchmark (JetBrains, Jul 2026):** SkillsBench (86 tasks, 425 trials, Claude Code 2.1.201, rtk v0.43): **+7.6% cost at low effort (p=0.004), flat at high effort, +13.8% turns**; hook touches only ~20% of tool-result bytes since Read/Grep bypass it. https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/ |
| **token-optimizer** (alexgreensh) | Python hooks: re-read file → only diff; code → skeleton; CLI output → compressed. | — | 1,939 stars, 2026-02-26 | Delta for file re-reads, not diagnostics. |
| **Context Gateway** (Compresr-ai) | Go API proxy; LLM-based background compaction. | — | 633 stars, 2026-02-10 | |
| **squeez** (claudioemmanuel) | Rust; hooks for Claude Code/Copilot/OpenCode/Gemini CLI/Codex; `PostToolUse updatedToolOutput`; cross-call dedup (FNV-1a + MinHash, 16-call window); reversible via MCP. | 91.2% (SR) | 187 stars, 2026-03-23 | Closest to a "delta": dedups repeated outputs. |
| **token-saver** (ppgranger) | Python, 36 format-aware processors (pytest, cargo, go, jest, eslint, ruff, clippy, mypy, tsc…). | pytest 95%, ruff 87% (SR). No deltas. | 138 stars, 2026-02-17 | |
| chop (Go), ecotokens (Rust), ctx-diet ("65.6% over 91,287 commands"), lm-resizer, hush, lakonai, caveman* | Same idea, smaller. | SR | Feb–Jul 2026 | **Market saturated at "regex-compress stdout" level.** |
| **Headroom** (API proxy) | Black-box context compression. | — | Independent A/B: savings came from `ENABLE_TOOL_SEARCH`, not proxy (S); arXiv 2607.12161 measured **+48.4% billed cost** (P). | |
| **build-output-tools-mcp** (jgordley) | MCP server runs pytest/npm, sends raw log to cheap LLM, returns JSON summary. | 3,017→458 tokens (SR) | 6 stars, Jul 2025 | LLM-summarization variant. |
| **pytest-receptor** (uibcdf) | pytest reporter for agents: one-line verdict, **failures grouped by root cause**. | 3,300→105 tokens (SR) | 0 stars, Jul 2026 | Python-only; no deltas. |
| No hits for: "cargo llm", "slimjson", jest/vitest reporters "for AI agents". `r3bl-rust-analyzer-mcp-server` (crates.io Aug 2026) exposes rust-analyzer diagnostics via MCP. |

**Key independent finding:** *Token Reduction Is Not Cost Reduction* (Weinberger & Hozez, arXiv 2607.12161, Jul–Aug 2026, P): 2,908 Claude Code runs, 103 tasks, 3 models; RTK v0.44.1 −1.3% tool-output tokens / −2.7% cost; RTK-ML −38.4% tokens / **+6.8% cost**, more turns; Headroom +48.4% cost; **Pearson r(token reduction, cost) = 0.15**; aggressive compression reduced patch-application success on SWE-bench Go. Cause: prompt-cache economics and behavioral change (extra retrieval/diagnosis turns).

## 2. How mainstream harnesses handle tool output (source-level)

| Harness | Limit / strategy | Source |
|---|---|---|
| **Claude Code** | Bash inline ~30,000 chars (`BASH_MAX_OUTPUT_LENGTH`, max 150,000); beyond → **full output saved to file (64 MiB cap) + short head preview + path**; failed commands ~10,000 chars head+tail. `PostToolUse` hooks can replace results via `updatedToolOutput`; `PreToolUse updatedInput` can rewrite command. Docs cost page recommends PreToolUse hook grepping test output for failures. | code.claude.com/docs/en/tools-reference, hooks, costs (P); issues #19901, #40100, #12054 |
| **Codex CLI** | `codex-rs/core/src/context_manager/truncate.rs`: **256 lines or 10 KiB, head 128 + tail 128** (v0.24, Aug 2025); `TruncationPolicy::Bytes(10_000)`. Asks: token-based limits #6426, auto-spill #14206. Sandbox: bubblewrap (`--ro-bind / /`, `--unshare-user/pid/net`, seccomp net filter), Landlock fallback; Seatbelt macOS. | PR #6476, #7906, linux-sandbox/README (P) |
| **OpenHands** | `max_message_chars` 30,000 per observation; LLM condenser. | docs, PR #4788 (P) |
| **SWE-agent** | ACI: observations older than last 5 collapsed; search capped; file viewer windows. | arXiv 2405.15793 (P) |
| **mini-SWE-agent** | >10,000 chars → first 5,000 + "[n chars elided]" + last 5,000; `max_observation_length` 100,000. #8 on TB 2.1 (76.2%). | swebench.yaml (P) |
| **Terminus 2** (TB reference; #3 on TB 2.1) | `max_bytes = 10000`, first/last half; tmux 160×40; summarization when free tokens < 8,000. | harbor/agents/terminus_2 (P) |
| **Gemini CLI** | `tools.truncateToolOutputThreshold` 40,000 chars; 20%/80%; `contextManagement.tools.distillation.maxOutputTokens` 10,000, `summarizationThresholdTokens` 20,000 → **LLM summarization of shell output**. | config ref (P) |
| **Roo Code** | 500 lines default, 20/80 head/tail. Cline: requested #4002. | Roo docs (P) |
| **Cursor** | ~20k command-result limit; staff: "long terminal output confuses agents… consume much more tokens". | forum Jan 2026 (S) |
| **Aider** | `--test-cmd` feeds failing output; lint errors with tree-sitter function context. | aider docs (P) |
| Copilot / Devin / Droid / Amp / Warp | closed; no primary source. | — |
| TB 2.0 top (Aug 2026): NexAU-AHE 84.7%, LemonHarness, Capy, Codex CLI 82.2%, Droid 77.3%. TB 2.1: Claude Code 83.8%, Codex 83.1%, Terminus 2 80.4%, mini-SWE-agent 76.2%. StateM (arXiv 2608.15089) 95.3% via "harness scaling". | tbench.ai (P) |

**Takeaway: every open harness uses byte/line head-tail truncation; Gemini CLI adds LLM summarization; Claude Code spills to file. None parses diagnostics or emits deltas natively.**

## 3. Structured compiler/test feedback wired into LLM loops
- Machine formats mature: `gcc -fdiagnostics-format=sarif-stderr|json`, `clang -fdiagnostics-format=sarif`, `cargo --message-format=json`, pytest `--tb=short/line -q`, `pytest-json-report`, `ctest --output-on-failure`, `errorformat`/`reviewdog`, `sarif-rs`. **No project found that converts SARIF/errorformat into agent prompts.**
- Structured diagnostics to agents: Claude Code code-intelligence plugins (LSP type errors after edits); `r3bl-rust-analyzer-mcp-server`; aider tree-sitter lint context; bachelor thesis on LSP feedback (youni20/code-translation-engine).
- Sanitizer/backtrace: **CodeRover-S** (arXiv 2411.03346) feeds ASan/UBSan bug type + stack trace, fixes 52.4% of 588; **DebugHarness** (arXiv 2604.03610) on SEC-bench: "LLM is utilized to distill these raw logs into concise feedback", 89.5% at $0.09/vuln; AgenticRepair (2607.29422). **All use an LLM to distill, none a deterministic parser + delta.**

## 4. Academic / industry prior art on observation compression (2025–26)
| Work | Venue/date | Result | Covers |
|---|---|---|---|
| **The Complexity Trap** (JetBrains) | DL4Code @ NeurIPS 2025; 2508.21433 | Observation tokens ≈84%/turn; masking cuts cost 50–57%, ≥ LLM summarization | where tokens go; no per-tool parsing |
| **AgentDiet** | **FSE 2026**; 2509.23586 | LLM removal of useless/redundant/expired info: −39.9–59.7% input tokens, steps 57.2→43.9 | partial "delta" via LLM |
| **CoACT** | 2607.02911, Jul 2026 | trained compressor "next-action preservation"; −33%; with AgentDiet $45.65→$25.88 | learned compression |
| **SWE-Pruner / Pro** | 2601.16746 / 2607.18213 | −23–54%, +success | learned pruning |
| **TACO** (self-evolving terminal observation compression) | 2604.19572, Apr 2026 | discovers compression *rules* from trajectories; +1–4% TB1/2; also CompileBench | closest to rule-based terminal distillation, LLM-discovered rules |
| CAT 2512.22087; ACON 2510.00615; AgentFold 2510.24699; Context-Folding 2510.11967; masking regime map 2606.00408 | arXiv | history compression | not tool-specific |
| **Token Reduction Is Not Cost Reduction** 2607.12161; JetBrains RTK benchmark | arXiv/blog | compression can raise cost; must measure billed cost, turns, cache | **evaluation bar** |
| Is Three the Magic Number? 2607.05197; Iterative Feedback Loops 2606.17514 | arXiv | first 3–4 iterations give most gains; feedback design > model | iteration metric |
| HARBOR (harness BO, 2604.20938); agent-harness survey 2606.20683 | arXiv | harness as first-class object | framing |
| **AgentCgroup** (2602.09345, cs.OS) | arXiv 2026 | eBPF cgroups aligned to tool-call boundaries; OS execution 55–60% of latency; 15.4× memory spikes | sandbox/resource side; sibling work |
| Sandboxes: Claude Code srt, Codex bwrap, nono (Rust, 3.8k★), hakoniwa (Rust, ns+cgroups+landlock+seccomp, 78★), fence (926★), greywall, microsandbox, OpenShell | — | mature; none shapes output | |

## 5. Demand signals
- Weekly limits 2025-07-28 (HN 609 pts); Register 2026-01-05 (limits in 10–15 min); **Register 2026-03-31: Anthropic admits users hit limits "way faster than expected"; cache bugs inflating cost 10–20×** (HN 331 pts).
- Anthropic docs: ≈$13/dev/active day; tells users to hook-filter test output.
- Observations ≈84% of SWE-agent turn tokens; one Claude Code diagnostics call ≈580k tokens; Cursor staff: long output "confuses agents".
- ≥15 output-compressor repos Jan–Jul 2026; RTK 77k stars in 7 months. **Demand is real but the naive fix is commoditized, and two independent studies show it may not save money.**

## 6. Venues & framing
DL4Code (5th ed. @ ICML 2026; Complexity Trap was a Master's thesis); FSE 2026 (AgentDiet); ICSE/ASE NIER; ISSTA; NeurIPS/ICLR agent workshops; arXiv-first with HN traction. Systems venues (OSDI/SOSP/EuroSys workshops, cs.OS) for AgentCgroup-style work. Traction requires **rigorous cost-not-tokens evaluation**.

## NOVELTY MATRIX (● covered, ◐ partial, ○ not)
| Component | RTK/token-saver/squeez | Claude Code/Codex/Gemini/Terminus 2 | Complexity Trap/AgentDiet/CoACT/SWE-Pruner/TACO | DebugHarness/CodeRover-S | pytest-receptor/build-output-mcp | Sandboxes (nono, hakoniwa, Codex bwrap, AgentCgroup) |
|---|---|---|---|---|---|---|
| Hermetic sandbox in Rust | ○ | ◐ | ○ | ○ | ○ | ● (hermetic/deterministic profile ○) |
| Deterministic profile | ○ | ○ | ○ | ○ | ○ | ◐ |
| Compiler-diagnostic parsing | ◐ | ◐ (LSP) | ○ | ○ | ○ | ○ |
| Sanitizer/backtrace distillation | ○ | ○ | ○ | ◐ (LLM-distilled) | ○ | ○ |
| Minimal failing-test info | ◐ | ○ | ○ | ○ | ● (pytest only) | ○ |
| **Delta vs previous run** | ◐ (dedup) | ○ | ◐ (LLM "expired") | ○ | ○ | ○ |
| Token + iteration + billed-cost measurement | ○ (SR, refuted) | ○ | ● | ◐ | ○ | ○ |
| Harness integration | ● | ● | ● | ◐ | ◐ | ● |

## Verdict
**Genuinely new:** (1) deterministic, typed feedback contract — parsed diagnostics + sanitizer/crash objects + test root-causes — emitted by the executor itself rather than post-hoc regex or LLM; (2) **diagnostic-level deltas** ("2 errors fixed, 1 new, 3 unchanged; crash moved from X to Y") — no tool or paper does this; (3) coupling distillation with a hermetic/deterministic profile so deltas are meaningful — nobody has argued determinism is a *prerequisite for compressible feedback*; (4) evaluation on C/C++/Rust with sanitizers.

**Engineering integration, not novelty:** the Rust sandbox itself (hakoniwa, nono, Codex bwrap), stdout filtering for pytest/cargo/go (RTK + 15 clones), LLM summarization of build logs, observation masking, hooks plumbing.

**Skeptical reviewer:** "RTK has 77k stars and two independent studies show it doesn't cut cost — why is yours different?" (answer: measure billed cost, turns, cache reads, success; show deltas reduce *turns*). "Masking already gets 50% for free." "Claude Code already spills to file and models can grep it." "Deltas lose information; show failure cases." "Determinism claims need a real definition and measured flakiness reduction." "Is this just TACO's rules hand-written?" "Evaluate a frontier harness, not only mini-swe-agent."

**Three strongest framings:**
1. **"Feedback as a typed API, not a byte stream"** — ACI for compilation/runtime feedback; metric: turns-to-solve and billed cost on C/C++/Rust tasks with sanitizers (SEC-bench, CompileBench, TB-2 subset), baselines masking + RTK. Venue: FSE/ICSE/ASE or DL4Code.
2. **"Deltas need determinism"** — systems framing: hermetic executor makes run-to-run diffs sound, enabling delta feedback and reproducible evals; report flakiness reduction + token/turn savings. Venue: EuroSys/SOSP workshop, cs.OS + cs.SE.
3. **"Token reduction ≠ cost reduction — what actually does?"** — empirical study contrasting byte-level compressors, LLM summarization, masking, structured+delta feedback across cache regimes. Venue: arXiv + DL4Code/ICLR agents workshop; best HN traction chance.
