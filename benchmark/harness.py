"""Benchmark harness - core execution engine using Suite protocol."""
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

from benchmark.config import RunResult
from benchmark.profilers import ProfilerInterface, PerfProfiler, get_profiler
from benchmark.results import ResultCollector
from benchmark.suites.base import Suite, Task

SLEEP_BETWEEN_RUNS = 2.0


def _check_cpu_governor(expected: str, callback=None):
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
            actual = f.read().strip()
        if actual != expected:
            msg = (f"WARNING: CPU governor is '{actual}', expected '{expected}'. "
                   f"Results may have higher variance. "
                   f"Set with: sudo cpupower frequency-set -g {expected}")
            if callback:
                callback(msg)
            else:
                print(msg, file=sys.stderr)
    except FileNotFoundError:
        pass


class BenchmarkHarness:
    def __init__(self, suite: Optional[Suite] = None,
                 repetitions: int = 5, warmup_runs: int = 1,
                 timeout_seconds: int = 300, min_runtime_seconds: float = 1.0,
                 progress_callback: Optional[Callable] = None):
        self.suite = suite
        self.repetitions = repetitions
        self.warmup_runs = warmup_runs
        self.timeout = timeout_seconds or (suite.default_timeout if suite else 300)
        self.min_runtime = min_runtime_seconds
        self.collector = ResultCollector()
        self.progress_callback = progress_callback or (lambda msg: print(msg, file=sys.stderr))
        _check_cpu_governor("performance", self.progress_callback)

    def run_task(self, task: Task, profiler_name: str = "perf",
                 repetitions: Optional[int] = None) -> List[RunResult]:
        """Run a single task with a single profiler."""
        reps = repetitions or self.repetitions
        profiler = get_profiler(profiler_name)
        if hasattr(profiler, 'set_source') and task.source_file:
            profiler.set_source(task.source_file, task.language)

        # Build the task (compile, construct run command)
        task = self.suite.build(task)
        if not task.run_command:
            self.progress_callback(f"  No run command for {task.name}, skipping")
            return []

        results = []

        # Warmup
        for i in range(self.warmup_runs):
            self.progress_callback(f"  Warmup {i+1}/{self.warmup_runs}")
            try:
                profiler.run(task.run_command, timeout=self.timeout)
            except Exception:
                pass

        # Estimate runtime for auto-repeat
        estimated = self._estimate_runtime(task.run_command)
        self._configure_auto_repeat(profiler, estimated)
        self._clear_cache()

        # Measurement runs
        for i in range(reps):
            if i > 0:
                time.sleep(SLEEP_BETWEEN_RUNS)
            self.progress_callback(f"  Run {i+1}/{reps}")
            try:
                profile_result = profiler.run(task.run_command, timeout=self.timeout)
                repeat_count = getattr(profiler, 'repeat_count', 1)
                valid = (True if repeat_count > 1
                         else self.suite.validate_output(profile_result.output, task))

                result = RunResult(
                    problem=task.name,
                    language=task.language,
                    size=task.metadata.get("size", "default"),
                    profiler=profiler_name,
                    energy_joules=profile_result.energy_joules,
                    time_seconds=profile_result.time_seconds,
                    output_valid=valid,
                    repetition=i + 1,
                    variant=task.variant,
                    suite=self.suite.name,
                    checkpoints=profile_result.checkpoints,
                )
                results.append(result)
                self.collector.add(result)
            except subprocess.TimeoutExpired:
                self.progress_callback(f"  Run {i+1} timed out")
            except Exception as e:
                self.progress_callback(f"  Run {i+1} failed: {e}")
        return results

    def run_suite(self, profilers: Optional[List[str]] = None,
                  repetitions: Optional[int] = None,
                  filters: Optional[dict] = None) -> ResultCollector:
        """Discover all tasks and run them with specified profilers."""
        profs = profilers or ["perf"]
        tasks = self.suite.discover(filters)
        self.progress_callback(f"Discovered {len(tasks)} tasks in {self.suite.name}")

        for task in tasks:
            for prof in profs:
                self.progress_callback(f"\n{task.name} [{task.variant}] profiler={prof}")
                self.run_task(task, prof, repetitions)
        return self.collector

    def _estimate_runtime(self, cmd: List[str]) -> float:
        try:
            start = time.perf_counter()
            subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            return time.perf_counter() - start
        except Exception:
            return 0.0

    def _configure_auto_repeat(self, profiler: ProfilerInterface, estimated_time: float):
        if not isinstance(profiler, PerfProfiler):
            return
        if estimated_time > 0 and estimated_time < self.min_runtime:
            repeat = math.ceil(self.min_runtime / estimated_time)
            profiler.repeat_count = repeat
            self.progress_callback(f"  Short workload ({estimated_time:.2f}s < {self.min_runtime}s), "
                                   f"auto-repeat x{repeat}")

    def _clear_cache(self):
        try:
            subprocess.run(["sync"], check=False)
            subprocess.run(["sudo", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
                           capture_output=True, check=False)
        except Exception:
            pass

    def cleanup(self):
        if self.suite:
            self.suite.cleanup()
