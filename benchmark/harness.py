"""Benchmark harness - core execution engine."""
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

from benchmark.config import BenchmarkConfig, Problem, RunResult, LanguageEnv
from benchmark.compilers import CompilerManager
from benchmark.profilers import ProfilerInterface, get_profiler
from benchmark.results import ResultCollector

BENCHMARKS_DIR = Path(__file__).parent / "benchmarksgame"
SLEEP_BETWEEN_RUNS = 2.0  # seconds between benchmark runs to reduce thermal effects

class BenchmarkHarness:
    def __init__(self, config: Optional[BenchmarkConfig] = None, progress_callback: Optional[Callable] = None):
        self.config = config or BenchmarkConfig.default()
        self.compiler = CompilerManager()
        self.collector = ResultCollector()
        self.progress_callback = progress_callback or (lambda msg: print(msg, file=sys.stderr))

    def discover_implementations(self, problem: str, language: str) -> List[Path]:
        problem_dir = BENCHMARKS_DIR / problem
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
        problem_dir = BENCHMARKS_DIR / problem
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
        for i in range(self.config.warmup_runs):
            self.progress_callback(f"  Warmup {i + 1}/{self.config.warmup_runs}")
            try:
                profiler.run(run_cmd, timeout=self.config.timeout_seconds)
            except subprocess.TimeoutExpired:
                pass
        self._clear_cache()
        for i in range(reps):
            if i > 0:
                time.sleep(SLEEP_BETWEEN_RUNS)
            self.progress_callback(f"  Run {i + 1}/{reps}")
            try:
                profile_result = profiler.run(run_cmd, timeout=self.config.timeout_seconds)
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
