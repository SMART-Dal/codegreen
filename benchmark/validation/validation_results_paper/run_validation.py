#!/usr/bin/env python3
"""CodeGreen Validation Script - Runs comprehensive benchmarks across all languages."""
import subprocess, json, re, time, os, sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

BASE = Path(__file__).parent.parent
LIB_PATH = BASE / "codegreen" / "lib"
RUNTIME_PATH = BASE / "codegreen" / "bin" / "runtime"
JAVA_RT = BASE / "codegreen" / "instrumentation" / "language_runtimes" / "java"
BENCH_PATH = BASE / "benchmark" / "benchmarksgame"
SLEEP_BETWEEN = 2

# Base tooling costs (measured empirically)
BASE_COST = {"C": 0.125, "C++": 0.125, "Java": 0.3, "Python": 0.15}  # seconds
PER_CHECKPOINT_US = 1.8  # microseconds per checkpoint

@dataclass
class BenchResult:
    benchmark: str
    language: str
    granularity: str  # "coarse" or "fine"
    size: str
    native_time: float
    inst_time: float
    energy_J: float
    raw_overhead_pct: float
    normalized_overhead_pct: float
    checkpoints: int

def run_timed(cmd: List[str], env: dict = None, runs: int = 3) -> float:
    times = []
    for _ in range(runs):
        time.sleep(0.5)
        start = time.perf_counter()
        subprocess.run(cmd, capture_output=True, timeout=300, env=env)
        times.append(time.perf_counter() - start)
    return sum(times) / len(times)

def get_perf_energy(cmd: List[str], runs: int = 3) -> float:
    energies = []
    for _ in range(runs):
        time.sleep(0.5)
        r = subprocess.run(['perf', 'stat', '-e', 'power/energy-pkg/', '--'] + cmd,
            capture_output=True, text=True, timeout=300)
        m = re.search(r'([\d.,]+)\s+Joules\s+power/energy-pkg/', r.stderr)
        if m:
            energies.append(float(m.group(1).replace(',', '')))
    return sum(energies) / len(energies) if energies else 0

def parse_cg_output(output: str) -> tuple:
    if "CODEGREEN_RESULT_START" not in output:
        return 0.0, 0
    try:
        start = output.index("--- CODEGREEN_RESULT_START ---") + len("--- CODEGREEN_RESULT_START ---")
        end = output.index("--- CODEGREEN_RESULT_END ---")
        raw = json.loads(output[start:end].strip())
        m = raw.get("measurements", [])
        if m:
            return m[-1].get("joules", 0) - m[0].get("joules", 0), len(m)
    except:
        pass
    return 0.0, 0

def run_instrumented(lang: str, inst_file: Path, size: str) -> tuple:
    if not inst_file.exists():
        return 0, 0, 0, f"Not found: {inst_file}"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME_PATH)
    env["LD_LIBRARY_PATH"] = str(LIB_PATH)

    if lang == "python3":
        cmd = ["python3", str(inst_file), size]
        start = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        elapsed = time.perf_counter() - start
    elif lang == "gcc":
        binary = inst_file.parent / f"{inst_file.stem}.out"
        comp = subprocess.run(['gcc', '-x', 'c', '-O3', str(inst_file), '-o', str(binary),
            '-L', str(LIB_PATH), '-lcodegreen-nemb', '-lm', f'-Wl,-rpath,{LIB_PATH}'], capture_output=True)
        if comp.returncode != 0:
            return 0, 0, 0, "C compile fail"
        start = time.perf_counter()
        r = subprocess.run([str(binary), size], capture_output=True, text=True, timeout=300)
        elapsed = time.perf_counter() - start
    elif lang == "gpp":
        binary = inst_file.parent / f"{inst_file.stem}.out"
        comp = subprocess.run(['g++', '-x', 'c++', '-O3', '-std=c++17', str(inst_file), '-o', str(binary),
            '-L', str(LIB_PATH), '-lcodegreen-nemb', '-lm', f'-Wl,-rpath,{LIB_PATH}'], capture_output=True)
        if comp.returncode != 0:
            return 0, 0, 0, "C++ compile fail"
        start = time.perf_counter()
        r = subprocess.run([str(binary), size], capture_output=True, text=True, timeout=300)
        elapsed = time.perf_counter() - start
    elif lang == "java":
        comp = subprocess.run(['javac', '-cp', str(JAVA_RT), str(inst_file)], capture_output=True)
        if comp.returncode != 0:
            return 0, 0, 0, "Java compile fail"
        cp = f"{JAVA_RT}:{inst_file.parent}"
        start = time.perf_counter()
        r = subprocess.run(['java', f'-Djava.library.path={LIB_PATH}', '-cp', cp, inst_file.stem, size],
            capture_output=True, text=True, timeout=300, env=env)
        elapsed = time.perf_counter() - start
    else:
        return 0, 0, 0, f"Unknown: {lang}"
    energy, ckpts = parse_cg_output(r.stdout + r.stderr)
    return elapsed, energy, ckpts, None

