"""03 Python Session API: context manager + per-task decorator.

`codegreen.Session` is the in-process equivalent of `codegreen run`: useful
when you want to measure specific code blocks inside a long-running script
without spawning a subprocess. The `@codegreen.task` decorator marks
a checkpoint inside an active Session.
"""
import sys

import codegreen


@codegreen.task("hot_loop")
def hot_loop(n: int) -> int:
    acc = 0
    for i in range(n):
        acc += i * i
    return acc


def main() -> int:
    with codegreen.Session("session_api_demo") as s:
        s.start_task("warmup")
        sum(range(100_000))
        s.stop_task("warmup")
        v = hot_loop(2_000_000)
    report = s.stop()
    tasks = report.get("tasks", [])
    total_j = sum(float(t.get("energy_j", 0.0)) for t in tasks)
    print(f"OK: session_api; tasks={len(tasks)}; total_energy_j={total_j:.4f}; hot_loop_result={v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
