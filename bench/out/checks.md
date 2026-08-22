# Verification checks (2026-08-22/23, WSL2 6.6)

## 1. Containment probes inside sbx — `bench/scripts/escape_probes.sh`

29 probes, **0 escaped** (after one hardening: the tmpfs root is now remounted read-only after
setup; `/work`, `/tmp`, `/dev/shm` stay writable as their own mounts).

| class | probes | result |
|---|---|---|
| host secrets / filesystem | read `/etc/shadow`; `/home`, `/root`, `/var` visible; `/proc/1/root` shows host; `/work/..` reaches host | contained |
| writes outside `/work` | `/usr`, `/etc`, `/bin`, `/` | contained |
| namespace/mount escapes | `mount -t tmpfs`, `unshare -U`, `chroot` | EPERM (seccomp) |
| ptrace / signals | `PTRACE_ATTACH` to a child; `kill(1000, 0)` on a host pid | contained (pid ns) |
| network | TCP to 1.1.1.1:53; DNS resolve | ENETUNREACH / fails |
| devices / kernel | `/dev/sda`, `/dev/mem`, `/dev/kmsg`; `/proc/sysrq-trigger`, `/proc/kcore` (masked: reads empty), write `/proc/sys` | contained |
| privilege | `sudo -n` | no (no_new_privs, nosuid) |
| syscall surface | `io_uring_setup`, `bpf`, `socket(AF_ALG)` | EPERM |
| leaks | hostname, env vars named *KEY/TOKEN/SECRET* | contained |

What this is not: a claim of kernel-level security. A user-namespace sandbox shares the host
kernel; the probes cover the mis-configuration classes that SandboxEscapeBench found to be the
practical escape routes (writable host paths, Docker socket, permissive caps, network), not kernel
exploits. For tenant isolation the same task format should run under a microVM.

## 2. Localization accuracy — `bench/scripts/localization_check.py`

Does the verdict's first user frame (or first error diagnostic) point at the ground-truth faulting
line? **10/10 tasks** (after three parser fixes found by this check: Rust ≥1.9x prints a thread id
in `thread 'main' (36) panicked at …`; unittest failures now carry the innermost frame in the code
under test, not the test file; ASan "attempting double-free" kind was cut at the first space).

| task | ground truth | verdict | via |
|---|---|---|---|
| c-heap-overflow | histogram.c:20 | histogram.c:20 | UBSan object-size load |
| c-use-after-free | list.c:21 | list.c:21 | ASan heap-use-after-free |
| c-stack-strcpy | greet.c:18 | greet.c:18 | ASan stack-buffer-overflow |
| c-double-free | pool.c:30 | pool.c:30 | ASan attempting double-free |
| c-null-deref | tokenizer.c:21 | tokenizer.c:21 | UBSan null member access |
| c-signed-overflow | checksum.c:5 | checksum.c:5 | UBSan signed overflow |
| cpp-vector-oob | grid.cpp:15 | grid.cpp:15 | ASan heap-buffer-overflow |
| rust-index-panic | main.rs:10 | main.rs:10 | rust-panic |
| py-unittest-crash | inventory.py:16/18/19 | inventory.py:16 | unittest failure (innermost frame) |
| c-compile-error | stats.c:49/50 | stats.c:49 | gcc diagnostic |

## 3. Parser robustness — `bench/scripts/fuzz_parsers.sh 300`

300 mutated inputs (byte flips, truncations, line shuffles, random bytes, 30× repeats, splices,
CRLF) → **0 failures**, every call exit 0 with a valid verdict; mean 4.5 ms per call including
process spawn, worst 18 ms.

## 4. Claude Code hook, live — nested headless session

A real `claude -p` (Claude Code 2.1.239, Windows host, model claude-haiku-4-5, 2 turns, \$0.03)
with the PostToolUse hook configured ran `cat asan.log`: the hook was invoked by Claude Code,
received `tool_response` as an **object** (not a `tool_output` string — the hook accepts both),
and replaced the 2 647-byte ASan report with a 544-byte verdict in **114 ms** (sbx in WSL via the
`SBX_WSL` bridge). Payload keys observed: `cwd, duration_ms, hook_event_name, permission_mode,
prompt_id, session_id, tool_input, tool_name, tool_response, tool_use_id, transcript_path`.
Hook log record: `{"bytes_in": 2647, "bytes_out": 544, "status": "crash", "sbx_ms": 114}`.
