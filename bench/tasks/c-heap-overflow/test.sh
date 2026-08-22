#!/bin/sh
# Build with sanitizers and check behaviour on a few inputs. Exit 0 iff all pass.
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra histogram.c -o histogram || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./histogram 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "basic"      "3\n0\n1\n1\n2\n2\n2\n"  "0: 1\n1: 2\n2: 3\ntotal=6"
check "empty"      "2\n"                    "0: 0\n1: 0\ntotal=0"
check "max-value"  "4\n3\n3\n"              "0: 0\n1: 0\n2: 0\n3: 2\ntotal=2"
check "out-of-range-ignored" "2\n0\n5\n1\n" "0: 1\n1: 1\ntotal=2"
check "boundary-N" "3\n3\n"                 "0: 0\n1: 0\n2: 0\ntotal=0"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
