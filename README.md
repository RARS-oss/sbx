# sbx — hermetic sandbox executor with typed, delta-aware feedback for coding agents

**Run a command in a throw-away Linux sandbox (no root, ~4 ms), and hand the agent a
typed *verdict* — parsed compiler diagnostics, sanitizer/crash objects with the first
user frame, failing tests grouped by root cause — plus a *delta* against the previous
run ("2 errors fixed, 1 new; crash moved from `a.c:9` to `b.c:15`"), instead of 30 KB
of raw stdout.**

> Portfolio/research note: this repository is the artifact behind a study on whether the
> *form* of execution feedback (raw bytes vs. typed + delta) changes how many turns and how
> much money a coding agent needs to fix C/C++/Rust/Python code. Token-level compression of
> tool output is already commoditised (and independently shown not to reduce billed cost);
> the bet here is different: **the executor owns the facts, so it should emit facts, and it
> should be deterministic enough that "what changed since last run" is meaningful.**

---

## What it does

```
$ sbx run --work /tmp/demo -- sh -c 'gcc -g -fsanitize=address overflow.c -o overflow && ./overflow'
[sbx] CRASH exit=1 wall=174ms raw=2820B
crash: AddressSanitizer heap-buffer-overflow (WRITE of size 4)
  at /work/overflow.c:9 in fill
  #0 fill /work/overflow.c:9
  #1 main /work/overflow.c:16
  #2 ? /usr/lib/x86_64-linux-gnu/libc.so.6+0x2a600
  #3 __libc_start_main /usr/lib/x86_64-linux-gnu/libc.so.6+0x2a717
  #4 _start /work/overflow+0x1184
  allocated at /work/overflow.c:14 in main
  0x7c3ff68e0038 is located 0 bytes after 40-byte region [0x7c3ff68e0010,0x7c3ff68e0038)
(full log available on request: sbx log)

$ # ... the agent edits, re-runs:
$ sbx run --work /tmp/demo -- sh -c 'gcc -g -fsanitize=address uaf.c -o uaf && ./uaf'
[sbx] CRASH exit=1 wall=55ms raw=3327B
delta: crash: moved heap-buffer-overflow @ /work/overflow.c:9 -> heap-use-after-free @ /work/uaf.c:15
crash: AddressSanitizer heap-use-after-free (READ of size 4)
  at /work/uaf.c:15 in sum
  ...
  allocated at /work/uaf.c:22 in main
  freed at /work/uaf.c:26 in main

$ sbx run --work /tmp/demo -- ./uaf
[sbx] CRASH exit=1 wall=16ms raw=3327B
delta: crash: SAME as last run (your change did not affect it)
```

The 2.8 KB ASan report (shadow-byte dump, legend, runtime frames) becomes ~12 lines; the
delta line is the most actionable sentence an agent can read after a re-run. Both come
from deterministic parsers — no LLM in the loop, no lossy summarisation.

Three crates, policy/mechanism split everywhere:

| Crate | Role |
|---|---|
| `hermit-core` | The mechanism. `clone(2)` into fresh **user / pid / mount / net / uts / ipc / cgroup** namespaces, tmpfs root with read-only host binds, fresh `/proc`, minimal `/dev`, read-only `/sys`, `pivot_root`, rlimits, best-effort cgroup v2, `no_new_privs`, `ADDR_NO_RANDOMIZE`, fixed environment profile. No root, no daemon, no Docker. Every `Outcome` carries an `Applied` record saying exactly which isolation features held, so experiments are self-describing. |
| `feedback` | The policy. `distill(stdout, stderr, facts) -> Verdict` (sanitizers → `Crash`, gcc/clang/rustc → `Diagnostic`s, pytest/cargo-test/ctest/gtest → `Tests`, Python tracebacks, bare signals), `diff(prev, cur) -> Delta` with line-shift-tolerant matching, and a stable text `render`. Pure functions, fixture-tested. |
| `sbx-cli` | `sbx run | verdict | selftest | bench`. `run` persists the last verdict under `<work>/.sbx/` so the next run prints a delta automatically; `--json` gives the full machine-readable outcome. |

## Why this and not "compress stdout"

- Tool output is 45–84 % of a coding agent's tokens (SWE-agent, Terminal-Bench, Claude Code
  measurements, 2025–2026). Everyone agrees it is the problem.
- Regex/line compressors of shell output (RTK and ~15 clones, 2026) are the obvious fix and
  two independent studies found they **do not reduce billed cost** (prompt-cache economics;
  agents take more turns to re-discover what was cut).
- No sandbox or agent harness we could find (E2B, Modal, Daytona, Docker Sandboxes, Claude Code,
  Codex, Gemini CLI, OpenHands, Terminus…) parses compiler/sanitizer/test output into
  structure, and none computes deltas between runs.
- So the hypothesis under test is not "fewer bytes" but **"fewer turns"**: typed facts + deltas
  should cut iterations-to-fix, which is what actually drives cost. The experiment design,
  baselines (observation masking, RTK-style compression, head/tail truncation as in Claude
  Code/Codex) and the literature behind all of the above live in `research/`.

