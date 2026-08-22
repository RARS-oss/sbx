#!/usr/bin/env bash
# Regenerate everything derived from results: per-model analysis tables (markdown), figures (SVG +
# PNG previews), and docs/report.html from docs/REPORT.md. Idempotent; run after any pilot finishes.
#   bash bench/scripts/finalize_report.sh
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
mkdir -p docs/paper bench/out/figs bench/out/figs-png
shopt -s nullglob
files=(bench/out/pilot-*.jsonl)
if [ ${#files[@]} -eq 0 ]; then echo "no results in bench/out"; exit 0; fi
for f in "${files[@]}"; do
  base=$(basename "$f" .jsonl)
  "$SBX_PY" bench/agent/analyze.py "$f" --md "docs/paper/${base}.md" >/dev/null && echo "analysis -> docs/paper/${base}.md"
done
"$SBX_PY" bench/agent/plot.py --results "${files[@]}" --startup bench/out/startup_bench.json --out bench/out/figs
"$SBX_PY" bench/agent/plot.py --results "${files[@]}" --startup bench/out/startup_bench.json --out bench/out/figs-png --fmt png >/dev/null
"$SBX_PY" bench/agent/build_report_html.py --md docs/REPORT.md --figs bench/out/figs --out docs/report.html
echo "--- summaries ---"
for f in "${files[@]}"; do echo "== $f"; "$SBX_PY" bench/agent/run.py --summary --out "$f" | head -12; done
echo "done $(date +%T)"
