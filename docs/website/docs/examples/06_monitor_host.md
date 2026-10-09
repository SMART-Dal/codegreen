# 06 - Monitor host

Run `codegreen.Monitor` (or `codegreen monitor`) to **continuously sample
host-wide energy** without launching a workload. Useful for already-running
daemons (Apache, gunicorn, system services) where you can't embed a Session.

## What you learn

- `codegreen.Monitor(interval_ms=...)` programmatic form.
- The shape of each sample: `t`, `joules_total`, `joules_delta`, `watts`.
- How to stream samples to a JSONL file for offline analysis.

## Prerequisites

- `pip install codegreen`
- A backend (RAPL on Linux, IOReport on macOS, EMI on Windows).

## Source

[`examples/06_monitor_host/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/06_monitor_host/main.py)

```python
--8<-- "examples/06_monitor_host/main.py"
```

## Run

```bash
python examples/06_monitor_host/main.py
```

## Equivalent CLI

```bash
codegreen monitor -d 3 -i 200 -o host.jsonl
```

## Expected output

```
OK: monitor_host; duration_s=3.00; total_joules=0.453; samples=12; jsonl_samples=12
```

## Why it matters

Continuous monitoring closes the gap between **measurement** (you wrote the
code, you bracket it) and **observation** (you didn't write the daemon,
you still want to know its energy footprint). The Monitor pulls cumulative
energy out of the NEMB backend at a fixed interval and computes deltas, so
you can plot host power over arbitrary windows.

!!! warning "RAPL is system-wide"
    Monitor reports the host's total CPU package energy. Two Monitor
    processes on the same socket will both observe the same Joules --
    they don't subtract each other out.

See also: [User guide: Continuous Monitoring](../user-guide/continuous-monitoring.md),
[07 - Monitor PID](07_monitor_pid.md).
