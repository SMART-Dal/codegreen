"""Result collection and statistical analysis."""
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from benchmark.config import RunResult

@dataclass
class Stats:
    mean: float
    std: float
    min: float
    max: float
    median: float
    ci95_lower: float
    ci95_upper: float
    n: int

class StatisticalAnalysis:
    @staticmethod
    def summarize(values: List[float]) -> Stats:
        n = len(values)
        if n == 0:
            return Stats(0, 0, 0, 0, 0, 0, 0, 0)
        sorted_vals = sorted(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / max(n - 1, 1)
        std = math.sqrt(variance)
        median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        t_value = 2.045 if n >= 30 else 2.262
        margin = t_value * std / math.sqrt(n) if n > 0 else 0
        return Stats(
            mean=mean, std=std, min=min(values), max=max(values),
            median=median, ci95_lower=mean - margin, ci95_upper=mean + margin, n=n
        )

    @staticmethod
    def compute_overhead(native_times: List[float], instrumented_times: List[float]) -> Dict[str, float]:
        native_mean = sum(native_times) / len(native_times) if native_times else 1
        instr_mean = sum(instrumented_times) / len(instrumented_times) if instrumented_times else 0
        overhead_pct = ((instr_mean - native_mean) / native_mean) * 100 if native_mean > 0 else 0
        return {"native_mean": native_mean, "instrumented_mean": instr_mean, "overhead_percent": overhead_pct}

class ResultCollector:
    def __init__(self):
        self.results: List[RunResult] = []

    def add(self, result: RunResult):
        self.results.append(result)

    def add_all(self, results: List[RunResult]):
        self.results.extend(results)

    def get_by_key(self, problem: str, language: str, size: str, profiler: str) -> List[RunResult]:
        return [r for r in self.results
                if r.problem == problem and r.language == language
                and r.size == size and r.profiler == profiler]

    def summarize_all(self) -> Dict[str, Stats]:
        summaries = {}
        keys = set((r.problem, r.language, r.size, r.profiler) for r in self.results)
        for problem, language, size, profiler in keys:
            results = self.get_by_key(problem, language, size, profiler)
            energies = [r.energy_joules for r in results if r.energy_joules > 0]
            times = [r.time_seconds for r in results]
            key = f"{problem}/{language}/{size}/{profiler}"
            summaries[key] = {
                "energy": StatisticalAnalysis.summarize(energies) if energies else None,
                "time": StatisticalAnalysis.summarize(times),
                "valid_runs": sum(1 for r in results if r.output_valid),
                "total_runs": len(results)
            }
        return summaries

    def to_json(self, path: Path):
        runs = []
        for r in self.results:
            d = asdict(r)
            d["timestamp"] = d["timestamp"].isoformat()
            # Strip full checkpoint array (can be 100K+ entries), keep summary only
            ckpts = d.pop("checkpoints", [])
            if ckpts:
                d["checkpoint_summary"] = {
                    "count": len(ckpts),
                    "first_joules": ckpts[0].get("joules", 0) if ckpts else 0,
                    "last_joules": ckpts[-1].get("joules", 0) if ckpts else 0,
                    "energy_delta": (ckpts[-1].get("joules", 0) - ckpts[0].get("joules", 0)) if len(ckpts) >= 2 else 0.0,
                }
            runs.append(d)
        data = {
            "metadata": {"timestamp": datetime.now().isoformat(), "total_runs": len(self.results)},
            "runs": runs,
            "summary": self._serialize_summary(self.summarize_all()),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _serialize_summary(self, summary: Dict) -> Dict:
        result = {}
        for key, val in summary.items():
            result[key] = {}
            for metric, stats in val.items():
                if isinstance(stats, Stats):
                    result[key][metric] = asdict(stats)
                else:
                    result[key][metric] = stats
        return result

    def to_csv(self, path: Path):
        lines = ["problem,language,size,profiler,repetition,energy_joules,time_seconds,output_valid"]
        for r in self.results:
            lines.append(f"{r.problem},{r.language},{r.size},{r.profiler},{r.repetition},{r.energy_joules:.6f},{r.time_seconds:.6f},{r.output_valid}")
        path.write_text("\n".join(lines))
