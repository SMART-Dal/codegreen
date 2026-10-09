# CodeGreen Examples

Canonical, end-to-end examples for `pip install codegreen`. Each example is
a self-contained Python script that runs against a fresh CodeGreen install
on Linux (RAPL) or macOS (IOReport); the only external assumption is the
`codegreen` CLI on PATH. Heavy ML examples (GPT-2) live in their own
subfolder with a `requirements.txt` and are skipped by the auto-test
harness.

Run an example directly:

```bash
python examples/01_quickstart_measure/main.py
```

Run all examples through the test harness:

```bash
pytest tests/test_examples.py -q
```

Each script prints a single `OK: <feature>; <metrics>` line on success or
`SKIP: <reason>` when a dependency is missing.

## Index

| # | Example | What it shows | Prereqs | Marker |
|---|---------|---------------|---------|--------|
| 01 | `01_quickstart_measure` | The 30-second `codegreen run` intro | none | `OK: quickstart_measure; ...` |
| 02 | `02_run_repeat` | Stable mean across `--repeat 5` runs, CV reporting | none | `OK: run_repeat; ...` |
| 03 | `03_session_api` | `codegreen.Session` ctx manager + `@codegreen.task` decorator | none | `OK: session_api; ...` |
| 04 | `04_project_hotspots_java` | `codegreen project java` end-to-end (per-method attribution) | JDK on PATH | `OK: project_hotspots_java; ...` |
| 05 | `05_gpt2_staged` | Multi-task Session over GPT-2 inference, time-series report | `pip install -r requirements.txt` | `OK: gpt2_staged; ...` (skipped in CI) |
| 06 | `06_monitor_host` | Host-wide cumulative sampling, JSONL output | none | `OK: monitor_host; ...` |
| 07 | `07_monitor_pid` | Per-PID attribution: cgroup_v2 vs cpu_percent backend | psutil | `OK: monitor_pid; ...` |
| 08 | `08_monitor_socket` | Per-request attribution via UDS annotation socket, in-process Monitor | stdlib only | `OK: monitor_socket; ...` |
| 09 | `09_project_hotspots_python` | `codegreen project python` per-function instrumentation | none | `OK: project_hotspots_python; ...` |
| 10 | `10_codegreen_vs_perf` | Cross-validate CodeGreen mean against `perf stat power/energy-pkg/` | `perf` on PATH | `OK: codegreen_vs_perf; ...` |
| 11 | `11_monitor_socket_standalone` | Same UDS annotation flow, but `codegreen monitor` runs as a SEPARATE process (XaBerr's production deployment shape: monitor sidecar + already-running webapp) | stdlib only | `OK: monitor_socket_standalone; ...` |
| 12 | `12_monitor_systemd_sidecar` | Same sidecar pattern, but supervised by user-mode systemd: survives terminal close + SSH drop + reboot (with `loginctl enable-linger`). Ephemeral `.service` unit installed under `~/.config/systemd/user/`, no root. | `systemctl --user`, stdlib | `OK: monitor_systemd_sidecar; ...` |
| 13 | `13_monitor_otlp_export` | `codegreen monitor --exporter otlp` streams energy metrics over OTLP/gRPC to an in-process OpenTelemetry collector. Demonstrates the production observability path: any OTel-compatible backend (Datadog, Honeycomb, Grafana Cloud, vendor OTel Collector) is one endpoint flag away. | `pip install codegreen[otlp]` | `OK: monitor_otlp_export; ...` |
| 14 | `14_monitor_prometheus_scrape` | `codegreen monitor --exporter prometheus --prometheus-port PORT` exposes a Prometheus-compatible `/metrics` pull endpoint (loopback by default, optional bearer-token auth, label-cardinality bounded). Scrape with vanilla `prometheus.yml` or any Datadog/Grafana Agent. | `pip install codegreen[prometheus]` | `OK: monitor_prometheus_scrape; ...` |

## "I want to ..."

- **Measure a one-liner Python script** -> 01_quickstart_measure
- **Get a tight mean over many runs** -> 02_run_repeat
- **Instrument a specific function inside a long Python program** -> 03_session_api
- **Find energy hotspots in a Java project** -> 04_project_hotspots_java
- **Profile staged ML inference (preprocess / load / generate)** -> 05_gpt2_staged
- **Watch a daemon's energy in the background** -> 06_monitor_host
- **Attribute system energy to a single PID** -> 07_monitor_pid
- **Attribute energy to individual HTTP requests in a web app (single-process)** -> 08_monitor_socket
- **Attach to an already-running web app from a separate codegreen sidecar** -> 11_monitor_socket_standalone
- **Keep the sidecar alive across terminal close / SSH drop / reboot** -> 12_monitor_systemd_sidecar
- **Ship CodeGreen energy metrics to Datadog/Honeycomb/Grafana via OpenTelemetry** -> 13_monitor_otlp_export
- **Expose a Prometheus-scrapeable /metrics endpoint for SRE / K8s pipelines** -> 14_monitor_prometheus_scrape
- **Find energy hotspots in a Python project** -> 09_project_hotspots_python
- **Sanity-check CodeGreen against the kernel** -> 10_codegreen_vs_perf

## Attribution backends

Examples 07 and 08 surface CodeGreen's per-PID attribution. The Monitor
selects a backend at start():

- **cgroup_v2** (preferred on Linux): reads `cpu.stat:usage_usec` from the
  PID's unified cgroup; share = cgroup_cpu_delta / system_cpu_busy_delta.
  Highly accurate even under heavy multi-tenant contention.
- **cgroup_v1** (fallback): same idea using `cpuacct.usage` (nanoseconds).
- **cpu_percent** (last resort): psutil `proc.cpu_percent / (100 * ncores)`;
  underestimates single-threaded workloads on many-core hosts because it
  normalizes against full system capacity.

The chosen backend is reported as `attribution_backend` on every header and
summary record. Override with `Monitor(attribution_mode=...)` or
`codegreen monitor --attribution-mode ...`.

## Contributing an example

1. Create `examples/NN_short_name/main.py` (use the next free NN; pick a
   short snake_case name).
2. Keep the script under 100 LOC of user-facing code (excluding tests).
3. End with exactly one `OK: <name>; <key>=<value>; ...` line on success
   or `SKIP: <reason>` if a dependency is missing.
4. Use only the public CodeGreen API (`codegreen.Session`, `codegreen.task`,
   `codegreen.Monitor`, `codegreen.annotate_request`) and the `codegreen`
   CLI; never import from `codegreen.instrumentation....` internals.
5. If your example needs heavy deps (`torch`, `tensorflow`, custom
   compilers), put it in a subfolder with its own `requirements.txt` and
   `README.md`, and add it to `HEAVY_EXAMPLES` in
   `tests/test_examples.py`.
6. If your example needs a per-example timeout other than the default,
   add an entry under `examples.per_example` in `codegreen/config.json`.
7. Run `pytest tests/test_examples.py::test_example_runs -k NN_ -q` and
   make sure it passes.

The docs site mirrors this layout at
<https://smart-dal.github.io/codegreen/examples/>.
