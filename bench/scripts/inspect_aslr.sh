#!/usr/bin/env bash
# Why does crash identity differ under ASLR on a task? Print kind/first_user_frame/frames for K runs.
#   bash bench/scripts/inspect_aslr.sh c-heap-overflow 3
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
T="${1:-c-heap-overflow}"; K="${2:-3}"
W=$(mktemp -d /tmp/sbx-aslr.XXXXXX); cp -r "bench/tasks/$T"/. "$W"/; rm -rf "$W/solution"
for i in $(seq 1 "$K"); do
  sbx run --work "$W" --no-delta --aslr --json -- sh -c "sh test.sh" | python3 -c '
import json,sys
d=json.load(sys.stdin); c=d["verdict"]["crash"] or {}
print("ASLR run: kind=", c.get("kind"), "| access=", c.get("access"), "| first_user=", c.get("first_user_frame"))
print("   frames:", [(f.get("idx"), f.get("func"), f.get("file"), f.get("line"), f.get("user")) for f in c.get("frames", [])[:4]])
'
  rm -rf "$W/.sbx"; rm -f "$W"/histogram "$W"/list "$W"/greet "$W"/pool "$W"/checksum "$W"/stats "$W"/grid "$W"/main
done
echo "--- hermetic ---"
sbx run --work "$W" --no-delta --json -- sh -c "sh test.sh" | python3 -c '
import json,sys
d=json.load(sys.stdin); c=d["verdict"]["crash"] or {}
print("hermetic: kind=", c.get("kind"), "| first_user=", c.get("first_user_frame"))
print("   frames:", [(f.get("idx"), f.get("func"), f.get("file"), f.get("line"), f.get("user")) for f in c.get("frames", [])[:4]])
'
rm -rf "$W"
