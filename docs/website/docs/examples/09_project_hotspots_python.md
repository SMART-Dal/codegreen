# 09 - Project hotspots (Python)

Run `codegreen project python` on a generated one-file program with three
functions of different cost. Python needs no build step, so only
`--run-cmd` is given. The script prints the instrumentation summary from
the JSON report.

## Prerequisites

- `pip install codegreen`

## Source

[`examples/09_project_hotspots_python/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/09_project_hotspots_python/main.py)

```python
--8<-- "examples/09_project_hotspots_python/main.py"
```

## Run

```bash
python examples/09_project_hotspots_python/main.py
```

```text
OK: project_hotspots_python; source_files=1; instrumented_files=1; checkpoints=6
```

Six checkpoints: an enter and an exit for each of `light`, `medium` and
`heavy`. To see the ranking, save `PROG` from the script as `main.py` in a
directory and run:

```bash
codegreen project python . --run-cmd "python3 main.py" --sensors rapl
```

```text
Phase 3: Measuring energy...
    Energy: 34.31 J, Attributed: 20.59 J (60%), Functions: 3

Results
  Total energy: 34.31 J (avg over 1 runs)
  Functions profiled: 3

Top hotspots by exclusive energy:
  Rank  Function                              Excl%   Incl%   Self  Verdict    Calls    uJ/call
  ----------------------------------------------------------------------------------------------------
  1     heavy                                 96.3%   96.3%  1.00 TYPE_2_INEFFICIENT        1 19834337.0
  2     medium                                 3.7%    3.7%  1.00    minor        1   757954.0
  3     light                                  0.0%    0.0%  1.00    minor        1     1762.0
Validity: valid
```

With `--json` each entry of `hotspots` also carries `quality`. In a JSON run
of the same program `heavy` (0.26 s) was `measured`, while `medium` (10 ms)
and `light` (21 us) were `below_resolution`: their energy is reported but
is too short to resolve against the 10 ms sampler.

See also: [Project Profiling](../user-guide/project-profiling.md),
[CLI reference: `project`](../user-guide/cli-reference.md#project),
[04 - Project hotspots (Java)](04_project_hotspots_java.md).
