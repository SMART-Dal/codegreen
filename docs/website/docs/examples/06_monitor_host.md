# 06 - Monitor host

Sample host-wide energy for a fixed duration with `codegreen monitor` and
read the result from the JSON summary and the JSONL stream. Use this shape
for a service you cannot modify, or to record the baseline load of a host.

## What you learn

- Running `codegreen monitor` for a bounded window (`-d`, `-i`).
- The JSONL stream (`header`, `sample`, `summary` records) and the
  `--json` summary.

## Prerequisites

- `pip install codegreen`
- A working energy provider (`codegreen capabilities energy`).

## Source

[`examples/06_monitor_host/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/06_monitor_host/main.py)

```python
--8<-- "examples/06_monitor_host/main.py"
```

## Run

```bash
python examples/06_monitor_host/main.py
```

The script runs:

```bash
codegreen monitor -d 3 -i 250 -o energy.jsonl --quiet --json
```

## Output

From a run on an AMD EPYC host with an NVIDIA GPU (default sensors, so the
GPU is in the total); energy depends on the host:

```text
OK: monitor_host; duration_s=3.00; total_joules=251.925; samples=11; jsonl_samples=11
```

Energy is host-wide: every process on the machine is in the total, and two
monitors on one host observe the same joules. The
[Continuous Monitoring guide](../user-guide/continuous-monitoring.md)
documents every record and summary field.

See also: [07 - Monitor PID](07_monitor_pid.md).
