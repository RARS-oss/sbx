#!/usr/bin/env python3
"""Generate docs/frontier-efficiency.svg — the frontier context-efficiency result
(Claude Opus + Sonnet: same fix, 2-18x less context). Dark teal style, matching docs/*.svg."""
import math
from pathlib import Path

BG0, BG1, PANEL, STROKE = "#12221f", "#0d1719", "#16262a", "#24363b"
TEAL, TEAL2, INK, MUT, RAW = "#2bc4b2", "#63e0cf", "#eaf3f2", "#9fb4ba", "#7d5b52"
OUT = Path(__file__).resolve().parents[2] / "docs" / "frontier-efficiency.svg"

# (model, task, raw_shown_chars, structured_delta_shown_chars) — the 7 clean pairs
DATA = [
    ("Opus",   "cpp-vector-oob",  36542, 2066),
    ("Opus",   "use-after-free",  18287, 1993),
    ("Sonnet", "use-after-free",  18118, 1509),
    ("Opus",   "double-free",      4642, 1936),
    ("Sonnet", "double-free",      4532, 1695),
    ("Opus",   "decoy-hist",       2904, 1035),
    ("Sonnet", "decoy-hist",       2882, 1256),
]

w, h = 1200, 470
x0, y0 = 250, 116
plotw, ploth = w - x0 - 140, 300
lo, hi = 100, 45000

def xp(v):
    return x0 + (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * plotw

s = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
    f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
    f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>'
    f'<linearGradient id="acc" x1="0" y1="0" x2="1" y2="0">'
    f'<stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{TEAL2}"/></linearGradient></defs>'
    f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="20" fill="url(#bg)" stroke="{STROKE}" stroke-width="1.5"/>'
]
s.append(f'<text x="40" y="50" fill="{INK}" font-size="22" font-weight="700">Same fix, far less context — on frontier models</text>')
s.append(f'<text x="40" y="78" fill="{MUT}" font-size="14">Claude Opus and Sonnet driven as the agent (real hermetic sandbox, run-before-edit). Characters shown to the model per episode, log scale — same success, same fix locus.</text>')
for gv in (100, 1000, 10000):
    gx = xp(gv)
    s.append(f'<line x1="{gx:.0f}" y1="{y0}" x2="{gx:.0f}" y2="{y0+ploth}" stroke="{STROKE}"/>')
    s.append(f'<text x="{gx:.0f}" y="{y0+ploth+20}" fill="{MUT}" font-size="12" text-anchor="middle" font-family="monospace">{gv:,}</text>')
rowh = ploth / len(DATA)
for i, (model, task, rawc, typc) in enumerate(DATA):
    cy = y0 + i * rowh + rowh / 2
    s.append(f'<text x="{x0-14}" y="{cy+4:.0f}" fill="{INK}" font-size="13" text-anchor="end" font-family="monospace">{model} · {task}</text>')
    s.append(f'<rect x="{x0}" y="{cy-13:.0f}" width="{xp(rawc)-x0:.0f}" height="11" rx="2" fill="{RAW}" opacity="0.85"/>')
    s.append(f'<text x="{xp(rawc)+6:.0f}" y="{cy-3:.0f}" fill="{RAW}" font-size="11" font-family="monospace">{rawc:,}</text>')
    s.append(f'<rect x="{x0}" y="{cy+2:.0f}" width="{max(xp(typc)-x0,2):.0f}" height="11" rx="2" fill="url(#acc)"/>')
    s.append(f'<text x="{xp(typc)+6:.0f}" y="{cy+12:.0f}" fill="{TEAL2}" font-size="11" font-family="monospace">{typc:,}</text>')
    red = rawc / typc
    s.append(f'<text x="{x0+plotw+95:.0f}" y="{cy+4:.0f}" fill="{TEAL2 if red>=2 else MUT}" font-size="15" font-weight="700" text-anchor="end">{red:.1f}x</text>')
s.append(f'<rect x="{x0}" y="{y0+ploth+34}" width="12" height="11" rx="2" fill="{RAW}"/><text x="{x0+18}" y="{y0+ploth+44}" fill="{MUT}" font-size="12">raw stdout</text>')
s.append(f'<rect x="{x0+110}" y="{y0+ploth+34}" width="12" height="11" rx="2" fill="url(#acc)"/><text x="{x0+128}" y="{y0+ploth+44}" fill="{MUT}" font-size="12">typed verdict + delta</text>')
s.append(f'<text x="{w-140}" y="{y0-12}" fill="{MUT}" font-size="12" text-anchor="middle">reduction</text>')
s.append(f'<text x="40" y="{h-22}" fill="{MUT}" font-size="12.5">Median 2.8x, up to 17.7x. On Haiku the same episode cost <tspan fill="{INK}">8x</tspan> less ($0.53 to $0.068). The gain scales with output size.</text>')
s.append('</svg>')
OUT.write_text("\n".join(s), encoding="utf-8")
print("wrote", OUT)
