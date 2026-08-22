#!/bin/sh
# Build with AddressSanitizer; a 16-char value to the mis-guarded field overflows its 16-byte slot.
# The crashing run's ASan report is left on stderr (not captured) so the executor can parse it.
set -u
CC=${CC:-gcc}
$CC -g -O1 -fsanitize=address -fno-omit-frame-pointer -Wall fields.c -o fields || exit 1

# Positive checks first (these pass on a correct build): 15-char accepted, 16-char rejected cleanly.
out=$(printf "17 AAAAAAAAAAAAAAA\n5 hello\n" | ./fields); rc=$?
if [ "$rc" -ne 0 ] || [ "$out" != "$(printf 'ok 17\nok 5')" ]; then
  echo "FAIL positive rc=$rc"; echo "$out"; exit 1
fi

# Overflow trigger: 16-char value to field 17. On a correct build this is rejected (rc 0);
# on the buggy build ASan aborts and prints the report to stderr, which the verdict parses.
printf "17 AAAAAAAAAAAAAAAA\n" | ./fields >/dev/null
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "FAIL field-17 overflow (rc=$rc)"
  exit 1
fi
echo "ALL TESTS PASSED"
