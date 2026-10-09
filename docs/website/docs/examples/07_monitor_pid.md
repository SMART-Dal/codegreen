# 07 - Monitor PID

Attribute system energy to **a specific process tree**, using cgroup_v2
where available and psutil cpu_percent as a fallback. Demonstrates the
two-orders-of-magnitude difference these backends can produce on a busy
multi-core host.

## What you learn

- `Monitor(pid=..., attribution_mode="auto")` PID attribution.
- The `attribution_backend` field on every sample.
- Why cgroup_v2 is dramatically more accurate than cpu_percent under
  contention.

## Prerequisites

- `pip install codegreen psutil`
- Linux with cgroup_v2 unified hierarchy for the high-accuracy backend.

## Source

[`examples/07_monitor_pid/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/07_monitor_pid/main.py)

```python
--8<-- "examples/07_monitor_pid/main.py"
```

## Run

```bash
python examples/07_monitor_pid/main.py
```

## Equivalent CLI

```bash
# Auto: cgroup_v2 if available, then cgroup_v1, then cpu_percent
codegreen monitor --pid 1234 -d 30 -o pid.jsonl

# Force a specific backend (useful for benchmarking)
codegreen monitor --pid 1234 --attribution-mode cgroup_v2
codegreen monitor --pid 1234 --attribution-mode cpu_percent
```

## Expected output

```
OK: monitor_pid; backend=cgroup_v2; cgroup_j=12.421; cpu_pct_j=0.197; delta_pct=6213.71
```

## Why it matters

System RAPL is per-socket, **not** per-process. To attribute a slice of
that system energy to your service, you need a per-process CPU usage
counter. cgroup_v2's `cpu.stat` is monotonic, kernel-attested, and
race-free; psutil cpu_percent is a sampled estimate that normalises against
full system capacity (so a single-threaded burner on a 64-core host
appears as 1.5% of the system instead of 100% of one core).

!!! tip "Always check `attribution_backend`"
    If the header says `cpu_percent`, treat the per-PID joules as a
    lower-bound estimate -- the real number can be 100x higher on a
    many-core idle host.

See also: [User guide: Continuous Monitoring](../user-guide/continuous-monitoring.md#per-pid-attribution),
[08 - Monitor socket](08_monitor_socket.md).