def compile_native(lang: str, src: Path, out: Path) -> bool:
    if lang == "gcc":
        r = subprocess.run(['gcc', '-x', 'c', '-O3', str(src), '-o', str(out), '-lm'], capture_output=True)
    elif lang == "gpp":
        r = subprocess.run(['g++', '-x', 'c++', '-O3', '-std=c++17', str(src), '-o', str(out), '-lm'], capture_output=True)
    elif lang == "java":
        r = subprocess.run(['javac', str(src)], capture_output=True, cwd=src.parent)
    else:
        return True
    return r.returncode == 0

BENCHMARKS = [
    # Coarse-grained (program-level): only main entry/exit
    {"name": "nbody", "size": "500000", "granularity": "coarse", "langs": [
        {"lang": "C", "key": "gcc", "inst": "nbody_coarse.gcc", "native": "nbody.gcc"},
        {"lang": "C++", "key": "gpp", "inst": "nbody_coarse.gpp", "native": "nbody.gpp"},
        {"lang": "Java", "key": "java", "inst": "nbody_coarse.java", "native": "nbody.java"},
        {"lang": "Python", "key": "python3", "inst": "nbody_coarse.python3", "native": "nbody.python3"},
    ]},
    # Fine-grained (method-level): entry/exit for each method
    {"name": "nbody", "size": "500000", "granularity": "fine", "langs": [
        {"lang": "C", "key": "gcc", "inst": "nbody_instrumented.gcc", "native": "nbody.gcc"},
        {"lang": "C++", "key": "gpp", "inst": "nbody_instrumented.gpp", "native": "nbody.gpp"},
        {"lang": "Java", "key": "java", "inst": "nbody_instrumented.java", "native": "nbody.java"},
        {"lang": "Python", "key": "python3", "inst": "nbody_instrumented.python3", "native": "nbody.python3"},
    ]},
    {"name": "fannkuchredux", "size": "10", "granularity": "fine", "langs": [
        {"lang": "C", "key": "gcc", "inst": "fannkuchredux_instrumented.gcc", "native": "fannkuchredux.gcc"},
        {"lang": "C++", "key": "gpp", "inst": "fannkuchredux_instrumented.gpp", "native": "fannkuchredux.gpp-3.gpp"},
        {"lang": "Java", "key": "java", "inst": "fannkuchredux_instrumented.java", "native": "fannkuchredux.java"},
        {"lang": "Python", "key": "python3", "inst": "fannkuchredux_instrumented.python3", "native": "fannkuchredux.python3"},
    ]},
    {"name": "binarytrees", "size": "18", "granularity": "fine", "langs": [
        {"lang": "C", "key": "gcc", "inst": "binarytrees_instrumented.gcc", "native": "binarytrees.gcc"},
        {"lang": "C++", "key": "gpp", "inst": "binarytrees_instrumented.gpp", "native": "binarytrees.gpp-2.gpp"},
        {"lang": "Java", "key": "java", "inst": "binarytrees_instrumented.java", "native": "binarytrees.java-2.java"},
    ]},
    {"name": "binarytrees", "size": "14", "granularity": "fine", "langs": [
        {"lang": "Python", "key": "python3", "inst": "binarytrees_instrumented.python3", "native": "binarytrees.python3"},
    ]},
]

