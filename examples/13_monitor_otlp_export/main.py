"""13 Monitor + OTLP/gRPC metric exporter.

Pattern: `codegreen monitor --exporter otlp --otlp-endpoint <local>` streams
energy metrics to an OpenTelemetry collector. This example stands up a thin
in-process gRPC server that implements the OTLP MetricsService — the same
wire any production collector (Datadog Agent, Honeycomb, Grafana Agent,
OTel Collector) speaks — and drives 3-route synthetic traffic through the
existing Monitor UDS annotation API. After the run we count the metric
points the collector saw and assert the canonical names landed.

Run:
    python examples/13_monitor_otlp_export/main.py

Skips cleanly when `opentelemetry-*` packages are missing:
    SKIP: opentelemetry-* not installed; pip install codegreen[otlp]
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
from concurrent import futures
from pathlib import Path

try:
    import grpc
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
        ExportMetricsServiceResponse,
    )
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2_grpc import (
        MetricsServiceServicer, add_MetricsServiceServicer_to_server,
    )
    _OTLP_OK = True
except ImportError:
    _OTLP_OK = False


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
            print(f"WARN: ack={ack!r}", flush=True)
            self.send_response(500); self.end_headers(); return
        tok = ack["token"]
        try:
            HANDLERS[path]()
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok\n")
        finally:
            _uds(self.sock_path, "end", token=tok, status="ok")

    def log_message(self, *a, **kw): pass


class _OtlpReceiver(MetricsServiceServicer):
    """Minimal in-process OTLP MetricsService — counts batches + metric names."""

    def __init__(self):
        self.batches = 0
        self.names = set()
        self.routes = set()
        self.resource_attrs = set()
        self._lock = threading.Lock()

    def Export(self, request, context):  # noqa: N802 - gRPC API
        with self._lock:
            self.batches += 1
            for rm in request.resource_metrics:
                for attr in rm.resource.attributes:
                    self.resource_attrs.add(attr.key)
                for sm in rm.scope_metrics:
                    for metric in sm.metrics:
                        self.names.add(metric.name)
                        # Walk every data point's attributes for label cardinality.
                        for fld in ("sum", "gauge", "histogram"):
                            data = getattr(metric, fld, None)
                            if data is None:
                                continue
                            for dp in getattr(data, "data_points", []):
                                for kv in dp.attributes:
                                    if kv.key == "route":
                                        self.routes.add(kv.value.string_value)
        return ExportMetricsServiceResponse()


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


def main() -> int:
    if not _OTLP_OK:
        print("SKIP: opentelemetry-* not installed; pip install codegreen[otlp]")
        return 0
    port = _free_port()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    rcv = _OtlpReceiver()
    add_MetricsServiceServicer_to_server(rcv, server)
    server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    endpoint = f"http://127.0.0.1:{port}"
    try:
        with tempfile.TemporaryDirectory(prefix="cg_otlp_") as td:
            sock_path = str(Path(td) / "cg.sock")
            jsonl_path = str(Path(td) / "energy.jsonl")
            mon = subprocess.Popen(
                ["codegreen", "monitor", "--listen-on-socket", sock_path,
                 "-o", jsonl_path, "--quiet", "--json", "-i", "150",
                 "--exporter", "otlp", "--otlp-endpoint", endpoint],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                _wait(lambda: Path(sock_path).exists(), 5.0, "UDS bind")
                _Handler.sock_path = sock_path
                srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                p_port = srv.server_address[1]
                t = threading.Thread(target=srv.serve_forever, daemon=True)
                t.start()
                try:
                    for path in ("/light", "/medium", "/heavy", "/heavy",
                                 "/medium", "/light", "/heavy"):
                        c = http.client.HTTPConnection("127.0.0.1", p_port, timeout=10)
                        c.request("GET", path); c.getresponse().read(); c.close()
                    time.sleep(1.5)  # give OTLP one export window
                finally:
                    srv.shutdown(); srv.server_close()
            finally:
                mon.send_signal(signal.SIGTERM)
                try:
                    stdout, _ = mon.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    mon.kill(); stdout, _ = mon.communicate()
                    raise
            summary = json.loads(stdout.decode().strip().splitlines()[-1])
    finally:
        server.stop(grace=1.0)

    ex = summary.get("exporters", {}).get("otlp", {})
    n_batches = rcv.batches
    n_names = len(rcv.names)
    print(json.dumps({
        "exporter": ex,
        "collector_batches": n_batches,
        "collector_metric_names": sorted(rcv.names),
        "collector_routes": sorted(rcv.routes),
        "resource_attrs": sorted(rcv.resource_attrs),
    }, indent=2))
    if "codegreen.energy.joules" not in rcv.names:
        print(f"FAIL: missing codegreen.energy.joules in {rcv.names}")
        return 1
    if "service.name" not in rcv.resource_attrs:
        print(f"FAIL: missing service.name in resource attrs {rcv.resource_attrs}")
        return 1
    print(
        "OK: monitor_otlp_export; "
        f"batches={n_batches}; metric_names={n_names}; routes={len(rcv.routes)}; "
        f"exported_samples={ex.get('exported_samples', 0)}; "
        f"exported_annotations={ex.get('exported_annotations', 0)}; "
        f"dropped_samples={ex.get('dropped_samples', 0)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
