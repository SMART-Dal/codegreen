"""Result collection and statistical analysis."""
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from benchmark.config import RunResult, SystemState

_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 25: 2.060, 29: 2.045}

def _get_t_value(n: int) -> float:
    df = n - 1
    if df >= 30:
        return 1.96
    if df in _T95:
        return _T95[df]
    candidates = [k for k in _T95 if k <= df]
    return _T95[max(candidates)] if candidates else 12.706

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
    outliers_removed: int = 0

class StatisticalAnalysis:
    @staticmethod
    def _iqr_filter(values: List[float]) -> tuple:
        if len(values) < 4:
            return values, 0
        sorted_v = sorted(values)
        n = len(sorted_v)
        q1 = sorted_v[n // 4]
        q3 = sorted_v[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = [v for v in values if lower <= v <= upper]
        if not filtered:
            return values, 0
        return filtered, len(values) - len(filtered)

    @staticmethod
    def summarize(values: List[float], filter_outliers: bool = True) -> Stats:
        n = len(values)
        if n == 0:
            return Stats(0, 0, 0, 0, 0, 0, 0, 0)
        raw_min, raw_max = min(values), max(values)
        filtered, outliers_removed = StatisticalAnalysis._iqr_filter(values) if filter_outliers else (values, 0)
        fn = len(filtered)
        sorted_vals = sorted(filtered)
        mean = sum(filtered) / fn
        variance = sum((x - mean) ** 2 for x in filtered) / max(fn - 1, 1)
        std = math.sqrt(variance)
        median = sorted_vals[fn // 2] if fn % 2 else (sorted_vals[fn // 2 - 1] + sorted_vals[fn // 2]) / 2
        t_value = _get_t_value(fn)
        margin = t_value * std / math.sqrt(fn) if fn > 0 else 0
        return Stats(
            mean=mean, std=std, min=raw_min, max=raw_max,
            median=median, ci95_lower=mean - margin, ci95_upper=mean + margin,
            n=n, outliers_removed=outliers_removed
        )

    @staticmethod
    def compare(baseline: 'Stats', current: 'Stats') -> Dict[str, float]:
        if baseline.mean == 0:
            return {"delta": current.mean, "delta_pct": 0.0, "regression": False}
        delta = current.mean - baseline.mean
        delta_pct = (delta / baseline.mean) * 100
        ci_overlap = current.ci95_lower <= baseline.ci95_upper and baseline.ci95_lower <= current.ci95_upper
        return {"delta": delta, "delta_pct": delta_pct, "regression": delta_pct > 5.0, "ci_overlap": ci_overlap}

    @staticmethod
    def compute_overhead(native_times: List[float], instrumented_times: List[float]) -> Dict[str, float]:
        native_mean = sum(native_times) / len(native_times) if native_times else 1
        instr_mean = sum(instrumented_times) / len(instrumented_times) if instrumented_times else 0
        overhead_pct = ((instr_mean - native_mean) / native_mean) * 100 if native_mean > 0 else 0
        return {"native_mean": native_mean, "instrumented_mean": instr_mean, "overhead_percent": overhead_pct}

class ComparisonReport:
    """Compare two sets of measurements (e.g., original vs patched, perf vs codegreen)."""

    @staticmethod
    def compare_variants(collector: 'ResultCollector',
                         baseline_variant: str = "original",
                         candidate_variant: str = "patched") -> List[Dict[str, Any]]:
        comparisons = []
        # Group by task (problem + profiler), compare variants
        tasks = {}
        for r in collector.results:
            key = (r.problem.rsplit('/', 1)[0] if '/' in r.problem else r.problem,
                   r.profiler)
            tasks.setdefault(key, {}).setdefault(r.variant, []).append(r)

        for (task_name, profiler), variants in tasks.items():
            baseline = variants.get(baseline_variant, [])
            candidate = variants.get(candidate_variant, [])
            if not baseline or not candidate:
                continue
            b_energies = [r.energy_joules for r in baseline if r.energy_joules > 0]
            c_energies = [r.energy_joules for r in candidate if r.energy_joules > 0]
            if not b_energies or not c_energies:
                continue
            b_stats = StatisticalAnalysis.summarize(b_energies)
            c_stats = StatisticalAnalysis.summarize(c_energies)
            delta = StatisticalAnalysis.compare(b_stats, c_stats)

            # Wilcoxon if enough samples
            p_value, significant = 1.0, False
            if len(b_energies) >= 3 and len(c_energies) >= 3:
                try:
                    from scipy.stats import wilcoxon
                    min_len = min(len(b_energies), len(c_energies))
                    stat, p_value = wilcoxon(b_energies[:min_len], c_energies[:min_len])
                    significant = p_value < 0.05
                except (ImportError, ValueError):
                    pass

            comparisons.append({
                "task": task_name,
                "profiler": profiler,
                "baseline_variant": baseline_variant,
                "candidate_variant": candidate_variant,
                "baseline_energy": b_stats,
                "candidate_energy": c_stats,
                "delta_pct": delta["delta_pct"],
                "p_value": p_value,
                "significant": significant,
                "n_baseline": len(b_energies),
                "n_candidate": len(c_energies),
            })
        return comparisons

    @staticmethod
    def compare_profilers(collector: 'ResultCollector',
                          baseline_profiler: str = "perf",
                          test_profiler: str = "codegreen") -> List[Dict[str, Any]]:
        comparisons = []
        tasks = {}
        for r in collector.results:
            key = (r.problem, r.variant)
            tasks.setdefault(key, {}).setdefault(r.profiler, []).append(r)

        for (task_name, variant), profilers in tasks.items():
            baseline = profilers.get(baseline_profiler, [])
            test = profilers.get(test_profiler, [])
            if not baseline or not test:
                continue
            b_energies = [r.energy_joules for r in baseline if r.energy_joules > 0]
            t_energies = [r.energy_joules for r in test if r.energy_joules > 0]
            if not b_energies or not t_energies:
                continue
            b_mean = sum(b_energies) / len(b_energies)
            t_mean = sum(t_energies) / len(t_energies)
            error_pct = abs(t_mean - b_mean) / b_mean * 100 if b_mean > 0 else 0

            comparisons.append({
                "task": task_name,
                "variant": variant,
                "baseline_profiler": baseline_profiler,
                "test_profiler": test_profiler,
                "baseline_mean_j": b_mean,
                "test_mean_j": t_mean,
                "error_pct": error_pct,
                "n_baseline": len(b_energies),
                "n_test": len(t_energies),
            })
        return comparisons


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
        system_state = SystemState.capture()
        data = {
            "metadata": {"timestamp": datetime.now().isoformat(), "total_runs": len(self.results)},
            "system_state": asdict(system_state),
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

    def to_markdown(self) -> str:
        summary = self.summarize_all()
        lines = ["| Problem | Language | Size | Profiler | Energy (J) | Std | Time (s) | Valid | N |",
                 "|---------|----------|------|----------|-----------|-----|----------|-------|---|"]
        for key, data in sorted(summary.items()):
            parts = key.split("/")
            e = data.get("energy")
            t = data.get("time")
            e_str = f"{e.mean:.4f} +/- {e.std:.4f}" if e else "N/A"
            e_std = f"{e.std:.4f}" if e else "-"
            t_str = f"{t.mean:.4f}" if t else "-"
            lines.append(f"| {parts[0]} | {parts[1]} | {parts[2]} | {parts[3]} "
                         f"| {e_str} | {e_std} | {t_str} | {data['valid_runs']}/{data['total_runs']} | {t.n if t else 0} |")
        return "\n".join(lines)

    def to_text(self) -> str:
        summary = self.summarize_all()
        lines = []
        for key, data in sorted(summary.items()):
            e = data.get("energy")
            t = data.get("time")
            e_str = f"{e.mean:.4f}J (std={e.std:.4f}, CI=[{e.ci95_lower:.4f}, {e.ci95_upper:.4f}])" if e else "N/A"
            t_str = f"{t.mean:.4f}s" if t else "-"
            valid = f"{data['valid_runs']}/{data['total_runs']}"
            lines.append(f"  {key}: {e_str}, {t_str}, valid={valid}")
        return "\n".join(lines)
