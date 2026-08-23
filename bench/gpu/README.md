# The strong-open-model experiment (rented 24 GB GPU)

The early pilots measured the wrong place: easy tasks hit a 4/4 ceiling, and small dumps a
strong model parses anyway. The value of typed feedback + **run-memory** shows up where the
work is actually hard — so this box runs a *middle* capability arm (a 32B open coder) between
the 3B/7B pilots and the frontier `claude-cli:` (Sonnet) arm, on **hard / noisy / long** tasks.

**Metric:** cache-aware **billed cost + turns over a whole session** — not bytes, not one fix.

## 1. Rent a box
A single **RTX 4090 (24 GB)** on **RunPod** or **Vast.ai** (~$0.3–0.7/hr). Pick an image that
already has the NVIDIA driver + CUDA (RunPod "PyTorch 2.x"; Vast "cuda:12.x"). Note its SSH
`host:port` and key.

## 2. One-command setup
On the pod:
```bash
curl -fsSL https://raw.githubusercontent.com/RARS-oss/sbx/main/bench/gpu/bootstrap.sh | bash
```
It builds `sbx`, installs vLLM, downloads the model, and serves an OpenAI-compatible endpoint at
`http://localhost:8000/v1`. Everything (sandbox + model + harness) runs on this one box.

- **Model:** `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ` (4-bit, ~19 GB — fits 24 GB).
  Long noisy logs? use `SBX_MODEL=Qwen/Qwen2.5-Coder-14B-Instruct-AWQ SBX_MAXLEN=32768` for room.
- **If vLLM OOMs / can't fit the KV cache:** `SBX_MAXLEN=4096 curl … | bash` (short context is fine —
  it makes the *raw* arm overflow, which is the point).
- Hosted pods on Ubuntu 24.04 restrict unprivileged user namespaces; the script lifts the AppArmor
  sysctl. If `sbx selftest` still fails, run the pod `--privileged` (RunPod: "Expose to host").

## 3. Run the experiment
```bash
export OPENAI_BASE_URL="http://localhost:8000/v1" OPENAI_API_KEY="x"
cd ~/sbx-gpu/sbx
# capability × condition matrix on the hard/noisy/long tasks
python bench/agent/run.py \
  --model "openai:Qwen/Qwen2.5-Coder-32B-Instruct-AWQ" \
  --conditions raw,structured,structured_delta \
  --tasks bench/tasks --seeds 3 --workers 1 --max-turns 20
python bench/agent/analyze.py bench/out/<run>.jsonl --md bench/out/gpu.md
```
`raw` = raw stdout (baseline); `structured` = typed verdict; `structured_delta` = verdict + delta +
**loop signals** (the run-memory arm). The frontier arm reuses `--model claude-cli:claude-sonnet-4-6`
on the same tasks — giving the full **7B → 32B → Sonnet** contrast.

## 4. Letting Claude drive it
Two ways:
- **SSH from the laptop:** add the pod to `~/.ssh/config` as host `sbxpod`; then Claude runs
  `ssh sbxpod "cd ~/sbx-gpu/sbx && …"` to provision, launch, and collect `bench/out/*.jsonl`.
- **Tunnel the endpoint** to the laptop (`ssh -L 8000:localhost:8000 sbxpod`) and run the harness
  locally against the remote model — but then `sbx` runs on the laptop's WSL, not the pod.
  Running everything on the pod (first option) is cleaner.

## What "value where it lives" looks like here
- **Hard tasks** (SWE-bench / ARVO via `bench/swe/swe_run.py`): where even the 32B stalls — headroom
  for the typed/run-memory arms to differ.
- **Huge noisy output** (200 KB CI logs, 5000-line failures, flakes): the `raw` arm overflows the 8 K
  context and burns tokens re-reading; the typed arm hands over a <1 KB verdict. See the noisy-log
  fixtures in `crates/feedback/tests/noisy.rs`.
- **Long sessions** (many runs per task): the delta + loop signals compound — anti-loop breaks the
  red-herring cycles that make a session long in the first place. Cost/turns are summed per session.

Honest reporting: if the 32B/Sonnet arms show **no** billed-cost win, we say so and keep the
model-agnostic claim (deterministic reproducible feedback + run-memory) + the proven cheap-model
turn-savings — see the repo README's positioning.
