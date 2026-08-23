//! Run-memory: a per-work-dir history of runs, and the anti-loop signals derived
//! from it.
//!
//! Where a [`Delta`](crate::Delta) answers *"what changed since your **last** run"*,
//! this answers *"how has this crash / diagnostic behaved across the **last N** runs"* —
//! turning the executor into a queryable external **memory of execution**. That memory is
//! what a strong model cannot reconstruct from a single stdout: it never sees its own past
//! runs. Two things fall out of it:
//!
//!  * `sbx history` — the timeline + per-item evolution ("appeared at run 2, gone since run 6").
//!  * **anti-loop signals** — "your last 3 runs produced an identical verdict", "this crash has
//!    survived 4 edits" — the red-herring guard that raw output can't give.
//!
//! Persisted as `<work>/.sbx/history.jsonl` (one compact [`RunRecord`] per line, oldest first,
//! capped at [`CAP`]). Identities are line-number-agnostic (scope/function based) so an item is
//! "the same" across the line churn of unrelated edits — the same principle as the delta.
//! Deterministic; no LLM.

use crate::parse::normalize_msg;
use crate::{Crash, Diagnostic, Status, Verdict};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::Path;

/// Keep at most this many runs of history per work dir.
pub const CAP: usize = 200;
pub const HISTORY_FILE: &str = "history.jsonl";

/// Stable identity of a crash across edits: `kind @ file:function` (falls back to `file:Lline`).
pub fn crash_id(c: &Crash) -> String {
    let loc = c
        .first_user_frame
        .as_ref()
        .map(|f| {
            let where_ = f
                .func
                .clone()
                .map(|name| format!("{name}()"))
                .or_else(|| f.line.map(|l| format!("L{l}")))
                .unwrap_or_else(|| "?".into());
            format!("{}:{}", f.file.clone().unwrap_or_default(), where_)
        })
        .unwrap_or_else(|| "?".into());
    format!("{} @ {}", c.kind, loc)
}

/// Stable identity of a diagnostic across edits: tool + scope(or file) + code + normalised message.
pub fn diag_id(d: &Diagnostic) -> String {
    let where_ = d
        .scope
        .clone()
        .map(|s| format!("{s}()"))
        .or_else(|| d.file.clone())
        .unwrap_or_default();
    let code = d.code.clone().unwrap_or_default();
    format!(
        "{} {} {} {}",
        d.tool,
        where_,
        code,
        normalize_msg(&d.message)
    )
    .split_whitespace()
    .collect::<Vec<_>>()
    .join(" ")
}

/// A compact, comparable signature of one run.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RunRecord {
    pub seq: u32,
    pub status: Status,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub crash: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub diags: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tests_failing: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wall_ms: Option<u64>,
}

impl RunRecord {
    pub fn of(v: &Verdict, seq: u32) -> Self {
        RunRecord {
            seq,
            status: v.status,
            crash: v.crash.as_ref().map(crash_id),
            diags: v.diagnostics.iter().map(diag_id).collect(),
            tests_failing: v
                .tests
                .as_ref()
                .map(|t| t.failures.iter().map(|f| f.name.clone()).collect())
                .unwrap_or_default(),
            wall_ms: v.wall_ms,
        }
    }

    /// Whole-run identity — used to detect "nothing changed" streaks.
    pub fn key(&self) -> String {
        let mut diags = self.diags.clone();
        diags.sort();
        let mut tests = self.tests_failing.clone();
        tests.sort();
        format!(
            "{:?}|{}|{}|{}",
            self.status,
            self.crash.clone().unwrap_or_default(),
            diags.join(";"),
            tests.join(";")
        )
    }

    /// Every open-problem identity this run carries (crash + diagnostics + failing tests).
    fn items(&self) -> Vec<String> {
        let mut v = Vec::new();
        if let Some(c) = &self.crash {
            v.push(c.clone());
        }
        v.extend(self.diags.iter().cloned());
        v.extend(self.tests_failing.iter().cloned());
        v
    }
}

pub fn load(state_dir: &Path) -> Vec<RunRecord> {
    match std::fs::read_to_string(state_dir.join(HISTORY_FILE)) {
        Ok(t) => t
            .lines()
            .filter(|l| !l.trim().is_empty())
            .filter_map(|l| serde_json::from_str(l).ok())
            .collect(),
        Err(_) => vec![],
    }
}

