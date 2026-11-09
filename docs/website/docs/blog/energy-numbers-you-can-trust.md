---
title: Your energy numbers may be wrong. CodeGreen 0.5.0 tells you when.
description: CodeGreen 0.5.0 attaches a validity verdict to every energy measurement and exits with code 3 when it cannot stand behind the number.
date: 2026-11-06
---

# Your energy numbers may be wrong. CodeGreen 0.5.0 tells you when.

*CodeGreen team, November 2026*

Here is a command that finishes in under two milliseconds, measured ten times:

```bash
codegreen run --sensors rapl --json -- true | jq -c '{error, readings_j: [.runs.energies_j[] | .*1000 | round/1000]}'
```

```text
{"error":"invalid_measurement: RUN_BELOW_RESOLUTION","readings_j":[0.139,0.131,0.155,0.155,0.078,0.155,0.155,0.155,0.155,0.078]}
```

Most readings land on one of two values, and one is about twice the other. That pattern is the sensor's step size, not your command's energy. CodeGreen still shows you the readings, marks the result invalid, and exits with code 3.

**A number that comes back is not always a number the sensor resolved.**

The CPU energy counters on Intel and AMD (RAPL) update about once per millisecond. A 1.8 ms command spans one or two counter updates, so each reading mostly counts how many updates landed inside the window. Averaging ten of them gives a steady-looking mean of a rounding artifact.

## Plausible numbers, silent failures

A tool that reads an energy counter will almost always hand back a number. The failure modes below produce numbers that look fine, and we know them well because CodeGreen 0.4 had several of them. As of 0.5.0, each one is detected and named:

| What goes wrong | What you would see | What CodeGreen 0.5.0 reports |
|---|---|---|
| The measured window is shorter than the sensor can resolve | A small, stable, meaningless number | `RUN_BELOW_RESOLUTION` (`run`), `TOTAL_BELOW_RESOLUTION` (`measure`, `project`) |
| The process is pinned to one CPU and the sampler thread waits behind the workload | Per-function energy interpolated across long gaps | `SAMPLER_STARVED`, with the warning `AFFINITY_SINGLE_CPU` |
| A function boundary falls outside the sampled range | The edge reading, used silently | `MARKER_CLAMPED` |
| A sensor read fails or stalls mid-run | A 0 J or negative reading folded into the total | `PROVIDER_READ_FAILED`, `PROVIDER_STALLED`, `ZERO_ENERGY`, `NEGATIVE_ENERGY` |
| Another process polls the GPU's power while you measure | GPU energy silently lost | `COUNTER_INTEGRAL_DIVERGED` |
| The GPU is summed into a CPU number | A "CPU energy" figure that includes the GPU | The warning `GPU_IN_TOTAL` |

One more failure mode needs no flag because CodeGreen prevents it. On AMD Linux hosts, the same package counter is reachable through two interfaces, and a tool that sums every interface it finds reports double. CodeGreen groups energy providers by the physical counter they read and keeps one per group.

## What CodeGreen is

CodeGreen is an open-source energy profiler for code. It reads hardware energy counters directly: RAPL on Intel and AMD CPUs under Linux, IOReport on Apple Silicon, NVML on NVIDIA GPUs and ROCm on AMD GPUs. It measures in three ways:

- `codegreen run` measures any command with repeats, warmups, confidence intervals and an energy budget.
- `codegreen measure` and `codegreen project` instrument your source and attribute energy to individual functions in Python, Java, C, C++ and JavaScript.
- `codegreen monitor` and the `Session` Python API measure services and code regions without a wrapper process, with Prometheus and OTLP export.

Since 0.5.0, all of them share one validity policy, and every result carries a `validity` block: `status`, the fatal `reasons`, a `detail` line per reason, and non-fatal `warnings`.

## Try it

```bash
pip install --upgrade codegreen
sudo codegreen init-sensors   # Linux only, one time; log out and back in
```

Pre-built wheels cover Linux (x86_64 and aarch64), macOS on Apple Silicon and Windows x86_64, for Python 3.10 to 3.13. Other platforms build from source.

