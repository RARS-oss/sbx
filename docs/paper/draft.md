# Facts, not bytes: typed, delta-aware execution feedback for coding agents under a hermetic executor

*Working draft v0.1 — 2026-08-22. Sections 1–4 are drafted; §5 holds the pilot slots. Numbers in
§1–2 are from the cited sources (see `../../research/raw/` for URLs and evidence grades).*

## Abstract

Tool output dominates the token budget of LLM coding agents — 45–84 % of input tokens in
SWE-agent, Terminal-Bench and Claude Code traces — yet every deployed harness shapes it the same
way, by byte or line truncation, and byte-level compressors have been shown in two independent
studies not to reduce billed cost. We argue that the executor, not a post-hoc filter, should own
the feedback: it already knows the exit status, the signal, the sanitizer report and the test
runner's summary. We present **sbx**, an unprivileged hermetic sandbox (user/pid/mount/net/uts/ipc
namespaces, `pivot_root`, seccomp, fixed environment, no ASLR; ≈4.6 ms per run) whose result is a
typed **Verdict** — compiler diagnostics, a crash object with the first user frame and allocation /
free sites, test failures grouped by root cause — and a **Delta** against the previous run
("2 errors fixed, 1 new; crash moved `a.c:9` → `b.c:15`"; "crash SAME — your change did not
affect it"). We show that (i) deltas are sound only under the hermetic profile (ASLR, locale,
clock and scheduling otherwise poison run-to-run identity); (ii) on N repair tasks in C and Python
with sanitizers, typed+delta feedback changes turns-to-fix by X % and billed cost by Y % relative
to raw, truncated, compressed and masked observations at equal or better success; and (iii) the
effect concentrates where raw output is largest and the model is weakest. sbx, the Verdict/Delta
contract, a Claude Code hook and the benchmark harness are open source.

## 1 Introduction

Coding agents spend most of their context on what their tools print. The JetBrains Research
measurement on SWE-agent found observation tokens ≈ 84 % of an average turn; CoACT reports 45.7 %
of all tokens on SWE-bench Verified and 67.8 % on Terminal-Bench; SWE-Pruner Pro quotes ">70 %";
a live Claude Code session measured with claude-devtools had 31 % of its context in tool outputs.
Single tool calls of 580 k (Claude Code `getDiagnostics`) and 948 k tokens (Codex `rg`) have been
reported as issues. At the same time the average Claude Code task costs \$8.17 and 21.6 M tokens
(Artificial Analysis, 2026), Anthropic's own docs advise hook-filtering test output "from tens of
thousands of tokens to hundreds", and weekly usage caps became a user-visible pain in 2025–26.

