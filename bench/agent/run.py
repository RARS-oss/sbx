#!/usr/bin/env python3
"""Experiment runner: tasks × conditions × seeds, N workers, resumable, with a summary table.

  python bench/agent/run.py --tasks bench/tasks --conditions raw,truncate30k,structured,structured_delta \
      --seeds 3 --model claude-opus-5 --effort high --out bench/out/pilot.jsonl --workers 3

Each episode is a subprocess call of agent.py (isolation: one crash cannot take the batch down).
Already-present (task, condition, mask, model, seed) records in --out are skipped, so the run
can be interrupted and resumed. `--summary` prints success / turns / cost / bytes per condition.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent


def key(r: dict) -> tuple:
    return (r["task"], r["condition"], r.get("mask"), r["model"], r.get("seed", 0))


def load_done(out: Path) -> set:
    s = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                try:
                    s.add(key(json.loads(line)))
                except Exception:
                    pass
    return s


def one(task: Path, cond: str, mask, model: str, effort: str, seed: int, out: Path, max_turns: int, traj_dir: Path | None, max_nudges: int | None = None, run_before_edit: bool = False) -> dict:
    cmd = [sys.executable, str(HERE / "agent.py"), "--task", str(task), "--condition", cond, "--model", model, "--effort", effort, "--seed", str(seed), "--max-turns", str(max_turns), "--out", str(out)]
    if mask is not None:
        cmd += ["--mask", str(mask)]
    if max_nudges is not None:
        cmd += ["--max-nudges", str(max_nudges)]
    if run_before_edit:
        cmd += ["--run-before-edit"]
    if traj_dir:
        cmd += ["--trajectory", str(traj_dir / f"{task.name}__{cond}__m{mask}__s{seed}.json")]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {"task": task.name, "condition": cond, "mask": mask, "model": model, "seed": seed, "error": p.stderr[-2000:]}
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"task": task.name, "condition": cond, "mask": mask, "model": model, "seed": seed, "error": "no JSON: " + p.stdout[-500:]}


def summarize(out: Path) -> None:
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if "error" not in r]
    if not rows:
        print("no records")
        return
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["condition"], r.get("mask"), r["model"]), []).append(r)
    print(f"{'condition':<18}{'mask':<6}{'model':<18}{'n':>4}{'success':>9}{'turns':>7}{'runs':>6}{'cost$':>9}{'in_tok':>9}{'cache%':>8}{'raw_B':>9}{'shown_ch':>10}{'ratio':>7}")
    for (cond, mask, model), rs in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][0], str(kv[0][1]))):
        n = len(rs)
        succ = sum(1 for r in rs if r["success"]) / n
        turns = st.mean(r["turns"] for r in rs)
        runs = st.mean(r["tool_calls"]["run"] for r in rs)
        cost = st.mean(r["cost_usd"] for r in rs)
        intok = st.mean(r["tokens"]["input"] + r["tokens"]["cache_read"] + r["tokens"]["cache_creation"] for r in rs)
        cache = st.mean((r["tokens"]["cache_read"] / max(1, r["tokens"]["input"] + r["tokens"]["cache_read"] + r["tokens"]["cache_creation"])) for r in rs) * 100
        rawb = st.mean(r["raw_bytes_total"] for r in rs)
        shown = st.mean(r["shown_chars_total"] for r in rs)
        ratio = shown / rawb if rawb else 0
        print(f"{cond:<18}{str(mask):<6}{model:<18}{n:>4}{succ:>9.0%}{turns:>7.1f}{runs:>6.1f}{cost:>9.4f}{intok:>9.0f}{cache:>7.0f}%{rawb:>9.0f}{shown:>10.0f}{ratio:>7.2f}")
    # per-task success matrix
    tasks = sorted({r["task"] for r in rows})
    conds = sorted({(r["condition"], r.get("mask")) for r in rows}, key=lambda cm: (cm[0], -1 if cm[1] is None else cm[1]))
    print("\nsuccess by task × condition:")
    print(f"{'task':<24}" + "".join(f"{c}{'' if m is None else f'/m{m}'}"[:16].ljust(17) for c, m in conds))
    for t in tasks:
        line = f"{t:<24}"
        for c, m in conds:
            rs = [r for r in rows if r["task"] == t and r["condition"] == c and r.get("mask") == m]
            line += (f"{sum(r['success'] for r in rs)}/{len(rs)}" if rs else "-").ljust(17)
        print(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=HERE.parent / "tasks")
    ap.add_argument("--only", default="", help="comma-separated task names")
    ap.add_argument("--conditions", default="raw,truncate30k,truncate10k,regex,structured,structured_delta")
    ap.add_argument("--masks", default="none", help="comma list, e.g. 'none,10' to also run masked variants")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-turns", type=int, default=25)
    ap.add_argument("--max-nudges", type=int, default=None)
    ap.add_argument("--run-before-edit", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", type=Path, default=HERE.parent / "out" / "results.jsonl")
    ap.add_argument("--trajectories", type=Path, default=None)
    ap.add_argument("--summary", action="store_true", help="only print the summary of --out")
    a = ap.parse_args()
    if a.summary:
        summarize(a.out)
        return
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tasks = sorted(p for p in a.tasks.iterdir() if (p / "task.toml").exists())
    if a.only:
        keep = set(a.only.split(","))
        tasks = [t for t in tasks if t.name in keep]
    conds = [c for c in a.conditions.split(",") if c]
    masks = [None if m == "none" else int(m) for m in a.masks.split(",")]
    done = load_done(a.out)
    jobs = []
    for seed in range(a.seeds):
        for t in tasks:
            for c in conds:
                for mk in masks:
                    if (t.name, c, mk, a.model, seed) in done:
                        continue
                    jobs.append((t, c, mk, seed))
    print(f"{len(jobs)} episodes to run ({len(done)} already done) -> {a.out}", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, t, c, mk, a.model, a.effort, seed, a.out, a.max_turns, a.trajectories, a.max_nudges, a.run_before_edit): (t, c, mk, seed) for (t, c, mk, seed) in jobs}
        for f in as_completed(futs):
            t, c, mk, seed = futs[f]
            r = f.result()
            if "error" in r:
                print(f"ERROR {t.name} {c} m{mk} s{seed}: …{r['error'][-400:]}", flush=True)
            else:
                print(f"{t.name:<22} {c:<17} m{str(mk):<5} s{seed} success={r['success']!s:<5} turns={r['turns']:<3} runs={r['tool_calls']['run']:<2} cost=${r['cost_usd']:.4f} shown/raw={r['shown_chars_total']}/{r['raw_bytes_total']}", flush=True)
    summarize(a.out)


if __name__ == "__main__":
    main()