## Status

Working today (Linux; verified on WSL2 6.6 and stock Ubuntu, unprivileged):

- [x] Namespaced sandbox with `pivot_root`, ro host system dirs, rw `/work`, `/tmp`, `/dev`, `/proc`, ro `/sys`
- [x] Hermetic profile: fixed env (`LC_ALL=C.UTF-8`, `TZ=UTC`, `SOURCE_DATE_EPOCH`, `PYTHONHASHSEED=0`, `ASAN_OPTIONS`…), hostname, no ASLR, `no_new_privs`, no network by default
- [x] Limits: wall timeout (SIGKILL of the pid-namespace init), RLIMIT_CPU/NOFILE/FSIZE/NPROC, core dumps off; cgroup v2 `memory.max`/`pids.max` when a delegated cgroup exists (reported otherwise)
- [x] Parsers: AddressSanitizer (+alloc/free stacks), UBSan, gcc/clang, rustc, pytest, cargo test, ctest/gtest, Python tracebacks, bare signals
- [x] Delta: diagnostics fixed/new/unchanged (±3-line tolerant), tests fixed/broken/still-failing, crash gone/new/moved/same
- [x] `sbx selftest` (isolation checks), `sbx bench` (startup latency), CI with fmt + clippy `-D warnings` + tests
- [x] seccomp-bpf denylist (`seccompiler`, EPERM): `io_uring_*`, `bpf`, `ptrace`, `perf_event_open`, `userfaultfd`, `keyctl`, `mount`/`unshare`/`setns`/`pivot_root`/`chroot`, `personality`, clock setters, `socket(AF_ALG…)` and ~40 exotic families — verified from inside: `unshare -U` → EPERM, `mount` → EPERM, AF_ALG → EPERM, ASan/gcc/python unaffected
- [x] Loopback UP inside the netns via raw netlink (no `ip` binary): `127.0.0.1` connect → ECONNREFUSED, listen+connect works, `1.1.1.1` → ENETUNREACH
- [x] Claude Code PostToolUse hook adapter (`adapters/claude-code/`), contract verified, e2e-tested
- [x] Experiment harness (`bench/`): instrumented agent on the official Anthropic SDK with six feedback conditions (raw / Claude-Code-style 30k truncation / Codex-style 10 KiB / RTK-style regex / structured / structured+delta) + observation masking, cache-aware cost accounting, independent success verification; resumable runner with summary table; **fourteen validated tasks** — C/C++ memory-safety (heap overflow, use-after-free, stack overflow, double free, NULL deref, vector OOB, a 24-guard "haystack", a 3-bug cascade), a C compile-error task, UBSan signed overflow, Rust index panic, and three Python unittest — buggy fails / solution passes under sbx; mock-mode smoke test (48/48) + Python/Rust renderer parity on all fixtures
- [x] Pilots run: Qwen2.5-Coder 3B/7B (Ollama) and **Claude Sonnet 4.6 via the Claude Code CLI (no API key)**, including a causal verdict-corruption study (`docs/REPORT.md` §6.7)
- [ ] Real-world-scale repair (SEC-bench / ARVO / multi-file) — where a frontier model must iterate, to measure the turn/cost win on strong models
- [ ] Landlock stacking (ABI-detect; WSL2 6.6 = V4)
- [ ] NEWTIME offsets, seeded `getrandom` via seccomp-notify
- [ ] mini-SWE-agent adapter, Harbor backend

## Results so far (honest summary; details in `docs/REPORT.md` §6)

- **Determinism:** under the hermetic profile the failing output of 4 sanitizer tasks is
  byte-identical across 40/40 runs; with ASLR on, 0/40 (and crash identity drifted too until it was
  made address-free). Deltas need the profile.
- **Containment / localization / fuzz / hook:** 29/29 escape probes contained; the verdict points at
  the ground-truth faulting line on 10/10 tasks; 300 mutated inputs, 0 failures, 4.5 ms/call; hook
  verified live inside a real Claude Code session (2 647 → 544 bytes, 114 ms).
- **Context reduction — the main token/memory win.** On a run-before-edit control (Claude Sonnet 4.6,
  driven through the Claude Code CLI, *no API key*), the typed verdict shows the model **7× fewer
  characters on average, up to 20×** (use-after-free 17 949 → 1 515; C++ vector OOB 36 302 → 1 836) at
  **equal success and equal turns** — the "same outcome, far less context" that byte-compression is
  shown *not* to deliver. On Qwen-3B, raw 0/12 → typed+delta 3/12 at 40.8 k → 17.5 k input tokens.
- **Feedback is a lever at the margin of capability.** A frontier model fixes short single-file bugs
  from source and never runs the buggy code, so feedback *form* is irrelevant there; the weak 3B model,
  which cannot fix from source, is where the typed verdict moves success (0 → 3/12). Turn- and
  cost-reductions therefore concentrate on weaker models and on tasks too large to fix from a glance
  (real-world-scale repair — SEC-bench/ARVO — is the next experiment).
