"""10 Cross-check: codegreen vs `perf stat -e power/energy-pkg/`.

Runs the same Python workload twice, once instrumented via codegreen and
once wrapped in perf stat, then prints the percentage delta. Useful for
sanity-checking that codegreen agrees with the kernel's perf counters
within a few percent.

Skips cleanly if `perf` or the `power/energy-pkg/` event are unavailable.
"""
import json
import re
import shutil
import subprocess
import sys


WORKLOAD = "x=0\nfor i in range(2_000_000): x+=i*i\nprint(x)"


def _codegreen_run() -> float:
    out = subprocess.run(
        ["codegreen", "run", "--repeat", "3", "--warmup", "1", "--json", "--",
         "python3", "-c", WORKLOAD],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["energy_j"]["mean"])


def _perf_run() -> float:
    if not shutil.which("perf"):
        return float("nan")
    p = subprocess.run(
        ["perf", "stat", "-x", ",", "-e", "power/energy-pkg/",
         "python3", "-c", WORKLOAD],
        capture_output=True, text=True,
    )
    for ln in p.stderr.splitlines():
        m = re.match(r"^([0-9.,]+),Joules,power/energy-pkg/", ln)
        if m:
            return float(m.group(1).replace(",", "."))
    return float("nan")


def main() -> int:
    cg_j = _codegreen_run()
    perf_j = _perf_run()
    if perf_j != perf_j:
        print(f"SKIP: perf or power/energy-pkg/ unavailable; codegreen_j={cg_j:.4f}")
        return 0
    delta_pct = 100.0 * (cg_j - perf_j) / perf_j
    print(f"OK: codegreen_vs_perf; codegreen_j={cg_j:.4f}; perf_j={perf_j:.4f}; delta_pct={delta_pct:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
