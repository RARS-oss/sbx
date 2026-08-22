#!/usr/bin/env bash
# H3 micro-experiment: is the *raw* failing output byte-identical across repeated runs?
# Compares the hermetic profile (default: no ASLR, fixed env, fixed hostname) against the same
# run with ASLR left on (--aslr) and with the inherited environment (--inherit-env), on the
# sanitizer-heavy tasks. Also checks verdict/crash-identity stability (what deltas depend on).
#   bash bench/scripts/determinism.sh [K=10]
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
K="${1:-10}"
echo "| task | profile | distinct raw outputs over $K runs | distinct crash identities | distinct verdict texts | wall ms (median) |"
echo "|---|---|---|---|---|---|"
for t in c-use-after-free c-heap-overflow c-stack-strcpy c-double-free; do
  for profile in "hermetic" "aslr" "aslr+inherit-env"; do
    flags=""
    case "$profile" in
      aslr) flags="--aslr";;
      "aslr+inherit-env") flags="--aslr --inherit-env";;
    esac
    W=$(mktemp -d /tmp/sbx-det.XXXXXX); cp -r "bench/tasks/$t"/. "$W"/; rm -rf "$W/solution"
    raws=(); ids=(); texts=(); walls=()
    for i in $(seq 1 "$K"); do
      # shellcheck disable=SC2086
      j=$(sbx run --work "$W" --no-delta --json $flags -- sh -c "sh test.sh")
      raws+=("$(printf '%s' "$j" | python3 -c 'import json,sys,hashlib; d=json.load(sys.stdin); print(hashlib.sha256((d["outcome"]["stdout"]+d["outcome"]["stderr"]).encode()).hexdigest()[:12])')")
      ids+=("$(printf '%s' "$j" | python3 -c 'import json,sys; d=json.load(sys.stdin); c=d["verdict"].get("crash") or {}; f=c.get("first_user_frame") or {}; print(c.get("kind"), f.get("file"), f.get("line"))')")
      texts+=("$(printf '%s' "$j" | python3 -c 'import json,sys,hashlib; d=json.load(sys.stdin); v=d["verdict"]; v["wall_ms"]=None; print(hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()[:12])')")
      walls+=("$(printf '%s' "$j" | python3 -c 'import json,sys; print(json.load(sys.stdin)["outcome"]["wall_ms"])')")
      rm -rf "$W/.sbx"; rm -f "$W"/histogram "$W"/list "$W"/greet "$W"/pool 2>/dev/null
    done
    rm -rf "$W"
    nraw=$(printf '%s\n' "${raws[@]}" | sort -u | wc -l)
    nid=$(printf '%s\n' "${ids[@]}" | sort -u | wc -l)
    ntext=$(printf '%s\n' "${texts[@]}" | sort -u | wc -l)
    med=$(printf '%s\n' "${walls[@]}" | sort -n | sed -n "$(( (K+1)/2 ))p")
    echo "| $t | $profile | $nraw | $nid | $ntext | $med |"
  done
done
