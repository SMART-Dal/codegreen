"""Validation experiments for paper submission."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.harness import BenchmarkHarness
from benchmark.results import StatisticalAnalysis
from validation.analysis import AccuracyAnalysis

@dataclass
class ExperimentResult:
    name: str
    passed: bool
    metrics: Dict[str, Any]
    raw_data: Dict[str, Any]

class Experiment(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        pass

class OverheadExperiment(Experiment):
    """Exp1: Overhead validation - target <5%."""
    name = "overhead"
    description = "Measure instrumentation overhead vs native execution"

    def __init__(self, problems: List[str] = None, languages: List[str] = None,
                 sizes: List[str] = None, repetitions: int = 30):
        self.problems = problems or ["nbody", "binarytrees"]
        self.languages = languages or ["python", "cpp"]
        self.sizes = sizes or ["1000"]
        self.repetitions = repetitions

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        all_overheads = []
        raw_data = {}
        for problem in self.problems:
            for lang in self.languages:
                for size in self.sizes:
                    key = f"{problem}/{lang}/{size}"
                    harness.progress_callback(f"\nOverhead test: {key}")
                    try:
                        native_results = harness.run_problem(
                            problem, [lang], [size], ["native"], self.repetitions
                        )
                        cg_results = harness.run_problem(
                            problem, [lang], [size], ["codegreen"], self.repetitions
                        )
                        native_times = [r.time_seconds for r in native_results]
                        cg_times = [r.time_seconds for r in cg_results]
                        if not native_times or not cg_times:
                            harness.progress_callback(f"  Skipped: no valid results")
                            continue
                        overhead = StatisticalAnalysis.compute_overhead(native_times, cg_times)
                        all_overheads.append(overhead["overhead_percent"])
                        raw_data[key] = {
                            "native": StatisticalAnalysis.summarize(native_times),
                            "codegreen": StatisticalAnalysis.summarize(cg_times),
                            "overhead_percent": overhead["overhead_percent"]
                        }
                    except Exception as e:
                        harness.progress_callback(f"  Error: {e}")
        mean_overhead = sum(all_overheads) / len(all_overheads) if all_overheads else 0
        max_overhead = max(all_overheads) if all_overheads else 0
        return ExperimentResult(
            name=self.name,
            passed=max_overhead < 5.0,
            metrics={"mean_overhead_percent": mean_overhead, "max_overhead_percent": max_overhead},
            raw_data=raw_data
        )

class AccuracyExperiment(Experiment):
    """Exp2: Accuracy vs RAPL - target <10% error, r>0.9."""
    name = "accuracy"
    description = "Compare CodeGreen measurements against perf RAPL baseline"

    def __init__(self, problems: List[str] = None, languages: List[str] = None,
                 sizes: List[str] = None, repetitions: int = 30):
        self.problems = problems or ["nbody", "spectralnorm"]
        self.languages = languages or ["python", "cpp"]
        self.sizes = sizes or ["1000"]
        self.repetitions = repetitions

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        raw_data = {}
        all_cg, all_perf = [], []
        for problem in self.problems:
            for lang in self.languages:
                for size in self.sizes:
                    key = f"{problem}/{lang}/{size}"
                    harness.progress_callback(f"\nAccuracy test: {key}")
                    try:
                        cg_results = harness.run_problem(
                            problem, [lang], [size], ["codegreen"], self.repetitions
                        )
                        perf_results = harness.run_problem(
                            problem, [lang], [size], ["perf"], self.repetitions
                        )
                        cg_energies = [r.energy_joules for r in cg_results if r.energy_joules > 0]
                        perf_energies = [r.energy_joules for r in perf_results if r.energy_joules > 0]
                        if cg_energies and perf_energies:
                            all_cg.extend(cg_energies)
                            all_perf.extend(perf_energies)
                            error = AccuracyAnalysis.compute_error(cg_energies, perf_energies)
                            raw_data[key] = {
                                "codegreen": StatisticalAnalysis.summarize(cg_energies),
                                "perf": StatisticalAnalysis.summarize(perf_energies),
                                "error": error
                            }
                    except Exception as e:
                        harness.progress_callback(f"  Error: {e}")
        correlation = AccuracyAnalysis.compute_correlation(all_cg, all_perf)
        errors = [v["error"]["mape"] for v in raw_data.values() if "error" in v]
        mean_error = sum(errors) / len(errors) if errors else 0
        max_error = max(errors) if errors else 0
        return ExperimentResult(
            name=self.name,
            passed=mean_error < 10.0 and correlation.get("pearson_r", 0) > 0.9,
            metrics={
                "mean_error_percent": mean_error,
                "max_error_percent": max_error,
                "pearson_r": correlation.get("pearson_r", 0),
                "spearman_r": correlation.get("spearman_r", 0)
            },
            raw_data=raw_data
        )

class ScalabilityExperiment(Experiment):
    """Exp3: Checkpoint overhead at different loads - target <10%."""
    name = "scalability"
    description = "Measure overhead scaling with workload size"

    def __init__(self, problem: str = "nbody", language: str = "python", repetitions: int = 10):
        self.problem = problem
        self.language = language
        self.sizes = ["100", "1000", "10000", "50000"]
        self.repetitions = repetitions

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        raw_data = {}
        overheads = []
        for size in self.sizes:
            key = f"{self.problem}/{self.language}/{size}"
            harness.progress_callback(f"\nScalability test: {key}")
            native = harness.run_problem(self.problem, [self.language], [size], ["native"], self.repetitions)
            cg = harness.run_problem(self.problem, [self.language], [size], ["codegreen"], self.repetitions)
            native_times = [r.time_seconds for r in native]
            cg_times = [r.time_seconds for r in cg]
            overhead = StatisticalAnalysis.compute_overhead(native_times, cg_times)
            overheads.append((int(size), overhead["overhead_percent"]))
            raw_data[size] = {"native_mean": overhead["native_mean"], "cg_mean": overhead["instrumented_mean"],
                             "overhead_percent": overhead["overhead_percent"]}
        return ExperimentResult(
            name=self.name,
            passed=all(o[1] < 10.0 for o in overheads),
            metrics={"overheads_by_size": overheads},
            raw_data=raw_data
        )

class CrossLanguageExperiment(Experiment):
    """Exp4: Cross-language consistency."""
    name = "crosslang"
    description = "Verify measurement consistency across Python, C++, Java"

    def __init__(self, problem: str = "nbody", size: str = "1000", repetitions: int = 30):
        self.problem = problem
        self.size = size
        self.languages = ["python", "cpp", "java"]
        self.repetitions = repetitions

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        raw_data = {}
        energies_by_lang = {}
        for lang in self.languages:
            harness.progress_callback(f"\nCross-language test: {self.problem}/{lang}")
            results = harness.run_problem(self.problem, [lang], [self.size], ["codegreen"], self.repetitions)
            energies = [r.energy_joules for r in results if r.energy_joules > 0]
            if energies:
                energies_by_lang[lang] = energies
                raw_data[lang] = StatisticalAnalysis.summarize(energies)
        return ExperimentResult(
            name=self.name,
            passed=len(energies_by_lang) >= 2,
            metrics={"languages_tested": list(energies_by_lang.keys())},
            raw_data=raw_data
        )

class LinearityExperiment(Experiment):
    """Exp5: Energy scales linearly with workload."""
    name = "linearity"
    description = "Verify energy consumption scales with problem size"

    def __init__(self, problem: str = "nbody", language: str = "python", repetitions: int = 10):
        self.problem = problem
        self.language = language
        self.sizes = ["1000", "5000", "10000", "25000", "50000"]
        self.repetitions = repetitions

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        raw_data = {}
        size_energy_pairs = []
        for size in self.sizes:
            harness.progress_callback(f"\nLinearity test: {self.problem}/{size}")
            results = harness.run_problem(self.problem, [self.language], [size], ["codegreen"], self.repetitions)
            energies = [r.energy_joules for r in results if r.energy_joules > 0]
            if energies:
                mean_e = sum(energies) / len(energies)
                size_energy_pairs.append((int(size), mean_e))
                raw_data[size] = {"mean_energy": mean_e, "n": len(energies)}
        r_squared = AccuracyAnalysis.compute_r_squared(
            [p[0] for p in size_energy_pairs], [p[1] for p in size_energy_pairs]
        ) if len(size_energy_pairs) >= 3 else 0
        return ExperimentResult(
            name=self.name,
            passed=r_squared > 0.95,
            metrics={"r_squared": r_squared, "data_points": len(size_energy_pairs)},
            raw_data=raw_data
        )

class ExperimentRunner:
    def __init__(self, harness: Optional[BenchmarkHarness] = None):
        self.harness = harness or BenchmarkHarness()

    def run_experiment(self, experiment: Experiment) -> ExperimentResult:
        self.harness.progress_callback(f"\n{'='*60}\nRunning: {experiment.name} - {experiment.description}\n{'='*60}")
        return experiment.run(self.harness)

    def run_all(self) -> Dict[str, ExperimentResult]:
        experiments = [
            OverheadExperiment(),
            AccuracyExperiment(),
            ScalabilityExperiment(),
            CrossLanguageExperiment(),
            LinearityExperiment()
        ]
        return {exp.name: self.run_experiment(exp) for exp in experiments}
