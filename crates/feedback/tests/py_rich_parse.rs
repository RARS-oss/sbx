use feedback::{distill, RunFacts};

#[test]
fn rich_traceback_is_parsed() {
    let v = distill(
        include_str!("fixtures/rich_traceback.txt").as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    let c = v.crash.clone().expect("crash");
    assert_eq!(c.tool, "python");
    assert_eq!(c.kind, "ZeroDivisionError");
    assert_eq!(c.message.as_deref(), Some("division by zero"));
    // innermost user frame — the boxed rich frames are parsed like a normal traceback
    let fuf = c.first_user_frame.expect("first_user_frame");
    assert_eq!(fuf.file.as_deref(), Some("/app/main.py"));
    assert_eq!(fuf.line, Some(8));
    assert_eq!(fuf.func.as_deref(), Some("divide"));
    // the box-drawing lines must not leak into the tail
    assert!(
        v.tail.iter().all(|l| !l.contains('│') && !l.contains('╭')),
        "tail: {:?}",
        v.tail
    );
}
