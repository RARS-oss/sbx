#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra pool.c -o pool || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./pool 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "add-find"        "add a\nadd b\nfind b\nfind z\n"          "1\n-1"
check "dump"            "add x\nadd y\ndump\n"                   "2: x y"
check "reset-then-use"  "add a\nadd b\nreset\ndump\nadd c\nfind c\ndump\n" "0:\n0\n1: c"
check "reset-empty"     "reset\ndump\n"                          "0:"
check "double-reset"    "add q\nreset\nreset\ndump\n"            "0:"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
