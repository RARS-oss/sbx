//! Deterministic parsers. Each parser claims the lines it understands; the
//! remainder feeds the "tail". Order matters: sanitizers first (they are the
//! most specific), then compiler diagnostics, then test runners.

use crate::{Crash, Diagnostic, Frame, RunFacts, Severity, Status, TestFailure, Tests, Verdict};
use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::BTreeSet;

static RE_ASAN_HEAD: Lazy<Regex> = Lazy::new(|| {
    // ==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000014 at pc ...
    // ==12345==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc ...)
    // ==12345==ERROR: LeakSanitizer: detected memory leaks
    // ==12345==ERROR: MemorySanitizer: use-of-uninitialized-value
    // ==12345==ERROR: ThreadSanitizer: data race ...
    // Group 2 = everything after the tool name; kind/address are split out by `split_kind`.
    Regex::new(r"^==\d+==\s*ERROR: (AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer|UndefinedBehaviorSanitizer): (.+)$").unwrap()
});

/// "heap-buffer-overflow on address 0x6020… at pc …" -> ("heap-buffer-overflow", Some("0x6020…"))
/// "attempting double-free on 0x6020… in thread T0:"  -> ("attempting double-free", Some(..))
/// "SEGV on unknown address 0x000… (pc …)"             -> ("SEGV", Some("0x000…"))
/// "detected memory leaks"                              -> ("detected memory leaks", None)
fn split_kind(rest: &str) -> (String, Option<String>) {
    let rest = rest.trim();
    let mut cut = rest.len();
    for sep in [
        " on address ",
        " on unknown address ",
        " on 0x",
        " at pc ",
        " (pc ",
        " in thread ",
        ":",
    ] {
        if let Some(i) = rest.find(sep) {
            cut = cut.min(i);
        }
    }
    let kind = rest[..cut].trim().trim_end_matches(':').to_string();
    let address = RE_HEX_ADDR
        .find(&rest[cut..])
        .map(|m| m.as_str().to_string());
    (kind, address)
}
static RE_ASAN_ACCESS: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^(READ|WRITE) of size (\d+) at (0x[0-9a-fA-F]+)").unwrap());
static RE_FRAME: Lazy<Regex> = Lazy::new(|| {
    //     #0 0x55d0c2a3b2f4 in main /work/a.c:12:5
    //     #1 0x7f3b1c829d8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58:16
    //     #2 0x... in func (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f) (BuildId: ...)
    //     #2 0x7c3ff8a2a1c9  (/usr/lib/x86_64-linux-gnu/libc.so.6+0x2a1c9) (BuildId: ...)   <- no symbol
    //     #0 0x... in main (/work/a.out+0x1234)
    Regex::new(r"^\s*#(\d+)\s+0x[0-9a-fA-F]+(?:\s+in\s+(.+?))?\s+(?:\(?([^\s()]+?)(?::(\d+))?(?::(\d+))?\)?)?\s*(?:\(BuildId: [0-9a-fA-F]+\))?$").unwrap()
});

/// Lines of the AddressSanitizer shadow-byte legend (never useful to an agent).
const LEGEND_PREFIXES: &[&str] = &[
    "Addressable:",
    "Partially addressable",
    "Heap left redzone",
    "Freed heap region",
    "Stack left redzone",
    "Stack mid redzone",
    "Stack right redzone",
    "Stack after return",
    "Stack use after scope",
    "Global redzone",
    "Global init order",
    "Poisoned by user",
    "Container overflow",
    "Array cookie",
    "Intra object redzone",
    "ASan internal",
    "Left alloca redzone",
    "Right alloca redzone",
    "Shadow gap",
];
static RE_ASAN_SECTION: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^(?:0x[0-9a-fA-F]+ is located .*|(?:previously )?(?:allocated|freed) by thread T\d+ here:|Address 0x[0-9a-fA-F]+ is .*)$").unwrap()
});
static RE_SUMMARY: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^SUMMARY: (AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer|UndefinedBehaviorSanitizer): (.+)$").unwrap()
});
static RE_HEX_ADDR: Lazy<Regex> = Lazy::new(|| Regex::new(r"0x[0-9a-fA-F]+").unwrap());
static RE_UBSAN: Lazy<Regex> = Lazy::new(|| {
    // /work/a.c:7:11: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
    Regex::new(r"^(\S+?):(\d+):(\d+): runtime error: (.+)$").unwrap()
});
static RE_DIAG: Lazy<Regex> = Lazy::new(|| {
    // gcc/clang: file:line:col: error|warning|note|fatal error: message [-Wflag]
    Regex::new(r"^(\S+?):(\d+)(?::(\d+))?:\s*(fatal error|error|warning|note):\s*(.+?)(?:\s*\[(-W[^\]]+|-f[^\]]+)\])?$").unwrap()
});
static RE_RUSTC: Lazy<Regex> = Lazy::new(|| {
    // error[E0308]: mismatched types   /   warning: unused variable: `x`   /   error: aborting due to 2 previous errors
    Regex::new(r"^(error|warning)(?:\[([A-Z]\d{4})\])?: (.+)$").unwrap()
});
static RE_RUSTC_LOC: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^\s*-->\s+(\S+?):(\d+):(\d+)\s*$").unwrap());
static RE_PYTEST_FAILED: Lazy<Regex> = Lazy::new(|| {
    // FAILED tests/test_x.py::test_add - AssertionError: assert 3 == 4
    // ERROR tests/test_y.py::test_z - ImportError: ...
    Regex::new(r"^(FAILED|ERROR) (\S+?)(?:::(\S+))?(?: - (.+))?$").unwrap()
});
static RE_PYTEST_SUMMARY: Lazy<Regex> = Lazy::new(|| {
    // ======= 2 failed, 5 passed, 1 skipped, 1 error in 0.12s =======
    Regex::new(r"^=+ (.+?) in [0-9.]+s(?: \([^)]*\))? =+$").unwrap()
});
static RE_CARGO_TEST_RESULT: Lazy<Regex> = Lazy::new(|| {
    // test result: FAILED. 3 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
    Regex::new(r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored").unwrap()
});
static RE_CARGO_TEST_FAIL: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^test (\S+) \.\.\. FAILED$").unwrap());
static RE_CARGO_PANIC: Lazy<Regex> = Lazy::new(|| {
    // thread 'tests::it_adds' panicked at src/lib.rs:10:9:
    // thread 'main' (36) panicked at main.rs:10:21:        <- Rust ≥ 1.9x prints the thread id
    Regex::new(r"^thread '([^']+)'(?: \(\d+\))? panicked at (\S+?):(\d+):(\d+):?$").unwrap()
});
static RE_PY_TRACE_LOC: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"^\s*File "([^"]+)", line (\d+), in (.+)$"#).unwrap());
static RE_PY_EXC: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^([A-Z][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning)): (.*)$").unwrap()
});
static RE_GTEST_FAIL: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[\s+FAILED\s+\] (\S+)").unwrap());
static RE_CTEST_FAIL: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\s*\d+ - (\S+) \((Failed|Timeout|SEGFAULT|Subprocess aborted|.*)\)$").unwrap()
});
static RE_CTEST_SUMMARY: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^(\d+)% tests passed, (\d+) tests failed out of (\d+)$").unwrap());

