# Energy Measurement

How CodeGreen turns hardware energy counters into per-run and per-function
energy, and what limits the result.

## Which command

| You want to ... | Use | How energy is taken |
|---|---|---|
| Measure an unmodified command, repeated, with statistics | [`codegreen run`](cli-reference.md#run) | Counters read at the start and end of every run |
| Per-function energy of one source file | [`codegreen measure`](cli-reference.md#measure) | Checkpoints at function entry and exit, interpolated in the sampled series |
| Per-function energy of a project with its own build | [`codegreen project`](project-profiling.md) | As `measure`, across every source file |
| Regions inside a Python program | [`codegreen.Session`](../api/python.md#manual-api-codegreensession) | Counters read at each task boundary |
| A service that is already running | [`codegreen monitor`](continuous-monitoring.md) | Periodic counter reads, optionally attributed to a PID or to requests |

## Providers and sensors

NEMB (the Native Energy Measurement Backend, `libcodegreen-nemb`) reads
energy through providers: `intel_rapl` (Linux powercap, Intel and AMD CPUs),
`amd_rapl` (AMD RAPL MSRs), `nvidia_gpu` (NVML) and `amd_gpu` (ROCm SMI) on
Linux, IOReport on macOS and EMI on Windows. See
[Installation](../getting-started/installation.md#hardware-sensors) for their
requirements.

`--sensors` (on `measure`, `run` and `project`) and
`measurement.default_sensors` choose which providers are summed: `rapl`,
`amd_cpu`, `nvidia`, `amd_gpu`. The default `"all"` sums every provider that
initializes, so on a GPU host the total includes GPU energy and carries the
warning `GPU_IN_TOTAL`. Use `--sensors rapl` for the CPU package alone.

The total sums non-overlapping counters only. For RAPL that is the package
zones plus DRAM where the CPU exposes it (or the psys zone alone, when
present); `core` and `uncore` lie inside the package and are reported as
domains but never added. AMD CPUs have no DRAM counter. Domain breakdowns
(`domains` in `run` and `Session` reports) therefore do not sum to the total;
`meta.domain_topology` says which domains are top-level.

RAPL, NVML and the other counters are system-wide: they include every
process on the package or device, not just the measured one. Measure on an
otherwise idle machine and do not run two measurements at the same time.

## How `measure` and `project` attribute energy

1. Inside the measured process, a background NEMB thread reads the selected
   providers every `measurement.nemb.coordinator.measurement_interval_ms`
   (default 10 ms) into a ring buffer of cumulative energy. The buffer is
   seeded with a reading before the thread starts and closed with one at
   exit, so every checkpoint lies between two real readings.
2. A checkpoint call records only a timestamp and a name; it does not read a
   counter. In CPython an instrumented call costs about 1 µs on an AMD EPYC
   9554P (1.27 million checkpoints added 1.2 s to a 0.4 s program).
3. At exit, each checkpoint's cumulative energy is linearly interpolated
   between the two readings that bracket it. A checkpoint outside the
   sampled range is flagged (`clamp`) and the run is invalid
   (`MARKER_CLAMPED`).
4. Calls are replayed on per-thread stacks: a call's inclusive energy is the
   difference between its exit and entry values, and its exclusive energy
   subtracts its instrumented callees.

`run` and `Session` read the counters directly at each boundary instead, so
their windows do not depend on the sampler interval (except for providers
that only report power, whose energy is integrated from the samples).

## Resolution

A window can be resolved only to the update interval of its slowest
selected provider or the sampler interval, whichever is larger. Each
provider reports its update interval in `sampler.providers[].update_interval_ms`;
on an AMD EPYC 9554P with an NVIDIA RTX 5000 Ada, RAPL updates every 1 ms and
NVML about every 100 ms. With the default 10 ms sampler:

| Result | Requirement (defaults) | Otherwise |
|---|---|---|
| `measure` / `project` root window | at least 2 sampler readings | `TOTAL_BELOW_RESOLUTION` (invalid) |
| Per-function `measured` | mean call at least 10 resolutions, and at least 10 readings in every call | `aggregate_only` (summed time at least 10 resolutions) or `below_resolution` |
| `run` | mean run at least 10 update intervals of the finest selected provider | `RUN_BELOW_RESOLUTION` (invalid) |
| `Session` task | at least 10 resolutions | warning `TASK_BELOW_RESOLUTION` |

Including a GPU provider widens the per-function resolution to its update
interval: with `"all"` on that host, a 0.73 s `main()` is
`below_resolution`, while with `--sensors rapl` it is `measured`.
The thresholds are in
[`measurement.report.validity`](configuration-reference.md#measurement-validity).

## Validity

Each result carries a `validity` verdict built from the sampler statistics
and the providers' own facts: CPU affinity, reading gaps, buffer wrap,
clamped checkpoints, window length, failed or stalled providers and zero or
negative energy. `measure`, `run` and `project` exit 3 on an invalid result.
The codes are listed under
[Exit codes and measurement validity](cli-reference.md#exit-codes-and-measurement-validity).

- Do not pin the measured process to one CPU: the sampler thread runs inside
  it and competes with the workload (`AFFINITY_SINGLE_CPU`, and usually
  `SAMPLER_STARVED`).
- Choose sensors explicitly on hosts with a GPU.
- Make measured windows long enough (see above); repeat short commands with
  `codegreen run --repeat N`.
- Read each function's `quality` before comparing functions.

## Granularity

| Mode | Instrumented | Use |
|---|---|---|
| `coarse` (default for `measure`) | The entry function's frame only | Whole-program energy with two checkpoints |
| `fine` (default for `project`) | Every function the language config matches | Per-function breakdown |

A fine run that records fewer than two checkpoints (all work at module level
or in child processes) is re-measured at coarse granularity, and
`instrumentation_audit.fallback_to_coarse` is `true`.

## Checkpoint throttling

`CODEGREEN_CHECKPOINT_THROTTLE_MS=N` makes the Python runtime drop a
checkpoint that repeats within N ms of the previous one with the same id.
It reduces overhead for very hot functions, but entry and exit checkpoints
are throttled independently, so the throttled functions lose most of their
calls and their energy is attributed to their callers. The result is still
reported as valid; use it only to locate coarse hotspots.

## Comparing with `perf`

`codegreen benchmark` runs programs under CodeGreen and `perf stat` RAPL and
compares the readings (it needs the Benchmarks Game sources in a source
checkout; see [CLI Reference: `benchmark`](cli-reference.md#benchmark)).
[Example 10](../examples/10_codegreen_vs_perf.md) does the same comparison
with `codegreen run` and `perf stat` directly.
