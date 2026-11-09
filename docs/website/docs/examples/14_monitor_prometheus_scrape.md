# 14 - Monitor Prometheus scrape

Expose Monitor metrics on a Prometheus `/metrics` endpoint. The example
starts `codegreen monitor --exporter prometheus` on an ephemeral port,
sends annotated requests, scrapes `/metrics` and `/healthz`, and checks the
metric names and `route` labels.

## Source

[`examples/14_monitor_prometheus_scrape/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/14_monitor_prometheus_scrape/main.py)

```python
--8<-- "examples/14_monitor_prometheus_scrape/main.py"
```

## Run

```bash
pip install 'codegreen[prometheus]'
python examples/14_monitor_prometheus_scrape/main.py
```

Without `prometheus_client` the script prints
`SKIP: prometheus_client not installed; pip install codegreen[prometheus]`
and exits 0.

The script:

1. Starts `codegreen monitor --listen-on-socket <sock> -o <jsonl> --quiet
   --json -i 150 --exporter prometheus --prometheus-port <random>`.
2. Sends 5 annotated HTTP requests (the middleware of
   [example 11](11_monitor_socket_standalone.md)).
3. Scrapes `http://127.0.0.1:<port>/metrics` with `urllib` and a small
   text-format parser, and reads `/healthz`.
4. Stops the monitor and checks the metric names, the resource labels, the
   `route` label and `dropped_samples == 0`.

## Output

From a run on an AMD EPYC host (port varies):

```text
{
  "exporter": {
    "listen_addr": "127.0.0.1",
    "port": 37589,
    "endpoint_metrics": "/metrics",
    "endpoint_health": "/healthz",
    "auth_token_required": false,
    "samples_seen": 7,
    "annotations_seen": 5,
    "distinct_labels": 3,
    "dropped_samples": 0,
    "uptime_s": 1.106
  },
  "health": {
    "status": "healthy",
    "uptime_s": 0.606,
    "samples_seen": 4,
    "annotations_seen": 5
  },
  "metrics_seen": 11,
  "canonical_missing": [],
  "routes": [
    "GET /heavy",
    "GET /light",
    "GET /medium"
  ],
  "dropped": 0
}
OK: monitor_prometheus_scrape; metrics_seen=11; routes=3; dropped=0
```

## With a real Prometheus

```bash
codegreen monitor --exporter prometheus --prometheus-port 9464 \
    -i 250 -o /var/log/codegreen/energy.jsonl --quiet
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: codegreen
    static_configs:
      - targets: ["host-running-codegreen:9464"]
```

The default bind is `127.0.0.1`, so the scraper must run on the same host.
To expose the endpoint, add `--prometheus-listen-addr 0.0.0.0` (a
`RuntimeWarning` records the choice), set
`monitor.exporters.prometheus.auth_token` and the matching `authorization`
block in the scrape config, and restrict the port to the scraper. The
metric catalog, authentication, redaction and histogram buckets are in
[Exporters: Prometheus](../user-guide/continuous-monitoring.md#prometheus).
