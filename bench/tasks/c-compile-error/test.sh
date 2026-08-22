#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra stats.c -o stats || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./stats 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "basic"     "1\n2\n3\n4\n"        "min=1 max=4 mean=2.50"
check "single"    "7\n"                 "min=7 max=7 mean=7.00"
check "negative"  "-5\n5\n"             "min=-5 max=5 mean=0.00"
check "empty"     ""                    "no data"
check "rounding"  "1\n2\n"              "min=1 max=2 mean=1.50"
check "big"       "1000000\n2000000\n"  "min=1000000 max=2000000 mean=1500000.00"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