fn is_user_path(p: &str) -> bool {
    !(p.starts_with("../sysdeps")
        || p.contains("/libc")
        || p.contains("libc_start")
        || p.contains("compiler-rt")
        || p.contains("/sanitizer_common/")
        || p.contains("asan_")
        || p.contains("/lib/x86_64-linux-gnu/")
        || p.contains("/usr/lib/")
        || p.contains("/usr/include/")
        || p.contains("/rustc/")
        || p.contains("/.cargo/registry/")
        || p.contains("/.rustup/")
        || p.contains("/site-packages/")
        || p.starts_with("<"))
}

fn is_user_func(f: &str) -> bool {
    !(f.starts_with("__")
        || f.starts_with("_start")
        || f.contains("__interceptor_")
        || f.contains("__asan")
        || f.contains("__ubsan")
        || f.contains("__sanitizer")
        || f.starts_with("std::")
        || f.starts_with("core::")
        || f.starts_with("alloc::")
        || f == "main_thread")
}

fn parse_frame(line: &str) -> Option<Frame> {
    let c = RE_FRAME.captures(line)?;
    let idx: u32 = c.get(1)?.as_str().parse().ok()?;
    let func = c.get(2).map(|m| m.as_str().trim().to_string());
    let file = c.get(3).map(|m| m.as_str().to_string());
    let line_no = c.get(4).and_then(|m| m.as_str().parse().ok());
    let col = c.get(5).and_then(|m| m.as_str().parse().ok());
    // "(/work/a.out+0x1234)" style: module+offset, no source location.
    let (file, line_no, col) = match &file {
        Some(f) if f.contains('+') && line_no.is_none() => (Some(f.clone()), None, None),
        _ => (file, line_no, col),
    };
    let user = match (&file, &func) {
        (Some(f), Some(fun)) => is_user_path(f) && is_user_func(fun) && line_no.is_some(),
        (Some(f), None) => is_user_path(f) && line_no.is_some(),
        (None, Some(fun)) => is_user_func(fun) && false,
        _ => false,
    };
    Some(Frame {
        idx,
        func,
        file,
        line: line_no,
        col,
        user,
    })
}

