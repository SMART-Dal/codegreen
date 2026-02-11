"""LaTeX table and plot generation for paper."""
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from validation.experiments import ExperimentResult
from benchmark.results import Stats

class LaTeXTableGenerator:
    @staticmethod
    def overhead_table(result: ExperimentResult) -> str:
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Instrumentation Overhead}",
            "\\begin{tabular}{llrrr}",
            "\\toprule",
            "Benchmark & Language & Native (s) & CodeGreen (s) & Overhead (\\%) \\\\",
            "\\midrule"
        ]
        for key, data in result.raw_data.items():
            parts = key.split("/")
            if len(parts) >= 2:
                problem, lang = parts[0], parts[1]
                native = data.get("native", {})
                cg = data.get("codegreen", {})
                overhead = data.get("overhead_percent", 0)
                native_mean = native.mean if isinstance(native, Stats) else native.get("mean", 0)
                cg_mean = cg.mean if isinstance(cg, Stats) else cg.get("mean", 0)
                lines.append(f"{problem} & {lang} & {native_mean:.4f} & {cg_mean:.4f} & {overhead:.2f} \\\\")
        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}"
        ])
        return "\n".join(lines)

    @staticmethod
    def accuracy_table(result: ExperimentResult) -> str:
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Measurement Accuracy vs RAPL}",
            "\\begin{tabular}{llrrrr}",
            "\\toprule",
            "Benchmark & Lang & CodeGreen (J) & RAPL (J) & Error (\\%) & r \\\\",
            "\\midrule"
        ]
        for key, data in result.raw_data.items():
            parts = key.split("/")
            if len(parts) >= 2:
                problem, lang = parts[0], parts[1]
                cg = data.get("codegreen", {})
                perf = data.get("perf", {})
                error = data.get("error", {})
                cg_mean = cg.mean if isinstance(cg, Stats) else cg.get("mean", 0)
                perf_mean = perf.mean if isinstance(perf, Stats) else perf.get("mean", 0)
                mape = error.get("mape", 0) if isinstance(error, dict) else 0
                lines.append(f"{problem} & {lang} & {cg_mean:.2f} & {perf_mean:.2f} & {mape:.2f} & - \\\\")
        r = result.metrics.get("pearson_r", 0)
        lines.extend([
            "\\midrule",
            f"\\multicolumn{{6}}{{l}}{{Overall Pearson r: {r:.4f}}} \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}"
        ])
        return "\n".join(lines)

    @staticmethod
    def summary_table(results: Dict[str, ExperimentResult]) -> str:
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\caption{Validation Summary}",
            "\\begin{tabular}{lcc}",
            "\\toprule",
            "Experiment & Result & Status \\\\",
            "\\midrule"
        ]
        for name, result in results.items():
            status = "\\checkmark" if result.passed else "\\times"
            key_metric = ""
            if name == "overhead":
                key_metric = f"Max: {result.metrics.get('max_overhead_percent', 0):.2f}\\%"
            elif name == "accuracy":
                key_metric = f"r={result.metrics.get('pearson_r', 0):.3f}"
            elif name == "linearity":
                key_metric = f"R^2={result.metrics.get('r_squared', 0):.3f}"
            lines.append(f"{name} & {key_metric} & {status} \\\\")
        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

class PlotGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def accuracy_scatter(self, codegreen: List[float], rapl: List[float], title: str = "Accuracy"):
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.scatter(rapl, codegreen, alpha=0.6)
            max_val = max(max(rapl), max(codegreen)) * 1.1
            ax.plot([0, max_val], [0, max_val], 'r--', label='Perfect agreement')
            ax.set_xlabel("RAPL Energy (J)")
            ax.set_ylabel("CodeGreen Energy (J)")
            ax.set_title(title)
            ax.legend()
            ax.set_xlim(0, max_val)
            ax.set_ylim(0, max_val)
            fig.savefig(self.output_dir / "accuracy_scatter.png", dpi=150, bbox_inches='tight')
            plt.close(fig)
        except ImportError:
            pass

    def overhead_bar_chart(self, data: Dict[str, float], title: str = "Overhead"):
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            labels = list(data.keys())
            values = list(data.values())
            ax.bar(labels, values, color='steelblue')
            ax.axhline(y=1.0, color='r', linestyle='--', label='1% threshold')
            ax.set_ylabel("Overhead (%)")
            ax.set_title(title)
            ax.legend()
            plt.xticks(rotation=45, ha='right')
            fig.savefig(self.output_dir / "overhead_bar.png", dpi=150, bbox_inches='tight')
            plt.close(fig)
        except ImportError:
            pass

    def linearity_plot(self, sizes: List[int], energies: List[float], title: str = "Linearity"):
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.plot(sizes, energies, 'o-', markersize=8)
            ax.set_xlabel("Problem Size (N)")
            ax.set_ylabel("Energy (J)")
            ax.set_title(title)
            fig.savefig(self.output_dir / "linearity_plot.png", dpi=150, bbox_inches='tight')
            plt.close(fig)
        except ImportError:
            pass
