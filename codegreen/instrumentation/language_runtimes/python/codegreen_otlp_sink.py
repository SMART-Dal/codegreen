"""OpenTelemetry OTLP/gRPC metric sink for codegreen.Monitor.

Optional dependency: enabled only when the user installs the `[otlp]` extra
(`pip install codegreen[otlp]`). The Monitor builds this sink lazily and fails
loud with the exact install command if dependencies are missing — never
silently no-ops. See `monitor.exporters.otlp.*` in `codegreen/config.json`
for the canonical config schema.

Backpressure: a bounded `queue.Queue(maxsize=queue_size)` decouples the
Monitor's sample loop from OTLP gRPC export latency. `feed_*` is wait-free
via `put_nowait`; a slow/unreachable collector causes drops (counted as
`dropped_samples` / `dropped_annotations`) — never wedges the sample
cadence. This is what keeps the <=1% perturbation budget vs JSONL-only.

Metric naming follows OpenTelemetry semantic conventions where they exist
(`energy.joules`, `power.watts`) and prefixes everything with `codegreen.`:

  codegreen.energy.joules           Counter,   monotonic cumulative joules
  codegreen.power.watts             Gauge,     last-tick wattage
  codegreen.request.energy.joules   Counter,   per-label closed-span joules
  codegreen.request.duration.seconds Histogram, per-label closed-span seconds

Resource attributes attached to every metric: `service.name`, `host.name`,
`process.pid`, `attribution_backend`, `codegreen.version`. Per-metric
attribute: `route` for request-scoped metrics (capped upstream by
`monitor.annotation.max_labels` so OTLP collectors never see unbounded
cardinality — same `__other__` overflow bucket).
"""
from __future__ import annotations

import threading
import warnings as _warnings
from queue import Queue, Empty, Full
from typing import Any, Dict, Optional

OTLP_INSTALL_HINT = "pip install 'codegreen[otlp]'"

try:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    _OTLP_AVAILABLE = True
except ImportError:
    _OTLP_AVAILABLE = False
    MeterProvider = None  # type: ignore[assignment]
    PeriodicExportingMetricReader = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    OTLPMetricExporter = None  # type: ignore[assignment]


# Defer Sink import to avoid circulars during normal module loading.
def _Sink_base():
    from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import Sink
    return Sink


