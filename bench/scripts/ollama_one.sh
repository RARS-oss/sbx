#!/usr/bin/env bash
# One live episode on a local Ollama model, with the trajectory kept for inspection.
#   bash bench/scripts/ollama_one.sh qwen2.5-coder:3b c-heap-overflow structured_delta
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
MODEL="${1:-qwen2.5-coder:3b}"; TASK="${2:-c-heap-overflow}"; COND="${3:-structured_delta}"
mkdir -p bench/out
TRAJ="bench/out/one-$(echo "$MODEL" | tr ':/' '__')-$TASK-$COND.json"
"$SBX_PY" bench/agent/agent.py --task "bench/tasks/$TASK" --condition "$COND" --model "ollama:$MODEL" \
  --max-turns 15 --trajectory "$TRAJ" | python3 -c '
import json,sys
r=json.load(sys.stdin)
print("success:", r["success"], "| final:", r["final_status"], "| turns:", r["turns"], "| nudges:", r["nudges"], "| tools:", r["tool_calls"])
print("tokens in/out:", r["tokens"]["input"], r["tokens"]["output"], "| wall:", r["wall_s"], "s | shown/raw:", r["shown_chars_total"], "/", r["raw_bytes_total"])
print("runs:", [x["status"] for x in r["runs"]])
'
echo "trajectory: $TRAJ"
python3 - "$TRAJ" <<'PY'
import json,sys
t=json.load(open(sys.argv[1]))["trajectory"]
for e in t:
    if "assistant" in e:
        for b in e["assistant"]:
            if b.get("type")=="text" and b.get("text"): print(f"[turn {e['turn']}] TEXT: {b['text'][:160]!r}")
            if b.get("type")=="tool_use": print(f"[turn {e['turn']}] CALL {b['name']} {json.dumps(b.get('input'))[:120]}")
    elif "tool" in e:
        print(f"[turn {e['turn']}]   -> {e['tool']} result {e['result_chars']} chars")
    elif "nudge" in e:
        print(f"[turn {e['turn']}]   (nudge #{e['nudge']})")
PY