/// Append `rec` to the history (oldest first, most-recent last), capped at [`CAP`].
pub fn append(state_dir: &Path, rec: &RunRecord) -> std::io::Result<Vec<RunRecord>> {
    let mut hist = load(state_dir);
    hist.push(rec.clone());
    if hist.len() > CAP {
        hist.drain(0..hist.len() - CAP);
    }
    std::fs::create_dir_all(state_dir)?;
    let body = hist
        .iter()
        .filter_map(|r| serde_json::to_string(r).ok())
        .collect::<Vec<_>>()
        .join("\n");
    std::fs::write(state_dir.join(HISTORY_FILE), body + "\n")?;
    Ok(hist)
}

/// Record the current verdict in the work dir's run-memory and return the anti-loop signals.
/// Assigns the next sequence number automatically.
pub fn record_run(state_dir: &Path, v: &Verdict) -> LoopSignals {
    let existing = load(state_dir);
    let seq = existing.last().map(|r| r.seq + 1).unwrap_or(1);
    let rec = RunRecord::of(v, seq);
    let hist = append(state_dir, &rec).unwrap_or_else(|_| {
        let mut h = existing;
        h.push(rec);
        h
    });
    analyze(&hist)
}

/// One "you may be stuck here" signal: an open problem that has survived several runs unchanged.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stuck {
    pub what: String,
    /// Consecutive most-recent runs (including this one) that still carry this item.
    pub streak: u32,
}

/// Anti-loop signals derived from the run history — the red-herring guard.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct LoopSignals {
    pub runs: u32,
    /// Consecutive most-recent runs with an identical verdict (including this one).
    pub verdict_streak: u32,
    /// Open problems that have survived several runs — likely red herrings you keep circling.
    pub stuck: Vec<Stuck>,
}

impl LoopSignals {
    /// Nothing worth telling the agent (fresh work dir, or steady progress).
    pub fn is_empty(&self) -> bool {
        self.verdict_streak < 2 && self.stuck.is_empty()
    }

    /// The agent-facing `loop:` lines (empty string when [`is_empty`](Self::is_empty)).
    pub fn render(&self) -> String {
        let mut out = String::new();
        if self.verdict_streak >= 2 {
            out.push_str(&format!(
                "loop: {} runs in a row with the SAME verdict — recent edits changed nothing; try a different locus\n",
                self.verdict_streak
            ));
        }
        for s in &self.stuck {
            out.push_str(&format!(
                "loop: {} has survived {} runs unchanged — likely a red herring, not the fix site\n",
                s.what, s.streak
            ));
        }
        out
    }
}

/// Count consecutive most-recent records (ending at the last) that satisfy `pred`.
fn tail_streak(hist: &[RunRecord], pred: impl Fn(&RunRecord) -> bool) -> u32 {
    hist.iter().rev().take_while(|r| pred(r)).count() as u32
}

/// Analyse a history whose LAST element is the current run.
pub fn analyze(hist: &[RunRecord]) -> LoopSignals {
    let mut sig = LoopSignals {
        runs: hist.len() as u32,
        ..Default::default()
    };
    let cur = match hist.last() {
        Some(c) => c.clone(),
        None => return sig,
    };
    let cur_key = cur.key();
    sig.verdict_streak = tail_streak(hist, |r| r.key() == cur_key);
    for item in cur.items() {
        let streak = tail_streak(hist, |r| r.items().contains(&item));
        if streak >= 3 {
            sig.stuck.push(Stuck { what: item, streak });
        }
    }
    sig.stuck
        .sort_by(|a, b| b.streak.cmp(&a.streak).then(a.what.cmp(&b.what)));
    sig
}