/// Parse a sanitizer report out of the lines. Returns the crash and the set of
/// line indices it consumed.
fn parse_sanitizer(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Crash> {
    let start = lines
        .iter()
        .position(|l| RE_ASAN_HEAD.is_match(l.trim_end()))?;
    let head = RE_ASAN_HEAD.captures(lines[start].trim_end())?;
    let tool = head
        .get(1)
        .map(|m| m.as_str())
        .unwrap_or("Sanitizer")
        .to_string();
    let (kind, address) = split_kind(head.get(2).map(|m| m.as_str()).unwrap_or("error"));
    claimed.insert(start);
    // The "=====" separator printed just before the header.
    if start > 0 {
        let prev = lines[start - 1].trim();
        if !prev.is_empty() && prev.chars().all(|c| c == '=') {
            claimed.insert(start - 1);
        }
    }

    let mut crash = Crash {
        tool,
        kind,
        access: None,
        address,
        message: None,
        frames: vec![],
        alloc_frames: vec![],
        free_frames: vec![],
        first_user_frame: None,
        summary: None,
    };
    #[derive(PartialEq)]
    enum Sec {
        Main,
        Alloc,
        Free,
        Other,
    }
    let mut sec = Sec::Main;
    let mut after_summary = false;
    for (i, raw) in lines.iter().enumerate().skip(start + 1) {
        let l = raw.trim_end();
        if let Some(c) = RE_SUMMARY.captures(l) {
            crash.summary = Some(c.get(2).unwrap().as_str().to_string());
            claimed.insert(i);
            after_summary = true;
            continue;
        }
        if after_summary {
            // Shadow-byte dump, legend and the ABORTING line follow the SUMMARY; a second
            // sanitizer report (rare) starts with a fresh "==PID==ERROR" header which we leave alone.
            if RE_ASAN_HEAD.is_match(l) {
                break;
            }
            let ls = l.trim_start();
            if l.is_empty()
                || l.starts_with("==")
                || l.starts_with("Shadow")
                || l.starts_with("=>")
                || ls.starts_with("0x")
                || ls.ends_with(": 00") // defensive
                || LEGEND_PREFIXES.iter().any(|p| ls.starts_with(p))
            {
                claimed.insert(i);
                continue;
            }
            continue;
        }
        if let Some(c) = RE_ASAN_ACCESS.captures(l) {
            crash.access = Some(format!(
                "{} of size {}",
                c.get(1).unwrap().as_str(),
                c.get(2).unwrap().as_str()
            ));
            claimed.insert(i);
            continue;
        }
        if RE_ASAN_SECTION.is_match(l) {
            sec = if l.contains("freed by") {
                Sec::Free
            } else if l.contains("allocated by") {
                Sec::Alloc
            } else {
                Sec::Other
            };
            if crash.message.is_none() && l.contains("is located") {
                crash.message = Some(l.to_string());
            }
            claimed.insert(i);
            continue;
        }
        if let Some(f) = parse_frame(l) {
            claimed.insert(i);
            match sec {
                Sec::Main => crash.frames.push(f),
                Sec::Alloc => crash.alloc_frames.push(f),
                Sec::Free => crash.free_frames.push(f),
                Sec::Other => {}
            }
            continue;
        }
        // Shadow-byte legend, blank lines, "Hint:" lines etc.
        if l.starts_with("Shadow bytes around")
            || l.starts_with("Shadow byte legend")
            || l.starts_with("=>")
            || l.starts_with("  0x")
            || l.starts_with("Hint:")
            || l.starts_with("==")
            || l.starts_with("    ") && l.contains(':') && l.len() < 40
            || l.is_empty()
        {
            claimed.insert(i);
            continue;
        }
        let ls = l.trim_start();
        if LEGEND_PREFIXES.iter().any(|p| ls.starts_with(p)) {
            claimed.insert(i);
            continue;
        }
    }
    crash.first_user_frame = crash.frames.iter().find(|f| f.user).cloned();
    Some(crash)
}

fn parse_ubsan(
    lines: &[&str],
    claimed: &mut BTreeSet<usize>,
    diags: &mut Vec<Diagnostic>,
) -> Option<Crash> {
    let mut first: Option<Crash> = None;
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if let Some(c) = RE_UBSAN.captures(l) {
            claimed.insert(i);
            let file = c.get(1).unwrap().as_str().to_string();
            let line: u32 = c.get(2).unwrap().as_str().parse().unwrap_or(0);
            let col: u32 = c.get(3).unwrap().as_str().parse().unwrap_or(0);
            let msg = c.get(4).unwrap().as_str().to_string();
            diags.push(Diagnostic {
                tool: "ubsan".into(),
                severity: Severity::Error,
                file: Some(file.clone()),
                line: Some(line),
                col: Some(col),
                code: Some("runtime-error".into()),
                message: msg.clone(),
            });
            // UBSAN_OPTIONS=print_stacktrace=1 prints frames after the line — sometimes after a
            // "0x…: note: pointer points here" block with a hex dump and a caret line.
            let mut frames: Vec<Frame> = Vec::new();
            for (j, next) in lines.iter().enumerate().skip(i + 1) {
                let nl = next.trim_end();
                if let Some(f) = parse_frame(nl) {
                    claimed.insert(j);
                    frames.push(f);
                    continue;
                }
                let t = nl.trim();
                let is_note = t.starts_with("0x") && t.contains(": note:");
                let is_hexdump = !t.is_empty()
                    && t.split_whitespace()
                        .all(|w| w.len() == 2 && w.chars().all(|c| c.is_ascii_hexdigit()));
                let is_caret = !t.is_empty() && t.chars().all(|c| c == '^' || c == ' ' || c == '~');
                if is_note || is_hexdump || is_caret {
                    claimed.insert(j);
                    continue;
                }
                break;
            }
            if first.is_none() {
                // Kind = first clause, with hex addresses normalised so that crash identity
                // (and therefore deltas) does not depend on ASLR even when it is left on.
                let kind = RE_HEX_ADDR
                    .replace_all(
                        msg.split(':').next().unwrap_or("runtime error").trim(),
                        "0x…",
                    )
                    .to_string();
                let frame = Frame {
                    idx: 0,
                    func: frames.first().and_then(|f| f.func.clone()),
                    file: Some(file),
                    line: Some(line),
                    col: Some(col),
                    user: true,
                };
                if frames.is_empty() {
                    frames.push(frame.clone());
                }
                first = Some(Crash {
                    tool: "UndefinedBehaviorSanitizer".into(),
                    kind,
                    access: None,
                    address: None,
                    message: Some(msg),
                    frames,
                    alloc_frames: vec![],
                    free_frames: vec![],
                    first_user_frame: Some(frame),
                    summary: None,
                });
            }
        }
    }
    first
}

static RE_SRC_ECHO: Lazy<Regex> = Lazy::new(|| {
    // gcc/clang/rustc source echo and caret lines:
    //    12 |     total += values[i];
    //       |     ^~~~~
    //   |
    //   = note: `#[warn(unused_variables)]` on by default
    Regex::new(r"^\s*(\d+\s*)?\|").unwrap()
});
static RE_IN_FUNCTION: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\S+: (In (?:function|member function|constructor|destructor|instantiation of|lambda function)|At (?:global|top level)) .*:?$|^\S+: In function .*$|^In file included from .*|^\s+from \S+:\d+[:,]$").unwrap()
});

fn parse_compiler(lines: &[&str], claimed: &mut BTreeSet<usize>, diags: &mut Vec<Diagnostic>) {
    // rustc: multi-line "error[E0308]: msg" followed by " --> file:line:col"
    let mut pending_rust: Option<(usize, Diagnostic)> = None;
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if claimed.contains(&i) {
            continue;
        }
        if RE_SRC_ECHO.is_match(l)
            || RE_IN_FUNCTION.is_match(l)
            || l.trim_start().starts_with("= note:")
            || l.trim_start().starts_with("= help:")
        {
            claimed.insert(i);
            continue;
        }
        if let Some(c) = RE_DIAG.captures(l) {
            let sev = match c.get(4).unwrap().as_str() {
                "error" | "fatal error" => Severity::Error,
                "warning" => Severity::Warning,
                _ => Severity::Note,
            };
            let tool = if l.contains("[-W") || l.contains("-fpermissive") {
                "gcc"
            } else {
                "cc"
            };
            diags.push(Diagnostic {
                tool: tool.into(),
                severity: sev,
                file: Some(c.get(1).unwrap().as_str().to_string()),
                line: c.get(2).and_then(|m| m.as_str().parse().ok()),
                col: c.get(3).and_then(|m| m.as_str().parse().ok()),
                code: c.get(6).map(|m| m.as_str().to_string()),
                message: c.get(5).unwrap().as_str().trim().to_string(),
            });
            claimed.insert(i);
            continue;
        }
        if let Some(c) = RE_RUSTC.captures(l) {
            let msg = c.get(3).unwrap().as_str();
            if msg.starts_with("aborting due to")
                || msg.starts_with("could not compile")
                || msg.starts_with("build failed")
                || msg.starts_with("test failed")
                || msg.contains(") generated ")
                || msg.starts_with("failed to run custom build command")
            {
                claimed.insert(i);
                continue;
            }
            let sev = if c.get(1).unwrap().as_str() == "error" {
                Severity::Error
            } else {
                Severity::Warning
            };
            let d = Diagnostic {
                tool: "rustc".into(),
                severity: sev,
                file: None,
                line: None,
                col: None,
                code: c.get(2).map(|m| m.as_str().to_string()),
                message: msg.to_string(),
            };
            if let Some((_, prev)) = pending_rust.take() {
                diags.push(prev);
            }
            pending_rust = Some((i, d));
            claimed.insert(i);
            continue;
        }
        if let Some(c) = RE_RUSTC_LOC.captures(l) {
            if let Some((_, mut d)) = pending_rust.take() {
                d.file = Some(c.get(1).unwrap().as_str().to_string());
                d.line = c.get(2).and_then(|m| m.as_str().parse().ok());
                d.col = c.get(3).and_then(|m| m.as_str().parse().ok());
                diags.push(d);
                claimed.insert(i);
                continue;
            }
        }
    }
    if let Some((_, d)) = pending_rust.take() {
        diags.push(d);
    }
}

