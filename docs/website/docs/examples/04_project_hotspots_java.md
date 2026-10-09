# 04 - Project hotspots (Java)

End-to-end run of `codegreen project java` against a small Java program.
Discovers source files, injects per-method checkpoints, compiles with the
project's `javac`, runs the binary, and emits per-function energy.

## What you learn

- The three phases of `codegreen project`: DISCOVER, INSTRUMENT+BUILD,
  MEASURE.
- How `--build-cmd` / `--run-cmd` plug arbitrary build systems (Maven,
  Gradle, raw `javac`).
- How per-method attribution differs from whole-program (the `methods`
  table in the JSON output).

## Prerequisites

- `pip install codegreen`
- JDK on `PATH` (`java`, `javac`).

## Source

The driver script and the Java fixture both live in the example directory:

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

## Expected output

```
OK: project_hotspots_java; source_files=1; checkpoints=6; hotspots=1
```

## Why it matters

Whole-program energy (from `codegreen run`) tells you the workload cost.
**Per-function** energy tells you *where* to optimise. The `project`
command stitches together the standard `codegreen measure` instrumentation
with a project's existing build system, so you don't need to vendor your
build commands into CodeGreen.

See also: [User guide: Project Profiling](../user-guide/project-profiling.md),
[09 - Project hotspots (Python)](09_project_hotspots_python.md).
