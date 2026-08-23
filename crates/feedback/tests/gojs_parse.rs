use feedback::{distill, RenderOpts, RunFacts, Status};

fn run(out: &str) -> feedback::Verdict {
    distill(
        out.as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    )
}

#[test]
fn go_test_is_parsed() {
    let v = run(include_str!("fixtures/go_test_fail.txt"));
    assert_eq!(v.status, Status::TestsFailed, "{v:?}");
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "go-test");
    assert_eq!((t.passed, t.failed), (2, 1));
    assert_eq!(t.failures.len(), 1);
    let f = &t.failures[0];
    assert_eq!(f.name, "TestProduct");
    assert_eq!(f.file.as_deref(), Some("calc_test.go"));
    assert_eq!(f.line, Some(24));
    assert_eq!(f.message.as_deref(), Some("Product(3, 4) = 7; want 12"));
    let text = feedback::render(&v, None, &RenderOpts::default());
    assert!(text.contains("failing tests (go-test):"), "{text}");
}

#[test]
fn jest_is_parsed() {
    let v = run(include_str!("fixtures/jest_fail.txt"));
    assert_eq!(v.status, Status::TestsFailed, "{v:?}");
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "jest");
    assert_eq!((t.passed, t.failed), (2, 1));
    assert_eq!(t.failures.len(), 1);
    let f = &t.failures[0];
    assert!(f.name.contains("adds two numbers"), "{}", f.name);
    assert_eq!(f.file.as_deref(), Some("src/sum.test.js"));
    assert_eq!(f.line, Some(7));
}

#[test]
fn vitest_is_parsed() {
    let v = run(include_str!("fixtures/vitest_fail.txt"));
    assert_eq!(v.status, Status::TestsFailed, "{v:?}");
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "vitest");
    assert_eq!((t.passed, t.failed), (2, 1));
    assert_eq!(t.failures.len(), 1);
    let f = &t.failures[0];
    assert_eq!(f.name, "subtracts");
    assert_eq!(f.file.as_deref(), Some("src/sum.test.ts"));
    assert_eq!(f.line, Some(11));
}

#[test]
fn junit_surefire_is_parsed() {
    let v = run(include_str!("fixtures/junit_surefire.txt"));
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "junit");
    assert_eq!((t.passed, t.failed), (2, 1));
    assert!(t.failures.iter().any(|f| f.name == "com.example.CalcTest.testAdd"), "{:?}", t.failures);
}

#[test]
fn junit_gradle_is_parsed() {
    let v = run(include_str!("fixtures/junit_gradle.txt"));
    let t = v.tests.clone().expect("tests");
    assert_eq!(t.runner, "junit");
    assert_eq!(t.failed, 1);
    assert!(t.failures.iter().any(|f| f.name.contains("testAdd")), "{:?}", t.failures);
}
