"""Prometheus pull-endpoint metric sink for codegreen.Monitor.

Optional dependency: enabled only when the user installs the `[prometheus]`
extra (`pip install codegreen[prometheus]`). Missing deps fail loud at
`Monitor.start()` — never silently no-op. See `monitor.exporters.prometheus.*`
in `codegreen/config.json` for the canonical config schema.

Design (vs OTLP D4 push pipeline):
  * NO worker thread + bounded queue. prometheus_client Counter/Gauge/Histogram
    are internally thread-safe (atomic increments + per-metric locks), so the
    Monitor's `feed_*` methods mutate them DIRECTLY on the sample-loop /
    annotation-listener threads.
  * A separate daemon HTTP server thread serves `/metrics` (and `/healthz`)
    by walking the per-Sink CollectorRegistry — a pure read of the same
    counters, no copy. Backpressure is N/A: Prometheus pull means the
    scraper controls the cadence; codegreen never blocks waiting on it.
  * Per-Sink `CollectorRegistry` (NOT the global default) so two Monitors on
    one host don't collide on metric names.

Compliance posture:
  * Default bind = `127.0.0.1` (loopback). Non-loopback bind emits a
    `RuntimeWarning` at start so the choice is auditable.
  * Optional bearer-token auth via `monitor.exporters.prometheus.auth_token`;
    comparison via `hmac.compare_digest` (timing-safe). Applies to every path
    except the health endpoint, which stays open for liveness probes.
  * Resource-attribute redaction via `monitor.exporters.prometheus.redact_resource_attrs`
    strips `host` / `pid` / `attribution_backend` from the labels emitted on
    metrics — useful for shared / regulated environments.
  * Label cardinality is bounded UPSTREAM by `monitor.annotation.max_labels`
    (overflow rolls into `__other__`); the sink never sees uncapped labels.
"""
from __future__ import annotations

import hmac
import http.server
import json
import threading
import time
import warnings as _warnings
from typing import Any, Dict, List, Optional

PROMETHEUS_INSTALL_HINT = "pip install 'codegreen[prometheus]'"

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    from prometheus_client.core import CollectorRegistry
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    CollectorRegistry = None  # type: ignore[assignment]
    generate_latest = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


_REDACT_VALUE = "__redacted__"


