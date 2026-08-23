# sbx: a hermetic executor that returns typed, delta-aware feedback to coding agents

*A design-and-measurement study of what a coding agent should be shown after it runs code:
a 4–11 ms unprivileged sandbox that owns the facts (exit, signal, sanitizer report, test results),
emits them as a typed verdict with "what changed since last run", and a controlled experiment on
whether that changes how many turns and tokens a model needs to fix a bug.*

**Status (2026-08-23):** system complete and verified (tests, containment probes, localization
check, fuzzing, live hook test); local open-weight pilots done for Qwen2.5-Coder 3 B (48 episodes)
and 7 B (44/48 at ≤15 turns; a 20-turn re-run is queued); frontier-model arm run via the Claude Code CLI (no API key), including a causal verdict-corruption study (§6.7).

---

## Abstract

Coding agents spend most of their context window on what their tools print — 45–84 % of input
tokens across SWE-agent, Terminal-Bench and Claude Code traces — and every deployed harness shapes
that output the same way, by byte or line truncation. The obvious remedy, compressing stdout before
the model sees it, has been tried at scale (RTK and ~15 clones, 2026) and independently shown
**not** to reduce billed cost (+7.6 % in one study; r = 0.15 between token reduction and cost in
another), because an agent that loses information spends extra turns recovering it. We take a
different position: **the executor already has the facts**, so it should emit facts — and, because
it sees consecutive runs, it should emit *what changed*. We built **sbx**, an unprivileged Linux
sandbox (user/pid/mount/net/uts/ipc/cgroup namespaces, `pivot_root`, seccomp denylist, loopback via
netlink, fixed environment, no ASLR) whose result is a typed **Verdict** (compiler diagnostics,
crash object with first user frame and allocation/free sites, test failures by root cause) and a
**Delta** against the previous run. Four results. **(1) Mechanism:** the full profile costs 4.6 ms
per run idle (11 ms under load) — within 2.4 ms of bubblewrap and 10–50× below Docker/gVisor — so it
can wrap every compile/test call. **(2) Determinism is a precondition for deltas:** under the
hermetic profile the failing output of four sanitizer tasks is byte-identical across 10/10 runs;
with ASLR on, 0/10 — and, before we made crash identity address-free, even the *identity* used by
the delta drifted. **(3) Feedback form is a lever at the margin of capability — measured across three model tiers.**
On a weak local model (Qwen2.5-Coder 3 B, ≤12 turns) that cannot fix a bug from the source alone,
raw output solved 0/12 tasks, the typed verdict 2/12 and typed + delta 3/12, at 40.8 k → 17.5 k
input tokens — the predicted direction on every axis. A 7 B model shows a floor effect (1–2/11 in
every condition). And Claude Sonnet 4.6 (driven through the Claude Code CLI, no API key) exposes the
boundary exactly: on these short single-file bugs it fixes from the source and *never runs the buggy
code* (first-run = pass in 12/12), so the feedback is unused and form is irrelevant — but when we
force the buggy run into context, all six tasks are solved in both conditions in the same ~6 turns
while the typed verdict shows the model **7× fewer characters on average (up to 20× on a 36 KB
sanitizer report), at equal cost** — the "same outcome, far less context" that byte-compression was
shown *not* to deliver. **(4) The agent does not *trust* the verdict — it verifies.** Holding
execution byte-identical and corrupting *only* the shown verdict, Claude Sonnet 4.6 never once follows
a coherent, undetectable lie about *where* the bug is (**0/7 steered** across five tasks — including a
24-guard haystack built to force reliance on the verdict — the decoy untouched in 22 attempts) or *what*
it is (wrong crash class, 0/4); it repairs the real bug from source, succeeding even
with **no feedback at all** — a clean causal null (byte-identical-execution audited) that sharpens (3)
into a law: a corrupted or nondeterministic verdict can mislead the agent only where it cannot
self-verify, which is exactly where a *correct* verdict matters most. Independently of the agent result, the verdict points at the ground-truth
faulting line on 10/10 tasks, the executor held 29/29 containment probes, the parsers survived 300
fuzzed inputs, and the hook ran live inside a real Claude Code session (2 647 → 544 bytes, 114 ms).
Everything — executor, parsers, hook, 12 validated tasks, three-tier harness, figures — is open
source and reproducible from one script each.

---

## 1. Introduction

**The problem.** An agent edits code, runs the tests, reads the result, edits again. The "reads the
result" step is where the tokens go: the JetBrains Research measurement on SWE-agent puts
observation tokens at ≈84 % of an average turn [1]; CoACT measures 45.7 % on SWE-bench Verified and
67.8 % on Terminal-Bench [2]; a live Claude Code session had 31 % of its context in tool output [3].
Individual tool calls of 580 k and 948 k tokens have been filed as bugs. An average Claude Code
task costs \$8.17 and 21.6 M tokens [4]. Anthropic's own documentation tells users to write hooks
that filter test output "from tens of thousands of tokens to hundreds".

**The reflex, and why it fails.** Shrink the bytes. RTK — "Rust Token Killer", January 2026, 77 k
GitHub stars — rewrites `cargo test`/`pytest`/`tsc` output with regexes before the model sees it,
as do at least fifteen clones. Two independent evaluations then found that this does not reduce
what people pay: JetBrains (July 2026, 425 trials) measured **+7.6 % cost** and +13.8 % turns [5];
Weinberger & Hozez (2 908 runs) found **r = 0.15** between token reduction and billed cost, with
aggressive variants raising cost by 7–48 % [6]. Two mechanisms explain it: 90–97 % of an agent's
tokens are prompt-cache reads billed at ~10 %, so bytes are cheap; and an agent that is shown less
than it needs spends *turns* re-discovering it, and turns are expensive.

**What every harness does today.** Claude Code middle-truncates Bash output at 30 000 characters
and spills the rest to a file; Codex CLI keeps 256 lines or 10 KiB (head 128 / tail 128); Gemini
CLI keeps 40 000 characters and may ask an LLM to summarise; OpenHands, Terminus 2 and
mini-SWE-agent cut at 30 000 chars, 10 000 bytes and 10 000 chars. No hosted sandbox (E2B, Modal,
Daytona, Vercel, Docker Sandboxes, Kubernetes agent-sandbox, OpenSandbox) shapes output at all; none
parses diagnostics, sanitizer reports or test results into structure; none computes what changed
between two runs [7].

