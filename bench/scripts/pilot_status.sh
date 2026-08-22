#!/usr/bin/env bash
# Status of running/finished pilots: records per file, current episode, progress lines, summary.
#   bash bench/scripts/pilot_status.sh [results.jsonl ...]
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
echo "time: $(date +%T)"
echo "--- running ---"
ps aux | grep "[a]gent.py --task" | sed 's/.*--task [^ ]*\/\([^ ]*\) --condition \([^ ]*\) --model \([^ ]*\).*/  \3  \1  \2/' | head -5
for p in bench/out/progress-*/; do
  [ -d "$p" ] || continue
  newest=$(ls -t "$p" 2>/dev/null | head -1)
  [ -n "$newest" ] && echo "  progress: $newest: $(cat "$p/$newest")"
done
echo "--- results ---"
files=("$@")
[ ${#files[@]} -eq 0 ] && files=(bench/out/pilot-*.jsonl)
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  n=$(wc -l < "$f")
  ok=$(python3 -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("success")))' "$f")
  echo "$f: $n records, $ok successes"
done
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  echo "=== summary: $f ==="
  "$SBX_PY" bench/agent/run.py --summary --out "$f" 2>/dev/null | head -40
done
