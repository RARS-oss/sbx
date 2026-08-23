//! Best-effort AST scope resolution: the enclosing function of a `(file, line)`, via tree-sitter.
//!
//! This is what makes the delta *semantic* rather than purely positional: two diagnostics are "the
//! same" if they sit in the same function, even after a refactor that moves the line far — a purely
//! line-shift-tolerant match (±3) cannot see that. Populated after distillation by [`enrich_scopes`],
//! which needs the source tree (the parser proper only sees stdout/stderr). C today; the same shape
//! extends to C++/Rust/Python by adding a grammar and a `function_definition` node kind.
use crate::Verdict;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Name of the function definition enclosing 1-based `line` in C source, if any.
pub fn enclosing_function_c(source: &str, line: u32) -> Option<String> {
    let mut parser = tree_sitter::Parser::new();
    parser.set_language(&tree_sitter_c::language()).ok()?;
    let tree = parser.parse(source, None)?;
    let target = line.saturating_sub(1) as usize; // tree-sitter rows are 0-based
    let mut best: Option<String> = None;
    let mut stack = vec![tree.root_node()];
    while let Some(node) = stack.pop() {
        if target < node.start_position().row || target > node.end_position().row {
            continue; // this subtree doesn't cover the line
        }
        if node.kind() == "function_definition" {
            if let Some(name) = function_name_c(node, source) {
                best = Some(name); // a deeper enclosing definition wins (nested fns are rare in C)
            }
        }
        let mut c = node.walk();
        for ch in node.children(&mut c) {
            stack.push(ch);
        }
    }
    best
}

fn function_name_c(func: tree_sitter::Node, source: &str) -> Option<String> {
    // function_definition -> declarator (possibly pointer_/function_declarator) -> identifier
    let decl = func.child_by_field_name("declarator")?;
    fn ident(n: tree_sitter::Node, src: &str) -> Option<String> {
        if matches!(n.kind(), "identifier" | "field_identifier") {
            return n.utf8_text(src.as_bytes()).ok().map(str::to_string);
        }
        let mut c = n.walk();
        for ch in n.children(&mut c) {
            if let Some(name) = ident(ch, src) {
                return Some(name);
            }
        }
        None
    }
    ident(decl, source)
}

fn is_c(file: &str) -> bool {
    let f = file.to_ascii_lowercase();
    f.ends_with(".c") || f.ends_with(".h")
}

/// Map a diagnostic/frame path to a host path under `root`. Diagnostics are usually relative
/// (`histogram.c`), crash frames absolute inside the sandbox (`/work/histogram.c`).
fn resolve(root: &Path, file: &str) -> PathBuf {
    let f = file.strip_prefix("/work/").unwrap_or(file);
    let cand = root.join(f);
    if cand.exists() {
        return cand;
    }
    if let Some(base) = Path::new(file).file_name() {
        return root.join(base);
    }
    cand
}

/// Fill in `Diagnostic::scope` (and any missing user-frame `func`) from the source tree at `root`.
/// Best-effort and side-effect-free on failure — a missing/unparsable file just leaves `scope: None`.
pub fn enrich_scopes(verdict: &mut Verdict, root: &Path) {
    let mut cache: HashMap<String, Option<String>> = HashMap::new();
    let mut source_of = |file: &str| -> Option<String> {
        cache
            .entry(file.to_string())
            .or_insert_with(|| std::fs::read_to_string(resolve(root, file)).ok())
            .clone()
    };

    for d in &mut verdict.diagnostics {
        if d.scope.is_some() {
            continue;
        }
        if let (Some(file), Some(line)) = (d.file.as_deref(), d.line) {
            if is_c(file) {
                if let Some(src) = source_of(file) {
                    d.scope = enclosing_function_c(&src, line);
                }
            }
        }
    }
    if let Some(crash) = verdict.crash.as_mut() {
        for fr in crash.frames.iter_mut().filter(|f| f.user && f.func.is_none()) {
            if let (Some(file), Some(line)) = (fr.file.as_deref(), fr.line) {
                if is_c(file) {
                    if let Some(src) = source_of(file) {
                        fr.func = enclosing_function_c(&src, line);
                    }
                }
            }
        }
    }
}
