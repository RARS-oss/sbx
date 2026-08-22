#!/usr/bin/env bash
# For every task: the shipped (buggy) sources must FAIL `run`, and solution/ must PASS — both
# inside sbx. Prints one line per task and exits non-zero if any expectation is violated.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
command -v sbx >/dev/null || { echo "sbx not on PATH (build with: cargo build --release -p sbx-cli)"; exit 2; }

bad=0
for dir in bench/tasks/*/; do
  t=$(basename "$dir")
  [ -f "$dir/task.toml" ] || continue
  run_cmd=$(python3 -c 'import tomllib,sys; print(tomllib.load(open(sys.argv[1],"rb"))["run"])' "$dir/task.toml")
  # extra sbx flags from task.toml: ro_binds (host paths, ~ expanded) and env (KEY=VALUE)
  extra=$(python3 -c 'import tomllib,sys,os; t=tomllib.load(open(sys.argv[1],"rb")); h=os.path.expanduser("~")
print(" ".join(["--ro "+p.replace("~",h) for p in t.get("ro_binds",[])] + ["--env "+k+"="+str(v).replace("~",h) for k,v in t.get("env",{}).items()]))' "$dir/task.toml")
  w=$(mktemp -d /tmp/sbx-validate.XXXXXX)
  cp -r "$dir"/. "$w"/
  rm -rf "$w/solution" "$w/.sbx"
  # shellcheck disable=SC2086
  out_bug=$(sbx run --work "$w" --no-delta --json $extra -- sh -c "$run_cmd")
  st_bug=$(printf '%s' "$out_bug" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["verdict"]["status"], d["verdict"]["raw_bytes"])')
  cp -r "$dir"/solution/. "$w"/
  # shellcheck disable=SC2086
  out_fix=$(sbx run --work "$w" --no-delta --json $extra -- sh -c "$run_cmd")
  st_fix=$(printf '%s' "$out_fix" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["verdict"]["status"], d["verdict"]["raw_bytes"])')
  rm -rf "$w"
  verdict="OK"
  case "$st_bug" in pass*) verdict="BAD(buggy passes)"; bad=1;; esac
  case "$st_fix" in pass*) ;; *) verdict="BAD(solution fails)"; bad=1;; esac
  printf '%-22s buggy=%-28s solution=%-14s %s\n' "$t" "$st_bug" "$st_fix" "$verdict"
done
exit $bad
