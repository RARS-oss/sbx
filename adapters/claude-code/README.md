# Claude Code adapter

Two ways to use `sbx` from Claude Code. Both are opt-in and reversible.

## 1. PostToolUse hook — distil verbose Bash output (safe default)

`sbx_hook.py` runs after every Bash tool call. If the output is large (≥ 1500 bytes by
default) **and** `sbx` recognises structure in it (sanitizer/crash report, compiler
diagnostics, test results), the hook replaces what the model sees with the rendered verdict
plus a delta against the previous Bash call in the same directory. The full log stays on
disk at `<cwd>/.sbx/claude/last.log`, and the verdict's last line says so, so the model can
`cat`/`grep` it when it really needs the raw bytes.

If nothing structured is found, or anything fails, the hook exits 0 without JSON and Claude
Code shows the output exactly as it would have — the hook can only remove noise, never add it.

Install:

```bash
cargo install --path crates/sbx-cli          # puts `sbx` on PATH (or set SBX_BIN)
cp adapters/claude-code/settings.example.json .claude/settings.json   # or merge the "hooks" block
```

Telemetry for the experiment: set `SBX_HOOK_LOG=~/.sbx/hook.jsonl` and each call appends
`{bytes_in, bytes_out, status, delta, sbx_ms}` — the raw material for "tokens shown per tool
call" and, joined with the session transcript, "turns to fix".

Known limitation: PostToolUse does not expose the command's exit code, only
`tool_output_is_error`; the hook passes `--exit 0/1` accordingly. `sbx run` (below) has the
real exit code, signal and rusage.

### Windows host + WSL2 (tested)

Claude Code on Windows runs hooks with Windows Python; `sbx` lives in WSL. Set
`SBX_WSL="<distro>:<linux path to sbx>"` and the hook transparently runs
`wsl.exe -d <distro> -- <sbx> verdict --raw - --state ~/.sbx/claude/<project-hash> --json`,
keeping state and the full log inside the distro (the verdict's last line tells the model the WSL
path). Measured on this machine: 0.2 s per hook call including the WSL round-trip; 2 648 → 544
bytes on an ASan report; deltas work across calls. See `settings.windows.example.json`:

```json
{ "hooks": { "PostToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command",
  "command": "set SBX_WSL=Ubuntu:/home/<you>/.cache/sbx-target/release/sbx&& python adapters\\claude-code\\sbx_hook.py",
  "timeout": 30 } ] } ] } }
```

(Build sbx once in WSL: `cargo build --release -p sbx-cli`; adjust the path. If your hooks run
under PowerShell, use `$env:SBX_WSL='…'; python …` instead of `set …&&`.)

### Verified live (2026-08-23)

A nested headless session — `claude -p "Run … cat asan.log" --allowedTools Bash --model
claude-haiku-4-5` (Claude Code 2.1.239, Windows host) — with this hook configured: Claude Code
invoked the hook, the payload carried `tool_response` as an **object** (keys: `cwd, duration_ms,
hook_event_name, permission_mode, prompt_id, session_id, tool_input, tool_name, tool_response,
tool_use_id, transcript_path`; no string `tool_output` — the hook handles both shapes), and the
hook replaced the 2 647-byte ASan report with a 544-byte verdict in 114 ms through the WSL bridge
(`hook.jsonl`: `{"bytes_in": 2647, "bytes_out": 544, "status": "crash", "sbx_ms": 114}`).

## 2. PreToolUse hook — run build/test commands hermetically (opt-in, changes semantics)

A PreToolUse hook may rewrite the Bash command via `hookSpecificOutput.updatedInput.command`.
Wrapping selected commands as `sbx run --work "$cwd" -- sh -c '<command>'` gives the model
the full verdict with exit code/signal/timeout, no network, fixed environment and no ASLR.
This is the configuration used in the experiment's "structured + hermetic" arm; it is **not**
the default because it changes what commands can do (no network, `/work` mount, hermetic env).
See `docs/hermetic-profile.md` for exactly what changes.

A minimal rewrite hook (bash + jq), for commands that look like builds/tests:

```bash
#!/usr/bin/env bash
set -eu
input=$(cat)
cmd=$(jq -r '.tool_input.command' <<<"$input")
cwd=$(jq -r '.cwd' <<<"$input")
case "$cmd" in
  *pytest*|*"cargo test"*|*"cargo build"*|*make*|*ctest*|*gcc*|*clang*|*"go test"*)
    esc=$(printf '%s' "$cmd" | sed "s/'/'\\\\''/g")
    jq -n --arg c "sbx run --work '$cwd' --timeout 600 -- sh -c '$esc'" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",updatedInput:{command:$c}}}' ;;
  *) ;;   # anything else: no JSON, normal flow
esac
```

## What the model sees

Before (2.8 KB, shown here truncated):

```
=================================================================
==7==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7c3ff68e0038 at pc ...
WRITE of size 4 at 0x7c3ff68e0038 thread T0
    #0 0x5555555552d8 in fill /work/overflow.c:9
    ... 40 more lines of frames, shadow bytes and legend ...
```

After (≈ 600 B):

```
[sbx] CRASH exit=1 raw=2820B
delta: crash: moved heap-buffer-overflow @ /work/overflow.c:9 -> heap-use-after-free @ /work/uaf.c:15
crash: AddressSanitizer heap-use-after-free (READ of size 4)
  at /work/uaf.c:15 in sum
  #0 sum /work/uaf.c:15
  #1 main /work/uaf.c:27
  allocated at /work/uaf.c:22 in main
  freed at /work/uaf.c:26 in main
(full log: /work/.sbx/claude/last.log)
```
