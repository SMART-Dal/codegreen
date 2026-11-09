# Python deep dive

Python has three entry points, each measuring a different window:

| Entry point | Window | Code changes |
|---|---|---|
| `codegreen run -- python3 script.py` | The whole process, per run, with repeat statistics | none |
| `codegreen.Session` | The tasks you mark inside the process | a few lines |
| `codegreen measure python script.py` | `main` (coarse) or every function (`-g fine`) | none (instrumented copy) |

The [numbered examples](index.md) are short runnable scripts; this page
covers each entry point in more depth. Field-by-field schemas are in the
[Python API](../api/python.md). The outputs below come from an AMD EPYC
9554P host with `--sensors rapl` (or `measurement.default_sensors` set to
`["rapl"]`).

## `codegreen.Session` { #manual-measurement-with-codegreensession }

`Session` reads the energy counters at the start and end of each task in
the running process. No subprocess, no instrumentation.

### Task forms

```python
import codegreen

# 1. Context manager
with codegreen.Session("training-run") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train_model()

# 2. Explicit start/stop
s = codegreen.Session("pipeline").start()
s.start_task("preprocess")
preprocess()
s.stop_task("preprocess")      # optional name check: a mismatch raises RuntimeError
report = s.stop()              # the report dict; also written to codegreen_<pid>.json

# 3. Decorator: each call is one task of the active Session
@codegreen.task("inference")
def infer(batch): ...

with codegreen.Session("svc"):
    for b in batches:
        infer(b)
```

Tasks nest: a task opened inside another gets `depth` and `parent`, and
`totals` sum only depth-0 tasks.

### Reading results

`stop()` returns the report and writes it to `codegreen_<pid>.json` (or
`output_file=`; a `.csv` path writes one row per task). The report has the
top-level keys `meta`, `tasks`, `totals`, `sampler` and `validity`.
`s.tasks` gives the same tasks as `TaskResult` objects:

```python
for t in s.tasks:
    print(t.name, t.energy_j, t.avg_power_w, t.duration_s, t.domains)
```

Check `report["validity"]["status"]` before using the numbers. `stop()` also
raises each validity reason and warning as a `RuntimeWarning`
(`codegreen: CODE: text`). A task shorter than ten provider update
intervals, for example, is named in `TASK_BELOW_RESOLUTION`.

### Time series and plots

`record_time_series=True` stores the sampler readings inside each task
(sampler period `measurement.nemb.coordinator.measurement_interval_ms`,
10 ms by default). A sample from a CPU and GPU host:

```python
{'t_ns': 37131993282157589, 'energy_j': 48.3493825807655, 'power_w': 104.141271051358,
 'domain_j': {'core': 0.025084, 'package-0': 41.301301, 'gpu0': 7.0480815807655},
 'domain_w': {'core': 0.015189966917642, 'package-0': 78.9542710513576, 'gpu0': 25.187}}
```

`t_ns` is a monotonic timestamp, `energy_j` and `domain_j` are cumulative
from the start of the session, `power_w` and `domain_w` are averages since
the previous sample. Power and energy arrays for any plotting library:

```python
t = s.tasks[0]
ts = t.timeseries
times_s = [(p["t_ns"] - ts[0]["t_ns"]) / 1e9 for p in ts]
power_w = [p["power_w"] for p in ts]
gpu_w = [p["domain_w"].get("gpu0", 0.0) for p in ts]
```

Integrating `power_w` over the samples gives the energy between the first
and the last sample. A task's `energy_j` also covers the few milliseconds
before its first and after its last sample. In a two-task CPU run (0.89 s
and 1.80 s, 88 and 178 samples) the trapezoidal integral was 67.86 J vs
`energy_j` 68.86 J, and 137.80 J vs 138.82 J.

`Session.export_plot(path)` draws power over time, one trace per task. The
extension selects the format: `.html` (Plotly), `.png`, `.svg` or `.pdf`
(matplotlib); any other extension writes HTML to the path with `.html` as
its extension. Install the plotting
libraries with `pip install plotly matplotlib` (or the `viz` extra when
installing from source); without them, and without
`record_time_series=True`, `export_plot` writes nothing.

```python
with codegreen.Session("infer", record_time_series=True) as s:
    with s.task("batch1"):
        infer(batch1)
    with s.task("batch2"):
        infer(batch2)
    s.export_plot("infer.html")
```

