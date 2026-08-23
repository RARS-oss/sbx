use feedback::{distill, render, RenderOpts, RunFacts};

#[test]
fn crash_hints_are_rendered_for_known_kinds() {
    let asan = include_str!("fixtures/asan_heap_overflow.txt");
    let v = distill(
        b"",
        asan.as_bytes(),
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    let text = render(&v, None, &RenderOpts::default());
    assert!(
        text.contains("  hint: read/write past the end (or before the start) of a heap allocation"),
        "{text}"
    );
    // the offending geometry (the "value" for a bounds bug) is captured, address-stripped, rendered
    assert_eq!(
        v.crash.as_ref().and_then(|c| c.region.as_deref()),
        Some("0 bytes after a 40-byte region")
    );
    assert!(text.contains("  offset: 0 bytes after a 40-byte region"), "{text}");
    let ub = include_str!("fixtures/ubsan.txt");
    let v = distill(
        b"",
        ub.as_bytes(),
        &RunFacts {
            exit_code: Some(1),
            ..Default::default()
        },
    );
    let text = render(&v, None, &RenderOpts::default());
    assert!(
        text.contains("  hint: signed arithmetic overflowed"),
        "{text}"
    );
    // unknown kinds get no hint line
    assert!(feedback::render::hint_for("AddressSanitizer", "something-new").is_none());
}
