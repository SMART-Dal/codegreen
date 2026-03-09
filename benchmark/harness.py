"""Benchmark harness - core execution engine."""
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

from benchmark.config import BenchmarkConfig, Problem, RunResult, LanguageEnv
from benchmark.compilers import CompilerManager
from benchmark.profilers import ProfilerInterface, PerfProfiler, get_profiler
from benchmark.results import ResultCollector

DEFAULT_BENCHMARKS_DIR = Path(__file__).parent / "benchmarksgame"
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
    def __init__(self, config: Optional[BenchmarkConfig] = None, progress_callback: Optional[Callable] = None):
        self.config = config or BenchmarkConfig.default()
        self.benchmarks_dir = Path(self.config.benchmarks_dir) if self.config.benchmarks_dir else DEFAULT_BENCHMARKS_DIR
        self.compiler = CompilerManager()
        self.collector = ResultCollector()
        self.progress_callback = progress_callback or (lambda msg: print(msg, file=sys.stderr))
        _check_cpu_governor(self.config.cpu_governor, self.progress_callback)

    def discover_implementations(self, problem: str, language: str) -> List[Path]:
        problem_dir = self.benchmarks_dir / problem
        if not problem_dir.exists():
            return []
        env = self.config.languages.get(language)
        if not env:
            return []
        ext = env.extension
        pattern = f"{problem}*{ext}*"
        files = sorted(problem_dir.glob(pattern))
        # Filter out pre-instrumented files (those with _coarse, _instrumented, etc.)
        clean_files = [f for f in files if '_coarse' not in f.name and '_instrumented' not in f.name]
        return clean_files if clean_files else files

    def validate_output(self, output: str, problem: str, size: str) -> bool:
        problem_dir = self.benchmarks_dir / problem
        expected_file = problem_dir / f"{size}_out"
        if not expected_file.exists():
            return True
        expected = expected_file.read_text().strip()
        actual = output.strip()
        if expected == actual:
            return True
        try:
            exp_lines = expected.split('\n')
            act_lines = actual.split('\n')
            if len(exp_lines) != len(act_lines):
                return False
            for exp, act in zip(exp_lines, act_lines):
                exp_val = float(exp.strip())
                act_val = float(act.strip())
                if abs(exp_val - act_val) > 1e-6:
                    return False
            return True
        except (ValueError, TypeError):
            return False

    def _estimate_runtime(self, cmd: List[str]) -> float:
        try:
            start = time.perf_counter()
            subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds)
            return time.perf_counter() - start
        except Exception:
            return 0.0

    def _configure_auto_repeat(self, profiler: ProfilerInterface, estimated_time: float):
        if not isinstance(profiler, PerfProfiler):
            return
        min_rt = self.config.min_runtime_seconds
        if estimated_time > 0 and estimated_time < min_rt:
            repeat = math.ceil(min_rt / estimated_time)
            profiler.repeat_count = repeat
            self.progress_callback(f"  Short workload ({estimated_time:.2f}s < {min_rt}s), "
                                   f"auto-repeat x{repeat} for perf accuracy")

    def run_single(self, source: Path, size: str, profiler_name: str,
                   language: str, repetitions: Optional[int] = None) -> List[RunResult]:
        reps = repetitions or self.config.repetitions
        env = self.config.languages[language]
        profiler = get_profiler(profiler_name)
        if hasattr(profiler, 'set_source'):
            profiler.set_source(source, language)
        try:
            binary = self.compiler.compile(source, env) if env.compiler else source
        except RuntimeError as e:
            self.progress_callback(f"  Compilation failed: {e}")
            return []
        run_cmd = self.compiler.get_run_command(source, binary, env, [size])
        results = []
        warmup_failures = 0
        for i in range(self.config.warmup_runs):
            self.progress_callback(f"  Warmup {i + 1}/{self.config.warmup_runs}")
            try:
                profiler.run(run_cmd, timeout=self.config.timeout_seconds)
            except (subprocess.TimeoutExpired, Exception):
                warmup_failures += 1
        if warmup_failures == self.config.warmup_runs and self.config.warmup_runs > 0:
            self.progress_callback(f"  All {self.config.warmup_runs} warmups failed, skipping measurement")
            return []
        estimated_time = self._estimate_runtime(run_cmd)
        self._configure_auto_repeat(profiler, estimated_time)
        is_short = estimated_time > 0 and estimated_time < self.config.min_runtime_seconds
        if is_short and not isinstance(profiler, PerfProfiler):
            self.progress_callback(f"  WARNING: Short workload ({estimated_time:.2f}s), "
                                   f"energy accuracy may be low")
        self._clear_cache()
        for i in range(reps):
            if i > 0:
                time.sleep(SLEEP_BETWEEN_RUNS)
            self.progress_callback(f"  Run {i + 1}/{reps}")
            try:
                profile_result = profiler.run(run_cmd, timeout=self.config.timeout_seconds)
                repeat_count = getattr(profiler, 'repeat_count', 1)
                if repeat_count > 1:
                    valid = True
                else:
                    valid = self.validate_output(profile_result.output, source.parent.name, size)
                result = RunResult(
                    problem=source.parent.name,
                    language=language,
                    size=size,
                    profiler=profiler_name,
                    energy_joules=profile_result.energy_joules,
                    time_seconds=profile_result.time_seconds,
                    output_valid=valid,
                    repetition=i + 1,
                    checkpoints=profile_result.checkpoints
                )
                results.append(result)
                self.collector.add(result)
            except subprocess.TimeoutExpired:
                self.progress_callback(f"  Run {i + 1} timed out")
            except Exception as e:
                self.progress_callback(f"  Run {i + 1} failed: {e}")
        return results

    def run_file(self, source: Path, language: str, args: Optional[List[str]] = None,
                 profilers: Optional[List[str]] = None,
                 repetitions: Optional[int] = None) -> List[RunResult]:
        env = self.config.languages.get(language)
        if not env:
            raise ValueError(f"Unknown language: {language}")
        profs = profilers or ["codegreen"]
        size = " ".join(args) if args else "default"
        all_results = []
        for prof in profs:
            self.progress_callback(f"\n{source.name}/{language} args={size} profiler={prof}")
            results = self.run_single(source, size, prof, language, repetitions)
            all_results.extend(results)
        return all_results

    def run_problem(self, problem: str, languages: Optional[List[str]] = None,
                    sizes: Optional[List[str]] = None, profilers: Optional[List[str]] = None,
                    repetitions: Optional[int] = None) -> List[RunResult]:
        langs = languages or list(self.config.languages.keys())
        problem_config = next((p for p in self.config.problems if p.name == problem), None)
        szs = sizes or (problem_config.sizes if problem_config else ["1000"])
        profs = profilers or ["codegreen"]
        all_results = []
        for lang in langs:
            impls = self.discover_implementations(problem, lang)
            if not impls:
                continue
            impl = impls[0]
            for size in szs:
                for idx, prof in enumerate(profs):
                    if idx > 0:
                        time.sleep(SLEEP_BETWEEN_RUNS)
                    self.progress_callback(f"\n{problem}/{lang} size={size} profiler={prof}")
                    results = self.run_single(impl, size, prof, lang, repetitions)
                    all_results.extend(results)
        return all_results

    def run_suite(self, problems: Optional[List[str]] = None, languages: Optional[List[str]] = None,
                  sizes: Optional[List[str]] = None, profilers: Optional[List[str]] = None,
                  repetitions: Optional[int] = None) -> ResultCollector:
        probs = problems or [p.name for p in self.config.problems]
        for problem in probs:
            self.run_problem(problem, languages, sizes, profilers, repetitions)
        return self.collector

    def _clear_cache(self):
        if not self.config.clear_cache:
            return
        try:
            subprocess.run(["sync"], check=False)
            subprocess.run(["sudo", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
                           capture_output=True, check=False)
        except Exception:
            pass

    def cleanup(self):
        self.compiler.cleanup()
