#!/usr/bin/env bash
# Probe how many CC turns a single JSON-emitting reply costs when built-in tools are disabled.
set -u
SPF_WSL=/tmp/sbx-sp-test.txt
SPF_WIN='C:\Users\user\AppData\Local\Temp\sbx-sp-test.txt'
printf 'You fix bugs. Reply with EXACTLY one JSON object like {"name":"run","arguments":{}} and nothing else. You have no real tools.' > "$SPF_WSL"
cp "$SPF_WSL" /mnt/c/Users/user/AppData/Local/Temp/sbx-sp-test.txt
CLAUDE='C:\Users\user\.local\bin\claude.exe'
cd /mnt/c/Users/user
for MT in 1 2 3 4; do
  echo "=== max-turns $MT ==="
  printf 'The file a.c does not compile. Run the tests first.' | \
    cmd.exe /d /c "$CLAUDE" -p --output-format json --model claude-haiku-4-5 \
      --disallowed-tools Bash --disallowed-tools Read --disallowed-tools Edit \
      --disallowed-tools Write --disallowed-tools Glob --disallowed-tools Grep --disallowed-tools TodoWrite \
      --system-prompt-file "$SPF_WIN" --max-turns "$MT" 2>/dev/null | tr -d '\r' | \
    python3 -c '
import json,sys
raw=sys.stdin.read()
for l in raw.splitlines()[::-1]:
    l=l.strip()
    if l.startswith("{") and l.endswith("}"):
        d=json.loads(l); print("is_error",d.get("is_error"),"num_turns",d.get("num_turns"),"stop",d.get("stop_reason"),"result",repr(d.get("result"))[:140]); break
else:
    print("noparse",raw[-200:])'
done
