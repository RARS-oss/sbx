#!/usr/bin/env bash
# Wait until no pilot runner (run.py --model ...) has been alive for IDLE_MIN consecutive minutes,
# then run the given command. Intended to be launched detached:
#   nohup setsid bash bench/scripts/queue_after_idle.sh 3 bash bench/scripts/ollama_pilot.sh qwen2.5-coder:7b 1 raw,structured 1 20 v2 > bench/out/queue.log 2>&1 < /dev/null &
set -uo pipefail
IDLE_MIN="${1:-3}"; shift
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
echo "$(date +%T) queued: $* (waiting for ${IDLE_MIN} idle minutes)"
idle=0
while [ "$idle" -lt "$IDLE_MIN" ]; do
  if pgrep -f "[r]un.py --model" >/dev/null; then idle=0; else idle=$((idle + 1)); fi
  sleep 60
done
echo "$(date +%T) starting: $*"
exec "$@"
