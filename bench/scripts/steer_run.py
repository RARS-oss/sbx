#!/usr/bin/env python3
"""Causal verdict-steering experiment runner.

Serial by necessity (the Claude CLI deadlocks on concurrent claude.exe). Each episode is a fresh
agent.py subprocess, i.e. an independent CLI session -> no cross-arm memory bleed (red-team Q1.8).
Execution inside sbx is byte-identical across arms; only the post-run feedback text differs, so any
behavioural difference is attributable to the feedback alone.

Clean tasks only: single unambiguous fix, with an expert-plausible, causally-inert decoy line of the
SAME syntactic class as the true fault, > 2k lines from the fix (red-team Q1.3/Q1.4/Q3).
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # sandbox-executor/

# task -> decoy line (a real, same-class, causally-inert statement, far from the fix)
#   c-heap-overflow : fix 16, crash 20 (counts[v]++ load); decoy 24 = counts[i] load, i bounded
#   c-use-after-free: fix 28->29 (return head after free); decoy 37 = s += n->value in sum()
#   c-null-deref    : fix 19->20 (guard head==NULL); decoy 45 = t->text deref in print_and_free
#   cpp-vector-oob  : fix 14 (>=rows/cols); decoy 26 = cin >> g[r] (same container, r bounded->inert)
TASKS = {
    "c-heap-overflow": 24,
    "c-use-after-free": 37,
    "c-null-deref": 45,
    "cpp-vector-oob": 26,
    # "haystack": 24 near-identical bounds guards, one off-by-one (field 17, line 27). Self-
    # verification is expensive here, so the verdict's line is load-bearing even for a strong model.
    # decoy 15 = field 5's guard (correct, causally inert), 12 lines from the fix.
    "c-haystack-oob": 15,
}

PRIO = {"truth": 0, "corrupt_line": 1, "corrupt_kind": 2, "no_feedback": 3, "raw": 4}

# corrupt_kind: swap the crash CLASS to a different, plausible one that misdirects the fix strategy
#   heap-overflow (OOB)   -> use-after-free  (pushes toward the free() at line 27, not the bound)
#   use-after-free        -> heap-buffer-overflow (pushes toward indexing, not lifetime)
#   null-deref            -> heap-buffer-overflow (pushes toward bounds, not the NULL guard)
#   vector-oob (overflow) -> heap-use-after-free (pushes toward lifetime, not the bound)
KINDSWAP = {
    "c-heap-overflow": ("AddressSanitizer", "heap-use-after-free"),
    "c-use-after-free": ("AddressSanitizer", "heap-buffer-overflow"),
    "c-null-deref": ("AddressSanitizer", "heap-buffer-overflow"),
    "cpp-vector-oob": ("AddressSanitizer", "heap-use-after-free"),
    "c-haystack-oob": ("AddressSanitizer", "heap-use-after-free"),
}


def arm_args(arm: str, task: str, decoy: int) -> list:
    if arm == "truth":
        return ["--condition", "structured_delta"]
    if arm == "corrupt_line":
        return ["--condition", "structured_delta", "--corrupt", "line", "--decoy-line", str(decoy)]
    if arm == "corrupt_kind":
        tool, kind = KINDSWAP[task]
        return ["--condition", "structured_delta", "--corrupt", "kind", "--as-kind", kind, "--as-tool", tool]
    if arm == "no_feedback":
        return ["--condition", "no_feedback"]
    if arm == "raw":
        return ["--condition", "raw"]
    raise ValueError(arm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-cli:claude-sonnet-4-6")
    ap.add_argument("--arms", default="truth,corrupt_line,no_feedback,raw")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--tasks", default=",".join(TASKS))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--trajdir", type=Path, required=True)
    a = ap.parse_args()

    arms = a.arms.split(",")
    tasks = [t for t in a.tasks.split(",") if t in TASKS]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.trajdir.mkdir(parents=True, exist_ok=True)

    plan = [(seed, task, arm) for seed in range(a.seeds) for task in tasks for arm in arms]
    # Causal pair (truth, corrupt_line) at seed 0 first, then context arms, then higher seeds:
    # any early stop still yields a complete, paired block (red-team Q6 nested stop points).
    plan.sort(key=lambda x: (x[0], PRIO.get(x[2], 9), x[1]))
    print(f"[plan] {len(plan)} episodes  arms={arms}  tasks={tasks}  seeds={a.seeds}", flush=True)

    done = 0
    for seed, task, arm in plan:
        decoy = TASKS[task]
        traj = a.trajdir / f"{arm}-{task}-s{seed}.json"
        argv = [
            "python", str(ROOT / "bench" / "agent" / "agent.py"),
            "--task", str(ROOT / "bench" / "tasks" / task),
            "--model", a.model, "--seed", str(seed), "--max-turns", str(a.max_turns),
            "--run-before-edit", "--trajectory", str(traj),
        ] + arm_args(arm, task, decoy)
        t0 = time.time()
        r = subprocess.run(argv, capture_output=True, text=True)
        rec = None
        for line in r.stdout.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    rec = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        done += 1
        if rec is None:
            print(f"[{done}/{len(plan)}] {arm}/{task} s{seed} ERROR rc={r.returncode} :: {r.stderr[-200:]}", flush=True)
            rec = {"task": task, "arm": arm, "seed": seed, "error": True, "stderr": r.stderr[-500:]}
        else:
            rec["arm"] = arm
            e1 = [e.get("changed_lines") for e in rec.get("edits", [])[:1]]
            print(f"[{done}/{len(plan)}] {arm}/{task} s{seed} ok={rec.get('success')} turns={rec.get('turns')} "
                  f"edit1={e1} shown={rec.get('shown_fault_line')} truth={rec.get('truth_fault_line')} "
                  f"{time.time() - t0:.0f}s", flush=True)
        with a.out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
