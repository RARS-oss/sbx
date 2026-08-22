#!/usr/bin/env python3
"""Claude Code PostToolUse hook: replace verbose Bash output with an sbx verdict (+ delta).

Wire it in .claude/settings.json (see settings.example.json next to this file):

    "PostToolUse": [{ "matcher": "Bash",
                      "hooks": [{ "type": "command", "command": "python3 /path/to/sbx_hook.py" }] }]

Behaviour (deliberately conservative — it only ever *replaces* output, never blocks):
  * reads the hook JSON from stdin; ignores anything that is not a Bash tool call;
  * extracts the tool output (``tool_output`` string, or ``tool_response`` object with
    stdout/stderr — both shapes are handled);
  * leaves small outputs alone (< SBX_HOOK_MIN_BYTES, default 1500) — nothing to gain;
  * runs ``sbx verdict --raw - --state <cwd>/.sbx/claude --json`` to distil + diff against
    the previous run in the same cwd; keeps the full log on disk and tells the model where;
  * replaces the output only when the verdict actually found structure (a crash, compiler
    diagnostics or test results). Otherwise the original output passes through untouched,
    so the hook can never make things worse than the harness default;
  * any failure -> exit 0 with no JSON (silent pass-through).

Environment:
  SBX_BIN               path to the sbx binary (default: "sbx" on PATH)
  SBX_HOOK_MIN_BYTES    minimum output size to bother (default 1500)
  SBX_HOOK_DISABLE=1    pass everything through
  SBX_HOOK_LOG=/path    append a one-line JSON record per call (bytes in/out, status) — telemetry
"""
import json
import os
import subprocess
import sys
import time


def passthrough() -> None:
    sys.exit(0)


def main() -> None:
    if os.environ.get("SBX_HOOK_DISABLE") == "1":
        passthrough()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        passthrough()
    if payload.get("tool_name") != "Bash":
        passthrough()

    # Output text: Claude Code's PostToolUse payload has carried either a string
    # ``tool_output`` or an object ``tool_response``; accept both.
    text = None
    is_error = bool(payload.get("tool_output_is_error", False))
    if isinstance(payload.get("tool_output"), str):
        text = payload["tool_output"]
    else:
        resp = payload.get("tool_response")
        if isinstance(resp, dict):
            out = resp.get("stdout") or ""
            err = resp.get("stderr") or ""
            text = (err + ("\n" if err and out else "") + out) if (out or err) else None
            is_error = bool(resp.get("is_error", is_error))
        elif isinstance(resp, str):
            text = resp
    if not text:
        passthrough()

    min_bytes = int(os.environ.get("SBX_HOOK_MIN_BYTES", "1500"))
    if len(text.encode("utf-8", "replace")) < min_bytes:
        passthrough()

    cwd = payload.get("cwd") or os.getcwd()
    # Windows host + WSL: SBX_WSL="<distro>:<linux path to sbx>" runs sbx inside WSL and keeps the
    # per-project state under the WSL home (no path translation needed); the full log is then at
    # ~/.sbx/claude/<project-hash>/last.log inside the distro.
    wsl = os.environ.get("SBX_WSL")
    if wsl and ":" in wsl:
        distro, linux_bin = wsl.split(":", 1)
        import hashlib
        h = hashlib.sha1(cwd.encode("utf-8", "replace")).hexdigest()[:10]
        state = f"/home/{os.environ.get('SBX_WSL_USER', 'user')}/.sbx/claude/{h}"
        cmd = ["wsl.exe", "-d", distro, "--", linux_bin, "verdict", "--raw", "-", "--state", state, "--json"]
    else:
        state = os.path.join(cwd, ".sbx", "claude")
        sbx = os.environ.get("SBX_BIN", "sbx")
        cmd = [sbx, "verdict", "--raw", "-", "--state", state, "--json"]
    # We do not know the real exit code in PostToolUse; is_error is the best proxy.
    cmd += ["--exit", "1" if is_error else "0"]
    try:
        t0 = time.time()
        res = subprocess.run(cmd, input=text.encode("utf-8", "replace"), capture_output=True, timeout=20)
        dt = time.time() - t0
        if res.returncode != 0:
            passthrough()
        data = json.loads(res.stdout.decode("utf-8", "replace"))
    except Exception:
        passthrough()

    verdict = data.get("verdict") or {}
    rendered = data.get("text") or ""
    structured = bool(verdict.get("crash")) or bool(verdict.get("diagnostics")) or bool(verdict.get("tests"))
    if not structured or not rendered:
        passthrough()
    # Never replace with something longer than the original.
    if len(rendered) >= len(text):
        passthrough()

    log = os.environ.get("SBX_HOOK_LOG")
    if log:
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": int(time.time()),
                    "cwd": cwd,
                    "bytes_in": len(text),
                    "bytes_out": len(rendered),
                    "status": verdict.get("status"),
                    "delta": bool(data.get("delta")),
                    "sbx_ms": int(dt * 1000),
                }) + "\n")
        except Exception:
            pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "toolOutput": rendered,
            "toolOutputIsError": is_error,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
