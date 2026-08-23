#!/usr/bin/env python3
"""Build docs/report.html from docs/REPORT.md with figures inlined as SVG.

  python bench/agent/build_report_html.py --md docs/REPORT.md --figs bench/out/figs --out docs/report.html

Minimal Markdown → HTML (headings, paragraphs, lists, tables, fenced code, inline code/bold/italic,
links); any line that is just a figure filename reference in backticks or a `*Figure:* ...` line
containing fig_*.svg gets the SVG inlined (self-contained page; works as a Claude artifact).
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

CSS = """
:root{--bg:#F6F7F5;--panel:#fff;--ink:#1b2125;--ink2:#3f4950;--muted:#69747c;--line:#d5dbd8;--acc:#2c6b8c;--acc2:#2e7d4f;--code:#eef2f0}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#14181b;--panel:#1e2529;--ink:#e6eaec;--ink2:#c4ccd1;--muted:#909ba4;--line:#2f393f;--acc:#78b6d6;--acc2:#72c596;--code:#242c31}}
:root[data-theme="dark"]{--bg:#14181b;--panel:#1e2529;--ink:#e6eaec;--ink2:#c4ccd1;--muted:#909ba4;--line:#2f393f;--acc:#78b6d6;--acc2:#72c596;--code:#242c31}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 "Source Serif 4",Georgia,serif}
.wrap{max-width:860px;margin:0 auto;padding:40px 22px 80px}
h1{font-family:"Newsreader",Georgia,serif;font-weight:500;font-size:2.2rem;line-height:1.12;margin:.2rem 0 .6rem;letter-spacing:-.01em}
h2{font-family:"Newsreader",Georgia,serif;font-weight:500;font-size:1.55rem;margin:2.2rem 0 .7rem;padding-top:1.2rem;border-top:1px solid var(--line)}
h3{font-size:1.08rem;margin:1.5rem 0 .5rem;font-family:"Source Sans 3",system-ui,sans-serif}
p{margin:0 0 .9rem}em.lede{color:var(--ink2)}
code,pre{font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;font-size:.84em}
code{background:var(--code);padding:.08em .35em;border-radius:3px}
pre{background:var(--code);border:1px solid var(--line);border-radius:4px;padding:.9rem 1rem;overflow-x:auto;line-height:1.45}
pre code{background:none;padding:0}
.tbl{overflow-x:auto;margin:.6rem 0 1.2rem;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-family:"Source Sans 3",system-ui,sans-serif;font-size:.9rem;min-width:560px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);background:var(--bg);white-space:nowrap}
tr:last-child td{border-bottom:none}
figure{margin:1.2rem 0 1.6rem;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:6px}
figure svg{width:100%;height:auto;display:block}
figcaption{font-family:"Source Sans 3",system-ui,sans-serif;font-size:.85rem;color:var(--muted);margin-top:.4rem}
ul,ol{margin:0 0 1rem;padding-left:1.3rem}li{margin:0 0 .3rem}
a{color:var(--acc)}hr{border:0;border-top:1px solid var(--line);margin:1.6rem 0}
.meta{font-family:"JetBrains Mono",monospace;font-size:.74rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
blockquote{border-left:3px solid var(--acc);margin:0 0 1rem;padding:.4rem .9rem;color:var(--ink2);background:var(--panel)}
"""
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">'


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    s = s.replace("\\$", "$")
    return s


def convert(md: str, figs: Path, base: Path) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []
    para: list[str] = []
    list_type = None
    list_buf: list[str] = []
    table_buf: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []

    def flush_list():
        nonlocal list_buf, list_type
        if list_buf:
            out.append(f"<{list_type}>" + "".join(f"<li>{inline(x)}</li>" for x in list_buf) + f"</{list_type}>")
            list_buf = []
            list_type = None

    def flush_table():
        nonlocal table_buf
        if table_buf:
            rows = [r for r in table_buf if not re.match(r"^\s*\|?\s*:?-{2,}", r)]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            if cells:
                h = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
                body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                out.append(f'<div class="tbl"><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>')
            table_buf = []

    def maybe_figures(text: str) -> bool:
        names = re.findall(r"(fig_[A-Za-z0-9_.\-]+\.svg)", text)
        if not names:
            return False
        for n in names:
            p = figs / n
            if p.exists():
                svg = p.read_text(encoding="utf-8")
                svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
                svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg)
                out.append(f"<figure>{svg}<figcaption>{html.escape(n)}</figcaption></figure>")
            else:
                out.append(f'<p class="meta">figure pending: {html.escape(n)}</p>')
        return True

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                flush_para(); flush_list(); flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if line.strip().startswith("|"):
            flush_para(); flush_list()
            table_buf.append(line)
            i += 1
            continue
        else:
            flush_table()
        if not line.strip():
            flush_para(); flush_list()
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            flush_para(); flush_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.strip() == "---":
            flush_para(); flush_list()
            out.append("<hr>")
            i += 1
            continue
        if line.startswith("> "):
            flush_para(); flush_list()
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            i += 1
            continue
        if "fig_" in line and ".svg" in line and (line.strip().startswith("*Figure") or line.strip().startswith("*Figures")):
            flush_para(); flush_list()
            out.append(f"<p>{inline(line)}</p>")
            maybe_figures(line)
            i += 1
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+\.svg)\)\s*$", line)
        if m:
            flush_para(); flush_list()
            alt, src = m.group(1), m.group(2)
            p = base / src
            # containment: only inline SVGs that live under the markdown's own dir
            # (a crafted absolute / ../ reference must never read files outside the repo).
            try:
                p.resolve().relative_to(base.resolve())
                contained = True
            except ValueError:
                contained = False
            if contained and p.exists():
                svg = p.read_text(encoding="utf-8")
                svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
                svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg)
                out.append(f"<figure>{svg}<figcaption>{html.escape(alt or src)}</figcaption></figure>")
            else:
                out.append(f'<p class="meta">figure pending: {html.escape(src)}</p>')
            i += 1
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            flush_para()
            if list_type != "ul":
                flush_list(); list_type = "ul"
            list_buf.append(m.group(1))
            i += 1
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m:
            flush_para()
            if list_type != "ol":
                flush_list(); list_type = "ol"
            list_buf.append(m.group(1))
            i += 1
            continue
        para.append(line.strip())
        i += 1
    flush_para(); flush_list(); flush_table()
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, default=Path("docs/REPORT.md"))
    ap.add_argument("--figs", type=Path, default=Path("bench/out/figs"))
    ap.add_argument("--out", type=Path, default=Path("docs/report.html"))
    ap.add_argument("--title", default="sbx Technical Report")
    a = ap.parse_args()
    md = a.md.read_text(encoding="utf-8")
    body = convert(md, a.figs, a.md.parent)
    page = f"<title>{html.escape(a.title)}</title>\n{FONTS}\n<style>{CSS}</style>\n<div class=\"wrap\">\n{body}\n</div>\n"
    a.out.write_text(page, encoding="utf-8")
    print(f"wrote {a.out} ({len(page)} bytes)")


if __name__ == "__main__":
    main()
