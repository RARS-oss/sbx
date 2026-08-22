#!/usr/bin/env bash
# Create the Python venv used by the benchmark harness and install the Anthropic SDK.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
if [ ! -x "$SBX_VENV/bin/python" ]; then
  python3 -m venv "$SBX_VENV"
fi
"$SBX_VENV/bin/pip" install -q --upgrade pip >/dev/null
"$SBX_VENV/bin/pip" install -q anthropic >/dev/null
"$SBX_VENV/bin/python" -c 'import anthropic, sys; print("anthropic", anthropic.__version__, "python", sys.version.split()[0])'
