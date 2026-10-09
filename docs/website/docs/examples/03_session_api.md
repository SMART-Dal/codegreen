# 03 - Session API

Use `codegreen.Session` from inside a long-running Python program to attribute
energy to **specific code regions** instead of the whole subprocess. Shows
the context-manager form and the `@codegreen.task` decorator side-by-side.

## What you learn

- `codegreen.Session("name")` as a top-level context.
- `with s.task("region"):` to bracket a region.
- `@codegreen.task("name")` to bracket a whole function.
- Where the per-task JSON lands on disk (`codegreen_<pid>.json`).

## Prerequisites

- `pip install codegreen` and a working backend (Linux RAPL / macOS IOReport).
- One Session per process -- the CLI wrapper and this API cannot overlap.

## Source

[`examples/03_session_api/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/03_session_api/main.py)

```python
--8<-- "examples/03_session_api/main.py"
```

## Run

```bash
python examples/03_session_api/main.py
```

## Expected output

```
OK: session_api; tasks=2; total_energy_j=0.9320; hot_loop_result=1333332333333000000
```

A `codegreen_<pid>.json` is left in the working directory with the full
per-task breakdown, per-domain energy, and metadata.

## Why it matters

`codegreen run` measures *the whole subprocess*, including interpreter
startup and imports. For libraries and ML scripts you usually only care
about the inner region. Session API brackets just that region, reads the
same RAPL/NVML counters in-process, and writes a structured JSON without
spawning a child process.

See also: [Python API: Session](../api/python.md#manual-api-codegreensession),
[05 - GPT-2 staged](05_gpt2_staged.md) for the same API on a real ML workload.
