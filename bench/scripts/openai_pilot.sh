#!/usr/bin/env bash
# Pilot on an OpenAI-compatible hosted model (Groq / Cerebras / OpenRouter / DashScope / vLLM …).
#   export OPENAI_BASE_URL=https://api.groq.com/openai/v1 OPENAI_API_KEY=...
#   bash bench/scripts/openai_pilot.sh "<model id>" [seeds=1] [conditions=all] [workers=2] [max_turns=20] [tag=hosted]
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
MODEL="${1:?model id}"
SEEDS="${2:-1}"
CONDS="${3:-raw,truncate30k,truncate10k,regex,structured,structured_delta}"
WORKERS="${4:-2}"
MAX_TURNS="${5:-20}"
TAG="${6:-hosted}"
: "${OPENAI_BASE_URL:?set OPENAI_BASE_URL (…/v1)}"; : "${OPENAI_API_KEY:?set OPENAI_API_KEY}"
SLUG="$(echo "$MODEL" | tr ':/' '__')-$TAG"
OUT="bench/out/pilot-$SLUG.jsonl"
mkdir -p bench/out
export SBX_PROGRESS_DIR="bench/out/progress-$SLUG"
echo "model=$MODEL base=$OPENAI_BASE_URL seeds=$SEEDS conditions=$CONDS workers=$WORKERS max_turns=$MAX_TURNS -> $OUT"
"$SBX_PY" bench/agent/run.py --model "openai:$MODEL" --seeds "$SEEDS" --conditions "$CONDS" --workers "$WORKERS" \
  --max-turns "$MAX_TURNS" --out "$OUT" --trajectories "bench/out/traj-$SLUG"
