# bench — the experiment harness

Everything needed to measure whether the *form* of execution feedback changes how many turns
and how much money a coding agent needs. One Python agent, one sandbox, one set of tasks, six
presentation conditions, one metric file.

```
bench/
├── agent/agent.py      # one episode: task × condition × model → JSON record (tokens, cost, turns, success…)
├── agent/run.py        # tasks × conditions × seeds, N workers, resumable; --summary prints the table
├── tasks/<name>/       # task.toml + sources + test.sh (+ solution/ for validation & mock runs)
├── scripts/env.sh      # PATH/venv setup (source it in WSL/Linux)
├── scripts/setup_venv.sh, validate_tasks.sh, smoke_agent.sh
└── out/                # results (.jsonl) — git-ignored
```

## Conditions (what the agent sees after `run`)

| condition | presentation | stands in for |
|---|---|---|
| `raw` | stdout + stderr verbatim + exit line | OpenHands/E2B-style "return everything" |
| `truncate30k` | middle truncation at 30 000 chars | Claude Code Bash tool default |
| `truncate10k` | 256 lines or 10 KiB, head 128 + tail 128 | Codex CLI default |
| `regex` | heuristic line compressor (drop shadow bytes/legend/deep frames/blank lines, collapse repeats, cap 8k) | RTK-style byte compressors |
| `structured` | sbx Verdict rendering | this project, no delta |
| `structured_delta` | sbx Verdict + Delta vs the previous run in the episode | this project |
| `--mask N` (orthogonal) | only the last N tool results verbatim, older ones replaced by a placeholder | observation masking (Complexity Trap) |

Execution is identical in every condition (`sbx run` inside the hermetic sandbox); only what the
model reads differs. That is the whole point of the experiment.

## Harness protocol v2 (after the first 7 B pilot)

