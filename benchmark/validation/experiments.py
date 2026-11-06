"""Validation experiments for paper submission."""
import json
import os
import statistics as st
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from benchmark.config import ValidityTolerances
from benchmark.harness import BenchmarkHarness
from benchmark.profilers import CodeGreenProfiler, PerfProfiler
from benchmark.results import StatisticalAnalysis, valid_energies
from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import _measurement_cfg
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
                            harness.progress_callback("  Skipped: no valid results")
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
        per_problem_correlations = []
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
                        cg_energies, perf_energies = valid_energies(cg_results), valid_energies(perf_results)
                        if cg_energies and perf_energies:
                            all_cg.extend(cg_energies)
                            all_perf.extend(perf_energies)
                            error = AccuracyAnalysis.compute_error(cg_energies, perf_energies)
                            per_corr = AccuracyAnalysis.compute_correlation(cg_energies, perf_energies)
                            per_problem_correlations.append(per_corr.get("pearson_r", 0))
                            raw_data[key] = {
                                "codegreen": StatisticalAnalysis.summarize(cg_energies),
                                "perf": StatisticalAnalysis.summarize(perf_energies),
                                "error": error,
                                "correlation": per_corr
                            }
                    except Exception as e:
                        harness.progress_callback(f"  Error: {e}")
        pooled_correlation = AccuracyAnalysis.compute_correlation(all_cg, all_perf)
        min_r = min(per_problem_correlations) if per_problem_correlations else 0
        errors = [v["error"]["mape"] for v in raw_data.values() if "error" in v]
        mean_error = sum(errors) / len(errors) if errors else 0
        max_error = max(errors) if errors else 0
        return ExperimentResult(
            name=self.name,
            passed=mean_error < 10.0 and min_r > 0.9,
            metrics={
                "mean_error_percent": mean_error,
                "max_error_percent": max_error,
                "pooled_pearson_r": pooled_correlation.get("pearson_r", 0),
                "min_per_problem_pearson_r": min_r,
                "pearson_r": min_r,
                "spearman_r": pooled_correlation.get("spearman_r", 0)
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
            energies = valid_energies(results)
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
            energies = valid_energies(results)
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

_MEASURE_ARGS = {"coarse": [], "fine": ["-g", "fine"], "rapl": ["--sensors", "rapl"]}
_VALIDITY_CFG = _measurement_cfg()  # the gap policy codegreen measure judges each run by


def _measure_facts(d: Dict[str, Any]) -> Dict[str, Any]:
    """Facts of one `codegreen measure --json` result that the validity contract must agree with."""
    cps = sorted(d.get("checkpoints") or [], key=lambda c: c["timestamp"])
    s = d.get("summary") or {}
    f = {"energy_j": s.get("total_energy_j"), "exclusive_sum_j": s.get("exclusive_sum_j"), "sampler": d.get("sampler")}
    if len(cps) >= 2:
        steps = list(zip(cps, cps[1:]))
        f.update(window_s=(cps[-1]["timestamp"] - cps[0]["timestamp"]) / 1e9,
                 clamped=sum(c["clamp"] != "none" for c in cps), negative_steps=sum(b["joules"] < a["joules"] for a, b in steps),
                 provider_decreases={p: sum(b["provider_j"][p] < a["provider_j"][p] for a, b in steps) for p in cps[0]["provider_j"]})
    return f


@dataclass
class ValidityExperiment(Experiment):
    """Exp6: the validity contract of codegreen measure/run on any host. Expectations come from each run's own facts
    (window in sampler intervals, sampler affinity, reading gaps, dropped checkpoints, GPU providers), never from host constants;
    starvation protocols pin the whole measured command to the first one or two CPUs of the inherited affinity;
    accuracy is `codegreen run --sensors rapl` against `perf stat -a` at the same CPU domain set."""
    problems: Sequence[str] = ("nbody", "binarytrees")
    languages: Sequence[str] = ("python", "c", "java")
    sizes: Optional[List[str]] = None
    repetitions: int = 5
    modes: Sequence[str] = ("coarse", "fine", "rapl", "run", "perf")
    tol: ValidityTolerances = field(default_factory=ValidityTolerances)
    name = "validity"
    description = "Validity status, invariants, accuracy and repeatability of codegreen measure and run"

    def one(self, harness: BenchmarkHarness, task, mode: str) -> Dict[str, Any]:
        rec: Dict[str, Any] = {"task": task.name, "mode": mode}
        if mode == "perf":
            r = PerfProfiler().run(task.run_command, harness.timeout)
            return {**rec, "energy_j": r.energy_joules, "duration_s": r.time_seconds}
        if mode == "run":
            p = subprocess.run(["codegreen", "run", "-n", "1", "-w", "0", "--no-validate", "--sensors", "rapl", "--json",
                                "--", *task.run_command], capture_output=True, text=True, timeout=harness.timeout + 60)
            d = json.loads(p.stdout)
            return {**rec, "rc": p.returncode, "validity": d.get("validity"),
                    "energy_j": (d.get("energy_j") or {}).get("mean"), "duration_s": (d.get("duration_s") or {}).get("mean")}
        prof = CodeGreenProfiler()
        prof.set_source(task.source_file, task.language)
        prof.extra_args = _MEASURE_ARGS[mode]
        r = prof.run(task.run_command, harness.timeout)
        return {**rec, "validity": r.validity, **_measure_facts(r.raw_data)}

    def expectation(self, r: Dict[str, Any]) -> tuple:
        """(required reasons, allowed reasons, required warnings) of a measure-mode run."""
        smp, req, opt, warn = r["sampler"], set(), set(), set()
        k = r["window_s"] * 1e3 / smp["interval_ms"]
        if k < self.tol.min_window_samples - 1:
            req.add("TOTAL_BELOW_RESOLUTION")
        elif k < self.tol.min_window_samples + 1:
            opt.add("TOTAL_BELOW_RESOLUTION")  # one late reading leaves a window of k intervals spanning k - 1 readings
        if smp["dropped_checkpoints"]:
            req.add("CHECKPOINT_CAP")
        if smp["affinity_cpus"] < self.tol.min_affinity_cpus:
            warn.add("AFFINITY_SINGLE_CPU")
            opt.add("SAMPLER_STARVED")
        pol, iv = _VALIDITY_CFG["gap_policy"][smp["marker_reads"]], smp["interval_ms_max"] * 1e6
        if smp["max_gap_ns"] > pol["max_gap_factor"] * iv or smp["median_gap_ns"] > _VALIDITY_CFG["median_gap_factor"] * iv:
            opt.add("SAMPLER_STARVED")  # the run's own reading gaps exceed the gap policy
        if "SAMPLER_STARVED" in opt:
            opt.add("TOTAL_BELOW_RESOLUTION")  # a starved sampler delivers fewer readings than the window length implies
        if "TOTAL_BELOW_RESOLUTION" in req | opt:
            opt.add("ZERO_ENERGY")  # a window no reading falls inside reports no energy
        if r["mode"] != "rapl" and any(p["hardware_type"] == "gpu" for p in smp["providers"]):
            warn.add("GPU_IN_TOTAL")
        return req, opt, warn

    def run(self, harness: BenchmarkHarness) -> ExperimentResult:
        full = sorted(os.sched_getaffinity(0))
        protocols = {"P": set(full), "A": {full[0]}, "B": set(full[:2])}
        recs = []
        for problem in self.problems:
            for task in harness.tasks(problem, list(self.languages), self.sizes):
                task = harness.suite.build(task)
                for proto, cpus in protocols.items():
                    os.sched_setaffinity(0, cpus)
                    try:
                        for rep in range(self.repetitions):
                            for mode in (self.modes if proto == "P" else ["rapl"]):
                                harness.progress_callback(f"  validity {task.name} {proto} {mode} rep {rep}")
                                try:
                                    rec = self.one(harness, task, mode)
                                except Exception as e:
                                    rec = {"task": task.name, "mode": mode, "error": f"{type(e).__name__}: {e}"}
                                recs.append({"proto": proto, "rep": rep, **rec})
                    finally:
                        os.sched_setaffinity(0, full)
        return self.aggregate(recs)

    def aggregate(self, recs: List[Dict[str, Any]]) -> ExperimentResult:
        tol, mism, inv, decreases, excl = self.tol, [], [], [], []
        errors, recs = [r for r in recs if "error" in r], [r for r in recs if "error" not in r]
        for r in (r for r in recs if r["mode"] in _MEASURE_ARGS):
            v = r["validity"]
            if "window_s" not in r:
                mism.append({"task": r["task"], "mode": r["mode"], "proto": r["proto"], "reasons": v["reasons"], "expected": "a window"})
                continue
            req, opt, warn = self.expectation(r)
            obs = set(v["reasons"])
            if not (req <= obs <= req | opt and warn <= set(v["warnings"]) and (v["status"] == "valid") == (not obs)):
                mism.append({"task": r["task"], "mode": r["mode"], "proto": r["proto"], "reasons": sorted(obs),
                             "warnings": sorted(v["warnings"]), "required": sorted(req), "allowed": sorted(opt),
                             "required_warnings": sorted(warn), "window_s": r["window_s"]})
            if v["status"] == "valid" and (r["clamped"] or r["negative_steps"] or not r["energy_j"] or r["energy_j"] < 0):
                inv.append(r)
            if any(r["provider_decreases"].values()):
                decreases.append(r)
            if (r["mode"] == "fine" and v["status"] == "valid" and "OVERLAPPING_THREADS" not in v["warnings"]
                    and r["exclusive_sum_j"] > r["energy_j"] * (1 + tol.exclusive_rel_tol)):
                excl.append(r)
        inv += [r for r in recs if r["mode"] == "run" and r["validity"]["status"] == "valid" and not (r["energy_j"] or 0) > 0]
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in recs:
            groups.setdefault((r["task"], r["proto"], r["mode"]), []).append(r)

        def ok(rs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return [r for r in rs if r["mode"] == "perf" or r["validity"]["status"] == "valid"]
        cv_fail, perf_rows = [], []
        for (task, proto, mode), rs in groups.items():
            e = [r["energy_j"] for r in ok(rs)]
            w = st.mean(r.get("window_s") or r.get("duration_s") or 0 for r in rs)
            lim = next((c for t, c in sorted(tol.cv_max_pct.items(), reverse=True) if w >= t), None)
            if mode in ("rapl", "run") and lim and len(e) > 1 and st.mean(e) > 0 and st.stdev(e) / st.mean(e) * 100 > lim:
                cv_fail.append({"task": task, "proto": proto, "mode": mode, "cv_pct": st.stdev(e) / st.mean(e) * 100, "limit": lim})
            pg = ok(groups.get((task, proto, "perf"), []))
            if mode == "run" and e and pg:
                ratio, d = st.mean(e) / st.mean(r["energy_j"] for r in pg), st.mean(r["duration_s"] for r in rs)
                perf_rows.append({"task": task, "proto": proto, "duration_s": d, "ratio": ratio,
                                  "fail": d >= tol.run_vs_perf_min_duration_s and abs(ratio - 1) > tol.run_vs_perf_rel_tol})
        starve: Dict[str, Dict[str, Any]] = {}
        for r in (r for r in recs if r.get("sampler")):
            s = starve.setdefault(r["proto"], {"runs": 0, "starved": 0, "max_gap_factor": 0.0})
            s["runs"] += 1
            s["starved"] += "SAMPLER_STARVED" in r["validity"]["reasons"]
            s["max_gap_factor"] = max(s["max_gap_factor"], r["sampler"]["max_gap_ns"] / (r["sampler"]["interval_ms"] * 1e6))
        criteria = {"all_runs_completed": not errors, "validity_matches_expectation": not mism, "valid_runs_invariants": not inv,
                    "no_provider_decreases": not decreases, "exclusive_le_inclusive": not excl,
                    "run_vs_perf": not any(x["fail"] for x in perf_rows), "cv_across_reps": not cv_fail}
        keep = ("task", "mode", "proto", "rep", "energy_j", "validity")
        return ExperimentResult(self.name, all(criteria.values()), criteria, {
            "errors": errors, "mismatches": mism, "invariant_violations": [{k: r.get(k) for k in keep} for r in inv],
            "provider_decreases": [{**{k: r.get(k) for k in keep}, "decreases": r["provider_decreases"]} for r in decreases],
            "exclusive_failures": [{**{k: r.get(k) for k in keep}, "exclusive_sum_j": r["exclusive_sum_j"]} for r in excl],
            "cv_failures": cv_fail, "run_vs_perf": perf_rows, "sampler_starvation": starve, "records": recs})


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


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="CodeGreen measurement-validity suite (portable)")
    ap.add_argument("--problems", nargs="+", default=list(ValidityExperiment.problems))
    ap.add_argument("--languages", nargs="+", default=list(ValidityExperiment.languages))
    ap.add_argument("--sizes", nargs="+")
    ap.add_argument("--reps", type=int, default=ValidityExperiment.repetitions)
    ap.add_argument("--out", required=True, help="JSON file for the criteria and raw records")
    a = ap.parse_args()
    harness = BenchmarkHarness(warmup_runs=0)
    try:
        res = ValidityExperiment(a.problems, a.languages, a.sizes, a.reps).run(harness)
    finally:
        harness.cleanup()
    with open(a.out, "w") as f:
        json.dump({"passed": res.passed, "criteria": res.metrics, **res.raw_data}, f, indent=1, default=str)
    print(json.dumps(res.metrics, indent=1))
    sys.exit(0 if res.passed else 1)
