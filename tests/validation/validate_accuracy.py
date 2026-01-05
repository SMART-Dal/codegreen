import subprocess
import json
import re
import os
import statistics
from pathlib import Path
import shutil

# Ensure logs directory exists
LOG_DIR = Path("tests/validation/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_execution(script_name, message, level="INFO"):
    log_file = LOG_DIR / f"{script_name}.log"
    with open(log_file, "a") as f:
        f.write(f"[{level}] {message}\n")

def run_command_with_logging(cmd, script_name, description):
    log_execution(script_name, f"--- Executing: {description} ---")
    log_execution(script_name, f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        log_execution(script_name, f"Return Code: {result.returncode}")
        if result.stdout:
            log_execution(script_name, f"Stdout:\n{result.stdout}")
        if result.stderr:
            log_execution(script_name, f"Stderr:\n{result.stderr}")
        return result
    except subprocess.TimeoutExpired:
        log_execution(script_name, "TIMEOUT EXPIRED (120s)", "ERROR")
        return None
    except Exception as e:
        log_execution(script_name, f"Exception: {e}", "ERROR")
        return None

def run_codegreen(script_path):
    script_name = Path(script_path).name
    ext = Path(script_path).suffix
    lang_map = {
        ".py": "python",
        ".c": "c",
        ".cpp": "cpp",
        ".java": "java"
    }
    lang = lang_map.get(ext)
    if not lang:
        return None
        
    cmd = ["codegreen", "measure", lang, str(script_path), "--json", "--no-cleanup"]
    
    result = run_command_with_logging(cmd, script_name, "CodeGreen Measure")
    
    if not result:
        return None
        
    if result.returncode != 0:
        return None
        
    try:
        data = json.loads(result.stdout)
        
        # Log the location of any preserved files from stdout if possible
        # (stdout is JSON, but maybe verbose logs in stderr have it)
        # We can look for "/tmp/codegreen_" in stderr to find preserved files
        matches = re.findall(r"(/tmp/codegreen_\S+)", result.stderr)
        if matches:
            log_execution(script_name, f"Preserved intermediate files might be at: {matches}", "INFO")

        checkpoints = data.get("measurement", {}).get("checkpoints", [])
        if not checkpoints:
            total = data.get("measurement", {}).get("total_joules")
            log_execution(script_name, f"No checkpoints found. Total Joules: {total}", "WARN")
            return total
        
        joules = [cp["joules"] for cp in checkpoints]
        if len(joules) >= 2:
            val = max(joules) - min(joules)
            log_execution(script_name, f"Calculated Energy (max-min): {val} J")
            return val
        
        total = data.get("measurement", {}).get("total_joules")
        return total
    except json.JSONDecodeError as je:
        log_execution(script_name, f"JSON Decode Error: {je}", "ERROR")
        return None

def run_perf(script_path):
    script_name = Path(script_path).name
    ext = Path(script_path).suffix
    bin_path = None
    class_file = None
    
    try:
        run_cmd = []
        if ext == ".py":
            run_cmd = ["python3", str(script_path)]
        elif ext == ".c":
            bin_path = f"{script_path}.bin"
            compile_cmd = ["gcc", str(script_path), "-o", bin_path, "-lm"]
            comp_res = run_command_with_logging(compile_cmd, script_name, "GCC Compilation")
            if not comp_res or comp_res.returncode != 0:
                return None
            run_cmd = [bin_path]
        elif ext == ".cpp":
            bin_path = f"{script_path}.bin"
            compile_cmd = ["g++", str(script_path), "-o", bin_path, "-lm"]
            comp_res = run_command_with_logging(compile_cmd, script_name, "G++ Compilation")
            if not comp_res or comp_res.returncode != 0:
                return None
            run_cmd = [bin_path]
        elif ext == ".java":
            compile_cmd = ["javac", str(script_path)]
            comp_res = run_command_with_logging(compile_cmd, script_name, "Javac Compilation")
            if not comp_res or comp_res.returncode != 0:
                return None
            class_name = Path(script_path).stem
            # Classpath must include current dir
            run_cmd = ["java", "-cp", str(Path(script_path).parent), class_name]
            class_file = Path(script_path).with_suffix(".class")
        else:
            return None

        perf_cmd = ["perf", "stat", "-e", "power/energy-pkg/"] + run_cmd
        result = run_command_with_logging(perf_cmd, script_name, "Perf Execution")
        
        if not result: 
            return None

        # Perf writes to stderr
        match = re.search(r"([\d,.]+)\s+Joules\s+power/energy-pkg/", result.stderr)
        if match:
            val = float(match.group(1).replace(",", ""))
            log_execution(script_name, f"Perf Measured: {val} J")
            return val
        else:
            log_execution(script_name, "Perf output did not contain Joules measurement", "ERROR")
            return None
            
    except Exception as e:
        log_execution(script_name, f"Perf Exception: {e}", "ERROR")
        return None
    finally:
        if bin_path and os.path.exists(bin_path):
            os.remove(bin_path)
        if class_file and os.path.exists(class_file):
            os.remove(class_file)

def validate():
    # Clear old logs
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir()

    test_dir = Path("tests/validation")
    # Match all relevant source files, excluding instrumented ones and logs
    scripts = sorted([
        s for s in test_dir.glob("*.*") 
        if "_instrumented" not in s.name 
        and s.name != "validate_accuracy.py"
        and s.suffix in [".py", ".c", ".cpp", ".java"]
        and not s.name.startswith("gen_")
        and not s.name.endswith(".log")
    ])
    
    print(f"Starting validation on {len(scripts)} scripts. Logs in {LOG_DIR}")
    print(f"{ 'Script':<25} | { 'CG Avg (J)':<12} | { 'Perf Avg (J)':<12} | { 'Delta (%)':<10}")
    print("-" * 70)
    
    for script in scripts:
        cg_runs = []
        perf_runs = []
        
        # Initialize log
        log_execution(script.name, f"Starting validation for {script.name}")
        
        print(f"Testing {script.name}...", end=" ", flush=True)
        # 3 runs each for speed
        for i in range(3):
            print(f"CG{i+1}", end="", flush=True)
            val = run_codegreen(script)
            if val is not None: cg_runs.append(val)
            
            print(f".P{i+1} ", end="", flush=True)
            val = run_perf(script)
            if val is not None: perf_runs.append(val)
            
        print("Done.")
        if not cg_runs or not perf_runs:
            print(f"{script.name:<25} | {'Error':<12} | {'Error':<12} | {'N/A'}")
            log_execution(script.name, f"Validation FAILED. CG runs: {len(cg_runs)}, Perf runs: {len(perf_runs)}", "ERROR")
            continue
            
        cg_avg = statistics.mean(cg_runs)
        perf_avg = statistics.mean(perf_runs)
        
        # Delta calculation
        delta = ((cg_avg - perf_avg) / perf_avg) * 100 if perf_avg > 0 else 0
        
        print(f"{script.name:<25} | {cg_avg:<12.4f} | {perf_avg:<12.4f} | {delta:<+10.2f}%")
        log_execution(script.name, f"Validation COMPLETE. Delta: {delta:.2f}%")

if __name__ == "__main__":
    validate()