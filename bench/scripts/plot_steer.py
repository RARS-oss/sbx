#!/usr/bin/env python3
"""The money figure for the verdict-steering experiment.

One row per task: a line-number axis showing the true-fix locus (green band), the line the CORRUPTED
verdict pointed at (red = decoy), the line the truthful verdict pointed at (blue = crash), and where
the agent's first edit actually landed under the corrupted verdict (● black). The edits sit on the
fix and ignore the decoy — the lie has no effect. Self-contained SVG, light-theme to match report.html.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import steer_analyze as SA  # noqa: E402

BG = "#F6F7F5"
INK = "#1b2125"
MUT = "#69747c"
FIX = "#2e7d4f"
DECOY = "#b5462f"
CRASH = "#2c6b8c"
LINE = "#c9d1cd"


def main():
    jsonl = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("bench/out/figs/fig_steer.svg")
    recs = [json.loads(x) for x in Path(jsonl).read_text(encoding="utf-8").splitlines() if x.strip()]
    recs = [r for r in recs if not r.get("error")]
    tasks = sorted({r["task"] for r in recs})
    fixmap = {t: SA.true_fix_lines(t) for t in tasks}
    cl = {r["task"]: r for r in recs if r["arm"] == "corrupt_line"}
    tr = {r["task"]: r for r in recs if r["arm"] == "truth"}

    # global line-number range across the shown files (pad a little)
    def flines(t):
        f = fixmap[t]
        vals = list(f) + [cl[t].get("shown_fault_line", 0), tr[t].get("truth_fault_line", 0)]
        vals += [l for e in (cl[t].get("edits") or [])[:1] for l in (e.get("changed_lines") or [])]
        return [v for v in vals if v]
    lo = 1
    hi = max(max(flines(t)) for t in tasks) + 2

    W, rowH, padL, padT, axW = 820, 62, 175, 96, 560
    H = padT + rowH * len(tasks) + 40
    x = lambda ln: padL + (ln - lo) / (hi - lo) * axW  # noqa: E731
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Source Sans 3,system-ui,sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
    s.append(f'<text x="{padL}" y="30" font-size="15" font-weight="600" fill="{INK}">A corrupted fault line does not move the agent\'s edit</text>')
    s.append(f'<text x="{padL}" y="50" font-size="12" fill="{MUT}">Under <tspan fill="{DECOY}">corrupt_line</tspan>, the verdict points at the red line; the agent\'s first edit (●) still lands on the true fix (green).</text>')
    # legend
    lg = padT - 20
    s.append(f'<rect x="{padL}" y="{lg-9}" width="16" height="10" fill="{FIX}" opacity="0.30"/><text x="{padL+21}" y="{lg}" font-size="11" fill="{MUT}">true fix</text>')
    s.append(f'<circle cx="{padL+112}" cy="{lg-4}" r="4" fill="{DECOY}"/><text x="{padL+120}" y="{lg}" font-size="11" fill="{MUT}">decoy shown</text>')
    s.append(f'<circle cx="{padL+232}" cy="{lg-4}" r="4" fill="{CRASH}"/><text x="{padL+240}" y="{lg}" font-size="11" fill="{MUT}">true crash line</text>')
    s.append(f'<circle cx="{padL+372}" cy="{lg-4}" r="5" fill="{INK}"/><text x="{padL+382}" y="{lg}" font-size="11" fill="{MUT}">first edit</text>')

    for i, t in enumerate(tasks):
        y = padT + i * rowH + 24
        s.append(f'<text x="{padL-12}" y="{y+4}" font-size="12" text-anchor="end" fill="{INK}">{t.replace("c-","").replace("cpp-","")}</text>')
        s.append(f'<line x1="{padL}" y1="{y}" x2="{padL+axW}" y2="{y}" stroke="{LINE}" stroke-width="1.5"/>')
        # fix band
        f = sorted(fixmap[t])
        fx0, fx1 = x(min(f) - 0.5), x(max(f) + 0.5)
        s.append(f'<rect x="{fx0:.0f}" y="{y-11}" width="{max(fx1-fx0,6):.0f}" height="22" fill="{FIX}" opacity="0.22"/>')
        # crash (truth) marker
        tc = tr[t].get("truth_fault_line")
        if tc:
            s.append(f'<circle cx="{x(tc):.0f}" cy="{y}" r="4" fill="{CRASH}"/>')
        # decoy marker
        dc = cl[t].get("shown_fault_line")
        if dc:
            s.append(f'<circle cx="{x(dc):.0f}" cy="{y}" r="4" fill="{DECOY}"/>')
            s.append(f'<text x="{x(dc):.0f}" y="{y-14}" font-size="10" text-anchor="middle" fill="{DECOY}">L{dc}</text>')
        # actual first edit under corruption
        e = (cl[t].get("edits") or [])
        for ln in (e[0].get("changed_lines") if e else [])[:4]:
            s.append(f'<circle cx="{x(ln):.0f}" cy="{y}" r="5.5" fill="{INK}"/>')
    s.append(f'<text x="{padL}" y="{H-14}" font-size="11" fill="{MUT}">line number →   (Claude Sonnet 4.6; 4/4 edits on the true fix, decoy touched 0 times)</text>')
    s.append("</svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(s), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
