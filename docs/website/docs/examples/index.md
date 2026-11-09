# Examples

Fourteen runnable examples ship in the repository under
[`examples/`](https://github.com/SMART-Dal/codegreen/tree/main/examples).
Each page embeds the script and shows its expected output.

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
python examples/01_quickstart_measure/main.py
```

Every script calls the `codegreen` CLI or API on `PATH` and prints one
`OK: <feature>; <metrics>` line, or `SKIP: <reason>` when an optional
dependency is missing. `pytest tests/test_examples.py -q` runs all of them;
05 runs only with `CODEGREEN_RUN_HEAVY_EXAMPLES=1`.

!!! note "Sensor selection"
    The scripts use the default sensor selection
    (`measurement.default_sensors`, `all`). On a host with a GPU the totals
    then include GPU energy and the report carries the `GPU_IN_TOTAL`
    warning. Pass `--sensors rapl` (CLI) or set `measurement.default_sensors`
    to `["rapl"]` for CPU-only numbers. The outputs shown on these pages come
    from an AMD EPYC 9554P host with an NVIDIA RTX 5000 Ada GPU; your numbers
    will differ.

## Index

| # | Example | What it shows | Prereqs |
|---|---------|---------------|---------|
| 01 | [Quickstart measure](01_quickstart_measure.md) | `codegreen run --json` on a one-liner | none |
| 02 | [Run with repeats](02_run_repeat.md) | `--repeat` / `--warmup`, mean, CI and CV | none |
| 03 | [Session API](03_session_api.md) | `codegreen.Session`, `start_task` / `stop_task`, `@codegreen.task` | none |
| 04 | [Project hotspots (Java)](04_project_hotspots_java.md) | `codegreen project java` per-method attribution | JDK |
| 05 | [GPT-2 staged inference](05_gpt2_staged.md) | Multi-task Session with time series and per-domain energy | `torch`, `transformers` |
| 06 | [Monitor host](06_monitor_host.md) | Host-wide sampling to JSONL | none |
| 07 | [Monitor PID](07_monitor_pid.md) | Per-PID attribution (cgroup or CPU share) | none |
| 08 | [Monitor socket (in-process)](08_monitor_socket.md) | Per-request energy over the UDS annotation channel | none |
| 09 | [Project hotspots (Python)](09_project_hotspots_python.md) | `codegreen project python` per-function attribution | none |
| 10 | [CodeGreen vs perf](10_codegreen_vs_perf.md) | Cross-check against `perf stat -e power/energy-pkg/` | `perf` |
| 11 | [Monitor socket (standalone)](11_monitor_socket_standalone.md) | `codegreen monitor` as a separate sidecar process | none |
| 12 | [Monitor systemd sidecar](12_monitor_systemd_sidecar.md) | The sidecar supervised by user-mode systemd | `systemctl --user` |
| 13 | [Monitor OTLP export](13_monitor_otlp_export.md) | `--exporter otlp` to an OpenTelemetry collector | `codegreen[otlp]` |
| 14 | [Monitor Prometheus scrape](14_monitor_prometheus_scrape.md) | `--exporter prometheus` `/metrics` endpoint | `codegreen[prometheus]` |

## Pick an example

| I want to... | Example |
|---|---|
| Measure any command, no code changes | [01](01_quickstart_measure.md) |
| Get a stable mean over many runs | [02](02_run_repeat.md) |
| Measure regions inside a Python program | [03](03_session_api.md) |
| Profile ML pipeline stages on CPU and GPU | [05](05_gpt2_staged.md) |
| Find per-function hotspots in a project | [04](04_project_hotspots_java.md) (Java), [09](09_project_hotspots_python.md) (Python) |
| Watch a host or a running process | [06](06_monitor_host.md), [07](07_monitor_pid.md) |
| Attribute energy to HTTP requests | [08](08_monitor_socket.md), [11](11_monitor_socket_standalone.md), [12](12_monitor_systemd_sidecar.md) |
| Export to an observability stack | [13](13_monitor_otlp_export.md), [14](14_monitor_prometheus_scrape.md) |
| Cross-check CodeGreen against the kernel | [10](10_codegreen_vs_perf.md) |

Per-PID attribution backends (`cgroup_v2`, `cgroup_v1`, `cpu_percent`) are
described in [Continuous Monitoring](../user-guide/continuous-monitoring.md#per-pid-attribution).

## Deep dives

- [Python](python.md): every `Session` form, time series and plots, `measure`
  per-function reports, before/after comparisons.
- [C/C++](cpp.md): single-file `codegreen measure c|cpp`.
- [Java](java.md): single-file `codegreen measure java`.
