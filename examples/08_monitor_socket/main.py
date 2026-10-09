"""08 Request-level energy attribution via the annotation UDS.

Starts an in-process Monitor with a Unix-domain socket listener, runs a
tiny HTTP server with 3 endpoints, hits each endpoint a few times via
`http.client`, and prints per-label energy + p50/p95 latency.

This is the XaBerr-style use case: instrument the web server with a
middleware that opens an annotation span per request; CodeGreen aggregates
the cumulative RAPL energy into per-route buckets. No Flask dependency.
"""
import http.client
import http.server
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import codegreen


HANDLERS = {
    "/light": lambda: sum(range(10_000)),
    "/medium": lambda: sum(i * i for i in range(200_000)),
    "/heavy": lambda: sum(i * i for i in range(2_000_000)),
}


def _send(sock_path: str, op: str, **kwargs) -> dict:
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


class Handler(http.server.BaseHTTPRequestHandler):
    sock_path = ""

    def do_GET(self):
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cg_monitor_sock_") as td:
        sock_path = str(Path(td) / "cg.sock")
        m = codegreen.Monitor(interval_ms=150, listen_socket_path=sock_path).start()
        Handler.sock_path = sock_path
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.2)
            for path in ("/light", "/medium", "/heavy", "/heavy", "/medium"):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                c.request("GET", path); c.getresponse().read(); c.close()
            time.sleep(0.4)
        finally:
            srv.shutdown()
            srv.server_close()
            summary = m.stop()
    per_label = summary.get("per_label", {})
    print(json.dumps({"labels": {k: v for k, v in per_label.items()}}, indent=2))
    print(f"OK: monitor_socket; labels={len(per_label)}; total_j={summary['total_joules']:.3f}; "
          f"requests={sum(v['count'] for v in per_label.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
