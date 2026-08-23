use feedback::scope::enclosing_function_c;
use feedback::{diff, Diagnostic, Severity, Verdict};

fn diag(file: &str, line: u32, msg: &str, scope: Option<&str>) -> Diagnostic {
    Diagnostic {
        tool: "gcc".into(),
        severity: Severity::Error,
        file: Some(file.into()),
        line: Some(line),
        col: Some(1),
        code: None,
        message: msg.into(),
        scope: scope.map(str::to_string),
    }
}

#[test]
fn enclosing_function_is_found() {
    let src = "int helper(int x){\n  return x + 1;\n}\n\nint main(void){\n  int y = 0;\n  return y;\n}\n";
    assert_eq!(enclosing_function_c(src, 2).as_deref(), Some("helper"));
    assert_eq!(enclosing_function_c(src, 6).as_deref(), Some("main"));
    assert_eq!(enclosing_function_c(src, 4), None); // the blank line between the two functions
}

#[test]
fn scope_match_survives_a_big_line_shift() {
    // Same diagnostic, same function, but 40 lines lower after a refactor above it. The ±3 line
    // window alone would call this "1 fixed + 1 new"; the scope keeps it a single unchanged one.
    let mut a = Verdict::empty();
    a.diagnostics = vec![diag("m.c", 10, "'x' undeclared (first use in this function)", Some("main"))];
    let mut b = Verdict::empty();
    b.diagnostics = vec![diag("m.c", 50, "'x' undeclared (first use in this function)", Some("main"))];
    let d = diff(&a, &b);
    assert_eq!(d.unchanged, 1, "{d:?}");
    assert!(d.fixed.is_empty() && d.new.is_empty(), "{d:?}");
}

#[test]
fn different_scope_is_a_different_diagnostic() {
    // Lines are within the ±3 window, but the diagnostic is now in a *different* function — the
    // scope must override and report it as fixed-here / new-there.
    let mut a = Verdict::empty();
    a.diagnostics = vec![diag("m.c", 10, "'x' undeclared", Some("foo"))];
    let mut b = Verdict::empty();
    b.diagnostics = vec![diag("m.c", 11, "'x' undeclared", Some("bar"))];
    let d = diff(&a, &b);
    assert_eq!((d.fixed.len(), d.new.len()), (1, 1), "{d:?}");
}