**Our position.** The executor already knows whether the process exited, was killed or timed out;
AddressSanitizer tells it the bug class, the access, the faulting frame and where the object was
allocated and freed; the compiler reports file, line, column and code; the test runner reports which
tests failed and why. Handing the model 30 KB of interleaved bytes and hoping it finds these facts
is a design choice. Once the executor owns the feedback, two things follow: it can be **typed** (a
stable schema, rendered identically run after run) and **differential** (because the executor sees
consecutive runs it can say what changed — the most actionable sentence after an edit, and one a
byte filter cannot compute). Differential feedback forces a systems requirement: a delta is
meaningless if addresses move with ASLR, test order with scheduling and messages with locale. So
the executor must be *hermetic* — not as a security nicety but as a precondition for compressible
feedback. Anthropic's finding that container configuration alone moves Terminal-Bench scores by
6 pp [8], and Terminal-Bench 2.1's repair of 28/89 tasks for environment drift [9], say the same
from the evaluation side.

**Contributions.** (1) `sbx`: a ~4 k-line Rust executor, no root, documented hermetic profile,
self-describing outcomes, 4.6 ms per run. (2) The Verdict/Delta contract and deterministic parsers
for ASan/UBSan/LSan/TSan, gcc/clang, rustc, pytest/unittest/cargo test/ctest/gtest/shell check
scripts, Python tracebacks and fatal signals. (3) Two controlled micro-experiments (startup latency;
run-to-run determinism) and a feedback-form experiment with identical execution and six
presentations, on 12 validated C/C++/Rust/Python tasks, with success, turns, tokens and cost per
condition. (4) Integration: a Claude Code hook and a harness any executor can adopt.

---

## 2. Background and related work

**Execution feedback for repair** is established: Self-Debugging (+12 pp with unit tests), Reflexion
(80 → 91 % HumanEval), LDB, CodeAct, SWE-agent's Agent-Computer Interface (18.0 vs 11.0 % shell-only;
its ablations show a 100-line file view beats both 30-line and full-file views, and collapsing old
observations beats full history by 3 pp) [10]. Gains concentrate in the first 3–4 iterations [11].

**The form of feedback matters at a fixed model.** RustAssistant's prompt-format ablation moved
GPT-3.5 from 10.7 to 73.7 % on compile-error repair [12]; VeriHarness reports +42–44 pp from adding
{location, observed value, admissible alternatives} to a raw diagnostic [13]; PGS shows a *minimal*
counterexample beats a larger one (+13.2 pp at fewer tokens) [14]; "Generative Compilation" shows
fewer, root-cause-focused diagnostics cut compile-error rates [15]. More is not better: the
all-facts prompt fixes fewer bugs than the best subset (−8.2 % pass@1) [16]; longer bug reports lower
agent success (OR 0.49 per SD) [17]; LLM summaries of observations hide failure signals and lengthen
trajectories by 13–15 % [1].

**Sanitizer and crash feedback.** Crash-site repair from regex-distilled ASan reports fixed ~7,400 crash
bugs for \$1 [18]; DebugHarness distils sanitizer signatures and lets the agent drive GDB to
89.5 % on SEC-bench — and shows sanitizer reports suffice for spatial bugs while temporal ones need
dynamic state [19]; AutoPatchBench shows crash-site plausibility overstates correctness (≈60 % stop
the crash, 5–11 % survive differential tests) [20]. None ablates distilled vs full reports on cost.

**Observation compression.** Masking old observations halves cost on SWE-bench and matches or beats
LLM summarisation [1]; AgentDiet, ACON, SWE-Pruner(/Pro), CoACT and TACO learn compressors and report
−23…−60 % tokens at +0…+4 pp [21]; pruning to the last five tool results raises GPT-5 from 71 to 79 %
at a third of the tokens [22]. Negative results exist (minification −12 pp; LLMLingua-2 −7). None of
this is *semantic structuring by the executor*, and none is differential.