/// A human-facing timeline + per-item evolution for `sbx history`.
pub fn summarize(hist: &[RunRecord]) -> String {
    if hist.is_empty() {
        return "no runs recorded in this work dir (.sbx/history.jsonl is empty)\n".into();
    }
    let last_seq = hist.last().map(|r| r.seq).unwrap_or(0);
    let mut out = format!(
        "run-memory: {} runs recorded in .sbx/history.jsonl\n\ntimeline (oldest → newest):\n",
        hist.len()
    );
    for r in hist {
        let mark = if let Some(c) = &r.crash {
            format!("crash {c}")
        } else if !r.tests_failing.is_empty() {
            format!("{} test(s) failing", r.tests_failing.len())
        } else if !r.diags.is_empty() {
            format!("{} diagnostic(s)", r.diags.len())
        } else {
            "clean".to_string()
        };
        out.push_str(&format!(
            "  run {:>3}  {:<13} {mark}\n",
            r.seq,
            format!("{:?}", r.status)
        ));
    }

    // per-item evolution: which runs each open problem appeared in
    let mut seen: BTreeMap<String, Vec<u32>> = BTreeMap::new();
    for r in hist {
        for it in r.items() {
            seen.entry(it).or_default().push(r.seq);
        }
    }
    if !seen.is_empty() {
        out.push_str("\nper-problem evolution:\n");
        for (item, seqs) in &seen {
            let first = seqs[0];
            let lastp = *seqs.last().unwrap();
            let streak = tail_streak(hist, |r| r.items().contains(item));
            let state = if lastp == last_seq {
                if streak >= 3 {
                    format!("STILL OPEN — unchanged {streak} runs ← likely stuck")
                } else {
                    format!("still open (streak {streak})")
                }
            } else {
                format!("fixed — gone since run {} ✓", lastp + 1)
            };
            out.push_str(&format!(
                "  {item}\n      first seen run {first} · {}× total · {state}\n",
                seqs.len()
            ));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{RunFacts, Verdict};

    fn asan(kind: &str, func: &str, line: u32) -> Verdict {
        let raw = format!(
            "==1==ERROR: AddressSanitizer: {kind} on address 0x60200000 at pc 0x0 bp 0x0 sp 0x0\n\
             READ of size 4 at 0x60200000 thread T0\n    #0 0x0 in {func} /work/a.c:{line}:5\n    \
             #1 0x0 in main /work/a.c:40:3\nSUMMARY: AddressSanitizer: {kind} /work/a.c:{line}:5 in {func}\n"
        );
        crate::distill(
            b"",
            raw.as_bytes(),
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        )
    }

    #[test]
    fn same_crash_across_runs_is_flagged_as_a_loop() {
        let v = asan("heap-use-after-free", "sum", 15);
        // three consecutive identical runs
        let hist: Vec<RunRecord> = (1..=3).map(|s| RunRecord::of(&v, s)).collect();
        let sig = analyze(&hist);
        assert_eq!(sig.runs, 3);
        assert_eq!(sig.verdict_streak, 3);
        assert_eq!(sig.stuck.len(), 1, "{:?}", sig.stuck);
        assert_eq!(sig.stuck[0].streak, 3);
        assert!(sig.stuck[0].what.contains("heap-use-after-free"));
        assert!(sig.render().contains("SAME verdict"));
        assert!(sig.render().contains("red herring"));
    }

    #[test]
    fn line_move_of_the_same_bug_is_still_the_same_item() {
        // same kind + function, different line each run — identity is scope-based, so it's one item.
        let hist: Vec<RunRecord> = vec![
            RunRecord::of(&asan("heap-buffer-overflow", "fill", 20), 1),
            RunRecord::of(&asan("heap-buffer-overflow", "fill", 24), 2),
            RunRecord::of(&asan("heap-buffer-overflow", "fill", 26), 3),
        ];
        let sig = analyze(&hist);
        assert_eq!(
            sig.stuck.len(),
            1,
            "line moved but it's the same crash: {:?}",
            sig.stuck
        );
        assert_eq!(sig.stuck[0].streak, 3);
    }

    #[test]
    fn progress_breaks_the_streak_and_is_not_flagged() {
        let mut clean = Verdict::empty();
        clean.status = Status::Pass;
        clean.exit_code = Some(0);
        let hist: Vec<RunRecord> = vec![
            RunRecord::of(&asan("heap-buffer-overflow", "fill", 20), 1),
            RunRecord::of(&asan("heap-buffer-overflow", "fill", 20), 2),
            RunRecord::of(&clean, 3),
        ];
        let sig = analyze(&hist);
        assert_eq!(sig.verdict_streak, 1, "the clean run is unique");
        assert!(
            sig.stuck.is_empty(),
            "no open problem carried into the current run"
        );
        assert!(sig.is_empty());
        // and the history summary calls the overflow "fixed"
        let sum = summarize(&hist);
        assert!(sum.contains("fixed"), "{sum}");
    }
}
