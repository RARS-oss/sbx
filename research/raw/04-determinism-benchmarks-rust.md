# Raw report 04 — Hermetic execution, agent benchmarks, building a Rust sandbox (2026-08-22)

Evidence: [P] primary, [S] secondary, [T] tertiary/unverified.

## A. Determinism / hermeticity

**Deterministic execution engines**
- **Hermit (Meta)** — Rust; Reverie backend (ptrace + seccomp interception). Controls thread scheduling, time, RNG, CPUID. Needs x86-64, user/PID/mount ns, perf counters. "Maintenance mode", "not a security boundary"; file/network contents remain inputs. https://github.com/facebookexperimental/hermit [P]
- **rr** — records nondeterministic syscall results + scheduling; needs ASLR disabled (issue #756). https://rr-project.org/ [P]
- **Antithesis deterministic hypervisor** (2024-03-20): single core per VM; guest time reads = virtual time from PMC instruction counts; VMCALL as only I/O boundary. https://antithesis.com/blog/deterministic_hypervisor/ [P]
- **DST**: tokio turmoil (seed replays everything); TigerBeetle VOPR; primer https://notes.eatonphil.com/2024-08-20-deterministic-simulation-testing.html [S]

**Hermetic build sandboxes (what to copy)**
- **Bazel linux-sandbox.cc**: clone() with NEWUSER|NEWNS|NEWIPC|NEWPID, NEWNET with -N, NEWUTS with fake hostname; read-only FS except -w dirs, tmpfs -e, -R fake root, -T timeout + -t SIGKILL grace; NO seccomp. https://github.com/bazelbuild/bazel/blob/master/src/main/tools/linux-sandbox.cc [P]
- **Nix**: private PID/mount/net/IPC/UTS ns; only declared store paths + private /proc,/dev; sandbox is for purity, not defense. https://nix.dev/manual/nix/2.23/command-ref/conf-file.html [P]; "the Nix sandbox is a hidden input" (2026-07-30) https://fzakaria.com/2026/07/30/the-nix-sandbox-is-a-hidden-input [S]
- **reproducible-builds.org**: SOURCE_DATE_EPOCH; variance sources: timestamps, build paths, ordering, locale, umask, hostname/user, kernel; `-ffile-prefix-map`. [P]
- **libfaketime 0.9.12**: LD_PRELOAD only — fails for static/setuid, Go/Java; prefer time namespaces + syscall interposition. [P]

**Snapshot/restore & replay for agent environments (2025–2026)**
- **Firecracker snapshots**: restoring many times duplicates identifiers/RNG seeds/entropy pool/tokens; VMGenID reseeds kernel PRNG not userspace; wall-clock stays at snapshot time unless `clock_realtime`. https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md [P]
- **E2B**: pause ≈4 s/GiB, resume ≈1 s. **Modal**: FS snapshots as diff images; memory snapshots 7-day TTL. Cold Firecracker boot 125–200 ms vs 5–30 ms from snapshot [S]; ForgeVM 28 ms restore via mmap + CoW (2026-03-16) [S].
- **DeltaBox** (SJTU/Huawei, arXiv 2605.22781, 2026-05): checkpoint ≈14.6 ms; restore 5.1 ms (fork template) / 8.0 ms (CRIU lazy); modified overlayfs + XFS reflink; network-proxy daemon keeps sockets out of agent address space; MCTS branching overhead 47–77% → 3–6%. [P]
- **Crab** (HKUST, arXiv 2604.28138): ZFS snapshot ≤22 ms; eBPF inspector skips 87% of turns that change no OS state; proactive rollback saved 29% wall-clock / 36% tokens. [P]
- **Sandlock** (arXiv 2605.26298, 2026-05): Rust ≈7K LOC; Landlock + seccomp-bpf + seccomp-notify + pidfd_getfd; no user ns/cgroups/root; ≈5 ms startup, ≈1,900 forks/s, 44× faster e2e than Docker; resource limits cooperative. [P]

**Why determinism matters for the agent loop**
- **Anthropic, "Quantifying infrastructure noise in agentic coding evals" (2026-02-05)**: Terminal-Bench 2.0 spread between container configs **6 pp (p<0.01)**; strict 1× CPU/mem vs 3× headroom changed infra-error rate 5.8%→2.1%; SWE-bench spread 1.54 pp; "differences below 3 pp deserve skepticism until eval configuration is documented and matched." https://www.anthropic.com/engineering/infrastructure-noise [P]
- **Terminal-Bench 2.1 (2026-05-06)** fixed 28 tasks: 9 external-dependency drift, 8 resource mismatches, 11 misspecifications; `polyglot-rust-c` +74.3 pp, `polyglot-c-py` +84.3 pp after fixes — low-level compile tasks most environment-sensitive. https://www.tbench.ai/news/terminal-bench-2-1 [P]
- COBALT (arXiv 2602.03806): models trained only on correct test feedback "learn to follow execution feedback without reasoning about its validity"; SWE-bench Pro runs every test 3× and drops non-deterministic tests. [P]

## B. Benchmarks and reproducibility

| Benchmark | Size / scope | Sandbox | Reproducibility notes | Cost/tokens first-class? | Source |
|---|---|---|---|---|---|
| Terminal-Bench 1.0 (2025-05) → 2.0 (2025-11) → 2.1 (2026-05) | 2.0: 89 tasks; Harbor harness | Docker; Harbor drives Daytona, Modal, E2B, Runloop, … | ≥5 trials per pair, 32,155 trials, 95% CI; 2.1 adds continuous validation | Paper reports tokens; **leaderboard no cost column** | arxiv 2601.11868; tbench.ai |
| TB 2.0 leaderboard (2026-08-22) | 142 entries | — | top ≈84–85% (GPT-5.5 harnesses, May 2026) | No | tbench.ai/leaderboard |
| SWE-bench Verified | 500 | Docker | Epoch AI: images rebuilt later "not identical"; UTBoost 26/500 need augmented tests, >24% entries revised; SWE-Bench+ 32.67% solution leakage; OpenAI stopped reporting it | No (HAL Verified-Mini: USD) | epoch.ai; arxiv 2410.06992 |
| SWE-bench Pro (Scale, 2025-09) | 731 public + 276 commercial + 858 held-out | Docker | tests run 3×, flaky dropped; best 23.3% | No | arxiv 2509.16941 |
| Multi-SWE-bench (ByteDance, 2025-04) | 1,632 (7 langs); Rust 10 repos, C 3, C++ 5 | Docker | Rust/C++ patches often >200 lines | No | arxiv 2504.02605 |
| SWE-bench-Live (Microsoft, NeurIPS 2025) | +50/month; C/C++/Rust tracks | Docker | — | No | github microsoft/SWE-bench-Live |
| SWE-rebench (Nebius) | >21k Python | Docker | contamination evidence | No | arxiv 2505.20411 |
| SWE-smith (NeurIPS'25) | 50k instances | Docker | successors: DockSmith, SWE-Hub, MEnvAgent, SWE-Bench++ | No | |
| **HAL** (Princeton, ICLR 2026) | 9 benchmarks, 26,597 rollouts | per-benchmark | "9× cost for 2 pp"; cost-accuracy Pareto; paused to study reliability | **Yes (USD + tokens)** | hal.cs.princeton.edu |
| Aider polyglot | 225 Exercism (C++/Go/Java/JS/Py/Rust) | local | — | **Yes (USD)** | |
| LIVE-KBENCH (2602.02690) | live kernel crashes from syzbot | isolated kernel envs | continuous | **Yes** | |
| SandboxEscapeBench (Oxford+AISI, 2026-03) | 18 escape scenarios | Docker/K8s | Opus 4.5 49%, GPT-5 50%; ~$1/attempt | Yes | arxiv 2603.02277 |

Low-level/crash-adjacent: DebugBench (4,253 C++/Java/Python); RustRepoTrans; CRUST-Bench. **No established benchmark targets C/C++/Rust crash triage with token accounting besides LIVE-KBENCH (kernel-only) — a gap.**

## C. Building the sandbox in Rust

**Kernel primitives**
- **Landlock ABI**: V1 5.13 (fs) → V2 5.19 (REFER) → V3 6.2 (TRUNCATE) → V4 6.7 (TCP bind/connect) → V5 6.10 (IOCTL_DEV) → V6 6.12 (scope unix socket + signal) → V7 6.15 (audit) → V8 7.0 (TSYNC) → V9 7.1 (RESOLVE_UNIX) → V10 (UDP). https://landlock.io/rust-landlock/landlock/enum.ABI.html [P]. Pitfall: IOCTL_DEV breaks TTY raw mode (nono #306).
- **io_uring**: `kernel.io_uring_disabled=2` (≥6.6); Docker default seccomp blocks `io_uring_*`; gVisor blocks it. [P]
- **cgroup v2 without root**: systemd delegation (`Delegate=yes`); memory+pids usually delegated. https://systemd.io/CGROUP_DELEGATION/ [P]

**Rust crates (Aug 2026)**
| Crate | Version/date | Role |
|---|---|---|
| `seccompiler` (rust-vmm) | 0.5.0, 2026-08-02; x86_64/aarch64/riscv64 | seccomp-bpf |
| `landlock` | 0.4.7; ABI V1–V9 | Landlock |
| `caps` | 0.5.6, 2026-08-09 | capabilities |
| `cgroups-rs` | updated 2026-07-14 | cgroup v1/v2 |
| `birdcage` (Phylum) | 0.8.1, 2026-06-08, GPL-3; Landlock + Seatbelt; rustix+seccompiler | embeddable |
| `youki` / `libcontainer` / `libcgroups` | active; rootless, cgroups v2, seccomp; 3-process model (main → intermediate creates ns/cgroups → init sets rootfs/exec) | OCI runtime to borrow from |
| `nono` (nolabs) | Rust CLI; Landlock/Seatbelt only, no namespaces; works in WSL2 | agent sandbox |
| Hermit, Sandlock | Rust | determinism / unprivileged |
| Anthropic `sandbox-runtime` | TypeScript; bubblewrap + netns + seccomp (blocks unix sockets) + socat → host proxy allowlist | reference design |
`gaol`/`rusty-sandbox`: no 2025–2026 activity (unmaintained).

**Performance**
| Option | Startup | Mem overhead | Isolation | Determinism support |
|---|---|---|---|---|
| In-process Landlock+seccomp (nono/Sandlock) | ~5 ms | ≈0 | weak–medium | none; limits cooperative |
| Namespaces+pivot_root+cgroups (own Rust / bwrap / runc) | ~20–50 ms (runc) | ~10 MB | medium (runc CVE-2025-31133/52565/52881) | net/UTS/time ns + ASLR-off easy |
| gVisor | +40–150 ms | ~30 MB | strong | none |
| Firecracker microVM | 125–200 ms cold; 5–30 ms snapshot | ~5 MB VMM | strongest practical | snapshot/fork; entropy/clock caveats |
| Hermit | ptrace overhead (3–6×) | small | not security | full |
| Antithesis | VM | — | VM | full; commercial |

**WSL2 specifics**
- Kernel 6.6 LTS (WSL 2.7.0 packages 6.6.114.1); Landlock since 5.15.57.1; io_uring since 5.10.60.1. Kernel 6.6 ⇒ **Landlock ABI V4 only** — plan feature detection.
- cgroup v2: `.wslconfig` `[wsl2] kernelCommandLine = cgroup_no_v1=all systemd.unified_cgroup_hierarchy=1` and `/etc/wsl.conf` `[boot] systemd=true`.
- `nestedVirtualization` default true on Win 11, but Firecracker on WSL2 "requires tweaking"; `/dev/kvm` absent inside wslc containers.
- Unprivileged user namespaces work in stock WSL2 kernel. Time namespaces since 5.6 → available.

**Security lessons 2025–2026**
- runc CVE-2025-31133 / 52565 / 52881 (Nov 2025): masked-path `/dev/null` symlink, `/dev/console` bind, LSM-label write redirect to `/proc/sysrq-trigger`. Lesson: never bind-mount over attacker-controlled paths; use `openat2(RESOLVE_NO_SYMLINKS|RESOLVE_BENEATH)`.
- bubblewrap CVE-2024-32462. SandboxEscapeBench: Docker socket, permissive caps, writable host mounts reliably exploited at ~$1/attempt; "treat plain Docker isolation as insufficient by default". NVIDIA Container Toolkit CVE-2025-23266.

## Recommended primitive stack (Rust, Linux/WSL2)
1. `clone3` with NEWUSER|NEWNS|NEWPID|NEWNET|NEWIPC|NEWUTS|NEWCGROUP|**NEWTIME** (rustix/nix) — mirrors Bazel/Nix/youki; NEWTIME gives offsettable CLOCK_MONOTONIC/BOOTTIME per sandbox.
2. Rootfs: read-only content-addressed base + overlayfs/tmpfs upper; `pivot_root` then `umount2(MNT_DETACH)`; mask `/proc/{kcore,sysrq-trigger,...}`, fresh `/proc` and `/dev`; `openat2` RESOLVE flags for every bind.
3. cgroup v2 leaf (cgroups-rs): `memory.max`, `pids.max`, `cpu.max` — floor=ceiling with calibrated headroom and record per task (Anthropic 2026-02-05); systemd delegation on WSL2.
4. `prctl(PR_SET_NO_NEW_PRIVS)`, drop all caps, rlimits (NOFILE/NPROC/CORE/AS).
5. `seccompiler` allowlist: deny `io_uring_*`, `ptrace`, `keyctl`, `bpf`, `perf_event_open`, `userfaultfd`, `unshare/setns/mount` after setup; optional seccomp-notify.
6. Landlock stacked (ABI-detect; WSL2 = V4).
7. Egress: NEWNET no veth by default; if needed unix-socket → host proxy with domain allowlist (Anthropic design), never Docker socket.
8. Snapshot/fork: overlayfs-upper diff + CRIU or template-fork (DeltaBox 5–15 ms); reseed RNG, reset clock per fork.
9. Escalation: same task format under Firecracker (Harbor-style backend swap) when tenant isolation matters; Hermit only for flake reproduction.

## "Hermetic profile" checklist
- Network: NEWNET, no default route; vendored deps; pinned images by digest.
- Time: NEWTIME offsets; `SOURCE_DATE_EPOCH`, `TZ=UTC`; record wall-clock at start.
- Identity: NEWUTS fixed hostname; fixed uid/gid; `umask 022`; fixed `HOME`, `PATH`, `LC_ALL=C.UTF-8`, `PYTHONHASHSEED=0`, `CARGO_HOME/RUSTUP_HOME`, `-ffile-prefix-map`.
- Memory layout: `personality(ADDR_NO_RANDOMIZE)` for reproducible crash addresses; fix `core_pattern`.
- Randomness: seeded `getrandom` via seccomp-notify or env seed; reseed after snapshot restore.
- Scheduling: pin CPU set; fixed `nproc`; single-core mode for replay.
- Resources: explicit floor=ceiling with headroom; log config; rerun N≥3 to detect flakiness.
- Filesystem: read-only base, tmpfs scratch, deterministic ordering; snapshot upper layer for diffing.
- Telemetry: record stdout/stderr/exit/syscall-denials/tokens/cost per run.

## Open gaps
- No public benchmark combines C/C++/Rust crash triage with token/cost accounting; Multi-SWE-bench C/C++/Rust splits tiny.
- Terminal-Bench per-task run-to-run variance not published.
- No measured numbers for Hermit slowdown on modern workloads or WSL2 6.6; Landlock V5+ absent on WSL2.
- Published cold-start/overhead figures for runc/gVisor/Firecracker are secondary blog benchmarks.
