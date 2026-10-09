"""06 Host-wide energy monitoring via `codegreen monitor`.

Streams cumulative energy samples for a fixed duration into a JSONL file.
Useful for already-running services or for capturing baseline system load
when no specific PID can be attributed.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cg_monitor_host_") as td:
        out = Path(td) / "energy.jsonl"
        cmd = ["codegreen", "monitor", "-d", "3", "-i", "250", "-o", str(out),
               "--quiet", "--json"]
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        summary = json.loads(p.stdout)
        records = [json.loads(ln) for ln in out.read_text().splitlines() if ln]
        sample_lines = sum(1 for r in records if r.get("type") == "sample")
    print(f"OK: monitor_host; duration_s={summary['duration_s']:.2f}; "
          f"total_joules={summary['total_joules']:.3f}; samples={summary['samples']}; "
          f"jsonl_samples={sample_lines}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
