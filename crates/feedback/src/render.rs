//! Compact, stable text rendering of a Verdict (+ optional Delta). This is the
//! default thing an agent sees. Deterministic order, no colours, no timestamps,
//! short lines. Designed so that a diff of two renderings is itself readable.

use crate::{Delta, Diagnostic, Severity, Status, Verdict};

#[derive(Debug, Clone)]
pub struct RenderOpts {
    /// Max diagnostics listed (rest summarised as "+N more").
    pub max_diagnostics: usize,
    /// Max stack frames listed per crash (user frames first).
    pub max_frames: usize,
    /// Max test failures listed.
    pub max_test_failures: usize,
    /// Include the unclaimed tail lines.
    pub include_tail: bool,
    pub max_tail: usize,
    /// Fixed last line, e.g. where the full log lives. Empty = no footer.
    pub footer: String,
}

impl Default for RenderOpts {
    fn default() -> Self {
        Self {
            max_diagnostics: 12,
            max_frames: 6,
            max_test_failures: 10,
            include_tail: true,
            max_tail: 6,
            footer: "(full log available on request)".to_string(),
        }
    }
}

/// Deterministic one-line glossary for common crash kinds. Sanitizer vocabulary is opaque to
/// smaller models ("load of address … with insufficient space for an object of type 'int'"
/// was read as an input-parsing problem in our pilots); the hint says what the kind *means*
/// and where to look. Keyed on (tool, kind prefix); kept in parity with the Python renderer.
pub fn hint_for(tool: &str, kind: &str) -> Option<&'static str> {
    let k = kind.to_ascii_lowercase();
    let t = tool.to_ascii_lowercase();
    if t.contains("addresssanitizer") {
        if k.contains("heap-buffer-overflow") {
            return Some("read/write past the end (or before the start) of a heap allocation — check the index or length used at the frame below against the allocation size");
        }
        if k.contains("stack-buffer-overflow") {
            return Some("read/write past the end of a local (stack) array — a fixed-size buffer is too small for the data copied into it; bound the copy");
        }
        if k.contains("heap-use-after-free") {
            return Some("memory used after it was freed — the free site is listed below; the pointer must not be dereferenced after free (or the free must happen later)");
        }
        if k.contains("double-free") {
            return Some("the same allocation freed twice — the second free is at the frame below; free once (null the pointer after freeing, or remove one free)");
        }
        if k.contains("stack-use-after-return") || k.contains("stack-use-after-scope") {
            return Some(
                "a pointer to a local variable is used after that variable's lifetime ended",
            );
        }
        if k.contains("segv") || k.contains("unknown address") {
            return Some(
                "invalid memory access (often a NULL or uninitialised pointer) at the frame below",
            );
        }
        if k.contains("global-buffer-overflow") {
            return Some("read/write past the end of a global array — check the index against the array size");
        }
        if k.contains("memory leak") {
            return Some("allocations never freed — see the allocation sites");
        }
    }
    if t.contains("undefinedbehaviorsanitizer") {
        if k.contains("insufficient space") || k.contains("misaligned") {
            return Some("out-of-bounds access: the address points past the end of the object (not an input-parsing problem) — check the index/bound at the frame below");
        }
        if k.contains("signed integer overflow") {
            return Some("signed arithmetic overflowed (undefined in C/C++) — use unsigned or wider types where wrap-around is intended");
        }
        if k.contains("null pointer") {
            return Some("a NULL pointer was dereferenced at the frame below — handle the empty/NULL case before using it");
        }
        if k.contains("index") && k.contains("out of bounds") {
            return Some("array index out of bounds at the frame below — check the loop bound");
        }
        if k.contains("division by zero") {
            return Some("integer division by zero at the frame below");
        }
        if k.contains("shift") {
            return Some("invalid shift amount/operand (undefined behaviour) at the frame below");
        }
    }
    if t == "rust-panic" {
        if k.contains("index out of bounds") {
            return Some("slice/array index beyond its length at the panic site — check the loop range or index arithmetic");
        }
        if k.contains("unwrap") || k.contains("none") {
            return Some(
                "unwrap()/expect() on None or Err at the panic site — handle the failing case",
            );
        }
        if k.contains("overflow") {
            return Some(
                "arithmetic overflow in debug mode — use checked/wrapping ops or wider types",
            );
        }
    }
    if t == "signal" {
        if k.contains("SEGV") || k.contains("SIGSEGV") {
            return Some("segmentation fault: invalid memory access (no sanitizer report available — build with -fsanitize=address for the exact site)");
        }
        if k.contains("ABRT") {
            return Some("process aborted (assertion failure or allocator check)");
        }
    }
    None
}

