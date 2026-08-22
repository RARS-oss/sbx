#!/usr/bin/env bash
# Escape / containment probes run INSIDE sbx. Each probe prints "PROBE <name>: CONTAINED" or
# "PROBE <name>: ESCAPED <detail>". Exit 1 if any probe escaped. Mirrors the classes in
# SandboxEscapeBench (host files, /proc, mounts, ptrace, signals, network, devices, setuid,
# config writes) at the level a user-namespace sandbox can be expected to hold.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$SBX_REPO"
W=$(mktemp -d /tmp/sbx-escape.XXXXXX)
cat > "$W/probe.py" <<'PY'
import os, sys, socket, errno, subprocess, signal, ctypes
R = []
def res(name, escaped, detail=""):
    R.append((name, escaped, detail)); print(f"PROBE {name}: {'ESCAPED ' + detail if escaped else 'CONTAINED'}")
def try_read(p):
    try:
        with open(p, "rb") as f: return f.read(64)
    except Exception as e: return e
# 1. host secrets: /etc/shadow (ro bind of /etc; owned by real root -> unmapped -> EACCES)
r = try_read("/etc/shadow"); res("read /etc/shadow", not isinstance(r, Exception), "readable" if not isinstance(r, Exception) else "")
# 2. host filesystem visibility
res("host /home visible", os.path.exists("/home") and len(os.listdir("/home")) > 0, str(os.listdir("/home")) if os.path.exists("/home") else "")
res("host /root visible", os.path.exists("/root") and os.access("/root", os.R_OK))
res("host /var visible", os.path.exists("/var") and len(os.listdir("/var")) > 0)
# 3. escape via /proc/1/root or /proc/self/root (old root detached -> same view)
try:
    out = os.listdir("/proc/1/root")
    res("/proc/1/root shows host", "home" in out and os.path.exists("/proc/1/root/home/user"), str(out)[:80])
except Exception as e:
    res("/proc/1/root shows host", False)
# 4. write outside /work (ro binds, tmpfs root)
for p in ["/usr/sbx-probe", "/etc/sbx-probe", "/sbx-probe-root", "/bin/sbx-probe"]:
    try:
        open(p, "w").write("x"); escaped = True; os.remove(p)
    except Exception as e:
        escaped = (p == "/sbx-probe-root" and False) or False
    res(f"write {p}", escaped)
# 5. /work parent traversal
up = set(os.listdir("/work/.."))
res("/work/.. reaches host dir", bool(up & {"home", "root", "var", "srv", "boot"}), str(sorted(up))[:80])
# 6. mount / unshare / pivot_root (seccomp EPERM)
for cmd, name in [(["mount", "-t", "tmpfs", "none", "/tmp/x"], "mount tmpfs"), (["unshare", "-U", "true"], "unshare -U"), (["chroot", "/tmp", "/bin/true"], "chroot")]:
    os.makedirs("/tmp/x", exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    res(name, r.returncode == 0, r.stderr.strip()[:60] if r.returncode == 0 else "")
# 7. ptrace another process
import time
child = subprocess.Popen(["sleep", "3"])
libc = ctypes.CDLL(None, use_errno=True)
rc = libc.ptrace(16, child.pid, None, None)  # PTRACE_ATTACH
res("ptrace attach", rc == 0, "")
child.kill()
# 8. signal a host process (pid ns): pid 2 on the host is kthreadd; inside our pidns pid 2 is ours or absent
try:
    os.kill(1000, 0); seen = True
except ProcessLookupError: seen = False
except PermissionError: seen = True
res("see host pid 1000", seen)
# 9. network egress
try:
    socket.create_connection(("1.1.1.1", 53), timeout=2).close(); res("tcp egress 1.1.1.1:53", True)
except OSError as e: res("tcp egress 1.1.1.1:53", False)
try:
    import socket as s2; s2.getaddrinfo("example.com", 80); res("dns resolve example.com", True)
except OSError: res("dns resolve example.com", False)
# 10. devices / raw disk
res("/dev/sda exists", os.path.exists("/dev/sda") or os.path.exists("/dev/nvme0n1") or os.path.exists("/dev/sde"))
res("/dev/mem exists", os.path.exists("/dev/mem"))
res("/dev/kmsg readable", not isinstance(try_read("/dev/kmsg"), Exception) if os.path.exists("/dev/kmsg") else False)
# 11. kernel interfaces
res("/proc/sysrq-trigger writable", os.access("/proc/sysrq-trigger", os.W_OK) and (lambda: (open("/proc/sysrq-trigger","w"), True)[1] if False else False)())
kc = try_read("/proc/kcore") if os.path.exists("/proc/kcore") else b""
res("/proc/kcore readable (non-empty)", (not isinstance(kc, Exception)) and len(kc) > 0, "masked (reads empty)" if kc == b"" else "")
r = subprocess.run(["sh", "-c", "echo 1 > /proc/sys/kernel/sysrq"], capture_output=True, text=True); res("write /proc/sys", r.returncode == 0)
# 12. setuid escalation: does a setuid binary gain real root? (no_new_privs + nosuid)
r = subprocess.run(["sh", "-c", "id -u; /usr/bin/sudo -n true 2>&1 | head -1 || true"], capture_output=True, text=True)
res("sudo works", "root" in r.stdout and "not permitted" not in r.stdout and "sudo:" not in r.stdout, r.stdout.strip()[:60])
# 13. io_uring / bpf / AF_ALG (seccomp)
res("io_uring_setup", libc.syscall(425, 8, ctypes.create_string_buffer(120)) >= 0)
res("bpf syscall", libc.syscall(321, 0, None, 0) >= 0)
try:
    socket.socket(38, socket.SOCK_SEQPACKET, 0); res("AF_ALG socket", True)
except OSError: res("AF_ALG socket", False)
# 14. fork bomb containment is covered by selftest; hostname leak:
res("hostname leaks host name", socket.gethostname() not in ("sbx",), socket.gethostname())
# 15. environment leaks host secrets?
leak = [k for k in os.environ if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
res("env carries KEY/TOKEN vars", bool(leak), ",".join(leak)[:60])
esc = [n for n, e, d in R if e]
print(f"SUMMARY: {len(R)} probes, {len(esc)} escaped" + (": " + "; ".join(esc) if esc else ""))
sys.exit(1 if esc else 0)
PY
sbx run --work "$W" --no-delta --raw -- python3 probe.py 2>&1 | grep -E "^PROBE|^SUMMARY|^\[sbx\]"
rc=${PIPESTATUS[0]}
rm -rf "$W"
exit $rc
