#!/bin/sh
set -e
gcc -fsanitize=address -g -O0 hist.c -o hist
out=$(./hist)
echo "$out"
[ "$out" = "fives=3" ]
