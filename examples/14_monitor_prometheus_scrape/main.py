"""14 Monitor + Prometheus /metrics pull endpoint.

Pattern: `codegreen monitor --exporter prometheus --prometheus-port PORT`
exposes an HTTP /metrics endpoint that Prometheus can scrape. Production
SRE / K8s teams ship every other metric this way; CodeGreen joins the
same fleet pipeline without a sidecar collector.

This example launches `codegreen monitor` as a subprocess, drives 5
HTTP requests through the UDS annotation middleware (mirrors example 11),
scrapes /metrics, and asserts the canonical metric names + per-route
labels landed.

Run:
    python examples/14_monitor_prometheus_scrape/main.py

Skips cleanly when `prometheus_client` is missing:
    SKIP: prometheus_client not installed; pip install codegreen[prometheus]
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
import urllib.request
from pathlib import Path

try:
    import prometheus_client  # noqa: F401
    _PROM_OK = True
except ImportError:
    _PROM_OK = False


HANDLERS = {
    "/light":  lambda: sum(range(10_000)),
    "/medium": lambda: sum(i * i for i in range(200_000)),
    "/heavy":  lambda: sum(i * i for i in range(1_000_000)),
}


def _uds(sock_path, op, **kw):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(sock_path)
    s.sendall((json.dumps({"op": op, **kw}) + "\n").encode())
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
        ack = _uds(self.sock_path, "start", name=f"GET {path}")
        if "token" not in ack:
            self.send_response(500); self.end_headers(); return
        tok = ack["token"]
        try:
            HANDLERS[path]()
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok\n")
        finally:
            _uds(self.sock_path, "end", token=tok, status="ok")

    def log_message(self, *a, **kw): pass


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def _wait(cond, timeout_s, desc):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for {desc} ({timeout_s}s)")


def _parse_prom_text(text):
    """Minimal Prometheus text-format parser. Returns dict[name] -> list[(labels_dict, value)].
    Skips HELP/TYPE lines; accepts simple `name{k="v",k2="v2"} 1.23` lines."""
    out = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if "{" in line:
            name, rest = line.split("{", 1)
            label_blob, _, val = rest.rpartition("}")
            value = val.strip().split()[0]
            labels = {}
            i = 0
            while i < len(label_blob):
                eq = label_blob.find("=", i)
                if eq < 0:
                    break
                key = label_blob[i:eq].strip().strip(",").strip()
                q1 = label_blob.find('"', eq)
                q2 = label_blob.find('"', q1 + 1)
                if q1 < 0 or q2 < 0:
                    break
                labels[key] = label_blob[q1 + 1:q2]
                i = q2 + 1
        else:
            parts = line.split()
            name, value = parts[0], parts[1]
            labels = {}
        try:
            v = float(value)
        except ValueError:
            continue
        out.setdefault(name, []).append((labels, v))
    return out


def _scrape(url, timeout=5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def main() -> int:
    if not _PROM_OK:
        print("SKIP: prometheus_client not installed; pip install codegreen[prometheus]")
        return 0
    prom_port = _free_port()
    with tempfile.TemporaryDirectory(prefix="cg_prom_") as td:
        sock_path = str(Path(td) / "cg.sock")
        jsonl_path = str(Path(td) / "energy.jsonl")
        mon = subprocess.Popen(
            ["codegreen", "monitor", "--listen-on-socket", sock_path,
             "-o", jsonl_path, "--quiet", "--json", "-i", "150",
             "--exporter", "prometheus", "--prometheus-port", str(prom_port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        scrape_url = f"http://127.0.0.1:{prom_port}/metrics"
        health_url = f"http://127.0.0.1:{prom_port}/healthz"
        try:
            _wait(lambda: Path(sock_path).exists(), 5.0, "UDS bind")
            _wait(lambda: _try_scrape(scrape_url), 5.0, "metrics endpoint")
            _Handler.sock_path = sock_path
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            p_port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                for path in ("/light", "/medium", "/heavy", "/medium", "/light"):
                    c = http.client.HTTPConnection("127.0.0.1", p_port, timeout=10)
                    c.request("GET", path); c.getresponse().read(); c.close()
                time.sleep(0.5)
                body = _scrape(scrape_url)
                health = json.loads(_scrape(health_url))
            finally:
                srv.shutdown(); srv.server_close()
        finally:
            mon.send_signal(signal.SIGTERM)
            try:
                stdout, _ = mon.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                mon.kill(); stdout, _ = mon.communicate()
                raise
    parsed = _parse_prom_text(body)
    summary = json.loads(stdout.decode().strip().splitlines()[-1])
    ex = summary.get("exporters", {}).get("prometheus", {})
    canonical = [
        "codegreen_energy_joules_total",
        "codegreen_power_watts",
        "codegreen_request_energy_joules_total",
        "codegreen_request_duration_seconds_count",
        "codegreen_monitor_uptime_seconds",
    ]
    missing = [m for m in canonical if m not in parsed]
    routes = {lbls.get("route") for lbls, _ in parsed.get(
        "codegreen_request_duration_seconds_count", []) if lbls.get("route")}
    dropped = int(ex.get("dropped_samples", 0))
    print(json.dumps({
        "exporter": ex, "health": health, "metrics_seen": len(parsed),
        "canonical_missing": missing, "routes": sorted(routes), "dropped": dropped,
    }, indent=2))
    if missing:
        print(f"FAIL: missing canonical metrics {missing}")
        return 1
    if len(routes) < 3:
        print(f"FAIL: expected >=3 distinct routes, got {sorted(routes)}")
        return 1
    if dropped != 0:
        print(f"FAIL: dropped_samples={dropped}; pull exporter should never drop")
        return 1
    print(
        "OK: monitor_prometheus_scrape; "
        f"metrics_seen={len(parsed)}; routes={len(routes)}; dropped={dropped}"
    )
    return 0


def _try_scrape(url):
    try:
        urllib.request.urlopen(url, timeout=0.5).read()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
