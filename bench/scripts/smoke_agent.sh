#!/usr/bin/env bash
# Plumbing smoke test: run the agent in mock mode on every task × condition (+ one masked variant)
# and assert that every episode succeeds (the mock writes the reference solution).
# Also checks that the Python port of the verdict renderer matches `sbx verdict` on fixtures.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
out=$(mktemp /tmp/sbx-smoke.XXXXXX.jsonl)
rm -f "$out"
fail=0
for t in bench/tasks/*/; do
  for c in raw truncate30k truncate10k regex structured structured_delta; do
    rec=$("$SBX_PY" bench/agent/agent.py --task "$t" --condition "$c" --model mock --out "$out" 2>&1 | tail -1)
    ok=$(printf '%s' "$rec" | python3 -c 'import json,sys; r=json.loads(sys.stdin.read()); print("ok" if r["success"] else "FAIL", r["turns"], r["tool_calls"]["run"], r["raw_bytes_total"], r["shown_chars_total"])' 2>/dev/null || echo "FAIL(parse) $rec")
    printf '%-22s %-17s %s\n' "$(basename "$t")" "$c" "$ok"
    case "$ok" in ok*) ;; *) fail=1;; esac
  done
done
rec=$("$SBX_PY" bench/agent/agent.py --task bench/tasks/c-heap-overflow --condition structured --model mock --mask 1 --out "$out" 2>&1 | tail -1)
printf '%-22s %-17s %s\n' "c-heap-overflow" "structured/mask1" "$(printf '%s' "$rec" | python3 -c 'import json,sys; r=json.loads(sys.stdin.read()); print("ok" if r["success"] else "FAIL")')"

echo "--- renderer parity (python port vs sbx) ---"
for f in crates/feedback/tests/fixtures/*.txt; do
  rust=$(sbx verdict --raw "$f" --exit 1)
  py=$("$SBX_PY" - "$f" <<'PY'
import json, subprocess, sys
sys.path.insert(0, "bench/agent")
from agent import render_like_sbx
j = json.loads(subprocess.run(["sbx", "verdict", "--raw", sys.argv[1], "--exit", "1", "--json"], capture_output=True, text=True).stdout)
print(render_like_sbx(j["verdict"], j.get("delta")), end="")
PY
)
  # the footers intentionally differ (CLI vs agent tool hint); compare everything above the footer
  a=$(printf '%s\n' "$rust" | sed '$d'); b=$(printf '%s\n' "$py" | sed '$d')
  if [ "$a" = "$b" ]; then echo "parity ok   $(basename "$f")"; else echo "parity DIFF $(basename "$f")"; diff <(echo "$a") <(echo "$b") | head -20; fail=1; fi
done
echo "summary:"; "$SBX_PY" bench/agent/run.py --summary --out "$out" | head -12
rm -f "$out"
exit $fail