- **The agent verifies, it doesn't trust (a causal result).** Holding execution byte-identical and
  corrupting *only* the shown verdict, Claude Sonnet 4.6 is **0/7 steered** across five tasks —
  including a 24-guard "haystack" built to force reliance on the verdict — never following a fabricated
  fault line or crash class; it repairs the real bug from source, even with **no feedback at all**. So a
  corrupted or nondeterministic verdict can mislead an agent only where it cannot self-verify — exactly
  where a *correct*, deterministic verdict matters most (see `docs/REPORT.md` §6.7).

## Report

The full design-and-measurement write-up (abstract → methodology → evaluation → threats), in the
style of a technical report, is `docs/REPORT.md`; `docs/report.html` is the same with figures
inlined (regenerate with `bench/agent/plot.py` + `bench/agent/build_report_html.py`). Experiment
outputs live in `bench/out/` (`startup_bench.md`, `determinism.md`, `pilot-*.jsonl`, `figs/`).

## Numbers (this machine: WSL2, kernel 6.6, 12 cores)

`sbx bench --n 30` — sandboxed `/bin/true` vs. plain `spawn`:

| | min | median | p90 |
|---|---|---|---|
| sandboxed (namespaces + pivot_root + mounts + netlink `lo` up + seccomp) | 4.06 ms | **4.59 ms** | 4.83 ms |
| same without seccomp/loopback | 3.89 ms | 4.15 ms | 4.50 ms |
| setup → exec inside the child | | 2.0 ms | |
| plain `Command::new("/bin/true")` | 0.54 ms | 0.56 ms | 0.70 ms |

For scale: Docker `run` is typically 100–500 ms, gVisor +40–150 ms, Firecracker 125–200 ms cold /
5–30 ms from snapshot (published vendor/blog numbers — see research report). Four milliseconds
means the sandbox can wrap *every* compile/test invocation without anyone noticing.

## Build & test

```bash
cargo test --workspace
cargo run -p sbx-cli -- selftest          # prints what isolation held on this kernel
cargo run -p sbx-cli -- bench --n 30
cargo run -p sbx-cli -- run --work /tmp/x -- sh -c 'gcc -fsanitize=address a.c && ./a.out'
cargo run -p sbx-cli -- run --work /tmp/x --json -- pytest -q     # full outcome + verdict + delta
cargo run -p sbx-cli -- verdict --raw some.log --exit 1            # distil an existing log
```

Requirements: Linux with unprivileged user namespaces (default on Ubuntu/Fedora/WSL2). On WSL2,
cgroup limits need a delegated cgroup (systemd user session); without it `sbx` says so in
`applied.cgroup` and falls back to rlimits. Building on Windows: develop in WSL2 and point
`CARGO_TARGET_DIR` at a native path for speed.

## Design notes

**Every outcome is self-describing.** `Outcome.applied` lists the namespaces, `pivot_root`,
`no_new_privs`, ASLR state, rlimits and the cgroup leaf (or the reason there is none). An
experiment can therefore be filtered by isolation level after the fact instead of trusting a
README.

**Read-only binds in a user namespace keep the lock flags.** Remounting a bind read-only while
dropping `nosuid/nodev/noexec/*atime` fails with `EPERM` in a userns; `hermit-core` reads the
source's `statvfs` flags and carries them into the remount. This is the #1 reason home-grown
sandboxes "work as root, fail as user".

**No `RLIMIT_AS` by default.** AddressSanitizer reserves ~20 TB of virtual address space and dies
under an address-space limit; memory must be bounded by the cgroup, not the rlimit (the option
exists for non-sanitized runs).

**Deltas are line-shift tolerant.** A diagnostic is "the same" if tool, file and normalised
message match and the line moved ≤3 — an edit above the error must not turn it into
"1 fixed, 1 new". Crash identity is (kind, first user frame ±3 lines).

**The parsers never invent.** Unclaimed lines go to a short tail; the full log is always kept in
`<work>/.sbx/last.stderr` and can be requested. Deterministic parsers make the rendered verdict
stable across runs — which is what lets a diff of two renderings be readable too.

## Layout

```
sandbox-executor/
├── crates/
│   ├── hermit-core/   # lib.rs (Spec/Outcome/run), child.rs (ns + mounts + exec), cgroup.rs, seccomp.rs, netlink.rs
│   ├── feedback/      # lib.rs (Verdict types), parse.rs, delta.rs, render.rs, tests/fixtures/
│   └── sbx-cli/       # sbx binary
├── adapters/claude-code/  # PostToolUse hook + settings example
├── bench/             # experiment harness: agent/, tasks/, scripts/ (see bench/README.md); demo/ = the examples above
└── docs/              # verdict-schema.md, hermetic-profile.md, paper/outline.md
```

MIT.
