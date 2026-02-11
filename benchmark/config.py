"""Benchmark configuration dataclasses and YAML loader."""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

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
    energy_joules: float
    time_seconds: float
    output_valid: bool
    repetition: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class BenchmarkConfig:
    problems: List[Problem]
    languages: Dict[str, LanguageEnv]
    repetitions: int = 30
    warmup_runs: int = 1
    timeout_seconds: int = 60
    clear_cache: bool = True
    cpu_governor: str = "performance"

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
