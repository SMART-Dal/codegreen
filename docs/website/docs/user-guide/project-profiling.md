# Project Profiling

`codegreen project` profiles a **whole project** with per-function energy
attribution. It plugs CodeGreen's tree-sitter instrumentation into the
project's own build system instead of asking you to vendor your build
commands into CodeGreen.

## Three phases

1. **DISCOVER** - walk `--source-glob` (or language defaults), parse with
   tree-sitter, build the list of instrumentation points.
2. **INSTRUMENT + BUILD** - rewrite each source file with checkpoint
   calls, then run `--build-cmd`. The runtime bridge is linked in
   automatically (`libcodegreen-nemb.so` for C/C++, `codegreen_runtime.py`
   for Python, JNI bridge for Java).
3. **MEASURE** - run `--run-cmd` under the NEMB backend, collect per-method
   energy via the same correlation pipeline as single-file `measure`.

## CLI

```bash
codegreen project [OPTIONS] LANGUAGE:{python|cpp|java|c|javascript} PROJECT_DIR
```

| Option | Description |
|---|---|
| `-b, --build-cmd TEXT` | Build command, e.g. `mvn package -DskipTests` |
| `-r, --run-cmd TEXT` | Run command, e.g. `java -jar target/benchmarks.jar` |
| `-s, --source-glob TEXT` | Source file glob pattern |
| `-g, --granularity [coarse\|fine]` | Instrumentation level (default: `fine`) |
| `--cores TEXT` | CPU cores for `taskset`, e.g. `0-7` |
| `-n, --repeat INTEGER` | Measurement repetitions (default: 1) |
| `--json` | Output as JSON |
| `--no-cleanup` | Keep instrumented files |
| `-o, --output PATH` | Output directory for results |

## Java + Gradle

```bash
codegreen project java . \
  -b "./gradlew build -x test" \
  -r "java -jar jmh/build/libs/benchmarks.jar '.*MyBench.*' -wi 10 -i 50 -f 1"
```

## Java + Maven

```bash
codegreen project java ./my-project \
  -b "mvn package -DskipTests" \
  -r "java -jar target/benchmarks.jar" \
  --cores 0-7
```

## Python

```bash
codegreen project python ./src \
  -r "python main.py" \
  --granularity fine
```

For Python projects the build phase is a no-op (no compile step); the
instrumented `.py` files are imported directly by the run command.

## C / C++

```bash
codegreen project c ./src \
  -b "make -j$(nproc)" \
  -r "./build/run_benchmark"
```

The build command must link against `libcodegreen-nemb.so`. The instrument
phase rewrites source in place; pass `--no-cleanup` to inspect the
rewritten files.

## Output

A `summary.json` lands in the output directory with the same per-method
schema as `codegreen measure -g fine`. Top fields:

- `methods` - list of `{name, file, total_joules, total_seconds, calls, exclusive_pct, ...}`
- `totals` - aggregate energy / duration over the whole run
- `meta` - command, language, build/run commands, host info

## When to use `project` vs `measure`

| Scenario | Use |
|---|---|
| Single source file, one entry point | [`codegreen measure`](cli-reference.md#measure) |
| Multi-file project with its own build system | **`codegreen project`** |
| Existing JMH benchmark suite | **`codegreen project`** with `--run-cmd "java -jar ...jar"` |
| Want to compare two commits | wrap each in `codegreen project` and diff `summary.json` |

## See also

- [04 - Project hotspots (Java)](../examples/04_project_hotspots_java.md)
- [09 - Project hotspots (Python)](../examples/09_project_hotspots_python.md)
- [CLI reference: `project`](cli-reference.md#project)
