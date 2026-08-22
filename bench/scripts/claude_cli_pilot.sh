#!/usr/bin/env bash
# Pilot using the Claude Code CLI as the model (no API key; OAuth login of the Windows session).
#   bash bench/scripts/claude_cli_pilot.sh [model=claude-haiku-4-5] [conditions] [seeds=1] [workers=2] [max_turns=10] [tag]
# Requires: claude.exe logged in on the Windows host; run from WSL (calls it via cmd.exe).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
MODEL="${1:-claude-haiku-4-5}"
CONDS="${2:-raw,structured_delta}"
SEEDS="${3:-1}"
WORKERS="${4:-2}"
MAX_TURNS="${5:-10}"
TAG="${6:-cli}"
SLUG="$(echo "$MODEL" | tr ':/' '__')-$TAG"
OUT="bench/out/pilot-$SLUG.jsonl"
mkdir -p bench/out
export SBX_PROGRESS_DIR="bench/out/progress-$SLUG"
echo "model=claude-cli:$MODEL conditions=$CONDS seeds=$SEEDS workers=$WORKERS max_turns=$MAX_TURNS -> $OUT"
"$SBX_PY" bench/agent/run.py --model "claude-cli:$MODEL" --conditions "$CONDS" --seeds "$SEEDS" --workers "$WORKERS" \
  --max-turns "$MAX_TURNS" --max-nudges 4 --out "$OUT" --trajectories "bench/out/traj-$SLUG"
