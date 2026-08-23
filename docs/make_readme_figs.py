#!/usr/bin/env python3
"""Generate the README graphics in the RARS-oss portfolio aesthetic (dark, teal accent),
matching light-andromeda's banner/architecture/result-graph style. Writes docs/*.svg."""
from pathlib import Path

BG0, BG1 = "#12221f", "#0d1719"
PANEL = "#16262a"
STROKE = "#24363b"
TEAL, TEAL2 = "#2bc4b2", "#63e0cf"
INK = "#eaf3f2"
MUT = "#9fb4ba"
GRAY = "#5c7076"
RAW = "#7d5b52"     # warm gray for "raw"
AMBER = "#d8a657"
OUT = Path(__file__).resolve().parent


def frame(w, h, rx=20):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>'
            f'<linearGradient id="acc" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{TEAL2}"/></linearGradient></defs>'
            f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{rx}" fill="url(#bg)" stroke="{STROKE}" stroke-width="1.5"/>')


# ---------------------------------------------------------------- banner.svg
def banner():
    w, h = 1200, 372
    s = [frame(w, h)]
    # faint grid
    s.append(f'<g opacity="0.06" stroke="{TEAL}" stroke-width="1">')
    for y in (93, 186, 279):
        s.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}"/>')
    s.append('</g>')
    s.append(f'<text x="56" y="66" fill="{TEAL}" font-size="15" font-weight="600" letter-spacing="4">RUST · HERMETIC SANDBOX · TYPED AGENT FEEDBACK</text>')
    s.append(f'<text x="52" y="150" fill="{INK}" font-size="86" font-weight="800" letter-spacing="-2">sbx</text>')
    s.append(f'<text x="180" y="150" fill="{MUT}" font-size="26" font-weight="600">a hermetic executor for coding agents</text>')
    s.append(f'<text x="56" y="196" fill="{MUT}" font-size="20">Run code in a 4 ms throw-away sandbox and hand the agent a typed <tspan fill="{TEAL2}">verdict</tspan> —</text>')
    s.append(f'<text x="56" y="223" fill="{MUT}" font-size="20">parsed crashes, diagnostics, failing tests, and a <tspan fill="{TEAL2}">delta</tspan> vs the last run — not 30 KB of stdout.</text>')

    # signature visual: raw log -> verdict
    bx, by, bw, bh = 56, 250, 470, 96
    s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="8" fill="{PANEL}" stroke="{STROKE}"/>')
    s.append(f'<text x="{bx+14}" y="{by+20}" fill="{RAW}" font-size="12" font-weight="600" letter-spacing="2" font-family="monospace">RAW STDOUT · ~30 KB</text>')
    import math
    for i in range(11):
        y = by + 32 + i * 5.4
        ln = 20 + (i * 53 % (bw - 60))
        s.append(f'<line x1="{bx+14}" y1="{y:.0f}" x2="{bx+14+ln}" y2="{y:.0f}" stroke="{RAW}" stroke-width="2" opacity="0.5"/>')
    # arrow
    ax = bx + bw + 26
    s.append(f'<text x="{ax}" y="{by+56}" fill="{TEAL}" font-size="40" font-weight="700">→</text>')
    s.append(f'<text x="{ax-4}" y="{by+80}" fill="{MUT}" font-size="12" font-family="monospace">4 ms</text>')
    # verdict panel
    vx = ax + 60
    vw = w - vx - 56
    s.append(f'<rect x="{vx}" y="{by}" width="{vw}" height="{bh}" rx="8" fill="{PANEL}" stroke="{TEAL}" stroke-opacity="0.5"/>')
    lines = [
        (TEAL, '[sbx] CRASH  exit=1  raw=2820B'),
        (INK, 'crash: AddressSanitizer heap-buffer-overflow'),
        (AMBER, '  hint: read/write past the end of a heap allocation'),
        (MUT, '  at histogram.c:20 in main'),
        (MUT, '  delta: crash SAME as last run'),
    ]
    for i, (c, t) in enumerate(lines):
        s.append(f'<text x="{vx+14}" y="{by+22+i*15}" fill="{c}" font-size="12.5" font-family="monospace">{t}</text>')
    s.append('</svg>')
    (OUT / 'banner.svg').write_text('\n'.join(s), encoding='utf-8')


