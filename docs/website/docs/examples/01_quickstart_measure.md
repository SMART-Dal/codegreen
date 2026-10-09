# 01 - Quickstart measure

The shortest possible CodeGreen example: wrap a one-liner Python workload
with `codegreen run --repeat 3 --warmup 0 --json` and read the mean energy
from the parsed JSON.

## What you learn

- The 30-second `codegreen run` shape for any shell command.
- The shape of the JSON output (`energy_j.mean`, `duration_s.mean`).
- Why `--` is required before `python3 -c "..."`.

## Prerequisites

- `pip install codegreen`
- On Linux: `sudo codegreen init-sensors` once (RAPL permissions).

## Source

[`examples/01_quickstart_measure/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/01_quickstart_measure/main.py)

```python
--8<-- "examples/01_quickstart_measure/main.py"
```

## Run

```bash
python examples/01_quickstart_measure/main.py
```

## Expected output

```
OK: quickstart_measure; mean_energy_j=0.7234; mean_duration_s=0.1421
```

## Why it matters

`codegreen run` is the **zero-instrumentation entry point**. No source
edits, no JNI, no AST -- it brackets the entire subprocess and reports
hardware RAPL energy with N-run statistics. For CI gating, replace the
ad-hoc parse with `--budget 5.0` to exit non-zero when the mean exceeds the
threshold.

See also: [CLI reference: `run`](../user-guide/cli-reference.md#run),
[02 - Run with repeats](02_run_repeat.md).