static RE_UNITTEST_HEAD: Lazy<Regex> = Lazy::new(|| {
    // FAIL: test_total (test_inventory.TestInventory.test_total)
    // ERROR: test_remove_missing (test_inventory.TestInventory.test_remove_missing)
    Regex::new(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)\s*$").unwrap()
});
static RE_UNITTEST_VERBOSE: Lazy<Regex> = Lazy::new(|| {
    // test_add (test_inventory.TestInventory.test_add) ... ok
    Regex::new(
        r"^\S+ \([^)]+\) \.\.\. (ok|FAIL|ERROR|skipped.*|expected failure|unexpected success)$",
    )
    .unwrap()
});
static RE_UNITTEST_RAN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^Ran (\d+) tests? in [0-9.]+s$").unwrap());
static RE_UNITTEST_SUMMARY: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^(OK|FAILED)(?: \((.*)\))?$").unwrap());

/// python -m unittest (verbose or not).
fn parse_unittest(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Tests> {
    let ran_idx = lines
        .iter()
        .position(|l| RE_UNITTEST_RAN.is_match(l.trim_end()))?;
    let mut t = Tests {
        runner: "unittest".into(),
        ..Default::default()
    };
    let total: u32 = RE_UNITTEST_RAN
        .captures(lines[ran_idx].trim_end())
        .and_then(|c| c.get(1)?.as_str().parse().ok())
        .unwrap_or(0);
    claimed.insert(ran_idx);
    // Summary line follows (possibly after a blank line).
    for (j, raw) in lines.iter().enumerate().skip(ran_idx + 1).take(3) {
        let l = raw.trim_end();
        if let Some(c) = RE_UNITTEST_SUMMARY.captures(l) {
            claimed.insert(j);
            if let Some(detail) = c.get(2) {
                for part in detail.as_str().split(',') {
                    let mut kv = part.trim().splitn(2, '=');
                    let k = kv.next().unwrap_or("");
                    let v: u32 = kv.next().and_then(|x| x.trim().parse().ok()).unwrap_or(0);
                    match k {
                        "failures" => t.failed = v,
                        "errors" => t.errors = v,
                        "skipped" | "expected failures" => t.skipped += v,
                        _ => {}
                    }
                }
            }
            break;
        }
    }
    t.passed = total.saturating_sub(t.failed + t.errors + t.skipped);
    // Per-failure blocks: header, separator, traceback, exception line.
    let mut i = 0;
    while i < lines.len() {
        let l = lines[i].trim_end();
        if let Some(c) = RE_UNITTEST_HEAD.captures(l) {
            claimed.insert(i);
            let name = c.get(3).unwrap().as_str().to_string();
            let mut file: Option<String> = None;
            let mut line_no: Option<u32> = None;
            let mut message: Option<String> = None;
            let mut j = i + 1;
            while j < lines.len() {
                let lj = lines[j].trim_end();
                if RE_UNITTEST_HEAD.is_match(lj) || RE_UNITTEST_RAN.is_match(lj) {
                    break;
                }
                let is_separator = !lj.is_empty() && lj.chars().all(|ch| ch == '-' || ch == '=');
                if let Some(fc) = RE_PY_TRACE_LOC.captures(lj) {
                    // Location: the innermost *user* frame outside the test file (the code under
                    // test) when there is one, otherwise the test-file frame itself.
                    let f_file = fc.get(1).unwrap().as_str().to_string();
                    let f_line: Option<u32> = fc.get(2).unwrap().as_str().parse().ok();
                    let in_test_file = f_file
                        .rsplit('/')
                        .next()
                        .map(|b| {
                            b.starts_with("test_")
                                || b.ends_with("_test.py")
                                || b.contains("/tests/")
                        })
                        .unwrap_or(false);
                    if file.is_none() || (!in_test_file && is_user_path(&f_file)) {
                        file = Some(f_file);
                        line_no = f_line;
                    }
                    claimed.insert(j);
                } else if let Some(ec) = RE_PY_EXC.captures(lj) {
                    message = Some(format!(
                        "{}: {}",
                        ec.get(1).unwrap().as_str(),
                        ec.get(2).unwrap().as_str()
                    ));
                    claimed.insert(j);
                    j += 1;
                    break;
                } else if is_separator
                    || lj.starts_with("Traceback (most recent call last):")
                    || lj.starts_with("    ")
                {
                    claimed.insert(j);
                }
                // blank lines: keep going
                j += 1;
            }
            t.failures.push(TestFailure {
                name,
                file,
                line: line_no,
                message,
            });
            i = j;
            continue;
        }
        let is_separator = (l.starts_with("======") || l.starts_with("------"))
            && l.chars().all(|ch| ch == '=' || ch == '-');
        if RE_UNITTEST_VERBOSE.is_match(l) || is_separator {
            claimed.insert(i);
        }
        i += 1;
    }
    if t.failed + t.errors == 0 && !t.failures.is_empty() {
        t.failed = t.failures.len() as u32;
    }
    Some(t)
}

static RE_CHECK_OK: Lazy<Regex> = Lazy::new(|| Regex::new(r"^ok\s+(\S+)\s*$").unwrap());
static RE_CHECK_FAIL: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^FAIL\s+(\S+)(?:\s+\((rc=\d+)\))?\s*$").unwrap());
static RE_CHECK_ALL: Lazy<Regex> = Lazy::new(|| Regex::new(r"^ALL TESTS PASSED$").unwrap());

/// Generic shell check scripts that print `ok <name>` / `FAIL <name> (rc=N)` per check
/// (the convention used by bench/tasks/*/test.sh and many hand-written test scripts).
fn parse_check_script(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Tests> {
    let mut t = Tests {
        runner: "check".into(),
        ..Default::default()
    };
    let mut seen = false;
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if let Some(c) = RE_CHECK_OK.captures(l) {
            let _ = c;
            seen = true;
            t.passed += 1;
            claimed.insert(i);
        } else if let Some(c) = RE_CHECK_FAIL.captures(l) {
            seen = true;
            t.failed += 1;
            // Detail block that check scripts print after a FAIL line (our convention:
            // "--- stdout ---", "--- stderr ---", "--- expected ---" sections) up to the next
            // ok/FAIL/summary line: keep a compact got-vs-expected message so the verdict is not
            // less informative than the raw output for logic bugs. Sanitizer reports inside the
            // block are left unclaimed here (the sanitizer parser already took them).
            let mut detail: Vec<String> = Vec::new();
            let mut section = "";
            let mut j = i + 1;
            while j < lines.len() {
                let lj = lines[j].trim_end();
                if RE_CHECK_OK.is_match(lj)
                    || RE_CHECK_FAIL.is_match(lj)
                    || RE_CHECK_ALL.is_match(lj)
                {
                    break;
                }
                if lj.starts_with("--- stdout") {
                    section = "got";
                    claimed.insert(j);
                } else if lj.starts_with("--- stderr") {
                    section = "stderr";
                    claimed.insert(j);
                } else if lj.starts_with("--- expected") {
                    section = "expected";
                    claimed.insert(j);
                } else if section == "got" || section == "expected" {
                    if !lj.trim().is_empty() && detail.len() < 24 {
                        detail.push(format!("{section}: {}", lj.trim()));
                    }
                    claimed.insert(j);
                } else if section == "stderr" && !claimed.contains(&j) && RE_ASAN_HEAD.is_match(lj)
                {
                    // leave sanitizer report lines to the sanitizer parser / tail
                }
                j += 1;
            }
            let mut message = c.get(2).map(|m| m.as_str().to_string()).unwrap_or_default();
            if !detail.is_empty() {
                let got: Vec<&str> = detail
                    .iter()
                    .filter(|d| d.starts_with("got: "))
                    .map(|d| &d[5..])
                    .collect();
                let exp: Vec<&str> = detail
                    .iter()
                    .filter(|d| d.starts_with("expected: "))
                    .map(|d| &d[10..])
                    .collect();
                let mut parts = Vec::new();
                if !exp.is_empty() {
                    parts.push(format!("expected [{}]", exp.join(" ⏎ ")));
                }
                if !got.is_empty() {
                    parts.push(format!("got [{}]", got.join(" ⏎ ")));
                } else if !exp.is_empty() {
                    parts.push("got [no output]".to_string());
                }
                if !parts.is_empty() {
                    let d = parts.join(", ");
                    let d: String = d.chars().take(360).collect();
                    message = if message.is_empty() {
                        d
                    } else {
                        format!("{message}; {d}")
                    };
                }
            }
            t.failures.push(TestFailure {
                name: c.get(1).unwrap().as_str().to_string(),
                file: None,
                line: None,
                message: if message.is_empty() {
                    None
                } else {
                    Some(message)
                },
            });
            claimed.insert(i);
        } else if RE_CHECK_ALL.is_match(l) {
            seen = true;
            claimed.insert(i);
        }
    }
    if seen {
        Some(t)
    } else {
        None
    }
}

fn parse_tests(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Tests> {
    if let Some(t) = parse_unittest(lines, claimed) {
        return Some(t);
    }
    let mut t: Option<Tests> = None;
    // pytest
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if let Some(c) = RE_PYTEST_SUMMARY.captures(l) {
            let mut tt = t.take().unwrap_or_default();
            tt.runner = "pytest".into();
            for part in c.get(1).unwrap().as_str().split(',') {
                let mut it = part.split_whitespace();
                let n: u32 = it.next().and_then(|x| x.parse().ok()).unwrap_or(0);
                match it.next().unwrap_or("") {
                    "passed" => tt.passed = n,
                    "failed" => tt.failed = n,
                    "error" | "errors" => tt.errors = n,
                    "skipped" | "deselected" | "xfailed" => tt.skipped += n,
                    _ => {}
                }
            }
            t = Some(tt);
            claimed.insert(i);
        } else if let Some(c) = RE_PYTEST_FAILED.captures(l) {
            let mut tt = t.take().unwrap_or_default();
            tt.runner = "pytest".into();
            let file = c.get(2).map(|m| m.as_str().to_string());
            let name = match c.get(3) {
                Some(n) => format!("{}::{}", file.clone().unwrap_or_default(), n.as_str()),
                None => file.clone().unwrap_or_default(),
            };
            tt.failures.push(TestFailure {
                name,
                file,
                line: None,
                message: c.get(4).map(|m| m.as_str().to_string()),
            });
            t = Some(tt);
            claimed.insert(i);
        }
    }
    if t.is_some() {
        return t;
    }
    // cargo test
    let mut ct = Tests {
        runner: "cargo-test".into(),
        ..Default::default()
    };
    let mut seen = false;
    let mut panics: Vec<(String, String, u32)> = vec![];
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if let Some(c) = RE_CARGO_TEST_RESULT.captures(l) {
            seen = true;
            ct.passed += c.get(2).unwrap().as_str().parse::<u32>().unwrap_or(0);
            ct.failed += c.get(3).unwrap().as_str().parse::<u32>().unwrap_or(0);
            ct.skipped += c.get(4).unwrap().as_str().parse::<u32>().unwrap_or(0);
            claimed.insert(i);
        } else if let Some(c) = RE_CARGO_TEST_FAIL.captures(l) {
            seen = true;
            ct.failures.push(TestFailure {
                name: c.get(1).unwrap().as_str().to_string(),
                file: None,
                line: None,
                message: None,
            });
            claimed.insert(i);
        } else if let Some(c) = RE_CARGO_PANIC.captures(l) {
            panics.push((
                c.get(1).unwrap().as_str().to_string(),
                c.get(2).unwrap().as_str().to_string(),
                c.get(3).unwrap().as_str().parse().unwrap_or(0),
            ));
            claimed.insert(i);
            // The panic message is on the next line.
            if let Some(next) = lines.get(i + 1) {
                let n = next.trim();
                if !n.is_empty() && !n.starts_with("note:") && !n.starts_with("stack backtrace") {
                    let last = panics.len() - 1;
                    let _ = last;
                    claimed.insert(i + 1);
                    if let Some(f) = ct.failures.iter_mut().find(|f| f.name == panics[last].0) {
                        f.message = Some(n.to_string());
                    } else {
                        ct.failures.push(TestFailure {
                            name: panics[last].0.clone(),
                            file: Some(panics[last].1.clone()),
                            line: Some(panics[last].2),
                            message: Some(n.to_string()),
                        });
                    }
                }
            }
        }
    }
    if seen {
        // attach locations from panics
        for (name, file, line) in &panics {
            if let Some(f) = ct.failures.iter_mut().find(|f| &f.name == name) {
                if f.file.is_none() {
                    f.file = Some(file.clone());
                    f.line = Some(*line);
                }
            }
        }
        ct.failures.sort_by(|a, b| a.name.cmp(&b.name));
        ct.failures.dedup_by(|a, b| a.name == b.name);
        return Some(ct);
    }
    // gtest / ctest
    let mut gt = Tests {
        runner: "ctest".into(),
        ..Default::default()
    };
    let mut seen = false;
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if let Some(c) = RE_CTEST_SUMMARY.captures(l) {
            seen = true;
            let failed: u32 = c.get(2).unwrap().as_str().parse().unwrap_or(0);
            let total: u32 = c.get(3).unwrap().as_str().parse().unwrap_or(0);
            gt.failed = failed;
            gt.passed = total.saturating_sub(failed);
            claimed.insert(i);
        } else if let Some(c) = RE_CTEST_FAIL.captures(l) {
            seen = true;
            gt.failures.push(TestFailure {
                name: c.get(1).unwrap().as_str().to_string(),
                file: None,
                line: None,
                message: Some(c.get(2).unwrap().as_str().to_string()),
            });
            claimed.insert(i);
        } else if let Some(c) = RE_GTEST_FAIL.captures(l) {
            seen = true;
            gt.runner = "gtest".into();
            let name = c.get(1).unwrap().as_str().to_string();
            if !gt.failures.iter().any(|f| f.name == name) {
                gt.failures.push(TestFailure {
                    name,
                    file: None,
                    line: None,
                    message: None,
                });
            }
            claimed.insert(i);
        }
    }
    if seen {
        if gt.runner == "gtest" {
            gt.failed = gt.failures.len() as u32;
        }
        return Some(gt);
    }
    parse_check_script(lines, claimed)
}

