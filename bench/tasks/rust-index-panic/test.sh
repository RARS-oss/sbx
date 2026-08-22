#!/bin/sh
set -u
export RUST_BACKTRACE=1
rustc --edition 2021 -g -o slmax main.rs 2>&1 || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./slmax 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "k1"        "1\n5\n3\n9\n"           "5\n3\n9"
check "k2"        "2\n1\n3\n2\n5\n4\n"     "3\n3\n5\n5"
check "k3"        "3\n4\n1\n7\n2\n8\n"     "7\n7\n8"
check "exact-k"   "3\n1\n2\n3\n"           "3"
check "too-few"   "4\n1\n2\n3\n"           ""
check "negatives" "2\n-5\n-1\n-9\n"        "-1\n-1"
check "k0"        "0\n1\n2\n"              ""

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
