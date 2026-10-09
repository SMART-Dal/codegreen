#!/usr/bin/env python3
"""
CodeGreen CLI - Command Line Interface

This module provides the main command-line interface for CodeGreen,
wrapping the C++ binary and providing a user-friendly Python interface.

Features:
- Type-safe command line arguments with automatic validation
- Rich-formatted help and error messages
- Automatic shell completion support
- Configuration management
- Sensor initialization and management
- Energy measurement and analysis
"""

import os
import sys
import subprocess
import platform
import time
import shutil
import itertools
import json
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Annotated, Union
from enum import Enum
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    psutil = None

import typer
from rich.console import Console
from rich.panel import Panel
from codegreen import __version__ as _VERSION
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

console = Console()

# Enhanced Typer app with advanced features
app = typer.Typer(
    name="codegreen",
    help="[bold green]CodeGreen[/bold green] - Know the true energy cost of your code",
    add_completion=True,  # Enable shell completion
    rich_markup_mode="rich",  # Enable Rich markup in help
    no_args_is_help=False,  # Allow version option without command
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="[dim]For more information, visit: https://github.com/SMART-Dal/codegreen[/dim]"
)

class Language(str, Enum):
    """Supported programming languages for energy measurement."""
    python = "python"
    cpp = "cpp"
    java = "java"
    c = "c"
    javascript = "javascript"  # analysis works; instrumented measurement needs JS runtime (WIP)

class SensorType(str, Enum):
    """Available NEMB sensor types."""
    rapl = "rapl"              # Intel RAPL (CPU package + cores)
    nvidia = "nvidia"          # NVIDIA GPU sensors
    amd_gpu = "amd_gpu"        # AMD GPU sensors
    amd_cpu = "amd_cpu"        # AMD CPU RAPL-like interface

class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Precision(str, Enum):
    """Measurement precision levels."""
    low = "low"
    medium = "medium"
    high = "high"

class Granularity(str, Enum):
    """Instrumentation granularity level."""
    coarse = "coarse"  # main entry/exit only (minimal overhead)
    fine = "fine"       # all points from language config (functions, methods, etc.)

def _is_root() -> bool:
    """Check for root/admin. Safe on all platforms (Windows lacks geteuid)."""
    return getattr(os, 'geteuid', lambda: 1)() == 0

def get_binary_path() -> Optional[Path]:
    """
    Get the path to the CodeGreen binary.
    
    Returns:
        Path to the binary if found, None otherwise
    """
    # Check multiple possible locations for the binary
    pkg_root = Path(__file__).resolve().parent.parent
    repo_root = pkg_root.parent
    possible_paths = [
        repo_root / "bin" / "codegreen",
        repo_root / "build" / "bin" / "codegreen",
        pkg_root / "bin" / "codegreen",
        shutil.which("codegreen"),
    ]
    
    for path in possible_paths:
        if path and Path(path).exists() and os.access(path, os.X_OK):
            return Path(path)
    
    return None

def get_config_path() -> Optional[Path]:
    """Get the path to the default configuration file."""
    pkg_root = Path(__file__).resolve().parent.parent
    possible_paths = [
        Path.home() / ".codegreen" / "config.json",            # user override (highest priority)
        pkg_root / "config.json",                              # pip install (inside codegreen/)
        pkg_root.parent / "config" / "codegreen.json",         # dev: repo_root/config/codegreen.json
    ]
    for path in possible_paths:
        if path.exists():
            return path
    return None

def _get_runtime_path() -> Optional[Path]:
    """Get path to runtime module directory"""
    pkg_root = Path(__file__).resolve().parent.parent
    runtime_paths = [
        pkg_root / "instrumentation" / "language_runtimes" / "python",
        pkg_root / "bin" / "runtime",
        pkg_root.parent / "bin" / "runtime",
    ]
    for path in runtime_paths:
        if path.exists() and (path / "codegreen_runtime.py").exists():
            return path
    return None

def ensure_runtime_available() -> bool:
    """Ensure the Python runtime module is available."""
    return _get_runtime_path() is not None

def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    if not config_path:
        config_path = get_config_path()
    
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            console.print(f"[yellow]Warning: Failed to load config: {e}[/yellow]")
    
    # Return default config
    return {
        "measurement": {
            "pmt": {
                "preferred_sensors": ["rapl", "nvidia", "amd_gpu"]
            }
        }
    }


# Hotspot taxonomy. OCP-compliant: each verdict is a *rule* declared as
# data, evaluated in priority order. Adding a new category is a single
# entry in HOTSPOT_RULES (and optionally a corresponding block in
# config.json) -- no change to the dispatch logic. The current rule set
# matches the historical thresholds at the original cli.py:3424-3435
# block prior to extraction.
#
# Each rule: (verdict, priority, predicate, default-thresholds).
# Predicate is a callable taking the metrics dict + the resolved
# threshold dict; lower priority wins when multiple rules match.
HotspotMetrics = Dict[str, float]
HotspotThresholds = Dict[str, float]
HotspotRule = Dict[str, Any]

_HOTSPOT_RULES: List[HotspotRule] = [
    {
        "verdict": "wrapper",
        "priority": 10,  # filter rule: fires before any actionable type
        "thresholds": {"self_ratio_max": 0.2, "inclusive_pct_min": 5.0},
        "predicate": lambda m, t: (m["self_ratio"] < t["self_ratio_max"]
                                   and m["inc_pct"] >= t["inclusive_pct_min"]),
        "doc": "Function attributes inclusive energy but body does little work.",
    },
    {
        "verdict": "TYPE_2_INEFFICIENT",
        "priority": 20,
        "thresholds": {"exclusive_pct_min": 5.0, "efficiency_ratio_min": 3.0},
        "predicate": lambda m, t: (m["exc_pct"] >= t["exclusive_pct_min"]
                                   and m["efficiency_ratio"] > t["efficiency_ratio_min"]),
        "doc": "Energy-per-call >> median: microarchitectural inefficiency.",
    },
    {
        "verdict": "TYPE_1_DIRECT",
        "priority": 30,
        "thresholds": {"exclusive_pct_min": 10.0},
        "predicate": lambda m, t: m["exc_pct"] >= t["exclusive_pct_min"],
        "doc": "High exclusive energy: optimise the function body itself.",
    },
    {
        "verdict": "TYPE_5_FREQUENCY",
        "priority": 40,
        "thresholds": {"calls_min": 100000, "exclusive_pct_min": 3.0,
                       "efficiency_ratio_max": 1.5},
        "predicate": lambda m, t: (m["calls"] > t["calls_min"]
                                   and m["exc_pct"] >= t["exclusive_pct_min"]
                                   and m["efficiency_ratio"] < t["efficiency_ratio_max"]),
        "doc": "High call count, low per-call cost: batch or cache.",
    },
    {
        "verdict": "TYPE_1_DIRECT",
        "priority": 50,  # relaxed fallback below the strict 10% bar
        "thresholds": {"exclusive_pct_min": 3.0},
        "predicate": lambda m, t: m["exc_pct"] >= t["exclusive_pct_min"],
        "doc": "Relaxed Type-1 fallback for moderate exclusive shares.",
    },
]


def _resolved_thresholds(rule: HotspotRule, config: Optional[Dict[str, Any]]) -> HotspotThresholds:
    """Merge rule's defaults with the user's overrides under
    ``config["hotspot_taxonomy"]["<verdict>"]``. Per-verdict block keeps
    name collisions safe across rule additions."""
    base = dict(rule["thresholds"])
    if config:
        tax = config.get("hotspot_taxonomy", {}) or {}
        # Per-verdict block (preferred, OCP-friendly): tax["<verdict>"]
        per_verdict = tax.get(rule["verdict"], {})
        if isinstance(per_verdict, dict):
            base.update({k: float(v) for k, v in per_verdict.items()
                         if k in rule["thresholds"]})
    return base


def _classify_hotspot_verdict(self_ratio: float, inc_pct: float, exc_pct: float,
                               calls: int, efficiency_ratio: float,
                               config: Optional[Dict[str, Any]] = None,
                               rules: Optional[List[HotspotRule]] = None) -> str:
    """Return the verdict for the given per-function metrics. Rules are
    evaluated in ascending priority order; first match wins. CodeGreen
    detects ``wrapper`` / ``TYPE_1_DIRECT`` / ``TYPE_2_INEFFICIENT`` /
    ``TYPE_5_FREQUENCY`` / ``minor``; ``TYPE_3_INDIRECT`` and
    ``TYPE_4_STRUCTURAL`` require callgraph analysis and are agent-side.

    OCP: pass a custom ``rules`` list to extend without modifying this
    function. config[hotspot_taxonomy][<verdict>] = {threshold: value}
    overrides per-verdict thresholds without code change."""
    metrics: HotspotMetrics = {
        "self_ratio": self_ratio, "inc_pct": inc_pct, "exc_pct": exc_pct,
        "calls": calls, "efficiency_ratio": efficiency_ratio,
    }
    active_rules = sorted(rules or _HOTSPOT_RULES, key=lambda r: r["priority"])
    for rule in active_rules:
        thresholds = _resolved_thresholds(rule, config)
        try:
            if rule["predicate"](metrics, thresholds):
                return rule["verdict"]
        except (KeyError, TypeError):
            continue
    return "minor"


# Backwards-compat: callers reading individual threshold values can still
# query a flat default map.
_DEFAULT_HOTSPOT_TAXONOMY = {
    f"{r['verdict'].lower()}_{k}": v
    for r in _HOTSPOT_RULES for k, v in r["thresholds"].items()
}


# ============================================================================
# Comprehensive Detection Functions for Init Command
# ============================================================================

def detect_environment() -> Dict[str, Any]:
    """Detect deployment environment type and characteristics."""
    if not psutil:
        console.print("[yellow]Warning: psutil not available - limited environment detection[/yellow]")
    
    env_info = {
        "type": "personal",  # Default
        "platform": platform.system().lower(),
        "platform_version": platform.release(),
        "deployment_mode": "development",
        "detected_features": []
    }
    
    # Check for containerized environment
    if (Path("/.dockerenv").exists() or 
        os.environ.get("CONTAINER") or 
        os.environ.get("CI")):
        env_info["type"] = "container"
        env_info["deployment_mode"] = "containerized"
        env_info["detected_features"].append("container_runtime")
    
    # Check for HPC environment
    elif (Path("/opt/slurm").exists() or 
          os.environ.get("SLURM_JOB_ID") or 
          Path("/usr/local/hpc").exists() or
          any(Path(f"/etc/modulefiles").exists() for _ in [1]) or
          Path("/usr/share/lmod").exists()):
        env_info["type"] = "hpc"
        env_info["deployment_mode"] = "cluster"
        env_info["detected_features"].extend(["job_scheduler", "module_system"])
    
    # Check for shared server environment
    elif len(list(Path("/home").iterdir())) > 10 if Path("/home").exists() else False:
        if psutil:
            try:
                # Check number of users and system load
                users = len(psutil.users())
                if users > 5:
                    env_info["type"] = "shared_server"
                    env_info["deployment_mode"] = "multi_user"
                    env_info["detected_features"].append("multi_user_system")
            except Exception:
                pass
        else:
            # Fallback detection without psutil
            env_info["type"] = "shared_server"
            env_info["deployment_mode"] = "multi_user"
    
    # Check for CI/CD environment
    ci_indicators = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TRAVIS"]
    if any(os.environ.get(indicator) for indicator in ci_indicators):
        env_info["type"] = "cicd"
        env_info["deployment_mode"] = "automation"
        env_info["detected_features"].append("ci_pipeline")
    
    # Detect additional system characteristics
    if psutil:
        try:
            # System resources
            memory_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            cpu_count = psutil.cpu_count()
            env_info["system_resources"] = {
                "memory_gb": memory_gb,
                "cpu_cores": cpu_count,
                "cpu_freq_mhz": int(psutil.cpu_freq().max) if psutil.cpu_freq() else None
            }
            
        except Exception:
            pass
    else:
        # Fallback system detection
        try:
            import multiprocessing
            env_info["system_resources"] = {
                "cpu_cores": multiprocessing.cpu_count(),
                "memory_gb": "unknown"
            }
        except Exception:
            pass

    # Power management capabilities
    if Path("/sys/class/power_supply").exists():
        env_info["detected_features"].append("power_management")
    
    # Virtualization detection
    if Path("/proc/vz").exists() or "hypervisor" in platform.processor().lower():
        env_info["detected_features"].append("virtualized")
    
    return env_info

