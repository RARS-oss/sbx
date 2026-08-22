# Verdict schema (v0.1)

The `Verdict` is the contract between the executor and whoever feeds an agent (CLI,
Claude Code hook, mini-SWE-agent adapter, Harbor backend). Field names are stable; new
optional fields may be added. Produced by `feedback::distill`, serialised with serde.

```jsonc
{
  "status": "pass | tests_failed | crash | runtime_error | build_failed | timeout | setup_failed | unknown",
  "exit_code": 1,              // null if killed by signal / timeout
  "signal": "SIGSEGV",         // null unless killed by a signal
  "timed_out": false,
  "wall_ms": 174,

  "diagnostics": [             // compiler / linter / UBSan diagnostics, deduplicated
    { "tool": "gcc", "severity": "error", "file": "src/main.c", "line": 12, "col": 5,
      "code": null, "message": "'total' undeclared (first use in this function)" },
    { "tool": "rustc", "severity": "error", "file": "src/main.rs", "line": 4, "col": 18,
      "code": "E0308", "message": "mismatched types" }
  ],
  "error_groups": 2,           // distinct (tool, code | normalised message) among errors

  "crash": {                   // null when the program did not crash
    "tool": "AddressSanitizer | UndefinedBehaviorSanitizer | LeakSanitizer | ThreadSanitizer | MemorySanitizer | signal | python",
    "kind": "heap-buffer-overflow",
    "access": "WRITE of size 4",
    "address": "0x602000000038",
    "message": "0x602000000038 is located 0 bytes after 40-byte region [...]",
    "frames": [ { "idx": 0, "func": "fill", "file": "/work/overflow.c", "line": 9, "col": 14, "user": true }, ... ],
    "alloc_frames": [ ... ],   // ASan "allocated by thread T0 here:"
    "free_frames":  [ ... ],   // ASan "freed by thread T0 here:"
    "first_user_frame": { "idx": 0, "func": "fill", "file": "/work/overflow.c", "line": 9, "col": 14, "user": true },
    "summary": "heap-buffer-overflow /work/overflow.c:9:14 in fill"
  },

  "tests": {                   // null when no test runner output was recognised
    "runner": "pytest | cargo-test | ctest | gtest",
    "passed": 5, "failed": 2, "errors": 0, "skipped": 0,
    "failures": [
      { "name": "tests/test_calc.py::test_divide", "file": "tests/test_calc.py", "line": null,
        "message": "ZeroDivisionError: division by zero" }
    ]
  },

  "tail": [ "make: *** [Makefile:12: build/main.o] Error 1" ],  // ≤12 unclaimed, non-empty lines
  "raw_bytes": 2820            // size of stdout+stderr the verdict was distilled from
}
```

## Status precedence

`setup_failed` > `timeout` > `crash` (sanitizer / signal) > `build_failed` (compiler errors
and non-zero exit) > `tests_failed` > `runtime_error` (Python/Rust panic without tests, or
non-zero exit with nothing recognised) > `pass` (exit 0).

## Delta (v0.1)

Produced by `feedback::diff(prev, cur)`.

```jsonc
{
  "status_from": "crash", "status_to": "crash",
  "fixed": [ /* Diagnostic */ ], "new": [ /* Diagnostic */ ], "unchanged": 3,
  "tests_fixed": ["t.py::a"], "tests_broken": ["t.py::c"], "tests_still_failing": 1,
  "crash_gone": false,
  "crash_new": null,                          // "kind @ file:line"
  "crash_moved": { "from": "heap-buffer-overflow @ /work/overflow.c:9",
                   "to":   "heap-use-after-free @ /work/uaf.c:15" },
  "crash_same": false
}
```

Matching rules:
- A diagnostic is *the same* if `tool`, `severity`, `file` match, the normalised message
  matches (quoted identifiers, hex and decimal numbers replaced by `_`, "; did you mean …"
  stripped; `code` must match when both have one), and `|Δline| ≤ 3`.
- A crash is *the same* if the kind matches and the first user frame is in the same file
  within ±3 lines; otherwise it *moved*.
- Tests are matched by name.

## Rendering

`feedback::render(verdict, delta, opts)` prints, in order: header line → delta line (+ new
diagnostics / newly failing tests) → crash block (first user frame, frames with user frames
first, alloc/free sites) → diagnostics (errors first, grouped by file) → failing tests → tail
→ the fixed footer `(full log available on request: sbx log)`. Deterministic and stable so
that two renderings can themselves be diffed.
