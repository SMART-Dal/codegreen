"""12 Production-shaped systemd sidecar: monitor as an always-on user unit.

Same wire as example 11 (separate process + UDS annotation socket), but the
Monitor is supervised by user-mode systemd. No root required. This is the
deployment shape that survives terminal close, SSH drop, AND host reboot
(when `loginctl enable-linger <user>` is set, the unit can stay up past
logout too).

Pattern:
  - tempdir/codegreen-monitor-<pid>.service installed to
    ~/.config/systemd/user/, ExecStart points at the local `codegreen`
    binary, --listen-on-socket points inside the tempdir.
  - `systemctl --user daemon-reload && systemctl --user start <unit>`.
  - small stdlib webapp drives 5 requests via the annotation UDS.
  - `systemctl --user stop <unit>` and `systemctl --user disable <unit>`.
  - assert JSONL was written + summary parses.

If `systemctl --user` is unavailable (CI containers, macOS, hosts without
a per-user systemd session bus), the example prints `SKIP: systemd not
available` and exits 0.

Adapting to production: keep the same unit, change the paths.
"""
import http.client
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


HANDLERS = {
    "/light":  lambda: sum(range(10_000)),
    "/medium": lambda: sum(i * i for i in range(200_000)),
    "/heavy":  lambda: sum(i * i for i in range(1_000_000)),
}


def _send(sock_path: str, op: str, **kwargs) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(sock_path)
    s.sendall((json.dumps({"op": op, **kwargs}) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(4096)
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf.decode().strip())


class _Handler(http.server.BaseHTTPRequestHandler):
    sock_path = ""

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in HANDLERS:
            self.send_response(404); self.end_headers(); return
        tok = _send(self.sock_path, "start", name=f"GET {path}")["token"]
        try:
            HANDLERS[path]()
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok\n")
        finally:
            _send(self.sock_path, "end", token=tok, status="ok")

    def log_message(self, *a, **kw): pass


def _systemd_user_available() -> bool:
    """systemctl --user works only when a per-user systemd manager + bus exist."""
    if not shutil.which("systemctl"):
        return False
    if not os.environ.get("XDG_RUNTIME_DIR"):
        return False
    try:
        p = subprocess.run(["systemctl", "--user", "is-system-running"],
                           capture_output=True, text=True, timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        return False
    # Accept "running", "degraded", "starting" — anything that proves the
    # user manager is alive. Reject "offline" or non-zero rc.
    return p.returncode == 0 and p.stdout.strip() in {"running", "degraded", "starting"}


def _wait(condition, timeout_s: float, desc: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {desc} ({timeout_s}s)")


def main() -> int:
    if not _systemd_user_available():
        print("SKIP: systemd not available (systemctl --user / XDG_RUNTIME_DIR missing)")
        return 0
    cg_bin = shutil.which("codegreen")
    if not cg_bin:
        print("SKIP: codegreen CLI not on PATH")
        return 0

    unit_name = f"codegreen-monitor-{os.getpid()}.service"
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / unit_name
    runtime_dir = Path(os.environ["XDG_RUNTIME_DIR"]) / f"cg-sidecar-{os.getpid()}"
    runtime_dir.mkdir(exist_ok=True)
    sock_path = runtime_dir / "cg.sock"
    jsonl_path = runtime_dir / "energy.jsonl"

    unit_text = f"""[Unit]
Description=CodeGreen sidecar (example 12 ephemeral)

[Service]
Type=simple
ExecStart={cg_bin} monitor --listen-on-socket {sock_path} -o {jsonl_path} \\
    --rotate-mb 50 --max-in-memory 0 --max-labels 100 --interval 250 \\
    --quiet --json
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
    unit_path.write_text(unit_text)

    def _systemctl(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["systemctl", "--user", *args],
                              capture_output=True, text=True, timeout=15)

    try:
        rc = _systemctl("daemon-reload")
        if rc.returncode != 0:
            print(f"SKIP: systemctl --user daemon-reload failed: {rc.stderr.strip()}")
            return 0
        rc = _systemctl("start", unit_name)
        if rc.returncode != 0:
            print(f"SKIP: systemctl --user start failed: {rc.stderr.strip()}")
            return 0
        _wait(lambda: sock_path.exists(), 10.0, f"socket {sock_path}")
        time.sleep(0.3)

        _Handler.sock_path = str(sock_path)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            for p in ("/light", "/medium", "/heavy", "/medium", "/light"):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                c.request("GET", p); c.getresponse().read(); c.close()
            time.sleep(0.6)
        finally:
            srv.shutdown(); srv.server_close()

        _systemctl("stop", unit_name)
        _wait(lambda: jsonl_path.exists() and jsonl_path.stat().st_size > 0,
              10.0, f"jsonl flush at {jsonl_path}")

        records = [json.loads(ln) for ln in jsonl_path.read_text().splitlines() if ln.strip()]
        n_samples = sum(1 for r in records if r.get("type") == "sample")
        n_starts = sum(1 for r in records if r.get("type") == "annotation_start")
        n_ends = sum(1 for r in records if r.get("type") == "annotation_end")
        summary = next((r for r in reversed(records) if r.get("type") == "summary"), None)
        if summary is None:
            raise RuntimeError("no summary record in JSONL")
        per_label = summary.get("per_label", {}) or {}
    finally:
        _systemctl("stop", unit_name)
        _systemctl("disable", unit_name)
        try:
            unit_path.unlink()
        except FileNotFoundError:
            pass
        _systemctl("daemon-reload")
        shutil.rmtree(runtime_dir, ignore_errors=True)

    print(
        "OK: monitor_systemd_sidecar; "
        f"labels={len(per_label)}; samples={n_samples}; "
        f"annotation_starts={n_starts}; annotation_ends={n_ends}; "
        f"total_j={summary.get('total_joules', 0.0):.3f}; "
        f"unit={unit_name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
