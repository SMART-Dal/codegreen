# 14 — Monitor Prometheus /metrics scrape

**Who this is for.** You run a Prometheus-based SRE stack — vanilla Prometheus,
Grafana Agent, Datadog Agent in Prometheus mode, OpenTelemetry Collector with
the Prometheus receiver, or anything else that speaks the standard pull
protocol. You want CodeGreen's energy metrics scraped on the same cadence
and stitched into the same dashboards as every other service metric.

This example stands up `codegreen monitor` with the Prometheus exporter on
an ephemeral port, drives a small synthetic webapp through the UDS
annotation middleware, scrapes `/metrics` with a tiny vendored parser, and
asserts the canonical metric names + per-route labels landed.

## Quick run

```bash
pip install 'codegreen[prometheus]'
python examples/14_monitor_prometheus_scrape/main.py
```

Expected last line on Linux with `prometheus_client` installed:

```text
OK: monitor_prometheus_scrape; metrics_seen=11; routes=3; dropped=0
```

When the optional deps are missing, the script prints
`SKIP: prometheus_client not installed; pip install codegreen[prometheus]`
and exits 0. The test harness accepts both.

## What the example does

1. Launches `codegreen monitor --listen-on-socket <sock> -o <jsonl>
   --quiet --json -i 150 --exporter prometheus --prometheus-port <random>`
   as a subprocess.
2. Drives 5 HTTP requests through a stdlib `ThreadingHTTPServer` plus the
   UDS annotation middleware from example 11.
3. Scrapes `http://127.0.0.1:<port>/metrics` with `urllib.request` and
   parses the Prometheus text format with ~30 lines of vendored code
   (no `prometheus_client` test dependency).
4. Calls `/healthz` for the structured JSON liveness payload.
5. Stops the monitor, asserts the canonical metric names appear with
   `host` / `pid` / `attribution_backend` resource labels plus the
   `route` label on request-scoped metrics, and `dropped_samples == 0`.

## Metric catalog

The Prometheus sink registers the following instruments on a per-Sink
`CollectorRegistry` (NOT the global default — two Monitors on the same
host stay isolated):

| Metric                                       | Kind      | Unit | Labels                                          |
|----------------------------------------------|-----------|------|-------------------------------------------------|
| `codegreen_energy_joules_total`              | Counter   | J    | `host`, `pid`, `attribution_backend`            |
| `codegreen_power_watts`                      | Gauge     | W    | `host`, `pid`, `attribution_backend`            |
| `codegreen_request_energy_joules_total`      | Counter   | J    | + `route`, `status`                             |
| `codegreen_request_duration_seconds`         | Histogram | s    | + `route`, `status`                             |
| `codegreen_monitor_uptime_seconds`           | Gauge     | s    | `host`, `pid`, `attribution_backend`            |
| `codegreen_distinct_labels`                  | Gauge     | -    | `host`, `pid`, `attribution_backend`            |
| `codegreen_overflow_label_count_total`       | Counter   | -    | `host`, `pid`, `attribution_backend`            |
| `codegreen_dropped_samples_total`            | Counter   | -    | + `sink`                                        |

Histogram buckets for `codegreen_request_duration_seconds` are configurable
via `monitor.exporters.prometheus.histogram_buckets_request_duration_seconds`
in `codegreen/config.json` (defaults: 5ms, 10ms, 25ms, 50ms, 100ms, 250ms,
500ms, 1s, 2.5s, 5s, 10s).

## Compliance posture

- **Default bind = `127.0.0.1`** (loopback). Setting `listen_addr` to a
  non-loopback address emits a `RuntimeWarning` at start — the audit log
  shows the operator made an explicit choice.
- **Bearer-token auth** via `monitor.exporters.prometheus.auth_token`. When
  set, both `/metrics` and `/healthz` require an `Authorization: Bearer
  <token>` header; comparison uses `hmac.compare_digest` (constant-time).
- **Cardinality cap** — labels passed to the sink are already capped by
  `monitor.annotation.max_labels`; the `__other__` overflow bucket
  guarantees the Prometheus label-value cardinality is bounded regardless
  of upstream URL-PII explosions.
- **Resource-attribute redaction** — set
  `monitor.exporters.prometheus.redact_resource_attrs` to a list containing
  any of `host`, `pid`, `attribution_backend`; matching labels render as
  `__redacted__` in the exposed metrics while the actual values continue
  to be tracked internally.
- **Pull, not push** — the exporter never makes outbound connections; only
  the scraper reaches in. No accidental data exfiltration when the
  endpoint is firewalled correctly.

## Adapting to a real Prometheus scrape

```yaml
# prometheus.yml
scrape_configs:
  - job_name: codegreen
    metrics_path: /metrics
    static_configs:
      - targets: ["host-running-codegreen:9464"]
    # optional: bearer_token: "..."
```

Run the monitor:

```bash
codegreen monitor --exporter prometheus \
    --prometheus-listen-addr 0.0.0.0 \
    --prometheus-port 9464 \
    -i 250 -o /var/log/codegreen/energy.jsonl
```

For shared environments add an `auth_token` in `codegreen/config.json` and
configure `bearer_token` in the corresponding `scrape_config`. Pair with a
network policy / firewall rule that only allows Prometheus's IP to reach
port 9464.
