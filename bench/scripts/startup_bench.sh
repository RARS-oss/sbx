#!/usr/bin/env bash
# Startup-latency comparison on this machine: sbx (full profile) vs sbx --no-seccomp --no-loopback
# vs bubblewrap (equivalent namespaces, ro host binds) vs plain spawn. N runs each of /bin/true.
# Prints a JSON line per variant and a markdown table; used by the report.
#   bash bench/scripts/startup_bench.sh [N=30]
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
N="${1:-30}"
W=$(mktemp -d /tmp/sbx-startup.XXXXXX)
"$SBX_PY" - "$N" "$W" <<'PY'
import json, os, statistics as st, subprocess, sys, time, shutil
N = int(sys.argv[1]); W = sys.argv[2]
def timeit(cmd, n=N, warm=2):
    for _ in range(warm):
        subprocess.run(cmd, capture_output=True)
    xs = []
    for _ in range(n):
        t = time.perf_counter(); r = subprocess.run(cmd, capture_output=True); xs.append((time.perf_counter() - t) * 1000)
        if r.returncode not in (0,):
            return None, r.stderr.decode()[:200]
    xs.sort()
    return {"min": round(xs[0], 2), "median": round(xs[len(xs)//2], 2), "p90": round(xs[int(len(xs)*0.9)], 2), "mean": round(st.mean(xs), 2), "sd": round(st.pstdev(xs), 2)}, None
variants = {
    "plain spawn": ["/bin/true"],
    "sbx (full: ns+pivot_root+seccomp+lo)": ["sbx", "run", "--work", W, "--no-delta", "--", "/bin/true"],
    "sbx --no-seccomp --no-loopback": ["sbx", "run", "--work", W, "--no-delta", "--no-seccomp", "--no-loopback", "--", "/bin/true"],
}
if shutil.which("bwrap"):
    variants["bubblewrap (unshare-all, ro /usr, tmpfs /tmp, proc, dev)"] = ["bwrap", "--unshare-all", "--die-with-parent", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin", "--ro-bind", "/etc", "/etc", "--tmpfs", "/tmp", "--proc", "/proc", "--dev", "/dev", "--bind", W, "/work", "--chdir", "/work", "/bin/true"]
rows = []
for name, cmd in variants.items():
    stats, err = timeit(cmd)
    if stats is None:
        print(f"{name}: FAILED {err}"); continue
    rows.append((name, stats))
    print(json.dumps({"variant": name, "n": N, **stats}))
print("\n| variant | min ms | median ms | p90 ms | mean ± sd |")
print("|---|---|---|---|---|")
for name, s in rows:
    print(f"| {name} | {s['min']:.2f} | **{s['median']:.2f}** | {s['p90']:.2f} | {s['mean']:.2f} ± {s['sd']:.2f} |")
PY
rm -rf "$W"
