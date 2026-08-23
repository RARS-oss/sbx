#!/usr/bin/env bash
# Turnkey setup for the sbx strong-open-model experiment on a rented 24 GB GPU (e.g. RTX 4090).
#
# Run on a fresh Ubuntu 22.04/24.04 pod that already has the NVIDIA driver + CUDA
# (RunPod "PyTorch 2.x" template, or a Vast.ai CUDA image). One command:
#
#     curl -fsSL https://raw.githubusercontent.com/RARS-oss/sbx/main/bench/gpu/bootstrap.sh | bash
#
# It: installs toolchains, builds `sbx`, creates a venv with vLLM + the harness deps,
# downloads the model, and launches an OpenAI-compatible endpoint that the harness
# (`agent.py`'s `openai:<model>` backend) talks to. Everything runs on this one box —
# the sandbox and the model share the machine, so there is no cross-host plumbing.
#
# Override via env: SBX_MODEL, SBX_VLLM_PORT, SBX_MAXLEN, SBX_GPU_UTIL.
set -euo pipefail

MODEL="${SBX_MODEL:-Qwen/Qwen2.5-Coder-32B-Instruct-AWQ}"   # ~19 GB in 4-bit AWQ; fits 24 GB
PORT="${SBX_VLLM_PORT:-8000}"
MAXLEN="${SBX_MAXLEN:-8192}"          # KV cache is tight for a 32B on 24 GB — lower to 4096 if OOM
UTIL="${SBX_GPU_UTIL:-0.90}"
ROOT="${SBX_ROOT:-$HOME/sbx-gpu}"

log() { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }
mkdir -p "$ROOT"; cd "$ROOT"

log "1/5  system deps"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq || apt-get update -qq
PKGS="git curl build-essential clang python3 python3-venv python3-pip pkg-config libssl-dev"
sudo apt-get install -y -qq $PKGS 2>/dev/null || apt-get install -y -qq $PKGS

log "2/5  rust + build sbx"
if ! command -v cargo >/dev/null 2>&1; then curl -fsSL https://sh.rustup.rs | sh -s -- -y; fi
. "$HOME/.cargo/env"
[ -d sbx ] || git clone --depth 1 https://github.com/RARS-oss/sbx.git
( cd sbx && cargo build --release -p sbx-cli )
export PATH="$ROOT/sbx/target/release:$PATH"
echo "sbx: $(sbx --version 2>/dev/null || echo built)"
# hosted GPU pods often restrict unprivileged userns via AppArmor (Ubuntu 24.04) — lift it
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 >/dev/null 2>&1 || true
sbx selftest 2>&1 | sed -n '1,2p' || echo "(selftest needs unprivileged user namespaces; see README if it fails)"

log "3/5  python venv: vLLM + harness"
python3 -m venv "$ROOT/venv"
. "$ROOT/venv/bin/activate"
pip install -q --upgrade pip
pip install -q vllm anthropic

log "4/5  launch vLLM (OpenAI-compatible), model=$MODEL"
pkill -f vllm.entrypoints.openai || true
nohup python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" --quantization awq --dtype float16 \
  --max-model-len "$MAXLEN" --gpu-memory-utilization "$UTIL" \
  --port "$PORT" > "$ROOT/vllm.log" 2>&1 &
echo "vLLM starting — first run downloads the model (a few minutes). Log: $ROOT/vllm.log"

log "5/5  wait for the endpoint"
up=0
for _ in $(seq 1 180); do
  if curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; then up=1; break; fi
  sleep 10
done
[ "$up" = 1 ] && echo "vLLM is UP at http://localhost:$PORT/v1" || { echo "vLLM not up yet — check $ROOT/vllm.log (OOM? lower SBX_MAXLEN)"; }

cat <<EOF

============================================================
 ready.  model served at  http://localhost:$PORT/v1   ($MODEL)

 run the experiment (venv active, from $ROOT/sbx):
   export OPENAI_BASE_URL="http://localhost:$PORT/v1" OPENAI_API_KEY="x"
   cd "$ROOT/sbx"
   python bench/agent/run.py --model "openai:$MODEL" \\
     --conditions raw,structured,structured_delta --seeds 3 --workers 1

 to also drive it from a laptop: expose the port over SSH
   ssh -L $PORT:localhost:$PORT <pod>        # then OPENAI_BASE_URL=http://localhost:$PORT/v1

 see bench/gpu/README.md for the full experiment matrix.
============================================================
EOF
