use std::io::{self, BufRead};

/// Maximum of every window of `k` consecutive values; empty if fewer than `k` values.
fn sliding_max(values: &[i64], k: usize) -> Vec<i64> {
    let mut out = Vec::new();
    if k == 0 || values.len() < k {
        return out;
    }
    for start in 0..=values.len() - k + 1 {
        let mut m = values[start];
        for i in start..start + k {
            if values[i] > m {
                m = values[i];
            }
        }
        out.push(m);
    }
    out
}

fn main() {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    let k: usize = match lines.next() {
        Some(Ok(l)) => l.trim().parse().unwrap_or(0),
        _ => return,
    };
    let values: Vec<i64> = lines
        .filter_map(|l| l.ok())
        .filter_map(|l| l.trim().parse().ok())
        .collect();
    for m in sliding_max(&values, k) {
        println!("{m}");
    }
}