The reflex response is to shrink the bytes. The ecosystem did exactly that: RTK ("Rust Token
Killer", Jan 2026, 77 k GitHub stars) and ≥15 clones rewrite `cargo test`, `pytest`, `tsc` output
with regexes before the model sees it. Two independent evaluations then found that this does not
buy what it promises: JetBrains (Jul 2026, 425 trials) measured **+7.6 % cost** and +13.8 % turns;
Weinberger & Hozez (arXiv 2607.12161, 2 908 runs) found a correlation of **r = 0.15** between
token reduction and billed cost, with aggressive variants *raising* cost by 7–48 %. The causes are
mechanical: 90–97 % of an agent's tokens are prompt-cache reads at ~10 % price, and an agent that
loses information re-derives it with extra turns.

Every deployed harness shapes tool output the same way — by size. Claude Code middle-truncates
Bash output at 30 000 characters and spills the rest to a file; Codex CLI keeps 256 lines or
10 KiB (head 128 / tail 128); Gemini CLI keeps 40 000 characters and optionally asks an LLM to
summarise; OpenHands, Terminus 2 and mini-SWE-agent cut at 30 000 chars, 10 000 bytes and 10 000
chars respectively. None of the hosted sandboxes (E2B, Modal, Daytona, Vercel, Docker Sandboxes,
Kubernetes agent-sandbox, OpenSandbox) shapes output at all; none parses compiler diagnostics,
sanitizer reports or test results into structure; none computes what changed between two runs.

We take a different position. **The executor already has the facts.** It knows whether the
process exited, was killed, or timed out; AddressSanitizer tells it the bug class, the access, the
faulting frame and where the object was allocated and freed; the compiler reports file, line,
column and code; the test runner reports which tests failed and why. Handing the model 30 KB of
interleaved bytes and hoping it finds these facts is a design choice, not a law. Two properties
follow once the executor owns the feedback. First, it can be *typed*: a stable schema rather than
a byte stream, so that the same facts render identically across runs. Second, it can be
*differential*: because the executor sees consecutive runs, it can say what changed — which is
the single most actionable sentence after an edit, and something a byte filter cannot compute.
Differential feedback, in turn, forces a systems question: a delta is meaningless if addresses
move with ASLR, test order varies with thread scheduling, and messages change with locale. Hence
the executor must be hermetic — not as a security nicety but as a precondition for compressible
feedback. Anthropic's measurement that container configuration alone moves Terminal-Bench scores by
6 pp, and Terminal-Bench 2.1's repair of 28/89 tasks for environment drift (with the C/Rust
compile tasks moving by +74/+84 pp), say the same thing from the evaluation side.

**Contributions.**
1. *System.* `sbx`, a ~4 k-line Rust executor that runs a command in fresh namespaces without
   root, applies a documented hermetic profile (fixed environment, `ADDR_NO_RANDOMIZE`,
   `no_new_privs`, seccomp denylist, isolated network with loopback up), and returns a
   self-describing `Outcome` (what isolation actually held) in ≈4.6 ms per run.
2. *Interface.* A typed `Verdict` (diagnostics, crash, tests, tail, status precedence) produced by
   deterministic parsers for ASan/UBSan/LSan/TSan, gcc/clang, rustc, pytest, unittest, cargo
   test, ctest/gtest, Python tracebacks and shell check scripts; and a `Delta` with line-shift
   tolerant diagnostic identity, test identity and crash identity (kind + first user frame).
3. *Evaluation.* A controlled comparison of six observation forms — raw, Claude-Code-style and
   Codex-style truncation, RTK-style compression, typed, typed+delta — plus observation masking,
   at identical execution, on sanitizer-heavy C and Python tasks, with success, turns, cache-aware
   billed cost and run-to-run variance reported per condition, on a frontier model (Claude) and an
   open-weight family (Qwen2.5-Coder). Negative results and failure cases of deltas are reported.
4. *Integration.* A Claude Code `PostToolUse` hook that replaces verbose Bash output with the
   verdict and keeps the full log on disk, and a benchmark harness that other executors can adopt.

## 2 Background and related work

**Execution feedback for repair.** Feeding execution results back to the model is established:
Self-Debugging (+12 pp on TransCoder/MBPP with unit tests), Reflexion (80 → 91 % HumanEval), LDB
(per-block runtime values, +9.8 pp), CodeAct (executable actions, up to +20 pp and 30 % fewer
actions), SWE-agent's Agent-Computer Interface (18.0 % vs 11.0 % shell-only, with ablations
showing that a 100-line file viewer beats both 30-line and full-file views, and that collapsing
older observations beats full history by 3 pp), AutoCodeRover, Agentless, OpenHands. Gains
concentrate in the first three to four iterations ("Is Three the Magic Number?", 2026; FeedbackEval;
CRUST-Bench), and the curve's shape is set more by feedback design than by the model.