def run_overhead_validation() -> List[BenchResult]:
    results = []
    for bench in BENCHMARKS:
        bench_dir = BENCH_PATH / bench["name"]
        granularity = bench.get("granularity", "fine")
        for cfg in bench["langs"]:
            print(f"  {bench['name']:15} {cfg['lang']:8} ({granularity})...", end=" ", flush=True)
            time.sleep(SLEEP_BETWEEN)
            native_src = bench_dir / cfg["native"]
            if not native_src.exists():
                print("SKIP (no native)")
                continue
            if cfg["key"] in ("gcc", "gpp"):
                native_bin = bench_dir / f"{native_src.stem}_native.out"
                if not compile_native(cfg["key"], native_src, native_bin):
                    print("SKIP (compile)")
                    continue
                native_time = run_timed([str(native_bin), bench["size"]])
            elif cfg["key"] == "java":
                compile_native("java", native_src, None)
                native_time = run_timed(['java', '-cp', str(bench_dir), native_src.stem, bench["size"]])
            else:
                native_time = run_timed(['python3', str(native_src), bench["size"]])
            inst_file = bench_dir / cfg["inst"]
            inst_time, energy, ckpts, err = run_instrumented(cfg["key"], inst_file, bench["size"])
            if err or energy <= 0:
                print(f"FAIL ({err or '0 energy'})")
                continue
            # Raw overhead: (instrumented - native) / native
            raw_overhead = (inst_time - native_time) / native_time * 100
            # Normalized overhead: subtract base tooling cost
            base_cost = BASE_COST.get(cfg["lang"], 0.15)
            checkpoint_cost = ckpts * PER_CHECKPOINT_US / 1e6  # convert to seconds
            tooling_cost = base_cost + checkpoint_cost
            normalized_overhead = (inst_time - native_time - tooling_cost) / native_time * 100
            normalized_overhead = max(0, normalized_overhead)  # can't be negative
            results.append(BenchResult(bench["name"], cfg["lang"], granularity, bench["size"],
                round(native_time, 4), round(inst_time, 4), round(energy, 3),
                round(raw_overhead, 1), round(normalized_overhead, 1), ckpts))
            print(f"raw={raw_overhead:.1f}% norm={normalized_overhead:.1f}% E={energy:.1f}J ckpts={ckpts}")
    return results

def run_accuracy_validation() -> Dict:
    print("\nAccuracy (CodeGreen vs Perf RAPL):")
    results = []
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME_PATH)
    coarse = BENCH_PATH / "nbody" / "nbody_coarse.python3"
    native = BENCH_PATH / "nbody" / "nbody.python3"
    for size in [100000, 250000, 500000]:
        time.sleep(SLEEP_BETWEEN)
        print(f"  n={size}...", end=" ", flush=True)
        perf_j = get_perf_energy(['python3', str(native), str(size)])
        r = subprocess.run(['python3', str(coarse), str(size)], capture_output=True, text=True, timeout=300, env=env)
        cg_j, _ = parse_cg_output(r.stdout + r.stderr)
        if cg_j > 0 and perf_j > 0:
            err = abs(cg_j - perf_j) / perf_j * 100
            results.append({"size": size, "codegreen_J": round(cg_j, 2), "perf_J": round(perf_j, 2), "error_pct": round(err, 1)})
            print(f"CG={cg_j:.1f}J Perf={perf_j:.1f}J err={err:.1f}%")
        else:
            print("FAIL")
    if len(results) >= 2:
        cg, perf = [r["codegreen_J"] for r in results], [r["perf_J"] for r in results]
        mean_cg, mean_perf = sum(cg)/len(cg), sum(perf)/len(perf)
        num = sum((c-mean_cg)*(p-mean_perf) for c,p in zip(cg, perf))
        den = (sum((c-mean_cg)**2 for c in cg) * sum((p-mean_perf)**2 for p in perf))**0.5
        r_corr = num/den if den > 0 else 0
        return {"data": results, "mean_error_pct": round(sum(r["error_pct"] for r in results)/len(results), 2),
                "correlation_r": round(r_corr, 4), "r_squared": round(r_corr**2, 4)}
    return {"data": results}

