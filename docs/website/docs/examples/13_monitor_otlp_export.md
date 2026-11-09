# 13 - Monitor OTLP export

Send Monitor metrics to an OpenTelemetry collector over OTLP/gRPC. The
example starts a minimal in-process OTLP/gRPC receiver, points
`codegreen monitor --exporter otlp` at it, and checks which metrics,
routes and resource attributes arrive.

## Source

[`examples/13_monitor_otlp_export/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/13_monitor_otlp_export/main.py)

```python
--8<-- "examples/13_monitor_otlp_export/main.py"
```

## Run

```bash
pip install 'codegreen[otlp]'
python examples/13_monitor_otlp_export/main.py
```

Without the OpenTelemetry packages the script prints
`SKIP: opentelemetry-* not installed; pip install codegreen[otlp]` and
exits 0.

The script:

1. Binds a gRPC `MetricsService` receiver on `127.0.0.1:<random port>`.
2. Starts `codegreen monitor --listen-on-socket <sock> -o <jsonl> --quiet
   --json -i 150 --exporter otlp --otlp-endpoint http://127.0.0.1:<port>`.
3. Sends 7 annotated HTTP requests (the middleware of
   [example 11](11_monitor_socket_standalone.md)).
4. Stops the monitor and prints the exporter summary and what the receiver
   recorded.

## Output

From a run on an AMD EPYC host (endpoint port varies):

```text
{
  "exporter": {
    "endpoint": "http://127.0.0.1:51963",
    "protocol": "grpc",
    "queue_size": 10000,
    "batch_size": 128,
    "dropped_samples": 0,
    "dropped_annotations": 0,
    "exported_samples": 15,
    "exported_annotations": 7
  },
  "collector_batches": 4,
  "collector_metric_names": [
    "codegreen.energy.joules",
    "codegreen.power.watts",
    "codegreen.request.duration.seconds",
    "codegreen.request.energy.joules"
  ],
  "collector_routes": [
    "GET /heavy",
    "GET /light",
    "GET /medium"
  ],
  "resource_attrs": [
    "attribution_backend",
    "codegreen.version",
    "host.name",
    "process.pid",
    "service.instance.id",
    "service.name",
    "telemetry.sdk.language",
    "telemetry.sdk.name",
    "telemetry.sdk.version"
  ]
}
OK: monitor_otlp_export; batches=4; metric_names=4; routes=3; exported_samples=15; exported_annotations=7; dropped_samples=0
```

`service.instance.id` and the `telemetry.sdk.*` attributes come from the
OpenTelemetry SDK; the others from CodeGreen.

## With a real collector

```bash
codegreen monitor --exporter otlp \
    --otlp-endpoint http://otel-collector.observability.svc:4317 \
    -i 250 -o /var/log/codegreen/energy.jsonl --quiet
```

The metric catalog, the configuration keys (headers, TLS files, queue) and
the drop policy are in
[Exporters: OTLP](../user-guide/continuous-monitoring.md#otlp).
