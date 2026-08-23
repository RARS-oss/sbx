#!/usr/bin/env python3
"""Run sbx on SWE-bench / ARVO-style instances (multi-file repo repair), reusing the agent harness.

An instance is a repo + a problem statement + a test command; the agent explores (`list_files`,
`read_file`), edits (`write_file`) and re-runs (`run`) inside sbx, and we record pass/fail, turns,
tokens and cache-aware cost per condition — so the token/turn measurement runs on real multi-file
repositories, not single-file toy tasks (the regime §6.7 of the report says is the decisive one).

Instance JSON (a SWE-bench-compatible subset):
  { "instance_id", "repo_dir", "problem_statement", "test_cmd", "protected"?, "timeout"?, "env"?, "ro_binds"? }

For real SWE-bench: prepare each instance's repo first — `git clone <repo>; git checkout <base_commit>;
git apply <test_patch>; <install deps>` — point "repo_dir" at that tree and derive "test_cmd" from the
instance's FAIL_TO_PASS. ARVO N-days: point "repo_dir" at the vulnerable checkout, "test_cmd" at the
PoC build+run (the oracle is the sanitizer). See bench/swe/README.md.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from agent import Task, run_episode  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load_instances(path: Path) -> list[dict]:
    if path.is_dir():
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(l) for l in text.splitlines() if l.strip()]
    obj = json.loads(text)
    return obj if isinstance(obj, list) else [obj]


def task_of(inst: dict) -> Task:
    rd = Path(inst["repo_dir"])
    repo = rd if rd.is_absolute() else (ROOT / rd)
    return Task(
        name=inst["instance_id"],
        dir=repo.resolve(),
        prompt=inst["problem_statement"],
        run=inst.get("test_cmd", "python3 -m pytest -q"),
        files=inst.get("files", []),
        protected=inst.get("protected", []),
        timeout=int(inst.get("timeout", 300)),
        lang=inst.get("lang", ""),
        family="swe-bench",
        bug=inst.get("bug", ""),
        ro_binds=inst.get("ro_binds", []),
        env=inst.get("env", {}),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", type=Path, required=True, help="instance .json/.jsonl or a dir of them")
    ap.add_argument("--model", default="mock", help="mock | ollama:<m> | openai:<m> | claude-cli:<m> | <anthropic model>")
    ap.add_argument("--conditions", default="raw,structured_delta")
    ap.add_argument("--max-turns", type=int, default=25)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "bench" / "out" / "swe.jsonl")
    ap.add_argument("--trajdir", type=Path, default=ROOT / "bench" / "out" / "traj-swe")
    a = ap.parse_args()

    insts = load_instances(a.instances)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.trajdir.mkdir(parents=True, exist_ok=True)
    print(f"[swe] {len(insts)} instance(s) · conditions={a.conditions} · model={a.model}", flush=True)

    rows = []
    for inst in insts:
        task = task_of(inst)
        if not task.dir.is_dir():
            print(f"  SKIP {task.name}: repo_dir not found: {task.dir}", flush=True)
            continue
        for seed in range(a.seeds):
            for cond in a.conditions.split(","):
                traj = a.trajdir / f"{task.name}-{cond}-s{seed}.json"
                rec = run_episode(task, cond, a.model, "high", a.max_turns, None, seed, True, False, traj)
                rec["instance_id"] = task.name
                with a.out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, default=str) + "\n")
                rows.append(rec)
                print(f"  {task.name} · {cond} · s{seed}: pass={rec.get('success')} turns={rec.get('turns')} "
                      f"reads={rec.get('tool_calls', {}).get('read_file')} shown={rec.get('shown_chars_total')} "
                      f"raw={rec.get('raw_bytes_total')} cost={rec.get('cost_usd')}", flush=True)

    print("\n=== summary (per condition) — the multi-file token/turn measurement ===")
    for cond in a.conditions.split(","):
        cr = [r for r in rows if r.get("condition") == cond]
        if not cr:
            continue
        n = len(cr)
        succ = sum(1 for r in cr if r.get("success"))
        turns = sum(r.get("turns", 0) for r in cr) / n
        shown = sum(r.get("shown_chars_total", 0) for r in cr) / n
        raw = sum(r.get("raw_bytes_total", 0) for r in cr) / n
        ratio = (raw / shown) if shown else 0
        print(f"  {cond:16s}: {succ}/{n} pass · {turns:.1f} turns · shown {shown:.0f} vs raw {raw:.0f} chars/ep ({ratio:.1f}x)")


if __name__ == "__main__":
    main()
