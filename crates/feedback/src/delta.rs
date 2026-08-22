//! Diagnostic-level deltas between two consecutive Verdicts.
//!
//! Keys are deliberately fuzzy on line numbers: an edit shifts lines, and a
//! diagnostic with the same (file, normalised message) within ±LINE_SLACK lines
//! is the same diagnostic. This is what makes "2 fixed, 1 new, 3 unchanged"
//! meaningful across an agent's edit.

use crate::parse::normalize_msg;
use crate::{Diagnostic, Status, Verdict};
use serde::{Deserialize, Serialize};

const LINE_SLACK: i64 = 3;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CrashMove {
    pub from: String,
    pub to: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct Delta {
    pub status_from: Option<Status>,
    pub status_to: Option<Status>,
    pub fixed: Vec<Diagnostic>,
    pub new: Vec<Diagnostic>,
    pub unchanged: u32,
    pub tests_fixed: Vec<String>,
    pub tests_broken: Vec<String>,
    pub tests_still_failing: u32,
    pub crash_gone: bool,
    pub crash_new: Option<String>,
    pub crash_moved: Option<CrashMove>,
    /// Same crash kind at the same user frame as last run.
    pub crash_same: bool,
}

impl Delta {
    pub fn is_noop(&self) -> bool {
        self.fixed.is_empty()
            && self.new.is_empty()
            && self.tests_fixed.is_empty()
            && self.tests_broken.is_empty()
            && !self.crash_gone
            && self.crash_new.is_none()
            && self.crash_moved.is_none()
    }
}

fn same_diag(a: &Diagnostic, b: &Diagnostic) -> bool {
    if a.tool != b.tool || a.severity != b.severity || a.file != b.file {
        return false;
    }
    let msg_eq = match (&a.code, &b.code) {
        (Some(x), Some(y)) if x == y => normalize_msg(&a.message) == normalize_msg(&b.message),
        (Some(_), Some(_)) => false,
        _ => normalize_msg(&a.message) == normalize_msg(&b.message),
    };
    if !msg_eq {
        return false;
    }
    match (a.line, b.line) {
        (Some(x), Some(y)) => (x as i64 - y as i64).abs() <= LINE_SLACK,
        (None, None) => true,
        _ => false,
    }
}

fn crash_loc(v: &Verdict) -> Option<String> {
    let c = v.crash.as_ref()?;
    let loc = c
        .first_user_frame
        .as_ref()
        .and_then(|f| Some(format!("{}:{}", f.file.clone()?, f.line?)))
        .unwrap_or_else(|| "?".to_string());
    Some(format!("{} @ {}", c.kind, loc))
}

pub fn diff(prev: &Verdict, cur: &Verdict) -> Delta {
    let mut d = Delta {
        status_from: Some(prev.status),
        status_to: Some(cur.status),
        ..Default::default()
    };

    // Diagnostics (errors + warnings).
    let mut matched_cur = vec![false; cur.diagnostics.len()];
    for p in &prev.diagnostics {
        if let Some((i, _)) = cur
            .diagnostics
            .iter()
            .enumerate()
            .find(|(i, c)| !matched_cur[*i] && same_diag(p, c))
        {
            matched_cur[i] = true;
            d.unchanged += 1;
        } else {
            d.fixed.push(p.clone());
        }
    }
    for (i, c) in cur.diagnostics.iter().enumerate() {
        if !matched_cur[i] {
            d.new.push(c.clone());
        }
    }

    // Tests.
    let prev_fail: Vec<String> = prev
        .tests
        .as_ref()
        .map(|t| t.failures.iter().map(|f| f.name.clone()).collect())
        .unwrap_or_default();
    let cur_fail: Vec<String> = cur
        .tests
        .as_ref()
        .map(|t| t.failures.iter().map(|f| f.name.clone()).collect())
        .unwrap_or_default();
    for n in &prev_fail {
        if cur_fail.contains(n) {
            d.tests_still_failing += 1;
        } else if cur.tests.is_some() {
            d.tests_fixed.push(n.clone());
        }
    }
    for n in &cur_fail {
        if !prev_fail.contains(n) {
            d.tests_broken.push(n.clone());
        }
    }

    // Crash.
    match (crash_loc(prev), crash_loc(cur)) {
        (Some(_), None) => d.crash_gone = true,
        (None, Some(c)) => d.crash_new = Some(c),
        (Some(p), Some(c)) => {
            let pk = prev.crash.as_ref().map(|x| x.kind.clone());
            let ck = cur.crash.as_ref().map(|x| x.kind.clone());
            let same_frame = {
                let pf = prev
                    .crash
                    .as_ref()
                    .and_then(|x| x.first_user_frame.as_ref());
                let cf = cur.crash.as_ref().and_then(|x| x.first_user_frame.as_ref());
                match (pf, cf) {
                    (Some(a), Some(b)) => {
                        a.file == b.file
                            && (a.line.unwrap_or(0) as i64 - b.line.unwrap_or(0) as i64).abs()
                                <= LINE_SLACK
                    }
                    (None, None) => true,
                    _ => false,
                }
            };
            if pk == ck && same_frame {
                d.crash_same = true;
            } else {
                d.crash_moved = Some(CrashMove { from: p, to: c });
            }
        }
        (None, None) => {}
    }
    d
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{RunFacts, Severity};

    fn diag(file: &str, line: u32, msg: &str) -> Diagnostic {
        Diagnostic {
            tool: "gcc".into(),
            severity: Severity::Error,
            file: Some(file.into()),
            line: Some(line),
            col: Some(1),
            code: None,
            message: msg.into(),
        }
    }

    #[test]
    fn line_shift_is_unchanged_new_and_fixed_are_detected() {
        let mut a = Verdict::empty();
        a.status = Status::BuildFailed;
        a.diagnostics = vec![
            diag("a.c", 10, "'x' undeclared (first use in this function)"),
            diag("a.c", 20, "expected ';' before '}' token"),
        ];
        let mut b = Verdict::empty();
        b.status = Status::BuildFailed;
        b.diagnostics = vec![
            diag("a.c", 12, "'x' undeclared (first use in this function)"),
            diag("b.c", 3, "incompatible types when returning type 'char *'"),
        ];
        let d = diff(&a, &b);
        assert_eq!(d.unchanged, 1);
        assert_eq!(d.fixed.len(), 1);
        assert_eq!(d.fixed[0].line, Some(20));
        assert_eq!(d.new.len(), 1);
        assert_eq!(d.new[0].file.as_deref(), Some("b.c"));
    }

    #[test]
    fn crash_moving_is_reported() {
        let asan1 = "==1==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000014 at pc 0x0 bp 0x0 sp 0x0\nWRITE of size 4 at 0x602000000014 thread T0\n    #0 0x0 in fill /work/a.c:7:5\n    #1 0x0 in main /work/a.c:20:3\nSUMMARY: AddressSanitizer: heap-buffer-overflow /work/a.c:7:5 in fill\n";
        let asan2 = "==1==ERROR: AddressSanitizer: heap-use-after-free on address 0x602000000014 at pc 0x0 bp 0x0 sp 0x0\nREAD of size 4 at 0x602000000014 thread T0\n    #0 0x0 in sum /work/a.c:31:9\n    #1 0x0 in main /work/a.c:22:3\nSUMMARY: AddressSanitizer: heap-use-after-free /work/a.c:31:9 in sum\n";
        let f = RunFacts {
            exit_code: Some(1),
            ..Default::default()
        };
        let a = crate::distill(b"", asan1.as_bytes(), &f);
        let b = crate::distill(b"", asan2.as_bytes(), &f);
        let d = diff(&a, &b);
        let m = d.crash_moved.expect("moved");
        assert!(m.from.starts_with("heap-buffer-overflow @ /work/a.c:7"));
        assert!(m.to.starts_with("heap-use-after-free @ /work/a.c:31"));
        let same = diff(&b, &b);
        assert!(same.crash_same && same.is_noop());
        let mut ok = Verdict::empty();
        ok.status = Status::Pass;
        ok.exit_code = Some(0);
        assert!(diff(&b, &ok).crash_gone);
    }

    #[test]
    fn test_fix_and_break() {
        let p = crate::distill(
            b"FAILED t.py::a - x\nFAILED t.py::b - y\n=== 2 failed, 1 passed in 0.1s ===\n",
            b"",
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        let c = crate::distill(
            b"FAILED t.py::b - y\nFAILED t.py::c - z\n=== 2 failed, 1 passed in 0.1s ===\n",
            b"",
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        let d = diff(&p, &c);
        assert_eq!(d.tests_fixed, vec!["t.py::a".to_string()]);
        assert_eq!(d.tests_broken, vec!["t.py::c".to_string()]);
        assert_eq!(d.tests_still_failing, 1);
    }
}
