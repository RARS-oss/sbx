//! feedback — turn raw execution output into a typed **Verdict**, diff two
//! Verdicts into a **Delta**, and render both as a compact, stable text block
//! meant to be the *only* thing a coding agent sees by default.
//!
//! Principle: the executor already knows the exit status, the signal, the
//! sanitizer report and the test runner's summary. Instead of handing the
//! model 30 000 characters of interleaved bytes, we hand it the facts, grouped
//! and deduplicated, plus "what changed since your last run".
//!
//! Parsers are deterministic (no LLM), format-spec driven, and unit-tested on
//! real fixtures. Anything the parsers do not understand is kept as a short
//! "tail" so the agent can still ask for the full log.

pub mod delta;
pub mod parse;
pub mod render;
pub mod scope;

use serde::{Deserialize, Serialize};

pub use delta::{diff, Delta};
pub use render::{render, RenderOpts};
pub use scope::enrich_scopes;

/// Top-level status, in increasing order of "the program ran further".
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Pass,
    TestsFailed,
    Crash,
    RuntimeError,
    BuildFailed,
    Timeout,
    SetupFailed,
    Unknown,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    Note,
    Warning,
    Error,
}

/// One compiler/linter diagnostic.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Diagnostic {
    /// "gcc" | "clang" | "rustc" | "ubsan" | "python" | ...
    pub tool: String,
    pub severity: Severity,
    pub file: Option<String>,
    pub line: Option<u32>,
    pub col: Option<u32>,
    /// e.g. "E0308", "-Wunused-variable", "-fpermissive"
    pub code: Option<String>,
    pub message: String,
    /// Enclosing function/scope (AST-derived, best-effort) — lets the delta match a diagnostic
    /// across a refactor even when its line number moves. Populated by [`enrich_scopes`]; `None`
    /// until then (and `#[serde(default)]` so a verdict written before this field still loads).
    #[serde(default)]
    pub scope: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Frame {
    pub idx: u32,
    pub func: Option<String>,
    pub file: Option<String>,
    pub line: Option<u32>,
    pub col: Option<u32>,
    /// Frame points into user code (not libc / sanitizer runtime / interpreter internals).
    pub user: bool,
}

/// A crash: sanitizer report, or a bare fatal signal.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Crash {
    /// "AddressSanitizer" | "UndefinedBehaviorSanitizer" | "signal" | "python" | "rust-panic"
    pub tool: String,
    /// "heap-buffer-overflow", "SEGV", "stack-use-after-return", "SIGSEGV", "ZeroDivisionError"...
    pub kind: String,
    /// "READ of size 4" etc.
    pub access: Option<String>,
    pub address: Option<String>,
    pub message: Option<String>,
    pub frames: Vec<Frame>,
    pub alloc_frames: Vec<Frame>,
    pub free_frames: Vec<Frame>,
    /// First frame that points into user code — the single most useful line.
    pub first_user_frame: Option<Frame>,
    /// SUMMARY line if the sanitizer produced one.
    pub summary: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TestFailure {
    pub name: String,
    pub file: Option<String>,
    pub line: Option<u32>,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct Tests {
    /// "pytest" | "cargo-test" | "ctest" | "gtest" | "go-test" | "generic"
    pub runner: String,
    pub passed: u32,
    pub failed: u32,
    pub errors: u32,
    pub skipped: u32,
    pub failures: Vec<TestFailure>,
}

/// The typed result of one run. Serialisable; stable field names (this is the
/// contract agents and harness adapters depend on).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Verdict {
    pub status: Status,
    pub exit_code: Option<i32>,
    pub signal: Option<String>,
    pub timed_out: bool,
    pub wall_ms: Option<u64>,
    pub diagnostics: Vec<Diagnostic>,
    pub crash: Option<Crash>,
    pub tests: Option<Tests>,
    /// Last few non-empty lines of combined output that no parser claimed (kept short).
    pub tail: Vec<String>,
    /// Size of the raw output the verdict was distilled from.
    pub raw_bytes: usize,
    /// Distinct (tool, code/message) error groups — what the agent must fix.
    pub error_groups: u32,
}

impl Verdict {
    pub fn empty() -> Self {
        Self {
            status: Status::Unknown,
            exit_code: None,
            signal: None,
            timed_out: false,
            wall_ms: None,
            diagnostics: vec![],
            crash: None,
            tests: None,
            tail: vec![],
            raw_bytes: 0,
            error_groups: 0,
        }
    }

    pub fn errors(&self) -> impl Iterator<Item = &Diagnostic> {
        self.diagnostics
            .iter()
            .filter(|d| d.severity == Severity::Error)
    }

    /// Rough token estimate (chars/4) of a rendered verdict vs. raw bytes — for telemetry only.
    pub fn est_tokens(&self, opts: &RenderOpts) -> (usize, usize) {
        let rendered = render(self, None, opts);
        (rendered.len() / 4, self.raw_bytes / 4)
    }
}

/// Inputs the executor knows without parsing anything.
#[derive(Debug, Clone, Default)]
pub struct RunFacts {
    pub exit_code: Option<i32>,
    /// e.g. "SIGSEGV"
    pub signal: Option<String>,
    pub timed_out: bool,
    pub setup_failed: Option<String>,
    pub wall_ms: Option<u64>,
}

/// Build a Verdict from raw stdout/stderr plus run facts.
pub fn distill(stdout: &[u8], stderr: &[u8], facts: &RunFacts) -> Verdict {
    parse::distill(stdout, stderr, facts)
}
