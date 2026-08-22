#!/usr/bin/env python3
"""Does the Verdict point at the right line? For every task with a crash/panic/exception, run the
shipped (buggy) version inside sbx and compare the Verdict's first user frame (or first error
diagnostic) with the ground-truth faulting line taken from the task sources.

  python bench/scripts/localization_check.py          (run from repo root, sbx on PATH)

Ground truth = the line where the fault *manifests* (crash site), which is what a sanitizer reports
and what the agent needs to start from; the fix may be elsewhere (e.g. a bound check a few lines up).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "bench" / "tasks"

# task -> (file, acceptable lines, what)
GROUND_TRUTH = {
    "c-heap-overflow": ("histogram.c", {20}, "counts[v]++ with v == n (off-by-one bound)"),
    "c-use-after-free": ("list.c", {21}, "loop increment cur = cur->next after free(cur)"),
    "c-stack-strcpy": ("greet.c", {18}, "strcpy(name, line) into char[32]"),
    "c-double-free": ("pool.c", {30}, "second free in pool_free after pool_reset freed items"),
    "c-null-deref": ("tokenizer.c", {21}, "while (cur->next) with cur == NULL"),
    "c-signed-overflow": ("checksum.c", {5}, "h * 31 + b overflows int"),
    "cpp-vector-oob": ("grid.cpp", {15}, "g[rr][cc] with rr == rows / cc == cols"),
    "rust-index-panic": ("main.rs", {10}, "values[start] with start == len-k+1"),
    "py-unittest-crash": ("inventory.py", {16, 18, 19}, "del/-= on a missing key (any failing test's innermost frame)"),
    "c-compile-error": ("stats.c", {49, 50}, "first compile error (int result = char*; puts(resutl))"),
}


def run_task(task_dir: Path) -> dict:
    t = tomllib.loads((task_dir / "task.toml").read_text())
    home = str(Path.home())
    w = Path(tempfile.mkdtemp(prefix="sbx-loc-"))
    for p in task_dir.iterdir():
        if p.name in ("solution", ".sbx"):
            continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, w / p.name)
    cmd = ["sbx", "run", "--work", str(w), "--no-delta", "--json"]
    for p in t.get("ro_binds", []):
        cmd += ["--ro", p.replace("~", home)]
    for k, v in t.get("env", {}).items():
        cmd += ["--env", f"{k}={str(v).replace('~', home)}"]
    cmd += ["--", "sh", "-c", t["run"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(w, ignore_errors=True)
    return json.loads(r.stdout)


def main() -> int:
    rows = []
    hits = 0
    total = 0
    for name, (gfile, glines, what) in GROUND_TRUTH.items():
        d = TASKS / name
        if not d.exists():
            continue
        j = run_task(d)
        v = j["verdict"]
        got_file = got_line = None
        source = ""
        c = v.get("crash")
        if c and c.get("first_user_frame"):
            f = c["first_user_frame"]
            got_file, got_line, source = f.get("file"), f.get("line"), f"crash:{c['tool']} {c['kind']}"
        elif c and c.get("frames"):
            f = c["frames"][0]
            got_file, got_line, source = f.get("file"), f.get("line"), f"crash(frame0):{c['tool']}"
        else:
            errs = [x for x in v.get("diagnostics", []) if x["severity"] == "error"]
            if errs:
                got_file, got_line, source = errs[0].get("file"), errs[0].get("line"), f"diag:{errs[0]['tool']}"
            elif v.get("tests") and v["tests"]["failures"]:
                # any failing test whose innermost frame hits the ground truth counts
                fs = v["tests"]["failures"]
                hit = next((f for f in fs if (f.get("file") or "").split("/")[-1] == gfile and f.get("line") in glines), None)
                ff = hit or fs[0]
                got_file, got_line, source = ff.get("file"), ff.get("line"), f"test-failure ({len(fs)} failures)"
        total += 1
        ok = bool(got_file) and got_file.split("/")[-1] == gfile and got_line in glines
        hits += ok
        rows.append((name, f"{gfile}:{'/'.join(map(str, sorted(glines)))}", f"{(got_file or '?').split('/')[-1]}:{got_line}", source, "✓" if ok else "✗", v["status"], v["raw_bytes"]))
    print("| task | ground truth | verdict points at | via | hit | status | raw B |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print(f"\nlocalization accuracy: {hits}/{total}")
    return 0 if hits == total else 1


if __name__ == "__main__":
    sys.exit(main())
