#!/usr/bin/env python3
"""Minimal, instrumented coding agent for the feedback-form experiment.

One episode = one task × one feedback condition × one model. The agent gets four tools
(read_file, write_file, run, done); `run` always executes the task's command inside sbx
(hermetic, identical across conditions) — only the *presentation* of the result differs:

  raw              stdout+stderr verbatim (+ exit line)
  truncate30k      Claude-Code-style middle truncation at 30 000 chars
  truncate10k      Codex-style head/tail: 256 lines or 10 KiB
  regex            RTK-style line-level compression (heuristics, no LLM)
  structured       sbx Verdict rendering (no delta)
  structured_delta sbx Verdict + Delta vs. the previous run in this episode

Orthogonal: --mask N keeps only the last N tool results verbatim and replaces older ones
with a placeholder (observation masking, Complexity Trap, Lindenbauer et al. 2025).

What gets measured (one JSON line per episode): API turns, tool calls, tokens by kind
(input / output / cache_read / cache_creation), billed cost from the public price list,
wall-clock, bytes produced by runs vs. bytes shown to the model, final success judged by
an independent sbx run of the task command after the agent stops, protected-file integrity.

Model: Claude via the official `anthropic` SDK (manual tool loop — we need full control
over observations). `--model mock` runs a scripted fake model to exercise the plumbing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import copy as _copy
import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# --------------------------------------------------------------------------- pricing (USD per 1M tokens)
PRICES = {
    # model: (input, output); cache read = 0.1 x input, cache write = 1.25 x input
    "claude-opus-5": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "mock": (0.0, 0.0),
}

CONDITIONS = ["raw", "truncate30k", "truncate10k", "regex", "structured", "structured_delta", "no_feedback"]

SYSTEM = """You are an expert software engineer fixing a bug in a small project inside a sandbox.
You have five tools: read_file, list_files, write_file, run, done.
- `list_files` lists the project's files — use it first on a multi-file project to find what to read.
- `run` builds and tests the project (it runs the project's fixed test command) and returns the result.
- Edit files only with write_file (write the complete new file content).
- Do not modify the test script or change the program's output format.
- Work iteratively: read the code, run, diagnose from the result, fix, run again.
- When the tests pass, call `done` with a one-sentence summary. If you cannot fix it, call `done` explaining why.
Be economical: do not re-read files you already have, and do not call run without having changed something."""

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a text file from the project. Returns its full content.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path relative to the project root"}}, "required": ["path"]},
    },
    {
        "name": "list_files",
        "description": "List the project's files (recursive tree, relative paths). Use it to explore a multi-file repository before reading or editing.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Subdirectory to list (default: project root)"}}, "additionalProperties": False},
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a text file in the project with the given complete content.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    },
    {
        "name": "run",
        "description": "Build and run the project's tests (the fixed test command). Returns the result of the run.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "done",
        "description": "Finish the episode. Call when the tests pass (or when you give up).",
        "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
    },
]


RUN_DESC_RAW = "Build and run the project's tests (the fixed test command). Returns the program's raw output (stdout+stderr) and the exit status."
RUN_DESC_TRUNC = "Build and run the project's tests (the fixed test command). Returns the program's output (long output is truncated in the middle/ends) and the exit status."
RUN_DESC_REGEX = "Build and run the project's tests (the fixed test command). Returns a compressed version of the program's output (noise lines removed) and the exit status."
RUN_DESC_STRUCTURED = (
    "Build and run the project's tests (the fixed test command). Returns a compact VERDICT instead of raw output:\n"
    "  [sbx] STATUS exit=N ...            overall result (PASS | BUILD FAILED | CRASH | TESTS FAILED | RUNTIME ERROR)\n"
    "  crash: <tool> <kind> (<access>)    the program crashed; `hint:` explains the kind; `at FILE:LINE in FUNC` is where it\n"
    "                                     happened in YOUR code (frames below, then `allocated at` / `freed at` when relevant)\n"
    "  diagnostics:                       compiler errors/warnings as FILE:LINE:COL: message\n"
    "  failing tests (...):               which checks failed, with expected vs got where available\n"
    "  output tail:                       last unparsed lines\n"
    "Everything shown is extracted from the real run; the full log path is given on the last line."
)
RUN_DESC_DELTA = RUN_DESC_STRUCTURED + (
    "\n  delta: ...                         what changed vs. your PREVIOUS run (diagnostics fixed/new, tests fixed/broken,\n"
    "                                     crash gone/new/moved/SAME). `crash: SAME as last run` means your edit did not affect the crash."
    "\n  loop: ...                          run-memory guard across your recent runs: `N runs in a row with the SAME verdict`\n"
    "                                     (your edits aren't landing — change locus) or `X has survived N runs` (that error is a\n"
    "                                     red herring, not the fix site). When you see a `loop:` line, stop repeating and try elsewhere."
)
RUN_DESC_NOFEEDBACK = "Build and run the project's tests (the fixed test command). Returns only whether the tests passed and the exit status — no program output."


def tools_for(condition: str) -> list:
    """Per-condition tool list: the `run` tool's description documents what its result looks like
    (part of the agent-computer interface of that condition); everything else is identical."""
    desc = {
        "raw": RUN_DESC_RAW,
        "truncate30k": RUN_DESC_TRUNC,
        "truncate10k": RUN_DESC_TRUNC,
        "regex": RUN_DESC_REGEX,
        "structured": RUN_DESC_STRUCTURED,
        "structured_delta": RUN_DESC_DELTA,
        "no_feedback": RUN_DESC_NOFEEDBACK,
    }.get(condition, RUN_DESC_RAW)
    out = []
    for t in TOOLS:
        if t["name"] == "run":
            out.append({**t, "description": desc})
        else:
            out.append(t)
    return out


# --------------------------------------------------------------------------- task loading
@dataclass
class Task:
    name: str
    dir: Path
    prompt: str
    run: str
    files: list[str]
    protected: list[str]
    timeout: int
    lang: str = ""
    family: str = ""
    bug: str = ""
    # Extra host paths bound read-only into the sandbox (toolchains) and env vars layered over
    # the hermetic profile (e.g. PATH extension, RUSTUP_HOME). Same for every condition.
    ro_binds: list = field(default_factory=list)
    env: dict = field(default_factory=dict)


def load_task(d: Path) -> Task:
    t = tomllib.loads((d / "task.toml").read_text())
    home = os.path.expanduser("~")
    return Task(
        name=t["name"], dir=d, prompt=t["prompt"].strip(), run=t["run"], files=t.get("files", []),
        protected=t.get("protected", []), timeout=int(t.get("timeout", 120)),
        lang=t.get("lang", ""), family=t.get("family", ""), bug=t.get("bug", ""),
        ro_binds=[p.replace("~", home) for p in t.get("ro_binds", [])],
        env={k: str(v).replace("~", home) for k, v in t.get("env", {}).items()},
    )


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


# --------------------------------------------------------------------------- observation shaping
def obs_raw(outcome: dict, cap: int = 120_000) -> str:
    exit_line = fmt_exit(outcome)
    body = outcome.get("stdout", "") + outcome.get("stderr", "")
    if len(body) > cap:
        body = body[:cap] + f"\n... [{len(body) - cap} chars not shown] ..."
    return f"{exit_line}\n{body}"


def fmt_exit(outcome: dict) -> str:
    e = outcome["exit"]
    k = e.get("kind")
    if k == "code":
        return f"[exit code {e['code']}]"
    if k == "signal":
        return f"[killed by {e['name']}]"
    if k == "timeout":
        return f"[timeout after {e['after_ms']} ms]"
    return f"[sandbox setup failed: {e.get('message')}]"


def obs_truncate_middle(outcome: dict, limit: int = 30_000) -> str:
    """Claude Code style: keep head and tail halves when output exceeds `limit` chars."""
    s = obs_raw(outcome, cap=10**9)
    if len(s) <= limit:
        return s
    half = limit // 2
    cut = len(s) - limit
    return s[:half] + f"\n\n... [{cut} characters truncated] ...\n\n" + s[-half:]


def obs_truncate_headtail(outcome: dict, max_lines: int = 256, max_bytes: int = 10_240) -> str:
    """Codex style: 256 lines or 10 KiB, head 128 + tail 128 lines."""
    s = obs_raw(outcome, cap=10**9)
    lines = s.splitlines()
    if len(lines) <= max_lines and len(s.encode()) <= max_bytes:
        return s
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines // 2):]
    out = "\n".join(head) + f"\n... [{len(lines) - max_lines} lines omitted] ...\n" + "\n".join(tail)
    if len(out.encode()) > max_bytes:
        b = out.encode()
        out = b[: max_bytes // 2].decode(errors="replace") + "\n... [bytes omitted] ...\n" + b[-max_bytes // 2:].decode(errors="replace")
    return out


_KEEP = re.compile(r"(error|warning|fail|FAIL|ERROR|assert|Assert|SUMMARY|==\d+==|^\s*#[0-3]\s|expected|got|rc=|exit|panicked|Traceback|Exception|ok   |ALL TESTS|runtime error|located|allocated by|freed by|READ of|WRITE of)")
_DROP = re.compile(r"(^\s*0x[0-9a-f]+: |^=>0x|Shadow byte|^\s*(Addressable|Partially addressable|Heap left|Freed heap|Stack |Global |Poisoned|Container|Array cookie|Intra object|ASan internal|Left alloca|Right alloca|Shadow gap)|^\s*#[4-9]\d*\s|^\s*#\d{2,}\s|^=+$)")


def obs_regex(outcome: dict, cap: int = 8_000) -> str:
    """RTK-style heuristic compressor: drop noise lines, collapse repeats, keep 'signal' lines."""
    s = obs_raw(outcome, cap=10**9)
    out: list[str] = []
    prev = None
    rep = 0
    for line in s.splitlines():
        if not line.strip():
            continue
        if _DROP.search(line):
            continue
        if not _KEEP.search(line) and len(line) > 200:
            line = line[:200] + "…"
        if line == prev:
            rep += 1
            continue
        if rep:
            out.append(f"  (previous line repeated {rep} more times)")
            rep = 0
        out.append(line)
        prev = line
    if rep:
        out.append(f"  (previous line repeated {rep} more times)")
    txt = "\n".join(out)
    if len(txt) > cap:
        txt = txt[: cap // 2] + "\n... [compressed output truncated] ...\n" + txt[-cap // 2:]
    return txt


def render_loop(ls: dict | None) -> str:
    """Python mirror of feedback::history::LoopSignals::render — the `loop:` anti-loop lines that
    the run-memory arm adds on top of the verdict + delta. Kept trivially in parity with the Rust."""
    if not ls:
        return ""
    out = ""
    vs = ls.get("verdict_streak", 0) or 0
    if vs >= 2:
        out += (f"loop: {vs} runs in a row with the SAME verdict — recent edits changed nothing; "
                "try a different locus\n")
    for s in ls.get("stuck", []) or []:
        out += (f"loop: {s.get('what')} has survived {s.get('streak')} runs unchanged — "
                "likely a red herring, not the fix site\n")
    return out


def shape(condition: str, sbx_json: dict, corrupt: dict | None = None) -> str:
    outcome = sbx_json["outcome"]
    if condition == "raw":
        return obs_raw(outcome)
    if condition == "truncate30k":
        return obs_truncate_middle(outcome, 30_000)
    if condition == "truncate10k":
        return obs_truncate_headtail(outcome)
    if condition == "regex":
        return obs_regex(outcome)
    if condition == "no_feedback":
        # Matched no-information control: the model learns only pass/fail + the exit line, never the
        # program's output. This is the honest denominator for "does the feedback content help".
        word = "PASS" if sbx_json["verdict"]["status"] == "pass" else "FAILED"
        return f"[sbx] {word}  {fmt_exit(outcome)}\n"
    if condition in ("structured", "structured_delta"):
        if corrupt and corrupt.get("mode"):
            # Hold execution byte-identical; mutate only the SHOWN verdict, consistently (so no
            # leftover raw line contradicts the lie), then render exactly as a truthful verdict.
            v = _copy.deepcopy(sbx_json["verdict"])
            apply_corruption(v, corrupt)
            d = sbx_json.get("delta") if condition == "structured_delta" else None
            return render_like_sbx(v, d)
        base = sbx_json["_rendered"]
        if condition == "structured_delta":
            # run-memory: append the anti-loop signals. Only the delta arm keeps state across the
            # episode's runs, so it is the only one that can warn "you're circling this red herring".
            base += render_loop(sbx_json.get("loop_signals"))
        return base
    raise ValueError(condition)


# --------------------------------------------------------------------------- sbx execution
def _within(child: Path, root: Path) -> bool:
    """True iff `child` is `root` or strictly inside it — a real path-boundary check, so a sibling
    like `<root>-evil/x` is NOT treated as inside `<root>` and `./x`/`a/../x` resolve correctly."""
    root, child = root.resolve(), child.resolve()
    return child == root or root in child.parents


def _to_wsl_path(p: str) -> str:
    """C:\\Users\\X\\... -> /mnt/c/Users/X/... (for reaching a Windows path from a WSL process)."""
    p = str(p)
    if len(p) > 2 and p[1] == ":":
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p.replace("\\", "/")


def sbx_run(workdir: Path, task: Task, keep_delta: bool) -> dict:
    """Run the task command inside sbx; return parsed JSON plus a rendered text (`_rendered`).

    SBX_WSL="<distro>:<linux path to sbx>" routes execution through WSL (for a Windows-Python
    orchestrator): the work dir and binds are translated to /mnt/<drive>/… paths.
    """
    cmd, timeout = task.run, task.timeout
    wsl = os.environ.get("SBX_WSL")
    if wsl and ":" in wsl:
        distro, linux_sbx = wsl.split(":", 1)
        base = ["wsl.exe", "-d", distro, "--", linux_sbx, "run", "--work", _to_wsl_path(str(workdir)), "--timeout", str(timeout)]
        for p in task.ro_binds:
            base += ["--ro", _to_wsl_path(p)]
        for k, v in task.env.items():
            base += ["--env", f"{k}={_to_wsl_path(v) if ('/' in v or '\\\\' in v) else v}"]
    else:
        base = ["sbx", "run", "--work", str(workdir), "--timeout", str(timeout)]
        for p in task.ro_binds:
            base += ["--ro", p]
        for k, v in task.env.items():
            base += ["--env", f"{k}={v}"]
    if not keep_delta:
        base.append("--no-delta")
    if os.environ.get("SBX_NO_SANDBOX"):
        # restricted host (unprivileged container / rented GPU pod): run directly, no namespaces.
        base.append("--no-sandbox")
    # JSON for metrics, text for the structured conditions. Two invocations would execute twice,
    # so we run once with --json and render the text from the saved state with `sbx verdict`.
    # sbx emits UTF-8 (…, —, box-drawing chars in verdicts). Decode as UTF-8 explicitly: the process
    # default is the console locale (cp1251 on RU Windows), whose reader thread crashes on bytes it
    # cannot map (e.g. 0x98) -> stdout becomes None -> json.loads(None). errors="replace" is a belt.
    j = subprocess.run(base + ["--json", "--", "sh", "-c", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        data = json.loads(j.stdout)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(f"sbx --json produced no JSON (rc={j.returncode}): {(j.stderr or '')[:500]}") from e
    # Render: verdict + delta -> text, using sbx's renderer on the captured raw log. We pass the
    # raw stderr+stdout back in and the previous verdict if delta is wanted; sbx run already wrote
    # .sbx/last.json (new verdict). For the render we need prev verdict *before* this run, which
    # `sbx run` overwrote — so we render from the JSON we have using the rust-identical text:
    data["_rendered"] = render_like_sbx(data["verdict"], data.get("delta"))
    return data


def hint_for(tool: str, kind: str):
    """Python mirror of feedback::render::hint_for (kept in parity by smoke_agent.sh)."""
    k = kind.lower()
    t = tool.lower()
    if "addresssanitizer" in t:
        if "heap-buffer-overflow" in k:
            return "read/write past the end (or before the start) of a heap allocation — check the index or length used at the frame below against the allocation size"
        if "stack-buffer-overflow" in k:
            return "read/write past the end of a local (stack) array — a fixed-size buffer is too small for the data copied into it; bound the copy"
        if "heap-use-after-free" in k:
            return "memory used after it was freed — the free site is listed below; the pointer must not be dereferenced after free (or the free must happen later)"
        if "double-free" in k:
            return "the same allocation freed twice — the second free is at the frame below; free once (null the pointer after freeing, or remove one free)"
        if "stack-use-after-return" in k or "stack-use-after-scope" in k:
            return "a pointer to a local variable is used after that variable's lifetime ended"
        if "segv" in k or "unknown address" in k:
            return "invalid memory access (often a NULL or uninitialised pointer) at the frame below"
        if "global-buffer-overflow" in k:
            return "read/write past the end of a global array — check the index against the array size"
        if "memory leak" in k:
            return "allocations never freed — see the allocation sites"
    if "undefinedbehaviorsanitizer" in t:
        if "insufficient space" in k or "misaligned" in k:
            return "out-of-bounds access: the address points past the end of the object (not an input-parsing problem) — check the index/bound at the frame below"
        if "signed integer overflow" in k:
            return "signed arithmetic overflowed (undefined in C/C++) — use unsigned or wider types where wrap-around is intended"
        if "null pointer" in k:
            return "a NULL pointer was dereferenced at the frame below — handle the empty/NULL case before using it"
        if "index" in k and "out of bounds" in k:
            return "array index out of bounds at the frame below — check the loop bound"
        if "division by zero" in k:
            return "integer division by zero at the frame below"
        if "shift" in k:
            return "invalid shift amount/operand (undefined behaviour) at the frame below"
    if t == "rust-panic":
        if "index out of bounds" in k:
            return "slice/array index beyond its length at the panic site — check the loop range or index arithmetic"
        if "unwrap" in k or "none" in k:
            return "unwrap()/expect() on None or Err at the panic site — handle the failing case"
        if "overflow" in k:
            return "arithmetic overflow in debug mode — use checked/wrapping ops or wider types"
    if t == "signal":
        if "SEGV" in kind or "SIGSEGV" in kind:
            return "segmentation fault: invalid memory access (no sanitizer report available — build with -fsanitize=address for the exact site)"
        if "ABRT" in kind:
            return "process aborted (assertion failure or allocator check)"
    return None


def apply_corruption(v: dict, spec: dict) -> int | None:
    """Mutate a verdict dict in place into a plausible-but-FALSE one, consistently, so the lie
    cannot be spotted from a leftover raw line. Execution is unchanged; only the presented verdict
    is altered. Returns the true (pre-corruption) fault line, for the record.

      spec = {"mode": "line", "decoy_line": N}   -> report the fault at line N instead of the truth
      spec = {"mode": "kind", "tool": T, "kind": K} -> report a different crash class (hint auto-follows)
    """
    c = v.get("crash")
    if not c:
        return None
    fuf = c.get("first_user_frame") or {}
    fname = (fuf.get("file") or "").split("/")[-1]
    true_line = fuf.get("line")
    if spec["mode"] == "line" and true_line is not None:
        decoy = int(spec["decoy_line"])
        fuf["line"] = decoy
        for fr in c.get("frames", []):
            if fr.get("user") and fr.get("line") == true_line:
                fr["line"] = decoy

        def scrub(s):
            if not s or not fname:
                return s
            return s.replace(f"{fname}:{true_line}:", f"{fname}:{decoy}:").replace(f"{fname}:{true_line} ", f"{fname}:{decoy} ")
        v["tail"] = [scrub(l) for l in v.get("tail", [])]
        if c.get("message"):
            c["message"] = scrub(c["message"])
        if c.get("summary"):
            c["summary"] = scrub(c["summary"])
        # Coherence: a diagnostic pointing at the true fault line would contradict the moved crash
        # frame and expose the lie (red-team B5). Move any such diagnostic to the decoy too.
        for dg in v.get("diagnostics", []):
            if (dg.get("file") or "").split("/")[-1] == fname and dg.get("line") == true_line:
                dg["line"] = decoy
            if dg.get("message"):
                dg["message"] = scrub(dg["message"])
    elif spec["mode"] == "kind":
        old = c.get("kind") or ""
        c["tool"] = spec.get("tool", c.get("tool"))
        c["kind"] = spec["kind"]
        # Sanitizer-specific tail phrasing cannot be faithfully rewritten into a different class,
        # so drop the raw sanitizer lines; the typed kind + auto-derived hint carry the (false) signal.
        sigs = ("AddressSanitizer", "UndefinedBehaviorSanitizer", "runtime error", "SUMMARY", "#0 ", "#1 ", "#2 ")
        v["tail"] = [l for l in v.get("tail", []) if not any(g in l for g in sigs)]
        # The concrete message describes the OLD class (e.g. "...insufficient space...") and render
        # prints it verbatim under an AddressSanitizer tool -> it would leak the true kind. Drop it.
        _ = old
        c["message"] = ""
        if c.get("summary"):
            c["summary"] = spec["kind"]
        # Drop diagnostics carrying the old sanitizer's runtime signature: a "load ... insufficient
        # space" diagnostic under a faked "use-after-free" kind would expose the lie (red-team B5/B6).
        san = ("runtime error", "insufficient space", "sanitizer", "-fsanitize", "AddressSanitizer", "UndefinedBehaviorSanitizer")
        v["diagnostics"] = [d for d in v.get("diagnostics", []) if not any(g in (d.get("message") or "").lower() for g in (x.lower() for x in san))]
    return true_line


def render_like_sbx(v: dict, d: dict | None) -> str:
    """Python port of feedback::render (kept in sync with render.rs; golden-tested in smoke)."""
    def loc(file, line, col):
        if file and line and col:
            return f"{file}:{line}:{col}"
        if file and line:
            return f"{file}:{line}"
        return file or "?"
    status_word = {"pass": "PASS", "tests_failed": "TESTS FAILED", "crash": "CRASH", "runtime_error": "RUNTIME ERROR", "build_failed": "BUILD FAILED", "timeout": "TIMEOUT", "setup_failed": "SANDBOX SETUP FAILED", "unknown": "UNKNOWN"}
    s = []
    head = f"[sbx] {status_word.get(v['status'], v['status'])}"
    if v.get("exit_code") is not None:
        head += f" exit={v['exit_code']}"
    if v.get("signal"):
        head += f" signal={v['signal']}"
    if v.get("wall_ms") is not None:
        head += f" wall={v['wall_ms']}ms"
    nerr = sum(1 for x in v["diagnostics"] if x["severity"] == "error")
    nwarn = sum(1 for x in v["diagnostics"] if x["severity"] == "warning")
    if nerr + nwarn:
        head += f" diagnostics={nerr}E/{nwarn}W in {v['error_groups']} group(s)"
    if v.get("tests"):
        t = v["tests"]
        head += f" tests={t['passed']}/{t['passed'] + t['failed'] + t['errors']} passed"
        if t["errors"]:
            head += f" ({t['errors']} errors)"
    head += f" raw={v['raw_bytes']}B"
    s.append(head)
    if d:
        parts = []
        if d.get("status_from") and d.get("status_to") and d["status_from"] != d["status_to"]:
            parts.append(f"status {status_word.get(d['status_from'])} -> {status_word.get(d['status_to'])}")
        if d["fixed"] or d["new"] or d["unchanged"]:
            parts.append(f"diagnostics: {len(d['fixed'])} fixed, {len(d['new'])} new, {d['unchanged']} unchanged")
        if d["tests_fixed"] or d["tests_broken"] or d["tests_still_failing"]:
            parts.append(f"tests: {len(d['tests_fixed'])} fixed, {len(d['tests_broken'])} newly failing, {d['tests_still_failing']} still failing")
        if d.get("crash_gone"):
            parts.append("crash: gone")
        if d.get("crash_new"):
            parts.append(f"crash: NEW {d['crash_new']}")
        if d.get("crash_moved"):
            parts.append(f"crash: moved {d['crash_moved']['from']} -> {d['crash_moved']['to']}")
        if d.get("crash_same"):
            parts.append("crash: SAME as last run (your change did not affect it)")
        if not parts:
            parts.append("no change vs last run")
        s.append("delta: " + "; ".join(parts))
        if d["new"]:
            s.append("new since last run:")
            for x in d["new"][:12]:
                s.append(fmt_diag(x, loc))
        if d["tests_broken"]:
            s.append("newly failing tests: " + ", ".join(d["tests_broken"]))
    c = v.get("crash")
    if c:
        line = f"crash: {c['tool']} {c['kind']}"
        if c.get("access"):
            line += f" ({c['access']})"
        if c.get("message"):
            if c["tool"] == "python":
                line += f": {c['message']}"
            elif c["tool"] == "UndefinedBehaviorSanitizer":
                rest = c["message"][len(c["kind"]):] if c["message"].startswith(c["kind"]) else c["message"]
                rest = rest.lstrip(":").strip()
                if rest:
                    line += f": {rest}"
        s.append(line)
        h = hint_for(c["tool"], c["kind"])
        if h:
            s.append(f"  hint: {h}")
        f = c.get("first_user_frame")
        if f:
            s.append(f"  at {loc(f.get('file'), f.get('line'), f.get('col'))} in {f.get('func') or '?'}")
        if c["frames"]:
            shown = 0
            ordered = [x for x in c["frames"] if x["user"]] + [x for x in c["frames"] if not x["user"]]
            for x in ordered:
                if shown >= 6:
                    s.append(f"  ... {len(c['frames']) - shown} more frames")
                    break
                if f and x == f and shown > 0:
                    continue
                s.append(f"  #{x['idx']} {x.get('func') or '?'} {loc(x.get('file'), x.get('line'), x.get('col'))}")
                shown += 1
        af = next((x for x in c["alloc_frames"] if x["user"]), None)
        if af:
            s.append(f"  allocated at {loc(af.get('file'), af.get('line'), af.get('col'))} in {af.get('func') or ''}")
        ff = next((x for x in c["free_frames"] if x["user"]), None)
        if ff:
            s.append(f"  freed at {loc(ff.get('file'), ff.get('line'), ff.get('col'))} in {ff.get('func') or ''}")
        if c.get("message") and c["tool"] == "AddressSanitizer":
            s.append(f"  {c['message']}")
    if v["diagnostics"]:
        sev_rank = {"error": 2, "warning": 1, "note": 0}
        lst = sorted(v["diagnostics"], key=lambda x: (-sev_rank[x["severity"]], x.get("file") or "", x.get("line") or 0))
        s.append("diagnostics:")
        for x in lst[:12]:
            s.append(fmt_diag(x, loc))
        if len(lst) > 12:
            s.append(f"  ... +{len(lst) - 12} more")
    t = v.get("tests")
    if t and t["failures"]:
        s.append(f"failing tests ({t['runner']}):")
        for x in t["failures"][:10]:
            line = f"  {x['name']}"
            if x.get("file"):
                line += f" @ {loc(x['file'], x.get('line'), None)}"
            if x.get("message"):
                line += f" — {x['message']}"
            s.append(line)
        if len(t["failures"]) > 10:
            s.append(f"  ... +{len(t['failures']) - 10} more")
    if v["tail"] and v["status"] != "pass":
        s.append("output tail:")
        for l in v["tail"][-6:]:
            s.append(f"  | {l}")
    s.append("(full log available on request: read_file .sbx/last.stderr)")
    return "\n".join(s) + "\n"


def fmt_diag(d: dict, loc) -> str:
    code = f" [{d['code']}]" if d.get("code") else ""
    return f"  {loc(d.get('file'), d.get('line'), d.get('col'))}: {d['severity']}{code}: {d['message']}"


# --------------------------------------------------------------------------- model clients
class MockModel:
    """Scripted fake: run -> write solution (if present) -> run -> done. Exercises the plumbing."""

    def __init__(self, task: Task):
        self.task = task
        self.step = 0

    def create(self, **kw):
        self.step += 1
        sol_dir = self.task.dir / "solution"
        sols = sorted(p for p in sol_dir.iterdir() if p.is_file()) if sol_dir.exists() else []
        usage = SimpleNamespace(input_tokens=1000 + 50 * self.step, output_tokens=120, cache_read_input_tokens=800 if self.step > 1 else 0, cache_creation_input_tokens=900 if self.step == 1 else 0)
        def tu(name, inp):
            return SimpleNamespace(type="tool_use", id=f"toolu_mock_{self.step}", name=name, input=inp)
        if self.step == 1:
            content = [SimpleNamespace(type="text", text="Let me run the tests first."), tu("run", {})]
        elif self.step == 2 and sols:
            content = [tu("write_file", {"path": sols[0].name, "content": sols[0].read_text()})]
        elif self.step == 3 and sols:
            content = [tu("run", {})]
        else:
            content = [tu("done", {"summary": "mock finished"})]
        return SimpleNamespace(content=content, stop_reason="tool_use", usage=usage, model="mock", stop_details=None)


class OllamaModel:
    """Local open-weight models through Ollama's native /api/chat with tool calling.

    Produces the same response shape as the Anthropic path (content blocks with type
    text|tool_use, stop_reason, usage) so the episode loop is provider-agnostic.
    Token accounting: prompt_eval_count -> input_tokens (Ollama reports *evaluated* prompt
    tokens, i.e. after its own KV-cache reuse), eval_count -> output_tokens; cost 0.
    """

    def __init__(self, name: str, url: str, num_ctx: int = 16384, temperature: float = 0.0):
        self.name = name
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.calls = 0

    @staticmethod
    def _to_ollama_messages(system: str, messages: list) -> list:
        out = [{"role": "system", "content": system}]
        for m in messages:
            role, content = m["role"], m["content"]
            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue
            if role == "assistant":
                text, calls = [], []
                for b in content:
                    bt = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
                    if bt == "text":
                        text.append(b["text"] if isinstance(b, dict) else b.text)
                    elif bt == "tool_use":
                        name = b["name"] if isinstance(b, dict) else b.name
                        inp = b["input"] if isinstance(b, dict) else b.input
                        calls.append({"function": {"name": name, "arguments": inp or {}}})
                msg = {"role": "assistant", "content": "\n".join(text)}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:  # user: tool results and/or text
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        out.append({"role": "tool", "content": str(b.get("content", ""))})
                    elif isinstance(b, dict) and b.get("type") == "text":
                        out.append({"role": "user", "content": b["text"]})
        return out

    @staticmethod
    def _extract_text_tool_calls(text: str, names: set) -> list:
        """Find {"name": <tool>, "arguments": {...}} objects in free text (incl. <tool_call> tags)."""
        out = []
        if not text or "{" not in text:
            return out
        s = text.replace("<tool_call>", " ").replace("</tool_call>", " ")
        i = 0
        while i < len(s):
            if s[i] != "{":
                i += 1
                continue
            depth, j, in_str, esc = 0, i, False, False
            while j < len(s):
                ch = s[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            chunk = s[i : j + 1]
            i = j + 1
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            name = obj.get("name") or obj.get("tool") or obj.get("function")
            if isinstance(name, dict):
                name = name.get("name")
            args = obj.get("arguments", obj.get("parameters", obj.get("input", {})))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            if name in names:
                out.append((name, args))
        return out

    def create(self, messages, system: str = SYSTEM, tools: list = TOOLS):
        import urllib.request

        self.calls += 1
        body = {
            "model": self.name,
            "messages": self._to_ollama_messages(system, messages),
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools],
            "stream": False,
            # num_predict bounds a runaway generation (small models can loop); 4096 tokens is
            # plenty for one tool call with a full file body.
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "num_predict": 2048},
        }
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read().decode())
        msg = data.get("message", {})
        content = []
        text = msg.get("content") or ""
        tool_calls = list(msg.get("tool_calls") or [])
        # Small models often emit the call as JSON *text* ({"name":..,"arguments":..}, possibly
        # wrapped in <tool_call> tags or several per message) instead of a structured tool_calls
        # field. Recover those; keep at most the first two calls so a "plan" of five calls does
        # not execute blindly.
        if not tool_calls:
            recovered = self._extract_text_tool_calls(text, {t["name"] for t in tools})
            if recovered:
                tool_calls = [{"function": {"name": n, "arguments": a}} for n, a in recovered]
                text = ""
        # One tool call per turn for local models: small models "plan" read+write+run in a single
        # message before seeing any result, which turns a feedback experiment into a test of
        # blind planning. Sequential execution keeps the loop observation-driven. Recorded in
        # the README; the Anthropic path keeps native parallel tool use.
        if len(tool_calls) > 1:
            tool_calls = tool_calls[:1]
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        for i, tc in enumerate(tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            if not isinstance(args, dict):
                args = {}
            content.append(SimpleNamespace(type="tool_use", id=f"call_{self.calls}_{i}", name=fn.get("name", ""), input=args))
        usage = SimpleNamespace(input_tokens=int(data.get("prompt_eval_count", 0) or 0), output_tokens=int(data.get("eval_count", 0) or 0), cache_read_input_tokens=0, cache_creation_input_tokens=0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else ("end_turn" if data.get("done_reason", "stop") == "stop" else data.get("done_reason", "end_turn"))
        return SimpleNamespace(content=content, stop_reason=stop, usage=usage, model=self.name, stop_details=None)


class OpenAICompatModel:
    """Any OpenAI-compatible chat-completions endpoint with tool calling — for hosted open
    models when the local GPU is too small (Groq, Cerebras, OpenRouter, Together, DashScope,
    vLLM/llama.cpp servers, …). Configure with OPENAI_BASE_URL (…/v1) and OPENAI_API_KEY.
    Same response shape as the other backends; cost 0 unless OPENAI_PRICE_IN/OUT ($/1M) are set.
    Raw HTTP (urllib) on purpose: no extra dependency, and provider quirks are visible.
    """

    def __init__(self, name: str, base_url: str | None = None, api_key: str | None = None, temperature: float = 0.0):
        self.name = name
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.temperature = temperature
        self.calls = 0

    @staticmethod
    def _to_openai_messages(system: str, messages: list) -> list:
        out = [{"role": "system", "content": system}]
        pending_tool_ids: list[str] = []
        for m in messages:
            role, content = m["role"], m["content"]
            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue
            if role == "assistant":
                text, calls = [], []
                for b in content:
                    bt = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
                    if bt == "text":
                        text.append(b["text"] if isinstance(b, dict) else b.text)
                    elif bt == "tool_use":
                        bid = b["id"] if isinstance(b, dict) else b.id
                        name = b["name"] if isinstance(b, dict) else b.name
                        inp = b["input"] if isinstance(b, dict) else b.input
                        calls.append({"id": bid, "type": "function", "function": {"name": name, "arguments": json.dumps(inp or {})}})
                msg = {"role": "assistant", "content": "\n".join(text) or None}
                if calls:
                    msg["tool_calls"] = calls
                    pending_tool_ids = [c["id"] for c in calls]
                out.append(msg)
            else:
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        out.append({"role": "tool", "tool_call_id": b.get("tool_use_id", pending_tool_ids[0] if pending_tool_ids else ""), "content": str(b.get("content", ""))})
                    elif isinstance(b, dict) and b.get("type") == "text":
                        out.append({"role": "user", "content": b["text"]})
        return out

    def create(self, messages, system: str = SYSTEM, tools: list = TOOLS):
        import urllib.request
        import urllib.error

        self.calls += 1
        body = {
            "model": self.name,
            "messages": self._to_openai_messages(system, messages),
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools],
            "tool_choice": "auto",
            "temperature": self.temperature,
            "max_tokens": 4096,
        }
        req = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise RuntimeError(f"HTTP {e.code} from {self.base_url}: {detail}") from e
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        content = []
        text = msg.get("content") or ""
        tool_calls = list(msg.get("tool_calls") or [])
        if not tool_calls:
            recovered = OllamaModel._extract_text_tool_calls(text, {t["name"] for t in tools})
            if recovered:
                tool_calls = [{"id": f"call_{self.calls}_{i}", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(recovered)]
                text = ""
        if len(tool_calls) > 1:
            tool_calls = tool_calls[:1]
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        for i, tc in enumerate(tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError:
                    args = {"_raw": args}
            content.append(SimpleNamespace(type="tool_use", id=tc.get("id") or f"call_{self.calls}_{i}", name=fn.get("name", ""), input=args if isinstance(args, dict) else {}))
        u = data.get("usage") or {}
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        usage = SimpleNamespace(input_tokens=int(u.get("prompt_tokens", 0) or 0) - int(cached), output_tokens=int(u.get("completion_tokens", 0) or 0), cache_read_input_tokens=int(cached), cache_creation_input_tokens=0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else ("end_turn" if choice.get("finish_reason") in (None, "stop") else str(choice.get("finish_reason")))
        return SimpleNamespace(content=content, stop_reason=stop, usage=usage, model=self.name, stop_details=None)


CLI_SYS_SUFFIX = """

=== OUTPUT PROTOCOL (read carefully — this overrides your usual behaviour) ===
This is a JSON-protocol harness, not a normal Claude Code session. You act ONLY by replying with
exactly ONE JSON object and NOTHING else — no prose, no explanation, no code fences. The harness
reads your JSON, performs the action for you, and sends back the result as the next message.

You DO have full ability to read, edit and run — you exercise it through the JSON, not through any
Claude Code tool. Never say you are unable to edit or that the system blocks file operations: to
change a file you simply emit a write_file JSON and the harness writes it. The five actions:

  {"name":"list_files","arguments":{}}
  {"name":"read_file","arguments":{"path":"histogram.c"}}
  {"name":"write_file","arguments":{"path":"histogram.c","content":"<the COMPLETE new file text>"}}
  {"name":"run","arguments":{}}
  {"name":"done","arguments":{"summary":"one sentence"}}

Rules: reply with one JSON object per turn; write_file must contain the entire new file, not a diff;
after you believe the fix is in, call run to check, and when the verdict shows the tests pass call
done. If you have diagnosed the fix, DO NOT describe it in prose — emit the write_file JSON that
applies it.

Example of the ONLY acceptable reply format (yours will differ in content):
{"name":"write_file","arguments":{"path":"histogram.c","content":"#include <stdio.h>\\nint main(void){return 0;}\\n"}}
Notice: no words before or after, no ```json fences — just the object."""


class ClaudeCLIModel:
    """Use the Claude Code CLI (claude.exe) as the model, driven turn-by-turn with --resume.

    No API key: the CLI authenticates with the interactive Windows session's OAuth login. On a
    Windows host with WSL, launching claude.exe via `cmd.exe /c` restores that credential context.
    The CLI's own tools are disabled; the model emits a JSON tool call as TEXT, which the harness
    parses and executes in sbx — so the loop, tools and conditions are ours, identical to the other
    backends. Multi-turn state lives in the CLI session; each turn sends only the newest message and
    uses a cumulative --max-turns.
    """

    DISABLED = ["Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch", "Task", "NotebookEdit", "TodoWrite"]

    def __init__(self, name: str, claude_path: str | None = None, via_cmd: bool | None = None):
        self.name = name
        self.claude = claude_path or os.environ.get("CLAUDE_BIN") or shutil.which("claude") or shutil.which("claude.exe") or "claude"
        # On Linux (WSL) reach the Windows exe through cmd.exe for credentials; on Windows call it directly.
        self.via_cmd = via_cmd if via_cmd is not None else (os.name != "nt")
        self.session: str | None = None
        # --max-turns is cumulative over the CLI session and, with built-in tools disabled, the
        # model burns a few internal turns attempting a tool before emitting text; give each of our
        # logical turns generous headroom so it reliably reaches the text answer.
        self.ceiling = 0
        self.headroom = int(os.environ.get("SBX_CLI_HEADROOM", "6"))
        self.spf: str | None = None
        self.calls = 0

    @staticmethod
    def _to_win_path(p: str) -> str:
        # /mnt/c/Users/... -> C:\Users\...  (for handing a WSL path to the Windows exe via cmd.exe)
        if p.startswith("/mnt/") and len(p) > 6:
            drive = p[5].upper()
            return drive + ":" + p[6:].replace("/", "\\")
        return p

    @staticmethod
    def _last_user_text(messages: list) -> str:
        m = messages[-1]
        c = m["content"]
        if isinstance(c, str):
            return c
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                parts.append(str(b.get("content", "")))
            elif isinstance(b, dict) and b.get("type") == "text":
                parts.append(b["text"])
        return "\n".join(parts) or "(continue)"

    def create(self, messages, system: str = SYSTEM, tools: list = TOOLS):
        self.calls += 1
        prompt = self._last_user_text(messages)
        argv = [self.claude, "-p", "--output-format", "json", "--model", self.name]
        for t in self.DISABLED:
            argv += ["--disallowed-tools", t]
        if self.session is None:
            sp = system + CLI_SYS_SUFFIX
            import tempfile as _tf
            fd, self.spf = _tf.mkstemp(prefix="sbx-sp-", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(sp)
            self.ceiling = self.headroom
            # The exe is Windows: on WSL the temp file is under /mnt/<drive>/… → convert to C:\…
            spf_arg = self._to_win_path(self.spf) if self.via_cmd else self.spf
            argv += ["--system-prompt-file", spf_arg, "--max-turns", str(self.ceiling)]
        else:
            self.ceiling += self.headroom
            argv += ["--resume", self.session, "--max-turns", str(self.ceiling)]

        if self.via_cmd:
            full = ["cmd.exe", "/d", "/c"] + argv
            cwd = os.environ.get("SBX_CLI_CWD", "/mnt/c")
        else:
            full = argv
            cwd = None
        import subprocess as sp_mod
        r = sp_mod.run(full, input=prompt.encode("utf-8"), capture_output=True, cwd=cwd, timeout=int(os.environ.get("SBX_CLI_TIMEOUT", "300")))
        raw = r.stdout.decode("utf-8", "replace").replace("\r", "")
        # The JSON result is the last {...} line; cmd.exe may prepend a UNC-cwd warning.
        data = None
        for line in raw.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            raise RuntimeError(f"claude CLI: no JSON result (rc={r.returncode}): {raw[-300:]} {r.stderr.decode(errors='replace')[-200:]}")
        if data.get("session_id"):
            self.session = data["session_id"]
        text = data.get("result") or ""
        if data.get("is_error") and not text:
            raise RuntimeError(f"claude CLI error: {data.get('subtype')} {data.get('result')}")
        content = []
        recovered = OllamaModel._extract_text_tool_calls(text, {t["name"] for t in tools})
        if recovered:
            n, a = recovered[0]
            content.append(SimpleNamespace(type="tool_use", id=f"cli_{self.calls}", name=n, input=a))
        elif text:
            content.append(SimpleNamespace(type="text", text=text))
        u = data.get("usage") or {}
        usage = SimpleNamespace(
            input_tokens=int(u.get("input_tokens", 0) or 0),
            output_tokens=int(u.get("output_tokens", 0) or 0),
            cache_read_input_tokens=int(u.get("cache_read_input_tokens", 0) or 0),
            cache_creation_input_tokens=int(u.get("cache_creation_input_tokens", 0) or 0),
        )
        usage.cost_usd = float(data.get("total_cost_usd", 0) or 0)
        stop = "tool_use" if recovered else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop, usage=usage, model=self.name, stop_details=None)


def make_client(model: str, task: Task, ollama_url: str = "http://localhost:11434"):
    if model == "mock":
        return MockModel(task)
    if model.startswith("ollama:"):
        return OllamaModel(model.split(":", 1)[1], ollama_url)
    if model.startswith("openai:"):
        return OpenAICompatModel(model.split(":", 1)[1])
    if model.startswith("claude-cli:"):
        return ClaudeCLIModel(model.split(":", 1)[1])
    import anthropic  # official SDK
    return anthropic.Anthropic()


def call_model(client, model: str, messages, effort: str, use_fallbacks: bool, tools=None):
    tools = tools or TOOLS
    if isinstance(client, MockModel):
        return client.create(messages=messages)
    if isinstance(client, (OllamaModel, OpenAICompatModel, ClaudeCLIModel)):
        return client.create(messages=messages, tools=tools)
    kw = dict(
        model=model,
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=tools,
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )
    if use_fallbacks and (model.startswith("claude-opus-5") or model.startswith("claude-fable-5")):
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
    return client.messages.create(**kw)


def block_to_dict(b) -> dict:
    if hasattr(b, "model_dump"):
        return b.model_dump()
    return {k: v for k, v in vars(b).items()}


def content_for_history(content) -> list:
    """Assistant content to append to history. Pass SDK blocks through unchanged (thinking blocks
    must be echoed back as-is); mock blocks are converted to plain dicts."""
    out = []
    for b in content:
        if hasattr(b, "model_dump"):
            out.append(b)
        else:
            d = {"type": b.type}
            if b.type == "text":
                d["text"] = b.text
            elif b.type == "tool_use":
                d.update(id=b.id, name=b.name, input=b.input)
            out.append(d)
    return out


# --------------------------------------------------------------------------- episode
@dataclass
class Metrics:
    turns: int = 0
    tool_calls: dict = field(default_factory=lambda: {"read_file": 0, "list_files": 0, "write_file": 0, "run": 0, "done": 0, "invalid": 0})
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    raw_bytes_total: int = 0
    shown_chars_total: int = 0
    runs: list = field(default_factory=list)  # per run: {status, raw_bytes, shown_chars, wall_ms}
    stop_reasons: list = field(default_factory=list)


def cost_of(model: str, usage) -> float:
    if hasattr(usage, "cost_usd"):
        return float(usage.cost_usd)  # provider-reported (Claude CLI)
    if model == "mock" or model.startswith("ollama:"):
        return 0.0
    if model.startswith("openai:"):
        # Hosted open models: price per 1M tokens from env (OPENAI_PRICE_IN / OPENAI_PRICE_OUT), else 0.
        try:
            pin, pout = float(os.environ.get("OPENAI_PRICE_IN", "0")), float(os.environ.get("OPENAI_PRICE_OUT", "0"))
        except ValueError:
            pin, pout = 0.0, 0.0
        i = getattr(usage, "input_tokens", 0) or 0
        o = getattr(usage, "output_tokens", 0) or 0
        cr = getattr(usage, "cache_read_input_tokens", 0) or 0
        return (i * pin + o * pout + cr * pin * 0.5) / 1e6
    pin, pout = PRICES.get(model, (5.0, 25.0))
    i = getattr(usage, "input_tokens", 0) or 0
    o = getattr(usage, "output_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (i * pin + o * pout + cr * pin * 0.1 + cw * pin * 1.25) / 1e6


def mask_old_tool_results(messages: list, keep_last: int) -> list:
    """Return a copy where all but the last `keep_last` tool_result contents are replaced."""
    if keep_last is None:
        return messages
    idxs = []
    for mi, m in enumerate(messages):
        if m["role"] == "user" and isinstance(m["content"], list):
            for ci, c in enumerate(m["content"]):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    idxs.append((mi, ci))
    to_mask = set(idxs[:-keep_last]) if keep_last > 0 else set(idxs)
    if not to_mask:
        return messages
    out = []
    for mi, m in enumerate(messages):
        if m["role"] == "user" and isinstance(m["content"], list):
            newc = []
            for ci, c in enumerate(m["content"]):
                if (mi, ci) in to_mask:
                    newc.append({**c, "content": "[earlier tool output omitted for brevity]"})
                else:
                    newc.append(c)
            out.append({**m, "content": newc})
        else:
            out.append(m)
    return out


def run_episode(task: Task, condition: str, model: str, effort: str, max_turns: int, mask: int | None, seed: int, use_fallbacks: bool, keep_workdir: bool, trajectory_path: Path | None, ollama_url: str = "http://localhost:11434", max_nudges: int = 2, require_run_before_edit: bool = False, corrupt: dict | None = None) -> dict:
    t0 = time.time()
    work = Path(tempfile.mkdtemp(prefix=f"sbx-ep-{task.name}-"))
    for p in task.dir.iterdir():
        if p.name in ("solution", ".sbx"):
            continue
        if p.is_dir():
            shutil.copytree(p, work / p.name)
        else:
            shutil.copy2(p, work / p.name)
    protected_hashes = {f: sha(work / f) for f in task.protected}

    client = make_client(model, task, ollama_url)
    m = Metrics()
    nudges = 0
    initial = task.prompt + "\n\nProject files: " + ", ".join(task.files) + f"\nTest command (run tool): `{task.run}`"
    messages: list[dict] = [{"role": "user", "content": initial}]
    trajectory: list[dict] = []
    keep_delta = condition == "structured_delta"
    done_summary = None
    final_stop = None

    infra_error = None
    ran_once = False
    truth_fault_line = None  # the line sbx's UN-corrupted verdict pointed at (for the steering metric)
    tools = tools_for(condition)
    # Budget = turns that actually call a tool. Prose-only / empty replies are nudged (bounded by
    # max_nudges) without consuming budget, so weak models are measured on what they do with the
    # feedback rather than on how often they forget to call a tool. Hard cap on API calls regardless.
    tool_turns = 0
    prose_turns = 0
    edits: list = []
    turn = -1
    while tool_turns < max_turns and turn < max_turns + max_nudges + 2:
        turn += 1
        sent = mask_old_tool_results(messages, mask) if mask is not None else messages
        try:
            resp = call_model(client, model, sent, effort, use_fallbacks, tools)
        except Exception as e:  # noqa: BLE001 — provider/network failure: retry once, then record
            try:
                time.sleep(5)
                resp = call_model(client, model, sent, effort, use_fallbacks, tools)
            except Exception as e2:  # noqa: BLE001
                infra_error = f"{type(e2).__name__}: {str(e2)[:200]}"
                trajectory.append({"turn": turn, "infra_error": infra_error, "first": f"{type(e).__name__}: {str(e)[:120]}"})
                break
        m.turns += 1
        m.input_tokens += getattr(resp.usage, "input_tokens", 0) or 0
        m.output_tokens += getattr(resp.usage, "output_tokens", 0) or 0
        m.cache_read_tokens += getattr(resp.usage, "cache_read_input_tokens", 0) or 0
        m.cache_creation_tokens += getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
        m.cost_usd += cost_of(model, resp.usage)
        m.stop_reasons.append(resp.stop_reason)
        final_stop = resp.stop_reason
        # Lightweight progress for long local runs (one line per turn, overwritten).
        if os.environ.get("SBX_PROGRESS_DIR"):
            try:
                pdir = Path(os.environ["SBX_PROGRESS_DIR"])
                pdir.mkdir(parents=True, exist_ok=True)
                (pdir / f"{task.name}__{condition}__m{mask}__s{seed}.txt").write_text(
                    f"turn={turn + 1} runs={m.tool_calls['run']} writes={m.tool_calls['write_file']} nudges={nudges} in_tok={m.input_tokens} out_tok={m.output_tokens} elapsed={time.time() - t0:.0f}s stop={resp.stop_reason}\n"
                )
            except Exception:
                pass
        trajectory.append({"turn": turn, "assistant": [block_to_dict(b) for b in resp.content], "stop_reason": resp.stop_reason})
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": content_for_history(resp.content)})
        if resp.stop_reason == "refusal":
            break
        if not tool_uses:
            # Smaller / open models sometimes answer in prose instead of calling a tool.
            # Nudge a bounded number of times (counted as turns) before giving up.
            prose_turns += 1
            if nudges < max_nudges:
                nudges += 1
                messages.append({"role": "user", "content": "Your last reply was prose, which does nothing here — the harness only acts on JSON. Reply now with ONLY one JSON object for the next action, e.g. {\"name\":\"write_file\",\"arguments\":{\"path\":\"…\",\"content\":\"…entire file…\"}} or {\"name\":\"run\",\"arguments\":{}}. No other text."})
                trajectory.append({"turn": turn, "nudge": nudges})
                continue
            break
        tool_turns += 1
        results = []
        stop = False
        for tu in tool_uses:
            name, inp = tu.name, (tu.input or {})
            if name == "read_file":
                m.tool_calls["read_file"] += 1
                p = (work / str(inp.get("path", ""))).resolve()
                if not _within(p, work) or not p.is_file():
                    res = f"error: no such file: {inp.get('path')}"
                else:
                    res = p.read_text(errors="replace")
            elif name == "list_files":
                m.tool_calls["list_files"] += 1
                base = (work / str(inp.get("path", ""))).resolve()
                if not _within(base, work) or not base.is_dir():
                    res = f"error: no such directory: {inp.get('path')}"
                else:
                    rels = []
                    for f in sorted(base.rglob("*")):
                        if f.is_file() and ".sbx" not in f.parts and ".git" not in f.parts:
                            rels.append(str(f.relative_to(work)).replace("\\", "/"))
                        if len(rels) >= 500:
                            rels.append("... (truncated at 500 files)")
                            break
                    res = "\n".join(rels) if rels else "(no files)"
            elif name == "write_file":
                m.tool_calls["write_file"] += 1
                rel = str(inp.get("path", ""))
                p = (work / rel).resolve()
                if require_run_before_edit and not ran_once:
                    # Force the buggy code to be executed at least once, so the run feedback is
                    # actually delivered before any edit (otherwise a strong model fixes straight
                    # from the source and never sees the feedback the experiment is about).
                    res = "error: run the tests first (call run) to see the current failure, then edit."
                    m.tool_calls["write_file"] -= 1
                    m.tool_calls["invalid"] += 1
                elif not _within(p, work):
                    res = "error: path outside project"
                elif p in {(work / x).resolve() for x in task.protected}:
                    # compare RESOLVED paths so `./test.sh` or `a/../test.sh` cannot slip past
                    res = f"error: {rel} is protected and must not be modified"
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    new_content = str(inp.get("content", ""))
                    old_content = p.read_text(errors="replace") if p.exists() else ""
                    # Which lines (of the new file) differ from the old one — lets the analysis
                    # ask "did the edit touch the faulting line?" without storing file bodies.
                    import difflib
                    changed = []
                    sm = difflib.SequenceMatcher(None, old_content.splitlines(), new_content.splitlines())
                    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
                        if tag != "equal":
                            changed.extend(range(j1 + 1, max(j2, j1 + 1) + 1))
                    p.write_text(new_content)
                    edits.append({"turn": turn, "path": rel, "changed_lines": changed[:200], "chars": len(new_content)})
                    res = f"wrote {rel} ({len(new_content)} chars)"
            elif name == "run":
                m.tool_calls["run"] += 1
                ran_once = True
                data = sbx_run(work, task, keep_delta)
                shown = shape(condition, data, corrupt)
                _fuf = (data["verdict"].get("crash") or {}).get("first_user_frame") or {}
                if _fuf.get("line") is not None:
                    truth_fault_line = _fuf.get("line")
                raw_bytes = data["verdict"]["raw_bytes"]
                m.raw_bytes_total += raw_bytes
                m.shown_chars_total += len(shown)
                vt = data["verdict"].get("tests") or {}
                vc = data["verdict"].get("crash") or {}
                m.runs.append({
                    "status": data["verdict"]["status"], "raw_bytes": raw_bytes, "shown_chars": len(shown), "wall_ms": data["outcome"]["wall_ms"],
                    "tests_failed": (vt.get("failed", 0) + vt.get("errors", 0)) if vt else None, "tests_passed": vt.get("passed") if vt else None,
                    "crash_kind": vc.get("kind"), "diag_errors": sum(1 for x in data["verdict"].get("diagnostics", []) if x["severity"] == "error"),
                })
                res = shown
            elif name == "done":
                m.tool_calls["done"] += 1
                done_summary = str(inp.get("summary", ""))
                res = "ok"
                stop = True
            else:
                m.tool_calls["invalid"] += 1
                res = f"error: unknown tool {name}"
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": res})
            trajectory.append({"turn": turn, "tool": name, "input": inp if name != "write_file" else {"path": inp.get("path"), "chars": len(str(inp.get("content", ""))), "changed_lines": (edits[-1]["changed_lines"] if edits and edits[-1]["turn"] == turn else [])}, "result_chars": len(res)})
        messages.append({"role": "user", "content": results})
        if stop:
            break

    # Independent verification: fresh sbx run of the task command, no delta state.
    verify = sbx_run(work, task, keep_delta=False)
    success = verify["verdict"]["status"] == "pass"
    protected_ok = all(sha(work / f) == h for f, h in protected_hashes.items())
    if not protected_ok:
        success = False
    wall = time.time() - t0
    rec = {
        "task": task.name, "family": task.family, "bug": task.bug, "lang": task.lang,
        "condition": condition, "mask": mask, "model": model, "effort": effort, "seed": seed,
        "success": success, "protected_ok": protected_ok, "final_status": verify["verdict"]["status"],
        "final_stop_reason": final_stop, "done_called": done_summary is not None, "done_summary": done_summary,
        "turns": m.turns, "tool_turns": tool_turns, "prose_turns": prose_turns, "nudges": nudges, "infra_error": infra_error,
        "ran_buggy_first": bool(m.runs) and m.runs[0]["status"] != "pass", "require_run_before_edit": require_run_before_edit,
        "corrupt": corrupt, "truth_fault_line": truth_fault_line,
        "shown_fault_line": (int(corrupt["decoy_line"]) if corrupt and corrupt.get("mode") == "line" else truth_fault_line),
        "tool_calls": m.tool_calls, "edits": edits,
        "tokens": {"input": m.input_tokens, "output": m.output_tokens, "cache_read": m.cache_read_tokens, "cache_creation": m.cache_creation_tokens},
        "cost_usd": round(m.cost_usd, 6), "wall_s": round(wall, 2),
        "raw_bytes_total": m.raw_bytes_total, "shown_chars_total": m.shown_chars_total, "runs": m.runs,
        "workdir": str(work) if keep_workdir else None,
    }
    if trajectory_path:
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_path.write_text(json.dumps({"record": rec, "trajectory": trajectory}, indent=1, default=str))
    if not keep_workdir:
        shutil.rmtree(work, ignore_errors=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, type=Path, help="task directory (contains task.toml)")
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--model", default="claude-opus-5", help="model id, or 'mock'")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-turns", type=int, default=25)
    ap.add_argument("--mask", type=int, default=None, help="keep only the last N tool results verbatim (observation masking)")
    ap.add_argument("--seed", type=int, default=0, help="bookkeeping only (API sampling is not seedable)")
    ap.add_argument("--no-fallbacks", action="store_true", help="do not request server-side refusal fallbacks on Opus 5 / Fable 5")
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--trajectory", type=Path, default=None, help="write full trajectory JSON here")
    ap.add_argument("--out", type=Path, default=None, help="append the episode record as one JSON line")
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"), help="Ollama server for --model ollama:<name>")
    ap.add_argument("--max-nudges", type=int, default=3, help="how many times to prompt a model that answered without a tool call")
    ap.add_argument("--run-before-edit", action="store_true", help="reject write_file until the tests have been run once, so the buggy-run feedback is delivered before any edit")
    ap.add_argument("--corrupt", choices=["none", "line", "kind"], default="none", help="(structured only) present a FALSE verdict: 'line' reports the fault at --decoy-line; 'kind' reports --as-kind. Execution is unchanged.")
    ap.add_argument("--decoy-line", type=int, default=None, help="with --corrupt line: the (wrong) line number to report as the fault site")
    ap.add_argument("--as-kind", type=str, default=None, help="with --corrupt kind: the (wrong) crash kind to report, e.g. heap-use-after-free")
    ap.add_argument("--as-tool", type=str, default="AddressSanitizer", help="with --corrupt kind: the tool to attribute the fake kind to")
    a = ap.parse_args()
    corrupt = None
    if a.corrupt == "line":
        if a.decoy_line is None:
            ap.error("--corrupt line requires --decoy-line")
        corrupt = {"mode": "line", "decoy_line": a.decoy_line}
    elif a.corrupt == "kind":
        if not a.as_kind:
            ap.error("--corrupt kind requires --as-kind")
        corrupt = {"mode": "kind", "kind": a.as_kind, "tool": a.as_tool}
    rec = run_episode(load_task(a.task), a.condition, a.model, a.effort, a.max_turns, a.mask, a.seed, not a.no_fallbacks, a.keep_workdir, a.trajectory, a.ollama_url, a.max_nudges, a.run_before_edit, corrupt)
    line = json.dumps(rec, default=str)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