# ---------------------------------------------------------------- architecture.svg
def architecture():
    w, h = 1200, 300
    s = [frame(w, h)]
    s.append(f'<text x="40" y="44" fill="{TEAL}" font-size="14" font-weight="600" letter-spacing="3">POLICY / MECHANISM SPLIT · THREE CRATES</text>')
    stages = [
        ("Spec", "command +\nisolation profile", MUT),
        ("hermit-core", "clone() into user/pid/mount/net\nns · pivot_root · seccomp · lo up\nno ASLR · rlimits · 4 ms", TEAL),
        ("Outcome", "exit / signal / timeout\nrusage · streams · Applied{}", MUT),
        ("feedback", "parse: sanitizer · gcc/clang/rustc\npytest/cargo · tracebacks\ndiff(prev,cur) → Delta", TEAL),
        ("Verdict", "crash · diagnostics · tests\n+ what changed since last run", TEAL2),
    ]
    n = len(stages)
    gap = 24
    bw = (w - 80 - gap * (n - 1)) / n
    x = 40
    y = 90
    bh = 150
    for i, (title, body, col) in enumerate(stages):
        fill = PANEL
        s.append(f'<rect x="{x:.0f}" y="{y}" width="{bw:.0f}" height="{bh}" rx="10" fill="{fill}" stroke="{col}" stroke-opacity="0.55"/>')
        s.append(f'<text x="{x+bw/2:.0f}" y="{y+32}" fill="{col}" font-size="19" font-weight="700" text-anchor="middle" font-family="monospace">{title}</text>')
        for j, line in enumerate(body.split("\n")):
            s.append(f'<text x="{x+bw/2:.0f}" y="{y+58+j*17}" fill="{MUT}" font-size="12.5" text-anchor="middle">{line}</text>')
        if i < n - 1:
            ax = x + bw + gap / 2
            s.append(f'<text x="{ax:.0f}" y="{y+bh/2+8:.0f}" fill="{TEAL}" font-size="24" text-anchor="middle" font-weight="700">→</text>')
        x += bw + gap
    s.append(f'<text x="40" y="{y+bh+40}" fill="{MUT}" font-size="14">The executor owns the facts, so it emits <tspan fill="{INK}">facts</tspan>; because it sees consecutive runs, it emits <tspan fill="{INK}">what changed</tspan>. Deterministic parsers, no LLM in the loop.</text>')
    s.append('</svg>')
    (OUT / 'architecture.svg').write_text('\n'.join(s), encoding='utf-8')


