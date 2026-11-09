# 04 - Project hotspots (Java)

Run `codegreen project java` on a one-class program. CodeGreen discovers
the sources, injects enter/exit checkpoints into every method, builds with
your command (`--build-cmd`), runs your command (`--run-cmd`) and reports
per-method energy. The same flags drive Maven, Gradle or JMH builds.

## Prerequisites

- `pip install codegreen`
- A JDK on `PATH` (`java`, `javac`). The script prints `SKIP:` without one.

## Source

- [`examples/04_project_hotspots_java/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/04_project_hotspots_java/main.py)
- [`examples/04_project_hotspots_java/Hello.java`](https://github.com/SMART-Dal/codegreen/blob/main/examples/04_project_hotspots_java/Hello.java)

```python
--8<-- "examples/04_project_hotspots_java/main.py"
```

```java
--8<-- "examples/04_project_hotspots_java/Hello.java"
```

## Run

```bash
python examples/04_project_hotspots_java/main.py
```

```text
OK: project_hotspots_java; source_files=1; checkpoints=6; hotspots=3
```

The script copies `Hello.java` into `.work/` next to itself and profiles
that copy. To see the hotspot table, run the command directly
(`--granularity` defaults to `fine` for `project`):

```bash
cd examples/04_project_hotspots_java/.work
codegreen project java . --build-cmd "javac Hello.java" --run-cmd "java -cp . Hello" --sensors rapl
```

```text
Phase 3: Measuring energy...
    Energy: 6.32 J, Attributed: 1.55 J (25%), Functions: 3

Results
  Total energy: 6.32 J (avg over 1 runs)
  Functions profiled: 3
  WARNING instrumented functions cover 24.5% of run energy (floor 25.0%); per-function shares are relative to the
attributed energy only

Top hotspots by exclusive energy:
  Rank  Function                              Excl%   Incl%   Self  Verdict    Calls    uJ/call
  ----------------------------------------------------------------------------------------------------
  1     Hello.slowSum                        100.0%  100.0%  1.00 TYPE_1_DIRECT        1  1551876.0
  2     Hello.warm                             0.0%    0.0%  0.00    minor        1        0.0
  3     Hello.main                             0.0%  100.0%  0.00  wrapper        1  1551876.0
Validity: valid
```

## Reading the result

- `Total energy` covers the whole run, JVM start-up included. `Attributed`
  is the energy inside instrumented methods (their exclusive energies). Here
  the JVM dominates a short program, so only 24.5% of the run is attributed
  and the report carries an attribution warning (floor
  `--min-attribution-pct`, default 25).
- `Excl%` and `Incl%` are shares of the attributed energy: exclusive energy
  partitions it, inclusive energy also counts callees. `Hello.main` is a
  `wrapper`: 100% inclusive, nearly nothing of its own.
- Exit code 3 means the measurement is invalid; see
  [Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity).

See also: [Project Profiling](../user-guide/project-profiling.md),
[09 - Project hotspots (Python)](09_project_hotspots_python.md).