A workload long enough for the sensor produces a valid result and exit code 0. `--sensors rapl` keeps the total to CPU package energy:

```bash
codegreen run --repeat 5 --sensors rapl -- python3 work.py
echo $?
```

```text
Energy: 81.7459 J +/- 0.4926 J
  Range: [81.3402 .. 82.3171] J
  CI95:  [81.1344, 82.3574] J (1.5% width)
  CV:    0.6% (excellent)
Time:   1.0506 s +/- 0.0058 s
  Runs: 5
Validity: valid
0
```

Here `work.py` builds a two-million-word string and counts the words three times. To see which function spends the energy, instrument it:

```bash
codegreen measure python work.py -g fine --sensors rapl
```

```text
Energy: 77.0714 J
Time:   0.9940 s

  Function                         Excl J     Incl J    Calls  Quality
  count_words                     56.6600    56.6600        3  measured
  build_text                      20.3886    20.3886        1  measured
  main                             0.0229    77.0714        1  measured
Validity: valid
```

Each function carries a `quality` label. A function too short for the sensor reads `below_resolution` instead of a confident number.

## Watch it refuse

Pinning is common in benchmarking and CI. Here, `crunch.py` runs a four-process pool, pinned to CPU 0 with `taskset`:

```bash
taskset -c 0 codegreen measure python crunch.py --sensors rapl
```

```text
Energy: 174.4757 J
Time:   2.2553 s

  Function                         Excl J     Incl J    Calls  Quality
  main                           174.4757   174.4757        1  measured
invalid_measurement: SAMPLER_STARVED
  SAMPLER_STARVED: reading gaps median 10.056 ms, max 43.544 ms vs interval 10 ms (interpolated)
  WARNING AFFINITY_SINGLE_CPU: measured process allowed on 1 CPU(s) (< 2); the sampler competes with the workload
```

The sampler should read the counter every 10 ms. With the workload holding the only CPU, one gap reached 44 ms, and any energy interpolated across that gap is a guess. The process exits with code 3. The verdict depends on scheduling: on our quiet test host, 6 of 19 pinned runs came back invalid, and the other 13 passed with the `AFFINITY_SINGLE_CPU` warning attached. The fix is to give the measured process at least two CPUs.

## Check it against perf

You should not take any energy tool on faith, including this one. `perf stat` reads the same RAPL package counter through the Linux kernel, so the two should agree. This command measures the same five executions with both tools, `perf` nested inside CodeGreen:

```bash
codegreen run --repeat 5 --warmup 0 --no-validate --sensors rapl --json -- \
  perf stat -x, -e power/energy-pkg/ -o perf.csv --append -- \
  python3 -c "print(sum(i*i for i in range(160_000_000)))" > cg.json
paste <(jq -r '.runs.energies_j[]' cg.json) <(grep Joules perf.csv | cut -d, -f1) \
  | awk '{printf "codegreen %8.2f J   perf %8.2f J   ratio %.4f\n", $1, $2, $1/$2}'
```

```text
codegreen   773.84 J   perf   772.29 J   ratio 1.0020
codegreen   779.40 J   perf   777.73 J   ratio 1.0022
codegreen  1107.09 J   perf  1105.36 J   ratio 1.0016
codegreen   834.16 J   perf   832.49 J   ratio 1.0020
codegreen   931.22 J   perf   929.49 J   ratio 1.0019
```

On 10-second CPU-bound runs (AMD EPYC 9554P, package energy, performance governor), CodeGreen read 0.16% to 0.22% more than `perf` on every run, including one run that drew far more energy than the rest. That gap is `perf` itself: CodeGreen's window also contains `perf` starting and exiting, which measured about 1.8 J on its own. Agreement shows that CodeGreen reads, scales and sums the counter correctly. It cannot show that RAPL matches a wall meter, because both tools read the same counter. Run this check after kernel, BIOS or CodeGreen upgrades.

## Another process can steal GPU energy

On NVIDIA GPUs, CodeGreen reads the cumulative energy counter at run boundaries and checks it against its own power integral. A clean three-second run passes:

```bash
codegreen run --sensors nvidia --repeat 3 -- python3 -c "import time;time.sleep(3)"
```

