#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra checksum.c -o checksum || exit 1

fail=0
errf=$(mktemp)
inf=$(mktemp)
# Reference implementation of the spec (wrap-around modulo 2^32).
ref() { python3 -c 'import sys
h=0
for b in sys.stdin.buffer.read():
    h=(h*31+b)&0xffffffff
print("%08x"%h)' <"$inf"; }
check() {
  name=$1; printf "%b" "$2" >"$inf"
  expected=$(ref)
  out=$(./checksum <"$inf" 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$expected" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; echo "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "empty"     ""
check "abc"       "abc"
check "hello"     "hello"
check "binary"    "\\000\\001\\002\\377"
check "long-64"   "$(printf 'x%.0s' $(seq 1 64))"
check "long-200"  "$(printf 'The quick brown fox jumps over the lazy dog. %.0s' $(seq 1 5))"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