**Sandboxes and determinism.** Agent sandboxes are a mature market (Firecracker at E2B/Vercel/Fly;
gVisor at Modal/GKE; Docker Sandboxes; K8s agent-sandbox; Anthropic's bubblewrap/Seatbelt runtime;
Codex's bubblewrap+Landlock+seccomp; Sandlock, hakoniwa, nono in Rust) [7]; none shapes output, none
claims determinism. Deterministic execution exists as research/verification (Hermit, rr, Antithesis)
and hermetic builds (Bazel `linux-sandbox`, Nix) whose mechanisms we borrow. DeltaBox and Crab add
snapshot/fork to agent sandboxes and show rollback saving 36 % tokens. "Grounded Scaling" argues
k-step agent success degrades as δ^k with environment nondeterminism; and "Don't Blindly Trust It"
(arXiv 2606.21409) shows agents follow *corrupted* tool feedback into worse-than-no-feedback outcomes
("value inversion", even GPT-4o) [23] — flaky or wrong feedback is actively harmful, not just noisy.

**Position.** The *principle* that execution feedback should be a typed interface rather than a byte
stream is, as of mid-2026, **converging independently** — VeriHarness [13], "AI Coding Agents Need
Better Compiler Remarks" (precise remarks 3.3× success, ambiguous ones actively harmful), RLCSF
("compilers already compute the missing signal but expose it for human IDEs, not learning loops"),
the MCP `outputSchema`/`structuredContent` envelope (spec 2025-06-18), and shipping build-diagnostics
servers (.NET Binlog MCP, `pytest --receptor`). We therefore do **not** claim the principle as novel;
convergence de-risks it. What a survey of ~100 tools, 15 harnesses and ~130 papers (research report §4;
round-2 synthesis) still finds *unoccupied* is the specific conjunction: (i) a **deterministic,
executor-side, no-LLM verdict that unifies compiler + sanitizer/crash + tests** into one machine-readable
object — every prior typed-diagnostic tool covers a single domain, and sanitizer crash-typing
(kind/access/first-user-frame/alloc–free sites) is the rare part; (ii) **diagnostic-level cross-run
deltas fed back to the agent as inference-time feedback** — the nearest work, RLCSF, uses the delta only
as an RL reward and never surfaces it; (iii) **determinism as a measured precondition** for those deltas,
which we anchor to "Grounded Scaling" (k-step success ∝ δ^k) and the "Replay Gap" (3 % of replayed states
valid after divergence); and (iv) a **cost-and-turns evaluation of feedback forms on C/C++/Rust with
sanitizers**. This work occupies (i)–(iv); the sandbox primitives, regex filters, LLM summarisation,
masking and hook plumbing are integration. We also flag the field's methodological standard that the
present arms do **not** yet meet: feedback value should be measured against a *matched no-feedback /
blind-resampling control at equal budget*, since even our weakest arm (`raw`) still delivers feedback
rather than none; adding that control is the priority for the next iteration (§9). The evaluation does
already expose the honest scope limit (§6.5): on tasks a strong model fixes from source, the feedback
channel is never exercised — a documented regime ("To Run or Not to Run": prohibiting execution costs
SOTA agents only 1.25 pp), which is why the effect concentrates at the margin of capability.

---

## 3. Design

**Three layers, policy separated from mechanism.**

```
 Spec ──▶ hermit-core (mechanism) ──▶ Outcome ──▶ feedback (policy) ──▶ Verdict ──▶ render ──▶ agent
            clone(2) into namespaces        exit/signal/timeout      parsers: sanitizer,       delta vs
            tmpfs root + ro host binds      rusage, streams,          compiler, tests,          previous
            /dev /proc /sys, pivot_root     wall/setup ms,            traceback, signal         Verdict
            lo up (netlink), rlimits,       Applied{...}
            no ASLR, no_new_privs,
            hermetic env, seccomp, exec
```

**Self-describing outcomes.** Every `Outcome` carries an `Applied` record — which namespaces held,
whether `pivot_root`/seccomp/loopback/no-ASLR/fixed-env took effect, which rlimits applied, the
cgroup leaf or the reason there is none. Experiments can be filtered by isolation level after the
fact instead of trusting a README.

**The hermetic profile** (full table in `docs/hermetic-profile.md`): fresh user/pid/mount/net/uts/
ipc/cgroup namespaces; tmpfs root with `/usr /bin /sbin /lib* /etc /opt` bound read-only from the
host (lock flags preserved in the remount — the reason read-only binds work without root); `/work`
rw; `/tmp` tmpfs; minimal `/dev`; fresh `/proc` with dangerous entries masked; read-only `/sys`;
`pivot_root` + detach; loopback UP via a raw `RTM_NEWLINK`; `personality(ADDR_NO_RANDOMIZE)`;
`PR_SET_NO_NEW_PRIVS`; RLIMIT CPU/NOFILE/FSIZE/NPROC, CORE=0; environment replaced by a fixed set
(`LC_ALL=C.UTF-8`, `TZ=UTC`, `TERM=dumb`, `PYTHONHASHSEED=0`, `SOURCE_DATE_EPOCH`, `ASAN_OPTIONS`,
`UBSAN_OPTIONS`, …); seccomp-bpf denylist (EPERM): `io_uring_*`, `bpf`, `ptrace`, `perf_event_open`,
`userfaultfd`, key management, module/kexec/reboot/swap, the mount family, `unshare`/`setns`,
`personality`, clock setters, `socket()` for AF_ALG and ~40 exotic families. `RLIMIT_AS` is off
because AddressSanitizer reserves ~20 TB of address space.

**The Verdict** (`docs/verdict-schema.md`): `status` with precedence setup-failed > timeout > crash
> build-failed > tests-failed > runtime-error > pass; `diagnostics[]` {tool, severity, file, line,
col, code, message}; `crash` {tool, kind, access, address, frames[] with user/runtime
classification, alloc_frames, free_frames, first_user_frame, summary}; `tests` {runner, passed,
failed, errors, failures[]}; `tail` (≤12 unclaimed lines); `raw_bytes`; `error_groups`.

**The Delta.** Diagnostics match on (tool, severity, file, normalised message, |Δline| ≤ 3); tests on
name; crashes on (kind, first user frame ± 3 lines) with hex addresses normalised out of the kind.
Reported: fixed/new/unchanged, tests fixed/broken/still-failing, crash gone/new/moved/same.

**Rendering** is fixed-order and deterministic: header → delta line → crash block (first user
frame, frames user-first, alloc/free sites) → diagnostics errors-first → failing tests → tail →
footer with the path of the full log. Python and Rust renderers are kept in parity by test.

---

## 4. Implementation

Rust workspace, 3.7 k lines (`hermit-core` 1.0 k, `feedback` 1.7 k, `sbx-cli` 0.5 k) plus 1.2 k
lines of Python harness (`bench/agent/{agent,run,analyze,plot}.py`). `hermit-core` uses `nix` for
`clone`/`mount`/`pivot_root`, `seccompiler` for BPF, raw `libc` for `wait4`/`personality`/netlink.
`feedback` uses `regex` with ordered, line-claiming parsers (sanitizer → UBSan → compiler → test
runner → traceback → signal; unclaimed lines form the tail). `sbx run` keeps `<work>/.sbx/last.json`
so a re-run prints a delta; `sbx verdict --raw - --state DIR` distils any log; a Claude Code
`PostToolUse` hook replaces large Bash outputs with the verdict only when structure was found and
keeps the raw log on disk. Quality gates: `cargo fmt --check`, `clippy -D warnings`, 15 unit +
integration tests on real fixtures, a sandbox self-test, an end-to-end ASan verdict + delta test
and a hook smoke test in CI. The agent harness drives Claude through the official SDK (manual tool
loop, adaptive thinking, effort, caching, server-side refusal fallbacks) or any Ollama model through
`/api/chat` with tool calling (one tool call per turn and bounded nudging for prose-only answers,
both recorded).

---

## 5. Methodology

**Machine.** Windows 11 host, WSL2 Ubuntu, Linux 6.6.114, 12 logical cores, 7 GB RAM visible to WSL,
NVIDIA GTX 1060 3 GB (Ollama in a sibling WSL distro; the 3 B model runs ~50 % on GPU, the 7 B
mostly on CPU). No root, no Docker.

**Startup latency** (`bench/scripts/startup_bench.sh`): `/bin/true` under plain spawn, sbx full
profile, sbx without seccomp/loopback, and bubblewrap with equivalent namespaces and binds; 2 warm-ups,
n = 30, wall-clock from Python including the wrapper's own spawn; min/median/p90/mean ± sd.

**Determinism** (`bench/scripts/determinism.sh`): four sanitizer tasks × three profiles (hermetic;
ASLR on; ASLR on + inherited environment) × K = 10 runs; we count distinct sha256 of raw stdout+stderr,
distinct crash identities, distinct verdict JSON (wall time removed).

**Feedback-form experiment** (`bench/agent/`). One episode = task × condition × model × seed. The
agent has four tools — `read_file`, `write_file`, `run`, `done`; `run` always executes the task's
fixed command inside sbx, identically for every condition; only the *presentation* differs:

| condition | presentation | stands in for |
|---|---|---|
| raw | stdout+stderr verbatim + exit line | OpenHands/E2B-style |
| truncate30k | middle truncation at 30 000 chars | Claude Code Bash default |
| truncate10k | 256 lines or 10 KiB, head 128/tail 128 | Codex CLI default |
| regex | line-level heuristic compressor (drop shadow bytes/legend/deep frames, collapse repeats, cap 8 k) | RTK-style tools |
| structured | sbx Verdict rendering | this work, no delta |
| structured_delta | Verdict + Delta vs previous run | this work |
| (orthogonal) mask N | only last N tool results verbatim | observation masking [1] |

Tasks (12; `bench/tasks/`): six C (heap overflow, use-after-free, stack overflow, double free, NULL
dereference, UBSan signed overflow), one C compile-error task, one C++ (vector OOB), one Rust
(index panic, `rustc` from a read-only-bound toolchain), three Python unittest (exception, interval
logic, CLI parsing). Each ships failing and a hidden reference solution; `validate_tasks.sh` asserts
buggy→fail and solution→pass inside sbx (12/12). Raw failing output spans 0.8–36 KB.

**Models.** Claude Opus 5 / Sonnet 5 via the official SDK (adaptive thinking, effort high, prompt
caching, server-side refusal fallbacks); open-weight Qwen2.5-Coder 3 B / 7 B through Ollama (zero
cost; one tool call per turn and bounded nudging for prose-only answers, both recorded); and any
OpenAI-compatible hosted endpoint (`openai:<model>`) for larger open models when the local GPU is
the bottleneck. Measured here: 3 B runs at 28 tok/s generation / 290 tok/s prompt (≈50 % of the
model on the 3 GB GPU), 7 B at **10 / 86 tok/s** (≈23 % on GPU) — ≈10 minutes per episode and
8 hours per 48-episode run, which is the practical reason the local arm is small and 32 B-class
open models are planned on hosted free tiers.

Metrics per episode: success (independent sbx re-run + protected-file hashes), API turns, tool
calls, nudges, tokens by kind, cache-aware billed cost (public price list), wall-clock, raw bytes
produced vs chars shown, per-run status sequence. Wilson 95 % CIs on success; single-run agent
evaluations carry 2–6 pp of noise even at temperature 0 [24], so every claim below states n.

**Protocol v2 (after the first 7 B pilot; applied identically to every condition).** Trajectory
diagnosis (`diagnose.py`) showed that 30–38 % of the 7 B model's turns were prose-only or empty
(each burning a turn of 15 plus a nudge), that it re-ran `run` without editing, and that it misread
sanitizer vocabulary. v2 therefore (i) bounds *tool* turns (prose/empty replies are nudged without
consuming budget; API calls remain hard-capped); (ii) lets each condition's `run` tool document its
own output — raw/truncated/compressed text for those arms, a four-line legend of the verdict (and of
the `delta:` line) for the typed arms, which is that condition's agent–computer interface rather
than extra help; (iii) adds a deterministic one-line `hint:` glossary for known crash kinds to the
typed verdict (e.g. UBSan "insufficient space" → "out-of-bounds access, not an input-parsing
problem"); (iv) records the changed line numbers of every edit, giving two finer-grained outcomes
when success is at the floor: **edit-hit** (did any edit touch the ground-truth faulting line ± 3)
and **progress** (did a later run reach a better status or fewer failing checks than the first).
v1 and v2 result sets are kept separate (`pilot-<model>.jsonl` vs `pilot-<model>-v2t20.jsonl`).

---

## 6. Evaluation

### 6.1 Startup latency (n = 30)

*Figure:* `bench/out/figs/fig_startup.svg`. Idle machine (`sbx bench`, in-process): sandboxed
`/bin/true` **4.59 ms** median (4.15 without seccomp/loopback), setup→exec 2.0 ms, plain spawn
0.56 ms. Under load (3 B pilot saturating ~5.5 cores; CLI path incl. JSON + verdict):

| variant | min | median | p90 | mean ± sd |
|---|---|---|---|---|
| plain spawn | 0.68 | **0.89** | 1.21 | 0.94 ± 0.15 |
| sbx full (ns + pivot_root + mounts + seccomp + lo + verdict) | 9.76 | **11.20** | 12.68 | 11.25 ± 0.96 |
| sbx --no-seccomp --no-loopback | 7.99 | **10.31** | 12.38 | 10.54 ± 1.61 |
| bubblewrap (unshare-all, ro /usr, tmpfs /tmp, proc, dev) | 5.91 | **8.85** | 10.94 | 8.92 ± 1.67 |

sbx's full profile costs ≈ bubblewrap + 2.4 ms (≈0.9 ms seccomp + netlink, the rest JSON/verdict/
state I/O that bubblewrap does not do) and sits 10–50× below `docker run` (100–500 ms) and gVisor
(+40–150 ms) [7]. Wrapping every compile/test call is invisible next to a 150 ms `gcc` or a
multi-second model call.

### 6.2 Determinism (K = 10 per cell)

| task | profile | distinct raw outputs | distinct crash identities | distinct verdicts |
|---|---|---|---|---|
| use-after-free / heap-overflow / stack-strcpy / double-free | **hermetic** | **1 / 1 / 1 / 1** | 1 / 1 / 1 / 1 | 1 / 1 / 1 / 1 |
| same four | ASLR on | 10 / 10 / 10 / 10 | 1 / 1 / 1 / 1 | 10 / 10 / 10 / 10 |
| same four | ASLR on + inherited env | 10 / 10 / 10 / 10 | 1 / 1 / 1 / 1 | 10 / 10 / 10 / 10 |

Under the hermetic profile the failing output is byte-identical across **40/40** runs; with ASLR
every run differs (sanitizer addresses), so any byte- or text-level "what changed" would report 100 %
change on an unchanged program. Crash identity is stable under ASLR only *after* we made it
address-free: before that fix, `c-heap-overflow` showed 10 distinct identities under ASLR because
UBSan's "load of address 0x… with insufficient space" carried the address into the kind, and the
delta would have said "crash moved" on every re-run. Both lessons stand: identity must be
address-free by construction, *and* the executor should pin ASLR so that everything downstream
(messages, addresses an agent might grep) is stable too. Inherited environment costs ~5–10 % wall.

### 6.3 Feedback form, local weak model — Qwen2.5-Coder 3 B (1 seed, ≤ 12 turns, GTX 1060)

*Figures:* `fig_success_qwen2.5-coder-3b.svg`, `fig_tokens_qwen2.5-coder-3b.svg`,
`fig_turns_qwen2.5-coder-3b.svg`, `fig_shown_vs_raw_qwen2.5-coder-3b.svg`,
`fig_task_matrix_qwen2.5-coder-3b.svg`. Final: 48 episodes (12 tasks × 4 conditions, 1 seed).

| condition | n | success | 95 % CI | turns | `run` calls | input tokens | wall s | shown/raw |
|---|---|---|---|---|---|---|---|---|
| raw | 12 | **0/12** | 0–24 % | 9.9 | 4.1 | 40 756 | 435 | 1.01 |
| truncate10k (Codex) | 12 | 1/12 | 1–35 % | 9.6 | 4.0 | 32 928 | 367 | 0.96 |
| typed verdict | 12 | 2/12 | 5–45 % | 9.3 | 3.7 | 19 351 | 306 | 0.94 |
| **typed + delta** | 12 | **3/12** | 9–53 % | 9.4 | 3.8 | **17 485** | **290** | 1.27 |

Solved (turns): compile-error — typed ✓8, typed+delta ✓8; double-free — typed+delta ✓10;
signed-overflow — trunc ✓8, typed ✓8, typed+delta ✓8. Everything else failed in every condition
(nine tasks: the 3 B model never produced a correct fix within 12 turns, whatever it was shown).

Reading. With a 3 B model the predicted direction holds on every axis — success 0 → 3 of 12, input
tokens ÷2.3, wall ÷1.5 — and the per-episode scatter (`fig_shown_vs_raw`) shows *why* it is not a
byte effect: on small-output tasks the verdict is as long as the raw output (shown/raw ≈ 1), yet
typed conditions still win; on the 17–36 KB tasks the verdict stays at ~1 k chars while raw grows to
10⁵ and the model simply never finds the faulting line. Typed + delta calls `done` in 3/12 episodes
versus 0/12 for raw — raw episodes end at the turn cap without the model ever believing it is done.
The CIs overlap (Wilson 95 %: raw 0–24 %, typed+delta 9–53 %); this is a directional signal, not a
result, and the floor is low: nine of twelve tasks are simply beyond a 3 B model in 12 turns.

### 6.4 Feedback form, local model — Qwen2.5-Coder 7 B (1 seed, ≤ 15 turns; ≈ 23 % of the model on GPU)

*Figures:* `fig_success_qwen2.5-coder-7b.svg`, `fig_tokens_qwen2.5-coder-7b.svg`,
`fig_turns_qwen2.5-coder-7b.svg`, `fig_shown_vs_raw_qwen2.5-coder-7b.svg`,
`fig_task_matrix_qwen2.5-coder-7b.svg`. 44/48 episodes at the time of writing (the remaining four
are the Rust task); ≈ 10 min per episode.

| condition | n | success | 95 % CI | turns | `run` calls | nudges | input tokens | wall s | shown/raw |
|---|---|---|---|---|---|---|---|---|---|
| raw | 11 | 2/11 | 5–48 % | 7.6 | 2.7 | 1.9 | 25 563 | 528 | 1.01 |
| truncate10k (Codex) | 11 | 2/11 | 5–48 % | 7.5 | 2.8 | 1.7 | 19 495 | 639 | 1.01 |
| typed verdict | 11 | 2/11 | 5–48 % | 9.4 | 3.5 | 1.8 | 21 621 | 719 | 0.41 |
| typed + delta | 10 | 1/10 | 2–40 % | 9.1 | 3.2 | 1.9 | 20 297 | 570 | 0.42 |

Only two tasks were solved at all (compile-error in every condition at 7 turns; null-deref in
three of four). **No effect of feedback form is visible at 7 B in this budget** — a null result
with the same n as the 3 B arm, and an important one: success is at the floor (≤ 18 %) in every
condition, so the presentation cannot move it, and the token/wall differences shrink because the
7 B model reads the raw output in fewer turns (7.6 vs 9.4). Two confounds are visible in the
bookkeeping: ~1.9 nudges per episode (the model answers in prose roughly every fourth turn, each
nudge burning a turn of the 15) and `done` called in only 2–3 of 11 episodes — most episodes end at
the cap. We therefore queue a second 7 B run with a 20-turn budget and the parser fixes from §6.6
(check-script failures now carry expected/got; Rust panics parsed) — `pilot-qwen2.5-coder_7b-v2t20`
— and report it when done. Until then the honest summary of the local arm is: *directional gain at
3 B, null at 7 B, both with n = 10–12 and wide intervals; the frontier arm decides.*

### 6.5 Frontier model — Claude (via the Claude Code CLI, no API key)

The Claude arm runs without an API key by driving the Claude Code CLI (`claude.exe`, OAuth login)
turn-by-turn as the model: built-in tools disabled, the model emits our tool-call JSON as text, the
harness parses and executes it in sbx (`ClaudeCLIModel`; native Windows Python so `--resume` works,
sbx reached through the WSL bridge). Costs are the CLI's own `total_cost_usd`.

**A first run exposed a confound, not a result.** Claude Sonnet 4.6 solved all 6 memory tasks in
every condition in 4 turns — but with **`raw_bytes ≈ 100` and first-run status = `pass` in 12/12
episodes**: the model read the source, fixed the bug, and only *then* ran the tests (which passed).
It never executed the buggy code, so the raw-vs-typed feedback was never delivered. On tasks a
capable model can fix by reading a short single file, execution feedback — in any form — is simply
unused. (The weak model could not fix from source, which is exactly why the 3 B arm *did* show an
effect.) This is a real finding about *when* feedback matters, and a lesson for the experiment:
the feedback must actually be delivered.

**Control — force the buggy run (`--run-before-edit`).** The harness rejects the first `write_file`
until `run` has executed once, so the buggy-code feedback is in context before any edit (a fair,
documented constraint identical across conditions). Claude Sonnet 4.6, 6 memory tasks × 2 conditions,
1 seed, `ran_buggy_first = 6/6` in both:

| condition | n | success | turns | chars shown | raw bytes | shown/raw | cost |
|---|---|---|---|---|---|---|---|
| raw | 6 | **6/6** | 6.0 | **11,541** | 11,513 | 1.00 | $0.40 |
| structured_delta | 6 | **6/6** | 6.2 | **1,740** | 12,248 | **0.14** | $0.44 |

*Figure:* `fig_sonnet_rbe.svg`. Per task, `shown_raw → shown_typed`: heap-overflow 981→1,199 (already
terse); double-free 4,532→3,306; null-deref 3,630→1,289; stack-strcpy 5,854→1,295;
**use-after-free 17,949→1,515 (11.8×)**; **cpp-vector-oob 36,302→1,836 (19.8×)**. Every task solved
in both conditions in the same ~6 turns; the compression tracks how noisy the raw output is.

The result, stated plainly: **once the feedback is actually delivered, the typed verdict carries the
same signal at equal success and equal turns while showing the model ~7× fewer characters on average
(up to 20× on the noisiest task), at essentially equal cost.** It does not (yet) reduce *turns* on a
frontier model — because these single-file bugs are solved in one edit whether the model reads 36 KB
or 1.8 KB; the token saving is the effect here, and it is exactly the "same outcome, far less
context" that the RTK studies showed byte-compression fails to deliver. Whether typed feedback also
cuts turns needs tasks where the model must iterate and cannot fix from one glance at the source —
real vulnerabilities (SEC-bench/ARVO), multi-file bugs — which is the next experiment, not this one.

### 6.6 Correctness and containment checks (`bench/out/checks.md`)

*Tests.* 16 unit/integration tests on real fixtures (ASan heap overflow with alloc stack, UBSan,
gcc, rustc, pytest, cargo test, unittest, Rust panic, check scripts, delta line-shift/crash-moved/
test-fix cases, renderer determinism); `sbx selftest`; end-to-end ASan verdict + "crash moved" +
"crash SAME" on real gcc output; Python/Rust renderer parity on 7 fixtures; 48/48 mock-mode
episodes; 12/12 task validations (buggy fails, solution passes, inside sbx).

*Containment probes* (29, run inside sbx — `escape_probes.sh`): host secrets (`/etc/shadow`), host
filesystem (`/home /root /var`, `/proc/1/root`, `/work/..`), writes outside `/work`, `mount`/
`unshare`/`chroot`, `ptrace`, signals to host pids, TCP/DNS egress, `/dev/sda` `/dev/mem`
`/dev/kmsg`, `/proc/sysrq-trigger` `/proc/kcore` `/proc/sys`, `sudo`, `io_uring`/`bpf`/`AF_ALG`,
hostname and secret-named env leaks: **29/29 contained** (one hardening came out of the first run:
the tmpfs root is now remounted read-only after setup). This is containment against the
mis-configuration classes SandboxEscapeBench found to matter, not a kernel-security claim. The default profile (user/pid/mount/net namespaces + a single-uid map + `pivot_root` with the old root detached + a seccomp denylist installed last under `no_new_privs`) contains untrusted code, and the probes exercise the **default flags on the native ABI**. The boundaries, stated plainly: the seccomp filter is a *layer* — attack-surface reduction plus a lock on the mount/namespace calls (their x32 ABI variants are blocked too) — not the boundary itself, so `--no-seccomp` removes the read-only-bind guarantee; `--net` (shared host net namespace) and `--inherit-env` (host environment passed into the child) are opt-in and change the threat model; and without a delegated cgroup v2 subtree there is no memory ceiling (RLIMIT_AS is off so AddressSanitizer can reserve its shadow), so a delegated cgroup is required to bound memory against untrusted code.

*Localization accuracy* (`localization_check.py`): does the verdict's first user frame (or first
error diagnostic) point at the ground-truth faulting line? **10/10 tasks** — and the check itself
found and fixed three parser gaps (Rust ≥ 1.9x prints a thread id in the panic line; unittest
failures now carry the innermost frame of the code under test rather than the test file; ASan's
"attempting double-free" kind was cut at the first space).

