# 10 - CodeGreen vs perf

Cross-validate CodeGreen's reported mean energy against `perf stat
power/energy-pkg/` on the same workload. If the two disagree by more than a
few percent, something is wrong on this host.

## What you learn

- How to read `perf stat -j -e power/energy-pkg/` Joules.
- How to compare it to `codegreen run --json` `energy_j.mean`.
- The expected relative error on a well-behaved RAPL system (< 1% on
  Skylake-SP and EPYC Zen 4 from our benchmark suite).

## Prerequisites

- `pip install codegreen`
- `perf` on PATH (`sudo apt install linux-tools-common linux-tools-generic`).
- Either `sudo` (recommended) or `kernel.perf_event_paranoid <= 2`.

## Source

[`examples/10_codegreen_vs_perf/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/10_codegreen_vs_perf/main.py)

```python
--8<-- "examples/10_codegreen_vs_perf/main.py"
```

## Run

```bash
python examples/10_codegreen_vs_perf/main.py
```

## Expected output

```
OK: codegreen_vs_perf; codegreen_j=0.8123; perf_j=0.8087; delta_pct=0.45
```

## Why it matters

`perf stat` is the kernel's own RAPL frontend. If CodeGreen's number
diverges from `perf` by more than 5%, you're likely seeing one of:

- a **multi-Monitor double-count** (another `codegreen monitor` running),
- a **DRAM domain mismatch** (`perf` includes DRAM, CodeGreen excludes it
  or vice versa -- check `meta.domain_topology`),
- a **wraparound bug** in the AMD provider (if you're not on a recent
  release).

This script is the canonical "is my measurement actually correct?" probe.
Run it after any kernel update, BIOS update, or CodeGreen upgrade.

See also: [User guide: Energy Measurement](../user-guide/energy-measurement.md#benchmark-accuracy),
[01 - Quickstart](01_quickstart_measure.md).