class OTLPMetricSink:
    """OpenTelemetry OTLP/gRPC metric exporter as a codegreen.Monitor Sink.

    Lifecycle:
      __init__ -> bound queue + worker thread + MeterProvider
      feed_*   -> non-blocking put_nowait; dropped events counted
      close()  -> flush worker queue, shutdown OTel MeterProvider, return
                  per-sink summary (dropped_samples, dropped_annotations,
                  exported_samples, exported_annotations, endpoint).
    """

    name = "otlp"

    def __init__(self, cfg: Dict[str, Any], resource: Dict[str, Any]):
        if not _OTLP_AVAILABLE:
            raise RuntimeError(
                f"OTLPMetricSink requires the OpenTelemetry SDK. {OTLP_INSTALL_HINT}"
            )
        self._endpoint = str(cfg.get("endpoint", "http://localhost:4317"))
        self._protocol = str(cfg.get("protocol", "grpc")).lower()
        if self._protocol != "grpc":
            raise ValueError(
                f"monitor.exporters.otlp.protocol={self._protocol!r}: only "
                f"'grpc' is currently supported (HTTP/protobuf deferred to D5+)"
            )
        headers = cfg.get("headers", {}) or {}
        timeout_s = float(cfg.get("timeout_s", 10.0))
        export_interval_ms = int(cfg.get("export_interval_ms", 1000))
        queue_size = int(cfg.get("queue_size", 10000))
        batch_size = int(cfg.get("batch_size", 128))
        if queue_size <= 0:
            raise ValueError("monitor.exporters.otlp.queue_size must be > 0")
        if batch_size <= 0:
            raise ValueError("monitor.exporters.otlp.batch_size must be > 0")
        self._batch_size = batch_size
        self._queue: "Queue[Dict[str, Any]]" = Queue(maxsize=queue_size)
        self._queue_size = queue_size
        self._dropped_samples = 0
        self._dropped_annotations = 0
        self._exported_samples = 0
        self._exported_annotations = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()

        # Build the OTel pipeline.
        resource_attrs = {str(k): _scalar(v) for k, v in resource.items()}
        otel_resource = Resource.create(resource_attrs)
        tls = cfg.get("tls", {}) or {}
        exporter_kwargs: Dict[str, Any] = {
            "endpoint": self._endpoint, "timeout": timeout_s,
        }
        if headers:
            exporter_kwargs["headers"] = tuple((k, str(v)) for k, v in headers.items())
        if tls.get("ca_file"):
            exporter_kwargs["certificate_file"] = str(tls["ca_file"])
        if tls.get("cert_file"):
            exporter_kwargs["client_certificate_file"] = str(tls["cert_file"])
        if tls.get("key_file"):
            exporter_kwargs["client_key_file"] = str(tls["key_file"])
        # insecure: http:// endpoints imply no TLS; gRPC SDK accepts True
        # for the local-collector + dev-loop case.
        if self._endpoint.startswith("http://"):
            exporter_kwargs["insecure"] = True
        self._exporter = OTLPMetricExporter(**exporter_kwargs)
        # Hard cap export_timeout to 2s so an unreachable collector cannot
        # block PeriodicExportingMetricReader.shutdown() longer than that;
        # the worker's own queue absorbs the burst meanwhile.
        export_timeout_ms = min(int(timeout_s * 1000), 2000)
        reader = PeriodicExportingMetricReader(
            exporter=self._exporter,
            export_interval_millis=max(100, export_interval_ms),
            export_timeout_millis=export_timeout_ms,
        )
        self._provider = MeterProvider(resource=otel_resource, metric_readers=[reader])
        # OTel's PeriodicExportingMetricReader creates a non-daemon background
        # thread that can wedge Python interpreter exit if the collector is
        # unreachable (gRPC retry loop). The Monitor's contract is fail-loud,
        # never-block — so we promote the reader's thread to a daemon. The
        # bounded shutdown in close() still drains in-flight exports.
        for t in threading.enumerate():
            if t.name.startswith("OtelPeriodicExportingMetricReader"):
                try:
                    t.daemon = True
                except RuntimeError:
                    pass
        meter = self._provider.get_meter("codegreen.monitor")
        self._joules_total = meter.create_counter(
            "codegreen.energy.joules", unit="J",
            description="Cumulative CPU+DRAM energy since Monitor.start()",
        )
        self._watts_gauge = meter.create_observable_gauge(
            "codegreen.power.watts", unit="W",
            description="Instantaneous power draw at last sample tick",
            callbacks=[self._observe_watts],
        )
        self._req_joules = meter.create_counter(
            "codegreen.request.energy.joules", unit="J",
            description="Per-route closed-span energy",
        )
        self._req_duration = meter.create_histogram(
            "codegreen.request.duration.seconds", unit="s",
            description="Per-route closed-span duration",
        )
        # Last-known sample state for the observable gauge callback.
        self._last_watts = 0.0
        self._last_joules_total = 0.0

        self._worker = threading.Thread(
            target=self._drain_loop, name="codegreen-otlp-sink", daemon=True,
        )
        self._worker.start()

    def feed_sample(self, rec: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(("sample", rec))
        except Full:
            with self._lock:
                self._dropped_samples += 1

    def feed_annotation_start(self, rec: Dict[str, Any]) -> None:
        # No metric emission yet — collectors expect the close event for
        # joules + duration. Tracking starts is left to remote-push (Q1).
        return

    def feed_annotation_end(self, rec: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(("annotation_end", rec))
        except Full:
            with self._lock:
                self._dropped_annotations += 1

    def feed_header(self, rec: Dict[str, Any]) -> None:
        # Header records are not metrics; OTLP collectors don't consume them.
        return

    def feed_aggregate(self, per_label: Dict[str, Dict[str, float]]) -> None:
        # Per-label snapshot at stop(); the per-sample counter+histogram
        # series carries the same totals at higher resolution. No-op here
        # avoids double-counting on the OTLP side.
        return

    def _observe_watts(self, options):
        from opentelemetry.metrics import Observation
        return [Observation(self._last_watts)]

    def _drain_loop(self) -> None:
        while not self._stop.is_set():
            batch = []
            try:
                evt = self._queue.get(timeout=0.5)
            except Empty:
                continue
            batch.append(evt)
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except Empty:
                    break
            self._emit_batch(batch)

    def _emit_batch(self, batch) -> None:
        for kind, rec in batch:
            try:
                if kind == "sample":
                    dj = float(rec.get("joules_delta", 0.0))
                    if dj > 0:
                        self._joules_total.add(dj)
                    self._last_watts = float(rec.get("watts", 0.0))
                    self._last_joules_total = float(rec.get("joules_total", 0.0))
                    with self._lock:
                        self._exported_samples += 1
                elif kind == "annotation_end":
                    route = str(rec.get("name", "__unknown__"))
                    j = float(rec.get("joules", 0.0))
                    dur = float(rec.get("duration_s", 0.0))
                    attrs = {"route": route, "status": str(rec.get("status", "ok"))}
                    if j > 0:
                        self._req_joules.add(j, attributes=attrs)
                    self._req_duration.record(dur, attributes=attrs)
                    with self._lock:
                        self._exported_annotations += 1
            except Exception as e:  # noqa: BLE001
                _warnings.warn(
                    f"codegreen.OTLPMetricSink._emit_batch: dropping {kind!r} "
                    f"after error ({type(e).__name__}: {e})",
                    RuntimeWarning, stacklevel=2,
                )

    def close(self) -> Dict[str, Any]:
        self._stop.set()
        # Drain queue best-effort so end-of-run events make it out.
        drained = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except Empty:
                break
        if drained:
            self._emit_batch(drained)
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
        # Bound shutdown latency hard: a slow / unreachable collector must not
        # wedge Monitor.stop(). MeterProvider.shutdown blocks on a final
        # synchronous export; on a refused endpoint gRPC retries internally
        # for seconds. Run it on a background thread with an explicit join
        # deadline; whatever doesn't drain in 1s is forfeit.
        def _bounded_shutdown() -> None:
            try:
                self._provider.force_flush(timeout_millis=300)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._provider.shutdown(timeout_millis=300)
            except Exception:  # noqa: BLE001
                pass
        t = threading.Thread(target=_bounded_shutdown, daemon=True,
                             name="codegreen-otlp-shutdown")
        t.start()
        t.join(timeout=1.0)
        return {
            "endpoint": self._endpoint,
            "protocol": self._protocol,
            "queue_size": self._queue_size,
            "batch_size": self._batch_size,
            "dropped_samples": self._dropped_samples,
            "dropped_annotations": self._dropped_annotations,
            "exported_samples": self._exported_samples,
            "exported_annotations": self._exported_annotations,
        }


def _scalar(v: Any) -> Any:
    """Resource attribute values must be primitives; coerce defensively."""
    if isinstance(v, (str, bool, int, float)):
        return v
    return str(v)
