#!/usr/bin/env bash
# Pilot on a local open-weight model through Ollama (no API key needed).
#   bash bench/scripts/ollama_pilot.sh [model=qwen2.5-coder:7b] [seeds=1] [conditions=all] [workers=1]
# Results -> bench/out/pilot-<model>.jsonl ; summary printed at the end.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
MODEL="${1:-qwen2.5-coder:7b}"
SEEDS="${2:-1}"
CONDS="${3:-raw,truncate30k,truncate10k,regex,structured,structured_delta}"
WORKERS="${4:-1}"     # local GPU: one episode at a time unless the model is tiny
MAX_TURNS="${5:-20}"
TAG="${6:-}"          # optional suffix to keep separate result sets (e.g. v2t20)
SLUG="$(echo "$MODEL" | tr ':/' '__')${TAG:+-$TAG}"
OUT="bench/out/pilot-$SLUG.jsonl"
mkdir -p bench/out
curl -s -m 5 "${OLLAMA_URL:-http://localhost:11434}/api/tags" >/dev/null || { echo "ollama not reachable at ${OLLAMA_URL:-http://localhost:11434}"; exit 2; }
export SBX_PROGRESS_DIR="bench/out/progress-$SLUG"
echo "model=$MODEL seeds=$SEEDS conditions=$CONDS workers=$WORKERS max_turns=$MAX_TURNS -> $OUT (progress: $SBX_PROGRESS_DIR)"
"$SBX_PY" bench/agent/run.py --model "ollama:$MODEL" --seeds "$SEEDS" --conditions "$CONDS" --workers "$WORKERS" \
  --max-turns "$MAX_TURNS" --out "$OUT" --trajectories "bench/out/traj-$SLUG"