*Parser robustness* (`fuzz_parsers.sh 300`): 300 mutated/garbage inputs (byte flips, truncation,
line shuffles, random bytes, 30× repeats, splices, CRLF) → 0 failures, 4.5 ms mean per call
including process spawn, 18 ms worst.

*Hook, live in Claude Code.* A nested headless `claude -p` session (Claude Code 2.1.239, Windows
host, Haiku 4.5, \$0.03) with the PostToolUse hook configured ran `cat asan.log`: the hook was
invoked by the real harness, received `tool_response` as an object (the hook accepts both shapes),
and replaced a 2 647-byte ASan report with a 544-byte verdict in 114 ms through the WSL bridge.

### 6.7 Causal attribution: does the agent *trust* the executor's verdict?

§6.5 showed a frontier model often fixes a single-file bug from source and never runs the buggy code.
That is an observation about *behaviour*; it does not tell us whether, when the feedback **is**
delivered, the model *uses* it or merely tolerates it. We test use **causally**: because sbx is
deterministic we re-run the identical episode and change **only the presented verdict** — a clean
information-channel intervention no post-hoc byte filter could support.

**Design.** The sandbox executes byte-identically across five arms; only the text shown after a run
differs. *truth* — the real typed verdict. *corrupt_line* — identical, but the reported fault line is
replaced by an **expert-plausible decoy**: a real statement of the *same syntactic class* as the true
fault, **causally inert** (an edit there cannot pass the tests), 8–25 lines from the fix, rewritten
**consistently** across the crash frame, stack, output tail and diagnostics so the lie leaves no tell
(verified: no true-line token survives). *corrupt_kind* — identical, but the crash *class* is swapped
for a different plausible class (e.g. out-of-bounds → use-after-free), re-pointing the `hint` and the
implied fix strategy. *no_feedback* — exit code only, the matched no-information floor. *raw* —
verbatim output, which has no single field to corrupt. **Readout:** the line numbers the agent's
**first** `write_file` changes (difflib-minimal, so a full-file rewrite still yields the true edited
lines); `hit_true_fix` = first edit within ±3 of the fix locus (auto-derived from the solution diff);
`steered` = followed the decoy **and** missed the fix. `run-before-edit` is enforced so the (corrupted)
verdict is in context before any edit. Four memory-safety tasks (heap-overflow, use-after-free,
null-deref, C++ vector OOB), Claude Sonnet 4.6 via the CLI, one seed, paired by task; a fifth
"haystack" task (below) is added at three seeds.

