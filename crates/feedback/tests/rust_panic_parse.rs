use feedback::{distill, render, RenderOpts, RunFacts, Status};

const PANIC: &str = "\nthread 'main' panicked at main.rs:10:21:\nindex out of bounds: the len is 3 but the index is 3\nstack backtrace:\n   0: rust_begin_unwind\n             at /rustc/abc123/library/std/src/panicking.rs:665:5\n   1: core::panicking::panic_fmt\n             at /rustc/abc123/library/core/src/panicking.rs:74:14\n   2: core::panicking::panic_bounds_check\n             at /rustc/abc123/library/core/src/panicking.rs:276:5\n   3: slmax::sliding_max\n             at ./main.rs:10:21\n   4: slmax::main\n             at ./main.rs:31:14\n   5: core::ops::function::FnOnce::call_once\n             at /rustc/abc123/library/core/src/ops/function.rs:250:5\nnote: Some details are omitted, run with `RUST_BACKTRACE=full` for a verbose backtrace.\nFAIL k1 (rc=101)\n--- stdout ---\n--- stderr ---\n--- expected ---\n5\n3\n9\nok   too-few\n";

#[test]
fn rust_panic_becomes_a_crash_with_site_and_user_frames() {
    let v = distill(
        PANIC.as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    assert_eq!(v.status, Status::Crash, "{v:?}");
    let c = v.crash.clone().expect("crash");
    assert_eq!(c.tool, "rust-panic");
    assert_eq!(
        c.kind,
        "index out of bounds: the len is _ but the index is _".replace('_', "3")
    );
    let f = c.first_user_frame.clone().unwrap();
    assert_eq!(f.file.as_deref(), Some("main.rs"));
    assert_eq!(f.line, Some(10));
    assert_eq!(f.col, Some(21));
    // backtrace frames parsed, user frames classified
    let user: Vec<_> = c.frames.iter().filter(|f| f.user).collect();
    assert!(user.len() >= 2, "{:?}", c.frames);
    assert_eq!(user[0].func.as_deref(), Some("slmax::sliding_max"));
    assert_eq!(user[0].file.as_deref(), Some("./main.rs"));
    // the check-script tests were still parsed
    let t = v.tests.clone().expect("tests");
    assert_eq!((t.passed, t.failed), (1, 1));
    let text = render(&v, None, &RenderOpts::default());
    assert!(
        text.contains("crash: rust-panic index out of bounds"),
        "{text}"
    );
    assert!(text.contains("at main.rs:10:21"), "{text}");
    // backtrace noise must not flood the tail
    assert!(
        v.tail.iter().all(|l| !l.contains("rust_begin_unwind")),
        "tail: {:?}",
        v.tail
    );
}
