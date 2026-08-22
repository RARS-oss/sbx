#!/usr/bin/env python3
"""Figures for the report, as self-contained SVG (matplotlib, no external fonts/assets).

  python bench/agent/plot.py --results bench/out/pilot-qwen2.5-coder_7b.jsonl [more ...] \
      --startup bench/out/startup_bench.json --out bench/out/figs

Produces (per results set, labelled by model):
  fig_success_<model>.svg       success rate by condition with Wilson 95% CI
  fig_tokens_<model>.svg        input tokens per episode by condition (box + points)
  fig_turns_<model>.svg         turns per episode (all) and turns-to-solve (successes only)
  fig_shown_vs_raw_<model>.svg  chars shown to the model vs raw bytes produced, per task × condition
  fig_task_matrix_<model>.svg   success heat-map task × condition
and, if --startup is given, fig_startup.svg (latency bars, log scale).
Colours are fixed per condition across all figures.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FMT = "svg"  # overridden by --fmt
COND_ORDER = ["raw", "truncate30k", "truncate10k", "regex", "structured", "structured_delta"]
COND_LABEL = {
    "raw": "raw",
    "truncate30k": "truncate 30k\n(Claude Code)",
    "truncate10k": "truncate 10 KiB\n(Codex)",
    "regex": "regex\n(RTK-style)",
    "structured": "typed\nverdict",
    "structured_delta": "typed\n+ delta",
}
COND_COLOR = {
    "raw": "#9aa4ae",
    "truncate30k": "#7a8fa3",
    "truncate10k": "#5b7a94",
    "regex": "#b08a3a",
    "structured": "#2c6b8c",
    "structured_delta": "#2e7d4f",
}
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "svg.fonttype": "none",
})


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "error" not in r:
                    rows.append(r)
    return rows


def short_model(m: str) -> str:
    return m.replace("ollama:", "").replace(":", "-").replace("/", "_")


def conds_present(rows):
    present = {r["condition"] for r in rows if r.get("mask") is None}
    return [c for c in COND_ORDER if c in present]


def fig_success(rows, model, out: Path):
    conds = conds_present(rows)
    ks, ns, los, his = [], [], [], []
    for c in conds:
        rs = [r for r in rows if r["condition"] == c and r.get("mask") is None]
        k = sum(1 for r in rs if r["success"])
        lo, hi = wilson(k, len(rs))
        ks.append(k / len(rs) if rs else 0)
        ns.append(len(rs))
        los.append(lo)
        his.append(hi)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = range(len(conds))
    ax.bar(x, ks, color=[COND_COLOR[c] for c in conds], width=0.6)
    ax.errorbar(x, ks, yerr=[[k - lo for k, lo in zip(ks, los)], [hi - k for k, hi in zip(ks, his)]], fmt="none", ecolor="#333", capsize=4, lw=1)
    for i, (k, n, hi) in enumerate(zip(ks, ns, his)):
        ax.text(i, hi + 0.03, f"{k:.0%}  (n={n})", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels([COND_LABEL[c] for c in conds], fontsize=8.5)
    ax.set_ylim(0, 1.22)
    ax.set_ylabel("success rate (independent re-run)")
    ax.set_title(f"Success by feedback condition — {model} (Wilson 95% CI)", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def fig_tokens(rows, model, out: Path):
    conds = conds_present(rows)
    data = [[r["tokens"]["input"] + r["tokens"]["cache_read"] + r["tokens"]["cache_creation"] for r in rows if r["condition"] == c and r.get("mask") is None] for c in conds]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bp = ax.boxplot(data, positions=range(len(conds)), widths=0.5, patch_artist=True, showfliers=False, medianprops={"color": "#111"})
    for patch, c in zip(bp["boxes"], conds):
        patch.set_facecolor(COND_COLOR[c])
        patch.set_alpha(0.55)
    for i, d in enumerate(data):
        ax.scatter([i + (j % 5 - 2) * 0.04 for j in range(len(d))], d, s=12, color="#222", alpha=0.7, zorder=3)
    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels([COND_LABEL[c] for c in conds], fontsize=8.5)
    ax.set_ylabel("input tokens per episode")
    ax.set_yscale("log")
    ax.set_title(f"Input tokens per episode — {model}", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def fig_turns(rows, model, out: Path):
    conds = conds_present(rows)
    all_t = [[r["turns"] for r in rows if r["condition"] == c and r.get("mask") is None] for c in conds]
    ok_t = [[r["turns"] for r in rows if r["condition"] == c and r.get("mask") is None and r["success"]] for c in conds]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = range(len(conds))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [st.mean(t) if t else 0 for t in all_t], width=w, color="#bbb", label="all episodes (mean)")
    ax.bar([i + w / 2 for i in x], [st.mean(t) if t else 0 for t in ok_t], width=w, color=[COND_COLOR[c] for c in conds], label="solved episodes (turns-to-solve)")
    for i, t in enumerate(ok_t):
        ax.text(i + w / 2, (st.mean(t) if t else 0) + 0.2, f"n={len(t)}", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([COND_LABEL[c] for c in conds], fontsize=8.5)
    ax.set_ylabel("API turns")
    ax.set_title(f"Turns per episode — {model}", fontsize=10.5)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def fig_shown_vs_raw(rows, model, out: Path):
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    conds = conds_present(rows)
    for c in conds:
        rs = [r for r in rows if r["condition"] == c and r.get("mask") is None and r["raw_bytes_total"] > 0]
        ax.scatter([r["raw_bytes_total"] for r in rs], [r["shown_chars_total"] for r in rs], s=28, color=COND_COLOR[c], label=COND_LABEL[c].replace("\n", " "), alpha=0.85, edgecolor="white", linewidth=0.5)
    lim = [1e2, max(1e3, max((r["raw_bytes_total"] for r in rows), default=1e3) * 1.5)]
    ax.plot(lim, lim, ls="--", color="#888", lw=1, label="shown = raw")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("raw bytes produced by runs (per episode)")
    ax.set_ylabel("chars shown to the model (per episode)")
    ax.set_title(f"What the model saw vs what the runs produced — {model}", fontsize=10.5)
    ax.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def fig_task_matrix(rows, model, out: Path):
    conds = conds_present(rows)
    tasks = sorted({r["task"] for r in rows})
    mat = [[None for _ in conds] for _ in tasks]
    for i, t in enumerate(tasks):
        for j, c in enumerate(conds):
            rs = [r for r in rows if r["task"] == t and r["condition"] == c and r.get("mask") is None]
            if rs:
                mat[i][j] = sum(1 for r in rs if r["success"]) / len(rs)
    fig, ax = plt.subplots(figsize=(1.4 + 1.1 * len(conds), 0.6 + 0.38 * len(tasks)))
    import numpy as np  # noqa: WPS433

    arr = np.array([[v if v is not None else np.nan for v in row] for row in mat], dtype=float)
    im = ax.imshow(arr, cmap="YlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels([COND_LABEL[c].replace("\n", " ") for c in conds], rotation=20, ha="right", fontsize=8)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(tasks, fontsize=8)
    for i in range(len(tasks)):
        for j in range(len(conds)):
            rs = [r for r in rows if r["task"] == tasks[i] and r["condition"] == conds[j] and r.get("mask") is None]
            if rs:
                k = sum(1 for r in rs if r["success"])
                ax.text(j, i, f"{k}/{len(rs)}", ha="center", va="center", fontsize=8, color="#111")
    ax.grid(False)
    ax.set_title(f"Success by task × condition — {model}", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def fig_startup(startup_json: Path, out: Path):
    rows = [json.loads(l) for l in startup_json.read_text().splitlines() if l.strip().startswith("{")]
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    names = [r["variant"] for r in rows]
    med = [r["median"] for r in rows]
    p90 = [r["p90"] for r in rows]
    y = range(len(rows))
    ax.barh(y, med, color=["#2c6b8c" if n.startswith("sbx") else "#9aa4ae" for n in names])
    for i, (m, p) in enumerate(zip(med, p90)):
        ax.plot([m, p], [i, i], color="#333", lw=1.2)
        ax.text(p * 1.08, i, f"{m:.2f} ms (p90 {p:.2f})", va="center", fontsize=8.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xscale("log")
    ax.set_xlabel("startup latency for /bin/true, ms (median, whisker to p90)")
    ax.invert_yaxis()
    ax.set_title("Sandbox startup latency (this machine)", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(out, format=out.suffix.lstrip("."), dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="*", default=[])
    ap.add_argument("--startup", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("bench/out/figs"))
    ap.add_argument("--fmt", default="svg", choices=["svg", "png"], help="svg for the report/artifact, png for quick viewing")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    global FMT
    FMT = a.fmt
    rows = load(a.results) if a.results else []
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    for model, rs in by_model.items():
        m = short_model(model)
        fig_success(rs, m, a.out / f"fig_success_{m}.{FMT}")
        fig_tokens(rs, m, a.out / f"fig_tokens_{m}.{FMT}")
        fig_turns(rs, m, a.out / f"fig_turns_{m}.{FMT}")
        fig_shown_vs_raw(rs, m, a.out / f"fig_shown_vs_raw_{m}.{FMT}")
        fig_task_matrix(rs, m, a.out / f"fig_task_matrix_{m}.{FMT}")
        print(f"{m}: {len(rs)} episodes -> 5 figures")
    if a.startup and a.startup.exists():
        fig_startup(a.startup, a.out / f"fig_startup.{FMT}")
        print("startup figure written")
    print(f"figures in {a.out}")


if __name__ == "__main__":
    main()
