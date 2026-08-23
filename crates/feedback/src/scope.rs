//! Best-effort AST scope resolution: the enclosing function of a `(file, line)`, via tree-sitter.
//!
//! This is what makes the delta *semantic* rather than purely positional: two diagnostics are "the
//! same" if they sit in the same function, even after a refactor that moves the whole function far —
//! a line-shift-tolerant match (±3) cannot see that. Populated after distillation by [`enrich_scopes`],
//! which needs the source tree (the parser proper only sees stdout/stderr). Languages: C, C++, Rust,
//! Python, Go.
use crate::Verdict;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Lang {
    C,
    Cpp,
    Rust,
    Python,
    Go,
}

fn lang_of(file: &str) -> Option<Lang> {
    let f = file.rsplit('.').next().unwrap_or("").to_ascii_lowercase();
    match f.as_str() {
        "c" | "h" => Some(Lang::C),
        "cpp" | "cc" | "cxx" | "hpp" | "hh" | "hxx" => Some(Lang::Cpp),
        "rs" => Some(Lang::Rust),
        "py" | "pyi" => Some(Lang::Python),
        "go" => Some(Lang::Go),
        _ => None,
    }
}

fn grammar(lang: Lang) -> (tree_sitter::Language, &'static [&'static str]) {
    match lang {
        Lang::C => (tree_sitter_c::language(), &["function_definition"]),
        Lang::Cpp => (tree_sitter_cpp::language(), &["function_definition"]),
        Lang::Rust => (tree_sitter_rust::language(), &["function_item"]),
        Lang::Python => (tree_sitter_python::language(), &["function_definition"]),
        Lang::Go => (
            tree_sitter_go::language(),
            &["function_declaration", "method_declaration"],
        ),
    }
}

/// Name of the function enclosing 1-based `line` in `source`, if any.
pub fn enclosing_function(lang: Lang, source: &str, line: u32) -> Option<String> {
    let (language, kinds) = grammar(lang);
    let mut parser = tree_sitter::Parser::new();
    parser.set_language(&language).ok()?;
    let tree = parser.parse(source, None)?;
    let target = line.saturating_sub(1) as usize; // tree-sitter rows are 0-based
    let mut best: Option<String> = None;
    let mut stack = vec![tree.root_node()];
    while let Some(node) = stack.pop() {
        if target < node.start_position().row || target > node.end_position().row {
            continue; // this subtree doesn't cover the line
        }
        if kinds.contains(&node.kind()) {
            if let Some(name) = fn_name(lang, node, source) {
                best = Some(name); // a deeper enclosing definition wins (nested fns / methods)
            }
        }
        let mut c = node.walk();
        for ch in node.children(&mut c) {
            stack.push(ch);
        }
    }
    best
}

/// Back-compat shim (C); kept for the existing test.
pub fn enclosing_function_c(source: &str, line: u32) -> Option<String> {
    enclosing_function(Lang::C, source, line)
}

fn fn_name(lang: Lang, node: tree_sitter::Node, src: &str) -> Option<String> {
    match lang {
        // C/C++: function_definition -> declarator -> (through pointer/function_declarator) identifier
        Lang::C | Lang::Cpp => {
            let decl = node.child_by_field_name("declarator")?;
            ident_of(decl, src)
        }
        // Rust/Python/Go: the definition node has a `name` field (an identifier).
        Lang::Rust | Lang::Python | Lang::Go => node
            .child_by_field_name("name")
            .and_then(|n| n.utf8_text(src.as_bytes()).ok())
            .map(str::to_string),
    }
}

fn ident_of(n: tree_sitter::Node, src: &str) -> Option<String> {
    if matches!(
        n.kind(),
        "identifier" | "field_identifier" | "qualified_identifier" | "destructor_name"
    ) {
        return n.utf8_text(src.as_bytes()).ok().map(str::to_string);
    }
    let mut c = n.walk();
    for ch in n.children(&mut c) {
        if let Some(name) = ident_of(ch, src) {
            return Some(name);
        }
    }
    None
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
/// Best-effort and side-effect-free on failure — a missing/unparsable file leaves `scope: None`.
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
            if let Some(lang) = lang_of(file) {
                if let Some(src) = source_of(file) {
                    d.scope = enclosing_function(lang, &src, line);
                }
            }
        }
    }
    if let Some(crash) = verdict.crash.as_mut() {
        for fr in crash
            .frames
            .iter_mut()
            .filter(|f| f.user && f.func.is_none())
        {
            if let (Some(file), Some(line)) = (fr.file.as_deref(), fr.line) {
                if let Some(lang) = lang_of(file) {
                    if let Some(src) = source_of(file) {
                        fr.func = enclosing_function(lang, &src, line);
                    }
                }
            }
        }
    }
}
