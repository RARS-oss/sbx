#!/usr/bin/env bash
# Robustness + cost of the distiller: feed N mutated/garbage inputs to `sbx verdict --raw -`
# (byte flips, truncations, line shuffles, pure random bytes, huge repeats) and assert it always
# exits 0 with a valid verdict; then time distillation on the largest real output.
#   bash bench/scripts/fuzz_parsers.sh [N=300]
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
N="${1:-300}"
"$SBX_PY" - "$N" <<'PY'
import json, os, random, subprocess, sys, time, glob
N = int(sys.argv[1]); random.seed(7)
fixtures = [open(p, "rb").read() for p in glob.glob("crates/feedback/tests/fixtures/*.txt")]
# add a real 36 KB ASan run if present
big = None
for p in glob.glob("bench/out/**/last.stderr", recursive=True):
    b = open(p, "rb").read()
    if big is None or len(b) > len(big): big = b
if big: fixtures.append(big)
def mutate(b: bytes) -> bytes:
    k = random.randrange(7)
    if k == 0:  # byte flips
        b = bytearray(b)
        for _ in range(max(1, len(b) // 50)):
            i = random.randrange(len(b)); b[i] = random.randrange(256)
        return bytes(b)
    if k == 1:  # truncate
        return b[: random.randrange(len(b) + 1)]
    if k == 2:  # shuffle lines
        ls = b.split(b"\n"); random.shuffle(ls); return b"\n".join(ls)
    if k == 3:  # random bytes
        return bytes(random.randrange(256) for _ in range(random.randrange(1, 4000)))
    if k == 4:  # repeat huge
        return b * random.randrange(2, 30)
    if k == 5:  # splice two fixtures
        o = random.choice(fixtures); i = random.randrange(len(b)); j = random.randrange(len(o)); return b[:i] + o[j:]
    return b.replace(b"\n", b"\r\n")  # CRLF
fails = 0; t_total = 0.0; worst = 0.0
for n in range(N):
    data = mutate(random.choice(fixtures))
    t = time.perf_counter()
    r = subprocess.run(["sbx", "verdict", "--raw", "-", "--exit", "1", "--json"], input=data, capture_output=True)
    dt = time.perf_counter() - t; t_total += dt; worst = max(worst, dt)
    ok = r.returncode == 0
    if ok:
        try:
            j = json.loads(r.stdout.decode()); ok = "verdict" in j and "status" in j["verdict"]
        except Exception: ok = False
    if not ok:
        fails += 1
        if fails <= 3:
            print("FAIL case:", r.returncode, r.stderr.decode(errors="replace")[:200])
print(f"fuzz: {N} inputs, {fails} failures, mean {t_total/N*1000:.1f} ms/call (incl. process spawn), worst {worst*1000:.0f} ms")
# distill cost on the biggest real output
if big:
    xs = []
    for _ in range(30):
        t = time.perf_counter(); subprocess.run(["sbx", "verdict", "--raw", "-", "--exit", "1"], input=big, capture_output=True); xs.append((time.perf_counter()-t)*1000)
    xs.sort(); print(f"distill {len(big)} B real sanitizer output: median {xs[len(xs)//2]:.1f} ms, p90 {xs[int(len(xs)*.9)]:.1f} ms (process spawn included)")
sys.exit(1 if fails else 0)
PY
