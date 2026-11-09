# Quick Start

From install to a per-function energy reading. Runnable single-purpose
scripts are in the [Examples](../examples/index.md); every option is in the
[CLI Reference](../user-guide/cli-reference.md).

## 1. Install and set up sensors

```bash
pip install codegreen
sudo codegreen init-sensors     # Linux only; log out and back in afterwards
codegreen doctor                # lists each energy provider and whether it initializes
```

See [Installation](installation.md) for platforms and source builds.

## 2. Measure a script

`sums.py`:

```python
def square_sum(n):
    return sum(i * i for i in range(n))

def cube_sum(n):
    return sum(i * i * i for i in range(n))

def main():
    for _ in range(3):
        square_sum(3_000_000)
    cube_sum(3_000_000)

if __name__ == "__main__":
    main()
```

```console
$ codegreen measure python sums.py -g fine --sensors rapl
...
Energy: 56.2122 J
Time:   0.7196 s
Power:  78.12 W

  Function                         Excl J     Incl J    Calls  Quality
  square_sum                      36.1288    36.1288        3  measured
  cube_sum                        20.0799    20.0799        1  measured
  main                             0.0034    56.2122        1  measured
Validity: valid
```

(AMD EPYC 9554P, Linux.) `-g fine` instruments every function; the default
`coarse` instruments only the entry function. `Incl J` is a function's energy
including its callees, summed over all calls; `Excl J` excludes callees, so
the exclusive column partitions the run. `Quality` says whether a function ran
long enough to be resolved (see [Per-function quality](../user-guide/cli-reference.md#per-function-quality)).

## 3. Get a trustworthy number

- **Choose the sensors.** Without `--sensors`, CodeGreen sums every provider
  that initializes (`measurement.default_sensors` is `"all"`), so on a host
  with a GPU the total includes GPU energy and carries the warning
  `GPU_IN_TOTAL`. `--sensors rapl` measures the CPU package only. To make that
  the default, set `measurement.default_sensors` to `["rapl"]`
  ([Configuration](configuration.md)).
- **Check the verdict.** Every result ends with `Validity: valid`, or with
  `invalid_measurement:` and the reasons. An invalid measurement exits with
  code 3 instead of 0.
- **Measure long enough.** The NEMB sampler reads the counters every 10 ms.
  The measured window must span at least 2 readings, and a function is
  `measured` only when each call spans at least 10 readings (about 100 ms);
  shorter functions are `aggregate_only` or `below_resolution`. A run that is
  too short is invalid:

```console
$ codegreen measure python short.py --sensors rapl     # main() sums 10 000 integers
...
Energy: 0.0000 J
Time:   0.0001 s
Power:  0.00 W

  Function                         Excl J     Incl J    Calls  Quality
  main                             0.0000     0.0000        1  below_resolution
invalid_measurement: TOTAL_BELOW_RESOLUTION,ZERO_ENERGY
  TOTAL_BELOW_RESOLUTION: root window spans 0 reading(s) < 2
  ZERO_ENERGY: root window measured 0 J
$ echo $?
3
```

For short commands, repeat them with `codegreen run` instead. The reason
codes are listed under [Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity).

## 4. Other ways to measure

Any command, repeated, with statistics (no instrumentation):

```bash
codegreen run --repeat 10 --sensors rapl -- python3 sums.py
codegreen run --budget 10.0 --json -- python3 train.py   # exit 1 above 10 J mean
```

Regions inside a Python program, without the CLI:

```python
import codegreen

with codegreen.Session("training") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train()
# writes codegreen_<pid>.json with per-task energy and per-domain breakdown
```

C, C++ and Java single files (script arguments follow the file):

```bash
codegreen measure cpp main.cpp 5000
codegreen measure c algorithm.c
codegreen measure java Main.java
```

A multi-file project with its own build, a running service, or an energy
timeline plot:

```bash
codegreen project python ./src -r "python3 main.py" --sensors rapl
codegreen monitor --pid 1234 -d 60 -o energy.jsonl
codegreen measure python sums.py -g fine --export-plot energy.html
```

## How `codegreen measure` works

1. Tree-sitter parses the source and finds function boundaries.
2. A checkpoint call is inserted at each function entry and exit.
3. Inside the measured process, a background NEMB thread reads the energy
   counters every `measurement.nemb.coordinator.measurement_interval_ms`
   (default 10 ms) into a ring buffer.
4. A checkpoint records only a timestamp. At process exit each checkpoint is
   placed between the two readings that bracket it and its cumulative energy
   is linearly interpolated.
5. The energy of a call is the difference between its exit and entry values.

`codegreen.Session` skips steps 1 and 2: you mark the regions, and task
boundaries read the counters directly.

## Next steps

- [Examples](../examples/index.md): runnable single-purpose scripts
- [CLI Reference](../user-guide/cli-reference.md): every command and option
- [Python API](../api/python.md): `Session`, `Monitor` and the output schema
- [Project Profiling](../user-guide/project-profiling.md): per-function hotspots across a project
- [Continuous Monitoring](../user-guide/continuous-monitoring.md): running services
- [CI/CD Integration](../user-guide/cicd-integration.md): energy budgets in pipelines