```text
Energy: 68.1980 J +/- 0.7590 J
Validity: valid
```

Repeat it while `nvidia-smi --query-gpu=power.draw.instant --format=csv -lms 10` polls in another terminal, and the counter loses most of its energy:

```text
Energy: 5.4787 J +/- 0.2027 J
invalid_measurement: COUNTER_INTEGRAL_DIVERGED
```

The detail line names the cause: another process reading the counter or instant power. Nothing in the 5.5 J figure itself tells you it is about 92% short of the clean run.

## Gate CI on validity, not only on budget

`--budget` fails a run whose mean energy exceeds a limit. Exit code 3 adds a second gate, so a pipeline never compares an invalid measurement against a budget:

```bash
codegreen run --repeat 10 --sensors rapl --budget 120 --json -- python3 work.py > energy.json
case $? in
  0) echo "energy OK: $(jq .energy_j.mean energy.json) J" ;;
  3) jq -r .error energy.json; exit 1 ;;
  *) echo "over budget or workload failed"; exit 1 ;;
esac
```

Exit code 0 means valid and within budget, 1 means over budget or a failed build or run, and 3 means the measurement is invalid. The JSON keeps every run's signed reading and status, so a reviewer can see why a gate failed.

## Beyond a single command

The same validity policy covers the rest of the toolkit:

```bash
# Per-function hotspots for a whole project: instrument, build, run, attribute
codegreen project python ./wordcount -r "python3 work.py" -s "**/*.py" --sensors rapl

# Host energy for 30 s, written as JSON lines
codegreen monitor -d 30 -o energy.jsonl

# Continuous export: codegreen_energy_joules_total and codegreen_power_watts
codegreen monitor --exporter prometheus --prometheus-port 9464
```

To measure regions of a Python program without the CLI, use a `Session`. It writes a JSON report with per-task energy and the same `validity` block, and raises each reason or warning as a Python `RuntimeWarning`:

```python
import codegreen
from work import build_text, count_words

with codegreen.Session("wordcount") as s:
    with s.task("build_text"):
        text = build_text(2_000_000)
    with s.task("count_words"):
        count_words(text)
```

## Limits worth knowing

- **RAPL is per socket, not per process.** Anything else running on the machine lands in your number. Use a quiet host and repeats, or `codegreen monitor --pid` for per-process attribution through cgroups.
- **AMD CPUs expose no DRAM energy counter.** Memory energy is missing from AMD results.
- **Threads share the package.** Concurrent threads inside instrumented functions are each charged the whole package energy (`OVERLAPPING_THREADS`), so exclusive energies can sum above the total.
- **Platform coverage varies.** On Windows, RAPL energy needs Windows 11 on an Intel CPU, and AMD CPUs on Windows and Windows 10 expose no counter. Without a supported sensor, CodeGreen falls back to time only.
- **The default total includes every sensor.** `measurement.default_sensors` is `"all"`, so a GPU joins the total and the result carries `GPU_IN_TOTAL`. Pass `--sensors rapl` for CPU-only numbers.

## Upgrading from 0.4

Three changes can affect existing scripts. `measure`, `run` and `project` now exit 3 on an invalid measurement, so read `validity.reasons` or set `measurement.report.validity.fail_on_invalid` to `false` to report without failing. Per-function `energy_j` is now inclusive energy summed over every call, so use `exclusive_j` when you want a partition of the run. An unparsable config file now raises instead of falling back to defaults. The [changelog](../about/changelog.md#upgrading-from-04x) lists the rest.

## Get started

```bash
pip install --upgrade codegreen
codegreen --version
```

- [Quick Start](../getting-started/quickstart.md) gets you from install to a first measurement.
- [Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity) lists every reason code.
- [CodeGreen vs perf](../examples/10_codegreen_vs_perf.md) packages the cross-check as a script.
- The source is on GitHub at [SMART-Dal/codegreen](https://github.com/SMART-Dal/codegreen), under MPL-2.0.

If CodeGreen calls a measurement invalid and you think it is wrong, or accepts one it should have refused, open an issue with the `--json` output. That block was built to make such reports easy to check.
