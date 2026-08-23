# sbx-cli

`sbx` runs a command inside a **hermetic Linux sandbox** and returns a **typed verdict** —
parsed compiler diagnostics, sanitizer/crash objects, and test results — plus a **delta**
against the previous run, instead of raw stdout/stderr. It is built for LLM coding agents:
less noise in the context window, a stable machine-readable shape, and a diff that says
*what changed* between two runs.

Part of the [sbx](https://github.com/RARS-oss/sbx) workspace.

## Install

```sh
cargo install sbx-cli
```

This installs the `sbx` binary. (Linux only — the sandbox uses user/pid/mount/net
namespaces, `pivot_root`, and seccomp.)

## Usage

```sh
sbx run -- cargo test              # typed verdict for a test run
sbx run --json -- ./a.out          # machine-readable JSON verdict
sbx run --repeat 20 -- ./flaky     # determinism / race probe over N runs
sbx run --overlay ./repo -- make   # overlay a large read-only tree
```

The previous verdict is remembered per working directory, so the next `sbx run`
also prints a **delta** (new / fixed / changed diagnostics, crashes, and tests).

See the [project README](https://github.com/RARS-oss/sbx) for architecture,
benchmarks, and the causal-attribution study.

## License

MIT
