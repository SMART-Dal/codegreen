"""Benchmark configuration dataclasses and YAML loader."""
import platform
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

@dataclass
class SystemState:
    cpu_model: str = ""
    cpu_governor: str = ""
    kernel_version: str = ""
    power_events: List[str] = field(default_factory=list)

    @classmethod
    def capture(cls) -> "SystemState":
        state = cls()
        state.kernel_version = platform.release()
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        state.cpu_model = line.split(":", 1)[1].strip()
                        break
        except (FileNotFoundError, OSError):
            pass
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
                state.cpu_governor = f.read().strip()
        except (FileNotFoundError, OSError):
            pass
        from benchmark.profilers import perf_power_events
        state.power_events = perf_power_events()
        return state

@dataclass
class Problem:
    name: str
    sizes: List[str]
    validation_output: Optional[str] = None

@dataclass
class LanguageEnv:
    extension: str
    run_cmd: str
    compiler: Optional[str] = None
    flags: List[str] = field(default_factory=list)

@dataclass
class RunResult:
    problem: str
    language: str
    size: str
    profiler: str
    energy_joules: Optional[float]
    time_seconds: float
    output_valid: bool
    repetition: int = 0
    variant: str = "default"
    suite: str = "benchmarksgame"
    timestamp: datetime = field(default_factory=datetime.now)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    validity: Optional[Dict[str, Any]] = None

    @property
    def measurement_valid(self) -> bool:
        """No fatal validity reason; profilers without a validity contract (perf, native) report None."""
        return self.validity is None or self.validity["status"] == "valid"

# perf power events summed as the CPU-scope truth, mirroring the RAPL adapters' top-level domain rule: the first set
# whose first event the power PMU offers wins (psys supersedes package + dram), using the offered events of that set.
PERF_CPU_EVENT_SETS = (("energy-psys",), ("energy-pkg", "energy-ram"))

@dataclass
class ValidityTolerances:
    """Expectations of benchmark.validation.experiments.ValidityExperiment. Windows are in sampler intervals
    (sampler.interval_ms of the run itself); a window below min_window_samples - 1 intervals must be flagged
    TOTAL_BELOW_RESOLUTION, one at or above min_window_samples + 1 must not, the two intervals between are either (one
    late reading costs the window a reading). A sampler allowed on fewer than min_affinity_cpus CPUs must raise the
    AFFINITY_SINGLE_CPU warning and may be SAMPLER_STARVED, as may any run whose reading gaps exceed codegreen's gap policy.
    cv_max_pct maps a minimum window (s) to the largest CV (%) of valid energies across repetitions."""
    min_window_samples: int = 2
    min_affinity_cpus: int = 2
    exclusive_rel_tol: float = 0.01
    run_vs_perf_rel_tol: float = 0.03
    run_vs_perf_min_duration_s: float = 1.0
    cv_max_pct: Dict[float, float] = field(default_factory=lambda: {1.0: 5.0, 0.1: 10.0})

@dataclass
class BenchmarkConfig:
    problems: List[Problem]
    languages: Dict[str, LanguageEnv]
    repetitions: int = 30
    warmup_runs: int = 1
    timeout_seconds: int = 60
    clear_cache: bool = True
    cpu_governor: str = "performance"
    min_runtime_seconds: float = 1.0
    mode: str = "local"
    benchmarks_dir: Optional[str] = None

    @classmethod
    def from_yaml(cls, path: Path) -> "BenchmarkConfig":
        if yaml is None:
            raise ImportError("PyYAML required for YAML config: pip install pyyaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        cfg = data.get("benchmark", data)
        problems = [Problem(**p) for p in cfg.get("problems", [])]
        languages = {k: LanguageEnv(**v) for k, v in cfg.get("languages", {}).items()}
        return cls(
            problems=problems,
            languages=languages,
            repetitions=cfg.get("repetitions", 30),
            warmup_runs=cfg.get("warmup_runs", 3),
            timeout_seconds=cfg.get("timeout_seconds", 300),
            clear_cache=cfg.get("best_practices", {}).get("clear_cache", True),
            cpu_governor=cfg.get("best_practices", {}).get("cpu_governor", "performance"),
            min_runtime_seconds=cfg.get("min_runtime_seconds", 1.0),
            mode=cfg.get("mode", "local"),
            benchmarks_dir=cfg.get("benchmarks_dir"),
        )

    @classmethod
    def default(cls) -> "BenchmarkConfig":
        return cls(
            problems=[
                Problem("nbody", ["1000", "5000", "50000"], "1000_out"),
                Problem("spectralnorm", ["100", "500", "1000"], "100_out"),
                Problem("binarytrees", ["10", "14", "18"], "10_out"),
                Problem("fannkuchredux", ["7", "10", "11"], "7_out"),
            ],
            languages={
                "python": LanguageEnv(".python3", "python3 {source}"),
                "c": LanguageEnv(".gcc", "{binary}", compiler="gcc", flags=["-O3", "-march=native", "-lm", "-lpthread"]),
                "cpp": LanguageEnv(".gpp", "{binary}", compiler="g++", flags=["-O3", "-march=native", "-lpthread"]),
                "java": LanguageEnv(".java", "java -cp {build_dir} {class_name}", compiler="javac", flags=[]),
            },
            repetitions=5,
            warmup_runs=1,
            timeout_seconds=180,
        )
