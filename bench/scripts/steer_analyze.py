#!/usr/bin/env python3
"""Analyse the causal verdict-steering experiment.

Readouts (red-team-hardened):
  * first-edit-locus  : which line the agent's FIRST edit changed (difflib-minimal, so a full-file
                        rewrite still yields the true changed lines).
  * hit_true_fix      : first edit within +/-k of the ground-truth fix locus (derived from the
                        solution diff, not hand-set).
  * followed_shown    : first edit within +/-k of the line the verdict SHOWED (truth crash line, or
                        the decoy under corrupt_line).
  * steered           : followed the decoy AND missed the true fix (corrupt_line only).
Unit of analysis = task (paired truth vs corrupt_line). Exact McNemar on the discordant pairs;
paired displacement with an exact sign test. Also: empirical chance baseline for touching the decoy
when it is NOT shown, and a byte-identical-execution audit (raw_bytes must match across arms/task).
"""
import argparse
import difflib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
K = 3  # line tolerance


def wilson(k: int, n: int):
    if n == 0:
        return (0.0, 0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, (c - h) / d, (c + h) / d)


def true_fix_lines(task: str) -> set:
    """Buggy-file line numbers constituting the fix, from the solution diff (auto-derived)."""
    tdir = ROOT / "bench" / "tasks" / task
    src = next((p for p in tdir.glob("*.c")), None) or next((p for p in tdir.glob("*.cpp")), None) \
        or next((p for p in tdir.glob("*.rs")), None) or next((p for p in tdir.glob("*.py")), None)
    sol = tdir / "solution" / src.name
    a = src.read_text().splitlines()
    b = sol.read_text().splitlines()
    lines = set()
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag == "replace" or tag == "delete":
            lines.update(range(i1 + 1, i2 + 1))          # buggy lines changed/removed
        elif tag == "insert":
            lines.update({i1, i1 + 1})                    # buggy lines bracketing the insertion
    return {x for x in lines if x >= 1}


def near(lines, targets, k=K):
    return any(abs(l - t) <= k for l in lines for t in ([targets] if isinstance(targets, int) else targets))


def mindist(lines, targets):
    ts = [targets] if isinstance(targets, int) else list(targets)
    if not lines or not ts:
        return None
    return min(abs(l - t) for l in lines for t in ts)


