//! `sbx` — hermetic run + typed verdict + delta vs. the previous run.
//!
//!   sbx run [--work DIR] [--timeout SECS] [--net] [--json] -- CMD ARGS...
//!   sbx verdict --raw FILE [--exit N] [--signal SIG] [--prev VERDICT.json]
//!   sbx selftest
//!   sbx bench [--n 50]
//!
//! `sbx run` stores the last verdict under `<work>/.sbx/last.json` so the next
//! run in the same work dir automatically prints a delta.

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use feedback::{RenderOpts, RunFacts, Verdict};
use hermit_core::{ExitKind, Spec};
use std::path::PathBuf;
use std::time::{Duration, Instant};

#[derive(Parser)]
#[command(
    name = "sbx",
    version,
    about = "Hermetic sandbox executor with typed, delta-aware feedback for coding agents"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Run a command inside the sandbox and print a verdict (default) or JSON.
    Run {
        /// Host directory mounted read-write at /work (default: cwd).
        #[arg(long)]
        work: Option<PathBuf>,
        /// Wall-clock timeout in seconds.
        #[arg(long, default_value_t = 60)]
        timeout: u64,
        /// Allow network (default: fully isolated).
        #[arg(long)]
        net: bool,
        /// Keep the caller's environment instead of the hermetic profile.
        #[arg(long)]
        inherit_env: bool,
        /// Keep ASLR (default: disabled for reproducible addresses).
        #[arg(long)]
        aslr: bool,
        /// Do not install the seccomp-bpf denylist.
        #[arg(long)]
        no_seccomp: bool,
        /// Leave `lo` DOWN inside the network namespace.
        #[arg(long)]
        no_loopback: bool,
        /// Extra read-only bind (host path, same path inside). Repeatable.
        #[arg(long = "ro")]
        ro: Vec<PathBuf>,
        /// Extra read-write bind (host path, same path inside). Repeatable.
        #[arg(long = "rw")]
        rw: Vec<PathBuf>,
        /// Mount /work as an overlay of this read-only lower dir (e.g. a large repo, mounted without
        /// copying); the agent's edits land in <work>/upper, the lower is untouched. <work> must be
        /// on a Linux filesystem that supports overlayfs (not a /mnt/c drvfs mount).
        #[arg(long)]
        overlay: Option<PathBuf>,
        /// Extra environment variable KEY=VALUE layered over the hermetic profile (PATH may be
        /// extended this way for toolchains bound with --ro). Repeatable.
        #[arg(long = "env")]
        env: Vec<String>,
        /// Print the full machine-readable outcome + verdict as JSON.
        #[arg(long)]
        json: bool,
        /// Print raw stdout/stderr instead of the distilled verdict.
        #[arg(long)]
        raw: bool,
        /// Do not read/write <work>/.sbx/last.json (no delta).
        #[arg(long)]
        no_delta: bool,
        /// Command and arguments.
        #[arg(last = true, required = true)]
        argv: Vec<String>,
    },
    /// Distil a verdict from a saved raw log (no sandbox). Useful for fixtures and hooks.
    Verdict {
        /// Raw log file (stdout+stderr as captured by the harness). "-" reads stdin.
        #[arg(long)]
        raw: PathBuf,
        #[arg(long)]
        exit: Option<i32>,
        #[arg(long)]
        signal: Option<String>,
        /// Previous verdict JSON to diff against (one-shot).
        #[arg(long)]
        prev: Option<PathBuf>,
        /// State directory: reads <state>/last.json as prev, then writes the new verdict,
        /// the raw log (<state>/last.log) and the rendered text there. Used by harness hooks.
        #[arg(long)]
        state: Option<PathBuf>,
        #[arg(long)]
        json: bool,
    },
    /// Run isolation checks inside the sandbox and report what holds on this machine.
    Selftest,
    /// Measure startup latency: sandboxed `/bin/true` vs plain spawn.
    Bench {
        #[arg(long, default_value_t = 30)]
        n: u32,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Run {
            work,
            timeout,
            net,
            inherit_env,
            aslr,
            no_seccomp,
            no_loopback,
            ro,
            rw,
            overlay,
            env,
            json,
            raw,
            no_delta,
            argv,
        } => {
            let work = work.unwrap_or(std::env::current_dir()?);
            let work = std::fs::canonicalize(&work)
                .with_context(|| format!("work dir {}", work.display()))?;
            let mut spec = Spec::new(argv, &work);
            spec.limits.wall = Duration::from_secs(timeout);
            spec.hermetic.no_network = !net;
            spec.hermetic.fixed_env = !inherit_env;
            spec.hermetic.no_aslr = !aslr;
            spec.hermetic.seccomp = !no_seccomp;
            spec.hermetic.loopback = !no_loopback;
            spec.ro_binds = ro;
            spec.rw_binds = rw;
            if let Some(lower) = overlay {
                spec.overlay_lower = Some(
                    std::fs::canonicalize(&lower)
                        .with_context(|| format!("overlay lower {}", lower.display()))?,
                );
            }
            for kv in env {
                if let Some((k, v)) = kv.split_once('=') {
                    spec.env.insert(k.to_string(), v.to_string());
                }
            }
            let outcome = hermit_core::run(&spec)?;
            let facts = facts_of(&outcome);
            let mut verdict = feedback::distill(&outcome.stdout, &outcome.stderr, &facts);
            // AST-enrich each diagnostic with its enclosing function (from the sources in <work>),
            // so the delta can match it across a refactor by scope, not just line number.
            feedback::enrich_scopes(&mut verdict, &work);

            let state_dir = work.join(".sbx");
            let prev: Option<Verdict> = if no_delta {
                None
            } else {
                std::fs::read(state_dir.join("last.json"))
                    .ok()
                    .and_then(|b| serde_json::from_slice(&b).ok())
            };
            let delta = prev.as_ref().map(|p| feedback::diff(p, &verdict));
            if !no_delta {
                let _ = std::fs::create_dir_all(&state_dir);
                let _ = std::fs::write(
                    state_dir.join("last.json"),
                    serde_json::to_vec_pretty(&verdict)?,
                );
                let _ = std::fs::write(state_dir.join("last.stdout"), &outcome.stdout);
                let _ = std::fs::write(state_dir.join("last.stderr"), &outcome.stderr);
            }

            if json {
                #[derive(serde::Serialize)]
                struct Full<'a> {
                    outcome: &'a hermit_core::Outcome,
                    verdict: &'a Verdict,
                    delta: &'a Option<feedback::Delta>,
                }
                println!(
                    "{}",
                    serde_json::to_string_pretty(&Full {
                        outcome: &outcome,
                        verdict: &verdict,
                        delta: &delta
                    })?
                );
            } else if raw {
                use std::io::Write;
                std::io::stdout().write_all(&outcome.stdout)?;
                std::io::stderr().write_all(&outcome.stderr)?;
                eprintln!(
                    "[sbx] {:?} wall={}ms setup={}ms cgroup={}",
                    outcome.exit, outcome.wall_ms, outcome.setup_ms, outcome.applied.cgroup
                );
            } else {
                let mut opts = RenderOpts::default();
                if !no_delta {
                    opts.footer = format!(
                        "(full log: {}/last.stdout, {}/last.stderr)",
                        state_dir.display(),
                        state_dir.display()
                    );
                }
                print!("{}", feedback::render(&verdict, delta.as_ref(), &opts));
            }
            std::process::exit(match outcome.exit {
                ExitKind::Code { code } => code,
                ExitKind::Signal { signal, .. } => 128 + signal,
                ExitKind::Timeout { .. } => 124,
                ExitKind::SetupFailed { .. } => 125,
            });
        }
        Cmd::Verdict {
            raw,
            exit,
            signal,
            prev,
            state,
            json,
        } => {
            let bytes = if raw.as_os_str() == "-" {
                use std::io::Read;
                let mut b = Vec::new();
                std::io::stdin().read_to_end(&mut b)?;
                b
            } else {
                std::fs::read(&raw)?
            };
            let facts = RunFacts {
                exit_code: exit,
                signal,
                ..Default::default()
            };
            let v = feedback::distill(b"", &bytes, &facts);
            let prev_path = prev.or_else(|| state.as_ref().map(|s| s.join("last.json")));
            let prev: Option<Verdict> = prev_path
                .and_then(|p| std::fs::read(p).ok())
                .and_then(|b| serde_json::from_slice(&b).ok());
            let d = prev.as_ref().map(|p| feedback::diff(p, &v));
            let mut opts = RenderOpts::default();
            if let Some(s) = &state {
                let _ = std::fs::create_dir_all(s);
                let _ = std::fs::write(s.join("last.json"), serde_json::to_vec_pretty(&v)?);
                let _ = std::fs::write(s.join("last.log"), &bytes);
                opts.footer = format!("(full log: {})", s.join("last.log").display());
            }
            let text = feedback::render(&v, d.as_ref(), &opts);
            if let Some(s) = &state {
                let _ = std::fs::write(s.join("last.txt"), &text);
            }
            if json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(
                        &serde_json::json!({"verdict": v, "delta": d, "text": text})
                    )?
                );
            } else {
                print!("{text}");
            }
            Ok(())
        }
        Cmd::Selftest => selftest(),
        Cmd::Bench { n } => bench(n),
    }
}

