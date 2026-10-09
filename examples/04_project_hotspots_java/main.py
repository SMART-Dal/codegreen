"""04 `codegreen project java` end-to-end on a single-class Java program.

Demonstrates: source discovery -> per-method instrumentation -> build ->
measure -> per-function attribution. The Java class has two methods so the
hotspot list isn't trivially "main()".

Skips cleanly if javac/java are not on PATH (printing SKIP: marker).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _extract_trailing_json(text: str) -> dict:
    """Return the last top-level JSON object embedded in `text`. CLIs may
    print non-JSON status lines before the JSON payload."""
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


def main() -> int:
    if not (shutil.which("javac") and shutil.which("java")):
        print("SKIP: javac/java not on PATH; install a JDK to run this example")
        return 0
    here = Path(__file__).resolve().parent
    work = here / ".work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    shutil.copy(here / "Hello.java", work / "Hello.java")
    cmd = [
        "codegreen", "project", "java", str(work),
        "--build-cmd", "javac Hello.java",
        "--run-cmd", "java -cp . Hello",
        "--source-glob", "**/*.java",
        "--granularity", "fine",
        "--json",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        return p.returncode
    data = _extract_trailing_json(p.stdout)
    src = data.get("source_files", 0)
    pts = data.get("total_points", 0)
    hotspots = data.get("hotspots") or []
    print(f"OK: project_hotspots_java; source_files={src}; checkpoints={pts}; hotspots={len(hotspots)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
