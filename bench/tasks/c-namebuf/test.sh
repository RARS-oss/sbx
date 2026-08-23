#!/bin/sh
set -e
gcc -fsanitize=address -g -O0 gen.c -o gen
out=$(./gen)
echo "$out"
[ "$out" = "records=50 totlen=2229" ]
