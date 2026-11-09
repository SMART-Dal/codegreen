# 03 - Session API

Measure regions inside a running Python program with `codegreen.Session`
instead of the whole process. The example uses two of the three task forms:
explicit `start_task` / `stop_task` and the `@codegreen.task` decorator
(the third is `with s.task(...)`).

`codegreen run` covers the whole process, including interpreter start-up and
imports. A Session reads the same counters in-process, only at the
boundaries of the tasks you mark, and writes a JSON report without spawning
a child process.

## Prerequisites

- `pip install codegreen` and a working energy backend.
- One Session per process: a second `Session` raises `RuntimeError` while
  the first is active.

## Source

[`examples/03_session_api/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/03_session_api/main.py)

```python
--8<-- "examples/03_session_api/main.py"
```

## Run

```bash
python examples/03_session_api/main.py
```

Output with `measurement.default_sensors` set to `["rapl"]`:

```text
.../codegreen_runtime.py:1431: RuntimeWarning: codegreen: TASK_BELOW_RESOLUTION: 1 task(s) shorter than 10 provider resolutions (first ['warmup']): their energy is not resolved
OK: session_api; tasks=2; total_energy_j=8.1415; hot_loop_result=2666664666667000000
```

The report is also written to `codegreen_<pid>.json` in the working
directory, with the top-level keys `meta`, `tasks`, `totals`, `sampler` and
`validity`. The `warmup` task lasted 1.2 ms, under ten RAPL update intervals,
so `validity.warnings` names it in `TASK_BELOW_RESOLUTION`; its energy is
reported but not resolved. `stop()` also raises every validity reason and
warning as a Python `RuntimeWarning`.

See also: [Python API: Session](../api/python.md#manual-api-codegreensession),
[Python deep dive](python.md),
[05 - GPT-2 staged](05_gpt2_staged.md) for the same API on an ML workload.
