"""11 Standalone-monitor + external webapp via the annotation UDS.

This is the production-deployment pattern: `codegreen monitor` runs as an
independent daemon-style process (e.g. systemd unit, sidecar container),
and an already-running web server attaches to it ONLY via the Unix-domain
socket, with a small middleware that opens an annotation span per
request. The monitor and the app are decoupled processes — restart one
without touching the other.

This is closer to XaBerr's deployment (Apache + mod_wsgi + Flask) than
example 08 (which runs both Monitor and the webapp inside one Python
process). Here:

  - Process A: `codegreen monitor --listen-on-socket <sock> -o energy.jsonl
               --quiet --json` (subprocess, sends SIGTERM to stop)
  - Process B: `http.server.ThreadingHTTPServer` with an annotation
               middleware that talks to <sock> via UDS

After the run, the JSONL file is the durable record (interleaved samples
+ annotation_start + annotation_end), and the monitor's JSON summary
carries `per_label` totals + p50/p95 latency per route.

Adapting to Flask / Django / FastAPI / WSGI: replace the
`BaseHTTPRequestHandler.do_GET` shim with the equivalent middleware /
before_request + teardown_request pair. The protocol over the UDS is
identical regardless of framework: one JSON envelope per newline-
terminated message.
"""
import http.client
import http.server
import json
import os
import signal
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
    "/heavy":  lambda: sum(i * i for i in range(2_000_000)),
}


def _send(sock_path: str, op: str, **kwargs) -> dict:
    """One round-trip over the annotation UDS."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall((json.dumps({"op": op, **kwargs}) + "\n").encode())
    resp = b""
    while b"\n" not in resp:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp += chunk
    s.close()
    return json.loads(resp.decode().strip())


class _Handler(http.server.BaseHTTPRequestHandler):
    """Per-request annotation middleware. Frame-agnostic — see module docstring."""
    sock_path = ""

    def do_GET(self):  # noqa: N802 - stdlib API
        path = self.path.split("?", 1)[0]
        if path not in HANDLERS:
            self.send_response(404); self.end_headers(); return
        ack = _send(self.sock_path, "start", name=f"GET {path}")
        tok = ack["token"]
        try:
            result = HANDLERS[path]()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"{result}\n".encode())
        finally:
            _send(self.sock_path, "end", token=tok, status="ok")

    def log_message(self, *a, **kw): pass


def _wait_for_socket(sock_path: str, timeout_s: float = 5.0) -> None:
    """Block until the monitor daemon has bound the UDS, or raise."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if Path(sock_path).exists():
            return
        time.sleep(0.05)
    raise RuntimeError(f"monitor did not bind {sock_path} within {timeout_s}s")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cg_monitor_standalone_") as td:
        sock_path = str(Path(td) / "cg.sock")
        jsonl_path = str(Path(td) / "energy.jsonl")

        # PROCESS A: monitor daemon. No --duration so it runs until SIGTERM.
        # Stdout buffers the JSON summary that gets printed on clean shutdown.
        mon = subprocess.Popen(
            ["codegreen", "monitor", "--listen-on-socket", sock_path,
             "-o", jsonl_path, "--quiet", "--json", "-i", "150"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            _wait_for_socket(sock_path)

            # PROCESS B: tiny webapp + middleware. In production this is
            # Apache+mod_wsgi+Flask; here it's the stdlib equivalent so the
            # example has zero extra deps.
            _Handler.sock_path = sock_path
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()

            try:
                # Simulated traffic. In production this is real curl/wrk/users.
                for path in ("/light", "/medium", "/heavy", "/heavy", "/medium",
                             "/light", "/heavy"):
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    c.request("GET", path); c.getresponse().read(); c.close()
                # Let one final sample tick land after the last request so /heavy
                # spans definitely overlap >=1 sample window.
                time.sleep(0.5)
            finally:
                srv.shutdown()
                srv.server_close()
        finally:
            # Cleanly stop the standalone monitor — same as a `systemctl stop`.
            mon.send_signal(signal.SIGTERM)
            try:
                stdout, _stderr = mon.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                mon.kill()
                stdout, _stderr = mon.communicate()
                raise

        # Parse the monitor's final summary (printed on clean SIGTERM exit).
        summary = json.loads(stdout.decode().strip().splitlines()[-1])
        per_label = summary.get("per_label", {}) or {}

        # The JSONL file is the durable record: post-mortem analysis lives here.
        records = [json.loads(ln) for ln in Path(jsonl_path).read_text().splitlines() if ln]
        n_samples = sum(1 for r in records if r.get("type") == "sample")
        n_starts  = sum(1 for r in records if r.get("type") == "annotation_start")
        n_ends    = sum(1 for r in records if r.get("type") == "annotation_end")

    print(json.dumps({"per_label": per_label}, indent=2))
    print(
        "OK: monitor_socket_standalone; "
        f"labels={len(per_label)}; samples={n_samples}; "
        f"annotation_starts={n_starts}; annotation_ends={n_ends}; "
        f"total_j={summary.get('total_joules', 0.0):.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