Each task with time series also gets a `noise` summary (power CV, samples
captured vs expected, quality label); see
[Noise / quality reporting](../api/python.md#noise--quality-reporting).

### Behavior

- One Session per process; a second one raises `RuntimeError`.
- Each thread keeps its own task stack.
- A Session that is never stopped is finalized at exit and its file is
  written.
- In a forked child, tasks are no-ops; only the parent reports.
- Without the native library the Session warns once and records nothing.
- Energy counters are system-wide: two CodeGreen processes measuring at the
  same time both count each other's work. The constructor warns when it
  finds another one.

## `codegreen measure`: per-function energy

`codegreen measure python script.py` instruments a temporary copy of the
script and runs it. Coarse granularity (the default) brackets `main`;
`-g fine` brackets every function.

```python
# sorting_comparison.py
import random

def generate_data(size):
    random.seed(42)
    return [random.randint(1, 10000) for _ in range(size)]

def bubble_sort(arr):
    n = len(arr)
    arr = arr.copy()
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

def main():
    data = generate_data(5000)
    print(bubble_sort(data)[0], quick_sort(data)[0])

if __name__ == "__main__":
    main()
```

```bash
codegreen measure python sorting_comparison.py -g fine --sensors rapl
```

```text
Energy: 82.6265 J
Time:   1.0699 s
Power:  77.23 W

  Function                         Excl J     Incl J    Calls  Quality
  bubble_sort                     81.1461    81.1461        1  measured
  quick_sort                       1.3354    16.1971     5581  aggregate_only
  generate_data                    0.1394     0.1394        1  below_resolution
  main                             0.0056    82.6265        1  measured
Validity: valid
```

How to read it:

- **Exclusive** energy (`Excl J`, `exclusive_j`) is the energy inside a
  function minus its instrumented callees. Exclusive energies partition the
  run: here they sum to the 82.63 J total.
- **Inclusive** energy (`Incl J`, `inclusive_j`, also reported as
  `energy_j`) adds the callees and is summed over every call. For a
  recursive function each nested call's window is counted again, so
  `quick_sort` shows 16.20 J inclusive against 1.34 J exclusive. Inclusive
  sums are not shares of the total.
- **Quality**: `measured` when each call spans enough sampler readings,
  `aggregate_only` when only the summed time of all calls does (5581 short
  recursive calls), `below_resolution` when not even that (`generate_data`
  ran for a few milliseconds).

The JSON report (`--json` or `-o file.json`) carries the same values per
function in `per_function_energy`, plus `validity`; see
[Reports](../user-guide/reports.md).

### Overhead of fine granularity

Fine mode adds an enter and an exit checkpoint to every call, so call-heavy
code slows down and its energy rises with it. A recursive `fib(25)` that
runs in 0.02 s uninstrumented took 0.49 s under `-g fine`:

```text
Energy: 37.9124 J
Time:   0.4883 s
Power:  77.64 W

  Function                         Excl J     Incl J    Calls  Quality
  fib                             37.9085   647.3114   242785  aggregate_only
  main                             0.0039    37.9124        1  measured
Validity: valid
```

`fib(30)` (about 2.7 million calls) exceeds
`measurement.report.max_checkpoints` and the run is invalid with
`CHECKPOINT_CAP` (exit code 3). Use coarse mode or `codegreen run` for
totals, and fine mode to locate hotspots in code with moderate call counts.

A run that is too short to resolve is also invalid: a 12 ms script fails
with `TOTAL_BELOW_RESOLUTION` (the root window must span at least two
sampler readings, 10 ms apart by default).

## Before and after: `codegreen run`

To compare two versions of a program, measure each with `codegreen run` and
several repeats. It needs no instrumentation and resolves short runs
(RAPL counters update every millisecond).

```python
# lookup_list.py; lookup_set.py is identical with set(...) instead of list(...)
def count_hits(queries, allowed):
    return sum(1 for q in queries if q in allowed)

def main():
    allowed = list(range(0, 20_000, 2))
    print(count_hits(range(20_000), allowed))

if __name__ == "__main__":
    main()
```

```bash
codegreen run --repeat 5 --sensors rapl -- python3 lookup_list.py
codegreen run --repeat 5 --sensors rapl -- python3 lookup_set.py
```

| Version | Energy (J) | Time (s) | CV | Validity |
|---|---:|---:|---:|---|
| `list` membership | 85.38 +/- 1.31 | 1.0806 | 1.5% | valid |
| `set` membership | 1.064 +/- 0.044 | 0.0133 | 4.1% | valid |

To see which function a change moved, save one `measure` report per
version and compare the JSON. `count_counter.py` replaces the body of
`count` in `count_loop.py` with `return Counter(words)`:

```python
# count_loop.py
def count(words):
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return counts

def main():
    words = [f"w{i % 5000}" for i in range(4_000_000)]
    print(len(count(words)))

if __name__ == "__main__":
    main()
```

```bash
codegreen measure python count_loop.py -g fine --sensors rapl -o loop.json
codegreen measure python count_counter.py -g fine --sensors rapl -o counter.json
```

```python
import json

for path in ("loop.json", "counter.json"):
    r = json.load(open(path))
    f = r["per_function_energy"]["count"]
    print(f'{path:13} {r["validity"]["status"]:6} total {r["summary"]["total_energy_j"]:6.2f} J'
          f'  count {f["exclusive_j"]:6.2f} J ({f["quality"]})')
```

```text
loop.json     valid  total  61.94 J  count  23.87 J (measured)
counter.json  valid  total  54.93 J  count  17.99 J (measured)
```

The total includes building the word list in `main`, which did not change;
`count` alone fell from 23.87 J to 17.99 J. These are single runs: repeat
them, or use `codegreen run --repeat`, before trusting a difference this
size.

Measure every candidate the same way: an optimization that seems obvious
can cost more. On CPython 3.13, building a 2-million-item string with `+=`
used 20.36 J and the same with `"".join` used 23.46 J (five runs each).

## Practices

- Pass `--sensors rapl` (or set `measurement.default_sensors`) unless you
  want GPU energy in the total.
- Check `validity` (or the exit code: 3 means invalid) before reading
  numbers.
- Make workloads long enough: a few hundred milliseconds or more for
  `measure` and Session tasks; GPU providers update slower than RAPL.
- Use the same inputs and seeds when comparing versions, and repeat runs.

## See also

- [Python API](../api/python.md)
- [CLI reference](../user-guide/cli-reference.md)
- [Reports and visualization](../user-guide/reports.md)
- [C/C++](cpp.md), [Java](java.md)
