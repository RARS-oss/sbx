# Raw report 02 — Token economics of LLM coding agents: how much is tool output, does compressing it help? (2026-08-22)

Legend — P = primary source fetched; S = secondary; U = unverified (user-reported issue / snippet).

## 1. Token composition of agent trajectories

- **Observation tokens ≈ 84% of an average SWE-agent turn.** "The Complexity Trap" (JetBrains Research, arXiv 2508.21433, Aug 2025; NeurIPS'25 DL4Code): "observation tokens make up around 84% of an average SWE-agent turn" (preliminary, SWE-bench Lite-50). https://arxiv.org/html/2508.21433 — P
- **45.7% (SWE-bench Verified) / up to 67.8% (Terminal-Bench)** of total token consumption are observation tokens — CoACT (arXiv 2607.02911, Jul 3 2026). https://arxiv.org/html/2607.02911 — P
- **"Tool outputs consume over 70% of tokens in multi-turn coding tasks"** — SWE-Pruner Pro (arXiv 2607.18213, Jul 20 2026). https://arxiv.org/html/2607.18213v1 — P
- **31.4% of a live Claude Code context was tool outputs** (15,680 of ~50k tokens at turn 25; system overhead 34.7%, tool inputs 16.6%, thinking 8.4%, CLAUDE.md 4.9%) measured with claude-devtools, Mar 24 2026. https://docs.bswen.com/blog/2026-03-24-claude-code-context-window-token-visualization/ — S (single session)
- **20–30% of token overhead from Bash/Read/Grep/Glob outputs** in a 206-spawn/day multi-agent Claude Code setup; one 50,000-line log re-loaded 10× ≈ 5M tokens (anthropics/claude-code #17611, Jan 12 2026, closed not-planned). — U
- **Single tool call = 580,700 tokens** (`getDiagnostics`, Claude Code #12054, Nov 20 2025); **948,372 tokens from one `rg` call** (openai/codex #16664, Apr 3 2026). — U
- Input vs output: Claude Code docs sample session — 1.2k input / 5.3k output / 940k cache-read / 50k cache-write = $0.55 (cache reads ≈ 94% of tokens). https://code.claude.com/docs/en/costs — P. "How Do AI Agents Spend Your Money?" (arXiv 2604.22750, Apr 2026; OpenHands, 8 models, 500 SWE-bench Verified × 4 runs): agentic coding uses ~3500× the tokens of single-turn reasoning, ~1200× multi-turn chat; growth "primarily driven by exponential growth of input tokens"; cache reads dominate cost; runs on the same task differ up to 30×; accuracy peaks at intermediate spend. — P
- Bouzenia & Pradel (ASE 2025, arXiv 2506.18824): OpenHands mean ~1.2M tokens/trajectory (median 900K) ≈ 52× AutoCodeRover (23K); RepairAgent 220K; in OpenHands, successful trajectories consume *more* input tokens than failures. — P
- Anthropic multi-agent research (Jun 13 2025): agents ≈4× chat tokens, multi-agent ≈15×; token usage explains 80% of BrowseComp variance. https://www.anthropic.com/engineering/multi-agent-research-system — P
- Augment Code (Apr/Jul 2026): "30,400 of 48,400 total tokens came from tool results"; input:output >150:1; Bun Zig→Rust migration: 5.9B uncached input, 690M output, 72B cached reads, ~$165K. — S

## 2. Anthropic's own material (exact figures)

- **Code execution with MCP** (Nov 4 2025): 150,000 → 2,000 tokens, "98.7%" savings; "Every intermediate result must pass through the model". https://www.anthropic.com/engineering/code-execution-with-mcp — P. Third-party replication: 112 GitHub tools, definitions ~150K→~1.2K (99.2%), typical conversation ~80K→~6K (92.5%). https://github.com/orgs/modelcontextprotocol/discussions/629 — S
- **Advanced tool use** (Nov 24 2025): Tool Search Tool "85% reduction"; ~72K tokens for 50+ MCP tools → ~8.7K; accuracy Opus 4 49%→74%, Opus 4.5 79.5%→88.1%. Programmatic Tool Calling: 43,588→27,297 tokens (−37%); docs: 75-tool benchmark −38% billed input tokens, no accuracy change. https://www.anthropic.com/engineering/advanced-tool-use — P
- **Effective context engineering** (Sep 29 2025): "attention budget"; "context rot"; "smallest possible set of high-signal tokens"; "One of the safest lightest touch forms of compaction is tool result clearing"; Claude Code compaction keeps "the five most recently accessed files." https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — P
- **Context management launch** (Sep 29 2025): context editing + memory tool "+39%" on agentic search; editing alone "+29%"; 100-turn web-search eval "reducing token consumption by 84%." API `clear_tool_uses_20250919`: default trigger 100,000 input tokens, keep 3 tool uses; clearing invalidates prompt cache. https://platform.claude.com/docs/en/build-with-claude/context-editing — P
- **Claude Code limits**: Bash inline ~30,000 chars (`BASH_MAX_OUTPUT_LENGTH`, hard ceiling 150,000), beyond → saved to file with short preview; failed results ~10,000 chars head/tail; Glob capped at 100 files; MCP schemas deferred by default; auto-compact at model limit/200K; after compaction "full tool outputs and intermediate reasoning are gone". Docs recommend hooks that filter test output "from tens of thousands of tokens to hundreds" and delegating "verbose operations to subagents"; agent teams ≈7× tokens. https://code.claude.com/docs/en/tools-reference , https://code.claude.com/docs/en/context-window , https://code.claude.com/docs/en/costs — P
- **Cost/plan**: enterprise avg ≈$13/dev/active-day, $150–250/dev/month, 90% under $30/day (2026); 1M context GA (Mar 13 2026): $5/$25 Opus 4.6, $3/$15 Sonnet 4.6, no long-context premium. Opus 4.5 (Nov 2025): matches Sonnet 4.5 SWE-bench "using 76% fewer output tokens". — P
- **Agent SDK** (Sep 29 2025): "Subagents use their own isolated context windows, and only send relevant information back"; "be conscious about how you design your tools to maximize context efficiency." — P

## 3. Long-context degradation / noisy observations

- **Chroma "Context Rot"** (Jul 14 2025, 18 models): focused ~300-token prompts beat full ~113k-token prompts across all models; distractors compound. https://www.trychroma.com/research/context-rot — P
- **NoLiMa** (Feb 2025): 10/12 models at 32K score ≤ half their base. — S. Lost in the Middle (2023); RULER — S
- **LOCA-bench** (Feb 2026, HKUST): Claude 4.5 Opus 96%→14.7% as environment context grows 8K→256K; GPT-5.2 72→21.3%; programmatic tool calling recovers 10+ pp. https://arxiv.org/html/2602.07962v1 — P
- **AgentNoiseBench** (Feb 2026): tool noise ≈20pp degradation; agents "significantly more sensitive to tool noise than to user noise." https://arxiv.org/html/2602.11348 — P
- **Lost in the Noise** (Jan 2026): up to 80% drop with distractors; "agentic workflows often amplify these errors by over-trusting noisy tool outputs". https://arxiv.org/abs/2601.07226 — P
- **SWE-agent** (2024) ablation: last-5-observations 18.0% vs full history 15.0%; file viewer 100 lines 18.0% vs full file 12.7% vs 30 lines 14.3% — "feedback should be informative but concise." — P
- Complexity Trap: LLM summarization lengthens trajectories 13–15% by "obscuring natural stopping signals." — P

## 4. Cost per task / spend pain

- **Artificial Analysis Coding Agent Index v1.4** (2026): Claude Code (Opus 5 xhigh) $8.17/task, 21.6M tokens/task, 23.7 min, 97% cache hit; Codex (GPT-5.6 Sol max) $6.42, 13.2M tokens, 10.2 min, 90% cache hit. https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-codex — P
- **mini-SWE-agent** (swebench.com, Aug 2025): $3 budget/instance; GPT-5-mini $0.12/instance; returns marginal past ~50 steps. — P. Complexity Trap raw-agent cost/instance: Qwen3-32B $1.12, Qwen3-Coder-480B $1.29, Gemini 2.5 Flash $0.41 — P
- **Long-Horizon-Terminal-Bench** (Aug 2026, 15 models): avg 9.66M tokens, $10.21, 85 min per task. https://arxiv.org/html/2607.08964v1 — P
- **Aider polyglot**: GPT-5 high 88.0% at $29.08/run; o3-pro $146.32; Claude Opus 4 72.0% at $65.75. — S
- **Weekly limits** (announced Jul 28, live Aug 28 2025): Pro 40–80 h Sonnet/wk; Max $200 240–480 h + 24–40 h Opus; "<5% of users" affected; reason: users running Claude Code "continuously around the clock". — S
- Developer reports: 59KB output (~15k tokens) re-sent over 50 turns = 750k input tokens (mksg.lu, Apr 2026) — S/U. Codex users: oversized outputs "drain 5h quota disproportionately" (#16664) — U

## 5. Context-management research & production truncation rules

| Method (date) | Target | Token/cost effect | Success effect | Source |
|---|---|---|---|---|
| Observation masking, M=10 (JetBrains, Aug 2025; 500 SWE-bench Verified) | old observations | cost −50.9% (Qwen3-32B), −52.7% (Qwen3-Coder-480B), −56–57% (Gemini 2.5 Flash) | masking ≥ LLM-summary in 4/5 settings; hybrid +2.6pp | P arxiv 2508.21433 |
| OpenHands LLMSummarizingCondenser (Apr 2025) | whole history | up to 2× per-turn cost reduction | 54% vs 53% | P |
| AgentDiet (Sep 2025, FSE'26) | useless/redundant trajectory info | input tokens −39.9–59.7%, cost −21.1–35.9% | unchanged | P arxiv 2509.23586 |
| ACON (Oct 2025, ICML'26) | observations + history | peak tokens −26–54% | small LMs up to +46% | P arxiv 2510.00615 |
| SWE-Pruner 0.6B skimmer (Jan 2026) | tool-output lines | −23–54% | 64% vs 62% | P arxiv 2601.16746 |
| SWE-Pruner Pro (Jul 2026) | tool outputs (>70% of tokens) | up to −39%; +15% wall-time | +3.8pp | P |
| CoACT (Jul 2026) | observations, next-action-preserving | −33% avg | +3.5/−1.5/+4.0pp; LLMLingua-2 57→50% | P |
| Squeez 2B (Apr 2026) | single tool observation → evidence block | removes 92% of input tokens, recall 0.86 | end-task effect not measured | P arxiv 2604.04979 |
| Minification (May 2026, TU Wien) | code context | −42% | **−12pp** — negative result | P arxiv 2606.01326 |
| Focus/Active Context Compression (Jan 2026) | raw history → knowledge block | −22.7% | 3/5 = baseline | P |
| Cursor Composer self-summarization (Mar 2026) | >100k → ~1k summary | 1/5 tokens | compaction errors −50% | P |
| Cursor dynamic context discovery | long tool outputs → files | MCP tokens −46.9% | — | S |

Production truncation defaults: Claude Code Bash 30,000 chars (middle-truncate/file); Codex CLI `TruncationPolicy::Bytes(10_000)` / 256 lines head+tail, `tool_output_token_limit` since 0.59.0-alpha.15 (Nov 2025); mini-SWE-agent: output >10,000 chars → first 5,000 + last 5,000; SWE-agent: last-5 observations; Anthropic API: clear tool uses at 100k, keep 3; Cognition (Jun 2025): compress history with fine-tuned model, "hard to get right"; Parallel Context Compaction (May 2026): summarization stalls tens of seconds.

## HARD NUMBERS (consolidated)

- Observation/tool-output share: 84%/turn (SWE-agent, Lite-50); 45.7% SWE-bench V, 67.8% Terminal-Bench (CoACT); ">70%" (SWE-Pruner Pro); 31.4% of a Claude Code context; 20–30% overhead (user report); 30.4k/48.4k (Augment).
- Tool-definition bloat: 150K→2K (98.7%); 72K→8.7K (85%); 46.9% (Cursor MCP).
- Compression → tokens: −50–57% (masking), −40–60% input (AgentDiet), −26–54% peak (ACON), −23–54% (SWE-Pruner), −33% (CoACT), −37/−38% (PTC), −84% (context editing, 100 turns), −42% (minification), 92% per-observation (Squeez).
- Compression → success: +1 to +5pp (masking vs summary), +2.6pp hybrid, +2pp (SWE-Pruner), +3.8pp (Pruner Pro), +3.5/−1.5/+4.0pp (CoACT), −12pp (minification), 0 (AgentDiet, Focus), summary trajectories +13–15% turns.
- Degradation: 96→14.7% (8K→256K, LOCA); ~20pp tool noise; full history −3pp, full file −5.3pp (SWE-agent).
- Cost/task: $8.17 (Claude Code, 21.6M tok) vs $6.42 (Codex, 13.2M tok); $10.21 & 9.66M tokens (LH-Terminal-Bench); $0.41–1.29 raw mini-SWE-agent; $13/dev/day; single tool calls of 580k and 948k tokens.

## What remains UNKNOWN / unmeasured

1. No standardized measurement of tool-output share (31%→84% depending on counting method); no breakdown per tool type (test logs vs file reads vs grep vs build logs).
2. **Structuring vs. masking/pruning**: nearly all evidence is for dropping/masking/pruning lines; no controlled study of *semantically structured* outputs (test logs → failure records, stack traces → frames) measuring tokens AND resolve rate.
3. Cache-aware cost: reductions in tokens ≠ proportional cost savings when 90–97% of tokens are cache reads at ~10% price and clearing invalidates cache prefixes.
4. Model dependence & negative results: lossy compression can hurt (CoACT −1.5pp, minification −12pp, LLMLingua-2 −7pp); no frontier-model replication of masking-vs-summary.
5. Truncation-induced errors: agents acting on silently truncated outputs never quantified on benchmarks.
6. Terminal-Bench/long-horizon: observation share highest (67.8%) yet context-management evals almost all SWE-bench.
7. Interaction with trajectory length: whether compressed/structured outputs change step count or timeout rates (79% of LH-Terminal-Bench failures) is unmeasured.
