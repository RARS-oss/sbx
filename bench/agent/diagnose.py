#!/usr/bin/env python3
"""Failure-mode diagnosis from saved trajectories (no model calls).

  python bench/agent/diagnose.py bench/out/traj-qwen2.5-coder_7b [--task c-heap-overflow] [--show 2]

Per condition: nudges, tool sequence shapes, how often a write was followed by a run, how often
the agent ever reached a better run status than its first run (progress), prose-only turns, and
the most common first/last tool. With --task, prints the tool sequence and the assistant prose
snippets of every episode for that task (what did the model *say* when it did not call a tool?).
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ORDER = {"setup_failed": 0, "timeout": 0, "crash": 1, "build_failed": 1, "runtime_error": 2, "tests_failed": 3, "pass": 4, "unknown": 0}


def load(d: Path):
    eps = []
    for p in sorted(d.glob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        eps.append((p.name, j["record"], j["trajectory"]))
    return eps


def summarize(eps, show_task: str | None, show: int):
    by_cond = defaultdict(list)
    for name, rec, tr in eps:
        by_cond[rec["condition"]].append((name, rec, tr))
    print(f"{'condition':<18}{'n':>3}{'succ':>5}{'nudges':>8}{'prose%':>8}{'writes':>8}{'runs':>6}{'w->run%':>9}{'progress%':>10}{'first tool':<12}{'last tool':<12}")
    for cond, rows in sorted(by_cond.items()):
        n = len(rows)
        succ = sum(1 for _, r, _ in rows if r["success"])
        nudges = [r.get("nudges", 0) for _, r, _ in rows]
        prose_turns = []
        writes = []
        runs = []
        w_then_run = []
        progress = []
        first_tools = Counter()
        last_tools = Counter()
        for _, r, tr in rows:
            tools = [e["tool"] for e in tr if "tool" in e]
            asst_turns = [e for e in tr if "assistant" in e]
            prose_only = sum(1 for e in asst_turns if not any(b.get("type") == "tool_use" for b in e["assistant"]))
            prose_turns.append(prose_only / max(1, len(asst_turns)))
            writes.append(tools.count("write_file"))
            runs.append(tools.count("run"))
            # write followed (eventually) by a run
            wr = 0
            for i, t in enumerate(tools):
                if t == "write_file" and "run" in tools[i + 1:]:
                    wr += 1
            w_then_run.append(wr / max(1, tools.count("write_file")) if tools.count("write_file") else 0)
            statuses = [x["status"] for x in r.get("runs", [])]
            if statuses:
                best = max(ORDER.get(s, 0) for s in statuses)
                progress.append(1 if best > ORDER.get(statuses[0], 0) else 0)
            else:
                progress.append(0)
            if tools:
                first_tools[tools[0]] += 1
                last_tools[tools[-1]] += 1
        print(f"{cond:<18}{n:>3}{succ:>5}{st.mean(nudges):>8.1f}{st.mean(prose_turns) * 100:>7.0f}%{st.mean(writes):>8.1f}{st.mean(runs):>6.1f}{st.mean(w_then_run) * 100:>8.0f}%{st.mean(progress) * 100:>9.0f}%  {first_tools.most_common(1)[0][0] if first_tools else '-':<12}{last_tools.most_common(1)[0][0] if last_tools else '-':<12}")
    # status progression table
    print("\nrun-status sequences (first -> last) per condition:")
    for cond, rows in sorted(by_cond.items()):
        c = Counter()
        for _, r, _ in rows:
            s = [x["status"] for x in r.get("runs", [])]
            c[(s[0] if s else "-") + " -> " + (s[-1] if s else "-")] += 1
        print(f"  {cond}: " + ", ".join(f"{k} ×{v}" for k, v in c.most_common(5)))
    if show_task:
        print(f"\n=== {show_task} ===")
        for name, rec, tr in eps:
            if rec["task"] != show_task:
                continue
            tools = [e["tool"] for e in tr if "tool" in e]
            print(f"\n[{rec['condition']}] success={rec['success']} turns={rec['turns']} nudges={rec.get('nudges')} runs={[x['status'] for x in rec.get('runs', [])]}")
            print("  tools:", " → ".join(tools) or "(none)")
            shown = 0
            for e in tr:
                if "assistant" in e:
                    texts = [b.get("text", "") for b in e["assistant"] if b.get("type") == "text" and b.get("text")]
                    calls = [b.get("name") for b in e["assistant"] if b.get("type") == "tool_use"]
                    if texts and shown < show:
                        shown += 1
                        print(f"  turn {e['turn']} prose ({'with' if calls else 'NO'} tool call): {texts[0][:220]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traj_dir", type=Path)
    ap.add_argument("--task", default=None)
    ap.add_argument("--show", type=int, default=2)
    a = ap.parse_args()
    eps = load(a.traj_dir)
    print(f"{len(eps)} trajectories in {a.traj_dir}")
    summarize(eps, a.task, a.show)


if __name__ == "__main__":
    main()
