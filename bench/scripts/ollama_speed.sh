#!/usr/bin/env bash
# Token throughput of local Ollama models (generation tok/s, prompt tok/s, VRAM share).
#   bash bench/scripts/ollama_speed.sh qwen2.5-coder:3b qwen2.5-coder:7b
set -uo pipefail
URL="${OLLAMA_URL:-http://localhost:11434}"
for m in "$@"; do
  python3 - "$URL" "$m" <<'PY'
import json, sys, urllib.request
url, model = sys.argv[1], sys.argv[2]
body = {"model": model, "prompt": "Write a C function that reverses a string in place, then explain it in three sentences.", "stream": False, "options": {"num_predict": 160, "num_ctx": 4096}}
req = urllib.request.Request(url + "/api/generate", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=1800) as r:
    d = json.loads(r.read().decode())
if "error" in d:
    print(model, "ERROR", d["error"]); sys.exit(0)
ev, ed = d.get("eval_count", 0), d.get("eval_duration", 1) / 1e9
pv, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 1) / 1e9
print(f"{model}: generation {ev/ed:.1f} tok/s ({ev} tok in {ed:.1f}s) | prompt {pv/pd:.0f} tok/s ({pv} tok in {pd:.2f}s) | load {d.get('load_duration',0)/1e9:.1f}s")
ps = json.loads(urllib.request.urlopen(url + "/api/ps").read().decode())
for mm in ps.get("models", []):
    if mm["name"] == model:
        print(f"   vram {mm.get('size_vram',0)//1048576} MiB of {mm.get('size',0)//1048576} MiB ({100*mm.get('size_vram',0)/max(1,mm.get('size',1)):.0f}% on GPU)")
PY
done
