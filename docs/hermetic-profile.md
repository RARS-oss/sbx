# Hermetic profile — what `sbx run` fixes, and why

Determinism is not a decoration here: the delta feature compares two runs, and every source
of run-to-run variance that leaks into the output (ASLR addresses, clock, locale, thread
interleaving, network drift) turns a delta into noise. This page lists what the profile pins
today, what it reports but cannot pin, and what is planned. `Outcome.applied` says which
items held on a given run.

## Pinned today (hermit-core 0.1)

| Dimension | Mechanism | Effect on the agent loop |
|---|---|---|
| Filesystem view | tmpfs root; `/usr /bin /sbin /lib* /etc /opt` bound read-only from the host (or an extracted rootfs dir); `/work` rw; `/tmp` tmpfs (1 GiB); fresh `/proc`; minimal `/dev` (null/zero/full/random/urandom/tty, shm, pts); ro `/sys`; `pivot_root` + detach of the old root; host `/home`, `/root`, `/var`, `/run` invisible | Same paths in every diagnostic; no accidental reads of host state; no writes outside `/work` |
| Processes | new pid namespace (command is PID 1 → SIGKILL on timeout kills everything); RLIMIT_NPROC; cgroup `pids.max` when delegated | Fork bombs bounded; no orphans |
| Network | new net namespace; `lo` brought UP via a raw RTM_NEWLINK over NETLINK_ROUTE (no `ip` binary) | External dependency drift eliminated (Terminal-Bench 2.1 repaired 9 tasks for exactly this); `127.0.0.1` works for local test servers, `1.1.1.1` → ENETUNREACH |
| Syscall surface | seccomp-bpf denylist (EPERM): `io_uring_*`, `bpf`, `perf_event_open`, `userfaultfd`, `keyctl`/`add_key`/`request_key`, `ptrace`, `process_vm_*`, `kcmp`, `pidfd_getfd`, module/kexec/reboot/swap/acct/quotactl, `open_by_handle_at`, `fanotify_init`, `unshare`/`setns`/`mount`/`umount2`/`pivot_root`/`chroot` and the new mount API, `sethostname`/`setdomainname`, `personality`, `settimeofday`/`clock_settime`/`adjtimex`, `socket()` for AF_ALG and ~40 exotic families | Setup cannot be undone from inside; ASLR state and clock cannot be changed; "Copy Fail"-class AF_ALG bugs unreachable; probing code degrades gracefully (EPERM, not SIGSYS) |
| Identity | user namespace, uid 0 ↔ caller; UTS namespace, hostname `sbx`; IPC namespace; cgroup namespace | Stable `uid`, `hostname`, no host IPC |
| Memory layout | `personality(ADDR_NO_RANDOMIZE)` | Identical addresses in sanitizer reports / backtraces across runs → crash identity is comparable |
| Privileges | `PR_SET_NO_NEW_PRIVS`; core dumps off (RLIMIT_CORE=0) | No setuid escalation; no multi-GB core files |
| Environment | replaced by: `PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, `HOME=/work`, `USER=sbx`, `LANG=LC_ALL=C.UTF-8`, `TZ=UTC`, `TERM=dumb`, `NO_COLOR=1`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, `CARGO_TERM_COLOR=never`, `RUST_BACKTRACE=1`, `ASAN_OPTIONS=symbolize=1:detect_leaks=0:abort_on_error=0:halt_on_error=1:print_stacktrace=1`, `UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1`, `SOURCE_DATE_EPOCH=<fixed>`, `SBX_SEED=<n>`, `SBX=1`; caller's extras layered on top | No colour codes, no locale-dependent messages, reproducible builds where tools honour `SOURCE_DATE_EPOCH`, stable Python hash order |
| Limits | wall timeout, RLIMIT_CPU/NOFILE/FSIZE/NPROC; cgroup `memory.max` + `pids.max` when a delegated cgroup v2 subtree exists | Runaway runs end the same way every time; resource model recorded per run (`applied.cgroup`) |

## Reported but not pinned

* **Memory** without a delegated cgroup (e.g. WSL2 without a systemd user session): only
  `RLIMIT_AS` is available, and it is off by default because AddressSanitizer needs ~20 TB of
  virtual address space. `applied.cgroup` carries the reason; an experiment should either
  run where delegation exists (`systemd-run --user --scope`, or a `Delegate=yes` slice) or
  treat memory as unbounded and say so.
* **Scheduling / thread interleaving**: not controlled (no CPU pinning yet; no deterministic
  scheduler like Hermit). Data-race-dependent output remains non-deterministic.
* **Time**: no time namespace offset yet; `date` inside the sandbox is the host's clock.
  `SOURCE_DATE_EPOCH` is fixed, `TZ=UTC` is fixed.
* **Randomness**: `/dev/urandom` is the host's; `SBX_SEED` is only a convention for programs
  that opt in.

## Planned

1. Landlock stacked on top (ABI-detected; WSL2 kernel 6.6 = V4).
2. Time namespace (`CLONE_NEWTIME` via `unshare` before the final fork) with a fixed
   monotonic/boottime offset; optional `getrandom` interposition via seccomp-notify for a
   seeded stream.
3. CPU-set pinning and a `--single-core` mode for replaying flaky runs.
4. Snapshot/fork of `/work` (overlayfs upper) for tree search over agent edits.
5. Capability bounding-set drop inside the userns (hygiene; no known escape path without it).

## Why each item matters — evidence

* Infrastructure noise alone moves agent scores by up to 6 pp between container configs
  (Anthropic, "Quantifying infrastructure noise in agentic coding evals", Feb 2026).
* Terminal-Bench 2.1 repaired 28/89 tasks for dependency drift, resource mismatches and
  misspecification; the low-level compile tasks moved by +74/+84 pp after repair.
* Single-run pass@1 varies 2–6 pp even at temperature 0 ("On Randomness in Agentic Evals",
  2026) — the environment must not add to that.
* Models trained on execution feedback "learn to follow it without reasoning about its
  validity" (COBALT, 2026) — flaky feedback is actively harmful, not just noisy.
