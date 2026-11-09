# Continuous Monitoring

`codegreen monitor` (CLI) and `codegreen.Monitor` (Python) sample cumulative
energy at a fixed interval without launching a workload. Use them for
processes that are already running (web servers, daemons, inference
servers) and for per-request attribution in a web application.

| Use case | Tool |
|---|---|
| Bracket a region inside a Python program | [`codegreen.Session`](../api/python.md#manual-api-codegreensession) |
| Measure an unmodified command, with repeats and a budget | [`codegreen run`](cli-reference.md#run) |
| Observe a running service or the whole host | `codegreen monitor` / `codegreen.Monitor` |
| Energy per HTTP request or batch | Monitor with `--listen-on-socket` plus `codegreen.annotate_request` |

## What a sample measures

Each sample is the change in cumulative energy since the previous sample,
summed over the providers of `measurement.default_sensors` (default `"all"`:
every provider that initializes, GPUs included). The reading is host-wide:
it contains every process on the machine, and two monitors on one host
observe the same joules. To restrict the sum to CPU energy, set
`measurement.default_sensors` to `["rapl"]` in your
[configuration](configuration-reference.md); `monitor` has no `--sensors`
option.

A failed read is never filled with zero. The sample is written to the JSONL
file as `{"type": "sample", "t": ..., "valid": false}`, is excluded from
memory, annotations and exporters, and the next valid sample's
`joules_delta` spans the gap. The summary's `validity` block reports
failed sample reads as the warning `SAMPLES_INVALID` and a failed final read
as the reason `PROVIDER_READ_FAILED` (`total_joules` then ends at the last
valid sample). A failed first read makes `start()` raise `RuntimeError`.

## CLI

```bash
codegreen monitor [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-d, --duration FLOAT` | run until stopped | Stop after N seconds (must be > 0) |
| `-i, --interval INT` | `monitor.interval_ms_default` (500) | Sample period in ms; below `monitor.interval_ms_min` (50) is an error |
| `-p, --pid INT` | none | Attribute a share of each sample to this process (needs `psutil`) |
| `-o, --output PATH` | none | Stream records as JSON lines to this file |
| `--rotate-mb INT` | `monitor.rotate_mb_default` (0) | Rotate the JSONL file at N MB; 0 disables |
| `--max-in-memory INT` | `monitor.max_samples_in_memory` (10000) | Samples kept in memory; 0 keeps none |
| `--max-labels INT` | `monitor.annotation.max_labels` (1000) | Distinct annotation labels; overflow goes to `__other__`; 0 = unlimited |
| `--listen-on-socket TEXT` | none | Bind a Unix-domain socket for annotation events; `default` = per-user path |
| `--attribution-mode TEXT` | `auto` | PID share backend: `auto`, `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `--exporter TEXT` | none | Enable an exporter, repeatable: `otlp`, `prometheus` |
| `--otlp-endpoint TEXT` | config | Overrides `monitor.exporters.otlp.endpoint`; requires `--exporter otlp` |
| `--prometheus-port INT` | config (9464) | Overrides `monitor.exporters.prometheus.port`; 0 = ephemeral; requires `--exporter prometheus` |
| `--prometheus-listen-addr TEXT` | config (`127.0.0.1`) | Overrides `monitor.exporters.prometheus.listen_addr`; requires `--exporter prometheus` |
| `--json` | off | Print the final summary as one JSON object, with `success` = validity is `valid` |
| `-q, --quiet` | off | Suppress the live sample lines |

SIGINT and SIGTERM stop the monitor and flush the summary. SIGHUP reloads
configuration (see [Reloading configuration](#reloading-configuration)).
The command exits 1 when the monitor cannot be constructed or started
(invalid option, missing optional dependency, unbindable socket or port,
failed first read) and 0 after a stop, whatever the validity; check
`success` or `validity.status` in the `--json` summary.

```bash
codegreen monitor -d 30                                   # 30 s at the default interval
codegreen monitor -i 1000 -d 3600 -o energy.jsonl         # 1 Hz for one hour
codegreen monitor --pid "$(pgrep -o gunicorn)" -d 600     # attribute to a process tree
codegreen monitor --listen-on-socket default -o req.jsonl # accept request annotations
```

Live output (`-d 1.2 -i 200 -o m.jsonl`; values depend on the host):

```text
Monitoring (interval=200ms, duration=1.2s)
  t=   0.4s  dJ=  19.38  W= 100.2
  t=   0.8s  dJ=  25.58  W=  99.0
  t=   1.0s  dJ=  20.07  W= 112.8

Summary
  duration: 1.21 s
  total energy: 121.536 J (0.0338 Wh)
  avg power: 100.77 W
  samples: 5 valid, 0 failed reads
  samples written: m.jsonl
```

Without `--quiet` the live display polls every min(1 s, 2 x interval), and
the final read happens when it notices the end of the run, so the summary
window can extend past `--duration` by up to one polling period. With
`--quiet` or `--json` it ends within one interval.

## Python API

```python
import codegreen

m = codegreen.Monitor(interval_ms=200, output_file="energy.jsonl").start()
run_load_test()
summary = m.stop()
print(summary["total_joules"], summary["avg_watts"])
```

`start()` returns the monitor, and the class is also a context manager that
calls `stop()` on exit. `stop()` returns the summary dict and, with
`output_file`, appends it as the final `summary` record; keep the dict from
the first call, because a later `stop()` recomputes `duration_s` up to the
time of that call. `m.samples` returns the samples kept in memory.

| Parameter | Default | Notes |
|---|---|---|
| `interval_ms` | `monitor.interval_ms_default` (500) | `ValueError` below `monitor.interval_ms_min` (50); `RuntimeWarning` below `monitor.interval_ms_warn_below` (100) when `duration_s` is `None` |
| `duration_s` | `None` | Stop automatically after N seconds; must be > 0 |
| `pid` | `None` | Process to attribute; requires `psutil` |
| `include_children` | `True` | Add descendants' CPU% to `proc_cpu_percent` |
| `output_file` | `None` | JSON-lines output path |
| `max_samples_in_memory` | `monitor.max_samples_in_memory` (10000) | 0 keeps no samples in memory |
| `rotate_mb` | `monitor.rotate_mb_default` (0) | Rotate `output_file` at N MB |
| `listen_socket_path` | `None` | Socket for annotation events; `"default"` = `default_socket_path()` |
| `attribution_mode` | `monitor.attribution.mode_default` (`"auto"`) | `auto`, `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `max_labels` | `monitor.annotation.max_labels` (1000) | 0 = unlimited |
| `exporters` | `None` | List of exporter names, e.g. `["prometheus"]` |
| `exporter_overrides` | `None` | Per-exporter config overrides, e.g. `{"prometheus": {"port": 0}}` |

A second `start()` on the same instance raises `RuntimeError`.

## Per-PID attribution

With `--pid`, each sample also carries the target's share of
`joules_delta`. The backend is chosen once at `start()`:

| Backend | Share of each sample | Source |
|---|---|---|
| `cgroup_v2` | cgroup CPU time / busy CPU time of the whole host, capped at 1 | `cpu.stat` `usage_usec` of the PID's cgroup, `/proc/stat` |
| `cgroup_v1` | same, from `cpuacct.usage` | `cpuacct.usage` of the PID's cgroup, `/proc/stat` |
| `cpu_percent` | process-tree CPU% / (100 x logical CPUs) | `psutil` |

`auto` tries `cgroup_v2`, then `cgroup_v1` (unless
`monitor.attribution.allow_cgroup_v1` is false), then falls back to
`cpu_percent` with a `RuntimeWarning`. An explicitly requested cgroup
backend that is unavailable raises `RuntimeError`. The resolved backend is
in the JSONL header and the summary (`attribution_backend`).

The two definitions answer different questions and diverge strongly on a
mostly idle many-core host. A single-threaded loop on a 128-CPU host, 3 s
at 200 ms, measured with [example 07](../examples/07_monitor_pid.md):

| Backend | Attributed | Host total |
|---|---|---|
| `cgroup_v2` | 274.6 J | 301.1 J |
| `cpu_percent` | 2.2 J | 301.2 J |

`cgroup_v2` charges the process with the host's energy in proportion to its
share of the busy CPU time, so idle and uncore power go to whoever is busy.
`cpu_percent` charges it with its share of total CPU capacity. Report which
backend produced a number.

Two caveats for the cgroup backends:

- They attribute the **cgroup** that contains the PID, not the PID alone. A
  process started from a login shell shares the session's cgroup with every
  other process of that session. Run the target in its own cgroup (a
  systemd service, a container) for a per-service share.
- The PID's cgroup is resolved through `/proc/<pid>/cgroup` and the cgroup
  filesystem as the monitor sees them (`monitor.attribution.cgroup_root`,
  `cgroup_unified_root`). Run the monitor in a namespace where both are
  visible.

With `cpu_percent`, the summary's `proc_attributed_joules` is summed over
the samples still in memory, so it covers only the last
`max_samples_in_memory` samples and is `null` with `--max-in-memory 0`. The
per-sample `proc_attributed_joules` values in the JSONL file are complete.

When the process exits, the monitor stops with
`terminated_reason: "pid <N> exited"`.

## Per-request attribution

Start the monitor with `--listen-on-socket` and wrap each request in
`codegreen.annotate_request`. The client sends `start` and `end` events over
the Unix-domain socket; the monitor aggregates `per_label` energy and
latency.

```python
from flask import Flask, g, request
import codegreen

app = Flask(__name__)

@app.before_request
def _cg_start():
    route = request.url_rule.rule if request.url_rule else "unmatched"
    g._cg = codegreen.annotate_request(f"{request.method} {route}")
    g._cg.__enter__()

@app.teardown_request
def _cg_end(exc):
    g._cg.__exit__(type(exc) if exc else None, exc, None)
```

```bash
codegreen monitor --listen-on-socket default -o energy.jsonl --quiet &
gunicorn -w 4 'app:app'
```

`annotate_request(name, labels=None, socket_path=None, timeout_s=0.25)`
connects to `socket_path`, by default `default_socket_path()`:
`$XDG_RUNTIME_DIR/codegreen.sock`, else `/tmp/codegreen-<uid>/codegreen.sock`,
the same path `--listen-on-socket default` binds. It raises when no monitor
listens there (for example `FileNotFoundError`); the annotation is not
dropped silently, so a request fails in the middleware above while the
monitor is down. Use route templates as names (`/users/<id>`, not
`/users/42`) so the label set stays bounded.

How request energy is computed:

- Every valid sample adds its whole `joules_delta` to every annotation that
  is open when the sample is taken. A request shorter than the interval
  gets 0 J or one full interval's energy; aggregate over many requests or
  shorten the interval.
- Concurrent requests each receive the full delta, so per-label totals can
  sum to more than `total_joules`.
- Request energy is host-wide energy, not the PID share, even with `--pid`.

In this run a 0.15 s request at a 200 ms interval received one full sample:

```json
{"type":"annotation_end","token":"24afe440731e4bc7a650dc710ded566b","name":"GET /heavy","labels":{},"status":"ok","t_open":0.145709,"t_close":0.298223,"duration_s":0.152514,"joules":20.780622,"n_samples":1,"ts":"2026-11-06T23:18:18.646080+00:00"}
```

### Socket protocol

One JSON object per line, one reply per line. Any language can be a client.

| Request | Reply |
|---|---|
| `{"op":"start","name":"GET /users","labels":{...},"token":"optional"}` | `{"ok":true,"token":"..."}` |
| `{"op":"end","token":"...","status":"ok"}` | `{"ok":true,"joules":...,"duration_s":...}` |
| malformed or unknown | `{"ok":false,"error":"..."}` |

A label set may hold at most `monitor.annotation.max_label_count` (64)
entries. The socket is created with mode 0600, so the application must run
as the same user as the monitor; the per-user default directory must be
owned by that user with mode 0700, and any other socket directory must
already exist. A second monitor bound
to the same path as the same user replaces the socket file, and the first
monitor stops receiving events without an error, so run one monitor per
socket. Socket paths are limited to about 108 bytes by the OS.

## Output

`-o` writes one JSON record per line. Records from a real run:

```json
{"type":"header","interval_ms":200,"pid":null,"start_ts":"2026-11-06T23:14:43.215473+00:00","rotate_mb":0,"max_samples_in_memory":10000,"max_labels":1000,"overflow_bucket":"__other__","listen_socket":null,"attribution_mode_requested":"auto","attribution_backend":null}
{"type":"sample","t":0.2005,"valid":true,"joules_total":15.792133,"joules_delta":15.792133,"watts":62.6974}
{"type":"summary","duration_s":1.2061,"total_joules":121.536371,"avg_watts":100.765,"samples":5,"invalid_samples":0,"validity":{"status":"valid","reasons":[],"detail":{},"warnings":{}},"samples_in_memory":5,"pid":null,"proc_attributed_joules":null,"attribution_mode_requested":"auto","attribution_backend":null,"terminated_reason":null,"annotations_open":0,"per_label":{},"max_labels":1000,"overflow_bucket":"__other__","distinct_labels":0,"reload_count":0,"end_ts":"2026-11-06T23:14:44.421532+00:00"}
```

| Record | Written | Fields |
|---|---|---|
| `header` | at start | `interval_ms`, `pid`, `start_ts`, `rotate_mb`, `max_samples_in_memory`, `max_labels`, `overflow_bucket`, `listen_socket`, `attribution_mode_requested`, `attribution_backend` |
| `sample` | every interval | `t` (s since start), `valid`, `joules_total` (since start), `joules_delta`, `watts` (backend power at the read) |
| `annotation_start` | request opened | `token`, `name`, `labels`, `t`, `ts` |
| `annotation_end` | request closed | `token`, `name`, `labels`, `status`, `t_open`, `t_close`, `duration_s`, `joules`, `n_samples`, `ts` |
| `reload` | after SIGHUP | `ts`, `interval_ms`, `max_samples_in_memory`, `rotate_mb`, `max_labels`, `reload_count` |
| `header_rotated` | first line of a new file after rotation | `ts`, `interval_ms` |
| `summary` | at stop | see below |

With `--pid`, samples also carry `proc_cpu_percent`, `proc_n_children`,
`proc_attribution_backend`, `proc_attributed_joules` and, for the cgroup
backends, `proc_cpu_share`, `cgroup_cpu_usec_delta`, `system_cpu_usec_delta`:

```json
{"type":"sample","t":0.5004,"valid":true,"joules_total":51.102818,"joules_delta":51.102818,"watts":131.3747,"proc_cpu_percent":100.9,"proc_n_children":0,"proc_attribution_backend":"cgroup_v2","proc_cpu_share":0.98613,"proc_attributed_joules":50.394002,"cgroup_cpu_usec_delta":1498917,"system_cpu_usec_delta":1520000}
```

Summary fields:

| Field | Meaning |
|---|---|
| `duration_s`, `total_joules`, `avg_watts` | Window from start to the final read, energy over it, mean power |
| `samples`, `invalid_samples`, `samples_in_memory` | Valid samples, failed sample reads, samples held in memory |
| `validity` | `{status, reasons, detail, warnings}`; see [What a sample measures](#what-a-sample-measures) |
| `pid`, `proc_attributed_joules`, `attribution_mode_requested`, `attribution_backend` | PID attribution; `null` without `--pid` |
| `terminated_reason` | `null`, or `pid <N> exited` |
| `annotations_open`, `distinct_labels`, `max_labels`, `overflow_bucket` | Annotation state at stop |
| `per_label` | Per label: `count`, `joules_total`, `duration_total_s`, `joules_per_call_avg`, `latency_ms_p50`, `latency_ms_p95`; the top `monitor.annotation.summary_top_labels` (50) labels by energy, plus `__other__` if present |
| `reload_count`, `end_ts` | SIGHUP reloads applied; stop time (UTC) |
| `exporters` | Per-exporter summary, present when `--exporter` is used |

## Long-running operation

**Rotation.** `--rotate-mb N` rolls `energy.jsonl` to `energy.jsonl.1`,
shifting older files up to `monitor.rotate_max_backups` (5) and deleting
the oldest. The new file starts with a `header_rotated` record. The summary
is written only at stop, to the current file.

**Memory.** The in-memory deque holds at most `--max-in-memory` samples;
totals do not depend on it.

**Label cardinality.** Once `--max-labels` distinct labels exist, a new label
is recorded under `__other__` and its requested name is kept in
`labels["__requested_name__"]` of its annotation records. `--max-labels 0`
removes the cap; use it only for a label source that is bounded by
construction.

### Reloading configuration

SIGHUP makes the monitor re-read the configuration (`CODEGREEN_CONFIG`, else
`~/.codegreen/config.json`, merged over the bundled defaults) at the next
sample tick and apply four values from it:

| Value | Key |
|---|---|
| sample period | `monitor.interval_ms_default` |
| rotation threshold | `monitor.rotate_mb_default` |
| in-memory samples | `monitor.max_samples_in_memory` |
| label cap | `monitor.annotation.max_labels` |

The config values replace the corresponding command-line options: a
monitor started with `-i 200` samples at `monitor.interval_ms_default` (500
ms by default) after a SIGHUP. An invalid value is rejected with a
`RuntimeWarning` and the previous value stays. The open JSONL file and open
annotations are kept, and a `reload` record is written. `--output`,
`--listen-on-socket`, `--pid` and `--duration` cannot change without a
restart.

```ini
[Service]
ExecReload=/bin/kill -HUP $MAINPID
```

### Keeping the monitor running

Closing a terminal sends SIGHUP, which the monitor treats as a reload, not
a stop. With `--quiet` it keeps running after the terminal closes (at the
reloaded interval). Without `--quiet`, the next live line fails on the
closed terminal and the process exits without writing a summary record.

| Mode | Survives terminal close | Survives reboot |
|---|---|---|
| `codegreen monitor ...` (live output) | No, and no summary record | No |
| `codegreen monitor --quiet ...` or `nohup codegreen monitor ... &` | Yes; the hangup is a reload | No |
| `tmux` / `screen` session | Yes | No |
| systemd unit ([example 12](../examples/12_monitor_systemd_sidecar.md)) | Yes | Yes (user units need `loginctl enable-linger`) |

## Exporters

`--exporter NAME` (repeatable) sends the same stream to an external system
in addition to the JSONL file. Each exporter reads `monitor.exporters.NAME.*`
from the configuration; the CLI flags override single keys. A missing
optional dependency makes `start()` raise `RuntimeError` with the install
command; an unknown exporter name raises `ValueError`. The exporter's
summary is returned under `summary["exporters"][NAME]`.

### OTLP

```bash
pip install 'codegreen[otlp]'
codegreen monitor --exporter otlp --otlp-endpoint http://otel-collector:4317 \
    -o /var/log/codegreen/energy.jsonl
```

| Metric | Instrument | Unit | Source |
|---|---|---|---|
| `codegreen.energy.joules` | Counter | J | sample `joules_delta` |
| `codegreen.power.watts` | Observable gauge | W | last sample `watts` |
| `codegreen.request.energy.joules` | Counter | J | `annotation_end` `joules` (spans with 0 J are not added) |
| `codegreen.request.duration.seconds` | Histogram | s | `annotation_end` `duration_s` |

Meter name `codegreen.monitor`. Request metrics carry the attributes `route`
(the annotation name) and `status`. Resource attributes: `service.name`
(`codegreen-monitor`), `host.name`, `process.pid` (the `--pid` target, else
the monitor), `attribution_backend` (`host` without `--pid`),
`codegreen.version`, plus the SDK's defaults and `OTEL_RESOURCE_ATTRIBUTES`.

Settings live under `monitor.exporters.otlp`
([key list](configuration-reference.md#monitor)). How they interact with the
OpenTelemetry environment variables:

- `endpoint` (default `http://localhost:4317`) is always passed explicitly,
  so `OTEL_EXPORTER_OTLP_ENDPOINT` has no effect; an `http://` endpoint
  disables TLS. `protocol` accepts only `grpc`.
- `headers` (a dict; not in the bundled config) and `tls.ca_file` fall back
  to `OTEL_EXPORTER_OTLP_HEADERS` and `OTEL_EXPORTER_OTLP_CERTIFICATE` when
  unset.
- `export_interval_ms` has a floor of 100; the per-export timeout is
  `timeout_s` capped at 2 s.

Events enter a bounded queue (`queue_size`) without blocking; when it is full the newest
event is dropped and counted. The exporter summary reports `endpoint`,
`protocol`, `queue_size`, `batch_size`, `dropped_samples`,
`dropped_annotations`, `exported_samples` and `exported_annotations`. At
stop, the final flush and shutdown run on a thread that is joined for at
most one second, so an unreachable collector cannot block `stop()`.

See [example 13](../examples/13_monitor_otlp_export.md).

### Prometheus

```bash
pip install 'codegreen[prometheus]'
codegreen monitor --exporter prometheus --prometheus-port 9464 \
    -o /var/log/codegreen/energy.jsonl
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: codegreen
    static_configs:
      - targets: ["app-host:9464"]
    # with monitor.exporters.prometheus.auth_token set:
    # authorization:
    #   type: Bearer
    #   credentials: <token>
```

| Metric | Type | Labels |
|---|---|---|
| `codegreen_energy_joules_total` | Counter | `host`, `pid`, `attribution_backend` |
| `codegreen_power_watts` | Gauge | `host`, `pid`, `attribution_backend` |
| `codegreen_request_energy_joules_total` | Counter | + `route`, `status` |
| `codegreen_request_duration_seconds` | Histogram | + `route`, `status` |
| `codegreen_monitor_uptime_seconds` | Gauge | `host`, `pid`, `attribution_backend` |
| `codegreen_distinct_labels` | Gauge | `host`, `pid`, `attribution_backend` |
| `codegreen_overflow_label_count_total` | Counter, annotations recorded under `__other__` | `host`, `pid`, `attribution_backend` |
| `codegreen_dropped_samples_total` | Counter, never incremented (pull exporter) | + `sink` |

Settings live under `monitor.exporters.prometheus`
([key list](configuration-reference.md#monitor)):

- `listen_addr` defaults to `127.0.0.1`; a non-loopback address emits a
  `RuntimeWarning`. A `port` in use fails at start; `0` picks a free port.
- `auth_token`, when set, makes `/metrics` require
  `Authorization: Bearer <token>` (constant-time comparison). The health
  endpoint (`/healthz`) stays open for liveness probes and returns
  `{"status":"healthy","uptime_s":...,"samples_seen":...,"annotations_seen":...}`.
- `redact_resource_attrs` takes any of `host`, `pid`, `attribution_backend`;
  their label values become `__redacted__`.
- `histogram_buckets_request_duration_seconds` sets the buckets of
  `codegreen_request_duration_seconds`.

The exporter uses its own registry, mutates the metrics in place on each
sample and serves them from a daemon HTTP thread; it never opens outbound
connections. There is no TLS; terminate TLS at a reverse proxy and restrict
the port to the scraper.

See [example 14](../examples/14_monitor_prometheus_scrape.md).

`monitor.exporters.remote_push` is a placeholder; `--exporter remote_push`
is rejected.

## Deployment notes

- **Web tier on one host.** Run the monitor as a systemd unit with
  `--listen-on-socket`, `-o`, `--rotate-mb`, `--max-labels` and `--quiet`,
  and annotate requests in the application
  ([example 11](../examples/11_monitor_socket_standalone.md),
  [example 12](../examples/12_monitor_systemd_sidecar.md)). Choose an
  interval below the typical request duration, or aggregate many requests.
- **Containers.** The energy counters must be readable inside the container
  (`codegreen capabilities energy` lists the providers that initialize).
  For per-PID attribution, see the cgroup caveats under
  [Per-PID attribution](#per-pid-attribution).
- **Batch windows.** Start one monitor per window with `-d` and a distinct
  `-o` file per window; the scheduler that starts the next window is
  outside CodeGreen.
- **CI gating.** To fail a build on energy, measure the step with
  [`codegreen run --budget`](cicd-integration.md), which sets the exit code.
  The monitor's exit code does not reflect energy or validity.

## Troubleshooting

**The JSONL file keeps growing.** Rotation is off by default
(`monitor.rotate_mb_default` is 0). Start the monitor with `--rotate-mb N`;
at most `monitor.rotate_max_backups` (5) rotated files are kept.

**`per_label` has too many labels.** The label source emits unbounded names,
usually raw URLs (`/users/42`) instead of route templates. Emit route
templates in the middleware (`request.url_rule.rule` in Flask, as above);
`--max-labels` caps the damage meanwhile: labels seen before the cap keep
their own entry, and new ones are counted under `__other__`.

**The monitor died when the terminal closed.** It was printing live lines;
see [Keeping the monitor running](#keeping-the-monitor-running). Use
`--quiet`, `nohup`, tmux or a systemd unit.

**Changing the rotation threshold without a restart.** Set
`monitor.rotate_mb_default` in the configuration and send SIGHUP
(`kill -HUP <pid>`, or `systemctl reload` with the `ExecReload` line above).
The open file is kept and rotates once it crosses the new threshold. The
reload also applies the configured interval, in-memory limit and label cap
in place of their command-line values; `monitor.rotate_max_backups` is read
only at start.

## See also

- Examples: [06 host](../examples/06_monitor_host.md),
  [07 PID](../examples/07_monitor_pid.md),
  [08 socket in-process](../examples/08_monitor_socket.md),
  [11 socket sidecar](../examples/11_monitor_socket_standalone.md),
  [12 systemd](../examples/12_monitor_systemd_sidecar.md),
  [13 OTLP](../examples/13_monitor_otlp_export.md),
  [14 Prometheus](../examples/14_monitor_prometheus_scrape.md)
- [Python API: Monitor](../api/python.md#codegreenmonitor),
  [annotate_request](../api/python.md#annotate_request)
