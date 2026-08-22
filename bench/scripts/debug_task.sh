#!/usr/bin/env bash
# Run one task's buggy version inside sbx and dump raw lines matching a pattern plus the verdict
# crash/tests fields — for parser debugging.
#   bash bench/scripts/debug_task.sh rust-index-panic 'panicked|index out of|backtrace'
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
T="${1:?task}"; PAT="${2:-error|FAIL}"
W=$(mktemp -d /tmp/sbx-dbg.XXXXXX); cp -r "bench/tasks/$T"/. "$W"/; rm -rf "$W/solution"
extra=$(python3 -c 'import tomllib,sys,os; t=tomllib.load(open(sys.argv[1],"rb")); h=os.path.expanduser("~")
print(" ".join(["--ro "+p.replace("~",h) for p in t.get("ro_binds",[])] + ["--env "+k+"="+str(v).replace("~",h) for k,v in t.get("env",{}).items()]))' "$W/task.toml")
run_cmd=$(python3 -c 'import tomllib,sys; print(tomllib.load(open(sys.argv[1],"rb"))["run"])' "$W/task.toml")
# shellcheck disable=SC2086
sbx run --work "$W" --no-delta --json $extra -- sh -c "$run_cmd" > "$W/out.json"
python3 - "$W/out.json" "$PAT" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1])); pat = re.compile(sys.argv[2])
out = d["outcome"]["stdout"] + d["outcome"]["stderr"]
for l in out.splitlines():
    if pat.search(l):
        print("RAW:", repr(l[:140]))
v = d["verdict"]
c = v.get("crash")
print("status:", v["status"], "| crash:", c and {k: c[k] for k in ("tool", "kind", "first_user_frame")})
print("tests:", v.get("tests") and {k: v["tests"][k] for k in ("runner", "passed", "failed")}, "| failures:", [(f["name"], f.get("file"), f.get("line")) for f in (v.get("tests") or {}).get("failures", [])][:4])
print("tail:", v["tail"][:8])
PY
rm -rf "$W"
