# Releasing sbx

Three distribution channels, all wired and verified. Cutting a release is two actions:
**publish the crates** (crates.io) and **push a tag** (which fires GitHub Releases + GHCR).

The workspace shares one version (`[workspace.package] version` in the root `Cargo.toml`).
Bump it there; every crate inherits it via `version.workspace = true`.

---

## 1. crates.io (`cargo install sbx-cli`)

The three crates carry the required metadata (`description`, `license`, `repository`,
`keywords`, `categories`, per-crate `README.md`). The path dependencies in
`[workspace.dependencies]` also carry a `version`, so they resolve from the registry once
published while still building from `path` locally.

**Publish order matters** — a crate can only be published after every crate it depends on is
already on the index:

```bash
cargo publish -p hermit-core     # leaf, no internal deps
cargo publish -p feedback        # leaf, no internal deps
cargo publish -p sbx-cli         # depends on hermit-core + feedback
```

Between steps, wait for the crate to appear on the index (usually seconds; `cargo` will retry).

**Verify before publishing.** `hermit-core` and `feedback` can be dry-run directly:

```bash
cargo publish --dry-run -p hermit-core   # OK
cargo publish --dry-run -p feedback      # OK
```

`cargo publish --dry-run -p sbx-cli` **fails until `feedback`/`hermit-core` are actually on
crates.io** — dry-run strips the `path` and looks the dependency up on the index, which is the
normal chicken-and-egg for a multi-crate workspace. sbx-cli is verified by the workspace build
and test suite (`cargo test --workspace`, 27 tests) in the meantime; its publish is the last
step above, after the two libraries are live.

Requires a crates.io API token (`cargo login <token>`). This is the maintainer's action — the
token is never stored in the repo.

---

## 2. GitHub Release binary + GHCR image (push a tag)

Both are produced by [`.github/workflows/release.yml`](../.github/workflows/release.yml) on any
tag matching `v*`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

- **`binary` job** — `cargo build --release -p sbx-cli`, strips it, tars it as
  `sbx-<tag>-x86_64-unknown-linux-gnu.tar.gz`, and attaches it to the GitHub Release
  (`softprops/action-gh-release`, with auto-generated notes). Users then:

  ```bash
  curl -L https://github.com/RARS-oss/sbx/releases/latest/download/sbx-v0.1.0-x86_64-unknown-linux-gnu.tar.gz \
    | tar xz && ./sbx selftest
  ```

- **`container` job** — builds the [`Dockerfile`](../Dockerfile) and pushes to
  `ghcr.io/rars-oss/sbx` tagged with both the version and `latest`
  (`docker/metadata-action` + `docker/build-push-action`). Uses the workflow's `GITHUB_TOKEN`;
  no extra secret needed. The package must be allowed to publish to GHCR (repo → Settings →
  Actions → Workflow permissions → *Read and write*, already requested by the workflow's
  `permissions: packages: write`).

---

## 3. Docker image (local build)

The [`Dockerfile`](../Dockerfile) is a two-stage build: `rust:1-slim` compiles `sbx`, then it
ships in a `debian:stable-slim` image with the toolchains sbx sandboxes (`build-essential`,
`clang`, `python3`).

```bash
docker build -t sbx .
docker run --security-opt seccomp=unconfined sbx selftest
docker run --security-opt seccomp=unconfined -v "$PWD:/work" sbx \
  run -- sh -c 'gcc -fsanitize=address a.c && ./a.out'
```

`--security-opt seccomp=unconfined` is required because Docker's default seccomp profile blocks
the `clone`/`unshare` namespace flags sbx uses to *build* its sandbox. sbx then installs its own
seccomp denylist inside the sandbox it creates, so the workload is still confined. On a host that
also restricts unprivileged user namespaces you may additionally need `--privileged` or a custom
profile that permits `unshare(CLONE_NEW*)`.

---

## Checklist

1. Bump `[workspace.package] version` in the root `Cargo.toml`.
2. `cargo test --workspace` — green (27 tests).
3. `cargo publish --dry-run -p hermit-core` and `-p feedback` — OK.
4. `cargo publish -p hermit-core` → `-p feedback` → `-p sbx-cli`.
5. `git tag vX.Y.Z && git push origin vX.Y.Z` — fires the binary + container jobs.
6. Confirm the GitHub Release assets and the `ghcr.io/rars-oss/sbx:vX.Y.Z` image exist.
