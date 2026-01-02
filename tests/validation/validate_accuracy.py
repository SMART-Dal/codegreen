
import subprocess
import json
import re
import os
import statistics
from pathlib import Path

def run_codegreen(script_path):
    cmd = ["codegreen", "measure", "python", str(script_path), "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        checkpoints = data.get("measurement", {}).get("checkpoints", [])
        if not checkpoints:
            return None
        
        # We look for the workload function checkpoints
        # The instrumented function is named workload
        workload_cps = [cp for cp in checkpoints if ":workload:" in cp["checkpoint_id"]]
        if len(workload_cps) < 2:
            # Fallback to absolute delta of all checkpoints if workload specific not found
            joules = [cp["joules"] for cp in checkpoints]
            return max(joules) - min(joules)
        
        joules = [cp["joules"] for cp in workload_cps]
        return max(joules) - min(joules)
    except Exception as e:
        print(f"CodeGreen Error on {script_path}: {e}")
        return None

def run_perf(script_path):
    # perf outputs energy to stderr
    cmd = ["perf", "stat", "-e", "power/energy-pkg/", "python3", str(script_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        # Regex to find "1.23 Joules power/energy-pkg/"
        match = re.search(r"([\d,.]+)\s+Joules\s+power/energy-pkg/", result.stderr)
        if match:
            val = match.group(1).replace(",", "")
            return float(val)
        return None
    except Exception as e:
        print(f"Perf Error on {script_path}: {e}")
        return None

def validate():
    test_dir = Path("tests/validation")
    # Strictly match only v*.py and exclude any instrumented variants or the runner itself
    scripts = sorted([s for s in test_dir.glob("v[0-9]*.py") if "_instrumented" not in s.name])
    
    print(f"Starting validation on {len(scripts)} scripts...")
    print(f"{'Script':<25} | {'CG Avg (J)':<12} | {'Perf Avg (J)':<12} | {'Delta (%)':<10}")
    print("-" * 70)
    
    for script in scripts:
        cg_runs = []
        perf_runs = []
        
        print(f"Testing {script.name}...", end=" ", flush=True)
        # 5 runs each
        for i in range(5):
            print(f"CG{i+1}", end="", flush=True)
            val = run_codegreen(script)
            if val is not None: cg_runs.append(val)
            
            print(f".P{i+1} ", end="", flush=True)
            val = run_perf(script)
            if val is not None: perf_runs.append(val)
            
        print("Done.")
        if not cg_runs or not perf_runs:
            print(f"{script.name:<25} | {'Error':<12} | {'Error':<12} | {'N/A'}")
            continue
            
        cg_avg = statistics.mean(cg_runs)
        perf_avg = statistics.mean(perf_runs)
        
        # Delta calculation
        delta = ((cg_avg - perf_avg) / perf_avg) * 100 if perf_avg > 0 else 0
        
        print(f"{script.name:<25} | {cg_avg:<12.4f} | {perf_avg:<12.4f} | {delta:<+10.2f}%")

if __name__ == "__main__":
    validate()