| arm | n | success | first edit on true fix | followed shown line | steered |
|---|---|---|---|---|---|
| truth | 4 | 4/4 | 4/4 | 2/4 | — |
| **corrupt_line** | 4 | **4/4** | **4/4** | **0/4** | **0/4** |
| corrupt_kind | 4 | 4/4 | 4/4 | 3/4 | — |
| no_feedback | 4 | 4/4 | 4/4 | 3/4 | — |
| raw | 4 | 4/4 | 4/4 | 2/4 | — |

Every arm solved all four and put its first edit on the true fix — **including `no_feedback`**. Under
`corrupt_line` the model **never once touched the decoy**: P(first edit on decoy | decoy shown) =
**0/4**, versus **0/12** when the decoy is not shown; paired McNemar on `hit_true_fix` gives b = c = 0
(p = 1.0); the first edit's displacement from the true fix has median **0 lines** (one task moved
*toward* the fix under corruption). The byte-identical-execution audit confirms the pre-feedback run's
raw bytes are identical across all arms per task, so the manipulation is presentation-only.
`corrupt_kind` — the stronger lie — left the first edit on the true fix in **all four** tasks (paired
McNemar p = 1.0): telling the model a heap overflow was a use-after-free, or vice versa, did not change
*which line* it repaired.