def first_edit(rec):
    es = rec.get("edits") or []
    return list(es[0].get("changed_lines") or []) if es else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--md", type=Path, default=None)
    a = ap.parse_args()
    recs = [json.loads(l) for l in a.jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if not r.get("error")]
    fixmap = {t: true_fix_lines(t) for t in {r["task"] for r in recs}}
    decoymap = {}  # task -> decoy line (from corrupt_line records)
    for r in recs:
        if r.get("corrupt", {}) and r["corrupt"].get("mode") == "line":
            decoymap[r["task"]] = int(r["corrupt"]["decoy_line"])

    # per-episode enrichment
    for r in recs:
        fe = first_edit(r)
        fx = fixmap[r["task"]]
        shown = r.get("shown_fault_line")
        r["_fe"] = fe
        r["_hit_true"] = near(fe, fx) if fe else False
        r["_dist_true"] = mindist(fe, fx)
        r["_followed_shown"] = (near(fe, shown) if (fe and shown is not None) else False)
        decoy = decoymap.get(r["task"])
        r["_touched_decoy"] = (near(fe, decoy) if (fe and decoy is not None) else False)
        r["_steered"] = bool(r["_followed_shown"] and not r["_hit_true"]) if r["arm"] == "corrupt_line" else False

    arms = ["truth", "corrupt_line", "corrupt_kind", "no_feedback", "raw"]
    out = []
    out.append(f"# Verdict-steering results  (k=+/-{K} lines, n_tasks={len({r['task'] for r in recs})})\n")
    out.append("true-fix loci (buggy-file lines, auto-derived): " + ", ".join(f"{t}={sorted(fixmap[t])}" for t in sorted(fixmap)))
    out.append("decoys: " + ", ".join(f"{t}={decoymap.get(t)}" for t in sorted(decoymap)) + "\n")

    out.append("| arm | n | success | turns | hit_true_fix | followed_shown | mean dist_true | steered |")
    out.append("|---|---|---|---|---|---|---|---|")
    by = {arm: [r for r in recs if r["arm"] == arm] for arm in arms}
    for arm in arms:
        rs = by[arm]
        if not rs:
            continue
        n = len(rs)
        succ = sum(1 for r in rs if r.get("success"))
        p, lo, hi = wilson(succ, n)
        turns = sum(r.get("turns", 0) for r in rs) / n
        hit = sum(1 for r in rs if r["_hit_true"])
        fol = sum(1 for r in rs if r["_followed_shown"])
        dists = [r["_dist_true"] for r in rs if r["_dist_true"] is not None]
        md = sum(dists) / len(dists) if dists else float("nan")
        steer = sum(1 for r in rs if r["_steered"])
        out.append(f"| {arm} | {n} | {succ}/{n} ({100*p:.0f}%, {100*lo:.0f}-{100*hi:.0f}) | {turns:.1f} | "
                   f"{hit}/{n} | {fol}/{n} | {md:.1f} | {steer}/{n} |")

    # Paired truth vs corrupt_line (by task+seed)
    def key(r):
        return (r["task"], r.get("seed", 0))
    tmap = {key(r): r for r in by["truth"]}
    cmap = {key(r): r for r in by["corrupt_line"]}
    pairs = [(tmap[k], cmap[k]) for k in tmap if k in cmap]
    out.append(f"\n## Paired truth vs corrupt_line  ({len(pairs)} pairs)\n")
    out.append("| task | truth edit1 | corrupt edit1 | truth hit | corrupt hit | truth dist | corrupt dist | steered |")
    out.append("|---|---|---|---|---|---|---|---|")
    b = c = 0  # McNemar discordants on hit_true_fix
    disp = []  # corrupt_dist - truth_dist
    for t, cc in pairs:
        if t["_hit_true"] and not cc["_hit_true"]:
            b += 1
        if cc["_hit_true"] and not t["_hit_true"]:
            c += 1
        if t["_dist_true"] is not None and cc["_dist_true"] is not None:
            disp.append(cc["_dist_true"] - t["_dist_true"])
        out.append(f"| {t['task']} | {t['_fe']} | {cc['_fe']} | {t['_hit_true']} | {cc['_hit_true']} | "
                   f"{t['_dist_true']} | {cc['_dist_true']} | {cc['_steered']} |")

    # exact McNemar (binomial on discordants)
    def binom_two_sided(b, c):
        n = b + c
        if n == 0:
            return 1.0
        from math import comb
        kk = min(b, c)
        tail = sum(comb(n, i) for i in range(0, kk + 1)) / (2 ** n)
        return min(1.0, 2 * tail)
    out.append(f"\nMcNemar on hit_true_fix: b(truth-hit, corrupt-miss)={b}, c(truth-miss, corrupt-hit)={c}, exact two-sided p={binom_two_sided(b, c):.4f}")

    # displacement sign test
    pos = sum(1 for d in disp if d > 0)
    neg = sum(1 for d in disp if d < 0)
    med = sorted(disp)[len(disp) // 2] if disp else None
    out.append(f"Displacement (corrupt_dist - truth_dist): median={med}, moved-away={pos}, moved-toward={neg}, values={disp}")
    out.append(f"Sign test on displacement: exact two-sided p={binom_two_sided(pos, neg):.4f}")

    # Paired truth vs corrupt_kind (a stronger lie: wrong crash CLASS). Readout: does the first edit
    # still land on the true fix, or does the faked class pull it elsewhere?
    kmap = {key(r): r for r in by.get("corrupt_kind", [])}
    kpairs = [(tmap[k], kmap[k]) for k in tmap if k in kmap]
    if kpairs:
        out.append(f"\n## Paired truth vs corrupt_kind  ({len(kpairs)} pairs)\n")
        out.append("| task | truth edit1 | kind-corrupt edit1 | truth hit | kind hit |")
        out.append("|---|---|---|---|---|")
        bk = ck = 0
        for t, kk in kpairs:
            if t["_hit_true"] and not kk["_hit_true"]:
                bk += 1
            if kk["_hit_true"] and not t["_hit_true"]:
                ck += 1
            out.append(f"| {t['task']} | {t['_fe']} | {kk['_fe']} | {t['_hit_true']} | {kk['_hit_true']} |")
        out.append(f"\nMcNemar on hit_true_fix (truth vs corrupt_kind): b={bk}, c={ck}, exact two-sided p={binom_two_sided(bk, ck):.4f}")

    # empirical chance baseline: touching the decoy line when it is NOT shown
    not_shown = [r for r in recs if r["arm"] in ("truth", "no_feedback", "raw")]
    td = sum(1 for r in not_shown if r["_touched_decoy"])
    out.append(f"\nChance baseline P(first edit touches decoy | decoy NOT shown) = {td}/{len(not_shown)}")
    shown_c = by["corrupt_line"]
    tds = sum(1 for r in shown_c if r["_touched_decoy"])
    out.append(f"P(first edit touches decoy | decoy shown, corrupt_line)      = {tds}/{len(shown_c)}")

    # byte-identical execution audit
    audit = {}
    for r in recs:
        rb = (r.get("runs") or [{}])[0].get("raw_bytes")
        audit.setdefault(r["task"], set()).add(rb)
    bad = {t: v for t, v in audit.items() if len(v) > 1}
    out.append(f"\nByte-identical-execution audit (first-run raw_bytes per task across arms): "
               + ("ALL MATCH" if not bad else f"MISMATCH {bad}"))

    text = "\n".join(out) + "\n"
    print(text)
    if a.md:
        a.md.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