fn facts_of(o: &hermit_core::Outcome) -> RunFacts {
    let mut f = RunFacts {
        wall_ms: Some(o.wall_ms),
        ..Default::default()
    };
    match &o.exit {
        ExitKind::Code { code } => f.exit_code = Some(*code),
        ExitKind::Signal { name, .. } => f.signal = Some(name.clone()),
        ExitKind::Timeout { .. } => f.timed_out = true,
        ExitKind::SetupFailed { message } => f.setup_failed = Some(message.clone()),
    }
    f
}

fn selftest() -> Result<()> {
    let tmp = std::env::temp_dir().join(format!("sbx-selftest-{}", std::process::id()));
    std::fs::create_dir_all(&tmp)?;
    std::fs::write(tmp.join("hello.txt"), "hi\n")?;
    let script = r#"
set -u
echo "pid=$$"
echo "uid=$(id -u) gid=$(id -g)"
echo "host=$(hostname)"
echo "cwd=$(pwd)"
echo "env_path=$PATH"
echo "env_home=$HOME"
echo "env_lc=$LC_ALL tz=$TZ seed=${SBX_SEED:-unset}"
echo "ro_usr=$(touch /usr/sbx-probe 2>/dev/null && echo WRITABLE || echo ro)"
echo "work_rw=$(touch /work/probe && echo rw || echo RO)"
echo "tmp_rw=$(touch /tmp/probe && echo rw || echo RO)"
echo "devnull=$(test -c /dev/null && echo ok || echo MISSING)"
echo "proc_pid1=$(cat /proc/1/comm 2>/dev/null || echo none)"
echo "nprocs=$(ls /proc | grep -c '^[0-9]')"
echo "net=$(cat /sys/class/net/lo/operstate 2>/dev/null || echo none)"
echo "aslr=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null) persona=$(cat /proc/self/personality 2>/dev/null)"
echo "oldroot=$(test -d /.oldroot && echo PRESENT || echo gone)"
echo "hostfs=$(test -e /home && echo VISIBLE || echo hidden)"
echo "nnp=$(grep NoNewPrivs /proc/self/status | tr -s ' ')"
echo "caps=$(grep CapEff /proc/self/status | tr -s ' ')"
( i=0; while [ $i -lt 300 ]; do sleep 30 </dev/null >/dev/null 2>&1 & i=$((i+1)); done ) 2>/dev/null
set -- /proc/[0-9]*
echo "fork_bomb_300=$# procs alive (cap via RLIMIT_NPROC/pids.max; glob count, no fork needed)"
echo "sysfs=$(test -d /sys/class/net && echo mounted_ro || echo absent)"
exit 0
"#;
    let mut spec = Spec::new(vec!["/bin/sh", "-c", script], &tmp);
    spec.limits.pids = Some(64);
    spec.limits.wall = Duration::from_secs(20);
    let o = hermit_core::run(&spec)?;
    println!(
        "exit: {:?}  wall={}ms setup={}ms",
        o.exit, o.wall_ms, o.setup_ms
    );
    println!("applied: {}", serde_json::to_string(&o.applied)?);
    println!("--- stdout ---\n{}", String::from_utf8_lossy(&o.stdout));
    if !o.stderr.is_empty() {
        println!("--- stderr ---\n{}", String::from_utf8_lossy(&o.stderr));
    }
    // Network probe: should fail fast.
    let net_probe = r#"
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import socket, errno, subprocess
def t(name, fn):
    try:
        r = fn(); print(f"{name}: {r}")
    except OSError as e:
        print(f"{name}: {errno.errorcode.get(e.errno, e.errno)}")
t("external 1.1.1.1:80", lambda: (socket.create_connection(("1.1.1.1", 80), timeout=2), "NET_OPEN")[1])
t("loopback 127.0.0.1:9", lambda: (socket.create_connection(("127.0.0.1", 9), timeout=1), "open?!")[1])
def lo_roundtrip():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
    c = socket.create_connection(s.getsockname(), timeout=1); c.close(); s.close(); return "ok"
t("loopback listen+connect", lo_roundtrip)
t("seccomp AF_ALG socket", lambda: (socket.socket(38, socket.SOCK_SEQPACKET, 0), "ALLOWED?!")[1])
t("seccomp unshare -U", lambda: subprocess.run(["unshare", "-U", "true"], capture_output=True, text=True).stderr.strip() or "ALLOWED?!")
t("ifaces", lambda: socket.if_nameindex())
PY
elif [ -x /bin/bash ]; then
  /bin/bash -c '(exec 3<>/dev/tcp/1.1.1.1/80) 2>&1 && echo NET_OPEN || echo net_closed'
else
  echo "no probe tool"
fi
"#;
    let mut spec2 = Spec::new(vec!["/bin/sh", "-c", net_probe], &tmp);
    spec2.limits.wall = Duration::from_secs(5);
    let o2 = hermit_core::run(&spec2)?;
    println!(
        "--- net probe ---\n{}{}",
        String::from_utf8_lossy(&o2.stdout),
        String::from_utf8_lossy(&o2.stderr)
    );
    // Timeout probe.
    let mut spec3 = Spec::new(vec!["/bin/sh", "-c", "sleep 30"], &tmp);
    spec3.limits.wall = Duration::from_millis(300);
    let t = Instant::now();
    let o3 = hermit_core::run(&spec3)?;
    println!(
        "--- timeout probe --- {:?} after {}ms",
        o3.exit,
        t.elapsed().as_millis()
    );
    let _ = std::fs::remove_dir_all(&tmp);
    Ok(())
}