**The form of feedback matters at fixed model.** RustAssistant's format ablation moved GPT-3.5
from 10.7 % to 73.7 % on compile-error repair and disabling error grouping dropped the fix rate to
≈14 %; VeriHarness reports +42–44 pp from adding {location, observed value, admissible
alternatives} to a raw diagnostic (same information as prose performs the same — structure per se
was not the lever, content selection was); PGS shows that a *minimal* counterexample beats a larger
one (+13.2 pp at 4.7 k tokens vs +9.1 pp at 5.7 k); Generative Compilation shows fewer,
root-cause-focused rustc diagnostics reduce compile-error rates. Conversely, more is not better:
the Fact Selection study finds the all-facts prompt fixes fewer bugs than the best subset (−8.2 %
pass@1); longer bug reports lower agent success (OR 0.49 per SD); SWE-agent's full-file and
full-history ablations lose 5.3 and 3.0 pp; LLM summaries of observations hide failure signals and
lengthen trajectories by 13–15 % (Complexity Trap). The Type-Error Ablation study (2026) is the
only controlled verbosity sweep for agents — on HM type errors with a 14 B model — and finds that
*relevant* structured detail helps the first hypothesis, not convergence.

**Sanitizer and crash feedback.** Crash-site repair from regex-distilled ASan reports fixed 358
ARVO bugs for \$0.68 (WilliamT); DebugHarness distils sanitizer signatures and lets the agent drive
GDB to reach 89.5 % on SEC-bench at \$0.09/vulnerability, with an ablation showing the sanitizer
report alone suffices for spatial bugs but temporal bugs (UAF) need dynamic state; AutoPatchBench
shows that crash-site plausibility overstates correctness (≈60 % build-and-stop-crash, 5–11 %
survive differential tests). None of these ablates distilled against full reports on cost, and none
measures what nondeterministic crash artifacts do to an agent.

**Observation compression.** Observation masking (Complexity Trap) halves cost on SWE-bench
Verified and matches or beats LLM summarisation; AgentDiet (FSE'26), ACON (ICML'26), SWE-Pruner
(/Pro), CoACT and TACO learn or optimise compressors and report −23…−60 % tokens at +0…+4 pp;
Squeez measures recall of tool-output pruning (92 % removal at 0.86 recall) without end-task
effect; "Less Context, Better Agents" finds pruning to the last five tool results raises GPT-5
from 71 % to 79 % at a third of the tokens. Negative results exist: code minification loses 12 pp;
LLMLingua-2 loses 7; CoACT loses 1.5 on one model. Almost all of this is Python SWE-bench; none is
*semantic structuring by the executor*, and none is differential.