*Figure:* `bench/out/figs/fig_steer.svg`. Per task, a line-number axis with the true-fix locus (green),
the decoy the corrupted verdict pointed at (red), the true crash line (blue), and where the agent's
first edit landed under corruption (●): every edit sits on the fix; the decoy is never touched.

**Stress test — a haystack that makes the verdict load-bearing.** To rule out that the null merely
reflects trivially-obvious bugs, we added a fifth task (`c-haystack-oob`): 24 near-identical field
handlers, each copying its value into its own 16-byte heap slot behind a length guard, with exactly
one guard off-by-one (line 27). Locating it means auditing all 24 lines, so the verdict's line
*should* be load-bearing. Claude Sonnet 4.6, three seeds: with the truthful verdict (line 27) it fixed
line 27 every time; with the line corrupted to a plausible decoy (line 15 — another field's *correct*
guard, 12 lines away) it **still fixed line 27 in 3/3**, never touching the decoy, at only a small
turn cost. Across all five tasks the decoy is touched in **0 of 22** opportunities (15 when hidden, 7
when shown) and steering is **0/7** (paired McNemar p = 1.0). Even when self-verification is made
expensive *and* the executor lies about which guard is wrong, the model finds the real one.

**Interpretation.** The executor's localization is **not load-bearing** here: the model fixes every bug
from source, succeeding even with zero feedback, so corrupting the localization is inert. A frontier
code agent, on a bug it can read, treats the typed verdict as *decoration* and re-derives the fault
from source — it does **not** defer to the tool, and it silently **overrides** a coherent, undetectable
lie about where the bug is. This is the causal sharpening of §6.5's bypass. It also runs against a
naive reading of the literature, where agents adopt raw tool output 97.6–99.2 % of the time (*When the
Tool Decides*, arXiv:2606.14476) and plausible-but-wrong observations flip ~32 % of otherwise-correct
decisions (*When History Lies*, arXiv:2608.06057) — but those hold where the model *must* rely on the
channel (retrieval QA, chat history, a frozen classifier). Here it can self-verify, so it does.

