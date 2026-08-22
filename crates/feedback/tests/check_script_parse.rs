use feedback::{distill, render, RenderOpts, RunFacts, Status};

const CHECK_OUT: &str = "ok   basic\nFAIL empty (rc=0)\n--- stdout ---\n0: 0\n1: 0\ntotal=1\n--- stderr ---\n--- expected ---\n0: 0\n1: 0\ntotal=0\nok   max-value\nFAIL boundary-N (rc=1)\n--- stdout ---\n--- stderr ---\n==5==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000024 at pc 0x0 bp 0x0 sp 0x0\nWRITE of size 4 at 0x602000000024 thread T0\n    #0 0x0 in main /work/histogram.c:19:9\n    #1 0x0 in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58:16\nSUMMARY: AddressSanitizer: heap-buffer-overflow /work/histogram.c:19:9 in main\n==5==ABORTING\n--- expected ---\n0: 0\n1: 0\n2: 0\ntotal=0\n";

#[test]
fn ok_fail_check_scripts_become_tests_and_crash_is_kept() {
    let v = distill(
        CHECK_OUT.as_bytes(),
        b"",
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    // A sanitizer report inside the script output still wins the status.
    assert_eq!(v.status, Status::Crash, "{v:?}");
    let t = v.tests.clone().expect("check-script tests");
    assert_eq!(t.runner, "check");
    assert_eq!((t.passed, t.failed), (2, 2));
    assert_eq!(t.failures[0].name, "empty");
    let msg = t.failures[0].message.clone().unwrap();
    assert!(msg.starts_with("rc=0; expected ["), "{msg}");
    assert!(
        msg.contains("total=0") && msg.contains("got [") && msg.contains("total=1"),
        "{msg}"
    );
    assert_eq!(t.failures[1].name, "boundary-N");
    let c = v.crash.clone().expect("crash");
    assert_eq!(c.kind, "heap-buffer-overflow");
    assert_eq!(c.first_user_frame.unwrap().line, Some(19));
    let text = render(&v, None, &RenderOpts::default());
    assert!(text.contains("tests=2/4 passed"), "{text}");
    assert!(text.contains("failing tests (check):"), "{text}");
    assert!(text.contains("  empty — rc=0; expected ["), "{text}");
}

#[test]
fn all_passed_check_script_is_pass() {
    let v = distill(
        b"ok   a\nok   b\nALL TESTS PASSED\n",
        b"",
        &RunFacts {
            exit_code: Some(0),
            ..Default::default()
        },
    );
    assert_eq!(v.status, Status::Pass);
    let t = v.tests.unwrap();
    assert_eq!((t.passed, t.failed), (2, 0));
    assert!(v.tail.is_empty(), "tail: {:?}", v.tail);
}
