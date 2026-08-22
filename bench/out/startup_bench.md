# Startup latency: sbx vs bubblewrap vs plain spawn (2026-08-22, WSL2 6.6, 12 cores, n = 30)

Command: `bash bench/scripts/startup_bench.sh 30` (each variant runs `/bin/true`; 2 warm-up runs;
timed from Python with `perf_counter`, includes process spawn of the wrapper itself).

**Measured while the Qwen 3b pilot was saturating ~5.5 cores** (Ollama `llama-server` at 550 % CPU):

| variant | min ms | median ms | p90 ms | mean ± sd |
|---|---|---|---|---|
| plain spawn | 0.68 | **0.89** | 1.21 | 0.94 ± 0.15 |
| sbx (full: ns + pivot_root + mounts + seccomp + lo up + verdict) | 9.76 | **11.20** | 12.68 | 11.25 ± 0.96 |
| sbx --no-seccomp --no-loopback | 7.99 | **10.31** | 12.38 | 10.54 ± 1.61 |
| bubblewrap (unshare-all, ro /usr, tmpfs /tmp, proc, dev, bind /work) | 5.91 | **8.85** | 10.94 | 8.92 ± 1.67 |

Idle-machine numbers from `sbx bench` earlier the same day (in-process timing of `hermit_core::run`,
no CLI/JSON/verdict overhead): sandboxed `/bin/true` **4.59 ms** median (4.15 without seccomp/lo),
setup→exec 2.0 ms, plain spawn 0.56 ms.

Reading.
- Under load the whole machine is ~2× slower; the *ordering* is what matters: sbx's full profile costs
  ≈ bubblewrap + 2.4 ms, of which ≈0.9 ms is seccomp + netlink and the rest is the CLI path (JSON
  outcome, verdict distillation, state files) that bubblewrap does not do. Both are an order of
  magnitude below `docker run` (100–500 ms, published) and below gVisor's +40–150 ms overhead.
- Conclusion for the design: wrapping *every* compile/test invocation of an agent in sbx costs
  single-digit milliseconds — invisible next to a 150 ms gcc invocation or a multi-second model call.
- TODO before the report: re-run on an idle machine (after the pilots finish) and report those numbers
  as the headline, keeping this table as the "under load" column.
