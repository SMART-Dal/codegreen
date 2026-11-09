# Project Profiling

`codegreen project` measures per-function energy across a whole project. It
instruments the sources in place, runs your own build and run commands, and
restores the sources afterwards.

## Three phases

1. **Discover**: find the sources (`--source-glob`, else the language
   config's patterns) and parse them with Tree-sitter to locate every
   function.
2. **Instrument and build**: insert checkpoint calls, copy the language
   runtime into the project (`codegreen_runtime.py` for Python, the Java
   standalone runtime for Java), then run `--build-cmd`. Without `-b`, the
   build system is detected from marker files listed in the language config:
   `CMakeLists.txt` or `Makefile` (C, C++), `pom.xml` or `build.gradle`
   (Java), `setup.py` (`pip install -e .`) or `pyproject.toml`
   (`poetry install`) for Python. A Python project needs no build; pass
   `-b true` to skip a detected one. For C and C++ nothing is
   copied: the build must put `codegreen/instrumentation/language_runtimes/c`
   (or `cpp`) on the include path and link `-lcodegreen-nemb`.
3. **Measure**: run `--run-cmd` in the project directory, `--repeat` times,
   and attribute energy to every function call.

The original files are backed up to `PROJECT_DIR/.codegreen_backup/` and
restored at the end; a run that was interrupted is restored at the start of
the next one. `--no-cleanup` keeps the instrumented files.

For the options see [CLI Reference: `project`](cli-reference.md#project).

## Examples

```bash
# Python: no build step
codegreen project python ./src -r "python3 main.py" --sensors rapl

# Java + Gradle + JMH
codegreen project java . \
  -b "./gradlew build -x test" \
  -r "java -jar jmh/build/libs/benchmarks.jar '.*MyBench.*' -wi 10 -i 50 -f 1"

# Java + Maven, run on cores 0-7
codegreen project java ./my-project \
  -b "mvn package -DskipTests" \
  -r "java -jar target/benchmarks.jar" --cores 0-7

# C: the build adds the runtime include path and links libcodegreen-nemb
codegreen project c ./src -b "make -j$(nproc)" -r "./build/run_benchmark"

# GPU work attributed to the Python function that launched it
codegreen project python ./src -r "python3 train.py" --sync-device cuda
```

A real run on the `sums.py` program of the [Quick Start](../getting-started/quickstart.md),
placed in `src/main.py`:

```console
$ codegreen project python ./src -r "python3 main.py" --sensors rapl
...
Phase 3: Measuring energy...
    Energy: 68.50 J, Attributed: 55.08 J (80%), Functions: 3

Results
  Total energy: 68.50 J (avg over 1 runs)
  Functions profiled: 3

Top hotspots by exclusive energy:
  Rank  Function                              Excl%   Incl%   Self  Verdict    Calls    uJ/call
  ----------------------------------------------------------------------------------------------------
  1     square_sum                            63.9%   63.9%  1.00 TYPE_1_DIRECT        3 11740302.3
  2     cube_sum                              36.0%   36.0%  1.00 TYPE_1_DIRECT        1 19858243.0
  3     main                                   0.0%  100.0%  0.00  wrapper        1 55082299.0
Validity: valid
```

`Energy` is the whole run, including interpreter start-up and exit;
`Attributed` is the energy inside instrumented functions (the sum of
exclusive energies).

## Output

With `--json` the result is printed; with `-o DIR` it is written to
`DIR/project_results.json`. Top-level fields of `--json`:

| Field | Meaning |
|---|---|
| `success`, `error` | `success` is `false` and `error` is `invalid_measurement: CODE[,CODE]` when the merged validity is invalid |
| `project`, `language`, `source_files`, `instrumented_files`, `total_points` | What was instrumented |
| `skipped_functions` | Functions that are not instrumented (async functions, generators, coroutines, C++ `constexpr`/`consteval`, some C functions) |
| `sync_device` | The `--sync-device` value |
| `attribution_pct`, `attribution_warning` | Last run: attributed energy as a percentage of the run's total. Below `--min-attribution-pct` (default 25) the warning `LOW_ATTRIBUTION` says the per-function shares cover only part of the run |
| `validity` | Every run's verdict merged, each text prefixed `run N:` |
| `runs` | One entry per repetition: `run_idx`, `total_energy_j`, `wall_time_s`, `avg_power_w`, `attributed_energy_j` (= `exclusive_energy_j`), `attribution_pct`, `attribution_warning`, `functions`, `total_checkpoints`, `sampler`, `validity`, `resolution_ns`, `overlapping_threads` |
| `hotspots` | The last run's functions ranked by exclusive share, each with `rank`, `function` and the fields below (top 20; `project_results.json` keeps all) |

`project_results.json` holds `validity`, `runs` and `hotspots`.

Per function:

| Field | Meaning |
|---|---|
| `energy_j` | Inclusive energy (with callees), summed over every call |
| `exclusive_energy_j` | Energy in the function's own body; these partition the attributed energy |
| `energy_pct`, `exclusive_pct` | `energy_j` and `exclusive_energy_j` as percentages of the attributed energy. Exclusive shares sum to 100; the root's inclusive share is 100; a recursive function's inclusive share counts every nested frame and can exceed 100 |
| `self_ratio` | `exclusive_energy_j / energy_j` |
| `verdict` | Hotspot class: `wrapper`, `TYPE_2_INEFFICIENT`, `TYPE_1_DIRECT`, `TYPE_5_FREQUENCY` or `minor` (thresholds in [`hotspot_taxonomy`](configuration-reference.md#hotspot-verdicts)) |
| `file`, `line` | Source file and 1-based declaration line (`null` when the name is declared in more than one file) |
| `signature` | Parameter types as written, where the language config sets `node_types.parameter_signature` (Java) |
| `wall_time_s`, `avg_power_w`, `calls`, `energy_per_call_uj` | Summed time, inclusive power, call count and inclusive microjoules per call |
| `quality` | `measured`, `aggregate_only` or `below_resolution` ([Per-function quality](cli-reference.md#per-function-quality)) |

Where probes emit qualified names (`instrumentation_config.record_name_field`,
Java and Python), methods sharing a name in one file are separate records
named `Class.method@<line>`; a record that still merges declarations carries
`merged_declarations`.

Java standalone runs build `sampler` from each JVM's `CG_CP_META` record
(`marker_reads: "last_poll"`), so a JIT or GC pause shows up as the warning
`SAMPLER_GAP` rather than an invalid run. The poller's settings come from
`project_config.runtime_injection.env` in
`codegreen/instrumentation/configs/java.json`; a value `{config:a.b.c}` is
that key of the active config, and the caller's environment overrides them.

## Getting valid attribution

- Pass `--cores` with at least two CPUs: the sampler runs inside the measured
  process (`AFFINITY_SINGLE_CPU` otherwise).
- Read each function's `quality` before comparing functions; only `measured`
  functions have meaningful per-call figures.
- A low `attribution_pct` means most of the run's energy is spent outside
  instrumented functions (start-up, module level, uninstrumented libraries, or
  writing millions of checkpoints at exit); the percentages then describe
  the instrumented part only.
- With several threads inside instrumented functions at once, each is charged
  the whole package energy (`OVERLAPPING_THREADS`), so exclusive energies can
  sum above the total.

## When to use `project` and `measure`

| Scenario | Use |
|---|---|
| One source file with an entry point | [`codegreen measure`](cli-reference.md#measure) |
| Multi-file project with its own build system | `codegreen project` |
| Existing JMH benchmark suite | `codegreen project` with `--run-cmd "java -jar ...jar"` |
| Compare two commits | run `codegreen project` on each with `-o` and compare `project_results.json` |

## See also

- [04 - Project hotspots (Java)](../examples/04_project_hotspots_java.md)
- [09 - Project hotspots (Python)](../examples/09_project_hotspots_python.md)
