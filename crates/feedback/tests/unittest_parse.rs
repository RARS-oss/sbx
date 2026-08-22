use feedback::{distill, RenderOpts, RunFacts, Status};

const UNITTEST: &str = include_str!("fixtures/unittest_fail.txt");

#[test]
fn unittest_failures_and_errors_are_parsed() {
    let v = distill(
        b"",
        UNITTEST.as_bytes(),
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    assert_eq!(v.status, Status::TestsFailed, "{:?}", v);
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "unittest");
    assert_eq!((t.passed, t.failed, t.errors), (2, 1, 1));
    assert_eq!(t.failures.len(), 2);
    let err = &t.failures[0];
    assert_eq!(err.name, "test_inventory.TestInventory.test_remove_missing");
    // innermost frame in the code under test (not the test file)
    assert_eq!(err.file.as_deref(), Some("/work/inventory.py"));
    assert_eq!(err.line, Some(12));
    assert_eq!(err.message.as_deref(), Some("KeyError: 'ghost'"));
    let fail = &t.failures[1];
    assert_eq!(fail.name, "test_inventory.TestInventory.test_total");
    assert_eq!(fail.message.as_deref(), Some("AssertionError: 4 != 5"));
    // The python traceback parser must not turn a test error into a bare runtime crash status.
    let text = feedback::render(&v, None, &RenderOpts::default());
    assert!(text.starts_with("[sbx] TESTS FAILED"), "{text}");
    assert!(text.contains("failing tests (unittest):"), "{text}");
    // nothing structural should leak into the tail
    assert!(
        v.tail
            .iter()
            .all(|l| !l.starts_with("Ran ") && !l.starts_with("FAILED")),
        "tail: {:?}",
        v.tail
    );
}
