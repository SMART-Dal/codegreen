"""07 Per-PID energy attribution: cgroup_v2 (preferred) vs cpu_percent.

Spawns a CPU-burn worker, monitors it with both backends, and prints the
attributed-joules delta. cgroup_v2 reads `cpu.stat:usage_usec` directly;
cpu_percent uses psutil sampling. On a single-PID workload the difference
is typically <10%; under heavy multi-tenant contention cgroup_v2 is
significantly more accurate.
"""
import json
import subprocess
import sys
import time


def _spawn_burn(seconds: float):
    code = (
        f"import time\n"
        f"t=time.time()+{seconds}\n"
        f"x=0\n"
        f"while time.time()<t:\n"
        f"    x=sum(i*i for i in range(50_000))\n"
    )
    return subprocess.Popen([sys.executable, "-c", code])


def _measure(pid: int, duration: float, mode: str) -> dict:
    import codegreen
    m = codegreen.Monitor(interval_ms=200, duration_s=duration, pid=pid,
                          attribution_mode=mode).start()
    m._thread.join()
    return m.stop()


def main() -> int:
    p = _spawn_burn(4.0)
    time.sleep(0.2)
    cg = _measure(p.pid, 3.0, "auto")
    p.wait(timeout=5)
    p = _spawn_burn(4.0)
    time.sleep(0.2)
    cp = _measure(p.pid, 3.0, "cpu_percent")
    p.wait(timeout=5)
    delta_pct = 100.0 * (cg["proc_attributed_joules"] - cp["proc_attributed_joules"]) / max(cp["proc_attributed_joules"], 1e-6)
    print(json.dumps({
        "cgroup_backend": cg["attribution_backend"],
        "cgroup_attributed_j": cg["proc_attributed_joules"],
        "cgroup_total_j": cg["total_joules"],
        "cpu_percent_attributed_j": cp["proc_attributed_joules"],
        "cpu_percent_total_j": cp["total_joules"],
        "delta_pct_vs_cpu_percent": round(delta_pct, 2),
    }, indent=2))
    print(f"OK: monitor_pid; backend={cg['attribution_backend']}; "
          f"cgroup_j={cg['proc_attributed_joules']:.3f}; cpu_pct_j={cp['proc_attributed_joules']:.3f}; "
          f"delta_pct={delta_pct:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