fn status_word(s: Status) -> &'static str {
    match s {
        Status::Pass => "PASS",
        Status::TestsFailed => "TESTS FAILED",
        Status::Crash => "CRASH",
        Status::RuntimeError => "RUNTIME ERROR",
        Status::BuildFailed => "BUILD FAILED",
        Status::Timeout => "TIMEOUT",
        Status::SetupFailed => "SANDBOX SETUP FAILED",
        Status::Unknown => "UNKNOWN",
    }
}

fn loc(file: &Option<String>, line: Option<u32>, col: Option<u32>) -> String {
    match (file, line, col) {
        (Some(f), Some(l), Some(c)) => format!("{f}:{l}:{c}"),
        (Some(f), Some(l), None) => format!("{f}:{l}"),
        (Some(f), None, _) => f.clone(),
        _ => "?".to_string(),
    }
}

fn fmt_diag(d: &Diagnostic) -> String {
    let sev = match d.severity {
        Severity::Error => "error",
        Severity::Warning => "warning",
        Severity::Note => "note",
    };
    let code = d
        .code
        .as_ref()
        .map(|c| format!(" [{c}]"))
        .unwrap_or_default();
    format!(
        "  {}: {}{}: {}",
        loc(&d.file, d.line, d.col),
        sev,
        code,
        d.message
    )
}

