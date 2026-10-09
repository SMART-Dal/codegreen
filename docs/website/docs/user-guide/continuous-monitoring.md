# Continuous Monitoring

`codegreen monitor` (CLI) and `codegreen.Monitor` (Python) **continuously
sample host energy** without launching a workload. Use them when:

- the process you care about is already running (Apache, gunicorn, a
  background daemon),
- you cannot edit the source to embed a Session,
- you want per-request energy attribution in a web framework.

## When to use Monitor vs Session vs `run`

| Use case | Tool | Why |
|---|---|---|
| Bracket a region inside a Python script | [Session](../api/python.md#manual-api-codegreensession) | In-process, structured output |
| Bracket an unmodified shell command | [`codegreen run`](cli-reference.md#run) | N-run stats, `--budget` gating |
| Already-running daemon, no source access | **Monitor** | External, non-invasive |
| Per-HTTP-request energy in a web app | **Monitor + annotate_request** | UDS annotation channel |

## CLI

```bash
codegreen monitor [OPTIONS]
```

| Option | Description |
|---|---|
| `-d, --duration FLOAT` | Stop after N seconds (default: run until Ctrl-C) |
| `-i, --interval INTEGER` | Sample period in ms (config floor enforced; min 50 ms) |
| `-p, --pid INTEGER` | Attribute energy to this process via CPU share |
| `-o, --output PATH` | Stream samples as JSON-lines to this file |
| `--rotate-mb INTEGER` | Rotate JSONL when it exceeds N MB (0 = disabled) |
| `--max-in-memory INTEGER` | Bound in-memory sample deque (0 = drop when `-o` set) |
| `--max-labels INTEGER` | Cap distinct annotation labels; overflow rolls into `__other__` (0 = unlimited; default 1000) |
| `--listen-on-socket TEXT` | Bind a UDS for request-annotation events |
| `--attribution-mode TEXT` | `auto` (default), `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `--exporter TEXT` | Enable a telemetry exporter sink (repeatable). Known: `otlp`, `prometheus`. See [Exporters](#exporters). |
| `--otlp-endpoint TEXT` | OTLP/gRPC collector endpoint (requires `--exporter otlp`) |
| `--prometheus-port INTEGER` | HTTP `/metrics` port (requires `--exporter prometheus`; default from config, 9464) |
| `--prometheus-listen-addr TEXT` | HTTP bind address (requires `--exporter prometheus`; default `127.0.0.1`; non-loopback emits a `RuntimeWarning`) |
| `--json` | Print final summary as JSON |
| `-q, --quiet` | Suppress live sample output |

### Common invocations

```bash
# 30-second host sample at default interval
codegreen monitor -d 30

# 1Hz sampling for an hour, JSONL output
codegreen monitor -i 1000 -d 3600 -o energy.jsonl

# Attribute to a running web server
codegreen monitor --pid $(pgrep -f gunicorn | head -1) -d 600

# Per-request UDS attribution (see annotation section below)
codegreen monitor --listen-on-socket /tmp/cg.sock -o requests.jsonl
```

## Python API

```python
import codegreen

m = codegreen.Monitor(interval_ms=200).start()
# ... your service runs / your test executes ...
summary = m.stop()
print(summary["total_joules"], summary["mean_watts"])
```

Constructor parameters:

| Param | Default | Notes |
|---|---|---|
| `interval_ms` | `200` | Sample period; minimum 50 ms (`ValueError` below) |
| `duration_s` | `None` | Stop after N seconds; `None` = manual `.stop()` |
| `pid` | `None` | PID to attribute (requires psutil) |
| `attribution_mode` | `"auto"` | `auto`, `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `output_path` | `None` | Stream samples as JSON-lines |
| `rotate_mb` | `0` | Rotate output file when it exceeds N MB |
| `max_in_memory` | `1000` | Bound the in-memory ring (0 = drop when streaming) |
| `max_labels` | `1000` | Cap distinct annotation labels; overflow rolls into `__other__` (0 = unlimited) |
| `listen_socket_path` | `None` | Bind UDS for `annotate_request` events |

See the [Python API reference](../api/python.md#codegreenmonitor) for the
full schema of each sample record and the `stop()` summary.

## Per-PID attribution

When `--pid` is set, every sample carries an extra share field computed
from a backend selected at `start()`:

| Backend | Source | Best for |
|---|---|---|
| `cgroup_v2` (preferred) | `cpu.stat:usage_usec` in the unified cgroup | Linux 5.x+ services under any contention |
| `cgroup_v1` | `cpuacct.usage` (nanoseconds) | Legacy Linux |
| `cpu_percent` | psutil `proc.cpu_percent() / (100 * ncores)` | Last resort, all platforms |

The chosen backend appears as `attribution_backend` on every sample header
and on the summary record. Override with `--attribution-mode` if you want
to compare backends side-by-side; otherwise `auto` picks the best
available.

!!! warning "cgroup_v2 vs cpu_percent can diverge by 100x"
    On heavily-loaded multi-core hosts the two backends can disagree by
    **two orders of magnitude** on the same workload. A single-threaded
    burner pinned to one core of a 64-core host:

    - `cgroup_v2`: ~100% of one core -> ~1.6% of system -> ~1.6% of RAPL J
    - `cpu_percent`: ~1.6% reported, **but normalised again** by some
      consumers -> ~0.025% in their pipeline -> ~125x undercount.

    Always check `attribution_backend` before trusting the per-PID
    Joules. The full forensic on this divergence is in the
    [07 - Monitor PID example](../examples/07_monitor_pid.md).

## Per-request attribution

For web servers, run one Monitor with `--listen-on-socket` and instrument
each request with `codegreen.annotate_request`. The Monitor receives
`start` / `end` events over a Unix-domain socket and aggregates
**per-label** energy + p50/p95 latency.

### Flask middleware recipe

```python
from flask import Flask, g, request
import codegreen

app = Flask(__name__)

@app.before_request
def _cg_start():
    g._cg = codegreen.annotate_request(
        f"{request.method} {request.path}",
        socket_path="/tmp/cg.sock",
    ).__enter__()

@app.teardown_request
def _cg_end(exc):
    g._cg.__exit__(None, None, None)
```

Start the Monitor separately (or as a sidecar):

```bash
codegreen monitor --listen-on-socket /tmp/cg.sock -o energy.jsonl &
gunicorn -w 4 'app:app'
```

The Monitor's final summary (printed on Ctrl-C or after `--duration`) has
a `per_label` dict:

```json
{
  "per_label": {
    "GET /search": {"count": 412, "total_joules": 8.31, "p50_ms": 21.0, "p95_ms": 84.3},
    "POST /api/v1/upload": {"count": 17, "total_joules": 12.07, "p50_ms": 412.0, "p95_ms": 1610.4}
  }
}
```

For a complete worked example with a tiny in-process HTTP server, see
[08 - Monitor socket](../examples/08_monitor_socket.md).

## Output streams

`-o energy.jsonl` writes one JSON object per line:

```jsonl
{"type": "header", "version": "1", "interval_ms": 200, "attribution_backend": "cgroup_v2", "pid": 1234}
{"type": "sample", "t": 0.20, "joules_total": 0.84, "joules_delta": 0.84, "watts": 4.2, "proc_cpu_percent": 192.0, "proc_attributed_joules": 0.21}
{"type": "sample", "t": 0.40, ...}
...
{"type": "summary", "duration_s": 30.0, "total_joules": 126.4, "mean_watts": 4.21, "per_label": {...}}
```

The header record always sits at the top of the file; subsequent
`sample` records carry deltas; the trailing `summary` record is written at
`stop()` (or on Ctrl-C / `--duration` expiry).

## Caveats

- **RAPL is system-wide.** Two `codegreen monitor` processes on the same
  socket double-count. The Monitor constructor warns when it detects
  another live CodeGreen PID.
- **Sub-50 ms intervals raise `ValueError`** -- RAPL noise floor.
- **PID death** is caught on `psutil.NoSuchProcess`. The Monitor stops
  cleanly with `terminated_reason = "pid <N> exited"` in the summary.
- **Forking servers** (Apache prefork, gunicorn workers): use the parent
  PID; psutil walks children automatically and credits worker energy back
  to the tree.

## SIGHUP-reload: policy changes without restart

`codegreen monitor` follows the POSIX-daemon convention: **SIGHUP
re-reads `monitor.*` from `codegreen/config.json` and hot-applies
reloadable fields without dropping in-flight annotations or the open
JSONL position**.

Reloadable on SIGHUP (no restart needed):

| Field | Source |
|---|---|
| sample period | `monitor.interval_ms_default` |
| rotation threshold | `monitor.rotate_mb_default` |
| in-memory ring size | `monitor.max_samples_in_memory` |
| label cardinality cap | `monitor.annotation.max_labels` |

Require a full restart (a log line is emitted on SIGHUP if you change
these):

- `--output / -o` path (kernel-level fd; can't migrate mid-stream)
- `--listen-on-socket` (UDS bind point; needs re-bind)
- `--pid` (psutil handle; needs re-attach)
- `--duration` (one-shot scheduler decision)

Wire `systemctl reload` to it:

```ini
[Service]
ExecReload=/bin/kill -HUP $MAINPID
```

Then `systemctl --user reload codegreen-monitor` is a zero-downtime
config push. The monitor emits a `{"type":"reload",...}` record in the
JSONL so postmortem can pinpoint when the policy changed.

If the new config is invalid (corrupt JSON, type mismatch, value below a
floor), the Monitor logs a `RuntimeWarning` and keeps the previous
values — it never crashes mid-run on a bad reload.

## Cardinality cap: high-cardinality labels can't OOM the aggregator

Always-on monitors that label requests by raw URL, request UUID, or
user-id grow `per_label` without bound. CodeGreen caps the number of
distinct labels (default `max_labels=1000`); past the cap, new labels
collapse into a single `__other__` bucket that aggregates count, total
joules, and duration like any other label. The overflow records carry
the originally-requested name in
`labels["__requested_name__"]` so you can still see what was attempted.

```bash
codegreen monitor --max-labels 1000 -o energy.jsonl --listen-on-socket /tmp/cg.sock
```

```json
{
  "per_label": {
    "GET /health": {"count": 87412, "joules_total": 4.21, ...},
    "GET /api/users/:id": {"count": 12044, "joules_total": 17.30, ...},
    "__other__": {"count": 31, "joules_total": 0.12, ...}
  }
}
```

The right fix is usually to normalise label sources upstream
(`GET /users/:id` not `GET /users/42`), but the cap is the safety net
when normalisation lags or breaks.

`--max-labels 0` disables the cap (no overflow bucket). Use only when
the label source is **already bounded** by your code (route templates,
enum values).

## Production deployment shapes

Eight shapes appear repeatedly in user reports. Each maps to a tested
example or a small variant of one.

### 1. Apache / Flask web tier

Apache `mod_wsgi` (or gunicorn / uwsgi) fronts a Flask app on a single
host. You want **per-request energy attribution + an always-on capture**
that survives terminal close, SSH drop, and reboot.

```bash
# /etc/systemd/system/codegreen-monitor.service
ExecStart=/usr/local/bin/codegreen monitor \
    --listen-on-socket /run/codegreen/cg.sock \
    -o /var/log/codegreen/energy.jsonl \
    --rotate-mb 100 --max-labels 1000 --interval 500 --quiet --json
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
```

Wire a `before_request` / `teardown_request` pair using
`codegreen.annotate_request` (see the [Flask snippet](#flask-middleware-recipe)
above).

**Pointer:** [Example 12 — Monitor systemd sidecar](../examples/12_monitor_systemd_sidecar.md).

**Caveats:**

- One monitor per host. Multiple monitors double-count RAPL.
- Sample interval ≥ request P50 for stable attribution; aggregate over
  many hits otherwise.
- Use SIGHUP to push new `--rotate-mb` / `--max-labels` without
  bouncing the unit.

### 2. Kubernetes SaaS API

A SaaS API pod on a multi-tenant node. You want per-pod energy
attribution and per-request labels exported to Prometheus.

```yaml
# Side-car container in the same Pod
containers:
- name: codegreen
  image: ghcr.io/your-org/codegreen:latest
  command: ["codegreen", "monitor",
            "--pid", "1",                       # share PID namespace
            "--attribution-mode", "cgroup_v2",
            "--listen-on-socket", "/var/run/cg/cg.sock",
            "-o", "/var/log/codegreen/energy.jsonl",
            "--rotate-mb", "50", "--max-labels", "5000",
            "--interval", "250", "--quiet", "--json"]
  volumeMounts:
  - {name: cg-run, mountPath: /var/run/cg}
  - {name: cg-log, mountPath: /var/log/codegreen}
```

The app container speaks to the sidecar via the shared `cg-run` volume's
UDS. Energy is per-pod because cgroup_v2 reads the pod's cgroup directly.

**Pointer:** [Example 11 — Monitor socket standalone](../examples/11_monitor_socket_standalone.md)
is the wire; pod manifest is the harness.

**Caveats:**

- `cgroup_v2` is required for accurate per-pod attribution. On older
  GKE nodes (cgroup_v1) the backend silently falls back to
  `cpu_percent` — check `attribution_backend` in the JSONL header.
- The sidecar restarts independently of the app container; the JSONL
  records a fresh `header` each time, so analysis tools should not
  assume monotonic timestamps across container restarts.

### 3. MLOps inference

A long-running PyTorch / TensorFlow inference server. You want per-batch
energy without re-instrumenting the model code.

```bash
codegreen monitor \
    --pid $(pgrep -f 'inference-server') \
    --listen-on-socket /tmp/cg.sock \
    -o /var/log/inference-energy.jsonl \
    --interval 100 \
    --rotate-mb 200 --max-labels 0 --quiet --json
```

The model server wraps each batch in `codegreen.annotate_request(...)`
with a stable label like `model=resnet50,batch=32`. `--max-labels 0` is
safe because the label source is the model registry (bounded).

**Pointer:** [Example 08 — Monitor socket](../examples/08_monitor_socket.md)
for the in-process variant; the staged-inference workflow is in
[Example 05 — GPT-2 staged](../examples/05_gpt2_staged.md).

**Caveats:**

- Sub-100 ms inference batches under-sample at the default 500 ms
  interval. Drop to `--interval 50` (the noise floor) and aggregate.
- GPU energy is **not** counted by RAPL. CodeGreen reports CPU + DRAM
  only; pair with `nvidia-smi --query-gpu=power.draw` if you need a
  full picture.

### 4. Batch ETL

A Kafka-fed ETL pipeline that processes streams in 30-minute windows.
You want per-window energy and per-stage labels.

```bash
codegreen monitor -d 1800 \
    --listen-on-socket /tmp/cg.sock \
    -o "/var/log/etl/window_$(date -u +%Y%m%d_%H%M).jsonl" \
    --max-labels 200 --rotate-mb 0 --interval 1000 --quiet --json
```

`--duration 1800` bounds the run; the cron / Airflow operator that
restarts it for the next window is upstream of CodeGreen.

**Pointer:** [Example 06 — Monitor host](../examples/06_monitor_host.md)
is the simplest version; layer in `--listen-on-socket` for per-stage
labels.

**Caveats:**

- Discrete files per window are easier to ingest than one rotated file.
- `--max-labels` should match your bounded stage count, not the input
  cardinality.

### 5. IoT / edge

A small Linux SBC (Raspberry Pi 4 / 5, NVIDIA Jetson) sampling its own
power for thermal / battery budgeting.

```bash
codegreen monitor -d 0 -i 1000 \
    -o /var/lib/codegreen/edge.jsonl \
    --rotate-mb 10 --max-in-memory 0 --max-labels 64 \
    --quiet --json
```

`--rotate-mb 10` plus the default `rotate_max_backups=5` bounds disk
usage at ≈ 50 MB. `--max-in-memory 0` flushes the deque so a sudden
power loss can't lose more than a single sample.

**Pointer:** [Example 06 — Monitor host](../examples/06_monitor_host.md).

**Caveats:**

- RAPL is x86-only. On ARM SBCs CodeGreen falls back to whatever
  hardware energy interface exists; see the [hardware support matrix](../user-guide/energy-measurement.md).
- Sub-second intervals on a small core can dominate the very workload
  you're measuring. Default 1 Hz here.

### 6. CI / CD energy gating

A GitHub Actions / Jenkins job that runs the test suite + measures its
energy + fails the PR if `total_joules` regressed by > 10 %.

```bash
codegreen monitor -d 0 -o ci-energy.jsonl --quiet --json &
MON=$!
pytest tests/ -q
kill -TERM $MON
wait $MON
codegreen run --json -- python compare_against_baseline.py ci-energy.jsonl
```

For long-running CI containers (always-on test farms) wire the same
SIGHUP-reload pattern as the production case: `kill -HUP $MAINPID` from
your config-management tool when you ship new rotation policies.

**Pointer:** [CI/CD integration guide](cicd-integration.md).

**Caveats:**

- VMs without RAPL passthrough produce no readings; CodeGreen fails
  loud. CI runners on bare-metal-like infrastructure (GitHub Larger
  runners, BuildJet, self-hosted) are the practical floor.

### 7. Live energy dashboards

Grafana / Datadog ingesting CodeGreen's JSONL through Promtail / Vector
/ Fluent Bit. Always-on, label-per-route exposed as Prometheus metrics.

```bash
codegreen monitor \
    --listen-on-socket /run/codegreen/cg.sock \
    -o /var/log/codegreen/dashboard.jsonl \
    --rotate-mb 100 --max-labels 5000 \
    --interval 500 --quiet --json
```

Then point Promtail at the JSONL with a `labels = {type, name}` pipeline
stage. The `summary` record at JSONL rotation gives you a periodic roll-up
without parsing every sample.

**Caveats:**

- High-cardinality dashboards push `max_labels` up — but Prometheus
  itself has a `label_limit` that fires earlier. Use the SIGHUP-reload
  hook to bump both in lockstep.
- Drop samples below your dashboard's resolution at ingest time
  (`Vector transforms`) rather than at CodeGreen — the durable JSONL is
  cheap.

### 8. Compliance reporting (ISO 14064 / GHG Protocol)

Audited monthly energy reports for sustainability disclosure. Always-on
capture, append-only, externally rotated.

```bash
codegreen monitor -d 0 \
    -o /var/lib/codegreen/compliance/$(date -u +%Y%m).jsonl \
    --rotate-mb 0 --max-in-memory 0 --max-labels 0 \
    --interval 1000 --quiet --json
```

`--rotate-mb 0` disables in-tool rotation; an external logrotate /
systemd-tmpfiles policy owns retention. `--max-labels 0` avoids dropping
any label (the auditor wants the full distribution).

**Caveats:**

- Without the cardinality cap, a bug in your label source can OOM the
  aggregator. Pair this shape with a strict label-normaliser upstream
  (route templates, no raw URLs, no UUIDs).
- The JSONL is append-only; a separate cron-rolled file per month is
  what auditors usually expect.

## Exporters

The Monitor's default sink is the in-process JSONL writer. To push the
same telemetry stream to an external collector, pass `--exporter NAME`
(repeatable). Every exporter reads its parameters from
`monitor.exporters.NAME.*` in `codegreen/config.json`; CLI flags override
specific fields. The fan-out happens AFTER the JSONL write, on a bounded
queue with a drop-newest policy — a slow or unreachable backend can
never wedge the sample loop.

### OTLP (OpenTelemetry over gRPC)

Install the optional dependency:

```bash
pip install 'codegreen[otlp]'
```

Enable and point at any OTLP/gRPC endpoint (real OTel Collector,
Datadog Agent, Honeycomb, Grafana Cloud, Lightstep, …):

```bash
codegreen monitor --exporter otlp \
    --otlp-endpoint http://otel-collector.svc:4317 \
    -o /var/log/codegreen/energy.jsonl --rotate-mb 100 --max-labels 1000
```

Standard OTel env vars are honoured by the underlying
`opentelemetry-exporter-otlp-proto-grpc` package:
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`,
`OTEL_EXPORTER_OTLP_CERTIFICATE`, `OTEL_RESOURCE_ATTRIBUTES`.

**Metric catalog**

| Metric                                | Kind             | Unit | Source                                 |
|---------------------------------------|------------------|------|----------------------------------------|
| `codegreen.energy.joules`             | Counter          | J    | per-sample `joules_delta`              |
| `codegreen.power.watts`               | Observable gauge | W    | last `watts`                           |
| `codegreen.request.energy.joules`     | Counter          | J    | per-`annotate_end` `joules`            |
| `codegreen.request.duration.seconds`  | Histogram        | s    | per-`annotate_end` `duration_s`        |

Resource attributes: `service.name=codegreen-monitor`, `host.name`,
`process.pid`, `attribution_backend`, `codegreen.version`. Per-metric
attribute: `route` (capped by `--max-labels`; overflow rolls into
`__other__`).

**Failure policy**

- Missing OTel deps → `Monitor.start()` raises `RuntimeError` with the
  exact `pip install` command. Never silently disabled.
- Unreachable collector → bounded queue drops; counts surface as
  `exporters.otlp.dropped_samples` / `dropped_annotations` in the
  summary. Sample loop never blocks.

Tunables under `monitor.exporters.otlp.*`: `endpoint`, `protocol` (gRPC
only today; HTTP/protobuf deferred), `headers`,
`timeout_s`, `queue_size` (default 10 000), `batch_size` (default 128),
`export_interval_ms` (default 1000), and a `tls: {ca_file, cert_file,
key_file}` block.

**Pointer:** [Example 13 — Monitor OTLP export](../examples/13_monitor_otlp_export.md).

### Prometheus pull endpoint

Install the optional dependency:

```bash
pip install 'codegreen[prometheus]'
```

Enable the exporter and pick a port (loopback bind by default):

```bash
codegreen monitor --exporter prometheus --prometheus-port 9464 \
    -o /var/log/codegreen/energy.jsonl --rotate-mb 100 --max-labels 1000
```

Scrape with vanilla Prometheus, Grafana Agent, Datadog Agent (Prometheus
mode), or the OTel Collector's Prometheus receiver:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: codegreen
    metrics_path: /metrics
    static_configs:
      - targets: ["app-host:9464"]
    # optional, for the auth_token configuration:
    # authorization:
    #   type: Bearer
    #   credentials: <token>
```

**Metric catalog**

| Metric                                  | Kind      | Unit | Labels (in addition to host/pid/attribution_backend) |
|-----------------------------------------|-----------|------|-------------------------------------------------------|
| `codegreen_energy_joules_total`         | Counter   | J    | —                                                     |
| `codegreen_power_watts`                 | Gauge     | W    | —                                                     |
| `codegreen_request_energy_joules_total` | Counter   | J    | `route`, `status`                                     |
| `codegreen_request_duration_seconds`    | Histogram | s    | `route`, `status`                                     |
| `codegreen_monitor_uptime_seconds`      | Gauge     | s    | —                                                     |
| `codegreen_distinct_labels`             | Gauge     | -    | —                                                     |
| `codegreen_overflow_label_count_total`  | Counter   | -    | —                                                     |
| `codegreen_dropped_samples_total`       | Counter   | -    | `sink`                                                |

Resource labels carried on every metric: `host`, `pid`,
`attribution_backend`. Histogram buckets configurable via
`monitor.exporters.prometheus.histogram_buckets_request_duration_seconds`.

**Failure policy**

- Missing `prometheus_client` → `Monitor.start()` raises `RuntimeError`
  with the exact `pip install` command. Never silently disabled.
- Pull semantics: the scraper controls cadence, so the exporter never
  drops on the producer side. `dropped_samples` is always `0` in the
  Prometheus exporter's per-sink summary.
- Address-in-use on the bind port → fail-loud at start, no fallback to a
  random port (the operator chose the address; surprises here are bugs).

#### Compliance posture

The Prometheus exporter is the most network-exposed sink CodeGreen ships;
it gets four layered defaults so that "install + enable" is safe in a
shared environment.

- **Default loopback bind.** `listen_addr=127.0.0.1`. Exposing on
  `0.0.0.0` (or any non-loopback) emits a `RuntimeWarning` at start so
  the choice appears in the audit trail.
- **Cardinality cap protects against URL-PII explosion.** Annotation
  labels are already capped by `monitor.annotation.max_labels` (default
  1000); labels beyond the cap collapse into the `__other__` overflow
  bucket. This means a buggy upstream that emits one label per request
  UUID can never blow up your Prometheus storage — neither the JSONL nor
  the exporter exceed the cap.
- **Optional bearer-token auth.** Set
  `monitor.exporters.prometheus.auth_token` to require an
  `Authorization: Bearer <token>` header on both `/metrics` and
  `/healthz`. Comparison uses `hmac.compare_digest` (constant-time).
  Pair with TLS termination at the reverse proxy (nginx, Envoy, Caddy)
  for transport-layer secrecy.
- **Resource-attribute redaction.** Set
  `monitor.exporters.prometheus.redact_resource_attrs` to any subset of
  `["host", "pid", "attribution_backend"]`; matching labels render as
  `__redacted__` in the exposed metrics. The Monitor's internal
  bookkeeping still uses the real values, so attribution is unchanged.
- **Pull, not push, means no surprise outbound.** The exporter never
  initiates a connection; only the scraper reaches in. Firewall the bind
  port to the scraper's IP and CodeGreen cannot exfiltrate anything.
- **No new audit-log behaviour.** The exporter is a read view over state
  already captured by the JSONL writer; nothing observable here that
  isn't also durable on disk.

**Pointer:** [Example 14 — Monitor Prometheus scrape](../examples/14_monitor_prometheus_scrape.md).

### Remote agent-to-server push

Coming in [todo.txt item Q1](https://github.com/SMART-Dal/codegreen).
Direct fleet-telemetry batch protocol, distinct from OTLP (for offline /
edge / air-gapped fleets). Wired through the same Sink ABC.

### Backpressure semantics

Push-mode exporters (OTLP, the future remote-push) share a contract:

- A bounded `queue.Queue(maxsize=monitor.exporters.<name>.queue_size)`
  decouples the sample loop from the exporter's IO path.
- `feed_*` calls are wait-free (`put_nowait`). On `queue.Full`, the
  newest event is dropped and counted; existing in-flight events are
  preserved.
- `dropped_samples` and `dropped_annotations` surface in
  `summary["exporters"][<name>]` so you can alert on lossy collectors.
- The Monitor's <=1% sample-cadence perturbation budget (the same
  threshold as the prior self-overhead audit) is honoured: the OTel
  reader thread is promoted to daemon at sink-construction time, the
  OTel `force_flush`/`shutdown` calls in close() are bounded to 300 ms
  each, and the gRPC channel uses `insecure=True` for `http://`
  endpoints by default.

The Prometheus exporter is pull-mode: the scraper controls cadence, so
there is no producer-side queue and `dropped_samples` is always 0.
`feed_*` mutates internally-thread-safe Counter/Gauge/Histogram objects
in place; reads happen on the HTTP server thread via
`generate_latest(self._registry)` over the same registry. No lock
contention with the sample loop.

## What to do when…

### …my JSONL keeps growing

Set `--rotate-mb N` to roll the file at N MB. CodeGreen keeps up to
`monitor.rotate_max_backups` (default 5) generations
(`energy.jsonl.1` … `.5`). Older generations are deleted automatically.

### …my `per_label` is exploding

The label source is producing too many distinct names — usually raw URLs
(`/users/42`) instead of route templates (`/users/:id`). Two fixes:

1. **Normalise upstream.** Best long-term: fix the middleware to emit
   bounded labels. For Flask, use `request.url_rule.rule`. For FastAPI
   use `request.scope["route"].path`.
2. **Cap with `--max-labels`.** Defensive net. Overflow rolls into
   `__other__` with count + total joules so you still see it happen.
   Combine with [SIGHUP-reload](#sighup-reload-policy-changes-without-restart)
   to raise the cap online when you fix the upstream bug.

### …I closed my terminal and the monitor died

Four ways to keep it alive. Reproduce of the table in
[example 11](../examples/11_monitor_socket_standalone.md#will-the-monitor-keep-running-if-i-close-the-terminal):

| Mode                              | Survives terminal close? | Survives reboot? | Use for                              |
|-----------------------------------|--------------------------|------------------|---------------------------------------|
| `codegreen monitor ...`           | No                       | No               | Interactive debugging                 |
| `nohup codegreen monitor ... &`   | Yes (ignores SIGHUP)     | No               | One-off long capture                  |
| `tmux new -d 'codegreen monitor ...'` | Yes (tmux owns it)   | No               | Personal dev box                      |
| `systemctl --user start codegreen-monitor.service` | Yes | **Yes** (auto-restart on crash) | **Production webapps** |

The systemd path is in [example 12](../examples/12_monitor_systemd_sidecar.md).

### …I want to update the rotation policy without losing data

Edit `monitor.rotate_mb_default` in `codegreen/config.json`, then send
`SIGHUP` to the monitor:

```bash
kill -HUP "$(pgrep -f 'codegreen monitor')"
# or under systemd:
systemctl --user reload codegreen-monitor
```

The new value applies on the next sample tick. The open JSONL file is
**not** closed or rotated by the reload itself — it rotates the next
time it hits the new threshold. In-flight annotations keep their open
tokens.

## See also

- [06 - Monitor host](../examples/06_monitor_host.md)
- [07 - Monitor PID](../examples/07_monitor_pid.md)
- [08 - Monitor socket](../examples/08_monitor_socket.md)
- [11 - Monitor socket (standalone)](../examples/11_monitor_socket_standalone.md)
- [12 - Monitor systemd sidecar](../examples/12_monitor_systemd_sidecar.md)
- [Python API: Monitor](../api/python.md#codegreenmonitor)
- [Python API: annotate_request](../api/python.md#annotate_request)
