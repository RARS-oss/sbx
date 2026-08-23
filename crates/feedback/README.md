# feedback

Typed, delta-aware machine feedback for coding agents.

`feedback` parses compiler diagnostics (rustc, clang/gcc), sanitizer & crash reports
(ASan/UBSan, Python tracebacks incl. `rich`), and test-runner output (libtest, pytest,
go test, Jest/Vitest, JUnit/Surefire/Gradle) into a structured `Verdict`; diffs two
consecutive verdicts into a `Delta`; and renders a compact, agent-facing summary.
Diagnostics are enriched with their **enclosing function** (via Tree-sitter) so a delta
survives line-number churn from unrelated edits.

Part of the [sbx](https://github.com/RARS-oss/sbx) workspace.

## License

MIT
