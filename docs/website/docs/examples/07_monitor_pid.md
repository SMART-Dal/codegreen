# 07 - Monitor PID

Attribute a share of host energy to one process tree, and compare the
cgroup backend with the `cpu_percent` backend on the same workload.

## What you learn

- `Monitor(pid=..., attribution_mode=...)`.
- `attribution_backend` and `proc_attributed_joules` in the summary.
- Why the two backends give very different numbers on a mostly idle
  many-core host.

## Prerequisites

- `pip install codegreen psutil`
- Linux with cgroup v2 (or v1) for the cgroup backend.

## Source

[`examples/07_monitor_pid/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/07_monitor_pid/main.py)

```python
--8<-- "examples/07_monitor_pid/main.py"
```

The script runs a single-threaded loop twice and monitors each run for 3 s
at 200 ms, once with `attribution_mode="auto"` and once with
`"cpu_percent"`.

## Run

```bash
python examples/07_monitor_pid/main.py
```

Equivalent CLI:

```bash
codegreen monitor --pid 1234 -d 30 -o pid.jsonl                          # auto
codegreen monitor --pid 1234 -d 30 --attribution-mode cpu_percent
```

## Output

From a 128-CPU AMD EPYC host:

```text
{
  "cgroup_backend": "cgroup_v2",
  "cgroup_attributed_j": 274.614392,
  "cgroup_total_j": 301.054388,
  "cpu_percent_attributed_j": 2.198933,
  "cpu_percent_total_j": 301.168014,
  "delta_pct_vs_cpu_percent": 12388.53
}
OK: monitor_pid; backend=cgroup_v2; cgroup_j=274.614; cpu_pct_j=2.199; delta_pct=12388.53
```

## Reading the result

`cgroup_v2` gives the process its cgroup's share of the host's busy CPU
time: on an otherwise idle host the one busy process receives almost all
measured energy, idle and uncore power included. `cpu_percent` gives it
its share of total CPU capacity: one busy core of 128 is under 1 %. Neither
is wrong; they answer different questions, so always report
`attribution_backend` with the number.

The cgroup backends attribute the whole cgroup that contains the PID. A
process started from a login shell shares that cgroup with the rest of the
session; a systemd service or container has its own. See
[Per-PID attribution](../user-guide/continuous-monitoring.md#per-pid-attribution).

See also: [08 - Monitor socket](08_monitor_socket.md).
