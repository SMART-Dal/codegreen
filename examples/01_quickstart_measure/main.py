"""01 Quickstart: `codegreen run` a one-liner Python workload.

The shortest possible CodeGreen example. Wraps a trivial CPU burn with
`codegreen run --repeat 3 --warmup 0 --json` and prints the mean energy.
"""
import json
import subprocess
import sys


def main() -> int:
    out = subprocess.run(
        ["codegreen", "run", "--repeat", "3", "--warmup", "0", "--json", "--",
         "python3", "-c", "sum(i*i for i in range(2_000_000))"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    mean_j = data["energy_j"]["mean"]
    dur_s = data["duration_s"]["mean"]
    print(f"OK: quickstart_measure; mean_energy_j={mean_j:.4f}; mean_duration_s={dur_s:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