def run_linearity_validation() -> Dict:
    print("\nLinearity (energy vs workload):")
    results = []
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME_PATH)
    coarse = BENCH_PATH / "nbody" / "nbody_coarse.python3"
    for size in [50000, 100000, 200000, 400000, 800000]:
        time.sleep(SLEEP_BETWEEN)
        print(f"  n={size}...", end=" ", flush=True)
        r = subprocess.run(['python3', str(coarse), str(size)], capture_output=True, text=True, timeout=300, env=env)
        energy, _ = parse_cg_output(r.stdout + r.stderr)
        if energy > 0:
            results.append({"size": size, "energy_J": round(energy, 2)})
            print(f"E={energy:.1f}J")
        else:
            print("FAIL")
    if len(results) >= 3:
        x, y = [r["size"] for r in results], [r["energy_J"] for r in results]
        n, sum_x, sum_y = len(x), sum(x), sum(y)
        sum_xy, sum_x2 = sum(xi*yi for xi,yi in zip(x,y)), sum(xi**2 for xi in x)
        denom = n*sum_x2 - sum_x**2
        if denom > 0:
            slope = (n*sum_xy - sum_x*sum_y) / denom
            intercept = (sum_y - slope*sum_x) / n
            ss_res = sum((yi-(slope*xi+intercept))**2 for xi,yi in zip(x,y))
            ss_tot = sum((yi-sum_y/n)**2 for yi in y)
            r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
            return {"data": results, "r_squared": round(r2, 4)}
    return {"data": results}

def main():
    print("=" * 70)
    print("CodeGreen Validation Suite")
    print("=" * 70)
    print(f"\nBase tooling costs: C/C++={BASE_COST['C']*1000:.0f}ms Python={BASE_COST['Python']*1000:.0f}ms Java={BASE_COST['Java']*1000:.0f}ms")
    print(f"Per-checkpoint cost: {PER_CHECKPOINT_US:.1f}μs")
    print("\n1. Overhead Validation:")
    overhead = run_overhead_validation()
    accuracy = run_accuracy_validation()
    linearity = run_linearity_validation()
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if overhead:
        # Group by granularity
        coarse = [r for r in overhead if r.granularity == "coarse"]
        fine = [r for r in overhead if r.granularity == "fine"]
        print(f"\nCOARSE-GRAINED (program-level, {len(coarse)} benchmarks):")
        if coarse:
            for r in coarse:
                print(f"  {r.benchmark:15} {r.language:8}: raw={r.raw_overhead_pct:6.1f}%  norm={r.normalized_overhead_pct:6.1f}%  ckpts={r.checkpoints}")
        print(f"\nFINE-GRAINED (method-level, {len(fine)} benchmarks):")
        if fine:
            by_lang = {}
            for r in fine:
                by_lang.setdefault(r.language, []).append((r.raw_overhead_pct, r.normalized_overhead_pct))
            for lang, vals in sorted(by_lang.items()):
                raw_mean = sum(v[0] for v in vals) / len(vals)
                norm_mean = sum(v[1] for v in vals) / len(vals)
                print(f"  {lang:8}: raw_mean={raw_mean:7.1f}%  normalized_mean={norm_mean:7.1f}%")
    print(f"\nAccuracy: error={accuracy.get('mean_error_pct', 'N/A')}%  R²={accuracy.get('r_squared', 'N/A')}")
    print(f"Linearity: R²={linearity.get('r_squared', 'N/A')}")
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_costs": {"c_cpp_ms": BASE_COST["C"]*1000, "python_ms": BASE_COST["Python"]*1000,
                      "java_ms": BASE_COST["Java"]*1000, "per_checkpoint_us": PER_CHECKPOINT_US},
        "overhead": [asdict(r) for r in overhead],
        "accuracy": accuracy, "linearity": linearity
    }
    out_file = Path(__file__).parent / "validation_results.json"
    out_file.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {out_file}")

if __name__ == "__main__":
    main()
