#!/bin/sh
set -u
CXX=${CXX:-g++}
$CXX -std=c++17 -g -O1 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra grid.cpp -o grid || exit 1

fail=0
errf=$(mktemp)
check() {
  name=$1; input=$2; expected=$3
  out=$(printf "%b" "$input" | ./grid 2>"$errf"); rc=$?
  if [ "$rc" -ne 0 ] || [ "$out" != "$(printf "%b" "$expected")" ]; then
    echo "FAIL $name (rc=$rc)"; echo "--- stdout ---"; echo "$out"; echo "--- stderr ---"; cat "$errf"; echo "--- expected ---"; printf "%b\n" "$expected"; fail=1
  else
    echo "ok   $name"
  fi
}

check "single-empty" "1 1\n.\n"              "0"
check "single-hash"  "1 1\n#\n"              "0"
check "row"          "1 3\n#.#\n"            "020"
check "square"       "2 2\n##\n##\n"         "33\n33"
check "cross"        "3 3\n.#.\n###\n.#.\n"  "333\n343\n333"
check "corner"       "3 3\n#..\n...\n..#\n"  "010\n121\n010"
check "wide"         "2 5\n#...#\n.....\n"   "01010\n11011"

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED"
exit $fail
