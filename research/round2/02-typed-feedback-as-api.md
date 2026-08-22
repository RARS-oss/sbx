# Round2-02 — Typed/structured tool results & "feedback-as-API" (2026-08-23)

Quality: A=spec/first-party; B=credible preprint; B–=niche single-source; C=product/repo. WebSearch
exhausted; from firecrawl arXiv/dev index + direct fetches (every load-bearing claim fetched).

## (A) Closest prior art, ranked (to "executor emits a typed parsed verdict of a run")
1. **Build/compile MCP servers with typed diagnostics (CLOSEST)** — .NET Binlog MCP (code/file/line/
   task, "exactly what lets an assistant fix without scrolling a raw log", devblogs 2026-06-30, A);
   IronPLC MCP (Diagnostic/SourceSpan, "identical results to CLI" — deterministic, C); Bleep (18
   structured tool calls "without parsing", C); XcodeBuildMCP (structuredContent + versioned schema
   `xcodebuildmcp.output.build-run-result`, schemaVersion:2, C); AL MCP. GAP: each single-tool/
   single-domain; NONE unify compiler+sanitizer/crash+tests; none parse sanitizer frames; schemas
   vendor-local. **sbx's cross-domain unification is unoccupied.**
2. **pytest-receptor / pytest --receptor** (pytest-dev#14710; `--receptor=llm`) — "exit codes tell
   THAT failed not WHAT failed." GAP: output compaction/recipient profile, not typed
   {runner,passed,failed,failures[]} contract.
3. **VeriHarness** (2607.14167) — typed fields {failure location, observed value, admissible
   alternatives}: 14/50→36/50. TWO lessons: (a) MOST gain from "admissible alternatives", location+
   value alone ≈ raw; (b) **prose ≈ keyed JSON — JSON syntax itself did NOT help.** GAP: TextWorld toy.
4. **Schema-First Tool APIs** (2603.13404) — schemas cut interface misuse not semantic; input-side.
5. **Self-Reflective APIs** (2606.05037, B–) — machine-readable recovery `suggestions[]` beat prose
   by +36.7–40.0 pp (Anthropic models). Recovery for API calls, not run verdict.
6. **Structured compiler feedback** — "AI Coding Agents Need Better Compiler Remarks" (2604.13927):
   precise remarks 3.3× success; AMBIGUOUS remarks actively harmful ("semantic-breaking
   hallucinations"); "bottleneck is the interface, not the agent." RLCSF/Lanser-CLI (2510.22907):
   "compilers/type-checkers already compute the missing signal but expose it for human IDEs not
   learning loops" — OUR THESIS in others' words.
7. SARIF-to-LLM (ZeroFalse 2510.02534 "structured contracts"; SecureFixAgent) — static-analysis, not runtime.
8. WILLIAMT (2505.13103) — crash-site template patch, 73.5% at −45.9% tokens. Distills REPAIR not observation.
9. DebugHarness (2604.03610) — LLM queries live runtime; non-deterministic investigation.
10. PGS Property-Generated Solver (2506.18315) — property/minimal signals, not deterministic run verdict.

## (B) Newest 2026 developments
- **MCP standardized the ENVELOPE**: spec 2025-06-18 adds `outputSchema` + `structuredContent`
  (servers MUST conform, clients SHOULD validate). Broad adoption: FastMCP output_schema, smolagents
  structured_output, Vercel AI SDK req. **Agent frameworks now HAVE A SLOT for a typed run verdict.**
- **Programmatic/code-execution tool calling reshapes results**: Anthropic "Code execution with MCP"
  (2025-11-04, results stay in exec env as typed TS, filtered in code, 150k→2k = 98.7%);
  exec-vs-bash-vs-IDE ablation on Claude Code + Codex (2607.10569); HyperTool (2606.13663). The SHAPE
  of a tool result is now a designed variable.
- Token-format research: "Notation Matters" TOON/TRON vs JSON (2605.29676); TSCG (2605.04107).
- **"Observation design" as first-class**: Agent-Computer Observation Interface AOI (2606.29472)
  generalizes SWE-agent's action thesis to observations; TACO-type terminal-observation compression
  (2604.19572); CoACT (2607.02911); SWE-Edit view/edit split (2604.26102); "harness-induced belief
  divergence" (2607.04528).
- **Typed-verdict framing arriving mid-2026**: "Diagnosis Before Recovery" (2608.11772): "compilers/
  tests/traces turn many failures into typed recovery signals" → argues for NARROW per-failure-type
  repair interface.

## (C) Is a typed "run-result" schema a standard? — envelope standardizing, PAYLOAD absent
- MCP defines WHERE a typed result goes, NO domain schema for a program run.
- Sandbox standards standardize lifecycle/transport not verdict: K8s agent-sandbox CRD (isolation);
  Alibaba OpenSandbox ("standardised execution layer" but result = raw stdout/stderr). Standardize the
  BOX not the VERDICT.
- Per-tool schemas exist but local (XcodeBuildMCP, IronPLC). **VERDICT: no cross-tool standard for a
  program-run result. That gap is sbx's opening — a standards land-grab.**

## (D) Frank novelty verdict + five upgrades
**Verdict:** the PRINCIPLE "feedback is a typed interface not a byte stream" is NO LONGER novel in
mid-2026 — converging across preprints (VeriHarness, Compiler Remarks, RLCSF, Schema-First,
Self-Reflective APIs, Diagnosis-Before-Recovery) AND shipping products (build-diagnostics MCPs,
pytest-receptor) AND Anthropic's own framing. Our survey's "NO prior art" is OUT OF DATE at the
principle level — but convergence VALIDATES/de-risks the thesis. **The specific artifact is still
differentiated**: nothing is simultaneously (a) deterministic/no-LLM, (b) executor-side, (c) unifies
compiler + sanitizer/crash (kind/access/frames/first_user_frame/alloc-free) + tests into ONE
machine-readable verdict. Sanitizer crash typing + cross-domain union are the genuinely rare parts.
**Sell "right typed fields + determinism + unification", NOT "it's JSON"** (VeriHarness: JSON=prose wash).

**Five upgrades:**
1. Enrich schema toward **admissible alternatives / fix affordances** (VeriHarness driver; Self-Reflective +37–40pp) — add typed `fix`/`next_admissible_edit` per diagnostic/crash/failure.
2. **Emit as MCP structuredContent behind a published versioned outputSchema** (`sbx.run-result`) → natively queryable in programmatic tool calling (branch on `verdict.crash.first_user_frame` in code).
3. Attach **provenance/evidence + reproducer** to every field (source span, exact command, seed) — auditable/replayable; determinism as moat.
4. **Route recovery by verdict `kind`** — narrow per-kind repair interface (Diagnosis-Before-Recovery 2608.11772).
5. Bundle a **compaction contract + a determinism benchmark** (deterministic-parse vs LLM-distill on cost/reliability; Compiler Remarks shows ambiguous LLM-shaped feedback induces hallucination). Propose the missing "run-result" schema as a standard.
