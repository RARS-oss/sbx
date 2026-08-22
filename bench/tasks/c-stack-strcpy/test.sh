#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra greet.c -o greet || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./greet 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "simple"     "ada\n"                       "Hello, ADA!"
check "two-names"  "ada\nlinus\n"                "Hello, ADA!\nHello, LINUS!"
check "blank-skip" "\nalan\n\n"                  "Hello, ALAN!"
check "exact-31"   "abcdefghijklmnopqrstuvwxyz01234\n" "Hello, ABCDEFGHIJKLMNOPQRSTUVWXYZ01234!"
check "long-40-truncated" "abcdefghijklmnopqrstuvwxyz0123456789abcd\n" "Hello, ABCDEFGHIJKLMNOPQRSTUVWXYZ01234!"
check "very-long-120"  "$(printf 'x%.0s' $(seq 1 120))\n" "Hello, XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX!"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
