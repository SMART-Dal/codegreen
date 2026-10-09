"""09 `codegreen project python` per-function instrumentation.

Generates a tiny Python project with three functions of differing cost,
runs `codegreen project python` to discover + instrument + execute, and
reports the instrumentation summary (files / checkpoints discovered).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _extract_trailing_json(text: str) -> dict:
    """Return the last top-level JSON object embedded in `text`. `codegreen
    project` may print non-JSON status lines before the JSON payload."""
    depth = 0
    start = -1
    last = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        last = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    start = -1
    if last is None:
        raise ValueError("no JSON object in output")
    return last


PROG = """
def light():
    return sum(range(1000))

def medium(n):
    return sum(i*i for i in range(n))

def heavy(n):
    acc = 0
    for i in range(n):
        acc += i*i
    return acc

if __name__ == "__main__":
    light()
    medium(200_000)
    print(heavy(5_000_000))
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cg_proj_py_") as td:
        proj = Path(td)
        (proj / "main.py").write_text(PROG)
        cmd = ["codegreen", "project", "python", str(proj),
               "--run-cmd", f"{sys.executable} main.py",
               "--granularity", "fine", "--json"]
        p = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
        if p.returncode != 0:
            print(p.stdout); print(p.stderr, file=sys.stderr); return p.returncode
        data = _extract_trailing_json(p.stdout)
    src = data.get("source_files", 0)
    instr = data.get("instrumented_files", 0)
    pts = data.get("total_points", 0)
    print(f"OK: project_hotspots_python; source_files={src}; instrumented_files={instr}; checkpoints={pts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