pub fn render(v: &Verdict, delta: Option<&Delta>, o: &RenderOpts) -> String {
    let mut s = String::new();
    // Header line.
    let mut head = format!("[sbx] {}", status_word(v.status));
    if let Some(c) = v.exit_code {
        head.push_str(&format!(" exit={c}"));
    }
    if let Some(sig) = &v.signal {
        head.push_str(&format!(" signal={sig}"));
    }
    if let Some(ms) = v.wall_ms {
        head.push_str(&format!(" wall={ms}ms"));
    }
    let nerr = v.errors().count();
    let nwarn = v
        .diagnostics
        .iter()
        .filter(|d| d.severity == Severity::Warning)
        .count();
    if nerr + nwarn > 0 {
        head.push_str(&format!(
            " diagnostics={nerr}E/{nwarn}W in {} group(s)",
            v.error_groups
        ));
    }
    if let Some(t) = &v.tests {
        head.push_str(&format!(
            " tests={}/{} passed",
            t.passed,
            t.passed + t.failed + t.errors
        ));
        if t.errors > 0 {
            head.push_str(&format!(" ({} errors)", t.errors));
        }
    }
    head.push_str(&format!(" raw={}B", v.raw_bytes));
    s.push_str(&head);
    s.push('\n');

    // Delta first: it is the most actionable line after a re-run.
    if let Some(d) = delta {
        let mut parts: Vec<String> = vec![];
        if let (Some(a), Some(b)) = (d.status_from, d.status_to) {
            if a != b {
                parts.push(format!("status {} -> {}", status_word(a), status_word(b)));
            }
        }
        if !d.fixed.is_empty() || !d.new.is_empty() || d.unchanged > 0 {
            parts.push(format!(
                "diagnostics: {} fixed, {} new, {} unchanged",
                d.fixed.len(),
                d.new.len(),
                d.unchanged
            ));
        }
        if !d.tests_fixed.is_empty() || !d.tests_broken.is_empty() || d.tests_still_failing > 0 {
            parts.push(format!(
                "tests: {} fixed, {} newly failing, {} still failing",
                d.tests_fixed.len(),
                d.tests_broken.len(),
                d.tests_still_failing
            ));
        }
        if d.crash_gone {
            parts.push("crash: gone".into());
        }
        if let Some(c) = &d.crash_new {
            parts.push(format!("crash: NEW {c}"));
        }
        if let Some(m) = &d.crash_moved {
            parts.push(format!("crash: moved {} -> {}", m.from, m.to));
        }
        if d.crash_same {
            parts.push("crash: SAME as last run (your change did not affect it)".into());
        }
        if parts.is_empty() {
            parts.push("no change vs last run".into());
        }
        s.push_str(&format!("delta: {}\n", parts.join("; ")));
        if !d.new.is_empty() {
            s.push_str("new since last run:\n");
            for x in d.new.iter().take(o.max_diagnostics) {
                s.push_str(&fmt_diag(x));
                s.push('\n');
            }
        }
        if !d.tests_broken.is_empty() {
            s.push_str(&format!(
                "newly failing tests: {}\n",
                d.tests_broken.join(", ")
            ));
        }
    }

    // Crash block.
    if let Some(c) = &v.crash {
        let mut line = format!("crash: {} {}", c.tool, c.kind);
        if let Some(a) = &c.access {
            line.push_str(&format!(" ({a})"));
        }
        if let Some(m) = &c.message {
            if c.tool == "python" {
                line.push_str(&format!(": {m}"));
            } else if c.tool == "UndefinedBehaviorSanitizer" {
                // message usually starts with the kind ("signed integer overflow: 2147483647 + 1 ...")
                let rest = m.strip_prefix(c.kind.as_str()).unwrap_or(m);
                let rest = rest.trim_start_matches(':').trim();
                if !rest.is_empty() {
                    line.push_str(&format!(": {rest}"));
                }
            }
        }
        s.push_str(&line);
        s.push('\n');
        if let Some(h) = hint_for(&c.tool, &c.kind) {
            s.push_str(&format!("  hint: {h}\n"));
        }
        if let Some(f) = &c.first_user_frame {
            s.push_str(&format!(
                "  at {} in {}\n",
                loc(&f.file, f.line, f.col),
                f.func.clone().unwrap_or_else(|| "?".into())
            ));
        }
        if !c.frames.is_empty() {
            // user frames first, then the rest, capped
            let mut shown = 0;
            for f in c
                .frames
                .iter()
                .filter(|f| f.user)
                .chain(c.frames.iter().filter(|f| !f.user))
            {
                if shown >= o.max_frames {
                    s.push_str(&format!("  ... {} more frames\n", c.frames.len() - shown));
                    break;
                }
                if Some(f) == c.first_user_frame.as_ref() && shown > 0 {
                    continue;
                }
                s.push_str(&format!(
                    "  #{} {} {}\n",
                    f.idx,
                    f.func.clone().unwrap_or_else(|| "?".into()),
                    loc(&f.file, f.line, f.col)
                ));
                shown += 1;
            }
        }
        if let Some(f) = c.alloc_frames.iter().find(|f| f.user) {
            s.push_str(&format!(
                "  allocated at {} in {}\n",
                loc(&f.file, f.line, f.col),
                f.func.clone().unwrap_or_default()
            ));
        }
        if let Some(f) = c.free_frames.iter().find(|f| f.user) {
            s.push_str(&format!(
                "  freed at {} in {}\n",
                loc(&f.file, f.line, f.col),
                f.func.clone().unwrap_or_default()
            ));
        }
        if let Some(m) = &c.message {
            if c.tool == "AddressSanitizer" {
                s.push_str(&format!("  {}\n", m));
            }
        }
    }

    // Diagnostics block (errors first, then warnings), grouped by file.
    if !v.diagnostics.is_empty() {
        let mut list: Vec<&Diagnostic> = v.diagnostics.iter().collect();
        list.sort_by(|a, b| {
            b.severity
                .cmp(&a.severity)
                .then(a.file.cmp(&b.file))
                .then(a.line.cmp(&b.line))
        });
        s.push_str("diagnostics:\n");
        for d in list.iter().take(o.max_diagnostics) {
            s.push_str(&fmt_diag(d));
            s.push('\n');
        }
        if list.len() > o.max_diagnostics {
            s.push_str(&format!("  ... +{} more\n", list.len() - o.max_diagnostics));
        }
    }

    // Tests block.
    if let Some(t) = &v.tests {
        if !t.failures.is_empty() {
            s.push_str(&format!("failing tests ({}):\n", t.runner));
            for f in t.failures.iter().take(o.max_test_failures) {
                let mut line = format!("  {}", f.name);
                if f.file.is_some() {
                    line.push_str(&format!(" @ {}", loc(&f.file, f.line, None)));
                }
                if let Some(m) = &f.message {
                    line.push_str(&format!(" — {}", m));
                }
                s.push_str(&line);
                s.push('\n');
            }
            if t.failures.len() > o.max_test_failures {
                s.push_str(&format!(
                    "  ... +{} more\n",
                    t.failures.len() - o.max_test_failures
                ));
            }
        }
    }

    if o.include_tail && !v.tail.is_empty() && v.status != Status::Pass {
        s.push_str("output tail:\n");
        for l in v
            .tail
            .iter()
            .rev()
            .take(o.max_tail)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
        {
            s.push_str(&format!("  | {l}\n"));
        }
    }
    if !o.footer.is_empty() {
        s.push_str(&o.footer);
        s.push('\n');
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::RunFacts;

    #[test]
    fn render_is_compact_and_deterministic() {
        let asan = include_str!("../tests/fixtures/asan_heap_overflow.txt");
        let v = crate::distill(
            b"",
            asan.as_bytes(),
            &RunFacts {
                exit_code: Some(1),
                wall_ms: Some(12),
                ..Default::default()
            },
        );
        let a = render(&v, None, &RenderOpts::default());
        let b = render(&v, None, &RenderOpts::default());
        assert_eq!(a, b);
        assert!(a.starts_with("[sbx] CRASH exit=1"));
        assert!(a.contains("heap-buffer-overflow (WRITE of size 4)"));
        assert!(a.contains("at /work/overflow.c:7:"));
        // several times smaller than the raw report (shadow bytes, legend, runtime frames dropped)
        assert!(
            a.len() * 3 < asan.len(),
            "rendered {} vs raw {}:\n{}",
            a.len(),
            asan.len(),
            a
        );
    }
}
