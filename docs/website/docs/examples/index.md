# Examples

Fourteen end-to-end examples that ship with CodeGreen. Every script lives under
[`examples/`](https://github.com/SMART-Dal/codegreen/tree/main/examples) in
the repository and is exercised by `pytest tests/test_examples.py`. Each
page on this site links back to the canonical source rather than duplicating
it.

Run an example directly:

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
python examples/01_quickstart_measure/main.py
```

Run them all through the harness:

```bash
pytest tests/test_examples.py -q
```

Each script prints exactly one `OK: <feature>; <metrics>` line on success or
`SKIP: <reason>` when a dependency is missing.

## Index

| # | Example | What it shows | Prereqs |
|---|---------|---------------|---------|
| 01 | [Quickstart measure](01_quickstart_measure.md) | 30-second `codegreen run` intro | none |
| 02 | [Run with repeats](02_run_repeat.md) | Stable mean across `--repeat`, CV reporting | none |
| 03 | [Session API](03_session_api.md) | `codegreen.Session` ctx manager + `@codegreen.task` | none |
| 04 | [Project hotspots (Java)](04_project_hotspots_java.md) | `codegreen project java` end-to-end | JDK |
| 05 | [GPT-2 staged inference](05_gpt2_staged.md) | Multi-task Session with time-series export | `torch`, `transformers` |
| 06 | [Monitor host](06_monitor_host.md) | Host-wide cumulative sampling, JSONL output | none |
| 07 | [Monitor PID](07_monitor_pid.md) | Per-PID attribution: cgroup_v2 vs cpu_percent | psutil |
| 08 | [Monitor socket — single-process](08_monitor_socket.md) | Per-request energy via UDS annotation, Monitor inside the webapp | stdlib only |
| 09 | [Project hotspots (Python)](09_project_hotspots_python.md) | `codegreen project python` per-function | none |
| 10 | [CodeGreen vs perf](10_codegreen_vs_perf.md) | Cross-validate against `perf stat power/energy-pkg/` | `perf` |
| 11 | [Monitor socket — standalone](11_monitor_socket_standalone.md) | Same UDS flow, but `codegreen monitor` runs as a separate sidecar process (production deployment shape: systemd / tmux / nohup) | stdlib only |
| 12 | [Monitor systemd sidecar](12_monitor_systemd_sidecar.md) | Same sidecar pattern, supervised by user-mode systemd. Survives terminal close, SSH drop, and reboot (with linger). No root required. | `systemctl --user`, stdlib |
| 13 | [Monitor OTLP export](13_monitor_otlp_export.md) | `codegreen monitor --exporter otlp` streams energy metrics over OTLP/gRPC to any OpenTelemetry-compatible collector (Datadog, Honeycomb, Grafana Cloud, vendor OTel Collector). Production observability path. | `pip install codegreen[otlp]` |
| 14 | [Monitor Prometheus scrape](14_monitor_prometheus_scrape.md) | `codegreen monitor --exporter prometheus --prometheus-port PORT` exposes a Prometheus-compatible `/metrics` endpoint. Loopback default, optional bearer-token auth, label cardinality bounded, two-Monitor isolation via per-Sink CollectorRegistry. | `pip install codegreen[prometheus]` |

## "I want to..."

- **Measure a one-liner Python script** -> [01](01_quickstart_measure.md)
- **Get a tight mean over many runs** -> [02](02_run_repeat.md)
- **Instrument a specific function inside a long Python program** -> [03](03_session_api.md)
- **Find energy hotspots in a Java project** -> [04](04_project_hotspots_java.md)
- **Profile staged ML inference (preprocess / load / generate)** -> [05](05_gpt2_staged.md)
- **Watch a daemon's energy in the background** -> [06](06_monitor_host.md)
- **Attribute system energy to a single PID** -> [07](07_monitor_pid.md)
- **Attribute energy to individual HTTP requests (single-process)** -> [08](08_monitor_socket.md)
- **Attach `codegreen monitor` to an already-running webapp from a separate process** -> [11](11_monitor_socket_standalone.md)
- **Keep the sidecar alive across terminal close / SSH drop / reboot** -> [12](12_monitor_systemd_sidecar.md)
- **Ship energy metrics to Datadog/Honeycomb/Grafana via OpenTelemetry** -> [13](13_monitor_otlp_export.md)
- **Expose a Prometheus-scrapeable /metrics endpoint** -> [14](14_monitor_prometheus_scrape.md)
- **Find energy hotspots in a Python project** -> [09](09_project_hotspots_python.md)
- **Sanity-check CodeGreen against the kernel** -> [10](10_codegreen_vs_perf.md)

## Attribution backends

Examples 07 and 08 surface CodeGreen's per-PID attribution. The Monitor
selects a backend at `start()`:

- **`cgroup_v2`** (preferred on Linux): reads `cpu.stat:usage_usec` from the
  PID's unified cgroup; share = `cgroup_cpu_delta / system_cpu_busy_delta`.
  Highly accurate even under heavy multi-tenant contention.
- **`cgroup_v1`** (fallback): same idea using `cpuacct.usage` (nanoseconds).
- **`cpu_percent`** (last resort): psutil `proc.cpu_percent / (100 * ncores)`;
  underestimates single-threaded workloads on many-core hosts because it
  normalizes against full system capacity.

!!! warning "cgroup_v2 vs cpu_percent divergence"
    On heavily-loaded multi-core hosts the two backends can disagree by
    **two orders of magnitude** on the same workload. Always check
    `attribution_backend` in the Monitor header before trusting per-PID
    energy.

The chosen backend appears as `attribution_backend` on every header and
summary record. Override with `Monitor(attribution_mode=...)` or
`codegreen monitor --attribution-mode ...`.

## Deep dives

Beyond the 14 canonical examples, the language-organized pages cover
patterns that don't fit a single script:

- [Python (manual + auto)](python.md) -- every `Session` form, plot export, per-domain attribution
- [C/C++](cpp.md) -- compilation chain, NEMB linkage
- [Java](java.md) -- `javac` integration, JNI bridge
