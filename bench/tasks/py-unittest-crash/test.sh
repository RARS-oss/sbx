#!/bin/sh
# Runs the unittest suite verbosely; exit code is unittest's (0 iff all pass).
python3 -m unittest -v test_inventory.py 2>&1
rc=$?
[ "$rc" -eq 0 ] && echo "ALL TESTS PASSED"
exit $rc