static RE_RUST_BT_FRAME: Lazy<Regex> = Lazy::new(|| {
    // RUST_BACKTRACE=1:   "   3: slmax::sliding_max"  /  "             at ./main.rs:10:21"
    Regex::new(r"^\s+(\d+): (.+)$|^\s+at (\S+?):(\d+)(?::(\d+))?$").unwrap()
});

/// A Rust panic outside cargo test ("thread 'main' panicked at main.rs:10:21:" + message line,
/// optionally followed by a RUST_BACKTRACE=1 stack).
fn parse_rust_panic(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Crash> {
    let (i, c) = lines
        .iter()
        .enumerate()
        .find_map(|(i, l)| RE_CARGO_PANIC.captures(l.trim_end()).map(|c| (i, c)))?;
    let file = c.get(2).unwrap().as_str().to_string();
    let line: u32 = c.get(3).unwrap().as_str().parse().unwrap_or(0);
    let col: Option<u32> = c.get(4).unwrap().as_str().parse().ok();
    claimed.insert(i);
    // The panic message is the next non-empty line that is not a note/backtrace line.
    let mut message = None;
    let mut j = i + 1;
    while j < lines.len() {
        let l = lines[j].trim_end();
        if l.trim().is_empty() {
            j += 1;
            continue;
        }
        if l.starts_with("note:") || l.starts_with("stack backtrace:") {
            break;
        }
        message = Some(l.trim().to_string());
        claimed.insert(j);
        j += 1;
        break;
    }
    // Backtrace frames: "   N: path::to::fn" then "at file:line:col"; keep user frames.
    let mut frames: Vec<Frame> = Vec::new();
    let mut pending_func: Option<(u32, String)> = None;
    while j < lines.len() {
        let l = lines[j].trim_end();
        if l.starts_with("note:") {
            claimed.insert(j);
            j += 1;
            continue;
        }
        if l.starts_with("stack backtrace:") {
            claimed.insert(j);
            j += 1;
            continue;
        }
        if let Some(m) = RE_RUST_BT_FRAME.captures(l) {
            claimed.insert(j);
            if let (Some(idx), Some(func)) = (m.get(1), m.get(2)) {
                pending_func = Some((idx.as_str().parse().unwrap_or(0), func.as_str().to_string()));
            } else if let (Some(f), Some(ln)) = (m.get(3), m.get(4)) {
                let file_s = f.as_str().to_string();
                let user = is_user_path(&file_s)
                    && pending_func
                        .as_ref()
                        .map(|(_, fun)| is_user_func(fun))
                        .unwrap_or(true);
                frames.push(Frame {
                    idx: pending_func
                        .as_ref()
                        .map(|(i, _)| *i)
                        .unwrap_or(frames.len() as u32),
                    func: pending_func.take().map(|(_, f)| f),
                    file: Some(file_s),
                    line: ln.as_str().parse().ok(),
                    col: m.get(5).and_then(|x| x.as_str().parse().ok()),
                    user,
                });
            }
            j += 1;
            continue;
        }
        break;
    }
    let site = Frame {
        idx: 0,
        func: None,
        file: Some(file),
        line: Some(line),
        col,
        user: true,
    };
    if frames.is_empty() {
        frames.push(site.clone());
    }
    Some(Crash {
        tool: "rust-panic".into(),
        kind: message
            .clone()
            .map(|m| RE_HEX_ADDR.replace_all(&m, "0x…").to_string())
            .unwrap_or_else(|| "panic".into()),
        access: None,
        address: None,
        message,
        frames,
        alloc_frames: vec![],
        free_frames: vec![],
        first_user_frame: Some(site),
        summary: None,
    })
}

fn parse_python_exception(lines: &[&str], claimed: &mut BTreeSet<usize>) -> Option<Crash> {
    let mut frames = vec![];
    let mut exc: Option<(String, String)> = None;
    let mut in_tb = false;
    for (i, raw) in lines.iter().enumerate() {
        let l = raw.trim_end();
        if l.starts_with("Traceback (most recent call last):") {
            in_tb = true;
            frames.clear();
            claimed.insert(i);
            continue;
        }
        if in_tb {
            if let Some(c) = RE_PY_TRACE_LOC.captures(l) {
                let file = c.get(1).unwrap().as_str().to_string();
                let user = is_user_path(&file);
                frames.push(Frame {
                    idx: frames.len() as u32,
                    func: Some(c.get(3).unwrap().as_str().to_string()),
                    file: Some(file),
                    line: c.get(2).unwrap().as_str().parse().ok(),
                    col: None,
                    user,
                });
                claimed.insert(i);
                continue;
            }
            if let Some(c) = RE_PY_EXC.captures(l) {
                exc = Some((
                    c.get(1).unwrap().as_str().to_string(),
                    c.get(2).unwrap().as_str().to_string(),
                ));
                claimed.insert(i);
                in_tb = false;
                continue;
            }
            // source line echo under a File line
            if l.starts_with("    ") {
                claimed.insert(i);
            }
        }
    }
    let (kind, msg) = exc?;
    // Python tracebacks list outermost first; "first user frame" should be the innermost user frame.
    let first_user = frames.iter().rev().find(|f| f.user).cloned();
    Some(Crash {
        tool: "python".into(),
        kind,
        access: None,
        address: None,
        message: Some(msg),
        frames,
        alloc_frames: vec![],
        free_frames: vec![],
        first_user_frame: first_user,
        summary: None,
    })
}

pub fn distill(stdout: &[u8], stderr: &[u8], facts: &RunFacts) -> Verdict {
    let out = String::from_utf8_lossy(stdout);
    let err = String::from_utf8_lossy(stderr);
    // Sanitizers and compilers write to stderr; test runners mostly to stdout. Parse both.
    let combined: String = format!("{}\n{}", err, out);
    let lines: Vec<&str> = combined.lines().collect();
    let mut claimed: BTreeSet<usize> = BTreeSet::new();
    let mut diags: Vec<Diagnostic> = vec![];

    let mut crash = parse_sanitizer(&lines, &mut claimed);
    let ub = parse_ubsan(&lines, &mut claimed, &mut diags);
    if crash.is_none() {
        crash = ub;
    }
    parse_compiler(&lines, &mut claimed, &mut diags);
    let tests = parse_tests(&lines, &mut claimed);
    // A panic/traceback inside a *test runner's* failure report (cargo test, pytest, unittest) is
    // already represented by the failure list; only a panic/traceback outside a test runner — e.g.
    // a program crashing under a shell check script — is a crash of its own.
    let inside_test_runner = tests
        .as_ref()
        .map(|t| t.runner != "check" && !t.failures.is_empty())
        .unwrap_or(false);
    if crash.is_none() && !inside_test_runner {
        crash = parse_rust_panic(&lines, &mut claimed);
    }
    if crash.is_none() && !inside_test_runner {
        crash = parse_python_exception(&lines, &mut claimed);
    }
    // Bare fatal signal without a sanitizer report.
    if crash.is_none() {
        if let Some(sig) = &facts.signal {
            crash = Some(Crash {
                tool: "signal".into(),
                kind: sig.clone(),
                access: None,
                address: None,
                message: None,
                frames: vec![],
                alloc_frames: vec![],
                free_frames: vec![],
                first_user_frame: None,
                summary: None,
            });
        }
    }

    // Dedup diagnostics (same tool/sev/file/line/message).
    let mut seen = BTreeSet::new();
    diags.retain(|d| {
        seen.insert(format!(
            "{}|{:?}|{:?}|{:?}|{}",
            d.tool, d.severity, d.file, d.line, d.message
        ))
    });

    let error_groups = {
        let mut g = BTreeSet::new();
        for d in diags.iter().filter(|d| d.severity == Severity::Error) {
            g.insert(format!(
                "{}|{}",
                d.tool,
                d.code.clone().unwrap_or_else(|| normalize_msg(&d.message))
            ));
        }
        g.len() as u32
    };

    // Tail: last unclaimed non-empty lines.
    let mut tail: Vec<String> = lines
        .iter()
        .enumerate()
        .filter(|(i, l)| !claimed.contains(i) && !l.trim().is_empty())
        .map(|(_, l)| l.trim_end().chars().take(200).collect::<String>())
        .collect();
    if tail.len() > 12 {
        tail = tail.split_off(tail.len() - 12);
    }

    let status = if let Some(m) = &facts.setup_failed {
        let _ = m;
        Status::SetupFailed
    } else if facts.timed_out {
        Status::Timeout
    } else if let Some(c) = &crash {
        if c.tool == "python" {
            if tests
                .as_ref()
                .map(|t| t.failed + t.errors > 0)
                .unwrap_or(false)
            {
                Status::TestsFailed
            } else {
                Status::RuntimeError
            }
        } else {
            Status::Crash
        }
    } else if diags.iter().any(|d| {
        d.severity == Severity::Error && (d.tool == "gcc" || d.tool == "cc" || d.tool == "rustc")
    }) && facts.exit_code.unwrap_or(1) != 0
    {
        Status::BuildFailed
    } else if let Some(t) = &tests {
        if t.failed + t.errors > 0 {
            Status::TestsFailed
        } else if facts.exit_code == Some(0) {
            Status::Pass
        } else {
            Status::RuntimeError
        }
    } else if facts.exit_code == Some(0) {
        Status::Pass
    } else if facts.exit_code.is_some() {
        Status::RuntimeError
    } else {
        Status::Unknown
    };

    Verdict {
        status,
        exit_code: facts.exit_code,
        signal: facts.signal.clone(),
        timed_out: facts.timed_out,
        wall_ms: facts.wall_ms,
        diagnostics: diags,
        crash,
        tests,
        tail,
        raw_bytes: stdout.len() + stderr.len(),
        error_groups,
    }
}

/// Normalise a message for grouping: strip quoted identifiers and numbers.
pub fn normalize_msg(m: &str) -> String {
    static RE_Q: Lazy<Regex> =
        Lazy::new(|| Regex::new(r"(['`‘’][^'`‘’]*['`‘’])|(0x[0-9a-fA-F]+)|(\b\d+\b)").unwrap());
    static RE_SUGGEST: Lazy<Regex> = Lazy::new(|| Regex::new(r";\s*did you mean.*$").unwrap());
    let m = RE_SUGGEST.replace(m, "");
    RE_Q.replace_all(&m, "_").trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    const ASAN: &str = include_str!("../tests/fixtures/asan_heap_overflow.txt");
    const GCC: &str = include_str!("../tests/fixtures/gcc_errors.txt");
    const PYTEST: &str = include_str!("../tests/fixtures/pytest_fail.txt");
    const UBSAN: &str = include_str!("../tests/fixtures/ubsan.txt");
    const RUSTC: &str = include_str!("../tests/fixtures/rustc_errors.txt");
    const CARGO_TEST: &str = include_str!("../tests/fixtures/cargo_test_fail.txt");

    #[test]
    fn asan_heap_overflow_is_distilled() {
        let v = distill(
            b"",
            ASAN.as_bytes(),
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::Crash);
        let c = v.crash.expect("crash");
        assert_eq!(c.tool, "AddressSanitizer");
        assert_eq!(c.kind, "heap-buffer-overflow");
        assert_eq!(c.access.as_deref(), Some("WRITE of size 4"));
        let f = c.first_user_frame.expect("user frame");
        assert_eq!(f.file.as_deref(), Some("/work/overflow.c"));
        assert_eq!(f.line, Some(7));
        assert_eq!(f.func.as_deref(), Some("fill"));
        assert!(!c.alloc_frames.is_empty(), "allocation stack captured");
        assert!(c.summary.is_some());
        // the shadow-byte dump must not leak into the tail
        assert!(
            v.tail.iter().all(|l| !l.contains("Shadow")),
            "tail: {:?}",
            v.tail
        );
    }

    #[test]
    fn gcc_diagnostics_are_grouped() {
        let v = distill(
            b"",
            GCC.as_bytes(),
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::BuildFailed);
        let errs: Vec<_> = v.errors().collect();
        assert_eq!(errs.len(), 3, "{errs:?}");
        assert_eq!(errs[0].file.as_deref(), Some("src/main.c"));
        assert_eq!(errs[0].line, Some(12));
        assert_eq!(errs[0].col, Some(5));
        assert!(v
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Warning
                && d.code.as_deref() == Some("-Wunused-variable")));
        assert_eq!(
            v.error_groups, 2,
            "two distinct error kinds: undeclared + incompatible types"
        );
    }

    #[test]
    fn pytest_failures_are_listed() {
        let v = distill(
            PYTEST.as_bytes(),
            b"",
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::TestsFailed);
        let t = v.tests.expect("tests");
        assert_eq!(t.runner, "pytest");
        assert_eq!((t.passed, t.failed, t.errors), (5, 2, 0));
        assert_eq!(t.failures.len(), 2);
        assert!(t.failures[0].name.contains("test_calc.py::test_divide"));
        assert!(t.failures[0]
            .message
            .as_deref()
            .unwrap()
            .contains("ZeroDivisionError"));
    }

    #[test]
    fn ubsan_runtime_error_is_a_crash_and_a_diagnostic() {
        let v = distill(
            b"",
            UBSAN.as_bytes(),
            &RunFacts {
                exit_code: Some(1),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::Crash);
        let c = v.crash.unwrap();
        assert_eq!(c.tool, "UndefinedBehaviorSanitizer");
        assert_eq!(c.kind, "signed integer overflow");
        assert_eq!(c.first_user_frame.unwrap().line, Some(7));
        assert_eq!(v.diagnostics.len(), 1);
    }

    #[test]
    fn rustc_errors_get_locations() {
        let v = distill(
            b"",
            RUSTC.as_bytes(),
            &RunFacts {
                exit_code: Some(101),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::BuildFailed);
        let errs: Vec<_> = v.errors().collect();
        assert_eq!(errs.len(), 2);
        assert_eq!(errs[0].code.as_deref(), Some("E0308"));
        assert_eq!(errs[0].file.as_deref(), Some("src/main.rs"));
        assert_eq!(errs[0].line, Some(4));
        assert_eq!(errs[1].code.as_deref(), Some("E0425"));
    }

    #[test]
    fn cargo_test_failures_get_panic_locations() {
        let v = distill(
            CARGO_TEST.as_bytes(),
            b"",
            &RunFacts {
                exit_code: Some(101),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::TestsFailed);
        let t = v.tests.unwrap();
        assert_eq!(t.runner, "cargo-test");
        assert_eq!((t.passed, t.failed), (3, 1));
        assert_eq!(t.failures.len(), 1);
        assert_eq!(t.failures[0].name, "tests::it_adds");
        assert_eq!(t.failures[0].file.as_deref(), Some("src/lib.rs"));
        assert_eq!(t.failures[0].line, Some(10));
        assert!(t.failures[0]
            .message
            .as_deref()
            .unwrap()
            .contains("assertion"));
    }

    #[test]
    fn bare_signal_becomes_crash() {
        let v = distill(
            b"",
            b"",
            &RunFacts {
                exit_code: None,
                signal: Some("SIGSEGV".into()),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::Crash);
        assert_eq!(v.crash.unwrap().kind, "SIGSEGV");
    }

    #[test]
    fn clean_exit_is_pass() {
        let v = distill(
            b"all good\n",
            b"",
            &RunFacts {
                exit_code: Some(0),
                ..Default::default()
            },
        );
        assert_eq!(v.status, Status::Pass);
        assert_eq!(v.tail, vec!["all good".to_string()]);
    }
}