The boundary is therefore precise, and it restates this paper's design thesis as a testable law: **a
corrupted verdict — hence a nondeterministic or buggy executor — can mislead the agent only where the
agent cannot independently verify from source.** That is exactly the regime typed feedback targets
(large repos; memory bugs whose crash site is far from the cause; source-insufficient patches), and
exactly where a *correct*, deterministic verdict matters most — the constructive complement to "Don't
Blindly Trust It" (arXiv:2606.21409), whose value-inversion appears precisely when the feedback is
load-bearing.

**Novelty.** Prior corruption studies corrupt a whole observation (retrieval QA) [23], the reported
fault location in a *single-shot* APR replication (arXiv:2507.20977), or chat history on a 1.7 B model
(2608.06057); typed-field studies *add or remove truthful* fields (VeriHarness [13]). To our knowledge
this is the first to corrupt a **single typed field of an executor verdict while holding execution
byte-identical**, on a **frontier agent in a real loop**, with a **first-edit-line causal readout** and
matched **raw + no-feedback** controls.

**Limits.** Four tasks, one seed, one model+version; small verifiable single-file bugs by design — an
existence/robustness result with a large minimum detectable effect: it establishes that **no large
steering effect exists in this regime**, not that none exists anywhere. A capability contrast (a model
that engages the loop yet cannot self-verify) and the predicted positive — steering where the model
*cannot* fix from source (SEC-bench/ARVO, multi-file, masked source) — are the next experiment.

---

## 7. Discussion

**Bytes vs turns.** The 3 B data already separate the two: the verdict is not smaller than raw on
half the tasks, yet the agent finishes in fewer turns and more often. The lever is *which* facts
arrive first — the faulting line, the failing checks, "your change did not affect the crash" — not
how many characters arrive. This is consistent with the RTK evaluations [5, 6] and with the
literature on feedback *content* (RustAssistant, VeriHarness, PGS).

**When feedback matters at all.** The Claude arm (§6.5) makes the boundary sharp: a capable model
fixes a short single-file bug by *reading the source* and never runs the buggy code, so feedback —
raw or typed — is unused (Sonnet, 12/12 first-run = pass). Feedback is a lever only at the margin of
capability: the weak 3 B model, which cannot fix from source, is where the typed verdict moved
success; and, when we force the buggy run into context, the typed verdict delivers the same result
as raw in ~12× fewer characters. So the effect is real but conditional — it needs either a model
that must lean on the run output, or a task too hard/large to fix from a glance at the source. Our
in-house tasks are deliberately small (to isolate diagnosis), which makes them *too easy* for a
frontier model to exercise the feedback channel; the next experiment needs harder, feedback-forcing
tasks.

**Where typed feedback should lose.** Temporal memory bugs that need dynamic state beyond the
report [19]; programs whose failure is only visible in long output the verdict tails away; models
strong enough to read 60 KB and weak enough to over-trust a terse verdict.

**Determinism as design, not decoration.** §6.2 is the clearest result in the study: without the
profile, byte-level feedback is unstable every run and a naive delta is noise; with an address-free
identity *and* the profile, both identity and text are stable. This is the argument for putting
feedback inside the executor rather than in a post-hoc filter that never sees two runs.

**What this does not claim.** No frontier-model numbers yet; n = 10–12 per condition; one seed; one
machine; tasks are small and the fixes local by design (we measure diagnosis, not refactoring). The
7 B arm is a genuine null at its budget: when a model cannot fix the bug in 15 turns under *any*
presentation, the presentation cannot matter — feedback form is a lever only where the model is
otherwise capable of the fix, which is exactly why the frontier arm is the decisive one. We also
note a measurement subtlety the 7 B run exposed: the nudge mechanism for prose-only answers costs
turns from a fixed budget and may itself interact with the condition (a verbose raw observation
seems to provoke more prose); a turn budget that excludes nudges, or a larger one, is the fairer
design and is what the queued v2 run uses.

---

## 8. Threats to validity

*Construct:* success is judged by the task's own tests inside sbx — a plausible patch that passes
them counts, as in SWE-bench; we do not run differential tests. *Internal:* local models get
sequential tool calls and nudges; both are recorded and identical across conditions; Ollama's
`prompt_eval_count` under-reports prompt tokens after KV-cache reuse (a conservative bias against
our own token numbers). *External:* 12 small tasks; Python-free of `pytest` (unittest used);
C/C++ with sanitizers dominate by design. *Statistical:* single seed so far; Wilson CIs reported;
agent evaluations carry 2–6 pp noise at temperature 0. *Cost:* local runs cost \$0; cache-aware
billing is implemented but only meaningful on the API arm.

