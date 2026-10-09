"""02 Stable mean via repetitions.

Demonstrates `codegreen run --repeat 5 --warmup 1` and the CV (coefficient
of variation across runs) reported by CodeGreen. Smaller CV -> tighter
estimate. Useful when comparing two variants of the same workload.
"""
import json
import subprocess
import sys


def main() -> int:
    cmd = ["codegreen", "run", "--repeat", "5", "--warmup", "1", "--json", "--",
           "python3", "-c", "x=0\nfor i in range(2_000_000): x+=i\nprint(x)"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    e = data["energy_j"]
    print(f"OK: run_repeat; mean_energy_j={e['mean']:.4f}; cv_pct={e['cv_percent_across_runs']:.2f}; n={data['runs']['measurement_runs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
