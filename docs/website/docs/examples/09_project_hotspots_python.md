# 09 - Project hotspots (Python)

`codegreen project python` against a small multi-file Python package.
Per-function attribution via tree-sitter instrumentation, no source edits.

## What you learn

- The Python flavour of `codegreen project` (no compile step, no JNI).
- Per-function energy ranking and hotspot detection.
- How `--source-glob` filters which files get instrumented.

## Prerequisites

- `pip install codegreen`
- Linux / macOS / Windows with a working backend.

## Source

[`examples/09_project_hotspots_python/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/09_project_hotspots_python/main.py)

```python
--8<-- "examples/09_project_hotspots_python/main.py"
```

## Run

```bash
python examples/09_project_hotspots_python/main.py
```

## Expected output

```
OK: project_hotspots_python; source_files=1; instrumented_files=1; checkpoints=8
```

## Why it matters

This is the **Python equivalent of `codegreen measure -g fine`** scaled
from a single file to a whole project. The discover phase walks
`--source-glob`, the instrument phase rewrites each file with checkpoint
calls injected at function boundaries, and the measure phase runs the
project under the NEMB backend. The output JSON has the same
per-function schema as the single-file `measure` command, so any
downstream tooling that consumes `measure` output works on projects too.

See also: [User guide: Project Profiling](../user-guide/project-profiling.md),
[04 - Project hotspots (Java)](04_project_hotspots_java.md).