class PrometheusSink:
    """Prometheus pull exporter as a codegreen.Monitor Sink.

    Lifecycle:
      __init__  -> CollectorRegistry + metric instruments + ThreadingHTTPServer
                   bound on `listen_addr:port` (loopback default).
      feed_*    -> mutate counters/gauges on the caller's thread; cheap
                   (prometheus_client uses atomic increments under the hood).
      close()   -> shutdown the HTTP server + return per-sink summary
                   (uptime, samples_seen, dropped_samples=0 by construction
                   since pull has no producer-side backpressure).
    """

    name = "prometheus"

    def __init__(self, cfg: Dict[str, Any], resource: Dict[str, Any]):
        if not _PROM_AVAILABLE:
            raise RuntimeError(
                f"PrometheusSink requires the prometheus_client package. "
                f"{PROMETHEUS_INSTALL_HINT}"
            )
        self._listen_addr = str(cfg.get("listen_addr", "127.0.0.1"))
        self._port = int(cfg.get("port", 9464))
        self._endpoint_metrics = str(cfg.get("endpoint_metrics", "/metrics"))
        self._endpoint_health = str(cfg.get("endpoint_health", "/healthz"))
        self._auth_token = str(cfg.get("auth_token", "") or "")
        buckets = cfg.get(
            "histogram_buckets_request_duration_seconds",
            [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        )
        self._buckets = tuple(float(b) for b in buckets)
        redact = cfg.get("redact_resource_attrs", []) or []
        self._redact = {str(r).lower() for r in redact}
        if self._listen_addr not in ("127.0.0.1", "localhost", "::1"):
            _warnings.warn(
                f"codegreen.PrometheusSink: listen_addr={self._listen_addr!r} is "
                f"non-loopback; the /metrics endpoint will be reachable from the "
                f"network. Set monitor.exporters.prometheus.auth_token for "
                f"compliance in shared environments.",
                RuntimeWarning, stacklevel=2,
            )

        self._registry = CollectorRegistry(auto_describe=False)
        host = str(resource.get("host.name", "") or "")
        pid = str(resource.get("process.pid", "") or "")
        backend = str(resource.get("attribution_backend", "host") or "host")
        self._resource_labels: Dict[str, str] = {
            "host": _REDACT_VALUE if "host" in self._redact else host,
            "pid": _REDACT_VALUE if "pid" in self._redact else pid,
            "attribution_backend": (
                _REDACT_VALUE if "attribution_backend" in self._redact else backend
            ),
        }

        common = ["host", "pid", "attribution_backend"]
        req = common + ["route", "status"]
        sink_lbl = common + ["sink"]
        self._joules_total = Counter(
            "codegreen_energy_joules_total",
            "Cumulative CPU+DRAM energy since Monitor.start() (J).",
            common, registry=self._registry,
        )
        self._power_watts = Gauge(
            "codegreen_power_watts",
            "Instantaneous power draw at last sample tick (W).",
            common, registry=self._registry,
        )
        self._req_joules = Counter(
            "codegreen_request_energy_joules_total",
            "Per-route closed-span energy (J).",
            req, registry=self._registry,
        )
        self._req_duration = Histogram(
            "codegreen_request_duration_seconds",
            "Per-route closed-span duration (s).",
            req, registry=self._registry, buckets=self._buckets,
        )
        self._dropped_samples = Counter(
            "codegreen_dropped_samples_total",
            "Samples dropped due to sink backpressure (per sink name).",
            sink_lbl, registry=self._registry,
        )
        self._uptime_gauge = Gauge(
            "codegreen_monitor_uptime_seconds",
            "Seconds since Monitor.start().",
            common, registry=self._registry,
        )
        self._distinct_labels = Gauge(
            "codegreen_distinct_labels",
            "Distinct annotation labels currently tracked (cardinality watch).",
            common, registry=self._registry,
        )
        self._overflow_labels = Counter(
            "codegreen_overflow_label_count_total",
            "Annotation labels collapsed into __other__ due to max_labels cap.",
            common, registry=self._registry,
        )

        self._t0 = time.monotonic()
        self._samples_seen = 0
        self._annotations_seen = 0
        self._overflow_key = "__other__"
        self._aux_lock = threading.Lock()
        self._distinct_label_set: set = set()

        self._server: Optional[http.server.ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._start_http_server()

    # ------------------------------------------------------------------ HTTP

    def _start_http_server(self) -> None:
        sink = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def _check_auth(self) -> bool:
                if not sink._auth_token:
                    return True
                hdr = self.headers.get("Authorization", "")
                if not hdr.startswith("Bearer "):
                    return False
                presented = hdr[len("Bearer "):].strip()
                return hmac.compare_digest(presented, sink._auth_token)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                if path != sink._endpoint_health and not self._check_auth():
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Bearer")
                    self.end_headers()
                    self.wfile.write(b'{"error":"unauthorized"}')
                    return
                if path == sink._endpoint_metrics:
                    sink._uptime_gauge.labels(**sink._resource_labels).set(
                        time.monotonic() - sink._t0
                    )
                    body = generate_latest(sink._registry)
                    self.send_response(200)
                    self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif path == sink._endpoint_health:
                    payload = json.dumps({
                        "status": "healthy",
                        "uptime_s": round(time.monotonic() - sink._t0, 3),
                        "samples_seen": sink._samples_seen,
                        "annotations_seen": sink._annotations_seen,
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a, **kw):  # silence default stderr log
                return

        try:
            self._server = http.server.ThreadingHTTPServer(
                (self._listen_addr, self._port), _Handler,
            )
        except OSError as e:
            raise RuntimeError(
                f"PrometheusSink: cannot bind {self._listen_addr}:{self._port} ({e})"
            ) from e
        self._port = self._server.server_address[1]  # capture ephemeral port
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="codegreen-prometheus-http", daemon=True,
        )
        self._server_thread.start()

    # ----------------------------------------------------------------- Sink

    def feed_header(self, rec: Dict[str, Any]) -> None:
        return

    def feed_sample(self, rec: Dict[str, Any]) -> None:
        dj = float(rec.get("joules_delta", 0.0))
        if dj > 0:
            self._joules_total.labels(**self._resource_labels).inc(dj)
        self._power_watts.labels(**self._resource_labels).set(
            float(rec.get("watts", 0.0))
        )
        self._samples_seen += 1

    def feed_annotation_start(self, rec: Dict[str, Any]) -> None:
        name = str(rec.get("name", "__unknown__"))
        with self._aux_lock:
            if name == self._overflow_key:
                self._overflow_labels.labels(**self._resource_labels).inc()
            self._distinct_label_set.add(name)
            self._distinct_labels.labels(**self._resource_labels).set(
                len(self._distinct_label_set)
            )

    def feed_annotation_end(self, rec: Dict[str, Any]) -> None:
        route = str(rec.get("name", "__unknown__"))
        status = str(rec.get("status", "ok"))
        j = max(0.0, float(rec.get("joules", 0.0)))
        dur = float(rec.get("duration_s", 0.0))
        attrs = dict(self._resource_labels, route=route, status=status)
        # Always call inc() so the series is registered even when a span
        # captured zero joules (short-lived requests under coarse sampling).
        # Counter.inc(0) is a no-op on the value but emits the labelset.
        self._req_joules.labels(**attrs).inc(j)
        self._req_duration.labels(**attrs).observe(dur)
        self._annotations_seen += 1

    def feed_aggregate(self, per_label: Dict[str, Dict[str, float]]) -> None:
        return

    def close(self) -> Dict[str, Any]:
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:  # noqa: BLE001
                pass
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)
        return {
            "listen_addr": self._listen_addr,
            "port": self._port,
            "endpoint_metrics": self._endpoint_metrics,
            "endpoint_health": self._endpoint_health,
            "auth_token_required": bool(self._auth_token),
            "samples_seen": self._samples_seen,
            "annotations_seen": self._annotations_seen,
            "distinct_labels": len(self._distinct_label_set),
            "dropped_samples": 0,
            "uptime_s": round(time.monotonic() - self._t0, 3),
        }
