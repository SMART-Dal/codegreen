# 13 — Monitor OTLP/gRPC metric export

**Who this is for.** You run a SaaS / Kubernetes / MLOps stack and consume
all telemetry through OpenTelemetry: Datadog, Honeycomb, Grafana Cloud,
Lightstep, New Relic, or a vendor OTel Collector. You want CodeGreen's
energy metrics to land at the same backend, with the same resource
attributes and label conventions as every other metric.

This example stands up a thin in-process OTLP/gRPC receiver — the exact
wire any production collector speaks — and pipes `codegreen monitor`
metrics into it. The receiver counts the OTLP batches and asserts the
canonical metric names + resource attributes landed.

## Quick run

```bash
pip install 'codegreen[otlp]'
python examples/13_monitor_otlp_export/main.py
```

Expected last line on Linux with `opentelemetry-*` installed:

```text
OK: monitor_otlp_export; batches=4; metric_names=5; routes=3; exported_samples=14; exported_annotations=7; dropped_samples=0
```

When the optional deps are missing, the script prints
`SKIP: opentelemetry-* not installed; pip install codegreen[otlp]` and
exits 0. The test harness accepts both.

## What the example does

1. Binds an in-process gRPC server on `127.0.0.1:<random>` implementing
   `opentelemetry.proto.collector.metrics.v1.MetricsService` — the same
   service the production OTel Collector exposes.
2. Launches `codegreen monitor --listen-on-socket <sock> -o <jsonl>
   --quiet --json -i 150 --exporter otlp --otlp-endpoint
   http://127.0.0.1:<port>` as a subprocess.
3. Drives 7 HTTP requests through a stdlib `ThreadingHTTPServer` plus the
   UDS annotation middleware from example 11.
4. Stops the monitor, parses the JSON summary, walks the collector's
   recorded protobuf batches, prints the metric names + label routes +
   resource attributes seen.
5. Asserts `codegreen.energy.joules` and the canonical resource attrs
   (`service.name`, `host.name`, `process.pid`) landed at the collector.

## Metric catalog

The OTLP sink exports the following instruments under the meter name
`codegreen.monitor`:

| Metric                                | Kind             | Unit | Per-sample? | Per-annotation? |
|---------------------------------------|------------------|------|-------------|-----------------|
| `codegreen.energy.joules`             | Counter          | J    | yes (delta) | no              |
| `codegreen.power.watts`               | Observable gauge | W    | yes         | no              |
| `codegreen.request.energy.joules`     | Counter          | J    | no          | yes (close)     |
| `codegreen.request.duration.seconds`  | Histogram        | s    | no          | yes (close)     |

Resource attributes on every export:

- `service.name = codegreen-monitor`
- `host.name = <gethostname>`
- `process.pid = <pid>` (set to `--pid` when present, else the monitor's own pid)
- `attribution_backend = cgroup_v2|cgroup_v1|cpu_percent|host`
- `codegreen.version = <pkg_version>`

Per-metric attribute (request-scoped metrics only):

- `route = <annotation name>` (cardinality bounded by `--max-labels`;
  overflow rolls into `__other__`)
- `status = ok|error`

## Backpressure semantics

The OTLP sink owns a bounded `queue.Queue(maxsize=queue_size)`. A
slow/unreachable collector causes the queue to fill and new events are
dropped at the producer side (counted as `dropped_samples` /
`dropped_annotations`). The monitor's sample loop is wait-free: it never
blocks on the OTLP path. The per-sink summary in the Monitor's final JSON
makes the drop rate observable.

## Adapting to a real OTel Collector

Replace the in-process receiver with your collector's endpoint:

```bash
codegreen monitor --exporter otlp \
    --otlp-endpoint http://otel-collector.observability.svc:4317 \
    -i 250 -o /var/log/codegreen/energy.jsonl
```

Pass headers / TLS material via `codegreen/config.json` under
`monitor.exporters.otlp.headers` / `monitor.exporters.otlp.tls.*`, or via
the standard OTel env vars `OTEL_EXPORTER_OTLP_HEADERS` and
`OTEL_EXPORTER_OTLP_CERTIFICATE` (consumed by the underlying
`opentelemetry-exporter-otlp-proto-grpc` package).