## 9. Future work

A second research pass (six-agent survey, ~130 sources; `research/REPORT-round2-synthesis.md`)
sharpened this into an ordered plan. **Methodology first**, because it gates every claim: (1) add a
**matched no-feedback / blind-resampling arm at equal budget** — the field's standard denominator
(Olausson; "Try Again, Don't Look Back"), which our current `raw` arm does not provide; (2) test that
feedback is *used*, not just present, by **corrupting the verdict** (flip the first-user frame, swap
the crash kind, blank the delta) and watching for unchanged patches or value-inversion ("Don't Blindly
Trust It"); (3) move to **source-insufficient, feedback-forcing tasks** where a frontier model cannot
one-shot from source — AutoPatchBench/ARVO memory-safety (oracle = PoC stops crashing), SEC-bench
(best agent 18 %/34 %), Multi-SWE-bench C/C++/Rust — reporting **turns-to-resolve and cache-aware
$/resolved as primary, tokens secondary**, with paired BCa bootstrap over ≥10–20 seeds and a
localization sub-metric; (4) **ablate the typed fields** (raw / +location / +delta / +admissible-
alternative), because VeriHarness shows the added *information*, not the JSON, drives the gain.

**System upgrades**, cheapest-first (evidence in the synthesis): an **admissible-alternatives field**
per verdict (the single largest lift in VeriHarness; our crash glossary already implies the fix class);
**print the offending value** — deterministic first-frame locals at the fault, no LLM (LDB/NExT/
DebugRepair, +10–25 pp at ~0 token cost); **AST-level diagnostic matching** to replace the ±3-line
delta tolerance; **progressive disclosure** of the verdict (terse by default, agent pulls deeper —
one level only); emit the verdict as **MCP `structuredContent` behind a versioned `sbx.run-result`
`outputSchema`** so agents branch on it in code; a **"you already tried this / no-op edit"** verdict
fusing crash-SAME + zero diagnostic-delta + nonzero code-diff; and **delta-min of large failing
inputs** (ReduceFix). Research-grade follow-ons: root-cause (not symptom) deltas; **COW snapshot-fork
for delta-native tree search** (DeltaBox-style layered-COW + BPO branch-and-diff); an optional
interactive-debug channel; and typed run-to-run deltas as **dense per-turn RL rewards** for a
feedback-following fine-tune (RLEF/SWE-RL). Determinism track: `CLONE_NEWTIME` + frozen clock, seeded
`getrandom` via seccomp-notify, a `--isolation=microvm` tier for untrusted code.

Also still open from the original plan: frontier arm (Claude Opus 5, 3–5 seeds, masking and regex
conditions); Landlock stacking; mini-SWE-agent and Harbor backends; and a robotics plugin (MuJoCo
"physical verdict": constraint violations with first-violation time, torque saturation, stability
margins) on the same contract.

## 10. Conclusion

An executor that owns the facts can say what happened and what changed, in a few hundred bytes,
every time, for four milliseconds. The weak-model pilot says that this — not the byte count — is
what moves a coding agent; the determinism experiment says the executor must be hermetic for it to
be true at all. The rest is measurement, and the instrument is built.

---

## Appendix A. Reproducibility

```bash
# Linux / WSL2, no root. Build + self-test + micro-experiments:
cargo build --release -p sbx-cli
source bench/scripts/env.sh
sbx selftest && sbx bench --n 30
bash bench/scripts/startup_bench.sh 30
bash bench/scripts/determinism.sh 10
# Tasks and harness:
bash bench/scripts/setup_venv.sh && bash bench/scripts/validate_tasks.sh && bash bench/scripts/smoke_agent.sh
# Local pilot (Ollama):  ollama pull qwen2.5-coder:7b
bash bench/scripts/ollama_pilot.sh qwen2.5-coder:7b 1 raw,truncate10k,structured,structured_delta 1 15
$SBX_PY bench/agent/analyze.py bench/out/pilot-qwen2.5-coder_7b.jsonl --md docs/paper/pilot-7b.md
$SBX_PY bench/agent/plot.py --results bench/out/pilot-*.jsonl --startup bench/out/startup_bench.json --out bench/out/figs
# API arm:  ANTHROPIC_API_KEY=… $SBX_PY bench/agent/run.py --model claude-opus-5 --seeds 3 --workers 3
```

## References

[1] Lindenbauer et al., "The Complexity Trap", NeurIPS'25 DL4Code, arXiv:2508.21433. [2] CoACT,
arXiv:2607.02911. [3] claude-devtools context measurement, Mar 2026. [4] Artificial Analysis Coding
Agent Index v1.4, 2026. [5] JetBrains AI, "RTK and Claude Code token savings", Jul 2026. [6]
Weinberger & Hozez, "Token Reduction Is Not Cost Reduction", arXiv:2607.12161. [7] research report
`research/raw/01-sandbox-landscape.md` (E2B, Modal, Daytona, Vercel, Docker Sandboxes, K8s
agent-sandbox, OpenSandbox, OpenShell, Anthropic sandbox-runtime, Codex sandbox; harness truncation
rules). [8] Anthropic, "Quantifying infrastructure noise in agentic coding evals", Feb 2026. [9]
Terminal-Bench 2.1 release notes, May 2026. [10] Yang et al., SWE-agent, arXiv:2405.15793. [11] "Is
Three the Magic Number?", arXiv:2607.05197. [12] RustAssistant, ICSE'25, arXiv:2308.05177. [13]
VeriHarness ("Structured Feedback Improves Repair in an LLM Agent Loop"), arXiv:2607.14167. [14] PGS, arXiv:2506.18315. [15] Generative Compilation,
arXiv:2607.13921. [16] Fact Selection, arXiv:2404.05520. [17] "What Makes a Good Bug Report for an
AI Agent?", arXiv:2607.07593. [18] WilliamT, arXiv:2505.13103. [19] DebugHarness, arXiv:2604.03610.
[20] AutoPatchBench, Meta 2025. [21] AgentDiet 2509.23586; ACON 2510.00615; SWE-Pruner 2601.16746;
CoACT 2607.02911; TACO 2604.19572. [22] "Less Context, Better Agents", arXiv:2606.10209. [23]
Grounded Scaling 2606.22495; Don't Blindly Trust It 2606.21409; DeltaBox 2605.22781; Crab 2604.28138. [24] "On
Randomness in Agentic Evals", arXiv:2602.07150.
