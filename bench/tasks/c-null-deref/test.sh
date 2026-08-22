#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra tokenizer.c -o tokenizer || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./tokenizer 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "three"     "a b c\n"          "3: a|b|c"
check "single"    "hello\n"          "1: hello"
check "empty"     "\n"               "0:"
check "spaces"    "   \n"            "0:"
check "leading"   "  lead\n"         "1: lead"
check "tabs"      "x\ty\t z\n"       "3: x|y|z"
check "multi"     "a b\n\nc\n"       "2: a|b\n0:\n1: c"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
