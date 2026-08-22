# Source this inside WSL/Linux before running bench scripts.
#   source bench/scripts/env.sh
export PATH="$HOME/.cache/sbx-target/release:$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/.cache/sbx-target}"
export SBX_REPO="${SBX_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export SBX_VENV="${SBX_VENV:-$HOME/.sbx-venv}"
if [ -x "$SBX_VENV/bin/python" ]; then
  export SBX_PY="$SBX_VENV/bin/python"
else
  export SBX_PY="python3"
fi
