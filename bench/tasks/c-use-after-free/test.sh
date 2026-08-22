#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra list.c -o list || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./list 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "push-print"        "push 1\npush 2\npush 3\nprint\n"                 "[3 2 1]"
check "remove-head"       "push 1\npush 2\nremove 2\nprint\nsum\n"           "[1]\nsum=1"
check "remove-middle"     "push 1\npush 2\npush 3\nremove 2\nprint\nsum\n"   "[3 1]\nsum=4"
check "remove-tail"       "push 1\npush 2\npush 3\nremove 1\nprint\n"        "[3 2]"
check "remove-missing"    "push 5\nremove 9\nprint\n"                        "[5]"
check "remove-then-more"  "push 1\npush 2\npush 3\nremove 3\npush 4\nprint\nsum\n" "[4 2 1]\nsum=7"
check "duplicates-first-only" "push 7\npush 7\npush 7\nremove 7\nprint\n"   "[7 7]"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
