# 01 - Quickstart measure

Measure a Python one-liner with `codegreen run --repeat 3 --warmup 0 --json`
and read the mean energy from the JSON report.

`codegreen run` needs no code changes: it reads the energy counters at the
start and end of each run of the command. Everything after `--` is the
measured command, so its own flags (here `-c`) are not parsed as CodeGreen
options.

## Prerequisites

- `pip install codegreen`
- Linux: `sudo codegreen init-sensors` once, for RAPL read access.

## Source

[`examples/01_quickstart_measure/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/01_quickstart_measure/main.py)

```python
--8<-- "examples/01_quickstart_measure/main.py"
```

## Run

```bash
python examples/01_quickstart_measure/main.py
```

```text
OK: quickstart_measure; mean_energy_j=11.0099; mean_duration_s=0.1170
```

Without `--sensors`, `run` sums every available provider. On this host a
JSON run of the same command reported `domains` of `package-0` 8.99 J and
`gpu0` 1.82 J (mean 10.81 J), with two entries in `validity.warnings`:
`GPU_IN_TOTAL` (the total mixes CPU and GPU) and
`COARSE_PROVIDER_RESOLUTION` (a 0.12 s run is shorter than ten updates of the
GPU energy counter). The same command with `--sensors rapl` measures the CPU
package only:

```bash
codegreen run --repeat 3 --warmup 0 --sensors rapl -- python3 -c "sum(i*i for i in range(2_000_000))"
```

```text
Energy: 9.4852 J +/- 0.6531 J
  Range: [8.9796 .. 10.2225] J
  CI95:  [7.8627, 11.1076] J (34.2% width)
  CV:    6.9% (good)
Time:   0.1223 s +/- 0.0084 s
Power:  77.53 W (mean of per-run E/t)
  Runs: 3

Domain Breakdown (mean over runs):
  package-0                   9.4852 J    77.53 W  ====================
  core                        0.0022 J     0.02 W
Validity: valid
```

## Next

- Exit codes: `run` exits 3 when the measurement is invalid and 1 when
  `--budget` is exceeded; see
  [Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity).
- [02 - Run with repeats](02_run_repeat.md) for tighter statistics,
  [CLI reference: `run`](../user-guide/cli-reference.md#run) for every flag.
