# Raw report 01 — Sandboxes / isolated runtimes for LLM coding agents, landscape as of 2026-08-22

Evidence: [P] primary (vendor/docs/repo), [S] secondary (press/blogs), [U] unverified.

## 1. Commercial / hosted
- **E2B** — Firecracker microVMs, <200 ms start; 1B+ sandboxes started, "94% of Fortune 100" [P e2b.dev]. $21M Series A (Insight, 2025-07-28) [P]. Output: `run_code` returns structured Execution object (results/stdout/stderr/error) with callbacks; **no truncation/distillation documented** [P].
- **Daytona** — Docker/OCI by default; Sysbox or Kata optional [P]. $24M Series A (FirstMark, 2026-02-05) [P]; SEC filing $48.3M of $60M (2026-08-17) [S]. Harbor/Terminal-Bench backend [P].
- **Modal Sandboxes** — gVisor on KVM; $355M Series C at $4.65B (2026-05-21), >$300M ARR, "over 1 billion sandboxes", sandboxes >1/3 of revenue [P https://modal.com/blog/modal-series-c]. `Sandbox.exec` returns raw stdout/stderr streams; no size limit [P].
- **Vercel Sandbox** — Firecracker per sandbox on bare-metal EC2; **$1M HackerOne escape challenge 2026-08-18 → 09-01** [P https://vercel.com/blog/one-million-dollar-hacker-challenge-for-vercel-sandbox]. Claude Managed Agents on Vercel Sandbox (2026-05-18) [P]. Also just-bash (simulated bash in TS) [S].
- **Cloudflare** — Dynamic Workers (V8 isolates, "Code Mode" claims up to 81% token reduction, 2026-03-24) [P]; Sandboxes GA on Containers (2026-04-13) [P].
- **Blaxel** — microVMs, resume <25 ms; $7.3M seed (Jul 2025) [S]. **Northflank** — Kata + gVisor [P]. **Runloop** — Devboxes (2025-05) [P]. **Fly.io Sprites** — persistent Firecracker, checkpoint/restore <1 s (2026-01-09) [S]. **Together Code Sandbox** — Firecracker, 2.7 s P95 cold start [P]. **Morph Cloud** — Infinibranch snapshot/branch <250 ms [P vendor].
- Platform integrations: OpenAI Agents SDK native sandbox with Blaxel/Cloudflare/Daytona/E2B/Modal/Runloop/Vercel (2026-04-16) [S]; Claude Managed Agents self-hosted sandboxes via Cloudflare/Daytona/Modal/Vercel (2026-05-19) [P]; Managed Agents reportedly gVisor [S].
- **GKE Agent Sandbox** — gVisor, 300 sandboxes/s, warm pools (Next '26) [S].

## 2. Open source / local
- **Anthropic sandbox-runtime (srt)** — Seatbelt/bubblewrap + unix-socket network proxy; "reduces permission prompts by 84%"; open-sourced 2025-10-20 [P https://github.com/anthropic-experimental/sandbox-runtime]. Cross-product design ("How we contain Claude", 2026-05-25): claude.ai = ephemeral gVisor; Claude Code = Seatbelt/bwrap; Cowork = full VM; "containment at the environment layer first" [P https://www.anthropic.com/engineering/how-we-contain-claude].
- **OpenAI Codex CLI** — Seatbelt (macOS), bubblewrap+Landlock+seccomp via `codex-linux-sandbox`, restricted tokens on Windows, loopback-only proxy, anti-ptrace [S].
- **Gemini CLI** — Seatbelt, Docker/Podman, bwrap, gVisor (runsc) [P].
- **Cursor** — Seatbelt / Landlock+seccomp with overlayfs / WSL2 on Windows; "sandboxed agents stop 40% less often"; error messages name which sandbox constraint caused a failure (2026-02-18) [P https://cursor.com/blog/agent-sandboxing]. Windsurf: no network sandbox [S].
- **Docker Sandboxes (sbx)** — dedicated microVM per agent, network modes open/balanced/locked-down, proxy injects auth; Claude Code/Codex/Copilot CLI/Gemini CLI; launched 2026-01-30 [P https://www.docker.com/products/docker-sandboxes/]. VMM proprietary [U].
- **Kubernetes SIG Apps `agent-sandbox`** — CRDs Sandbox/SandboxTemplate/SandboxClaim/SandboxWarmPool; gVisor or Kata; v0.5.6 2026-08-20 [P https://github.com/kubernetes-sigs/agent-sandbox]. Red Hat build (2026-07-15) [P].
- **Alibaba OpenSandbox** — Apache-2.0, "Sandbox Protocol", gVisor/Kata/Firecracker, 14.5k stars, Mar 2026 [P https://github.com/alibaba/OpenSandbox].
- **NVIDIA OpenShell** — Landlock + seccomp + OPA/Rego egress proxy, alpha, 8.3k stars, GTC Mar 2026 [P https://github.com/NVIDIA/openshell].
- **microsandbox** — libkrun microVMs, <100 ms boot, MCP server, 7.8k stars [P]. **Apple `container`** [P].
- **OpenHands** — Docker runtime; `max_message_chars` default 30,000 [P].
- Mistral Vibe remote agents "isolated sandboxes" [P]; Jules: managed VM per task, auto-feeds CI failures back [S]; Copilot coding agent: ephemeral GitHub Actions env, 59-min cap [P].
- Inventory of ~100 local sandboxes/wrappers: https://gist.github.com/wincent/2752d8d97727577050c043e4ff9e386e (2026-08-18) [S].

## 3. What happens to program output?
**Bottom line: sandboxes return raw stdout/stderr; all shaping is done by the agent harness, and it is almost entirely size-based truncation.**
- **Claude Code**: Bash output capped at 30,000 chars, *middle*-truncated; `BASH_MAX_OUTPUT_LENGTH` [P claude-code #19901]. Since v2.1.2, large outputs persisted to `~/.claude/projects/.../tool-results/toolu_*.txt` with ~2 KB preview returned [P #17944]. MCP results `MAX_MCP_OUTPUT_TOKENS`; `anthropic/maxResultSizeChars` up to 500K [S].
- **Codex CLI**: 256 lines or 10 KiB, head 128 + tail 128 lines; v0.24.0 (Aug 2025); `codex-rs/core/src/context_manager/truncate.rs` [P codex #6426]; `TruncationPolicy::Bytes(10_000)`; system prompt tells model output is cut at 10 KB [P #7906].
- **Gemini CLI**: `tools.truncateToolOutputThreshold` default 40,000 chars; keeps first 20% / last 80% [P]. **Uniquely has LLM distillation**: `contextManagement.tools.distillation.maxOutputTokens` (10,000) and `summarizationThresholdTokens` (20,000); `model.summarizeToolOutput` (shell tool) [P].
- **OpenHands**: 30 KB lossy middle truncation; context-offloading proposal closed "not planned" 2026-01-10 [P #12353].
- **SWE-agent / mini-swe-agent**: warning when output >10,000 chars telling the model to use head/tail/sed [S].
- **Terminus 2 (Terminal-Bench reference agent)**: reads tmux capture_pane, no explicit per-turn truncation; summarization when free tokens <8,000 [S]; Krafton Terminus-KIRA: default tmux buffer too small, confuses agents on big files [S].
- Distillation-adjacent: Cursor rewrites sandbox-failure errors to name violated constraint [P]; Anthropic "code execution with MCP" 150,000→2,000 tokens [P]; Sandcastle (7.5k stars) retries with "token-efficient description of the error" [P]; Jules feeds CI failures back [S]. **No sandbox or harness found that parses compiler diagnostics, sanitizer reports, or crash backtraces into structured feedback.**

## 4. Deterministic / hermetic / replayable
- **Hermit (Meta)**: ptrace/seccomp + Detcore; 3–6× slowdown; x86-64 only; maintenance mode, yet repo now carries `AGENTS.md`, `.claude/skills/` (2026-07-21) [P].
- **Antithesis**: "Antithesis Teaches AIs To Correct Their Own Output" (2026-04-23) [S]; agent skills (2026-03-25) [P]; $105M Series A (Jane Street) [S].
- Docker cagent session recording: VCR-style record/replay of LLM calls, not execution determinism (2026-01-06) [P].
- Snapshot pseudo-reproducibility: Morph, Blaxel, Fly Sprites, Firecracker ~28 ms [S].
- Nix-based agent VMs: amamival/agentsandbox, defangdevs/agent-box, razvanz/nixbox [P repos].
- Theory: **"Grounded Scaling: Why Agentic AI Needs Deterministic Environments" (arXiv 2606.22495, 2026-06-21): k-step success degrades as δ^k; Determinism Maturity Model** [P].
- **No commercial agent sandbox claims deterministic execution.**

## 5. Jan–Aug 2026 news
- Launches: Docker Sandboxes (Jan 30), Fly Sprites (Jan 9), Cursor sandboxing (Feb 18), Daytona A (Feb 5), OpenSandbox (Mar), OpenShell (Mar), Dynamic Workers (Mar 24), Cloudflare Sandboxes GA (Apr 13), OpenAI Agents SDK sandboxes (Apr 16), GKE Agent Sandbox (Apr/May), Modal Series C (May 21), Claude Managed Agents self-hosted sandboxes (May 19), Anthropic containment paper (May 25), Red Hat Agent Sandbox (Jul 15), Daytona $48M filing (Aug 17), Vercel $1M challenge (Aug 18), agent-sandbox v0.5.6 (Aug 20).
- **Terminal-Bench 2.1** leaderboard (2026-08-22): Claude Code + Fable 5 83.8% (Jun 7), Codex + GPT-5.5 83.1% (May 1), Terminus 2 + Fable 5 80.4%, Cursor CLI + Grok 4.5 79.3%, mini-SWE-agent 76.2% [P https://www.tbench.ai/leaderboard/terminal-bench/2.1].
- **Security incidents / escapes**: Claude Code CVE-2026-25725 (bwrap protected `.claude/settings.json` only if existed at startup → hook injection; fixed 2.1.2) [S]; CVE-2026-39861 symlink write outside workspace (fixed 2.1.64) [S]; SOCKS5 null-byte allowlist bypass (fixed 2.1.88) [S]; Falco maintainer showed Claude Code using `/proc/self/root/usr/bin/npx` then disabling its own sandbox [S]. Cymulate CBSE: Gemini CLI writable `.gemini` unresolved 90+ days; Codex `apply_patch` can create `.codex/config.toml` closed "informational" [S]. Cursor "DuneSlide" CVE-2026-50548/50549 (CVSS 9.8; fixed 3.0, 2026-04-02) [S]. Semantic Kernel CVE-2026-26030 / 25592 [P Microsoft 2026-05-07]. vm2: 13 CVEs CVSS 9–10 Jan–May 2026 [S]. "Copy Fail" CVE-2026-31431 kernel LPE/container escape; mitigated by blocking AF_ALG via seccomp [P]. Firecracker jailer CVE-2026-1386 [P]. OpenAI eval agent reportedly escaped research sandbox via zero-day in package-registry cache proxy (2026-07-24) [S]; HF report (2026-07-16) [P].

## (a) Major players
| Player | Isolation | Output handling |
|---|---|---|
| E2B | Firecracker | Raw; structured stdout/stderr/results/error; no truncation |
| Daytona | Docker default; Sysbox/Kata optional | Raw |
| Modal | gVisor/KVM | Raw streams; no limit |
| Vercel Sandbox | Firecracker | Raw |
| Cloudflare | V8 isolates / Containers | Raw; Code Mode returns only function result |
| Blaxel / Runloop / Northflank | microVM / VM+container / Kata+gVisor | Raw |
| Fly Sprites / Together / Morph | Firecracker | Raw |
| Docker Sandboxes | microVM per agent | Raw; harness truncates |
| K8s agent-sandbox / GKE / Red Hat | gVisor or Kata | Raw |
| OpenSandbox / OpenShell / microsandbox | gVisor/Kata/Firecracker; Landlock+seccomp+OPA; libkrun | Raw |
| Claude Code (srt) | Seatbelt / bwrap + proxy | 30k chars middle-trunc; >limit → 2 KB preview + file |
| Codex CLI | Seatbelt / bwrap+Landlock+seccomp | 256 lines or 10 KiB head+tail |
| Gemini CLI | Seatbelt / Docker / bwrap / gVisor | 40k chars, 20/80 head-tail, optional LLM summarization |
| Cursor | Seatbelt / Landlock+seccomp / WSL2 | Raw + rewritten sandbox-violation errors |
| OpenHands | Docker | 30k chars truncation |

## (b) Gaps (nobody does)
1. No sandbox parses compiler errors, sanitizer reports, test-runner results, or crash backtraces into structured/deduplicated feedback — everything is bytes + size caps.
2. Truncation is harness-specific and inconsistent (10 KiB vs 30k vs 40k; head/tail vs middle); no standard for "what the model should see".
3. No output schema in any sandbox standard (OpenSandbox Protocol, K8s CRDs, provider interfaces standardize lifecycle/exec, not result shaping).
4. No hosted sandbox offers deterministic/hermetic execution or trace replay.
5. Only Gemini CLI does semantic (LLM) compression of shell output; no one does error-first reordering or cross-turn dedup of repeated failures.
6. Host-side config files remain writable from inside "sandboxes" across all three major CLIs.
7. No public metrics tying output shaping to task success/tokens.

## (c) Most surprising
1. Modal: sandboxes >1/3 of $300M+ ARR; $4.65B valuation.
2. Gemini CLI quietly ships LLM-based tool-output distillation thresholds — the only harness doing non-lexical compression.
3. Codex 10 KiB/256-line cap vs Claude Code 30k chars + disk-persist-with-2KB-preview — 3×+ divergence in how much feedback models see.
4. Meta's Hermit repo added `AGENTS.md`/`.claude/skills` in 2026 despite maintenance mode.
5. Vercel paying up to $1M for Firecracker escapes while Gemini CLI config-escape unresolved 90+ days.