Diagnosis of the 7 B v1 trajectories (`bench/agent/diagnose.py`): ~30–38 % of assistant turns were
prose-only or empty (each costing a turn of 15 plus a nudge), the model re-ran `run` without
editing, and it misread sanitizer vocabulary ("load of address … with insufficient space" → "input
parsing problem"). Changes, all applied identically across conditions:

- **Budget counts tool turns.** `--max-turns` now bounds turns that call a tool; prose/empty replies
  are nudged (≤ `--max-nudges`) without consuming budget (hard cap on API calls remains). Records
  carry `tool_turns`, `prose_turns`, `nudges`.
- **The `run` tool documents its own output format** — per condition: raw/truncated/compressed
  text for those arms; a short legend of the verdict lines (and of the `delta:` line) for the
  typed arms. This is the agent–computer interface of each condition, not extra help.
- **Deterministic hints** for known crash kinds (`hint:` line after `crash:` — ASan/UBSan/Rust panic
  glossary; Rust `feedback::render::hint_for`, mirrored in Python; parity-tested).
- **Check-script failures carry expected/got**, Rust panics are parsed, unittest failures point at
  the innermost frame of the code under test (see `bench/out/checks.md`).
- **Edit tracking:** every `write_file` records the changed line numbers (no file bodies) →
  `analyze.py` reports *edit-hit* (did any edit touch the ground-truth faulting line ±3) and
  *progress* (did a later run reach a better status or fewer failing checks than the first run) —
  finer-grained signals than binary success when the floor is low.

Result sets are tagged (`ollama_pilot.sh … <tag>` → `pilot-<model>-<tag>.jsonl`) so v1/v2 stay
separate.

## Metrics per episode (one JSON line)

`success` (independent sbx re-run of the task command after the agent stops, plus protected-file
hash check), `turns` (API calls), `tool_calls`, `tokens` {input, output, cache_read, cache_creation},
`cost_usd` (public price list, cache-aware), `wall_s`, `raw_bytes_total` (bytes the runs produced),
`shown_chars_total` (chars the model was shown), per-run status list, final stop reason, whether
`done` was called.

## Run

```bash
# in WSL / Linux
source bench/scripts/env.sh
cargo build --release -p sbx-cli            # puts sbx in ~/.cache/sbx-target/release (on PATH via env.sh)
bash bench/scripts/setup_venv.sh            # venv + anthropic SDK
bash bench/scripts/validate_tasks.sh        # every task: buggy fails, solution passes (inside sbx)
bash bench/scripts/smoke_agent.sh           # mock model: plumbing + renderer parity

# one real episode
export ANTHROPIC_API_KEY=...                # or `ant auth login`
$SBX_PY bench/agent/agent.py --task bench/tasks/c-use-after-free --condition structured_delta \
    --model claude-opus-5 --effort high --trajectory bench/out/traj.json

# the pilot: 3 tasks × 6 conditions × 3 seeds, 3 workers, resumable
$SBX_PY bench/agent/run.py --conditions raw,truncate30k,truncate10k,regex,structured,structured_delta \
    --seeds 3 --model claude-opus-5 --effort high --workers 3 --out bench/out/pilot.jsonl
$SBX_PY bench/agent/run.py --summary --out bench/out/pilot.jsonl
```

## Tasks (12, all validated: buggy fails / `solution/` passes, inside sbx)

| task | lang | failure class | raw bytes (buggy run) |
|---|---|---|---|
| c-heap-overflow | C | ASan heap-buffer-overflow (off-by-one bound) | 857 |
| c-use-after-free | C | ASan heap-use-after-free (temporal; 7 tests) | 17 766 |
| c-stack-strcpy | C | ASan stack-buffer-overflow (unbounded strcpy/strcat) | 5 710 |
| c-double-free | C | ASan double-free on the reset path | 4 408 |
| c-null-deref | C | ASan SEGV on NULL (empty list) | 3 505 |
| c-signed-overflow | C | UBSan signed integer overflow (rolling checksum) | 1 357 |
| c-compile-error | C | gcc: undeclared identifier, wrong type, warnings | 812 |
| cpp-vector-oob | C++ | ASan out-of-bounds in a grid neighbour count (7 tests) | 36 168 |
| rust-index-panic | Rust | index-out-of-bounds panic + off-by-one (rustc via ro-bound `~/.rustup`) | 4 781 |
| py-unittest-crash | Python | unittest ERROR (KeyError) + FAIL (wrong total) | 1 798 |
| py-unittest-logic | Python | unittest FAIL ×5 (interval merge off-by-one) | 4 190 |
| py-cli-args | Python | unittest FAIL ×6 (hand-rolled arg parser: `=`, `--`, repeats) | 6 758 |

Mock-mode smoke numbers (chars shown to the model per episode, two runs each):

| task | raw | regex | truncate10k | structured | structured_delta |
|---|---|---|---|---|---|
| c-heap-overflow | 981 | 935 | 981 | 724 | 807 |
| c-stack-strcpy | 5 854 | 2 726 | 5 854 | 820 | 861 |
| c-use-after-free | 17 949 | 7 682 | 10 434 | 851 | 892 |
| c-double-free | 4 532 | 2 678 | 4 532 | 1 123 | 1 164 |
| c-signed-overflow | 1 472 | 1 250 | 1 472 | 954 | 1 037 |
| c-compile-error | 900 | 898 | 900 | 718 | 795 |
| py-unittest-crash | 2 527 | 2 375 | 2 527 | 837 | 935 |
| py-unittest-logic | 5 166 | 4 719 | 5 166 | 1 298 | 1 396 |

Structured ≈ 0.05–0.8× raw depending on how noisy the failure is (0.05 on the UAF task, 0.8 on the
already-terse compile error); regex/truncation land between 0.46× and 1.0×. **Bytes are not the
claim** — turns and billed cost are; the table only shows the instrument behaves as intended.

## Local open-weight models (no API key): Ollama

`--model ollama:<name>` talks to Ollama's native `/api/chat` with tool calling (`OLLAMA_URL`,
default `http://localhost:11434`; from WSL2 a server in any WSL distro is reachable on localhost).
Same loop, same tools, same conditions; cost is 0 and tokens come from `prompt_eval_count` /
`eval_count`. Two accommodations for small open models, both recorded: (1) if the model answers
in prose instead of calling a tool, the loop nudges it up to `--max-nudges` times (counted as
turns, recorded as `nudges`); tool calls emitted as JSON text / `<tool_call>` tags are recovered;
(2) **one tool call per turn** — small models "plan" read+write+run in a single message before
seeing any result, which would turn a feedback experiment into a test of blind planning; the
Anthropic path keeps native parallel tool use. `qwen2.5-coder:3b` is the sanity/weak arm (it
mostly fails — expected); `qwen2.5-coder:7b` is the real local pilot model.