# ---------------------------------------------------------------- context-reduction.svg
def context():
    # shown_raw -> shown_typed per task, run-before-edit control (REPORT §6.5)
    data = [
        ("cpp-vector-oob", 36302, 1836),
        ("use-after-free", 17949, 1515),
        ("stack-strcpy", 5854, 1295),
        ("double-free", 4532, 3306),
        ("null-deref", 3630, 1289),
        ("heap-overflow", 1199, 981),
    ]
    w, h = 1200, 430
    s = [frame(w, h)]
    s.append(f'<text x="40" y="46" fill="{INK}" font-size="22" font-weight="700">Same fix, far less context — 7–20× fewer characters shown</text>')
    s.append(f'<text x="40" y="72" fill="{MUT}" font-size="14">Claude Sonnet 4.6, run-before-edit control: raw stdout vs the typed verdict, per task (log scale). Equal success, equal turns.</text>')
    import math
    x0, y0 = 210, 110
    plotw, ploth = w - x0 - 120, 280
    lo, hi = 100, 40000
    def xp(v):
        return x0 + (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * plotw
    # gridlines
    for gv in (100, 1000, 10000):
        gx = xp(gv)
        s.append(f'<line x1="{gx:.0f}" y1="{y0}" x2="{gx:.0f}" y2="{y0+ploth}" stroke="{STROKE}" stroke-width="1"/>')
        s.append(f'<text x="{gx:.0f}" y="{y0+ploth+20}" fill="{MUT}" font-size="12" text-anchor="middle" font-family="monospace">{gv:,}</text>')
    rowh = ploth / len(data)
    for i, (name, raw, typ) in enumerate(data):
        cy = y0 + i * rowh + rowh / 2
        s.append(f'<text x="{x0-14}" y="{cy+4:.0f}" fill="{INK}" font-size="13" text-anchor="end" font-family="monospace">{name}</text>')
        # raw bar
        s.append(f'<rect x="{x0}" y="{cy-13:.0f}" width="{xp(raw)-x0:.0f}" height="11" rx="2" fill="{RAW}" opacity="0.85"/>')
        s.append(f'<text x="{xp(raw)+6:.0f}" y="{cy-3:.0f}" fill="{RAW}" font-size="11" font-family="monospace">{raw:,}</text>')
        # typed bar
        s.append(f'<rect x="{x0}" y="{cy+2:.0f}" width="{max(xp(typ)-x0,2):.0f}" height="11" rx="2" fill="url(#acc)"/>')
        s.append(f'<text x="{xp(typ)+6:.0f}" y="{cy+12:.0f}" fill="{TEAL2}" font-size="11" font-family="monospace">{typ:,}</text>')
        red = raw / typ
        s.append(f'<text x="{x0+plotw+70:.0f}" y="{cy+4:.0f}" fill="{TEAL2 if red>=2 else MUT}" font-size="14" font-weight="700" text-anchor="end">{red:.0f}×</text>')
    s.append(f'<rect x="{x0}" y="{y0+ploth+34}" width="12" height="11" rx="2" fill="{RAW}"/><text x="{x0+18}" y="{y0+ploth+44}" fill="{MUT}" font-size="12">raw stdout</text>')
    s.append(f'<rect x="{x0+110}" y="{y0+ploth+34}" width="12" height="11" rx="2" fill="url(#acc)"/><text x="{x0+128}" y="{y0+ploth+44}" fill="{MUT}" font-size="12">typed verdict</text>')
    s.append(f'<text x="{w-120}" y="{y0-14}" fill="{MUT}" font-size="12" text-anchor="middle">reduction</text>')
    s.append('</svg>')
    (OUT / 'context-reduction.svg').write_text('\n'.join(s), encoding='utf-8')


# ---------------------------------------------------------------- steer.svg (dark)
def steer():
    # fix / decoy / first-edit per task (corrupt_line arm)
    data = [
        ("heap-overflow", 16, 20, 24, 16),
        ("null-deref", 19, 21, 45, 19),
        ("use-after-free", 29, 21, 37, 29),
        ("vector-oob", 14, 15, 26, 14),
        ("haystack", 27, 27, 15, 27),
    ]
    w, h = 1200, 430
    s = [frame(w, h)]
    s.append(f'<text x="40" y="46" fill="{INK}" font-size="22" font-weight="700">We lied to the agent about its bug. It didn\'t listen.</text>')
    s.append(f'<text x="40" y="72" fill="{MUT}" font-size="14">Execution held byte-identical; only the verdict\'s fault line is corrupted to a plausible decoy. The first edit (●) still lands on the true fix.</text>')
    x0, y0 = 200, 108
    plotw = w - x0 - 90
    lo, hi = 1, 50
    xp = lambda v: x0 + (v - lo) / (hi - lo) * plotw
    rowh = 290 / len(data)
    # legend
    lx = 40
    s.append(f'<rect x="{lx}" y="{y0-30}" width="14" height="9" rx="2" fill="{TEAL}" opacity="0.30"/><text x="{lx+20}" y="{y0-22}" fill="{MUT}" font-size="12">true fix</text>')
    s.append(f'<circle cx="{lx+150}" cy="{y0-26}" r="4" fill="{AMBER}"/><text x="{lx+160}" y="{y0-22}" fill="{MUT}" font-size="12">decoy the verdict pointed at</text>')
    s.append(f'<circle cx="{lx+360}" cy="{y0-26}" r="5" fill="{INK}"/><text x="{lx+372}" y="{y0-22}" fill="{MUT}" font-size="12">agent\'s first edit</text>')
    for i, (name, fix, crash, decoy, edit) in enumerate(data):
        cy = y0 + i * rowh + rowh / 2
        s.append(f'<text x="{x0-16}" y="{cy+4:.0f}" fill="{INK}" font-size="13" text-anchor="end" font-family="monospace">{name}</text>')
        s.append(f'<line x1="{x0}" y1="{cy:.0f}" x2="{x0+plotw}" y2="{cy:.0f}" stroke="{STROKE}" stroke-width="1.5"/>')
        s.append(f'<rect x="{xp(fix)-9:.0f}" y="{cy-12:.0f}" width="18" height="24" rx="4" fill="{TEAL}" opacity="0.28"/>')
        s.append(f'<circle cx="{xp(decoy):.0f}" cy="{cy:.0f}" r="5" fill="{AMBER}"/>')
        s.append(f'<text x="{xp(decoy):.0f}" y="{cy-14:.0f}" fill="{AMBER}" font-size="10" text-anchor="middle" font-family="monospace">L{decoy}</text>')
        s.append(f'<circle cx="{xp(edit):.0f}" cy="{cy:.0f}" r="6" fill="{INK}"/>')
    s.append(f'<text x="{x0}" y="{y0+300}" fill="{MUT}" font-size="12">line number →   Claude Sonnet 4.6 · 0/7 steered · the decoy is never touched · byte-identical execution audited</text>')
    s.append('</svg>')
    (OUT / 'steer.svg').write_text('\n'.join(s), encoding='utf-8')


banner(); architecture(); context(); steer()
print("wrote:", *(p.name for p in (OUT/'banner.svg', OUT/'architecture.svg', OUT/'context-reduction.svg', OUT/'steer.svg')))