**Sandboxes and determinism.** Agent sandboxes are a mature market (Firecracker at E2B/Vercel/Fly;
gVisor at Modal/GKE; Docker Sandboxes; Kubernetes agent-sandbox; Anthropic's bubblewrap/Seatbelt
runtime; Codex's bubblewrap+Landlock+seccomp; Sandlock, hakoniwa, nono in Rust). None shapes output
and none claims determinism. Deterministic execution exists as research or verification products
(Hermit, rr, Antithesis) and hermetic build sandboxes (Bazel's `linux-sandbox`, Nix), whose
mechanisms we borrow. DeltaBox and Crab add snapshot/fork to agent sandboxes and show rollback
saving 36 % tokens — evidence that executor-side state can change agent economics. "Grounded
Scaling" (2026) argues k-step agent success degrades as δ^k with environment nondeterminism; COBALT
finds models trained on execution feedback "learn to follow it without reasoning about its
validity" — flaky feedback is actively harmful.

**Position.** In the novelty matrix of the research report (§4), four cells are empty across
~100 tools, 15 harnesses and ~60 papers: a typed feedback contract emitted by the executor;
diagnostic-level deltas; determinism as a precondition for deltas; and a cost-and-turns evaluation
of feedback forms on C/C++/Rust with sanitizers. This paper fills them; everything else — the
sandbox primitives, regex filters, LLM summarisation, masking, hook plumbing — is integration.

## 3 System

### 3.1 hermit-core: the executor

A run is described by a `Spec` (argv, work dir, extra binds, rootfs mode, env, limits, hermetic
knobs) and produces an `Outcome` (exit kind — code / signal / timeout / setup-failed — rusage,
captured streams with truncation flags, wall and setup time, and an `Applied` record). The parent
`clone(2)`s into new user, pid, mount, net, uts, ipc and cgroup namespaces; writes uid/gid maps;
places the child in a cgroup leaf when a delegated cgroup v2 subtree exists (otherwise records why
not) and releases it. The child mounts a tmpfs root, binds the host's `/usr /bin /sbin /lib* /etc
/opt` read-only — preserving each source's `nosuid/nodev/noexec/*atime` lock flags in the remount,
which is what makes read-only binds work without root — binds the task directory read-write at
`/work`, mounts `/tmp`, a minimal `/dev` (null/zero/full/random/urandom/tty/shm/pts, fd symlinks),
a fresh `/proc` with dangerous entries masked, and a read-only `/sys`; `pivot_root`s and detaches
the old root; brings `lo` up with a raw `RTM_NEWLINK` over NETLINK_ROUTE; sets
`personality(ADDR_NO_RANDOMIZE)`, `PR_SET_NO_NEW_PRIVS`, rlimits (CPU, NOFILE, FSIZE, NPROC,
CORE=0); replaces the environment with the hermetic profile; installs a seccomp-bpf denylist
(EPERM: io_uring, bpf, ptrace, perf_event_open, userfaultfd, key management, module/kexec/reboot,
mount family, unshare/setns, personality, clock setters, AF_ALG and ~40 socket families); reports
what held to the parent through a pipe; and `execve`s. A wall-clock timeout SIGKILLs the pid-1 of
the sandbox, which takes the namespace with it. Startup is 4.6 ms median on WSL2 6.6 (4.15 ms
without seccomp/loopback), against 0.56 ms for a plain `spawn` and 100–500 ms for `docker run`.
`RLIMIT_AS` is off by default because AddressSanitizer reserves ~20 TB of address space.

### 3.2 feedback: Verdict, Delta, render

`distill(stdout, stderr, facts) → Verdict` runs deterministic parsers in order of specificity:
sanitizer reports (header, access, frames with user/runtime classification, allocation and free
stacks, summary, shadow dump and legend consumed), UBSan runtime errors (+ frames), gcc/clang and
rustc diagnostics (multi-line rustc locations, source-echo and caret lines consumed, grouping by
tool + code or normalised message), test runners (unittest, pytest, cargo test with panic
locations, ctest/gtest, generic `ok`/`FAIL` check scripts), Python tracebacks, and bare fatal
signals. Unclaimed lines feed a short tail. Status precedence is setup-failed > timeout > crash >
build-failed > tests-failed > runtime-error > pass. `diff(prev, cur) → Delta` matches diagnostics
by (tool, severity, file, normalised message, |Δline| ≤ 3), tests by name, crashes by (kind, first
user frame ± 3 lines), and reports fixed/new/unchanged, tests fixed/broken/still failing, crash
gone/new/moved/same. `render` prints a fixed-order text block (header, delta, crash with first user
frame and alloc/free sites, diagnostics errors-first, failing tests, tail, footer with the log
path); Python and Rust renderers are kept in parity by test. On the tasks below the rendered
verdict is 0.05–0.8× the raw bytes (0.05 on a 17 KB use-after-free run; 0.8 on an already terse
compile error).

### 3.3 Integration

`sbx run` persists the last verdict per work dir so a re-run prints a delta; `sbx verdict --raw -
--state DIR` distils any log; a Claude Code `PostToolUse` hook replaces large Bash outputs with the
verdict only when structure was found and keeps the raw log on disk (2 648 → 534 bytes on an ASan
report); the benchmark harness below drives any model through the same loop.

## 4 Experimental design

**Hypotheses.** H1 (form): at identical execution, typed feedback reduces turns-to-solve and
billed cost versus raw / truncated / compressed observations at equal or better success. H2
(deltas): adding the delta further reduces turns on multi-iteration repairs; the effect vanishes
without the hermetic profile. H3 (determinism): the hermetic profile lowers run-to-run variance and
infrastructure error rate.

**Conditions** (presentation only; execution identical, inside sbx): A raw; B middle truncation at
30 000 chars (Claude Code); C head/tail 256 lines or 10 KiB (Codex); D RTK-style line compression;
E typed; F typed + delta; G typed + delta without the hermetic profile (for H2/H3); orthogonal
observation masking M = 10 (Complexity Trap).

**Tasks.** Eight in-house tasks (six C: heap overflow, use-after-free, stack overflow, double free,
UBSan signed overflow, compile errors; two Python unittest: exception, logic) validated so the
shipped version fails and a reference solution passes under sbx; raw failing output 0.8–17.8 KB.
Planned extension: SEC-bench/ARVO subset (C/C++, ASan, reproducible PoCs), ComBench, CRUST-Bench,
Terminal-Bench 2.1 `polyglot-*`, to 150–250 tasks.

**Models and harness.** Claude Opus 5 / Sonnet 5 via the official SDK (adaptive thinking, effort
high, prompt caching, server-side refusal fallbacks); open-weight Qwen2.5-Coder 3 B / 7 B through
Ollama (zero cost; one tool call per turn and bounded nudging for prose-only answers, both
recorded). Agent: four tools (read_file, write_file, run, done), 12–25 turns, independent success
verification by a fresh sbx run plus protected-file hashes.

**Metrics.** success (pass@1 with N ≥ 3–5 seeds and CIs — single-run agent evals carry 2–6 pp of
noise even at temperature 0), turns, tool calls, tokens by kind, billed cost with cache pricing,
wall-clock, bytes produced vs shown, per-run status sequence, nudges; by task family.

**Threats.** Cache economics (clearing or reshaping results invalidates prefixes); model dependence
(CoACT −1.5 pp on one model, minification −12 pp); the Python bias of prior work; plausibility ≠
correctness for crash patches (we verify by tests, not by crash absence); small-model tool-calling
artefacts (mitigated by recovery + sequential calls, disclosed).

## 5 Results (pilot slots)

*5.1 Local open-weight pilot (Qwen2.5-Coder 3 B, 8 tasks × {raw, truncate10k, typed, typed+delta},
1 seed, ≤12 turns; GTX 1060 3 GB, ≈50 % CPU offload).* **Interim, first 4 tasks (16/32 episodes,
2026-08-22 02:38):**

| condition | n | success | turns (mean) | `run` calls | input tokens | shown/raw | wall s |
|---|---|---|---|---|---|---|---|
| raw | 4 | 0/4 | 11.0 | 4.8 | 62 619 | 0.99 | 156 |
| truncate10k (Codex-style) | 4 | 1/4 | 10.0 | 4.2 | 48 984 | 0.91 | 133 |
| typed (structured) | 4 | 2/4 | 9.8 | 4.0 | 19 304 | 0.99 | 87 |
| typed + delta | 4 | 3/4 | 9.5 | 3.8 | 17 988 | 1.29 | 76 |

Per task (success; turns when solved): compile-error raw 0 / trunc 0 / typed 1 (8) / typed+delta 1 (8);
double-free 0 / 0 / 0 / 1 (10); heap-overflow 0 / 0 / 0 / 0; signed-overflow 0 / 1 (8) / 1 (8) / 1 (8).
Reading: with a weak model the direction is the predicted one on every axis — success 0 → 3 of 4,
input tokens ÷3.5, wall ÷2 — and *not* because the verdict is smaller on these tasks (shown/raw is
≈1 when the raw output is already short): the typed verdict names the faulting line and the failing
checks up front, which a 3 B model cannot extract from 60 KB of repeated ASan dumps within 12
turns. n is far too small for inference (Wilson 95 % CIs overlap); it is a sanity signal, not a
result. Full 32-episode table to follow; then the 7 B run.

*5.1 final (12 tasks × 4 conditions, 1 seed, ≤12 turns):* raw 0/12, truncate10k 1/12, typed 2/12,
typed+delta 3/12; input tokens 40.8 k → 17.5 k; wall 435 → 290 s. Directional, CIs overlap.

*5.2 Qwen2.5-Coder 7 B pilot (≤15 turns, 44/48):* raw 2/11, truncate10k 2/11, typed 2/11,
typed+delta 1/10 — **null**; floor effect (only compile-error and null-deref solved), ~1.9 nudges
per episode, `done` called in ≤3/11. A 20-turn re-run with the fixed parsers is queued
(`pilot-qwen2.5-coder_7b-v2t20`). Full tables: `docs/REPORT.md` §6.3–6.4, `docs/paper/pilot-*.md`.

*5.2b Protocol v2 (queued 7 B re-run, 20 tool-turns):* budget counts tool turns only; each
condition's `run` tool documents its own output format (legend for typed arms); deterministic
`hint:` glossary for crash kinds; edit-line tracking → edit-hit and progress metrics. Motivated by
trajectory diagnosis (30–38 % prose/empty turns at 7 B; re-running without edits; UBSan kind
misread as input parsing). See REPORT §5.

*5.3 Claude pilot.* — 8 tasks × 6 conditions × 3 seeds, effort high; main table: condition × {success,
turns, runs, cost, cache share, shown/raw}.

*5.4 Delta ablation (F vs E; G vs F).* *5.5 Variance (H3).* *5.6 Failure cases.*

## 6 Discussion (to write after results)

Token reduction vs turn reduction; when typed feedback hurts (temporal bugs needing dynamic state;
weak models over-trusting a terse verdict); generality of the contract beyond our parsers; what E2B
/ Harbor / Claude Code would need to adopt it.

## 7 Artifact

`sandbox-executor/` — crates (`hermit-core`, `feedback`, `sbx-cli`), `adapters/claude-code`,
`bench/` (agent, runner, tasks, scripts), `docs/` (verdict schema, hermetic profile); CI with fmt,
clippy `-D warnings`, unit + integration tests, sandbox self-test, e2e ASan verdict + delta and hook
smoke test on GitHub's Ubuntu runners.

## References (short keys; full list in `../../research/raw/`)

Complexity Trap 2508.21433 · CoACT 2607.02911 · SWE-Pruner Pro 2607.18213 · Token Reduction Is Not
Cost Reduction 2607.12161 · JetBrains RTK benchmark (Jul 2026) · SWE-agent ACI 2405.15793 ·
RustAssistant 2308.05177 · VeriHarness 2607.14167 · PGS 2506.18315 · FeedbackEval 2504.06939 ·
Fact Selection 2404.05520 · Type-Error Ablation 2606.01522 · Generative Compilation 2607.13921 · Is
Three the Magic Number 2607.05197 · WilliamT 2505.13103 · DebugHarness 2604.03610 · AutoPatchBench
(Meta 2025) · SEC-bench 2506.11791 · AgentDiet 2509.23586 · ACON 2510.00615 · TACO 2604.19572 ·
Squeez 2604.04979 · Less Context Better Agents 2606.10209 · Randomness in Agentic Evals 2602.07150 ·
Anthropic infrastructure-noise (Feb 2026) · Terminal-Bench 2.1 · Grounded Scaling 2606.22495 ·
COBALT 2602.03806 · DeltaBox 2605.22781 · Crab 2604.28138 · Sandlock 2605.26298 · Anthropic
code-execution-with-MCP / advanced-tool-use / context-engineering (2025) · LOCA-bench 2602.07962 ·
AgentNoiseBench 2602.11348.
