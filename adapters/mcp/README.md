# sbx as an MCP server

Attach the hermetic executor to any [MCP](https://modelcontextprotocol.io) client — Claude Desktop,
Cursor, Windsurf, Roo Code, Cline — so the model gets a **typed verdict + delta** instead of raw
stdout, with no custom hook. One file, one dependency (`mcp`).

## Tools it exposes

| Tool | What it does |
|---|---|
| `run(command, cwd?, timeout?)` | Run a shell command in a throw-away sbx sandbox; returns the typed Verdict as MCP **`structuredContent`** (behind an `outputSchema`): `{status, exit_code, crash{kind,first_user_frame,offset,…}, diagnostics[], tests{}, delta{}, rendered}` — the client reads the error as an object. `delta` is what changed vs your previous `run` in that dir (`crash SAME`, `2 tests fixed`). |
| `verdict(log, exit_code?)` | Distill an already-captured build/test log (e.g. a CI artifact) into the same typed verdict, without running anything. |

## Install

```bash
pip install mcp          # the MCP Python SDK
cargo build --release -p sbx-cli   # if you don't already have the sbx binary
```

## Configure (one block)

`command` runs the server over stdio. Point `SBX_BIN` at the `sbx` binary (or leave it if `sbx` is on
`PATH`). Config file per client: Claude Desktop → `claude_desktop_config.json`; Cursor → `~/.cursor/mcp.json`;
Windsurf → `~/.codeium/windsurf/mcp_config.json`; Cline/Roo → the extension's MCP settings.

**Linux / macOS (sbx on PATH or via `SBX_BIN`):**
```json
{
  "mcpServers": {
    "sbx": {
      "command": "python",
      "args": ["/abs/path/to/sandbox-executor/adapters/mcp/sbx_mcp.py"],
      "env": { "SBX_BIN": "/abs/path/to/sbx" }
    }
  }
}
```

**Windows host (sbx runs in WSL — the server bridges automatically):**
```json
{
  "mcpServers": {
    "sbx": {
      "command": "python",
      "args": ["C:\\path\\to\\sandbox-executor\\adapters\\mcp\\sbx_mcp.py"],
      "env": { "SBX_WSL": "Ubuntu:/home/<you>/.cache/sbx-target/release/sbx" }
    }
  }
}
```

Restart the client; you should see the `sbx` server with its `run` / `verdict` tools. Ask the agent to
"run the tests with sbx" and it will get the compact verdict.

## Environment

| Var | Meaning | Default |
|---|---|---|
| `SBX_BIN` | Path to the `sbx` binary | `sbx` on `PATH` |
| `SBX_WSL` | `<distro>:<linux path to sbx>` — run through WSL from Windows; work dir `C:\…` → `/mnt/c/…` | (off) |
| `SBX_WORK` | Default work dir for `run` | the server's cwd |

The verdict is deterministic (parsers, no LLM). See the top-level [README](../../README.md) and
[`docs/REPORT.md`](../../docs/REPORT.md) for what the verdict/delta contain and why determinism matters.
