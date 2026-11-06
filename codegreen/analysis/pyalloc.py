"""Run a Python script or module under tracemalloc and write its allocation hot spots by source line (profiled runs only).

python -m codegreen.analysis.pyalloc --out alloc.json [--frames 1] [--top 50] [--interval 0.5] -- script.py args | -m module args
Output: {"top": [{file, line, size_b, count}], "total_b", "frames", "snapshots"}: per allocating line, the largest live
size seen over periodic snapshots (every --interval s and once before the target's globals are released), so short-lived
allocations that peak between program start and exit count; allocations born and freed between two snapshots do not.
Import machinery and this tracer are excluded. Tracing slows the run, so its timing is never a measurement.
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
import threading
import tracemalloc

SKIP = ("<frozen *>", "<unknown>", tracemalloc.__file__, runpy.__file__, threading.__file__, __file__)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pyalloc")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        raise SystemExit("pyalloc: no script or -m module given")
    module = cmd[0] == "-m"
    target, sys.argv = (cmd[1], cmd[1:]) if module else (cmd[0], cmd)
    peak: dict[tuple[str, int], tuple[int, int]] = {}
    done, n = threading.Event(), [0]

    def snap() -> None:
        n[0] += 1
        for s in tracemalloc.take_snapshot().filter_traces([tracemalloc.Filter(False, p) for p in SKIP]).statistics("lineno"):
            k = (s.traceback[0].filename, s.traceback[0].lineno)
            if s.size > peak.get(k, (0, 0))[0]:
                peak[k] = (s.size, s.count)

    def loop() -> None:
        while not done.wait(a.interval) and tracemalloc.is_tracing():
            snap()

    tracemalloc.start(a.frames)
    threading.Thread(target=loop, daemon=True).start()
    try:
        g = runpy.run_module(target, run_name="__main__", alter_sys=True) if module else runpy.run_path(target, run_name="__main__")
        snap()   # the target's module globals are still alive here
        del g
    finally:
        done.set()
        tracemalloc.stop()
        top = sorted(peak.items(), key=lambda kv: -kv[1][0])
        with open(a.out, "w") as fh:
            json.dump({"top": [{"file": f, "line": ln, "size_b": sz, "count": c} for (f, ln), (sz, c) in top[:a.top]],
                       "total_b": sum(sz for sz, _ in peak.values()), "frames": a.frames, "snapshots": n[0]}, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
