# 10 - CodeGreen vs perf

Compare the mean energy of `codegreen run` with the kernel's own RAPL reading
from `perf stat -x , -e power/energy-pkg/` on the same Python workload.

## Prerequisites

- `pip install codegreen`
- `perf` on `PATH` with access to the `power/energy-pkg/` event (root, or a
  permissive `kernel.perf_event_paranoid`). Without it the script prints
  `SKIP:`.

## Source

[`examples/10_codegreen_vs_perf/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/10_codegreen_vs_perf/main.py)

```python
--8<-- "examples/10_codegreen_vs_perf/main.py"
```

## Run

```bash
python examples/10_codegreen_vs_perf/main.py
```

```text
OK: codegreen_vs_perf; codegreen_j=20.8444; perf_j=16.5600; delta_pct=25.87
```

The script compares like with like only on a host without a GPU. It calls
`codegreen run` without `--sensors`, so on a GPU host the CodeGreen mean
includes GPU energy while `energy-pkg` is the CPU package alone; the 26%
above is that difference. Restrict CodeGreen to RAPL for the comparison:

```bash
WORKLOAD=$'x=0\nfor i in range(2_000_000): x+=i*i\nprint(x)'
codegreen run --repeat 3 --warmup 1 --sensors rapl --json -- python3 -c "$WORKLOAD"
perf stat -x , -e power/energy-pkg/ python3 -c "$WORKLOAD"
```

Two such pairs on the same host gave 16.17 J vs 15.96 J and 16.56 J vs
15.73 J (CodeGreen mean of three runs vs one `perf` run).

## When they disagree

- Different scope: GPU or other providers in the CodeGreen total (check
  `domains` and `validity.warnings` for `GPU_IN_TOTAL`), or a different set
  of RAPL domains (check `meta.domain_topology`).
- Different samples: `perf` measures one run, CodeGreen the mean of
  `--repeat` runs. Short workloads vary from run to run; compare means over
  several runs of each.
- Another process on the host: RAPL is system-wide, so both tools count
  everything that ran during the window.

See also: [Energy Measurement](../user-guide/energy-measurement.md),
[01 - Quickstart](01_quickstart_measure.md).
