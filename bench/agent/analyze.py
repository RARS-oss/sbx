#!/usr/bin/env python3
"""Deeper analysis of pilot results: per-condition aggregates with Wilson CIs, per-task matrix,
turn/run distributions, shown-vs-raw, and a Markdown table ready to paste into docs/paper.

  python bench/agent/analyze.py bench/out/pilot-qwen2.5-coder_7b.jsonl [more.jsonl ...] [--md out.md]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


ORDER = {"setup_failed": 0, "timeout": 0, "unknown": 0, "crash": 1, "build_failed": 1, "runtime_error": 2, "tests_failed": 3, "pass": 4}


def ground_truth() -> dict:
    """task -> (file, lines) from bench/scripts/localization_check.py, if importable."""
    try:
        import importlib.util
        p = Path(__file__).resolve().parents[1] / "scripts" / "localization_check.py"
        spec = importlib.util.spec_from_file_location("loc", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return {k: (v[0], set(v[1])) for k, v in mod.GROUND_TRUTH.items()}
    except Exception:
        return {}


GT = ground_truth()


def fix_lines(task: str) -> dict:
    """file -> set of line numbers (buggy-file numbering) changed between the shipped buggy
    sources and solution/ — i.e. where the reference fix is."""
    import difflib
    out: dict = {}
    d = Path(__file__).resolve().parents[1] / "tasks" / task
    sol = d / "solution"
    if not sol.exists():
        return out
    for p in sol.iterdir():
        if not p.is_file():
            continue
        buggy = d / p.name
        if not buggy.exists():
            continue
        a = buggy.read_text(errors="replace").splitlines()
        b = p.read_text(errors="replace").splitlines()
        lines = set()
        for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if tag != "equal":
                lines.update(range(i1 + 1, max(i2, i1 + 1) + 1))
        if lines:
            out[p.name] = lines
    return out


_FIX_CACHE: dict = {}


def edit_hit(r: dict) -> bool | None:
    """Did any write touch the ground-truth fix lines (reference solution diff, ±3) or the
    faulting line (±3)? None if no edits / no ground truth."""
    edits = r.get("edits") or []
    if not edits:
        return None
    task = r["task"]
    if task not in _FIX_CACHE:
        _FIX_CACHE[task] = fix_lines(task)
    targets: dict = {f: set(ls) for f, ls in _FIX_CACHE[task].items()}
    gt = GT.get(task)
    if gt:
        targets.setdefault(gt[0], set()).update(gt[1])
    if not targets:
        return None
    for e in edits:
        f = (e.get("path") or "").split("/")[-1]
        if f not in targets:
            continue
        for ln in e.get("changed_lines", []):
            if any(abs(ln - g) <= 3 for g in targets[f]):
                return True
    return False


def progressed(r: dict) -> bool | None:
    runs = r.get("runs") or []
    if len(runs) < 2:
        return None
    first = ORDER.get(runs[0]["status"], 0)
    best = max(ORDER.get(x["status"], 0) for x in runs[1:])
    # also count "fewer failing tests" as progress when status is unchanged
    tf = [x.get("tests_failed") for x in runs if x.get("tests_failed") is not None]
    fewer = len(tf) >= 2 and min(tf[1:]) < tf[0]
    return best > first or fewer


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "error" not in r:
                    r["_file"] = p.name
                    rows.append(r)
    return rows


def cond_label(r: dict) -> str:
    c = r["condition"]
    if r.get("mask") is not None:
        c += f"/mask{r['mask']}"
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--md", type=Path, default=None)
    a = ap.parse_args()
    rows = load(a.files)
    if not rows:
        print("no records")
        return
    out: list[str] = []
    models = sorted({r["model"] for r in rows})
    for model in models:
        rs_m = [r for r in rows if r["model"] == model]
        out.append(f"\n## {model}  (n={len(rs_m)} episodes, {len({r['task'] for r in rs_m})} tasks)\n")
        out.append("| condition | n | success | 95% CI | turns (mean/median) | runs | nudges | infra err | edit-hit | progress | in_tok | out_tok | cost $ | shown/raw | wall s |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        groups: dict[str, list] = defaultdict(list)
        for r in rs_m:
            groups[cond_label(r)].append(r)
        for c in sorted(groups):
            rs = groups[c]
            n = len(rs)
            k = sum(1 for r in rs if r["success"])
            lo, hi = wilson(k, n)
            turns = [r["turns"] for r in rs]
            runs = [r["tool_calls"]["run"] for r in rs]
            nud = [r.get("nudges", 0) for r in rs]
            itok = [r["tokens"]["input"] + r["tokens"]["cache_read"] + r["tokens"]["cache_creation"] for r in rs]
            otok = [r["tokens"]["output"] for r in rs]
            cost = [r["cost_usd"] for r in rs]
            ratio = [r["shown_chars_total"] / r["raw_bytes_total"] for r in rs if r["raw_bytes_total"]]
            wall = [r["wall_s"] for r in rs]
            infra = sum(1 for r in rs if r.get("infra_error"))
            eh = [edit_hit(r) for r in rs]
            eh_known = [x for x in eh if x is not None]
            eh_s = f"{sum(eh_known)}/{len(eh_known)}" if eh_known else "-"
            pg = [progressed(r) for r in rs]
            pg_known = [x for x in pg if x is not None]
            pg_s = f"{sum(pg_known)}/{len(pg_known)}" if pg_known else "-"
            out.append(
                f"| {c} | {n} | {k}/{n} ({k / n:.0%}) | {lo:.0%}-{hi:.0%} | {st.mean(turns):.1f}/{st.median(turns):.0f} | {st.mean(runs):.1f} | {st.mean(nud):.1f} | {infra} | {eh_s} | {pg_s} | {st.mean(itok):,.0f} | {st.mean(otok):,.0f} | {st.mean(cost):.4f} | {st.mean(ratio) if ratio else 0:.2f} | {st.mean(wall):.0f} |"
            )
        # success-only turn stats (turns-to-solve)
        out.append("\nTurns-to-solve on successful episodes (mean / median / n):")
        for c in sorted(groups):
            ok = [r["turns"] for r in groups[c] if r["success"]]
            if ok:
                out.append(f"- {c}: {st.mean(ok):.1f} / {st.median(ok):.0f} / {len(ok)}")
            else:
                out.append(f"- {c}: - (no successes)")
        # per task matrix
        tasks = sorted({r["task"] for r in rs_m})
        conds = sorted(groups)
        out.append("\nSuccess by task x condition:\n")
        out.append("| task | " + " | ".join(conds) + " |")
        out.append("|---|" + "---|" * len(conds))
        for t in tasks:
            cells = []
            for c in conds:
                rs = [r for r in groups[c] if r["task"] == t]
                if rs:
                    k = sum(1 for r in rs if r["success"])
                    turns_ok = [r["turns"] for r in rs if r["success"]]
                    cells.append(f"{k}/{len(rs)}" + (f" (t={st.mean(turns_ok):.0f})" if turns_ok else ""))
                else:
                    cells.append("-")
            out.append(f"| {t} | " + " | ".join(cells) + " |")
        # run-status sequences: how often the final run was pass but agent did not call done, etc.
        out.append("\nOutcome bookkeeping:")
        for c in conds:
            rs = groups[c]
            done = sum(1 for r in rs if r["done_called"])
            prot = sum(1 for r in rs if not r["protected_ok"])
            capped = sum(1 for r in rs if not r["done_called"] and not r["success"])
            out.append(f"- {c}: done called {done}/{len(rs)}; protected-file violations {prot}; ended without done and failed {capped}")
    text = "\n".join(out)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", "replace"))
        sys.stdout.buffer.write(b"\n")
    if a.md:
        a.md.parent.mkdir(parents=True, exist_ok=True)
        a.md.write_text(text + "\n")
        print(f"\n(wrote {a.md})")


if __name__ == "__main__":
    main()