fn bench(n: u32) -> Result<()> {
    let tmp = std::env::temp_dir().join(format!("sbx-bench-{}", std::process::id()));
    std::fs::create_dir_all(&tmp)?;
    let spec = Spec::new(vec!["/bin/true"], &tmp);
    // warm-up
    let _ = hermit_core::run(&spec)?;
    let mut sandboxed = Vec::with_capacity(n as usize);
    let mut setup = Vec::with_capacity(n as usize);
    for _ in 0..n {
        let t = Instant::now();
        let o = hermit_core::run(&spec)?;
        sandboxed.push(t.elapsed().as_secs_f64() * 1000.0);
        setup.push(o.setup_ms as f64);
    }
    let mut plain = Vec::with_capacity(n as usize);
    for _ in 0..n {
        let t = Instant::now();
        let _ = std::process::Command::new("/bin/true").status()?;
        plain.push(t.elapsed().as_secs_f64() * 1000.0);
    }
    let stats = |v: &mut Vec<f64>| {
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let med = v[v.len() / 2];
        let p90 = v[(v.len() as f64 * 0.9) as usize];
        let min = v[0];
        (min, med, p90)
    };
    let (smin, smed, sp90) = stats(&mut sandboxed);
    let (_, setmed, _) = stats(&mut setup);
    let (pmin, pmed, pp90) = stats(&mut plain);
    println!("{{\"n\":{n},\"sandboxed_ms\":{{\"min\":{smin:.2},\"median\":{smed:.2},\"p90\":{sp90:.2}}},\"setup_to_exec_median_ms\":{setmed:.1},\"plain_spawn_ms\":{{\"min\":{pmin:.2},\"median\":{pmed:.2},\"p90\":{pp90:.2}}}}}");
    let _ = std::fs::remove_dir_all(&tmp);
    Ok(())
}
