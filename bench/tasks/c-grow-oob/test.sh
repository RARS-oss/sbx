#!/bin/sh
set -e
gcc -fsanitize=address -g -O0 gen.c -o gen
out=$(./gen)
echo "$out"
[ "$out" = "total=335 sum=42445" ]
