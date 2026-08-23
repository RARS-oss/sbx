//! "Huge noisy output" axis (research plan §1): a real fault buried in a giant CI log.
//! A strong model still burns tokens re-reading a 200 KB+ log to find the one line that matters;
//! sbx hands it a <1 KB typed verdict instead. These tests pin that reduction on realistic noise.

use feedback::{distill, render, RenderOpts, RunFacts, Status};

/// ~300 KB of npm/webpack/CI chatter with one AddressSanitizer crash buried in the middle.
fn ci_log_with_buried_asan() -> String {
    let mut s = String::with_capacity(320_000);
    for i in 0..2500 {
        s.push_str(&format!(
            "[{i:05}] npm WARN deprecated left-pad@1.0.0: use String.prototype.padStart instead\n"
        ));
    }
    // the single block that actually matters, drowned in noise
    s.push_str("==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000038 at pc 0x55 bp 0x7f sp 0x7f\n");
    s.push_str("READ of size 4 at 0x602000000038 thread T0\n");
    s.push_str("    #0 0x5555 in histogram /work/src/stats.c:42:16\n");
    s.push_str("    #1 0x5556 in main /work/src/main.c:88:3\n");
    s.push_str("    #2 0x7ffff in __libc_start_main /lib/x86_64-linux-gnu/libc.so.6\n");
    s.push_str(
        "0x602000000038 is located 0 bytes after 40-byte region [0x602000000010,0x602000000038)\n",
    );
    s.push_str(
        "SUMMARY: AddressSanitizer: heap-buffer-overflow /work/src/stats.c:42:16 in histogram\n",
    );
    for i in 0..2500 {
        s.push_str(&format!(
            "[{i:05}] webpack: asset bundle-{i}.js 1.2 MiB [emitted] [big] (name: main)\n"
        ));
    }
    s
}

#[test]
fn a_crash_buried_in_a_huge_ci_log_is_distilled_to_a_tiny_verdict() {
    let raw = ci_log_with_buried_asan();
    assert!(
        raw.len() > 200_000,
        "the log is genuinely huge: {} bytes",
        raw.len()
    );

    let v = distill(
        raw.as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );

    // the needle was found in the haystack
    assert_eq!(v.status, Status::Crash);
    let c = v.crash.clone().expect("crash extracted from the noise");
    assert_eq!(c.kind, "heap-buffer-overflow");
    assert_eq!(c.region.as_deref(), Some("0 bytes after a 40-byte region"));
    let fuf = c.first_user_frame.clone().expect("first user frame");
    assert_eq!(fuf.file.as_deref(), Some("/work/src/stats.c"));
    assert_eq!(fuf.line, Some(42));
    assert_eq!(fuf.func.as_deref(), Some("histogram"));

    // the whole point: the agent sees a tiny verdict, not the 200 KB+.
    let text = render(&v, None, &RenderOpts::default());
    assert!(
        text.len() < 1200,
        "rendered verdict stays tiny: {} bytes\n{text}",
        text.len()
    );
    let reduction = raw.len() as f64 / text.len() as f64;
    assert!(reduction > 200.0, "reduction only {reduction:.0}x");
    eprintln!(
        "noisy-log: {} raw bytes -> {} rendered bytes  ({:.0}x smaller)",
        raw.len(),
        text.len(),
        reduction
    );
}

/// A 5000-line test run with thousands of passing lines and a few failures buried in it.
#[test]
fn a_few_failures_in_a_flood_of_passing_tests_are_pulled_out() {
    let mut s = String::with_capacity(200_000);
    for i in 0..2400 {
        s.push_str(&format!("test suite::module_{i}::case_ok ... ok\n"));
    }
    s.push_str("---- suite::stats::histogram_bounds stdout ----\n");
    s.push_str("thread 'suite::stats::histogram_bounds' panicked at 'index out of bounds: the len is 40 but the index is 40', src/stats.rs:42:16\n");
    for i in 0..2400 {
        s.push_str(&format!("test suite::other::case_{i} ... ok\n"));
    }
    s.push_str("failures:\n    suite::stats::histogram_bounds\n");
    s.push_str(
        "test result: FAILED. 4800 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out\n",
    );

    let v = distill(
        s.as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(101),
            ..Default::default()
        },
    );
    let text = render(&v, None, &RenderOpts::default());
    // the raw is huge; the verdict is small and names the one failing test
    assert!(s.len() > 100_000, "{}", s.len());
    assert!(
        text.len() < 1200,
        "rendered stays small: {} bytes\n{text}",
        text.len()
    );
    assert!(
        text.contains("histogram_bounds"),
        "the buried failure is surfaced:\n{text}"
    );
    eprintln!(
        "noisy-tests: {} raw bytes -> {} rendered bytes ({:.0}x smaller)",
        s.len(),
        text.len(),
        s.len() as f64 / text.len() as f64
    );
}
