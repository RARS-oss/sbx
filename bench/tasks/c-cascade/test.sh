#!/bin/sh
set -u
CC=${CC:-gcc}
$CC -g -O1 -fsanitize=address -fno-omit-frame-pointer -Wall stats.c -o stats || exit 1
# n=5, values 10 20 30 40 50 -> mean=30, values >=30 are {30,40,50} = 3
out=$(printf "5\n10 20 30 40 50\n" | ./stats); rc=$?
if [ "$rc" -ne 0 ]; then echo "FAIL crash rc=$rc"; exit 1; fi
if [ "$out" != "mean=30 above=3" ]; then echo "FAIL wrong output: [$out] expected [mean=30 above=3]"; exit 1; fi
# a second case: n=3, values 1 2 9 -> mean=4, values >=4 = {9} = 1
out2=$(printf "3\n1 2 9\n" | ./stats); rc2=$?
if [ "$rc2" -ne 0 ] || [ "$out2" != "mean=4 above=1" ]; then echo "FAIL case2 rc=$rc2 out=[$out2]"; exit 1; fi
echo "ALL TESTS PASSED"
