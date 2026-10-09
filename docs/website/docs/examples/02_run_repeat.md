# 02 - Run with repeats

Get a tight mean and coefficient-of-variation across multiple runs of the
same command. Demonstrates the `--repeat` / `--warmup` knobs and the
outlier-removed statistics that ship with `codegreen run`.

## What you learn

- How `--warmup` discards the first N runs (filesystem cache, JIT, etc.).
- How `--repeat` builds a sample for mean / std / 95% CI.
- How to read `energy_j.mean`, `energy_j.std`, `energy_j.ci95`, and the
  outlier-removed counts.

## Prerequisites

- `pip install codegreen`
- Linux RAPL or macOS IOReport.

## Source

[`examples/02_run_repeat/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/02_run_repeat/main.py)

```python
--8<-- "examples/02_run_repeat/main.py"
```

## Run

```bash
python examples/02_run_repeat/main.py
```

## Expected output

```
OK: run_repeat; mean_energy_j=0.8123; cv_pct=2.40; n=5
```

## Why it matters

The killer feature of CodeGreen's CLI mode is **stable means without
manual scripting**. Hyperfine pioneered this for wall time; `codegreen run`
extends it to RAPL energy. A CV under 5% on a sub-second workload tells you
the measurement is repeatable. CV above 20% is a signal that the workload
is too short, the host is contended, or another CodeGreen session is
overlapping.

See also: [01 - Quickstart](01_quickstart_measure.md),
[CLI reference: `run`](../user-guide/cli-reference.md#run).
