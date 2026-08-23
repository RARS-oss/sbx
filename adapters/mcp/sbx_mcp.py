#!/usr/bin/env python3
"""sbx as an MCP server.

Exposes the hermetic executor as two tools any MCP client (Claude Desktop, Cursor, Windsurf, Roo
Code, ...) can attach with one line of config — no custom hook:

  * run     — run a shell command in a throw-away sbx sandbox; returns the typed Verdict (+ a Delta
              vs the previous run in the same work dir, which sbx persists under <work>/.sbx/).
  * verdict — distill an existing captured log (e.g. a CI artifact) into the same typed Verdict.

The heavy lifting is `sbx` itself; this file is a thin, dependency-light wrapper (only the `mcp`
package). Configuration:

  SBX_BIN   path to the sbx binary            (default: "sbx" on PATH)
  SBX_WSL   "<distro>:<linux path to sbx>"    run sbx through WSL from a Windows host; the work dir
                                              is translated C:\\… -> /mnt/c/… (mirrors the bench harness)
  SBX_WORK  default work dir for `run`        (default: the client's cwd)

Run it directly for a stdio server:  python adapters/mcp/sbx_mcp.py
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _to_wsl_path(p: str) -> str:
    """C:\\Users\\X\\... -> /mnt/c/Users/X/... (reach a Windows path from a WSL process)."""
    p = str(p)
    if len(p) > 2 and p[1] == ":":
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p.replace("\\", "/")


def _base_argv(work: str, timeout: int, extra: list[str]) -> tuple[list[str], bool]:
    """Build the sbx argv, honoring the optional WSL bridge. Returns (argv, via_wsl)."""
    wsl = os.environ.get("SBX_WSL")
    if wsl and ":" in wsl:
        distro, linux_sbx = wsl.split(":", 1)
        return (["wsl.exe", "-d", distro, "--", linux_sbx, "run",
                 "--work", _to_wsl_path(work), "--timeout", str(timeout), *extra], True)
    sbx = os.environ.get("SBX_BIN", "sbx")
    return ([sbx, "run", "--work", work, "--timeout", str(timeout), *extra], False)


def sbx_run(command: str, cwd: str | None = None, timeout: int = 120) -> str:
    """Run `command` inside sbx and return the rendered typed verdict (+ delta). No LLM in the loop."""
    work = cwd or os.environ.get("SBX_WORK") or os.getcwd()
    argv, _ = _base_argv(work, timeout, ["--", "sh", "-c", command])
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout + 30)
    except FileNotFoundError:
        return ("error: `sbx` not found. Install it (cargo build --release -p sbx-cli) and set SBX_BIN, "
                "or set SBX_WSL=<distro>:<path-to-sbx> on a Windows host.")
    except subprocess.TimeoutExpired:
        return f"error: sbx timed out after {timeout}s"
    out = (r.stdout or "").strip()
    return out if out else (r.stderr or "").strip() or "(no output)"


def sbx_verdict(log_text: str, exit_code: int = 1) -> str:
    """Distill an already-captured log into the typed verdict (no execution)."""
    wsl = os.environ.get("SBX_WSL")
    if wsl and ":" in wsl:
        distro, linux_sbx = wsl.split(":", 1)
        argv = ["wsl.exe", "-d", distro, "--", linux_sbx, "verdict", "--raw", "-", "--exit", str(exit_code)]
    else:
        argv = [os.environ.get("SBX_BIN", "sbx"), "verdict", "--raw", "-", "--exit", str(exit_code)]
    try:
        r = subprocess.run(argv, input=log_text, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except FileNotFoundError:
        return "error: `sbx` not found (set SBX_BIN or SBX_WSL)."
    return (r.stdout or r.stderr or "(no output)").strip()


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit("The MCP SDK is required: pip install mcp  (or: uvx --from mcp ...). "
                         "See adapters/mcp/README.md.")
    mcp = FastMCP("sbx")

    @mcp.tool()
    def run(command: str, cwd: str = "", timeout: int = 120) -> str:
        """Run a shell command (build/test/execute) in a hermetic, deterministic sbx sandbox and
        return a compact TYPED verdict — parsed compiler diagnostics, sanitizer/crash object with the
        first user frame, failing tests by root cause — plus a DELTA vs your previous run in the same
        directory ("crash moved / SAME", "2 tests fixed, 1 new"). Prefer this over reading raw stdout.

        command: the shell command to run (e.g. "cargo test", "pytest -q", "go test ./...").
        cwd:     working directory (default: SBX_WORK or the server's cwd).
        timeout: seconds before the run is killed (default 120).
        """
        return sbx_run(command, cwd or None, timeout)

    @mcp.tool()
    def verdict(log: str, exit_code: int = 1) -> str:
        """Distill an already-captured build/test log (e.g. a CI artifact) into the same typed sbx
        verdict, without re-running anything. `log` is the raw text; `exit_code` is its process exit."""
        return sbx_verdict(log, exit_code)

    mcp.run()


if __name__ == "__main__":
    main()
