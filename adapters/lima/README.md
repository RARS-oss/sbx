# sbx on macOS (and anywhere) via Lima

sbx's isolation is Linux-native (user namespaces + seccomp + `pivot_root`), which macOS and Windows
don't provide. The portable answer is a **persistent** Linux micro-VM behind the CLI — startup is paid
once, so each `sbx run` stays fast. This is the macOS counterpart of the Windows→WSL bridge the bench
harness already uses (`SBX_WSL`).

```bash
brew install lima
git clone https://github.com/RARS-oss/sbx ~/sbx          # so the VM can build it (or set SBX_SRC)
limactl start --name=sbx ~/sbx/adapters/lima/sbx.yaml     # first start builds sbx (~2-3 min)

~/sbx/adapters/lima/sbx run -- cargo test                 # then use it like a local binary
~/sbx/adapters/lima/sbx run --repeat 10 -- pytest -q
~/sbx/adapters/lima/sbx selftest
```

`sbx.yaml` provisions Ubuntu 24.04 (Virtualization.framework), installs Rust + build tools, and
`cargo install`s the CLI. The `sbx` wrapper runs `limactl shell --workdir "$PWD" sbx sbx …`, so your
cwd (mounted at the same path) is the work dir and `--work` / `--overlay` paths resolve unchanged.

> Status: authored to mirror the tested WSL2 path; **not yet exercised on macOS in CI** (no macOS
> runner in this project's environment). PRs with a macOS run are welcome. On Linux, use `sbx` directly
> — no VM needed.