```bash
ollama pull qwen2.5-coder:7b                       # 4.7 GB; 3b (1.9 GB) fits a 3 GB GPU entirely
bash bench/scripts/ollama_pilot.sh qwen2.5-coder:7b 1     # 8 tasks × 6 conditions, 1 seed, 1 worker
$SBX_PY bench/agent/run.py --summary --out bench/out/pilot-qwen2.5-coder_7b.jsonl
```

Why this arm matters for the paper: an open, reproducible model family alongside Claude; and
weaker models are where feedback form should matter *most* (they cannot recover a truncated
report by reasoning), so it is a sensitivity probe as well as a cost-free pilot.

## Hosted open models (OpenAI-compatible endpoints) — when the local GPU is too small

On this machine (GTX 1060 3 GB, ~1.3 GB free VRAM) measured throughput is 3 B: 28 tok/s generation /
290 tok/s prompt (≈50 % on GPU); 7 B: **10 tok/s / 86 tok/s** (23 % on GPU) → ≈10 min per episode,
8 h per 48-episode run, and any concurrent run makes Ollama swap models in and out of VRAM (30 s
load per call). `--model openai:<name>` sends the same loop to any OpenAI-compatible chat-completions
API with tool calling:

```bash
export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # or https://api.cerebras.ai/v1, https://openrouter.ai/api/v1, DashScope …
export OPENAI_API_KEY=...
bash bench/scripts/openai_pilot.sh "qwen/qwen3-32b" 1 raw,structured_delta,truncate10k,structured 2 20 groq
```

Free tiers that serve Qwen-class open models at tens-to-hundreds of tok/s exist (Groq, Cerebras,
OpenRouter `:free` models; check each provider's current model list and rate limits). Cost is
recorded as 0 unless `OPENAI_PRICE_IN`/`OPENAI_PRICE_OUT` ($/1M) are set; prompt-cache reads are
taken from `usage.prompt_tokens_details.cached_tokens` when the provider reports them. Tool-call
text recovery and one-call-per-turn are applied as for Ollama.

## Adding a task

`task.toml`:

```toml
name = "c-double-free"
lang = "c"            # c | cpp | rust | python
family = "memory-safety"
bug = "double free"
prompt = """What the agent is told (what the program should do, that tests fail, what not to touch)."""
run = "sh test.sh"    # executed inside sbx by the agent's `run` tool and by the final verification
files = ["main.c"]    # shown to the agent in the initial message
protected = ["test.sh"]   # hash-checked; modifying them = failure
timeout = 120
```

Plus the buggy sources, `test.sh` (compile with `-fsanitize=address,undefined -U_FORTIFY_SOURCE
-D_FORTIFY_SOURCE=0` so ASan, not glibc fortify, reports), and `solution/` with the fixed files
(used by `validate_tasks.sh` and the mock model; never copied into the agent's workdir).

Design rules for tasks: the raw output should be *large* when the bug is present (several tests,
sanitizer reports), the fix should be local (≤ 5 lines) so the experiment measures diagnosis rather
than refactoring skill, and `test.sh` must print per-test `ok`/`FAIL` lines so every condition has
something to show.

## Analysis plan (see docs/paper/outline.md §4–5)

Per condition: success rate (N ≥ 5 seeds per task, CIs), turns-to-solve, `run` calls, billed cost,
cache share, shown/raw ratio. Main comparisons: structured(_delta) vs raw; structured vs regex
(same byte budget class); delta vs no-delta; masked variants. Report negative results per task.
