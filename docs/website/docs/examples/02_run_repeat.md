# 02 - Run with repeats

Run the same command several times and report the mean energy and its
coefficient of variation (CV) with `codegreen run --repeat 5 --warmup 1`.

- `--warmup N` runs the command N times unmeasured first (file cache, JIT).
  Warmup runs never enter the statistics.
- `--repeat N` measured runs give the mean, standard deviation, min, max and
  95% confidence interval in `energy_j`, `duration_s` and `power_w`.
- Only runs that read a positive energy enter the statistics. Failed, zero
  or negative readings are listed in `runs.status` and make the result
  invalid (exit code 3); when no run reads energy, `run` exits 1.

## Prerequisites

- `pip install codegreen` and a working energy backend (see
  [Installation](../getting-started/installation.md)).

## Source

[`examples/02_run_repeat/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/02_run_repeat/main.py)

```python
--8<-- "examples/02_run_repeat/main.py"
```

## Run

```bash
python examples/02_run_repeat/main.py
```

```text
OK: run_repeat; mean_energy_j=14.5196; cv_pct=6.36; n=5
```

The JSON fields the script reads:

| Field | Meaning |
|---|---|
| `energy_j.mean` | Mean energy over the measured runs (J) |
| `energy_j.cv_percent_across_runs` | Standard deviation / mean, in percent |
| `runs.measurement_runs` | The `--repeat` value |
| `runs.energy_valid` | Runs that entered the statistics |

## Reading the CV

With three or more runs the text report labels the CV: excellent below 5%,
good below 15%, moderate below 30%, high noise above. A high CV usually means the workload is too
short, the host is busy, or another process reads the same counters. Raise
`--repeat`, lengthen the workload, or quiet the host. Outlier filtering is
off by default; `measurement.report.outlier_method: "iqr_<k>"` adds a
`filtered` block next to the unfiltered statistics.

See also: [01 - Quickstart](01_quickstart_measure.md),
[CLI reference: `run`](../user-guide/cli-reference.md#run).
