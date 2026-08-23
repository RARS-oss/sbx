# Running sbx on SWE-bench / ARVO-style instances

`swe_run.py` runs the sbx agent loop on **multi-file repository repair** instances and records
pass/fail, turns, tokens and cache-aware cost per feedback condition — the measurement the report
(§6.7) argues is the decisive one. Single-file toy tasks are fixed straight from source, so feedback
form doesn't move a frontier model there; the token- and turn-reductions concentrate on **multi-file
repos where the model must explore (`list_files`, `read_file`) and iterate** — which is exactly this.

## Instance format (a SWE-bench-compatible subset)

```json
{
  "instance_id": "...",
  "repo_dir": "path/to/a/prepared/working/tree",
  "problem_statement": "what to fix",
  "test_cmd": "python3 -m pytest -q path/to/failing_tests.py",
  "protected": ["path/to/failing_tests.py"],
  "timeout": 300
}
```

`repo_dir` is a **prepared** tree (checked out, deps installed). `test_cmd` is the oracle. A synthetic
instance (`instances/mini-stats.json`, a 3-file Python package with a cross-file bug) ships so the
runner works out of the box.

## Run

```bash
python bench/swe/swe_run.py --instances bench/swe/instances/mini-stats.json \
  --model claude-cli:claude-sonnet-4-6 --conditions raw,structured_delta --max-turns 20
```

`--model`: `mock` | `ollama:<m>` | `openai:<m>` | `claude-cli:<m>` | an Anthropic model (needs a key).
The per-condition summary reports pass-rate, mean turns, and the shown-vs-raw character ratio.

## Pointing at real SWE-bench

Each SWE-bench instance is `{repo, base_commit, problem_statement, test_patch, FAIL_TO_PASS, ...}`.
Prepare it once, then describe it as an instance JSON:

```bash
git clone https://github.com/<repo> <dir>
git -C <dir> checkout <base_commit>
git -C <dir> apply <test_patch>        # adds the failing tests
pip install -e <dir>                    # or the instance's documented setup
```
```json
{ "instance_id": "<id>", "repo_dir": "<dir>", "problem_statement": "<problem_statement>",
  "test_cmd": "python -m pytest -q <FAIL_TO_PASS paths>", "protected": ["<test files>"] }
```

The gold patch is the oracle; sbx runs the FAIL_TO_PASS tests and the verdict/delta come for free.
(SWE-bench's official harness uses per-instance Docker images; here the repo just needs to be a
prepared tree that `test_cmd` runs against inside sbx.)

## Pointing at ARVO (memory-safety N-days)

`repo_dir` = the vulnerable checkout; `test_cmd` = build with the sanitizer and run the PoC. The oracle
is "the sanitizer no longer fires" — sbx parses the ASan/UBSan report into the crash verdict, and the
delta says `crash gone / SAME / moved`. This is the regime where a *correct*, deterministic verdict is
most valuable (report §6.7).

## Notes

- Tools: `list_files` / `read_file` / `write_file` / `run` / `done`; `run` executes `test_cmd` inside sbx.
- `sbx run --overlay <repo>` mounts a huge repo without copying it, but only helps a **fully-sandboxed**
  runtime; this harness reads/edits host-side, so it uses a copied work tree (see the top-level README
  roadmap for the overlay-native agent path).