def detect_hardware_sensors() -> Dict[str, Dict[str, Any]]:
    """Detect available hardware sensors and their capabilities."""
    sensors = {}
    
    # CPU Energy (RAPL) Detection
    rapl_info = {"available": False, "details": "Not detected"}
    rapl_paths = [
        "/sys/class/powercap/intel-rapl:0/energy_uj",
        "/sys/class/powercap/intel-rapl:0",
        "/sys/devices/virtual/powercap/intel-rapl"
    ]
    
    for path in rapl_paths:
        if Path(path).exists():
            try:
                # Try to read energy file to verify accessibility
                if str(path).endswith("energy_uj"):
                    with open(path, 'r') as f:
                        energy_val = f.read().strip()
                        if energy_val.isdigit():
                            rapl_info = {
                                "available": True,
                                "details": f"Intel RAPL accessible at {path}",
                                "domains": ["package", "pp0", "pp1", "dram"]
                            }
                            break
                else:
                    # Check for energy files in directory
                    energy_files = list(Path(path).rglob("energy_uj"))
                    if energy_files:
                        rapl_info = {
                            "available": True, 
                            "details": f"Intel RAPL domains found: {len(energy_files)}",
                            "domains": [f.parent.name for f in energy_files[:4]]
                        }
                        break
            except (PermissionError, FileNotFoundError):
                rapl_info["details"] = "Intel RAPL detected but permission denied"
                rapl_info["permission_issue"] = True
    
    sensors["intel_rapl"] = rapl_info
    
    # AMD CPU Energy Detection
    amd_rapl_info = {"available": False, "details": "Not detected"}
    amd_paths = ["/sys/class/powercap/amd-rapl:0", "/sys/class/hwmon"]
    
    for path in amd_paths:
        if Path(path).exists():
            amd_rapl_info = {"available": True, "details": f"AMD energy monitoring at {path}"}
            break
    
    sensors["amd_cpu"] = amd_rapl_info
    
    # NVIDIA GPU Detection
    nvidia_info = {"available": False, "details": "Not detected"}
    
    # Check for nvidia-smi tool
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_info = result.stdout.strip().split('\n')
                nvidia_info = {
                    "available": True,
                    "details": f"NVIDIA GPUs detected: {len(gpu_info)}",
                    "gpus": [line.split(',')[0].strip() for line in gpu_info if ',' in line]
                }
            else:
                nvidia_info["details"] = "NVIDIA driver installed but no GPUs detected"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            nvidia_info["details"] = "NVIDIA tools timeout/error"
    
    sensors["nvidia_gpu"] = nvidia_info
    
    # AMD GPU Detection
    amd_gpu_info = {"available": False, "details": "Not detected"}
    
    # Check for ROCm tools
    rocm_tools = ["rocm-smi", "rocminfo"]
    for tool in rocm_tools:
        if shutil.which(tool):
            try:
                result = subprocess.run([tool], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    amd_gpu_info = {
                        "available": True,
                        "details": f"AMD ROCm detected via {tool}",
                        "tool": tool
                    }
                    break
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
    
    sensors["amd_gpu"] = amd_gpu_info
    
    # External sensors (USB power meters, etc.)
    external_info = {"available": False, "details": "Not detected"}
    
    # Check for PowerSensor devices (if drivers available)
    usb_devices = Path("/dev").glob("ttyUSB*")
    if any(usb_devices):
        external_info = {
            "available": False,  # Requires specific driver detection
            "details": "USB devices present - may support external sensors",
            "requires_setup": True
        }
    
    sensors["external_sensors"] = external_info
    
    return sensors

def check_energy_permissions() -> Dict[str, Dict[str, Any]]:
    """Check permissions for energy monitoring resources."""
    permissions = {}
    
    # RAPL CPU energy files
    rapl_permission = {"accessible": False, "details": "Not checked"}
    
    rapl_files = [
        "/sys/class/powercap/intel-rapl:0/energy_uj",
        "/sys/class/powercap/intel-rapl:1/energy_uj"
    ]
    
    accessible_files = []
    denied_files = []
    
    for file_path in rapl_files:
        if Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    f.read(10)  # Try to read a small amount
                accessible_files.append(file_path)
            except PermissionError:
                denied_files.append(file_path)
    
    if accessible_files:
        rapl_permission = {
            "accessible": True,
            "details": f"Can access {len(accessible_files)} RAPL energy files",
            "accessible_files": accessible_files
        }
    elif denied_files:
        rapl_permission = {
            "accessible": False,
            "details": f"Permission denied for {len(denied_files)} RAPL files",
            "denied_files": denied_files,
            "fix_command": "sudo install/setup_permissions.sh",
            "fix_instructions": [
                "Run: sudo install/setup_permissions.sh",
                "Or: sudo codegreen init --setup-permissions",
                "Then logout and login again for group changes to take effect"
            ]
        }
    
    permissions["rapl_cpu"] = rapl_permission
    
    # GPU permissions (NVIDIA)
    gpu_permission = {"accessible": False, "details": "Not checked"}
    
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                gpu_permission = {
                    "accessible": True,
                    "details": "Can access NVIDIA GPU power data"
                }
            else:
                gpu_permission = {
                    "accessible": False,
                    "details": "NVIDIA tools present but power data inaccessible"
                }
        except Exception:
            gpu_permission["details"] = "NVIDIA permission check failed"
    
    permissions["nvidia_gpu"] = gpu_permission
    
    # System permissions (general)
    general_permission = {"accessible": True, "details": "Basic system access OK"}
    
    # Check if running as root (usually not recommended)
    if _is_root():
        general_permission = {
            "accessible": True,
            "details": "Running as root - all permissions available",
            "warning": "Running as root not recommended for regular use"
        }
    
    permissions["system"] = general_permission
    
    return permissions

def detect_performance_settings() -> Dict[str, Any]:
    """Detect optimal performance settings for the current system."""
    
    if psutil:
        settings = {
            "cpu_cores": psutil.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "recommended_settings": {}
        }
        
        # CPU scaling detection
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            settings["cpu_freq_mhz"] = {
                "current": cpu_freq.current,
                "min": cpu_freq.min,
                "max": cpu_freq.max
            }
            
            # Recommend frequency scaling settings
            if cpu_freq.current < cpu_freq.max * 0.9:
                settings["recommended_settings"]["cpu_scaling"] = "Consider disabling CPU frequency scaling for consistent measurements"
        
        # Memory optimization
        memory = psutil.virtual_memory()
        if memory.available < memory.total * 0.2:  # Less than 20% free
            settings["recommended_settings"]["memory"] = "Low memory - consider reducing measurement buffer sizes"
        
        # Thread count recommendations
        logical_cores = psutil.cpu_count()
        physical_cores = psutil.cpu_count(logical=False)
        
        settings["recommended_threads"] = min(physical_cores or logical_cores, 4)
        settings["recommended_settings"]["threading"] = f"Recommended worker threads: {settings['recommended_threads']}"
        
        # I/O and storage
        try:
            disk_usage = psutil.disk_usage('/')
            if disk_usage.free < disk_usage.total * 0.1:
                settings["recommended_settings"]["storage"] = "Low disk space - enable temp file cleanup"
        except Exception:
            pass

    else:
        # Fallback settings without psutil
        import multiprocessing
        cpu_cores = multiprocessing.cpu_count()
        settings = {
            "cpu_cores": cpu_cores,
            "memory_gb": "unknown",
            "recommended_settings": {},
            "recommended_threads": min(cpu_cores, 4)
        }
        settings["recommended_settings"]["threading"] = f"Recommended worker threads: {settings['recommended_threads']}"
    
    return settings

def generate_optimized_config(
    environment_info: Dict[str, Any], 
    sensor_info: Dict[str, Any], 
    permission_info: Dict[str, Any],
    performance_info: Dict[str, Any],
    custom_config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate an optimized configuration based on detected system capabilities."""
    
    # Start with base configuration from existing config file
    base_config_path = get_config_path()
    if base_config_path and base_config_path.exists():
        with open(base_config_path, 'r') as f:
            config = json.load(f)
    else:
        config = load_config()  # Default config
    
    # Add initialization metadata
    config["initialization"] = {
        "completed": True,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "environment_type": environment_info["type"],
        "detected_sensors": list(sensor_info.keys()),
        "version": _VERSION
    }
    
    # Environment-specific optimizations
    if environment_info["type"] == "container":
        # Container optimizations
        config["measurement"]["accuracy"]["minimize_system_noise"] = False
        config["performance"]["threading"]["max_worker_threads"] = 2
        config["measurement"]["nemb"]["coordinator"]["auto_restart_failed_providers"] = True
        
    elif environment_info["type"] == "hpc":
        # HPC optimizations
        config["measurement"]["nemb"]["accuracy_mode"] = "production"
        config["measurement"]["accuracy"]["priority"] = "maximum"
        config["performance"]["threading"]["max_worker_threads"] = performance_info.get("recommended_threads", 4)
        config["measurement"]["accuracy"]["disable_frequency_scaling"] = False  # HPC manages this
        
    elif environment_info["type"] == "shared_server":
        # Shared server optimizations
        config["measurement"]["accuracy"]["minimize_system_noise"] = True
        config["performance"]["threading"]["max_worker_threads"] = min(2, performance_info.get("recommended_threads", 2))
        config["measurement"]["nemb"]["coordinator"]["measurement_buffer_size"] = 500  # Reduced for shared systems
        
    elif environment_info["type"] == "cicd":
        # CI/CD optimizations
        config["measurement"]["accuracy"]["priority"] = "balanced"
        config["measurement"]["nemb"]["accuracy_mode"] = "testing"
        config["developer"]["debug_mode"] = True
        config["performance"]["threading"]["max_worker_threads"] = 1
    
    # Sensor-specific optimizations
    nemb_providers = config["measurement"]["nemb"]["providers"]
    
    # Configure Intel RAPL
    if sensor_info.get("intel_rapl", {}).get("available", False):
        nemb_providers["intel_rapl"]["enabled"] = True
        nemb_providers["intel_rapl"]["validation_enabled"] = True
    else:
        nemb_providers["intel_rapl"]["enabled"] = False
    
    # Configure NVIDIA GPU
    if sensor_info.get("nvidia_gpu", {}).get("available", False):
        nemb_providers["nvidia_gpu"]["enabled"] = True
        nemb_providers["nvidia_gpu"]["validation_enabled"] = True
    else:
        nemb_providers["nvidia_gpu"]["enabled"] = False
    
    # Configure AMD CPU
    if sensor_info.get("amd_cpu", {}).get("available", False):
        nemb_providers["amd_cpu"]["enabled"] = True
    else:
        nemb_providers["amd_cpu"]["enabled"] = False
    
    # Performance optimizations based on system capabilities
    if performance_info["memory_gb"] < 4:
        config["performance"]["database"]["batch_operations"] = True
        config["performance"]["database"]["transaction_size"] = 500
        config["measurement"]["nemb"]["coordinator"]["measurement_buffer_size"] = 500
    
    # Apply custom configuration overrides
    if custom_config:
        def deep_merge(base_dict, override_dict):
            for key, value in override_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    deep_merge(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_merge(config, custom_config)
    
    return config

def test_configuration(config: Dict[str, Any]) -> Dict[str, Any]:
    """Test the generated configuration for basic functionality."""
    
    test_results = {"success": True, "errors": [], "warnings": []}
    
    try:
        # Test 1: Verify binary exists and can initialize
        binary_path = get_binary_path()
        if not binary_path:
            test_results["errors"].append("CodeGreen binary not found")
            test_results["success"] = False
            return test_results
        
        # Test 2: Quick sensor initialization test
        try:
            result = subprocess.run(
                [str(binary_path), "--init-sensors"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                test_results["warnings"].append("Sensor initialization returned non-zero exit code")
        except subprocess.TimeoutExpired:
            test_results["warnings"].append("Sensor initialization timeout")
        except Exception as e:
            test_results["warnings"].append(f"Sensor initialization error: {e}")
        
        # Test 3: Validate configuration structure
        required_sections = ["measurement", "performance", "security", "languages"]
        for section in required_sections:
            if section not in config:
                test_results["errors"].append(f"Missing required configuration section: {section}")
                test_results["success"] = False
        
        # Test 4: Check for enabled providers
        nemb_providers = config.get("measurement", {}).get("nemb", {}).get("providers", {})
        enabled_providers = [name for name, provider in nemb_providers.items() 
                           if provider.get("enabled", False) == True]
        
        if not enabled_providers:
            test_results["warnings"].append("No energy providers enabled - measurements may not work")
        
        # Test 5: Quick measurement test (if possible)
        if enabled_providers and test_results["success"]:
            try:
                # Run a very quick workload test
                result = subprocess.run(
                    [str(binary_path), "measure-workload", "--workload=cpu_stress", "--duration=1"],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    test_results["measurement_test"] = "passed"
                else:
                    test_results["warnings"].append("Quick measurement test failed")
            except Exception:
                test_results["warnings"].append("Could not run measurement test")
    
    except Exception as e:
        test_results["errors"].append(f"Configuration test failed: {e}")
        test_results["success"] = False
    
    return test_results

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    debug: Annotated[bool, typer.Option("--debug", "--verbose", help="Enable verbose diagnostic output")] = False,
    config: Annotated[Optional[Path], typer.Option("--config", help="Path to configuration file")] = None,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version and exit")] = False,
    log_level: Annotated[LogLevel, typer.Option("--log-level", help="Set logging level")] = LogLevel.INFO,
):
    """
    [bold green]CodeGreen[/bold green] - Know the true energy cost of your code

    Precise, hardware-level energy measurement for any program. Reads directly
    from CPU and GPU energy counters (Intel/AMD RAPL, NVIDIA NVML, Apple
    IOReport, Windows EMI) -- no estimation, no modeling, just what the
    hardware reports.

    [bold]Quick Start:[/bold]
    - [dim]codegreen doctor[/dim]                              - Check system readiness
    - [dim]codegreen run -- python3 script.py[/dim]            - Measure energy of a command
    - [dim]codegreen measure python script.py[/dim]            - Per-function energy breakdown
    - [dim]codegreen run --json --budget 10 -- ./binary[/dim]  - CI/CD energy gate
    """
    if version:
        console.print(f"[bold green]CodeGreen version {_VERSION}[/bold green]")
        raise typer.Exit()

    # If no command is provided and version is not requested, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        # Quick setup check for new users
        backend = _get_energy_backend()
        if isinstance(backend, _TimeOnlyBackend):
            console.print("\n[yellow]Energy measurement not available.[/yellow]")
            if sys.platform == "linux":
                console.print("  Run: [cyan]sudo codegreen init-sensors[/cyan]  (one-time setup)")
            elif sys.platform == "darwin":
                console.print("  NEMB library required. Reinstall: [cyan]pip install --force-reinstall codegreen[/cyan]")
            console.print("  Then: [cyan]codegreen doctor[/cyan]  (verify setup)")
        raise typer.Exit()
    
    if debug:
        os.environ['CODEGREEN_DEBUG'] = '1'
    if config:
        os.environ['CODEGREEN_CONFIG'] = str(config)
    os.environ['CODEGREEN_LOG_LEVEL'] = log_level.value

    if debug:
        import platform as _pf
        pkg_root = Path(__file__).resolve().parent.parent
        import psutil
        console.print(f"\n[bold]CodeGreen Diagnostics:[/bold]")
        console.print(f"  Version:    {_VERSION}")
        console.print(f"  Platform:   {_pf.system()} {_pf.machine()}")
        console.print(f"  OS:         {_pf.platform()}")
        console.print(f"  Python:     {sys.version.split()[0]} ({sys.executable})")
        console.print(f"  Package:    {pkg_root}")
        # Hardware
        try:
            cpu_name = _pf.processor() or "unknown"
            try:
                if sys.platform == "linux":
                    for line in open("/proc/cpuinfo"):
                        if line.startswith("model name"):
                            cpu_name = line.split(":")[1].strip(); break
                elif sys.platform == "darwin":
                    import subprocess as _sp
                    cpu_name = _sp.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
            except Exception:
                pass
            console.print(f"  CPU:        {cpu_name}")
            console.print(f"  Cores:      {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
            mem = psutil.virtual_memory()
            console.print(f"  RAM:        {mem.total / (1024**3):.1f} GB ({mem.percent}% used)")
        except Exception:
            pass
        # Dependencies
        try:
            import tree_sitter
            console.print(f"  tree-sitter: {tree_sitter.__version__}")
        except Exception:
            console.print(f"  tree-sitter: not found")
        try:
            import typer as _ty
            console.print(f"  typer:      {_ty.__version__}")
        except Exception:
            pass
        # NEMB library check
        nemb_files = list((pkg_root / "lib").glob("*codegreen-nemb*")) if (pkg_root / "lib").is_dir() else []
        if nemb_files:
            for f in nemb_files:
                console.print(f"  NEMB lib:   {f.name} ({f.stat().st_size} bytes)")
        else:
            console.print(f"  NEMB lib:   [red]NOT FOUND[/red] in {pkg_root / 'lib'}")
            # Search other common locations
            for alt in [pkg_root.parent / "lib", pkg_root.parent / "build" / "lib"]:
                alt_files = list(alt.glob("*codegreen-nemb*")) if alt.is_dir() else []
                if alt_files:
                    console.print(f"  NEMB alt:   found at {alt_files[0]} (not in expected location)")
        # Try loading NEMB and capture exact error
        import ctypes as _ct
        nemb_load_error = None
        nemb_init_result = None
        try:
            test_be = _NEMBBackend()
            lib = test_be._load()
            if not lib or lib is False:
                nemb_load_error = "library not found in search paths"
            else:
                lib.nemb_initialize.restype = _ct.c_int
                nemb_init_result = lib.nemb_initialize()
        except OSError as e:
            nemb_load_error = f"OS load error: {e}"
        except Exception as e:
            nemb_load_error = f"error: {e}"
        if nemb_load_error:
            console.print(f"  NEMB load:  [red]{nemb_load_error}[/red]")
        elif nemb_init_result is not None:
            if nemb_init_result == 1:
                console.print(f"  NEMB load:  [green]OK (providers detected)[/green]")
            else:
                console.print(f"  NEMB load:  loaded but no energy providers found (init={nemb_init_result})")
        # Energy backend detection
        try:
            backend = _get_energy_backend()
            console.print(f"  Backend:    {backend.name}")
            console.print(f"  All backends: {', '.join(f'{b.name}(avail={b.is_available()})' for b in sorted(_ENERGY_BACKENDS, key=lambda x: -x.priority))}")
        except Exception as e:
            console.print(f"  Backend error: {e}")
        # Config
        cfg_path = get_config_path()
        console.print(f"  Config:     {cfg_path or 'not found'}")
        console.print()

@app.command("measure", rich_help_panel="Measurement")
def measure_energy(
    language: Annotated[Language, typer.Argument(help="Programming language to analyze")],
    script: Annotated[Path, typer.Argument(help="Path to the script file to measure")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file for results")] = None,
    sensors: Annotated[Optional[List[SensorType]], typer.Option("--sensors", "-s", help="Sensors to use for measurement")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="Verbose output")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output results in JSON format")] = False,
    precision: Annotated[Precision, typer.Option("--precision", "-p", help="Measurement precision")] = Precision.high,
    timeout: Annotated[Optional[int], typer.Option("--timeout", "-t", help="Timeout in seconds")] = None,
    no_cleanup: Annotated[bool, typer.Option("--no-cleanup", help="Keep temporary files")] = False,
    is_instrumented: Annotated[bool, typer.Option("--instrumented", help="Script is already instrumented")] = False,
    granularity: Annotated[Granularity, typer.Option("--granularity", "-g", help="Instrumentation level: coarse (main only) or fine (all functions)")] = Granularity.coarse,
    export_plot: Annotated[Optional[Path], typer.Option("--export-plot", help="Export energy timeline (HTML default, or PNG/PDF)")] = None,
    args: Annotated[Optional[List[str]], typer.Argument(help="Arguments to pass to the script")] = None,
):
    """
    [bold]Measure energy consumption[/bold] of a script with detailed analysis.

    This command analyzes your code structure, instruments it with measurement
    points, and measures energy consumption using available hardware sensors
    (Intel RAPL, NVIDIA NVML, AMD ROCm).

    [bold]Granularity:[/bold]
    - [cyan]coarse[/cyan] (default): Instruments only main entry/exit - minimal overhead, total program energy
    - [cyan]fine[/cyan]: Instruments all functions/methods per language config - per-function energy breakdown

    [bold]Examples:[/bold]
    - [cyan]codegreen measure python fibonacci.py[/cyan]
    - [cyan]codegreen measure python script.py --granularity fine[/cyan]
    - [cyan]codegreen measure python script.py --sensors rapl nvidia[/cyan]
    - [cyan]codegreen measure python main.py --timeout 60 --output results.json[/cyan]
    - [cyan]codegreen measure python main.py --json[/cyan]

    [bold]Sensor Types:[/bold] rapl, nvidia, amd_gpu, amd_cpu
    [bold]Precision Levels:[/bold] low, medium, high
    """
    
    if not script.exists():
        if not json_output:
            console.print(f"[red]Error: Script file not found: {script}[/red]")
        else:
            print(json.dumps({"success": False, "error": f"Script file not found: {script}"}))
        raise typer.Exit(1)
    
    try:
        # Step 1: Analyze code (always do this for suggestions and metadata)
        with open(script, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if not json_output:
            console.print(f"[green]Analyzing code structure...[/green]")
            console.print(f"Language: [cyan]{language.value}[/cyan]")
            console.print(f"Script: [cyan]{script}[/cyan]")
            
        from ..instrumentation.language_engine import LanguageEngine
        engine = LanguageEngine()
        result = engine.analyze_code(source_code, language.value)

        if not result.success:
            if not json_output:
                console.print(f"[red]Analysis failed: {result.error}[/red]")
            else:
                print(json.dumps({"success": False, "error": result.error}))
            raise typer.Exit(1)
        
        if not json_output:
            console.print(f"[green][ok] Analysis completed![/green]")
            console.print(f"Instrumentation points found: [cyan]{result.checkpoint_count}[/cyan]")

        # Apply granularity filter
        points = result.instrumentation_points
        if granularity == Granularity.coarse:
            points = _filter_main_entry_points(points, language.value)
            if not json_output:
                console.print(f"Granularity: coarse (main entry/exit) -> [cyan]{len(points)}[/cyan] points")
        else:
            if not json_output:
                console.print(f"Granularity: fine (config-driven) -> [cyan]{len(points)}[/cyan] points")

        # Step 2: Handle Instrumentation
        run_path = script
        temp_dir = None

        if not is_instrumented:
            if not json_output:
                console.print(f"\n[green]Instrumenting {language.value} code...[/green]")
            _ns = result.metadata.get('normalised_source', source_code)
            instrumented_code = engine.instrument_code(_ns, points, language.value, pre_normalised_source=_ns)

            # Determine correct output extension
            ext_map = {'python': '.py', 'c': '.c', 'cpp': '.cpp', 'java': '.java', 'javascript': '.js'}
            ext = ext_map.get(language.value, script.suffix)
            if language == Language.java:
                # Java requires filename to match public class name
                import tempfile
                temp_dir = Path(tempfile.mkdtemp(prefix="codegreen_java_"))
                run_path = temp_dir / f'{script.stem}{ext}'
            else:
                run_path = script.with_name(f'{script.stem}_instrumented{ext}')
            with open(run_path, 'w', encoding='utf-8') as f:
                f.write(instrumented_code)
            
        # Step 3: Run the measurement
        try:
            measurement_result = None
            if _should_run_actual_measurement(sensors):
                if not json_output:
                    console.print(f"\n[green]Running energy measurement...[/green]")
                measurement_result = _run_energy_measurement(
                    run_path, language, sensors, verbose and not json_output, timeout, args, json_output
                )

                # Graceful degradation: fine granularity produced a clean run but
                # no usable per-function checkpoints (work ran at module level or in
                # child processes we cannot attribute). Re-measure at coarse
                # (main/module enter-exit) so we still report whole-program total
                # energy instead of a silent 0 J. A crashed run (no 'success') is
                # left alone so its real error is surfaced. Best-effort: any failure
                # here keeps the original fine result.
                fine_checkpoint_count = len((measurement_result or {}).get('checkpoints') or [])
                n_prospects = len(result.instrumentation_points)
                run_crashed = _output_has_error((measurement_result or {}).get('output', '') or '')
                # Flag (never silence): prospects were detected but runtime capture
                # fell short. Either legitimate (module-level/child-process work) or
                # an instrumentation bug -- surface it so bugs are caught even when
                # the coarse fallback below provides a usable total.
                instrumentation_warning = None
                if (measurement_result and not is_instrumented
                        and n_prospects >= 2 and fine_checkpoint_count < 2):
                    cause = ("the instrumented program crashed (see error)" if run_crashed
                             else "work runs at module level or in child processes; "
                                  "reporting whole-program energy via coarse fallback")
                    instrumentation_warning = (
                        f"{n_prospects} instrumentation prospects detected but only "
                        f"{fine_checkpoint_count} runtime checkpoint(s) captured; per-function "
                        f"attribution unavailable -- {cause}. If functions were expected to run, "
                        f"treat as a possible instrumentation bug.")
                    # JSON consumers get this in instrumentation_audit.warning; only
                    # humans get the console line (never pollute stdout in JSON mode).
                    if not json_output:
                        console.print(f"[yellow]INSTRUMENTATION WARNING: {instrumentation_warning}[/yellow]")

                # Fall back to coarse only for a CLEAN run (a crash keeps its error).
                fallback_used = False
                if (granularity != Granularity.coarse and not is_instrumented
                        and measurement_result and not run_crashed
                        and fine_checkpoint_count < 2):
                    coarse_points = _filter_main_entry_points(
                        result.instrumentation_points, language.value)
                    if coarse_points:
                        _ns = result.metadata.get('normalised_source', source_code)
                        c_ext = {'python': '.py', 'c': '.c', 'cpp': '.cpp',
                                 'java': '.java', 'javascript': '.js'}.get(
                                     language.value, script.suffix)
                        c_path = script.with_name(f'{script.stem}_coarse{c_ext}')
                        c_path.write_text(
                            engine.instrument_code(_ns, coarse_points, language.value,
                                                   pre_normalised_source=_ns),
                            encoding='utf-8')
                        try:
                            c_res = _run_energy_measurement(
                                c_path, language, sensors, False, timeout, args, json_output)
                            if c_res and len(c_res.get('checkpoints') or []) >= 2:
                                measurement_result = c_res
                                granularity = Granularity.coarse
                                fallback_used = True
                        finally:
                            if not no_cleanup and c_path.exists() and c_path != script:
                                os.remove(c_path)

                if output:
                    _save_measurement_results(output, result, measurement_result)
                    if not json_output:
                        console.print(f"[green][ok] Results saved to: {output}[/green]")
            else:
                if not json_output:
                    console.print(f"\n[yellow]Note: No energy sensors available. Code analysis completed.[/yellow]")
            
            if json_output:
                combined_results = _build_comprehensive_json(
                    result, measurement_result, source_code, script, language.value, granularity.value
                )
                combined_results["instrumentation_audit"] = {
                    "prospects_detected": n_prospects,
                    "fine_runtime_checkpoints": fine_checkpoint_count,
                    "fallback_to_coarse": fallback_used,
                    **({"warning": instrumentation_warning} if instrumentation_warning else {}),
                }
                print(json.dumps(combined_results, indent=2))
            else:
                if measurement_result and measurement_result.get('success'):
                    console.print(f"\n[green][ok] CodeGreen measurement completed successfully![/green]")
            if export_plot and measurement_result and measurement_result.get('checkpoints'):
                from ..analyzer.plot import export_plot as do_export
                do_export(measurement_result['checkpoints'], export_plot)
                if not json_output:
                    console.print(f"[green]Energy plot: {export_plot}[/green]")
        finally:
            # Cleanup
            if not no_cleanup and run_path != script:
                if temp_dir and temp_dir.exists():
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                elif run_path.exists():
                    os.remove(run_path)
        
    except FileNotFoundError as e:
        if not json_output:
            console.print(f"[red]Error: File not found: {e}[/red]")
        else:
            print(json.dumps({"success": False, "error": str(e)}))
        raise typer.Exit(1)
    except Exception as e:
        if not json_output:
            console.print(f"[red]Unexpected error: {e}[/red]")
            if verbose:
                import traceback
                console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
        else:
            print(json.dumps({"success": False, "error": str(e)}))
        raise typer.Exit(1)


def _filter_main_entry_points(points: List, language: str) -> List:
    """Filter instrumentation points to keep only main entry/exit (coarse-grained).

    Main detection per language:
    - Python: function named 'main', or top-level module enter/exit
    - C/C++: function named 'main'
    - Java: method named 'main'
    Falls back to first+last function enter/exit if no 'main' found.
    """
    main_names = {"main", "__main__"}
    main_points = [p for p in points if p.name in main_names
                   and p.type in ("function_enter", "function_exit")]
    if main_points:
        return main_points
    # Fallback: keep only the first function_enter and last function_exit
    enters = [p for p in points if p.type == "function_enter"]
    exits = [p for p in points if p.type == "function_exit"]
    fallback = []
    if enters:
        fallback.append(enters[0])
    if exits:
        fallback.append(exits[-1])
    return fallback


def _output_has_error(output: str) -> bool:
    """True if captured output shows a crash/error (traceback or error marker),
    ignoring CodeGreen's own report lines. Distinguishes a crashed run (surface the
    error) from a clean run that simply produced no checkpoints (fall back to coarse)."""
    if not output:
        return False
    for ln in output.splitlines():
        if ln.startswith("Traceback (most recent call last)"):
            return True
        if "CODEGREEN" in ln.upper():
            continue
        low = ln.lower()
        if "error:" in low or ln.strip().endswith("Error") or "exception" in low:
            return True
    return False


def _extract_failure_reason(output: str) -> str:
    """Salient failure line from a failed run's captured output, so a zero-checkpoint
    measurement reports WHY it failed instead of a silent 0 J. Language-agnostic:
    Python tracebacks, then compiler/runtime error markers, else the last output line."""
    if not output or not output.strip():
        return "program produced no checkpoints and no output"
    # Drop CodeGreen's own report/sentinel lines (an atexit handler prints them
    # even after the program crashes), so they don't mask the real error.
    lines = [ln for ln in output.splitlines()
             if ln.strip() and "CODEGREEN" not in ln.upper()]
    if not lines:
        return "program produced no diagnostic output"
    # Python traceback: the exception summary is the first non-indented line after
    # the last 'Traceback' header (call frames are indented).
    tb = max((i for i, ln in enumerate(lines)
              if ln.startswith("Traceback (most recent call last)")), default=None)
    if tb is not None:
        for ln in lines[tb + 1:]:
            if ln and not ln[0].isspace():
                return ln.strip()
    for ln in reversed(lines):
        low = ln.lower()
        if "error:" in low or ln.strip().endswith("Error") or "exception" in low:
            return ln.strip()
    return lines[-1].strip()


def _build_comprehensive_json(
    analysis_result, measurement_result, source_code: str,
    script: Path, language: str, granularity: str
) -> Dict[str, Any]:
    """Build comprehensive JSON output as single source of truth."""
    import hashlib, platform
    source_hash = hashlib.sha256(source_code.encode('utf-8')).hexdigest()
    points_map = {}
    for pt in analysis_result.instrumentation_points:
        content_around = source_code.splitlines()[pt.line - 1].strip() if 0 < pt.line <= len(source_code.splitlines()) else ""
        content_hash = hashlib.md5(f"{pt.name}:{content_around}".encode()).hexdigest()[:12]
        points_map[pt.id] = {
            "type": pt.type, "name": pt.name, "line": pt.line,
            "column": pt.column, "context": pt.context,
            "stable_id": f"{pt.name}@{content_hash}",
            "insertion_mode": pt.insertion_mode,
        }
    checkpoints = []
    per_func = {}
    if measurement_result and measurement_result.get('checkpoints'):
        checkpoints = measurement_result['checkpoints']
        for cp in checkpoints:
            # Parse type and name from checkpoint_id: "type:name:point_id#inv_N_tXXX"
            cp_id = cp.get('checkpoint_id', '')
            parts = cp_id.split(':')
            ctype = parts[0] if len(parts) >= 1 else cp.get('type', '')
            fname = parts[1] if len(parts) >= 2 else cp.get('name', 'unknown')
            joules = cp.get('joules', 0.0)
            ts = cp.get('timestamp', 0)
            if fname not in per_func:
                per_func[fname] = {"enter_j": None, "exit_j": None, "enter_ts": 0, "exit_ts": 0, "calls": 0}
            if ctype == 'enter':
                per_func[fname]['enter_j'] = joules
                per_func[fname]['enter_ts'] = ts
                per_func[fname]['calls'] += 1
            elif ctype == 'exit':
                per_func[fname]['exit_j'] = joules
                per_func[fname]['exit_ts'] = ts
    func_energy = {}
    for fname, data in per_func.items():
        if data['enter_j'] is not None and data['exit_j'] is not None:
            delta = data['exit_j'] - data['enter_j']
            wall_ns = data['exit_ts'] - data['enter_ts']
            wall_s = wall_ns / 1e9 if wall_ns > 1e6 else wall_ns / 1e3
            energy = max(delta, 0.0)
            func_energy[fname] = {
                "energy_j": round(energy, 6),
                "wall_time_s": round(wall_s, 6),
                "avg_power_w": round(energy / wall_s, 2) if wall_s > 0 else 0.0,
                "calls": data['calls'],
            }
    system = {"kernel": platform.release(), "cpu_model": "", "governor": ""}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    system["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
            system["governor"] = f.read().strip()
    except OSError:
        pass
    total_energy = 0.0
    wall_time = 0.0
    if checkpoints and len(checkpoints) >= 2:
        total_energy = max(checkpoints[-1].get('joules', 0) - checkpoints[0].get('joules', 0), 0.0)
        ts_delta = checkpoints[-1].get('timestamp', 0) - checkpoints[0].get('timestamp', 0)
        wall_time = ts_delta / 1e6 if ts_delta > 1e6 else ts_delta
    success = bool(measurement_result and measurement_result.get('success'))
    result = {
        "success": success,
        "file": str(script), "language": language, "granularity": granularity,
        "source_fingerprint": source_hash,
        "system": system,
        "summary": {"total_energy_j": total_energy, "wall_time_s": wall_time,
                     "avg_power_w": total_energy / wall_time if wall_time > 0 else 0.0,
                     "checkpoint_count": len(checkpoints)},
        "instrumentation_points": points_map,
        "per_function_energy": func_energy,
        "checkpoints": checkpoints,
        "optimization_suggestions": analysis_result.optimization_suggestions,
    }
    # Never report a silent 0 J: when the run recorded no usable checkpoints,
    # surface WHY -- a real crash (traceback) vs a clean run that produced no
    # measurement markers -- so callers can distinguish "measured 0" from "failed".
    if not success or len(checkpoints) < 2:
        out = (measurement_result or {}).get('output', '') or ''
        result["error"] = (_extract_failure_reason(out) if _output_has_error(out)
                            else "no runtime checkpoints captured (per-function "
                                 "attribution unavailable; see instrumentation_audit)")
    return result


def _should_run_actual_measurement(sensors: Optional[List[SensorType]]) -> bool:
    """Check if actual energy measurement should be performed"""
    # For now, check if binary exists for actual measurement
    backend = _get_energy_backend()
    return not isinstance(backend, _TimeOnlyBackend)


def _parse_runtime_measurements(output: str) -> List[Dict[str, Any]]:
    """Extract structured energy measurements from process output"""
    measurements = []
    
    # Look for the JSON blob between markers
    start_marker = "--- CODEGREEN_RESULT_START ---"
    end_marker = "--- CODEGREEN_RESULT_END ---"
    
    if start_marker in output and end_marker in output:
        try:
            start_idx = output.find(start_marker) + len(start_marker)
            end_idx = output.find(end_marker)
            json_str = output[start_idx:end_idx].strip()
            
            data = json.loads(json_str)
            measurements = data.get("measurements", [])
        except Exception:
            # Silently fail if parsing fails
            pass
            
    return measurements


def _get_c_runtime_paths(language: str = "c") -> tuple:
    """Get include path and lib path for C/C++ runtime."""
    pkg_root = Path(__file__).resolve().parent.parent
    repo_root = pkg_root.parent
    include_path = _get_runtime_source_dir() / language
    for candidate in [repo_root / "lib", repo_root / "build" / "lib", pkg_root / "lib"]:
        if candidate.exists() and any(candidate.glob("libcodegreen-nemb*")):
            pkg_rt = candidate / "runtime" / language
            if pkg_rt.exists():
                include_path = pkg_rt
            return include_path, candidate
    return include_path, repo_root / "lib"


def _compile_instrumented(instrumented_path: Path, language: Language, verbose: bool) -> Optional[Path]:
    """Compile instrumented C/C++/Java code. Returns binary path or None on failure."""
    build_dir = instrumented_path.parent
    stem = instrumented_path.stem
    if language == Language.c:
        include_path, lib_path = _get_c_runtime_paths("c")
        binary = build_dir / f"{stem}.out"
        cmd = ["gcc", "-O2", f"-I{include_path}", str(instrumented_path),
               f"-L{lib_path}", "-lcodegreen-nemb", "-lm", "-lpthread", "-o", str(binary)]
    elif language == Language.cpp:
        include_path, lib_path = _get_c_runtime_paths("cpp")
        binary = build_dir / f"{stem}.out"
        cmd = ["g++", "-O2", f"-I{include_path}", str(instrumented_path),
               f"-L{lib_path}", "-lcodegreen-nemb", "-lpthread", "-o", str(binary)]
    elif language == Language.java:
        java_runtime = _get_runtime_source_dir() / "java"
        cmd = ["javac", "-cp", str(java_runtime), "-d", str(build_dir), str(instrumented_path)]
        binary = build_dir / f"{stem}.class"
    else:
        return None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            if verbose:
                console.print(f"[red]Compilation failed: {result.stderr}[/red]")
            return None
        return binary
    except Exception as e:
        if verbose:
            console.print(f"[red]Compilation error: {e}[/red]")
        return None


def _run_energy_measurement(
    instrumented_path: Path,
    language: Language,
    sensors: Optional[List[SensorType]],
    verbose: bool,
    timeout: Optional[int],
    args: Optional[List[str]],
    json_output: bool = False,
    no_cleanup: bool = False
) -> Dict[str, Any]:
    """Run actual energy measurement on instrumented code.

    Unified approach for all languages:
    - Python: run directly with runtime module
    - C/C++: compile instrumented code, run binary
    - Java: compile with javac, run with java
    """
    env = os.environ.copy()
    runtime_path = _get_runtime_path()
    binary_to_cleanup = None

    if runtime_path:
        pythonpath = str(runtime_path)
        if 'PYTHONPATH' in env:
            pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
        env['PYTHONPATH'] = pythonpath

    if language == Language.python:
        cmd = ['python3', str(instrumented_path)]
        if args:
            cmd.extend(args)
    elif language in (Language.c, Language.cpp):
        binary = _compile_instrumented(instrumented_path, language, verbose)
        if not binary or not binary.exists():
            return {'success': False, 'error': 'Compilation failed'}
        binary_to_cleanup = binary
        # Set LD_LIBRARY_PATH for NEMB library
        _, lib_path = _get_c_runtime_paths(language.value)
        ld_path = str(lib_path)
        if 'LD_LIBRARY_PATH' in env:
            ld_path = f"{ld_path}:{env['LD_LIBRARY_PATH']}"
        env['LD_LIBRARY_PATH'] = ld_path
        cmd = [str(binary)]
        if args:
            cmd.extend(args)
    elif language == Language.java:
        binary = _compile_instrumented(instrumented_path, language, verbose)
        if not binary:
            return {'success': False, 'error': 'Java compilation failed'}
        class_name = instrumented_path.stem
        build_dir = instrumented_path.parent
        java_runtime = _get_runtime_source_dir() / "java"
        _, lib_path = _get_c_runtime_paths("java")
        cp = f"{build_dir}:{java_runtime}"
        cmd = ['java', '-cp', cp,
               f'-Djava.library.path={lib_path}',
               f'-Dcodegreen.lib.path={lib_path / "libcodegreen-nemb.so"}',
               class_name]
        if args:
            cmd.extend(args)
    else:
        return {'success': False, 'error': f'Unsupported language: {language}'}
    
    def _run_with_output_capture(cmd, timeout, env):
        """Run subprocess and capture ALL output including atexit handlers."""
        env = env.copy()
        env['PYTHONUNBUFFERED'] = '1'
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        try:
            stdout, _ = proc.communicate(timeout=timeout or 300)
            return stdout
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, _ = proc.communicate(timeout=5)
                return stdout
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return ""

    try:
        if verbose and not json_output:
            console.print(f"Command: [dim]{' '.join(cmd)}[/dim]")
        # No spinner/progress bar during measurement - avoid CPU noise
        output = _run_with_output_capture(cmd, timeout, env)
        measurements = _parse_runtime_measurements(output)
        success = "--- CODEGREEN_RESULT_END ---" in output
        if json_output:
            return {
                'success': success,
                'output': output,
                'error': None if success else 'incomplete',
                'checkpoints': measurements
            }
        if success:
            return {'success': True, 'output': output, 'checkpoints': measurements}
        else:
            console.print("[yellow]Warning: Measurement may be incomplete[/yellow]")
            return {'success': False, 'error': 'incomplete', 'output': output}
    except Exception as e:
        if not json_output:
            console.print(f"[red]Energy measurement failed: {e}[/red]")
        return {'success': False, 'error': str(e)}
    finally:
        if not no_cleanup and binary_to_cleanup and binary_to_cleanup.exists():
            try:
                binary_to_cleanup.unlink()
            except OSError:
                pass


def _save_measurement_results(
    output_path: Path,
    analysis_result: Any,
    measurement_result: Dict[str, Any]
) -> None:
    """Save combined analysis and measurement results"""
    
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        'analysis': {
            'language': analysis_result.language,
            'success': analysis_result.success,
            'instrumentation_points': analysis_result.checkpoint_count,
            'optimization_suggestions': analysis_result.optimization_suggestions,
            'metadata': analysis_result.metadata
        },
        'measurement': measurement_result
    }
    
    # Save as JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


@app.command("analyze", rich_help_panel="Measurement")
def analyze_code_structure(
    language: Annotated[Language, typer.Argument(help="Programming language to analyze")],
    script: Annotated[Path, typer.Argument(help="Path to the script file to analyze")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file for analysis results")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="Verbose output with detailed instrumentation points")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output results in JSON format")] = False,
    show_suggestions: Annotated[bool, typer.Option("--suggestions", help="Show optimization suggestions")] = True,
    save_instrumented: Annotated[bool, typer.Option("--save-instrumented", help="Save instrumented code to current directory")] = False,
    output_dir: Annotated[Optional[Path], typer.Option("--output-dir", help="Directory to save instrumented code")] = None,
    no_cleanup: Annotated[bool, typer.Option("--no-cleanup", help="Keep temporary files (default: auto-cleanup)")] = False,
):
    """
    [bold]Analyze code structure[/bold] without energy measurement.

    This command performs static analysis of your code using Tree-sitter AST parsing
    to identify optimal instrumentation points for energy measurement. No code execution
    occurs - this is pure analysis for planning and optimization.

    [bold]Examples:[/bold]
    - [cyan]codegreen analyze python script.py[/cyan]
    - [cyan]codegreen analyze python module.py --verbose[/cyan]
    - [cyan]codegreen analyze python app.py --output analysis.json --suggestions[/cyan]
    - [cyan]codegreen analyze cpp main.cpp --verbose[/cyan]
    - [cyan]codegreen analyze python main.py --json[/cyan]

    [bold]Output formats:[/bold] JSON report with instrumentation points and suggestions
    [bold]Languages supported:[/bold] python, cpp, c, java
    """
    
    if not script.exists():
        if not json_output:
            console.print(f"[red]Error: Script file not found: {script}[/red]")
        else:
            print(json.dumps({"success": False, "error": f"Script file not found: {script}"}))
        raise typer.Exit(1)
    
    try:
        # Read source code
        with open(script, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if not json_output:
            console.print(f"[green]Analyzing code structure...[/green]")
            console.print(f"Language: [cyan]{language.value}[/cyan]")
            console.print(f"Script: [cyan]{script}[/cyan]")
        
        # Try to use Python language engine, fall back to C++ binary
        try:
            from ..instrumentation.language_engine import LanguageEngine
            engine = LanguageEngine()
            result = engine.analyze_code(source_code, language.value)
            
            if not result.success:
                if not json_output:
                    console.print(f"[red]Analysis failed: {result.error}[/red]")
                else:
                    print(json.dumps({"success": False, "error": result.error}))
                raise typer.Exit(1)
                
        except ImportError:
            if not json_output:
                console.print("[yellow]Language engine not available. Using C++ binary fallback.[/yellow]")
            # Fall back to C++ binary
            binary_path = get_binary_path()
            if not binary_path:
                if not json_output:
                    console.print("[red]Error: Neither Python language engine nor C++ binary found![/red]")
                else:
                    print(json.dumps({"success": False, "error": "Neither Python language engine nor C++ binary found!"}))
                raise typer.Exit(1)
            
            cmd = [str(binary_path), "--analyze", str(script)]
            if verbose:
                cmd.append("--verbose")
            if save_instrumented:
                cmd.append("--save-instrumented")
            if output_dir:
                cmd.extend(["--output-dir", str(output_dir)])
            if no_cleanup:
                cmd.append("--no-cleanup")
            
            # Subprocess handles its own output, but if JSON is requested we need to be careful
            # The C++ binary might not support --json yet
            result = subprocess.run(cmd, capture_output=True, text=True)
            if not json_output:
                console.print(result.stdout)
            if result.returncode != 0:
                if not json_output:
                    console.print(f"[red]Analysis failed: {result.stderr}[/red]")
                else:
                    print(json.dumps({"success": False, "error": result.stderr}))
                raise typer.Exit(1)
            
            if json_output:
                # If JSON was requested but we used C++ fallback, we might have to parse its output or return error
                print(json.dumps({"success": True, "method": "cpp_fallback", "output": result.stdout}))
            return
        
        if not json_output:
            # Display analysis results
            console.print(f"[green][ok] Analysis completed![/green]")
            console.print(f"Analysis method: [cyan]{result.metadata.get('analysis_method', 'unknown')}[/cyan]")
            console.print(f"Parser available: [cyan]{result.metadata.get('parser_available', False)}[/cyan]")
            console.print(f"Instrumentation points: [cyan]{result.checkpoint_count}[/cyan]")
            console.print(f"Analysis time: [cyan]{result.metadata.get('analysis_time_ms', 0):.2f}ms[/cyan]")
            console.print(f"Source lines: [cyan]{result.metadata.get('source_lines', 0)}[/cyan]")
        
        # Save instrumented code if requested
        if save_instrumented:
            if not json_output:
                console.print(f"\n[green]Instrumenting code...[/green]")
            _ns = result.metadata.get('normalised_source', source_code)
            instrumented_code = engine.instrument_code(_ns, result.instrumentation_points, language.value, pre_normalised_source=_ns)

            # Create output directory if it doesn't exist
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                instrumented_filename = script.stem + "_instrumented" + script.suffix
                instrumented_file_path = output_path / instrumented_filename
            else:
                instrumented_file_path = script.with_name(f'{script.stem}_instrumented{script.suffix}')
            
            with open(instrumented_file_path, 'w', encoding='utf-8') as f:
                f.write(instrumented_code)
            
            if not json_output:
                console.print(f"[green][ok] Instrumented code saved to: {instrumented_file_path}[/green]")
        
        if verbose and result.instrumentation_points and not json_output:
            # Show detailed instrumentation points
            console.print(f"\n[bold]Instrumentation Points:[/bold]")
            table = Table()
            table.add_column("Type", style="cyan")
            table.add_column("Subtype", style="blue")
            table.add_column("Name", style="green")
            table.add_column("Line", style="yellow")
            table.add_column("Context", style="dim")
            
            for point in result.instrumentation_points:
                table.add_row(
                    point.type,
                    point.subtype,
                    point.name,
                    str(point.line),
                    point.context[:60] + "..." if len(point.context) > 60 else point.context
                )
            
            console.print(table)
        
        if show_suggestions and result.optimization_suggestions and not json_output:
            console.print(f"\n[bold yellow]Optimization Suggestions:[/bold yellow]")
            for i, suggestion in enumerate(result.optimization_suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        
        # Output JSON results if requested or save to file
        analysis_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            'script': str(script),
            'language': result.language,
            'success': True,
            'analysis_metadata': {
                'method': result.metadata.get('analysis_method'),
                'parser_available': result.metadata.get('parser_available'),
                'time_ms': result.metadata.get('analysis_time_ms'),
                'source_lines': result.metadata.get('source_lines')
            },
            'instrumentation_points_count': result.checkpoint_count,
            'instrumentation_points': [
                {
                    'id': point.id,
                    'type': point.type,
                    'subtype': point.subtype,
                    'name': point.name,
                    'line': point.line,
                    'column': point.column,
                    'context': point.context,
                    'metadata': point.metadata
                }
                for point in result.instrumentation_points
            ],
            'optimization_suggestions': result.optimization_suggestions
        }

        if json_output:
            print(json.dumps(analysis_data, indent=2))
        
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2)
            if not json_output:
                console.print(f"[green][ok] Analysis saved to: {output}[/green]")
        
        if not json_output:
            console.print(f"\n[green][ok] Code analysis completed successfully![/green]")
        
    except Exception as e:
        if not json_output:
            console.print(f"[red]Analysis failed: {e}[/red]")
            if verbose:
                import traceback
                console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
        else:
            print(json.dumps({"success": False, "error": str(e)}))
        raise typer.Exit(1)

@app.command("init", rich_help_panel="Setup")
def comprehensive_init(
    force: Annotated[bool, typer.Option("--force", "-f", help="Force re-initialization even if config exists")] = False,
    interactive: Annotated[bool, typer.Option("--interactive", "-i", help="Interactive mode with user confirmation")] = True,
    config_path: Annotated[Optional[Path], typer.Option("--config", help="Custom config file path")] = None,
    auto_detect_only: Annotated[bool, typer.Option("--auto-detect-only", help="Only auto-detect, no user interaction")] = False,
    setup_permissions: Annotated[bool, typer.Option("--setup-permissions", help="Automatically run permission setup if needed")] = False,
):
    """
    [bold]Comprehensive CodeGreen system initialization[/bold].

    Performs intelligent system detection and configuration optimization:
    - [cyan]Environment detection[/cyan]: personal/server/HPC/container/CI environments
    - [cyan]Hardware sensor discovery[/cyan]: Intel RAPL, NVIDIA NVML, AMD ROCm
    - [cyan]Permission validation[/cyan]: RAPL access, GPU permissions, system capabilities
    - [cyan]Performance tuning[/cyan]: CPU scaling, memory optimization, threading
    - [cyan]Auto-configuration[/cyan]: generates optimized config based on your system

    This initialization caches all system information to avoid detection overhead
    during actual energy measurements, ensuring maximum measurement accuracy.

    [bold]Examples:[/bold]
    - [cyan]codegreen init[/cyan] - Interactive setup with confirmations
    - [cyan]codegreen init --auto-detect-only[/cyan] - Quick auto-detection
    - [cyan]codegreen init --setup-permissions[/cyan] - Auto-fix sensor permissions
    - [cyan]codegreen init --force[/cyan] - Re-initialize even if already configured
    """
    console.print(Panel.fit("[bold blue]CodeGreen Comprehensive Initialization[/bold blue]"))
    
    config_file_path = config_path or get_config_path()
    
    # Check if initialization already completed
    if not force and config_file_path and Path(config_file_path).exists():
        config = load_config(config_file_path)
        if config.get("initialization", {}).get("completed", False):
            console.print(f"[yellow]CodeGreen already initialized at: {config_file_path}[/yellow]")
            console.print("Use [cyan]--force[/cyan] to re-initialize")
            return
    
    # Step 1: Environment Detection
    console.print("\n[bold]Step 1: Environment Detection[/bold]")
    environment_info = detect_environment()
    
    # Step 2: Hardware Sensor Detection
    console.print("\n[bold]Step 2: Hardware Sensor Detection[/bold]")
    sensor_info = detect_hardware_sensors()
    
    # Step 3: Permission Validation
    console.print("\n[bold]Step 3: Permission Validation[/bold]")
    permission_info = check_energy_permissions()
    
    # Auto-run permission setup if requested and needed
    if setup_permissions and not permission_info.get("rapl_cpu", {}).get("accessible", False):
        install_dir = Path(__file__).resolve().parent.parent.parent / "install"
        setup_script = install_dir / "setup_permissions.sh"
        
        if install_dir.exists() and setup_script.exists():
            console.print("[blue]Auto-running permission setup...[/blue]")
            try:
                result = subprocess.run(
                    ["sudo", str(setup_script)],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    console.print("[green]Permission setup completed![/green]")
                    # Re-check permissions after setup
                    permission_info = check_energy_permissions()
                else:
                    console.print("[red]Permission setup failed[/red]")
                    if result.stderr:
                        console.print(result.stderr)
            except subprocess.SubprocessError as e:
                console.print(f"[red]Setup script error: {e}[/red]")
            except subprocess.TimeoutExpired:
                console.print("[red]Setup script timeout[/red]")
        else:
            console.print("[yellow]Permission setup requested but script not found[/yellow]")
    
    # Step 4: Performance Settings Detection
    console.print("\n[bold]Step 4: Performance Settings Detection[/bold]")
    performance_info = detect_performance_settings()
    
    # Display detection summary
    console.print("\n" + "="*60)
    console.print("[bold]Detection Summary[/bold]")
    console.print("="*60)
    
    # Environment table
    env_table = Table(title="Environment Information")
    env_table.add_column("Property", style="cyan")
    env_table.add_column("Value", style="green")
    env_table.add_row("Environment Type", environment_info["type"])
    env_table.add_row("Platform", environment_info["platform"])
    env_table.add_row("Deployment Mode", environment_info["deployment_mode"])
    console.print(env_table)
    
    # Hardware table  
    hw_table = Table(title="Hardware Sensors")
    hw_table.add_column("Sensor", style="cyan")
    hw_table.add_column("Status", style="green")
    hw_table.add_column("Details")
    
    for sensor, info in sensor_info.items():
        status = "Available" if info["available"] else "Unavailable"
        hw_table.add_row(sensor, status, info.get("details", ""))
    console.print(hw_table)
    
    # Permissions table
    perm_table = Table(title="Energy Access Permissions")
    perm_table.add_column("Resource", style="cyan") 
    perm_table.add_column("Status", style="green")
    perm_table.add_column("Details")
    
    for resource, info in permission_info.items():
        status = "Accessible" if info["accessible"] else "Denied"
        perm_table.add_row(resource, status, info.get("details", ""))
    console.print(perm_table)
    
    # Interactive confirmation (unless auto-detect-only)
    if interactive and not auto_detect_only:
        console.print("\n[bold]Configuration Confirmation[/bold]")
        
        # Environment-specific setup recommendations
        install_dir = Path(__file__).resolve().parent.parent.parent / "install"
        
        if not permission_info.get("rapl_cpu", {}).get("accessible", False):
            console.print("[yellow]RAPL Permission Setup Required[/yellow]")
            rapl_info = permission_info.get("rapl_cpu", {})
            if "fix_instructions" in rapl_info:
                for instruction in rapl_info["fix_instructions"]:
                    console.print(f"   [cyan]{instruction}[/cyan]")
            else:
                if install_dir.exists():
                    setup_script = install_dir / "setup_permissions.sh"
                    console.print(f"   Run: [cyan]sudo {setup_script}[/cyan]")
                else:
                    console.print("   Run: [cyan]sudo install/setup_permissions.sh[/cyan]")
        
        if environment_info["type"] == "container":
            console.print("[yellow]Container Environment Detected[/yellow]")
            if install_dir.exists():
                docker_script = install_dir / "docker-setup.sh"
                console.print(f"   See container setup: [cyan]{docker_script}[/cyan]")
            console.print("   May need --privileged or specific capabilities")
            
        elif environment_info["type"] == "hpc":
            console.print("[yellow]HPC Environment Detected[/yellow]")
            if install_dir.exists():
                hpc_module = install_dir / "hpc-module.lua"
                console.print(f"   HPC module available: [cyan]{hpc_module}[/cyan]")
            console.print("   Contact admin about module installation and permissions")
            
        # Offer to run setup automatically
        if not permission_info.get("rapl_cpu", {}).get("accessible", False):
            if install_dir.exists() and (install_dir / "setup_permissions.sh").exists():
                run_setup = typer.confirm("Run permission setup script automatically?")
                if run_setup:
                    console.print("[blue]Running permission setup...[/blue]")
                    try:
                        result = subprocess.run(
                            ["sudo", str(install_dir / "setup_permissions.sh")],
                            capture_output=True, text=True, timeout=60
                        )
                        if result.returncode == 0:
                            console.print("[green]Permission setup completed![/green]")
                            console.print("Re-running permission check...")
                            # Re-check permissions after setup
                            permission_info = check_energy_permissions()
                        else:
                            console.print("[red]Permission setup failed[/red]")
                            console.print(result.stderr)
                    except subprocess.SubprocessError as e:
                        console.print(f"[red]Setup script error: {e}[/red]")
                    except subprocess.TimeoutExpired:
                        console.print("[red]Setup script timeout[/red]")
        
        proceed = typer.confirm("Proceed with configuration generation?")
        if not proceed:
            console.print("[yellow]Initialization cancelled by user[/yellow]")
            return
        
        # Allow configuration customization
        custom_config = {}
        if typer.confirm("Customize configuration settings?"):
            # Environment-specific customizations
            if environment_info["type"] == "hpc":
                custom_config["measurement"] = {"nemb": {"accuracy_mode": "production"}}
            elif environment_info["type"] == "container":
                custom_config["performance"] = {"minimize_system_noise": False}
    else:
        custom_config = {}
    
    # Step 5: Generate optimized configuration
    console.print("\n[bold]Step 5: Generating Configuration[/bold]")
    config = generate_optimized_config(environment_info, sensor_info, permission_info, performance_info, custom_config)
    
    # Step 6: Test configuration
    console.print("\n[bold]Step 6: Testing Configuration[/bold]")
    test_results = test_configuration(config)
    
    if test_results["success"]:
        console.print("[green]Configuration test successful![/green]")
        
        # Save configuration
        config_dir = Path(config_file_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(config_file_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        console.print(f"\n[green]Initialization completed successfully![/green]")
        console.print(f"Configuration saved to: [cyan]{config_file_path}[/cyan]")
        
        # Display next steps
        console.print("\n[bold]Next Steps:[/bold]")
        console.print("• Run [cyan]codegreen info[/cyan] to verify system status")
        console.print("• Test with [cyan]codegreen run --repeat 3 -- python3 -c 'sum(range(10**7))'[/cyan]")
        console.print("• Customize settings with [cyan]codegreen config --edit[/cyan]")
        
    else:
        console.print("[red]Configuration test failed[/red]")
        for error in test_results.get("errors", []):
            console.print(f"  • {error}")
        
        if interactive:
            save_anyway = typer.confirm("Save configuration anyway?")
            if save_anyway:
                with open(config_file_path, 'w') as f:
                    json.dump(config, f, indent=2)
                console.print(f"Configuration saved with warnings: [cyan]{config_file_path}[/cyan]")
            else:
                console.print("[yellow]Configuration not saved[/yellow]")
        
        raise typer.Exit(1)

@app.command("info", rich_help_panel="Diagnostics")
def show_info(
    detailed: Annotated[bool, typer.Option("--detailed", "-d", help="Show detailed information")] = False,
):
    """
    [bold]Display CodeGreen installation and system information[/bold].

    Provides comprehensive status overview including binary locations, configuration
    files, runtime availability, sensor status, and system capabilities.

    [bold]Information included:[/bold]
    - Binary and runtime file locations
    - Configuration file status and settings
    - Python package version and dependencies
    - Hardware sensor availability
    - System platform and environment details

    [bold]Examples:[/bold]
    - [cyan]codegreen info[/cyan] - Basic system information
    - [cyan]codegreen info --detailed[/cyan] - Comprehensive system details
    """
    console.print(Panel.fit("[bold blue]CodeGreen Installation Information[/bold blue]"))
    
    binary_path = get_binary_path()
    config_path = get_config_path()
    runtime_available = ensure_runtime_available()
    config = load_config(config_path)
    
    # Create info table
    table = Table(title="Installation Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    # Binary information
    if binary_path:
        table.add_row("Binary", "[ok] Found", str(binary_path))
    else:
        table.add_row("Binary", "[!!] Missing", "CodeGreen binary not found")
    
    # Configuration information
    if config_path:
        table.add_row("Config", "[ok] Found", str(config_path))
    else:
        table.add_row("Config", "- Default", "Using default configuration")
    
    # Runtime information
    if runtime_available:
        table.add_row("Runtime", "[ok] Available", "Python runtime modules found")
    else:
        table.add_row("Runtime", "- Missing", "Runtime modules not found")
    
    # System information
    table.add_row("Platform", "[ok]", f"{platform.system()} {platform.machine()}")
    table.add_row("Python", "[ok]", sys.version.split()[0])
    
    # Package information
    try:
        import codegreen
        table.add_row("Version", "[ok]", f"CodeGreen {_VERSION}")
    except Exception:
        table.add_row("Version", "-", "Unknown")
    
    console.print(table)
    
    if detailed:
        console.print("\n[bold]Configuration Details:[/bold]")
        config_table = Table()
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")
        
        # Show key config settings
        pmt_config = config.get("measurement", {}).get("pmt", {})
        config_table.add_row("Preferred Sensors", ", ".join(pmt_config.get("preferred_sensors", [])))
        config_table.add_row("Fallback Enabled", str(pmt_config.get("fallback_enabled", True)))
        config_table.add_row("Validation Enabled", str(pmt_config.get("validation_enabled", True)))
        
        console.print(config_table)

@app.command("doctor", rich_help_panel="Diagnostics")
def diagnose(
    test_sensors: Annotated[bool, typer.Option("--test-sensors", help="Run a live energy measurement test")] = False,
):
    """
    [bold]Diagnose CodeGreen installation and configuration issues[/bold].

    Performs comprehensive system diagnostics to identify and resolve common
    installation, configuration, and runtime problems. Provides actionable
    recommendations for fixing detected issues.

    [bold]Diagnostic checks include:[/bold]
    - Binary accessibility and execution
    - Python dependencies and imports
    - Configuration file validity
    - Hardware sensor functionality
    - Permission and access issues
    - Runtime module availability

    [bold]Examples:[/bold]
    - [cyan]codegreen doctor[/cyan] - Basic diagnostic checks
    - [cyan]codegreen doctor --test-sensors[/cyan] - Include sensor functionality tests
    - [cyan]codegreen doctor --test-sensors[/cyan] - Run live sensor test
    """
    console.print(Panel.fit("[bold green]CodeGreen Doctor - System Diagnosis[/bold green]"))
    
    issues = []
    warnings = []
    
    # Check binary
    binary_path = get_binary_path()
    if not binary_path:
        issues.append("CodeGreen binary not found")
    else:
        console.print(f"[green][ok][/green] Binary: {binary_path}")
    
    # Check dependencies
    try:
        import typer, rich, psutil
        console.print("[green][ok][/green] Python dependencies available")
    except ImportError as e:
        issues.append(f"Missing Python dependency: {e}")
    # Check runtime
    if not ensure_runtime_available():
        warnings.append("Runtime modules not found - some features may not work")
    else:
        console.print("[green][ok][/green] Runtime modules available")
    
    # Check configuration
    config_path = get_config_path()
    if not config_path:
        warnings.append("Default configuration file not found")
    else:
        console.print(f"[green][ok][/green] Configuration: {config_path}")
    
    # Check NEMB native library
    nemb = _NEMBBackend()
    lib = nemb._load()
    if lib and lib is not False:
        console.print("[green][ok][/green] NEMB native library loaded")
    else:
        issues.append("NEMB native library not found (energy measurement unavailable)")

    # Check energy backend availability
    backend = _get_energy_backend()
    if isinstance(backend, _TimeOnlyBackend):
        issues.append(f"No energy backend available (time-only fallback)")
    else:
        console.print(f"[green][ok][/green] Energy backend: {backend.name}")

    # Check GPU (NVIDIA)
    gpu_detected = False
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                gpu_detected = True
                console.print(f"[green][ok][/green] NVIDIA GPU: {r.stdout.strip().splitlines()[0]}")
        except Exception:
            pass
    if gpu_detected and not (lib and lib is not False):
        warnings.append("NVIDIA GPU detected but NEMB library not loaded (no GPU energy measurement)")
        warnings.append("Fix: pip install --force-reinstall --no-cache-dir codegreen")

    # Check energy permissions (Linux RAPL / macOS sudo)
    if sys.platform == "linux":
        perms = check_energy_permissions()
        rapl = perms.get("rapl_cpu", {})
        if rapl.get("accessible"):
            console.print(f"[green][ok][/green] RAPL access: {rapl.get('details', 'OK')}")
        elif rapl.get("denied_files"):
            issues.append(f"RAPL permission denied for {len(rapl['denied_files'])} files")
            for hint in rapl.get("fix_instructions", []):
                warnings.append(hint)
        else:
            warnings.append("RAPL interface not found (non-Intel/AMD CPU?)")
    elif sys.platform == "darwin":
        if not shutil.which("powermetrics"):
            warnings.append("powermetrics not found (macOS energy measurement unavailable)")

    # Test actual measurement if requested
    if test_sensors and not isinstance(backend, _TimeOnlyBackend):
        console.print("\n[bold]Testing energy measurement...[/bold]")
        try:
            backend._quiet = True
            e, t = backend.measure(["true"] if sys.platform != "win32" else ["cmd", "/c", "echo"], timeout=10)
            if e is not None and e > 0:
                console.print(f"[green][ok][/green] Sensor test passed ({e:.4f} J in {t:.3f} s)")
            else:
                warnings.append(f"Sensor returned no energy data (elapsed {t:.3f}s)")
        except Exception as ex:
            issues.append(f"Sensor test failed: {ex}")

    # Summary
    console.print("\n[bold]Diagnosis Summary:[/bold]")
    
    if issues:
        console.print("[red]Issues found:[/red]")
        for issue in issues:
            console.print(f"  [red][!!][/red] {issue}")
    
    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")
    
    if not issues and not warnings:
        console.print("[green][ok] No issues found! CodeGreen appears to be properly installed.[/green]")
    
    if issues:
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("1. Try reinstalling CodeGreen: [cyan]pip install --force-reinstall codegreen[/cyan]")
        console.print("2. Check system requirements in the documentation")
        console.print("3. Run [cyan]codegreen init[/cyan] to initialize sensors")
        console.print("4. Report issues at: https://github.com/SMART-Dal/codegreen/issues")


@app.command("validate", hidden=True, rich_help_panel="Validation")
def validate_accuracy(
    reference: Annotated[str, typer.Option("--reference", help="Reference tool (rapl, perf, both)")] = "both",
    duration: Annotated[int, typer.Option("--duration", "-d", help="Duration in seconds")] = 5,
    tolerance: Annotated[float, typer.Option("--tolerance", "-t", help="Acceptable error percentage")] = 5.0,
):
    """
    [bold]Validate measurement accuracy against native hardware tools[/bold].

    Compares CodeGreen's NEMB energy measurements with native tools (RAPL, perf,
    nvidia-smi) to ensure accuracy and detect measurement contamination. Critical
    for verifying energy measurement quality in research and production environments.

    [bold red]Requires root access[/bold red] for direct hardware energy interfaces.

    [bold]Validation methods:[/bold]
    - Direct RAPL register comparison
    - Cross-validation with perf energy events
    - NVIDIA GPU power measurement verification
    - Statistical accuracy analysis

    [bold]Examples:[/bold]
    - [cyan]sudo codegreen validate[/cyan] - Full validation suite
    - [cyan]sudo codegreen validate --reference rapl --tolerance 3.0[/cyan]
    - [cyan]sudo codegreen validate --duration 15[/cyan] - Extended validation
    """
    
    validation_script = Path(__file__).resolve().parent.parent.parent / "test_nemb_validation.sh"
    
    if not validation_script.exists():
        console.print("[red]Error: Validation script not found![/red]")
        console.print(f"Expected location: {validation_script}")
        raise typer.Exit(1)
    
    # Check if running as root
    if not _is_root():
        console.print("[red]Error: Root access required for validation![/red]")
        console.print("Hardware energy interfaces (RAPL, MSR) require privileged access.")
        console.print(f"Please run: [cyan]sudo codegreen validate[/cyan]")
        raise typer.Exit(1)
    
    console.print(Panel.fit("[bold green]CodeGreen NEMB Accuracy Validation[/bold green]"))
    
    try:
        with Progress(
            SpinnerColumn(), 
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running comprehensive validation...", total=None)
            
            console.print(f"[green]Configuration:[/green]")
            console.print(f"  Reference tools: [cyan]{reference}[/cyan]")
            console.print(f"  Duration: [cyan]{duration}s[/cyan]")
            console.print(f"  Tolerance: [cyan]±{tolerance}%[/cyan]")
            console.print(f"  Script: [dim]{validation_script}[/dim]")
            
            # Set environment variables for the validation script
            env = os.environ.copy()
            env['DURATION'] = str(duration)
            env['TOLERANCE'] = str(tolerance)
            env['REFERENCE'] = reference
            
            # Execute validation script with sudo
            result = subprocess.run(
                [str(validation_script)], 
                capture_output=True, 
                text=True,
                timeout=duration+60,
                env=env
            )
            progress.update(task, completed=True)
        
        console.print("\n[bold]Validation Results:[/bold]")
        console.print(result.stdout)
        
        if result.stderr:
            console.print("\n[bold yellow]Warnings/Debug:[/bold yellow]")
            console.print(result.stderr)
        
        if result.returncode == 0:
            console.print("\n[green][ok] Validation completed successfully![/green]")
        else:
            console.print(f"\n[red][!!] Validation failed with exit code {result.returncode}[/red]")
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("[red]Validation timed out[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)

@app.command("config", rich_help_panel="Setup")
def config_management(
    show: Annotated[bool, typer.Option("--show", help="Show current configuration")] = False,
    edit: Annotated[bool, typer.Option("--edit", help="Edit configuration file")] = False,
    reset: Annotated[bool, typer.Option("--reset", help="Reset to default configuration")] = False,
):
    """
    [bold]Manage CodeGreen configuration and settings[/bold].

    View, modify, and manage CodeGreen's configuration including sensor preferences,
    measurement accuracy settings, performance tuning, and environment-specific
    optimizations. All changes are validated before saving.

    Works out of the box with sensible defaults. Customize by creating
    a user config at [cyan]~/.codegreen/config.json[/cyan] (overrides package defaults).

    [bold]Key settings:[/bold]
    - [cyan]measurement_interval_ms[/cyan]: RAPL polling rate (default: 1ms)
    - [cyan]measurement_buffer_size[/cyan]: ring buffer capacity (default: 100000)
    - [cyan]cross_validation_threshold[/cyan]: provider agreement threshold (default: 0.05)
    - Provider enable/disable: [cyan]intel_rapl[/cyan], [cyan]nvidia_nvml[/cyan], [cyan]amd_rocm[/cyan]

    [bold]Examples:[/bold]
    - [cyan]codegreen config[/cyan]         - Show active settings summary
    - [cyan]codegreen config --show[/cyan]  - Full JSON dump
    - [cyan]codegreen config --edit[/cyan]  - Open user config in editor (creates if needed)
    - [cyan]codegreen config --reset[/cyan] - Delete user config, revert to defaults
    """
    config_path = get_config_path()
    user_config = Path.home() / ".codegreen" / "config.json"

    if show:
        if config_path:
            console.print(f"[green]Active config:[/green] {config_path}")
            if config_path == user_config:
                console.print(f"  [dim](user override -- delete to revert to defaults)[/dim]")
            config = load_config(config_path)
            console.print(json.dumps(config, indent=2))
        else:
            console.print("[yellow]No configuration file found (using built-in defaults)[/yellow]")

    elif edit:
        if not user_config.exists():
            if config_path:
                user_config.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(config_path, user_config)
                console.print(f"[green]Created user config:[/green] {user_config}")
                console.print(f"  [dim]Copied defaults from {config_path}[/dim]")
            else:
                console.print("[red]No default config to copy[/red]")
                raise typer.Exit(1)
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
        console.print(f"[blue]Opening {user_config} with {editor}[/blue]")
        os.execvp(editor, [editor, str(user_config)])

    elif reset:
        if user_config.exists():
            user_config.unlink()
            console.print(f"[green]Removed user config:[/green] {user_config}")
            console.print(f"  Using package defaults from: {get_config_path() or 'built-in'}")
        else:
            console.print("[dim]No user config to reset (already using defaults)[/dim]")

    else:
        # No flag: show summary of what's active and how to customize
        console.print(f"[bold]Configuration[/bold]")
        if config_path:
            console.print(f"  Active: {config_path}")
        else:
            console.print(f"  Active: built-in defaults")
        if user_config.exists():
            console.print(f"  User override: {user_config}")
        else:
            console.print(f"  User override: [dim]none (using defaults)[/dim]")
        config = load_config(config_path) if config_path else {}
        nemb = config.get("measurement", {}).get("nemb", {})
        coord = nemb.get("coordinator", {})
        console.print(f"\n[bold]Measurement Settings[/bold]")
        console.print(f"  Sampling interval:  {coord.get('measurement_interval_ms', 10)} ms")
        console.print(f"  Buffer size:        {coord.get('measurement_buffer_size', 1000)}")
        console.print(f"  Cross-validation:   {coord.get('cross_validation', True)}")
        console.print(f"\n[dim]To customize: codegreen config --edit[/dim]")
        console.print(f"[dim]Full dump:    codegreen config --show[/dim]")

@app.command("init-sensors", rich_help_panel="Setup")
def init_sensors():
    """
    [bold]Initialize energy sensor permissions[/bold].

    Creates a 'codegreen' group, adds the current user, and sets read
    permissions on RAPL sysfs files. A udev rule ensures permissions
    persist across reboots. Must be run once with sudo.

    [bold]Examples:[/bold]
    - [cyan]sudo codegreen init-sensors[/cyan] - Set up RAPL access
    """
    import os
    import pwd
    import grp
    from pathlib import Path

    # First check if sensors are already accessible (no sudo needed)
    rapl_test_paths = list(Path("/sys/class/powercap").glob("intel-rapl*/energy_uj"))
    if rapl_test_paths:
        try:
            rapl_test_paths[0].read_text()
            console.print("[green]Sensors already initialized and accessible![/green]")
            console.print("")
            console.print("Current user has permission to read RAPL sensors.")
            console.print("You can now use CodeGreen commands without sudo:")
            console.print("  codegreen info")
            console.print("  codegreen run --repeat 3 -- python3 -c 'sum(range(10**7))'")
            return
        except PermissionError:
            pass

    # Check if running as root
    if not _is_root():
        console.print("[red]This command must be run with sudo[/red]")
        console.print("[yellow]Usage: sudo codegreen init-sensors[/yellow]")
        raise typer.Exit(1)

    # Get actual user
    actual_user = os.environ.get('SUDO_USER', os.environ.get('USER'))
    if not actual_user or actual_user == 'root':
        console.print("[red]Could not determine actual user[/red]")
        raise typer.Exit(1)

    console.print(f"[bold blue]Setting up CodeGreen for user: {actual_user}[/bold blue]")
    console.print("")

    try:
        # 1. Create codegreen group
        console.print("[cyan]Creating 'codegreen' group...[/cyan]")
        try:
            grp.getgrnam('codegreen')
            console.print("  [ok] Group already exists")
        except KeyError:
            subprocess.run(['groupadd', 'codegreen'], check=True)
            console.print("  [ok] Group created")

        # 2. Add user to group
        console.print(f"[cyan]Adding {actual_user} to 'codegreen' group...[/cyan]")
        user_groups = [g.gr_name for g in grp.getgrall() if actual_user in g.gr_mem]
        if 'codegreen' not in user_groups:
            subprocess.run(['usermod', '-aG', 'codegreen', actual_user], check=True)
            console.print("  [ok] User added to group")
        else:
            console.print("  [ok] User already in group")

        # 3. Set RAPL permissions
        console.print("[cyan]Setting RAPL permissions...[/cyan]")
        rapl_paths = Path("/sys/class/powercap").glob("intel-rapl*/energy_uj")
        count = 0
        for rapl_file in rapl_paths:
            subprocess.run(['chgrp', 'codegreen', str(rapl_file)], check=False)
            subprocess.run(['chmod', 'g+r', str(rapl_file)], check=False)
            count += 1

        max_paths = Path("/sys/class/powercap").glob("intel-rapl*/max_energy_range_uj")
        for rapl_file in max_paths:
            subprocess.run(['chgrp', 'codegreen', str(rapl_file)], check=False)
            subprocess.run(['chmod', 'g+r', str(rapl_file)], check=False)

        if count > 0:
            console.print(f"  [ok] Set permissions on {count} RAPL domains")
        else:
            console.print("  ! No RAPL files found (CPU may not support it)")

        # 4. Create udev rule
        console.print("[cyan]Creating udev rule for persistent permissions...[/cyan]")
        udev_rule = """# CodeGreen - Persistent RAPL permissions
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", GROUP="codegreen", MODE="0640"
"""
        udev_file = Path("/etc/udev/rules.d/99-codegreen-rapl.rules")
        udev_file.write_text(udev_rule)
        console.print(f"  [ok] Created {udev_file}")

        # 5. Reload udev
        console.print("[cyan]Reloading udev rules...[/cyan]")
        subprocess.run(['udevadm', 'control', '--reload-rules'], check=False)
        subprocess.run(['udevadm', 'trigger'], check=False)
        console.print("  [ok] Udev rules reloaded")

        console.print("")
        console.print("[green]Sensor setup complete![/green]")
        console.print("")
        console.print("[yellow]IMPORTANT: Log out and log back in for group changes to take effect[/yellow]")
        console.print("")
        console.print("After relogin, test with:")
        console.print("  codegreen info")
        console.print("  codegreen run --repeat 3 -- python3 -c 'sum(range(10**7))'")
        console.print("")
        console.print("[green]No sudo needed after this![/green]")

    except Exception as e:
        console.print(f"[red]Setup failed: {e}[/red]")
        raise typer.Exit(1)

@app.command("measure-workload", hidden=True, rich_help_panel="Validation")
def run_measure_workload(
    duration: Annotated[int, typer.Option("--duration", help="Duration in seconds to run the workload")] = 3,
    workload: Annotated[str, typer.Option("--workload", help="Type of workload to measure (cpu_stress, memory_stress)")] = "cpu_stress",
):
    """
    [bold]Measure energy consumption of specified workload[/bold].

    Executes a controlled workload while measuring energy consumption using
    hardware sensors. This is useful for benchmarking system energy usage,
    calibrating sensors, and testing measurement accuracy.

    [bold]Available workloads:[/bold]
    - [cyan]cpu_stress[/cyan] - Intensive CPU computation (mathematical operations)
    - [cyan]memory_stress[/cyan] - Memory allocation and access patterns
    - [cyan]mixed[/cyan] - Combination of CPU and memory operations

    [bold]Measurement details:[/bold]
    - Uses Intel RAPL energy counters for CPU package power
    - Measures total energy consumption in Joules
    - Calculates average power consumption in Watts
    - Reports measurement uncertainty and validity
    - Creates timestamped measurement records

    [bold]Requirements:[/bold]
    - Initialized sensors (run 'codegreen init-sensors' first)
    - Hardware energy measurement support
    - Sufficient system permissions for sensor access

    [bold]Examples:[/bold]
    - [cyan]codegreen measure-workload[/cyan] - Default 3-second CPU stress test
    - [cyan]codegreen measure-workload --duration 10 --workload cpu_stress[/cyan]
    - [cyan]codegreen measure-workload --duration 5 --workload memory_stress[/cyan]

    [bold]Output includes:[/bold]
    - Total energy consumed (Joules)
    - Average power consumption (Watts)
    - Measurement duration and validity
    - Uncertainty estimates and error bounds
    """
    console.print(f"[bold blue]Starting workload measurement...[/bold blue]")
    console.print(f"[blue]Duration:[/blue] {duration} seconds")
    console.print(f"[blue]Workload:[/blue] {workload}")
    
    backend = _get_energy_backend()
    if isinstance(backend, _TimeOnlyBackend):
        console.print("[red]No energy measurement backend available[/red]")
        raise typer.Exit(1)

    # Generate workload command
    if workload == "cpu_stress":
        cmd = ["python3", "-c", f"import time;t=time.time();[sum(range(10**6)) for _ in iter(lambda:time.time()-t<{duration},True)]"]
    elif workload == "memory_stress":
        cmd = ["python3", "-c", f"import time;t=time.time();exec('x=[]\\nwhile time.time()-t<{duration}:\\n x.append(bytearray(10**6))\\n if len(x)>100: x.clear()')"]
    else:
        cmd = ["python3", "-c", f"import time;time.sleep({duration})"]

    try:
        energy_j, elapsed = backend.measure(cmd, timeout=duration + 30)
        if energy_j and energy_j > 0:
            console.print("[green]Workload measurement completed successfully[/green]")
            console.print(f"Energy: {energy_j:.4f} J")
            console.print(f"Power:  {energy_j/elapsed:.2f} W")
            console.print(f"Duration: {elapsed:.2f} s")
        else:
            console.print("[red]Workload measurement failed: backend returned no energy[/red]")
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("[red]Workload measurement timed out[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error during workload measurement: {e}[/red]")
        raise typer.Exit(1)

@app.command("benchmark", rich_help_panel="Validation")
def run_benchmark(
    suite_name: Annotated[str, typer.Option("--suite", help="Benchmark suite: benchmarksgame, perfopt")] = "benchmarksgame",
    problems: Annotated[Optional[List[str]], typer.Option("--problem", "-p", help="Problems/tasks to run")] = None,
    languages: Annotated[Optional[List[str]], typer.Option("--lang", "-l", help="Languages to test")] = None,
    sizes: Annotated[Optional[List[str]], typer.Option("--size", "-s", help="Problem sizes")] = None,
    profilers: Annotated[Optional[List[str]], typer.Option("--profiler", help="Profilers: codegreen, perf")] = None,
    repetitions: Annotated[int, typer.Option("--reps", "-r", help="Repetitions per test")] = 5,
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Output directory")] = Path("benchmark/results"),
    compare: Annotated[bool, typer.Option("--compare", help="Show variant comparison (original vs patched)")] = False,
    dataset_dir: Annotated[Optional[Path], typer.Option("--dataset-dir", help="Dataset directory (for perfopt)")] = None,
    jars_dir: Annotated[Optional[Path], typer.Option("--jars-dir", help="Pre-built JARs directory (for perfopt)")] = None,
):
    """Run benchmarks comparing codegreen vs perf RAPL.

    Suites: benchmarksgame (default), perfopt (Java JMH benchmarks).

    Examples:
      codegreen benchmark                              # benchmarksgame defaults
      codegreen benchmark -p nbody -l python --reps 5  # specific problem
      codegreen benchmark --suite perfopt --dataset-dir ~/data/PerfOpt --jars-dir ~/data/jars -p 9bb2f78
    """
    from benchmark.suites import get_suite
    from benchmark.harness import BenchmarkHarness
    from benchmark.results import ComparisonReport

    def progress_cb(msg: str):
        console.print(f"[dim]{msg}[/dim]")

    output_dir.mkdir(parents=True, exist_ok=True)

    suite_kwargs = {}
    if suite_name == "benchmarksgame":
        suite_kwargs = {"languages": languages, "problems": problems, "sizes": sizes}
    elif suite_name == "perfopt":
        suite_kwargs = {"dataset_dir": dataset_dir, "jars_dir": jars_dir,
                        "projects": languages, "tasks": problems}

    suite = get_suite(suite_name, **suite_kwargs)
    harness = BenchmarkHarness(suite=suite, repetitions=repetitions,
                                progress_callback=progress_cb)
    profs = profilers or ["perf", "codegreen"]

    console.print(f"[bold]Running benchmarks[/bold]")
    console.print(f"  Suite: {suite_name}")
    console.print(f"  Profilers: {profs}")
    console.print(f"  Repetitions: {repetitions}")
    console.print(f"  Output: {output_dir}")

    try:
        filters = {}
        if problems:
            filters["problems"] = problems
        if languages:
            filters["languages"] = languages

        collector = harness.run_suite(profilers=profs, repetitions=repetitions,
                                       filters=filters if filters else None)

        console.print(f"\n[bold green]Benchmark complete: {len(collector.results)} runs[/bold green]")

        # Profiler comparison table (CodeGreen vs perf accuracy)
        if "perf" in profs and "codegreen" in profs:
            prof_comparisons = ComparisonReport.compare_profilers(collector)
            if prof_comparisons:
                table = Table(title="Profiler Accuracy: CodeGreen vs perf RAPL")
                table.add_column("Task")
                table.add_column("Perf (J)")
                table.add_column("CodeGreen (J)")
                table.add_column("Error %")
                for c in prof_comparisons:
                    table.add_row(c["task"], f"{c['baseline_mean_j']:.2f}",
                                  f"{c['test_mean_j']:.2f}", f"{c['error_pct']:.1f}%")
                console.print(table)

        # Variant comparison table (original vs patched for PerfOpt)
        if compare or suite_name == "perfopt":
            var_comparisons = ComparisonReport.compare_variants(collector)
            if var_comparisons:
                table = Table(title="Energy: Original vs Patched")
                table.add_column("Task")
                table.add_column("Original (J)")
                table.add_column("Patched (J)")
                table.add_column("Delta %")
                table.add_column("Significant")
                for c in var_comparisons:
                    b = c["baseline_energy"]
                    p = c["candidate_energy"]
                    b_str = f"{b.mean:.2f}" if hasattr(b, 'mean') else str(b)
                    p_str = f"{p.mean:.2f}" if hasattr(p, 'mean') else str(p)
                    sig = "Yes" if c["significant"] else "No"
                    table.add_row(c["task"], b_str, p_str,
                                  f"{c['delta_pct']:.1f}%", sig)
                console.print(table)

        json_file = output_dir / f"benchmark_{suite_name}_latest.json"
        csv_file = output_dir / f"benchmark_{suite_name}_latest.csv"
        collector.to_json(json_file)
        collector.to_csv(csv_file)
        console.print(f"\n{collector.to_text()}")
        console.print(f"\nResults saved to {json_file}")
    finally:
        harness.cleanup()

@app.command("run", rich_help_panel="Measurement")
def run_command(
    command: Annotated[List[str], typer.Argument(help="Command to measure energy for")],
    repeat: Annotated[int, typer.Option("--repeat", "-n", help="Number of repetitions")] = 10,
    warmup: Annotated[int, typer.Option("--warmup", "-w", help="Warmup runs")] = 1,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    budget: Annotated[Optional[float], typer.Option("--budget", help="Energy budget in Joules (fail if exceeded)")] = None,
    include_warmup: Annotated[bool, typer.Option("--include-warmup", help="Measure energy during warmup and include in results")] = False,
    stdin_file: Annotated[Optional[str], typer.Option("--stdin", help="Bind file as stdin (avoids unsafe bash -c '... < file' wrapping)")] = None,
    validate: Annotated[bool, typer.Option("--validate/--no-validate", help="Execute the command once, unmeasured, before measuring (a failing command is also caught by the first measured run)")] = True,
    validate_timeout: Annotated[int, typer.Option("--validate-timeout", help="Seconds allowed for the validation run")] = 300,
    timeout: Annotated[Optional[int], typer.Option("--timeout", help="Per-run limit in seconds (default: none; the caller bounds the call)")] = None,
):
    """[bold]Measure energy[/bold] of any shell command with hardware-level precision.

    [bold]Important:[/bold] Use [cyan]--[/cyan] before commands that have their own flags.
    Without it, flags like -c or -jar are parsed as codegreen options and will fail.

    [bold]Examples:[/bold]
    - [cyan]codegreen run python3 script.py[/cyan]
    - [cyan]codegreen run -- python3 -c "sum(range(10**7))"[/cyan]
    - [cyan]codegreen run --repeat 20 -- ./my_binary -v arg1[/cyan]
    - [cyan]codegreen run --budget 10.0 --json -- python train.py[/cyan]
    - [cyan]codegreen run -- java -cp build MyClass[/cyan]
    """
    import subprocess, time, math
    from benchmark.results import StatisticalAnalysis

    if repeat < 1:
        console.print("[red]--repeat must be >= 1[/red]")
        raise typer.Exit(1)
    if warmup < 0:
        console.print("[red]--warmup must be >= 0[/red]")
        raise typer.Exit(1)

    # Resolve the executable: check it exists before doing anything
    exe = command[0]
    ext = Path(exe).suffix.lower()
    _SCRIPT_INTERPRETERS = {".py": "python3", ".js": "node", ".rb": "ruby", ".sh": "bash", ".pl": "perl"}
    def _run_error(msg: str):
        if json_output:
            print(json.dumps({"success": False, "error": msg}))
        else:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)

    if ext in _SCRIPT_INTERPRETERS and not shutil.which(exe):
        if not Path(exe).is_file():
            _run_error(f"File not found: {exe}")
        else:
            interp = _SCRIPT_INTERPRETERS[ext]
            if json_output:
                _run_error(f"'{exe}' is a script. Use: codegreen run {interp} {' '.join(command)}")
            else:
                console.print(f"[red]'{exe}' is a script, not an executable.[/red]")
                console.print(f"[dim]Try: codegreen run {interp} {' '.join(command)}[/dim]")
                raise typer.Exit(1)
    if not shutil.which(exe) and not Path(exe).is_file():
        hint = " (try 'python3' on macOS)" if exe == "python" else ""
        _run_error(f"Command not found: {exe}{hint}")

    backend = _get_energy_backend()

    # Refuse to run without real energy data -- no silent fallbacks
    if isinstance(backend, _TimeOnlyBackend):
        err_lines = ["No energy measurement backend available."]
        fix_lines = []
        if sys.platform == "linux":
            perms = check_energy_permissions()
            rapl = perms.get("rapl_cpu", {})
            if rapl.get("denied_files"):
                err_lines.append(rapl.get("details", "RAPL permission denied"))
                fix_lines = rapl.get("fix_instructions", [])
            else:
                err_lines.append("NEMB library not found and no RAPL access.")
                fix_lines = ["Install NEMB: pip install --force-reinstall --no-cache-dir codegreen",
                             "Or install perf: sudo apt install linux-tools-common linux-tools-$(uname -r)"]
        elif sys.platform == "darwin":
            err_lines.append("NEMB native library not built.")
            fix_lines = ["Install cmake: brew install cmake",
                         "Rebuild: pip install --force-reinstall --no-cache-dir codegreen",
                         "Or run with sudo for powermetrics: sudo codegreen run ..."]
        elif sys.platform == "win32":
            err_lines.append("NEMB native library not found.")
            fix_lines = ["Reinstall with cmake: pip install --force-reinstall --no-cache-dir codegreen"]
        if json_output:
            print(json.dumps({"success": False, "error": " ".join(err_lines), "fix": fix_lines}))
        else:
            for line in err_lines:
                console.print(f"[red]{line}[/red]")
            for hint in fix_lines:
                console.print(f"  [yellow]{hint}[/yellow]")
            console.print(f"\n  Run [cyan]codegreen doctor[/cyan] for full diagnostics.")
        raise typer.Exit(1)

    # Warn if using a lower-priority backend (perf instead of NEMB)
    if not json_output:
        if isinstance(backend, _PerfBackend):
            console.print(f"[yellow]Energy backend: {backend.name} (perf stat wrapper)[/yellow]")
            console.print(f"  [dim]For per-domain breakdown + GPU energy, install NEMB: pip install --force-reinstall codegreen[/dim]")
        elif isinstance(backend, _PowermetricsBackend):
            console.print(f"[yellow]Energy backend: {backend.name} (estimated from power samples)[/yellow]")
            console.print(f"  [dim]For direct measurement, install NEMB: pip install --force-reinstall codegreen[/dim]")
        else:
            console.print(f"[dim]Energy backend: {backend.name}[/dim]")

    # Linux RAPL permission check even for NEMB (partial access scenario)
    if sys.platform == "linux" and isinstance(backend, _PerfBackend):
        perms = check_energy_permissions()
        rapl = perms.get("rapl_cpu", {})
        if not rapl.get("accessible", False) and rapl.get("denied_files"):
            err = rapl.get("details", "RAPL permission denied")
            if json_output:
                print(json.dumps({"success": False, "error": err,
                                  "fix": rapl.get("fix_instructions", [])}))
            else:
                console.print(f"[red]{err}[/red]")
                for hint in rapl.get("fix_instructions", []):
                    console.print(f"  [yellow]{hint}[/yellow]")
            raise typer.Exit(1)

    # Always capture output during measurement for consistent timing (B1 fix).
    # Display captured output afterward in human mode.
    backend._quiet = True
    # stdin file (if any) is attached after the dry-run validator opens it.

    # --stdin: open once, rewind on every invocation. Surface a structured
    # failure_reason when the file is missing rather than letting subprocess
    # raise an opaque FileNotFoundError downstream.
    stdin_fh = None
    if stdin_file is not None:
        if not Path(stdin_file).is_file():
            msg = f"stdin_file_missing: {stdin_file}"
            if json_output:
                print(json.dumps({"success": False, "error": msg}))
            else:
                console.print(f"[red]{msg}[/red]")
            raise typer.Exit(1)
        stdin_fh = open(stdin_file, "rb")
        backend._stdin_fh = stdin_fh

    def _stdin():
        if stdin_fh is None:
            return None
        stdin_fh.seek(0)
        return stdin_fh

    # Dry run: validate command executes successfully before measuring energy.
    # Optional: it doubles wall time for long workloads, and a failing command
    # also fails the first measured run.
    check = None
    try:
        if validate:
            check = subprocess.run(command, capture_output=True, timeout=validate_timeout,
                                   stdin=_stdin())
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        msg = (f"Command not found: {exe}" if isinstance(e, FileNotFoundError)
               else f"Command timed out during validation (>{validate_timeout}s)")
        if json_output:
            print(json.dumps({"success": False, "error": msg}))
        else:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(1)
    if check is not None and check.returncode != 0:
        stderr = (check.stderr or b"").decode(errors="replace").strip()
        msg = f"Command failed (exit {check.returncode})"
        if json_output:
            print(json.dumps({"success": False, "error": msg, "stderr": stderr[:500]}))
        else:
            console.print(f"[red]{msg}:[/red]")
            if stderr:
                console.print(f"[red]{stderr[:500]}[/red]")
        raise typer.Exit(1)

    import socket as _socket
    import uuid as _uuid
    from datetime import timezone as _tz
    from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import (
        build_meta_block as _build_meta,
        _iso_local_now,
    )

    _meta_started_at = datetime.now(_tz.utc).isoformat(timespec="microseconds")
    _meta_started_at_local = _iso_local_now()
    _meta_t0_mono = time.monotonic()
    try:
        _meta_hostname = _socket.gethostname()
    except Exception:
        _meta_hostname = "unknown"
    _meta_run_id = _uuid.uuid4().hex[:12]

    def _backend_descriptor() -> Dict[str, Any]:
        """Structured backend identity. Open for extension: a new backend type
        slots in by adding an isinstance branch returning the same shape."""
        nm = backend.name
        domains_seen: List[str] = []
        if isinstance(backend, _NEMBBackend):
            try:
                domains_seen = list(backend.get_last_domain_breakdown().keys())
            except Exception:
                domains_seen = []
            driver = "nemb_native"
        elif "perf" in nm.lower():
            driver = "perf_rapl"
        elif "powermetrics" in nm.lower():
            driver = "powermetrics_ioreport"
        elif isinstance(backend, _TimeOnlyBackend):
            driver = "time_only"
        else:
            driver = "unknown"
        return {"name": nm, "driver": driver, "domains_seen": domains_seen}

    def _emit_failure_meta(error_msg: str, **extra) -> str:
        """Always include meta on failure paths so log-correlation works."""
        meta = _build_meta(
            run_id=_meta_run_id,
            started_at_iso=_meta_started_at,
            ended_at_iso=datetime.now(_tz.utc).isoformat(timespec="microseconds"),
            started_at_local_iso=_meta_started_at_local,
            ended_at_local_iso=_iso_local_now(),
            duration_total_s=time.monotonic() - _meta_t0_mono,
            hostname=_meta_hostname,
            session_name=None,
            measurement_quality="failed",
            domain_support="none",
            domains={},
            record_time_series=False,
        )
        payload = {"success": False, "error": error_msg, "meta": meta,
                   "command": command, "backend": _backend_descriptor()}
        payload.update(extra)
        return json.dumps(payload, indent=2)

    measurement_pairs: List[tuple] = []
    warmup_pairs: List[tuple] = []
    domain_runs: List[Dict[str, float]] = []

    def _collect_run(label: str, idx: int, total: int, into: List[tuple]):
        if not json_output:
            console.print(f"[dim]{label} {idx+1}/{total}[/dim]")
        energy_j, elapsed = backend.measure(command, timeout=timeout)
        if energy_j is not None and energy_j > 0:
            into.append((energy_j, elapsed))
            if isinstance(backend, _NEMBBackend):
                d = backend.get_last_domain_breakdown()
                if d and label == "Run":
                    domain_runs.append(d)
        else:
            into.append((None, elapsed))

    for i in range(warmup):
        if include_warmup:
            try:
                _collect_run("Warmup", i, warmup, warmup_pairs)
            except RuntimeError as e:
                if json_output: print(_emit_failure_meta(f"Warmup failed: {e}"))
                else: console.print(f"[red]Warmup failed: {e}[/red]")
                raise typer.Exit(1)
        else:
            if not json_output:
                console.print(f"[dim]Warmup {i+1}/{warmup}[/dim]")
            try:
                subprocess.run(command, capture_output=True, timeout=300,
                               stdin=_stdin())
            except subprocess.TimeoutExpired:
                if json_output: print(_emit_failure_meta("Warmup timed out"))
                else: console.print(f"[red]Warmup timed out[/red]")
                raise typer.Exit(1)

    for i in range(repeat):
        try:
            _collect_run("Run", i, repeat, measurement_pairs)
        except RuntimeError as e:
            if json_output: print(_emit_failure_meta(str(e)))
            else: console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

    energy_valid_pairs = [(e, t) for (e, t) in measurement_pairs if e is not None]
    zero_energy_dropped = len(measurement_pairs) - len(energy_valid_pairs)
    energies = [e for (e, _) in energy_valid_pairs]
    times = [t for (_, t) in energy_valid_pairs]

    if not energies:
        msg = f"No energy data collected ({backend.name})"
        diag = ""
        if sys.platform == "linux":
            perms = check_energy_permissions()
            rapl = perms.get("rapl_cpu", {})
            if not rapl.get("accessible", False):
                diag = ". " + rapl.get("details", "")
        elif sys.platform == "darwin":
            diag = ". powermetrics requires sudo: run 'sudo codegreen run ...'"
        if isinstance(backend, _TimeOnlyBackend):
            diag = ". No energy sensor found (need NEMB library, or perf on Linux)"
        msg += diag
        if json_output:
            t_only = [t for (_, t) in measurement_pairs]
            t_mean = sum(t_only) / len(t_only) if t_only else 0
            print(_emit_failure_meta(msg, duration_s={"mean": t_mean},
                                     runs={"attempted": len(measurement_pairs),
                                           "energy_valid": 0,
                                           "zero_energy_dropped": zero_energy_dropped}))
        else:
            console.print(f"[red]{msg}[/red]")
            if measurement_pairs:
                t_stats = StatisticalAnalysis.summarize([t for (_, t) in measurement_pairs])
                console.print(f"[bold]Time:[/bold] {t_stats.mean:.4f} s +/- {t_stats.std:.4f} s")
        raise typer.Exit(1)

    e_stats = StatisticalAnalysis.summarize(energies)
    pre_iqr_n = len(energies)
    surviving = set(range(pre_iqr_n))
    iqr_outliers_removed = e_stats.outliers_removed
    times_paired = times
    t_stats = StatisticalAnalysis.summarize(times_paired)

    avg_domains: Dict[str, float] = {}
    domain_active_count: Dict[str, int] = {}
    if domain_runs:
        all_keys: set = set()
        for dr in domain_runs: all_keys.update(dr.keys())
        for d in all_keys:
            vals = [dr.get(d, 0.0) for dr in domain_runs]
            avg_domains[d] = sum(vals) / len(domain_runs)
            domain_active_count[d] = sum(1 for v in vals if v > 0)

    per_run_power = [e / t for (e, t) in energy_valid_pairs if t > 0]
    p_stats = StatisticalAnalysis.summarize(per_run_power) if per_run_power else None
    cv = (e_stats.std / e_stats.mean * 100) if e_stats.mean > 0 else 0.0
    avg_power = p_stats.mean if p_stats else 0.0

    avg_domains_power: Dict[str, float] = {}
    if avg_domains and t_stats.mean > 0:
        avg_domains_power = {d: j / t_stats.mean for d, j in avg_domains.items()}

    budget_exceeded = budget is not None and e_stats.mean > budget

    if json_output:
        _meta_ended_at = datetime.now(_tz.utc).isoformat(timespec="microseconds")
        _meta_ended_at_local = _iso_local_now()
        meta_obj = _build_meta(
            run_id=_meta_run_id,
            started_at_iso=_meta_started_at,
            ended_at_iso=_meta_ended_at,
            started_at_local_iso=_meta_started_at_local,
            ended_at_local_iso=_meta_ended_at_local,
            duration_total_s=time.monotonic() - _meta_t0_mono,
            hostname=_meta_hostname,
            session_name=None,
            measurement_quality="ok" if energies else "no_energy",
            domain_support="full" if avg_domains else ("scalar_only" if energies else "none"),
            domains=avg_domains,
            record_time_series=False,
            extras={"include_warmup": bool(include_warmup), "warmup_runs_configured": warmup},
        )
        out = {
            "meta": meta_obj,
            "command": command,
            "backend": _backend_descriptor(),
            "runs": {
                "attempted": len(measurement_pairs),
                "energy_valid": len(energies),
                "iqr_outliers_removed": iqr_outliers_removed,
                "zero_energy_dropped": zero_energy_dropped,
                "warmup_included_in_stats": bool(include_warmup),
                "warmup_runs": len(warmup_pairs) if include_warmup else 0,
                "measurement_runs": repeat,
            },
            "energy_j": {
                "mean": e_stats.mean, "std": e_stats.std, "min": e_stats.min, "max": e_stats.max,
                "ci95_lower": e_stats.ci95_lower, "ci95_upper": e_stats.ci95_upper,
                "cv_percent_across_runs": round(cv, 2),
            },
            "duration_s": {
                "mean": t_stats.mean, "std": t_stats.std, "min": t_stats.min, "max": t_stats.max,
                "outliers_removed": t_stats.outliers_removed,
            },
            "power_w": {
                "mean": (round(p_stats.mean, 4) if p_stats else 0.0),
                "std":  (round(p_stats.std, 4) if p_stats else 0.0),
                "min":  (round(p_stats.min, 4) if p_stats else 0.0),
                "max":  (round(p_stats.max, 4) if p_stats else 0.0),
                "ci95_lower": (round(p_stats.ci95_lower, 4) if p_stats else 0.0),
                "ci95_upper": (round(p_stats.ci95_upper, 4) if p_stats else 0.0),
                "computation": "mean_of_per_run_e_over_t",
            },
            "budget_exceeded": budget_exceeded,
        }
        if budget is not None:
            out["budget_j"] = budget
        if avg_domains:
            out["domains"] = {d: round(j, 6) for d, j in sorted(avg_domains.items(), key=lambda x: -x[1])}
            out["domains_power_w"] = {d: round(w, 4) for d, w in
                                      sorted(avg_domains_power.items(), key=lambda x: -x[1])}
        print(json.dumps(out, indent=2))
        if budget_exceeded:
            raise typer.Exit(1)
    else:
        ci_width = e_stats.ci95_upper - e_stats.ci95_lower
        ci_pct = (ci_width / e_stats.mean * 100) if e_stats.mean > 0 else 0

        if len(energies) < 3:
            quality, color = "N/A (need 3+ runs)", "dim"
        elif cv < 5:
            quality, color = "excellent", "green"
        elif cv < 15:
            quality, color = "good", "yellow"
        elif cv < 30:
            quality, color = "moderate", "bright_yellow"
        else:
            quality, color = "high noise", "red"

        console.print(f"\n[bold]Energy:[/bold] {e_stats.mean:.4f} J +/- {e_stats.std:.4f} J")
        console.print(f"  Range: [{e_stats.min:.4f} .. {e_stats.max:.4f}] J")
        console.print(f"  CI95:  [{e_stats.ci95_lower:.4f}, {e_stats.ci95_upper:.4f}] J ({ci_pct:.1f}% width)")
        console.print(f"  CV:    [{color}]{cv:.1f}% ({quality})[/{color}]")
        console.print(f"[bold]Time:[/bold]   {t_stats.mean:.4f} s +/- {t_stats.std:.4f} s")
        console.print(f"[bold]Power:[/bold]  {e_stats.mean / t_stats.mean:.2f} W (avg)")
        runs_note = f"  Runs: {len(energies)}, Outliers removed: {e_stats.outliers_removed}"
        if include_warmup and warmup > 0:
            runs_note += f" (includes {warmup} warmup)"
        console.print(runs_note)

        if avg_domains:
            console.print(f"\n[bold]Domain Breakdown (avg of {len(domain_runs)} runs):[/bold]")
            max_j = max(avg_domains.values()) if avg_domains else 1
            for domain, joules in sorted(avg_domains.items(), key=lambda x: -x[1]):
                if joules <= 0: continue
                bar_len = min(20, int(joules / max_j * 20)) if max_j > 0 else 0
                bar = "[cyan]" + "=" * bar_len + "[/cyan]" + " " * (20 - bar_len)
                power = joules / t_stats.mean if t_stats.mean > 0 else 0
                console.print(f"  {domain:<25} {joules:>8.4f} J  {power:>7.2f} W  {bar}")

        if cv > 20:
            console.print(f"[yellow]  Tip: high variance -- try --repeat 30 or reduce background load[/yellow]")
        if budget is not None:
            if e_stats.mean > budget:
                console.print(f"[red]BUDGET EXCEEDED: {e_stats.mean:.4f}J > {budget}J[/red]")
                raise typer.Exit(1)
            else:
                console.print(f"[green]Within budget: {e_stats.mean:.4f}J <= {budget}J[/green]")


class _EnergyBackend:
    """Base class for CLI energy measurement backends.
    Open/closed: add new hardware support by subclassing and appending to _ENERGY_BACKENDS.
    No file I/O during measurement -- all data via in-memory APIs or pipes."""
    name: str = "unknown"
    priority: int = 0  # higher = preferred
    _quiet: bool = False
    _stdin_fh = None  # file handle bound by --stdin; rewound per measurement
    def _stdin(self):
        if self._stdin_fh is None:
            return None
        self._stdin_fh.seek(0)
        return self._stdin_fh
    def is_available(self) -> bool: return False
    def measure(self, command: list, timeout: Optional[int] = None) -> tuple:
        """Returns (energy_joules or None, elapsed_seconds)."""
        raise NotImplementedError
    def wrap_command(self, cmd_str: str, energy_file: str, checkpoint_file: str) -> str:
        """Wrap a shell command for energy + checkpoint capture (project mode)."""
        return f"bash -c '{cmd_str} 2>{checkpoint_file}'"
    def parse_energy(self, energy_file: str) -> float:
        """Parse energy from output file (project mode only). Returns joules or 0."""
        return 0.0
    def run_project(self, cmd_str: str, cwd: str, checkpoint_file: str, env: dict) -> tuple:
        """Run a project-mode command with stderr sent to checkpoint_file.
        Returns (CompletedProcess with bytes output, energy_joules, wall_seconds)."""
        energy_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False).name
        try:
            start = time.perf_counter()
            result = subprocess.run(self.wrap_command(cmd_str, energy_file, checkpoint_file),
                                    shell=True, cwd=cwd, env=env, capture_output=True)
            wall = time.perf_counter() - start
            return result, self.parse_energy(energy_file), wall
        finally:
            os.unlink(energy_file)


class _NEMBBackend(_EnergyBackend):
    """In-process NEMB measurement via ctypes. Zero file I/O during measurement.
    Uses the same background polling + ring buffer architecture as fine-grained mode."""
    name = "NEMB (native energy measurement)"
    priority = 100
    _lib = None
    _quiet = False

    def _load(self):
        if self._lib is not None:
            return self._lib
        import ctypes
        pkg_root = Path(__file__).resolve().parent.parent
        search_dirs = [pkg_root / "lib", pkg_root.parent / "lib", pkg_root.parent / "build" / "lib"]
        for d in search_dirs:
            if not d.is_dir():
                continue
            for p in d.glob("*codegreen-nemb*"):
                if p.suffix in (".so", ".dylib", ".dll"):
                    try:
                        self._lib = ctypes.CDLL(str(p))
                        return self._lib
                    except OSError:
                        pass
        self._lib = False
        return False

    def is_available(self) -> bool:
        lib = self._load()
        if not lib:
            return False
        import ctypes
        try:
            lib.nemb_initialize.restype = ctypes.c_int
            return lib.nemb_initialize() == 1
        except Exception:
            return False

    def measure(self, command: list, timeout: Optional[int] = None) -> tuple:
        import ctypes, subprocess, time
        lib = self._load()
        lib.nemb_start_session.restype = ctypes.c_uint64
        lib.nemb_start_session.argtypes = [ctypes.c_char_p]
        lib.nemb_stop_session.restype = ctypes.c_int
        lib.nemb_stop_session.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]

        sid = lib.nemb_start_session(b"run")
        start = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=self._quiet,
                                    timeout=timeout, stdin=self._stdin())
            elapsed = time.perf_counter() - start
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - start
            energy, power = ctypes.c_double(0), ctypes.c_double(0)
            lib.nemb_stop_session(sid, ctypes.byref(energy), ctypes.byref(power))
            raise RuntimeError(f"Command timed out after {timeout}s")

        energy, power = ctypes.c_double(0), ctypes.c_double(0)
        ok = lib.nemb_stop_session(sid, ctypes.byref(energy), ctypes.byref(power))
        if result.returncode != 0:
            stderr = ""
            if self._quiet and result.stderr:
                stderr = result.stderr.decode(errors="replace").strip()[:300]
            raise RuntimeError(f"Command failed (exit {result.returncode}){': ' + stderr if stderr else ''}")
        self._last_domains = {}
        try:
            buf = ctypes.create_string_buffer(4096)
            lib.nemb_get_domain_energy_json.restype = ctypes.c_int
            lib.nemb_get_domain_energy_json.argtypes = [ctypes.c_char_p, ctypes.c_int]
            n = lib.nemb_get_domain_energy_json(buf, 4096)
            if n > 0:
                self._last_domains = json.loads(buf.value.decode())
        except Exception:
            pass
        return (energy.value if ok and energy.value > 0 else None, elapsed)

    def get_last_domain_breakdown(self) -> dict:
        return getattr(self, '_last_domains', {})

    def run_project(self, cmd_str: str, cwd: str, checkpoint_file: str, env: dict) -> tuple:
        # Whole-run energy from an in-process NEMB session spanning the child,
        # the same path `codegreen run` uses; there is no energy file to parse.
        import ctypes
        lib = self._load()
        lib.nemb_start_session.restype = ctypes.c_uint64
        lib.nemb_start_session.argtypes = [ctypes.c_char_p]
        lib.nemb_stop_session.restype = ctypes.c_int
        lib.nemb_stop_session.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        energy, power = ctypes.c_double(0), ctypes.c_double(0)
        sid = lib.nemb_start_session(b"project")
        start = time.perf_counter()
        try:
            result = subprocess.run(self.wrap_command(cmd_str, "", checkpoint_file),
                                    shell=True, cwd=cwd, env=env, capture_output=True)
        finally:
            wall = time.perf_counter() - start
            ok = lib.nemb_stop_session(sid, ctypes.byref(energy), ctypes.byref(power))
        if not ok or energy.value <= 0:
            raise RuntimeError(f"NEMB session returned no energy for project run ({wall:.2f}s)")
        return result, energy.value, wall


class _PerfBackend(_EnergyBackend):
    name = "perf (Linux RAPL)"
    priority = 50
    def is_available(self) -> bool:
        import shutil
        return sys.platform == "linux" and shutil.which("perf") is not None
    def _events(self) -> str:
        import subprocess
        events = "power/energy-pkg/"
        try:
            r = subprocess.run(["perf", "list", "power"], capture_output=True, text=True, timeout=5)
            if "energy-ram" in r.stdout:
                events += ",power/energy-ram/"
        except Exception:
            pass
        return events
    def measure(self, command: list, timeout: Optional[int] = None) -> tuple:
        import subprocess, time, tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            pf = f.name
        try:
            full = ["perf", "stat", "-e", self._events(), "-o", pf, "--"] + command
            start = time.perf_counter()
            try:
                result = subprocess.run(full, capture_output=self._quiet,
                                        timeout=timeout, stdin=self._stdin())
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Command timed out after {timeout}s")
            if result.returncode != 0:
                raise RuntimeError(f"Command failed (exit {result.returncode})")
            elapsed = time.perf_counter() - start
            energy = self.parse_energy(pf)
            return (energy if energy > 0 else None, elapsed)
        finally:
            try: os.unlink(pf)
            except OSError: pass
    def wrap_command(self, cmd_str: str, perf_file: str, checkpoint_file: str) -> str:
        return f"perf stat -e {self._events()} -o {perf_file} -- bash -c '{cmd_str} 2>{checkpoint_file}'"
    def parse_energy(self, perf_file: str) -> float:
        import re
        try:
            content = open(perf_file).read()
            total = 0.0
            for m in re.finditer(r'([\d.,]+)\s+Joules', content):
                total += float(m.group(1).replace(',', ''))
            return total
        except Exception:
            return 0.0


class _PowermetricsBackend(_EnergyBackend):
    name = "powermetrics (macOS IOReport)"
    priority = 30
    def is_available(self) -> bool:
        import shutil
        return sys.platform == "darwin" and shutil.which("powermetrics") is not None
    def measure(self, command: list, timeout: Optional[int] = None) -> tuple:
        import subprocess, time, tempfile, os, re
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            pm_file = f.name
        proc = None
        try:
            proc = subprocess.Popen(
                ["sudo", "-n", "powermetrics", "--samplers", "cpu_power",
                 "-i", "100", "-o", pm_file],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            time.sleep(0.2)
            # Check if sudo failed immediately (password required)
            if proc.poll() is not None:
                stderr = (proc.stderr.read() or b"").decode(errors="replace").strip()
                if "password" in stderr.lower() or proc.returncode != 0:
                    raise RuntimeError("powermetrics requires sudo. Run: sudo codegreen run ...")
            start = time.perf_counter()
            try:
                result = subprocess.run(command, capture_output=self._quiet,
                                        timeout=timeout, stdin=self._stdin())
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Command timed out after {timeout}s")
            elapsed = time.perf_counter() - start
            if result.returncode != 0:
                raise RuntimeError(f"Command failed (exit {result.returncode})")
            time.sleep(0.3)
            proc.terminate()
            try: proc.wait(timeout=5)
            except: proc.kill()
            mw_samples = []
            try:
                for line in open(pm_file):
                    if "Combined Power" in line or "CPU Power" in line:
                        m = re.search(r'(\d+)\s*mW', line)
                        if m: mw_samples.append(int(m.group(1)))
            except Exception:
                pass
            if mw_samples:
                return ((sum(mw_samples) / len(mw_samples) / 1000.0) * elapsed, elapsed)
            return (None, elapsed)
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=3)
                except: proc.kill()
            try: os.unlink(pm_file)
            except OSError: pass
    def wrap_command(self, cmd_str: str, perf_file: str, checkpoint_file: str) -> str:
        return f"bash -c '{cmd_str} 2>{checkpoint_file}'"


class _TimeOnlyBackend(_EnergyBackend):
    name = "time-only (no energy)"
    def is_available(self) -> bool: return True
    def measure(self, command: list, timeout: Optional[int] = None) -> tuple:
        import subprocess, time
        start = time.perf_counter()
        result = subprocess.run(command, capture_output=self._quiet,
                                timeout=timeout, stdin=self._stdin())
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            raise RuntimeError(f"Command failed (exit {result.returncode})")
        return (None, elapsed)


_ENERGY_BACKENDS = [_NEMBBackend(), _PerfBackend(), _PowermetricsBackend(), _TimeOnlyBackend()]

def _get_energy_backend() -> _EnergyBackend:
    """Auto-detect best available energy backend, sorted by priority.
    NEMB (100) > perf (50) > powermetrics (30) > time_only (0).
    Extensible: add new backends to _ENERGY_BACKENDS."""
    for b in sorted(_ENERGY_BACKENDS, key=lambda x: x.priority, reverse=True):
        if b.is_available():
            return b
    return _TimeOnlyBackend()


def _load_language_config(language: str) -> dict:
    """Load language config JSON. Single source of truth for language-specific settings."""
    config_dir = Path(__file__).resolve().parent.parent / "instrumentation" / "configs"
    config_file = config_dir / f"{language}.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {}


def _get_runtime_source_dir() -> Path:
    """Get path to language_runtimes directory."""
    return Path(__file__).resolve().parent.parent / "instrumentation" / "language_runtimes"


def _inject_project_runtime(
    proj_cfg: dict, backups: dict, project_dir: Path
) -> list:
    """Inject runtime files into project based on language config.
    Returns list of created files/dirs for cleanup."""
    rt_cfg = proj_cfg.get("runtime_injection", {})
    rt_type = rt_cfg.get("type", "")
    created = []

    if rt_type == "source_copy":
        # Copy actual runtime source files from language_runtimes/ into project
        rt_source_dir = _get_runtime_source_dir() / rt_cfg.get("source_dir", "")
        target_rel = rt_cfg.get("target_relative_path", "")
        files = rt_cfg.get("files", [])

        # Find source roots from instrumented files (config-driven markers)
        src_roots = _find_source_roots(backups.keys(), proj_cfg)
        for src_root in src_roots:
            target_dir = src_root / target_rel
            target_dir.mkdir(parents=True, exist_ok=True)
            for fname in files:
                src = rt_source_dir / fname
                dst = target_dir / fname
                if src.exists():
                    import shutil
                    shutil.copy2(str(src), str(dst))
                    created.append(dst)
            # Track dirs for cleanup (deepest first)
            p = target_dir
            while p != src_root:
                created.append(p)
                p = p.parent

    elif rt_type == "pythonpath":
        rt_src = _get_runtime_path()
        module = rt_cfg.get("module", "codegreen_runtime")
        if rt_src:
            rt_dest = project_dir / f"{module}.py"
            if not rt_dest.exists():
                import shutil
                shutil.copy2(str(rt_src / f"{module}.py"), str(rt_dest))
                created.append(rt_dest)

    return created


_NEMB_RESULT_START = "--- CODEGREEN_RESULT_START ---"
_NEMB_RESULT_END = "--- CODEGREEN_RESULT_END ---"


def _stderr_checkpoint_events(path: str, func_data: dict):
    """Yield `CG_CP|type|name|id|ts|energy_uj|tid` events from a checkpoint file.
    Pre-aggregated `CG_CP_SUM|tid|name|calls|incl_uj|excl_uj|time_ns` records
    (Java standalone runtime) are folded straight into func_data."""
    with open(path) as cf:
        for line in cf:
            parts = line.rstrip("\n").split("|")
            if parts[0] == "CG_CP_SUM" and len(parts) >= 7:
                d = func_data.setdefault(parts[2], {"inclusive_uj": 0, "exclusive_uj": 0, "time_ns": 0, "calls": 0})
                d["calls"] += int(parts[3])
                d["inclusive_uj"] += int(parts[4])
                d["exclusive_uj"] += int(parts[5])
                d["time_ns"] += int(parts[6])
            elif parts[0] == "CG_CP" and len(parts) >= 6:
                yield parts[1], parts[2], parts[3], int(parts[4]), int(parts[5]), parts[6] if len(parts) > 6 else "0"


def _nemb_checkpoint_events(stdout: str, known_ids) -> list:
    """Per-event checkpoints from the NEMB result block on stdout (C/C++/Python runtimes).
    Markers are `type:name:id#inv_N_t<thread>` with cumulative joules. The language
    runtime and NEMB's own atexit may both print the same data, so the largest block
    is used, never a sum. Names may contain ':' (C++ scopes), so the id is the
    suffix that matches an instrumented checkpoint id."""
    blocks = [json.loads(chunk.split(_NEMB_RESULT_END, 1)[0]) for chunk in stdout.split(_NEMB_RESULT_START)[1:]]
    measurements = max((b.get("measurements", []) for b in blocks), key=len, default=[])
    splits, events = {}, []
    for m in measurements:
        marker, sep, inv = m["checkpoint_id"].rpartition("#inv_")
        if not sep:
            raise ValueError(f"NEMB checkpoint without invocation suffix: {m['checkpoint_id']!r}")
        cp_type, _, rest = marker.partition(":")
        if rest not in splits:
            splits[rest] = next(((rest[:i], rest[i + 1:]) for i, c in enumerate(rest)
                                 if c == ":" and rest[i + 1:] in known_ids), rest.rpartition(":")[::2])
        name, cp_id = splits[rest]
        events.append((cp_type, name, cp_id, int(m["timestamp"]), round(m["joules"] * 1e6), inv.rpartition("_t")[2]))
    events.sort(key=lambda e: e[3])
    return events


def _device_sync_count(stdout: str) -> int:
    """Device synchronisations the Python runtime performed, from its result block."""
    return sum(json.loads(chunk.split(_NEMB_RESULT_END, 1)[0]).get("device_sync", {}).get("syncs", 0)
               for chunk in stdout.split(_NEMB_RESULT_START)[1:])


def _replay_checkpoint_events(events, func_data: dict) -> set:
    """Replay enter/exit events on per-thread call stacks into func_data
    (name -> inclusive_uj, exclusive_uj, time_ns, calls). Exits without a
    matching frame are ignored; abandoned inner frames are unwound. Returns the
    (name, checkpoint_id) pairs seen."""
    stacks, seen = {}, set()
    for cp_type, name, cp_id, ts, energy, tid in events:
        seen.add((name, cp_id))
        d = func_data.setdefault(name, {"inclusive_uj": 0, "exclusive_uj": 0, "time_ns": 0, "calls": 0})
        stack = stacks.setdefault(tid, [])
        if cp_type == "enter":
            stack.append([name, ts, energy, 0])
            continue
        if cp_type != "exit":
            continue
        idx = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == name), None)
        if idx is None:
            continue
        frame = stack[idx]
        del stack[idx:]
        dt, inclusive = ts - frame[1], energy - frame[2]
        if dt > 0 and inclusive >= 0:
            d["inclusive_uj"] += inclusive
            d["exclusive_uj"] += max(inclusive - frame[3], 0)
            d["time_ns"] += dt
            d["calls"] += 1
            if stack:
                stack[-1][3] += inclusive
    return seen


def _find_source_roots(file_paths, proj_cfg: dict) -> set:
    """Find source root directories from file paths using config-driven markers.
    Reads source_root_markers from project_config (e.g., ["src/main/java"] for Java).

    Fallback for flat single-file projects (e.g. CLBG, HeCBench kernels,
    one-off Python scripts) where no Maven/Gradle/SBT marker matches:
    use the directory containing the instrumented file as the root.
    Without this fallback, the runtime source-copy step is a no-op and
    the user's build_cmd fails with `cannot find symbol:
    variable CodeGreenStandaloneRuntime`."""
    markers = proj_cfg.get("source_root_markers", ["src"])
    roots = set()
    unmatched = []
    for f in file_paths:
        matched = False
        for marker in markers:
            marker_parts = marker.split("/")
            parts = Path(f).parts
            for i in range(len(parts) - len(marker_parts) + 1):
                if list(parts[i:i+len(marker_parts)]) == marker_parts:
                    roots.add(Path(*parts[:i+len(marker_parts)]))
                    matched = True
                    break
            if matched:
                break
        if not matched:
            unmatched.append(f)
    # Flat-layout fallback: every instrumented file whose path didn't
    # match any marker contributes its parent dir as a root. We do this
    # only when NO file matched any marker (so well-formed Maven/Gradle
    # repos that have one stray script don't accidentally get an
    # extra root).
    if not roots and unmatched:
        for f in unmatched:
            roots.add(Path(f).parent)
    return roots


def _rewrite_instrumented_for_standalone(code: str, rt_cfg: dict) -> str:
    """Rewrite instrumented code to use standalone runtime instead of JNI runtime."""
    rewrites = rt_cfg.get("import_rewrite", {})
    if rewrites:
        code = code.replace(rewrites.get("from", ""), rewrites.get("to", ""))
    rewrites = rt_cfg.get("checkpoint_rewrite", {})
    if rewrites:
        code = code.replace(rewrites.get("from", ""), rewrites.get("to", ""))
    return code


@app.command("monitor", rich_help_panel="Measurement")
def monitor_energy(
    duration: Annotated[Optional[float], typer.Option("--duration", "-d", help="Stop after N seconds (default: run until Ctrl-C)")] = None,
    interval: Annotated[Optional[int], typer.Option("--interval", "-i", help="Sample period in ms (config floor enforced)")] = None,
    pid: Annotated[Optional[int], typer.Option("--pid", "-p", help="Attribute energy to this process via CPU% share")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Stream samples as JSON-lines to this file")] = None,
    rotate_mb: Annotated[Optional[int], typer.Option("--rotate-mb", help="Rotate JSONL when it exceeds N MB (0 = disabled)")] = None,
    max_in_memory: Annotated[Optional[int], typer.Option("--max-in-memory", help="Bound in-memory sample deque (0 = drop when -o set)")] = None,
    max_labels: Annotated[Optional[int], typer.Option("--max-labels", help="Cap distinct annotation labels; overflow collapses into __other__ bucket (0 = unlimited)")] = None,
    listen_socket: Annotated[Optional[str], typer.Option("--listen-on-socket", help="Bind a UDS for request-annotation events ('default' = per-user path, see annotate_request)")] = None,
    attribution_mode: Annotated[Optional[str], typer.Option("--attribution-mode", help="PID share backend: auto|cgroup_v2|cgroup_v1|cpu_percent (default: auto)")] = None,
    exporter: Annotated[Optional[List[str]], typer.Option("--exporter", help="Enable a telemetry exporter sink (repeatable). Known: otlp, prometheus. Requires `pip install codegreen\\[otlp]` for OTLP or `codegreen\\[prometheus]` for Prometheus.")] = None,
    otlp_endpoint: Annotated[Optional[str], typer.Option("--otlp-endpoint", help="OTLP/gRPC collector endpoint (overrides monitor.exporters.otlp.endpoint)")] = None,
    prometheus_port: Annotated[Optional[int], typer.Option("--prometheus-port", help="Prometheus /metrics port (overrides monitor.exporters.prometheus.port). 0 = ephemeral.")] = None,
    prometheus_listen_addr: Annotated[Optional[str], typer.Option("--prometheus-listen-addr", help="Prometheus bind address (overrides monitor.exporters.prometheus.listen_addr). Default 127.0.0.1; non-loopback emits a runtime warning.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Print final summary as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress live sample output")] = False,
):
    """[bold]Continuously sample[/bold] system energy without launching a workload.

    Use this for already-running services (web servers, daemons) where the
    Session API cannot be embedded. Samples cumulative energy from the NEMB
    backend at fixed intervals; optionally attributes a share to a target PID
    or per-request via the UDS annotation channel.

    [bold]Examples:[/bold]
    - [cyan]codegreen monitor -d 30[/cyan] - sample for 30 seconds
    - [cyan]codegreen monitor --pid 1234 -o energy.jsonl[/cyan] - attribute to PID
    - [cyan]codegreen monitor -i 1000 -d 3600[/cyan] - 1Hz sampling for 1 hour
    - [cyan]codegreen monitor --listen-on-socket default -o energy.jsonl[/cyan]
      - accept request annotations from a Flask/Django/FastAPI middleware
    - [cyan]codegreen monitor --max-labels 1000[/cyan]
      - cap distinct labels at 1000; overflow collapses to `__other__`

    [bold]Signals:[/bold] SIGINT/SIGTERM stop cleanly (summary flushed).
    SIGHUP re-reads `monitor.*` from config.json and hot-applies
    `--interval`, `--rotate-mb`, `--max-in-memory`, `--max-labels`
    without dropping in-flight annotations or the open JSONL position.
    """
    from codegreen import Monitor
    import signal

    def _fail(msg: str) -> None:
        rec = {"success": False, "error": msg}
        if json_output:
            print(json.dumps(rec), file=sys.stderr)
        else:
            print(f"error: {msg}", file=sys.stderr)
        raise typer.Exit(1)

    exporters_req = list(exporter) if exporter else None
    exporter_overrides: Dict[str, Dict[str, Any]] = {}
    if otlp_endpoint:
        exporter_overrides["otlp"] = {"endpoint": otlp_endpoint}
        if not exporters_req or "otlp" not in exporters_req:
            _fail("--otlp-endpoint requires --exporter otlp")
    if prometheus_port is not None or prometheus_listen_addr is not None:
        if not exporters_req or "prometheus" not in exporters_req:
            _fail("--prometheus-port/--prometheus-listen-addr require --exporter prometheus")
        prom_over: Dict[str, Any] = {}
        if prometheus_port is not None:
            prom_over["port"] = int(prometheus_port)
        if prometheus_listen_addr is not None:
            prom_over["listen_addr"] = str(prometheus_listen_addr)
        exporter_overrides["prometheus"] = prom_over
    try:
        mon = Monitor(interval_ms=interval, duration_s=duration, pid=pid,
                      output_file=str(output) if output else None,
                      rotate_mb=rotate_mb, max_samples_in_memory=max_in_memory,
                      listen_socket_path=listen_socket,
                      attribution_mode=attribution_mode,
                      max_labels=max_labels,
                      exporters=exporters_req,
                      exporter_overrides=exporter_overrides or None)
    except (ValueError, RuntimeError) as e:
        _fail(str(e))

    def _on_sigint(signum, frame):
        mon._stop_evt.set()
    def _on_sighup(signum, frame):
        mon.request_reload()
    signal.signal(signal.SIGINT, _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _on_sighup)

    try:
        mon.start()
    except (ValueError, RuntimeError) as e:
        _fail(str(e))
    eff_interval = int(mon._interval_s * 1000)
    if not quiet and not json_output:
        console.print(f"[green]Monitoring[/green] (interval={eff_interval}ms"
                      + (f", duration={duration}s" if duration else ", press Ctrl-C to stop")
                      + (f", pid={pid}" if pid else "")
                      + (f", listen={listen_socket}" if listen_socket else "") + ")")

    if not quiet and not json_output:
        last_n = 0
        try:
            while not mon._stop_evt.is_set() and (mon._thread and mon._thread.is_alive()):
                time.sleep(min(1.0, mon._interval_s * 2))
                cur = mon._samples_count
                if cur > last_n and mon._samples:
                    s = mon._samples[-1]
                    extra = f" cpu={s.get('proc_cpu_percent','-')}%" if pid else ""
                    console.print(f"  t={s['t']:>6.1f}s  dJ={s['joules_delta']:>7.2f}  W={s['watts']:>6.1f}{extra}")
                    last_n = cur
        except KeyboardInterrupt:
            mon._stop_evt.set()
    else:
        if mon._thread:
            mon._thread.join()

    summary = mon.stop()
    if json_output:
        print(json.dumps({"success": True, **summary}))
    else:
        console.print("\n[bold]Summary[/bold]")
        console.print(f"  duration: {summary['duration_s']:.2f} s")
        console.print(f"  total energy: {summary['total_joules']:.3f} J ({summary['total_joules']/3600.0:.4f} Wh)")
        console.print(f"  avg power: {summary['avg_watts']:.2f} W")
        console.print(f"  samples: {summary['samples']}")
        if pid:
            backend = summary.get("attribution_backend") or "cpu_percent"
            console.print(f"  pid {pid} attributed: {summary['proc_attributed_joules']:.3f} J [backend={backend}]")
        if summary.get('terminated_reason'):
            console.print(f"  [yellow]terminated: {summary['terminated_reason']}[/yellow]")
        if summary.get("per_label"):
            console.print(f"  [bold]Per-label[/bold] ({len(summary['per_label'])} groups):")
            for name, b in summary["per_label"].items():
                console.print(f"    {name:30s} n={b['count']:>5d} J={b['joules_total']:>8.3f} "
                              f"p50={b['latency_ms_p50']:>6.1f}ms p95={b['latency_ms_p95']:>6.1f}ms")
        if output:
            console.print(f"  samples written: [cyan]{output}[/cyan]")


def _remove_injected(path: Path) -> None:
    """Remove an injected runtime file or empty dir, and a Python module's
    bytecode caches (__pycache__/<stem>.*.pyc): importing the injected
    runtime writes one, which outlived the .py it came from."""
    if path.is_file():
        path.unlink()
        if path.suffix == ".py":
            for pyc in (path.parent / "__pycache__").glob(f"{path.stem}.*.pyc"):
                pyc.unlink()
    elif path.is_dir() and not any(path.iterdir()):
        path.rmdir()


@app.command("project", rich_help_panel="Measurement")
def project_energy(
    language: Annotated[Language, typer.Argument(help="Project language")],
    project_dir: Annotated[Path, typer.Argument(help="Project root directory")],
    build_cmd: Annotated[str, typer.Option("--build-cmd", "-b", help="Build command (e.g., 'mvn package -DskipTests')")] = "",
    run_cmd: Annotated[str, typer.Option("--run-cmd", "-r", help="Run command (e.g., 'java -jar target/benchmarks.jar')")] = "",
    source_glob: Annotated[Optional[List[str]], typer.Option("--source-glob", "-s", help="Source file glob pattern (repeatable)")] = None,
    granularity: Annotated[Granularity, typer.Option("--granularity", "-g", help="Instrumentation level")] = Granularity.fine,
    cores: Annotated[str, typer.Option("--cores", help="CPU cores for taskset (e.g., '0-7')")] = "",
    repeat: Annotated[int, typer.Option("--repeat", "-n", help="Measurement repetitions")] = 1,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_cleanup: Annotated[bool, typer.Option("--no-cleanup", help="Keep instrumented files")] = False,
    output_dir: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output directory for results")] = None,
    sync_device: Annotated[str, typer.Option("--sync-device", help=(
        "Accelerator to synchronise at every probe (python: cuda). Kernel launches are asynchronous, so without this "
        "a frame's interval covers launch time only and GPU energy lands outside every function. With it, "
        "torch.cuda.synchronize() runs before each enter/exit timestamp, so a frame owns the device work it launched. "
        "Costs one device drain per probe (no CPU/GPU overlap): wall time and total energy of the profiled run differ "
        "from an unsynchronised run. Fails if no synchronisation ran. Off by default."))] = "",
    min_attribution_pct: Annotated[float, typer.Option("--min-attribution-pct", help=(
        "Floor for attribution_pct (exclusive function energy / total run energy). Below it the result carries an "
        "attribution_warning: per-function shares are relative to the attributed energy only and are not meaningful."))] = 25.0,
):
    """Profile a project's energy consumption with per-function attribution.

    Three-phase workflow:
    1. DISCOVER: Find and analyze all source files, identify instrumentation points.
    2. INSTRUMENT + BUILD: Instrument code, inject runtime, build with project's build system.
    3. MEASURE: Run benchmark, collect per-function energy via checkpoints.

    Examples:
    - codegreen project java ./my-project --build-cmd "mvn package -DskipTests"
      --run-cmd "java -jar target/benchmarks.jar" --cores 0-7
    - codegreen project java . -b "./gradlew build -x test"
      -r "java -jar jmh/build/libs/benchmarks.jar '.*MyBench.*' -wi 10 -i 50 -f 1"
    - codegreen project python ./src --run-cmd "python main.py" --granularity fine
    """
    import subprocess, time, re, shutil, glob as globmod, tempfile

    project_dir = project_dir.resolve()
    if not project_dir.exists():
        console.print(f"[red]Project directory not found: {project_dir}[/red]")
        raise typer.Exit(1)

    # Load project config from language JSON config (config-driven, not hardcoded)
    _lang_config = _load_language_config(language.value)
    proj_cfg = _lang_config.get("project_config", {})

    # Source discovery: use config patterns or CLI override
    source_patterns = list(source_glob) if source_glob else proj_cfg.get("source_patterns", [f"**/*{_lang_config['extensions'][0]}"])
    exclude_patterns = proj_cfg.get("exclude_patterns", [])

    # Build system auto-detection from config
    if not build_cmd:
        for bs_name, bs_cfg in proj_cfg.get("build_systems", {}).items():
            detect_file = bs_cfg.get("detect", "")
            if detect_file and (project_dir / detect_file).exists():
                build_cmd = bs_cfg.get("build_cmd", "")
                # Handle wrapper scripts (e.g., gradlew)
                wrapper = bs_cfg.get("wrapper", "")
                if wrapper and (project_dir / wrapper).exists():
                    build_cmd = build_cmd.replace(bs_name, f"./{wrapper}")
                if not json_output:
                    console.print(f"  Auto-detected build system: {bs_name} ({build_cmd})")
                break

    if not run_cmd:
        console.print("[red]--run-cmd is required (the command to execute the benchmark)[/red]")
        raise typer.Exit(1)
    if sync_device and sync_device not in proj_cfg.get("device_sync", []):
        console.print(f"[red]--sync-device {sync_device!r} unsupported for {language.value}; "
                      f"supported: {proj_cfg.get('device_sync', [])}[/red]")
        raise typer.Exit(1)

    if output_dir:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

    # ==========================================
    # PRE-CLEANUP: Detect and remove stale instrumented files from previous runs
    # ==========================================
    _backup_dir = project_dir / ".codegreen_backup"
    if (_backup_dir / "manifest.json").exists():
        manifest = json.loads((_backup_dir / "manifest.json").read_text())
        for fpath, copy in manifest.items():
            Path(fpath).write_text((_backup_dir / copy).read_text(encoding="utf-8"), encoding="utf-8")
        injected = (json.loads((_backup_dir / "runtime.json").read_text())
                    if (_backup_dir / "runtime.json").exists() else [])
        for rf in map(Path, reversed(injected)):
            _remove_injected(rf)
        shutil.rmtree(_backup_dir)
        if not json_output and manifest:
            console.print(f"  [yellow]Restored {len(manifest)} files left instrumented by an interrupted run[/yellow]")
    _stale_marker = project_dir / ".codegreen_instrumented"
    if _stale_marker.exists():
        stale_files = _stale_marker.read_text().strip().splitlines()
        if stale_files:
            restored = 0
            for fpath in stale_files:
                p = Path(fpath)
                if p.exists():
                    # Restore via git checkout if in a git repo, else skip
                    _git_restore = subprocess.run(
                        ["git", "checkout", "--", str(p)],
                        cwd=str(project_dir), capture_output=True, timeout=10)
                    if _git_restore.returncode == 0:
                        restored += 1
            if not json_output and restored:
                console.print(f"  [yellow]Cleaned {restored} stale instrumented files from previous run[/yellow]")
        _stale_marker.unlink(missing_ok=True)

    # Checked after the restore above: a missing backend must not leave an interrupted run's sources instrumented.
    if not _NEMBBackend().is_available():
        console.print("[red]codegreen project needs the NEMB native measurement library, which this install lacks "
                      "(a source build without cmake and a C++ compiler installs Python-only). Install a prebuilt "
                      "wheel or reinstall with cmake and a compiler available.[/red]")
        raise typer.Exit(1)

    # ==========================================
    # PHASE 1: DISCOVER
    # ==========================================
    if not json_output:
        console.print(f"\n[bold cyan]Phase 1: Discovering source files...[/bold cyan]")

    # Find source files: use Path.glob for each source pattern from config
    extensions = set(_lang_config.get("extensions", []))
    source_files_set = set()
    for pattern in source_patterns:
        # Globs are project-relative (Path.rglob rejects absolute patterns); an
        # absolute pattern inside the project is taken relative to it.
        if Path(pattern).is_absolute():
            if not Path(pattern).is_relative_to(project_dir.resolve()):
                console.print(f"[red]--source-glob {pattern} is outside {project_dir}[/red]")
                raise typer.Exit(1)
            pattern = str(Path(pattern).relative_to(project_dir.resolve()))
        clean = pattern.removeprefix("**/")
        for f in project_dir.rglob(clean):
            if f.is_file() and f.suffix in extensions:
                source_files_set.add(f)
    # An explicit --source-glob that matches nothing is a caller error; widening
    # to every source file would silently instrument (and slow) the whole project.
    if not source_files_set and source_glob:
        console.print(f"[red]--source-glob {list(source_glob)} matched no {language.value} files in {project_dir}[/red]")
        raise typer.Exit(1)
    if not source_files_set:
        for ext in extensions:
            source_files_set.update(project_dir.rglob(f"*{ext}"))

    # Exclude: check if any path component matches an exclude directory name.
    # Config patterns like "**/src/test/**" mean "exclude if 'test' appears as a
    # child of 'src' anywhere in the path." We extract the meaningful directory
    # segments and check if they appear consecutively in the file's path parts.
    import fnmatch as _fnmatch

    def _matches_exclude(filepath: Path, patterns: list) -> bool:
        rel_str = str(filepath.relative_to(project_dir))
        parts = filepath.relative_to(project_dir).parts
        for pat in patterns:
            # Extract consecutive directory segments from the pattern
            # e.g., "**/src/test/**" -> ["src", "test"]
            segments = [s for s in pat.replace("**", "").strip("/").split("/") if s and "*" not in s]
            if not segments:
                continue
            # Check if these segments appear consecutively in the path parts
            seg_len = len(segments)
            for i in range(len(parts) - seg_len + 1):
                if list(parts[i:i+seg_len]) == segments:
                    return True
        return False

    # Safety invariant: NEVER instrument files that define the checkpoint runtime.
    # Config-driven: instrumentation_config.runtime_guard_files lists filenames
    # (e.g., ["CodeGreenRuntime.java", "CodeGreenStandaloneRuntime.java"]) that must
    # never be instrumented. If instrumented, checkpoint() calls checkpoint() = infinite
    # recursion + stack overflow at runtime.
    # This guard works across all languages via config -- no hardcoded names.
    inst_cfg = _lang_config.get("instrumentation_config", {})
    _guard_filenames = set(inst_cfg.get("runtime_guard_files", []))

    def _is_runtime_file(filepath: Path) -> bool:
        """Returns True if this file is a CodeGreen runtime file (must not be instrumented)."""
        return filepath.name in _guard_filenames

    source_files = sorted(
        f for f in source_files_set
        if f.is_file()
        and not _matches_exclude(f, exclude_patterns)
        and not _is_runtime_file(f)
    )

    if not source_files:
        console.print(f"[red]No {language.value} source files found matching {source_patterns}[/red]")
        raise typer.Exit(1)

    if not json_output:
        console.print(f"  Found {len(source_files)} source files")

    # Analyze each file for instrumentation points
    from codegreen.instrumentation.language_engine import LanguageEngine
    engine = LanguageEngine()
    analysis_results = {}
    total_points = 0

    for src_file in source_files:
        try:
            code = src_file.read_text(encoding='utf-8', errors='replace')
            result = engine.analyze_code(code, language.value, filename=str(src_file))
            if result and result.instrumentation_points:
                points = result.instrumentation_points
                if granularity == Granularity.coarse:
                    points = _filter_main_entry_points(points, language.value)
                analysis_results[src_file] = {"code": code, "points": points, "result": result}
                total_points += len(points)
        except Exception:
            pass

    skipped_functions = [{"file": str(f), **s} for f, d in analysis_results.items()
                         for s in d["result"].metadata.get("skipped_functions", [])]
    if not json_output:
        console.print(f"  Instrumentable files: {len(analysis_results)}/{len(source_files)}")
        console.print(f"  Total instrumentation points: {total_points}")
        if skipped_functions:
            console.print(f"  [yellow]Not instrumented: {len(skipped_functions)} functions cannot hold a frame "
                          f"(first: {skipped_functions[0]['function']}: {skipped_functions[0]['reason']})[/yellow]")

    if not analysis_results:
        console.print("[red]No instrumentable code found[/red]")
        raise typer.Exit(1)

    # Build checkpoint_id prefix -> file_path map for accurate function-to-file resolution.
    # Each instrumentation point has a unique ID containing the method name and line number.
    # By mapping these IDs to files, we can resolve which file a checkpoint belongs to,
    # even when multiple files have methods with the same name (e.g., update()).
    checkpoint_id_to_file = {}  # checkpoint_id -> file_path
    func_file_map = {}  # function_name -> file_path (best guess for single-name functions)
    for src_file, data in analysis_results.items():
        for point in data["points"]:
            if point.type == "function_enter" and point.name:
                # The checkpoint_id format is: function_enter_{name}_{line}_{idx}
                checkpoint_id_to_file[point.id] = str(src_file)
                # Also build simple name->file map using both bare and qualified names
                func_file_map[point.name] = str(src_file)
                qn = point.metadata.get('qualified_name', point.name)
                if qn != point.name:
                    func_file_map[qn] = str(src_file)

    # ==========================================
    # PHASE 2: INSTRUMENT + BUILD
    # ==========================================
    if not json_output:
        console.print(f"\n[bold cyan]Phase 2: Instrumenting and building...[/bold cyan]")

    # Originals are kept in memory for the normal restore and copied under
    # .codegreen_backup/ before any file is rewritten, so a run killed before
    # its `finally` (SIGKILL, power loss) is restored at the next run with or
    # without git. SIGTERM/SIGHUP are turned into SystemExit so `finally` runs:
    # a campaign stopped mid-profiling left 52 instrumented RoaringBitmap files.
    import signal as _signal
    backups = {}
    runtime_files_created = []
    backup_dir = project_dir / ".codegreen_backup"
    backup_dir.mkdir(exist_ok=True)
    backup_manifest: Dict[str, str] = {}

    def _exit_on_signal(signum, frame):
        raise SystemExit(128 + signum)
    _prev_handlers = {s: _signal.signal(s, _exit_on_signal)
                      for s in (_signal.SIGTERM, getattr(_signal, "SIGHUP", _signal.SIGTERM))}

    try:
        # Instrument each file in-place
        instrumented_count = 0
        for src_file, data in analysis_results.items():
            # Double-check: skip if file defines a checkpoint class (defense in depth)
            if _is_runtime_file(src_file):
                continue
            try:
                _ns = data["result"].metadata.get("normalised_source", data["code"]) if hasattr(data.get("result"), "metadata") else data["code"]
                instrumented = engine.instrument_code(_ns, data["points"], language.value, pre_normalised_source=_ns)
                if instrumented and instrumented != _ns:
                    # Rewrite for standalone runtime if config specifies rewrites
                    rt_cfg = proj_cfg.get("runtime_injection", {})
                    instrumented = _rewrite_instrumented_for_standalone(instrumented, rt_cfg)
                    backups[src_file] = data["code"]
                    copy = backup_dir / f"{len(backup_manifest)}.orig"
                    copy.write_text(data["code"], encoding="utf-8")
                    backup_manifest[str(src_file)] = copy.name
                    (backup_dir / "manifest.json").write_text(json.dumps(backup_manifest))
                    src_file.write_text(instrumented, encoding='utf-8')
                    instrumented_count += 1
            except Exception as e:
                if not json_output:
                    console.print(f"  [yellow]Skip {src_file.name}: {e}[/yellow]")

        if not json_output:
            console.print(f"  Instrumented: {instrumented_count} files")

        # Write marker file listing instrumented files (for stale artifact cleanup)
        _stale_marker = project_dir / ".codegreen_instrumented"
        _stale_marker.write_text("\n".join(str(f) for f in backups.keys()))

        # Inject runtime module ONLY into source roots that have instrumented files
        runtime_files_created = _inject_project_runtime(proj_cfg, backups, project_dir)
        (backup_dir / "runtime.json").write_text(json.dumps([str(f) for f in runtime_files_created]))
        if not json_output and runtime_files_created:
            console.print(f"  Runtime files injected: {len([f for f in runtime_files_created if isinstance(f, Path) and f.is_file()])}")

        # Build the project
        if build_cmd:
            if not json_output:
                console.print(f"  Building: {build_cmd}")
            build_result = subprocess.run(
                build_cmd, shell=True, cwd=str(project_dir),
                capture_output=True, text=True, timeout=600)
            if build_result.returncode != 0:
                error_output = (build_result.stderr or "") + (build_result.stdout or "")
                console.print(f"[red]Build failed:[/red]")
                console.print(error_output[-500:])
                raise typer.Exit(1)
            if not json_output:
                console.print(f"  [green]Build successful[/green]")

        # ==========================================
        # PHASE 3: MEASURE
        # ==========================================
        if not json_output:
            console.print(f"\n[bold cyan]Phase 3: Measuring energy...[/bold cyan]")

        # Runtimes copied into the project cannot locate the NEMB library or the
        # package config relative to themselves; point them at the install.
        _, nemb_lib_dir = _get_c_runtime_paths()
        run_env = dict(os.environ)
        run_env.setdefault("CODEGREEN_INSTALL_DIR", str(Path(__file__).resolve().parents[2]))
        run_env.setdefault("CODEGREEN_LIB_PATH", str(nemb_lib_dir))
        run_env.pop("CODEGREEN_SYNC_DEVICE", None)
        if sync_device:
            run_env["CODEGREEN_SYNC_DEVICE"] = sync_device
        run_env["LD_LIBRARY_PATH"] = os.pathsep.join(
            filter(None, [str(nemb_lib_dir), os.environ.get("LD_LIBRARY_PATH")]))
        all_runs = []
        for run_idx in range(repeat):
            if not json_output and repeat > 1:
                console.print(f"  Run {run_idx+1}/{repeat}")

            # Construct the run command with optional taskset
            full_cmd = run_cmd
            if cores:
                full_cmd = f"taskset -c {cores} {full_cmd}"

            energy_backend = _get_energy_backend()
            checkpoint_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False).name
            # Java runtimes append their per-JVM aggregates here (every forked
            # JVM of the run, e.g. JMH forks); stderr carries per-event lines.
            sum_file = tempfile.NamedTemporaryFile(suffix='.sum', delete=False).name
            # Capture bytes: workloads like Mandelbrot write binary stdout.
            run_result, total_energy_j, wall_time = energy_backend.run_project(
                full_cmd, str(project_dir), checkpoint_file,
                {**run_env, "CG_CP_CHECKPOINT_FILE": sum_file})
            run_result.stdout = (run_result.stdout or b"").decode("utf-8", errors="replace")
            run_result.stderr = (run_result.stderr or b"").decode("utf-8", errors="replace")

            # Checkpoints arrive on stderr as CG_CP / CG_CP_SUM (Java standalone
            # runtime) or on stdout as the NEMB result block (C/C++/Python).
            func_data = {}  # name -> {inclusive_uj, exclusive_uj, time_ns, calls}
            try:
                seen = _replay_checkpoint_events(itertools.chain(
                    _stderr_checkpoint_events(checkpoint_file, func_data),
                    _stderr_checkpoint_events(sum_file, func_data)), func_data)
                if not func_data:
                    seen = _replay_checkpoint_events(
                        _nemb_checkpoint_events(run_result.stdout, checkpoint_id_to_file), func_data)
                stderr_tail = Path(checkpoint_file).read_text(errors="replace")[-500:]
            finally:
                if no_cleanup and output_dir:
                    shutil.copy2(checkpoint_file, str(output_dir / f"checkpoints_run{run_idx}.txt"))
                    shutil.copy2(sum_file, str(output_dir / f"checkpoints_run{run_idx}.sum"))
                os.unlink(checkpoint_file)
                os.unlink(sum_file)
            for cp_name, cp_id in seen:
                if cp_id in checkpoint_id_to_file:
                    func_file_map[cp_name] = checkpoint_id_to_file[cp_id]
            if not func_data:
                console.print(f"[red]No checkpoint records captured from {total_points} instrumented points "
                              f"(exit {run_result.returncode}).[/red]")
                console.print(stderr_tail)
                raise typer.Exit(1)
            if sync_device and not _device_sync_count(run_result.stdout):
                console.print(f"[red]--sync-device {sync_device}: no device synchronisation ran in the profiled run "
                              f"(the workload never initialised {sync_device}); attribution would be unsynchronised.[/red]")
                raise typer.Exit(1)

            # Compute per-function metrics (inclusive + exclusive)
            func_energy = {}
            total_inclusive = sum(d["inclusive_uj"] for d in func_data.values())
            total_exclusive = sum(d["exclusive_uj"] for d in func_data.values())
            for name, data in sorted(func_data.items(), key=lambda x: x[1]["exclusive_uj"], reverse=True):
                inc_j = data["inclusive_uj"] / 1e6
                exc_j = data["exclusive_uj"] / 1e6
                time_s = data["time_ns"] / 1e9
                calls = data["calls"]
                inc_pct = (data["inclusive_uj"] / total_inclusive * 100) if total_inclusive > 0 else 0
                exc_pct = (data["exclusive_uj"] / total_exclusive * 100) if total_exclusive > 0 else 0
                self_ratio = data["exclusive_uj"] / data["inclusive_uj"] if data["inclusive_uj"] > 0 else 0
                # Hotspot taxonomy (Types 1-5, see energy_agent_workflow.txt 9C)
                # CodeGreen detects Types 1, 2, 5 from its data alone.
                # Types 3, 4 need callgraph analysis (agent's job).
                median_epc = sorted(
                    [d["inclusive_uj"] / d["calls"] for d in func_data.values() if d["calls"] > 0]
                )
                med_epc = median_epc[len(median_epc) // 2] if median_epc else 1
                epc = data["inclusive_uj"] / calls if calls > 0 else 0
                efficiency_ratio = epc / med_epc if med_epc > 0 else 0
                verdict = _classify_hotspot_verdict(
                    self_ratio=self_ratio, inc_pct=inc_pct, exc_pct=exc_pct,
                    calls=calls, efficiency_ratio=efficiency_ratio,
                    config=load_config())
                func_energy[name] = {
                    "energy_j": round(inc_j, 6),
                    "energy_pct": round(inc_pct, 2),
                    "exclusive_energy_j": round(exc_j, 6),
                    "exclusive_pct": round(exc_pct, 2),
                    "self_ratio": round(self_ratio, 3),
                    "verdict": verdict,
                    "file": func_file_map.get(name, ""),
                    "wall_time_s": round(time_s, 6),
                    "avg_power_w": round(inc_j / time_s, 2) if time_s > 0 else 0,
                    "calls": calls,
                    "energy_per_call_uj": round(data["inclusive_uj"] / calls, 2) if calls > 0 else 0,
                }

            attribution_pct = round(total_exclusive / 1e6 / total_energy_j * 100, 1) if total_energy_j > 0 else 0
            all_runs.append({
                "run_idx": run_idx,
                "total_energy_j": round(total_energy_j, 4),
                "wall_time_s": round(wall_time, 3),
                "avg_power_w": round(total_energy_j / wall_time, 2) if wall_time > 0 else 0,
                "attributed_energy_j": round(total_exclusive / 1e6, 4),
                "exclusive_energy_j": round(total_exclusive / 1e6, 4),
                # Exclusive energy partitions the run; inclusive double-counts nested calls.
                "attribution_pct": attribution_pct,
                "attribution_warning": None if attribution_pct >= min_attribution_pct else {
                    "code": "LOW_ATTRIBUTION", "attribution_pct": attribution_pct, "floor_pct": min_attribution_pct,
                    "sync_device": sync_device,
                    "message": f"instrumented functions cover {attribution_pct}% of run energy (floor {min_attribution_pct}%); "
                               "per-function shares are relative to the attributed energy only"},
                "functions": func_energy,
                "total_checkpoints": sum(d["calls"] * 2 for d in func_data.values()),
            })

            if not json_output:
                pct_str = f"{total_exclusive/1e6/total_energy_j*100:.0f}%" if total_energy_j > 0 else "n/a"
                console.print(f"    Energy: {total_energy_j:.2f} J, "
                              f"Attributed: {total_exclusive/1e6:.2f} J ({pct_str}), "
                              f"Functions: {len(func_energy)}")

            # Cooldown between runs
            if run_idx < repeat - 1:
                time.sleep(30)

        # ==========================================
        # OUTPUT RESULTS
        # ==========================================

        # Aggregate across runs (use last run for function list, average energy)
        if all_runs:
            avg_energy = sum(r["total_energy_j"] for r in all_runs) / len(all_runs)
            last_funcs = all_runs[-1]["functions"]

            # Hotspot ranking by exclusive energy (actual work, not wrappers)
            hotspots = sorted(last_funcs.items(),
                              key=lambda x: x[1].get("exclusive_pct", x[1]["energy_pct"]),
                              reverse=True)

            if json_output:
                result = {
                    "success": True,
                    "project": str(project_dir),
                    "language": language.value,
                    "source_files": len(source_files),
                    "instrumented_files": instrumented_count,
                    "total_points": total_points,
                    "skipped_functions": skipped_functions,
                    "sync_device": sync_device,
                    "attribution_pct": all_runs[-1]["attribution_pct"],
                    "attribution_warning": all_runs[-1]["attribution_warning"],
                    "runs": all_runs,
                    "hotspots": [{"rank": i+1, "function": name, **data}
                                 for i, (name, data) in enumerate(hotspots[:20])],
                }
                print(json.dumps(result, indent=2))
            else:
                console.print(f"\n[bold green]Results[/bold green]")
                console.print(f"  Total energy: {avg_energy:.2f} J (avg over {len(all_runs)} runs)")
                console.print(f"  Functions profiled: {len(last_funcs)}")
                if all_runs[-1]["attribution_warning"]:
                    console.print(f"  [yellow]WARNING {all_runs[-1]['attribution_warning']['message']}[/yellow]")
                console.print(f"\n[bold]Top hotspots by exclusive energy:[/bold]")
                console.print(f"  {'Rank':<5} {'Function':<35} {'Excl%':>7} {'Incl%':>7} {'Self':>6} "
                              f"{'Verdict':>8} {'Calls':>8} {'uJ/call':>10}")
                console.print("  " + "-" * 100)
                for i, (name, data) in enumerate(hotspots[:15]):
                    console.print(f"  {i+1:<5} {name:<35} {data.get('exclusive_pct', data['energy_pct']):>6.1f}% "
                                  f"{data['energy_pct']:>6.1f}% {data.get('self_ratio', 1.0):>5.2f} "
                                  f"{data.get('verdict', ''):>8} {data['calls']:>8} "
                                  f"{data['energy_per_call_uj']:>10.1f}")

            if output_dir:
                with open(output_dir / "project_results.json", "w") as f:
                    json.dump({"runs": all_runs, "hotspots": [
                        {"rank": i+1, "function": name, **data}
                        for i, (name, data) in enumerate(hotspots)]}, f, indent=2)
                if not json_output:
                    console.print(f"\n  Results saved to: {output_dir / 'project_results.json'}")

    finally:
        for _s, _h in _prev_handlers.items():
            _signal.signal(_s, _h)
        # ==========================================
        # CLEANUP: Restore original files
        # ==========================================
        if not no_cleanup:
            unrestored = []
            for src_file, original_code in backups.items():
                try:
                    src_file.write_text(original_code, encoding='utf-8')
                except OSError as e:
                    unrestored.append(f"{src_file}: {e}")
            if unrestored:
                print(f"codegreen: could not restore {len(unrestored)} files; originals kept in "
                      f"{backup_dir}: {unrestored[:3]}", file=sys.stderr)
            else:
                shutil.rmtree(backup_dir, ignore_errors=True)
            for rf in reversed(runtime_files_created):
                try:
                    _remove_injected(rf)
                except OSError as e:
                    print(f"codegreen: could not remove injected {rf}: {e}", file=sys.stderr)
            # Remove stale artifact marker
            _marker = project_dir / ".codegreen_instrumented"
            if _marker.exists():
                _marker.unlink(missing_ok=True)
            if not json_output and backups:
                console.print(f"\n  [dim]Restored {len(backups)} original files[/dim]")
        else:
            if not json_output:
                console.print(f"\n  [yellow]Instrumented files preserved (--no-cleanup)[/yellow]")
                console.print(f"  [yellow]Runtime files also preserved. To manually rebuild and run:[/yellow]")
                console.print(f"  [dim]  1. {proj_cfg.get('build_systems', {}).get(list(proj_cfg.get('build_systems', {}).keys() or [''])[0], {}).get('build_cmd', 'Build the project')}[/dim]")
                console.print(f"  [dim]  2. Run your benchmark, capturing stderr: <cmd> 2>checkpoints.txt[/dim]")
                console.print(f"  [dim]  3. Restore with: git checkout -- {project_dir}[/dim]")


@app.command("timeline", rich_help_panel="Measurement")
def timeline_cmd(
    out: Annotated[Path, typer.Option("--out", help="Perfetto/Chrome trace JSON to write (ui.perfetto.dev)")],
    nemb: Annotated[Optional[Path], typer.Option("--nemb", help="NEMB time series JSON (power + cumulative energy)")] = None,
    jfr: Annotated[Optional[Path], typer.Option("--jfr", help="`jfr print --json` output (stacks, GC, allocation)")] = None,
    jfr_offset_ns: Annotated[int, typer.Option(help="monotonic minus realtime ns taken during the run")] = 0,
    torch_trace: Annotated[Optional[Path], typer.Option("--torch", help="torch.profiler Chrome trace JSON")] = None,
    torch_offset_ns: Annotated[int, typer.Option(help="ns added to Kineto ts to reach the monotonic clock")] = 0,
    rel_change: Annotated[float, typer.Option(help="power change (fraction) that starts a phase")] = 0.2,
    confirm: Annotated[int, typer.Option(help="consecutive samples confirming a phase change")] = 3,
    gap_min_us: Annotated[float, typer.Option(help="GPU idle gap counted above this length")] = 10.0,
    launch_bound_frac: Annotated[float, typer.Option(help="gap share covered by CUDA launches to call it launch-bound")] = 0.8,
):
    """One time axis for a run: power, CPU stacks, GC, allocation and GPU kernels,
    exported for ui.perfetto.dev plus a phase and bottleneck summary."""
    from codegreen.analysis import timeline as tl
    if not (nemb or jfr or torch_trace):
        raise typer.BadParameter("give at least one of --nemb, --jfr, --torch")
    tr = tl.Trace()
    if nemb:
        tr = tr.merge(tl.from_nemb(json.loads(nemb.read_text())))
    if jfr:
        tr = tr.merge(tl.from_jfr(json.loads(jfr.read_text()), jfr_offset_ns))
    if torch_trace:
        tr = tr.merge(tl.from_torch(json.loads(torch_trace.read_text()), torch_offset_ns))
    out.write_text(json.dumps(tl.to_perfetto(tr)))
    print(json.dumps(tl.analyze(tr, rel_change=rel_change, confirm=confirm, gap_min_ns=int(gap_min_us * 1000),
                                launch_bound_frac=launch_bound_frac), indent=2, default=str))


@app.command("validate-accuracy", hidden=True, rich_help_panel="Validation")
def run_validation(
    experiment: Annotated[str, typer.Argument(help="Experiment: overhead, accuracy, scalability, crosslang, linearity, all")] = "all",
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Output directory")] = Path("validation_results"),
    latex: Annotated[bool, typer.Option("--latex", help="Generate LaTeX tables")] = False,
    plots: Annotated[bool, typer.Option("--plots", help="Generate plots")] = False,
    repetitions: Annotated[int, typer.Option("--reps", "-r", help="Repetitions per test")] = 30,
):
    """Run validation experiments for paper submission."""
    from benchmark.harness import BenchmarkHarness
    from validation.experiments import (ExperimentRunner, OverheadExperiment, AccuracyExperiment,
                                        ScalabilityExperiment, CrossLanguageExperiment, LinearityExperiment)
    from validation.reporting import LaTeXTableGenerator, PlotGenerator
    import json

    output_dir.mkdir(parents=True, exist_ok=True)

    def progress_cb(msg: str):
        console.print(f"[dim]{msg}[/dim]")

    harness = BenchmarkHarness(progress_callback=progress_cb)
    runner = ExperimentRunner(harness)

    experiments_map = {
        "overhead": OverheadExperiment(repetitions=repetitions),
        "accuracy": AccuracyExperiment(repetitions=repetitions),
        "scalability": ScalabilityExperiment(repetitions=min(repetitions, 10)),
        "crosslang": CrossLanguageExperiment(repetitions=repetitions),
        "linearity": LinearityExperiment(repetitions=min(repetitions, 10)),
    }

    if experiment == "all":
        to_run = list(experiments_map.values())
    elif experiment in experiments_map:
        to_run = [experiments_map[experiment]]
    else:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        console.print(f"Available: {', '.join(experiments_map.keys())}, all")
        raise typer.Exit(1)

    results = {}
    for exp in to_run:
        console.print(f"\n[bold]Running: {exp.name}[/bold]")
        result = runner.run_experiment(exp)
        results[exp.name] = result
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        console.print(f"  Result: {status}")
        for k, v in result.metrics.items():
            console.print(f"    {k}: {v}")

    results_file = output_dir / "validation_results.json"
    with open(results_file, "w") as f:
        from dataclasses import asdict
        def serialize_stats(obj):
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return obj
        results_data = {}
        for k, v in results.items():
            raw = {}
            for rk, rv in v.raw_data.items():
                raw[rk] = {rkk: serialize_stats(rvv) for rkk, rvv in rv.items()} if isinstance(rv, dict) else rv
            results_data[k] = {"passed": v.passed, "metrics": v.metrics, "raw_data": raw}
        json.dump(results_data, f, indent=2, default=str)
    console.print(f"\n[green]Results saved to {results_file}[/green]")

    if latex:
        latex_gen = LaTeXTableGenerator()
        if "overhead" in results:
            (output_dir / "overhead_table.tex").write_text(latex_gen.overhead_table(results["overhead"]))
        if "accuracy" in results:
            (output_dir / "accuracy_table.tex").write_text(latex_gen.accuracy_table(results["accuracy"]))
        (output_dir / "summary_table.tex").write_text(latex_gen.summary_table(results))
        console.print(f"[green]LaTeX tables saved to {output_dir}[/green]")

    if plots:
        plot_gen = PlotGenerator(output_dir)
        if "accuracy" in results:
            cg_vals = []
            perf_vals = []
            for data in results["accuracy"].raw_data.values():
                cg = data.get("codegreen", {})
                pf = data.get("perf", {})
                if cg and pf:
                    cg_vals.append(cg.get("mean", 0) if isinstance(cg, dict) else cg.mean)
                    perf_vals.append(pf.get("mean", 0) if isinstance(pf, dict) else pf.mean)
            if cg_vals and perf_vals:
                plot_gen.accuracy_scatter(cg_vals, perf_vals)
        if "overhead" in results:
            overhead_data = {k: v.get("overhead_percent", 0) for k, v in results["overhead"].raw_data.items()}
            plot_gen.overhead_bar_chart(overhead_data)
        if "linearity" in results:
            sizes = [int(s) for s in results["linearity"].raw_data.keys()]
            energies = [v.get("mean_energy", 0) for v in results["linearity"].raw_data.values()]
            if sizes and energies:
                plot_gen.linearity_plot(sizes, energies)
        console.print(f"[green]Plots saved to {output_dir}[/green]")

    harness.cleanup()

def main_cli():
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if os.environ.get('CODEGREEN_DEBUG'):
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)

if __name__ == '__main__':
    main_cli()