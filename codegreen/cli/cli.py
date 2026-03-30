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
import json
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Annotated, Union
from enum import Enum
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

console = Console()

# Enhanced Typer app with advanced features
app = typer.Typer(
    name="codegreen",
    help="[bold green]CodeGreen[/bold green] - Energy-aware software development tool",
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
        pkg_root / "config.json",                              # pip install (inside codegreen/)
        pkg_root.parent / "config" / "codegreen.json",         # dev: repo_root/config/codegreen.json
        Path.home() / ".codegreen" / "codegreen.json",         # user override
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
            except:
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
        except:
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
    if os.geteuid() == 0:
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
            if disk_usage.free < disk_usage.total * 0.1:  # Less than 10% free
                settings["recommended_settings"]["storage"] = "Low disk space - enable temp file cleanup"
        except:
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
        "timestamp": datetime.now().isoformat(),
        "environment_type": environment_info["type"],
        "detected_sensors": list(sensor_info.keys()),
        "version": codegreen.__version__
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
                    [str(binary_path), "benchmark", "cpu_stress", "--duration=1"],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0 and "Energy consumed:" in result.stdout:
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
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug output")] = False,
    config: Annotated[Optional[Path], typer.Option("--config", help="Path to configuration file")] = None,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version and exit")] = False,
    log_level: Annotated[LogLevel, typer.Option("--log-level", help="Set logging level")] = LogLevel.INFO,
):
    """
    [bold green]CodeGreen[/bold green] - Energy-aware software development and optimization tool

    Advanced energy profiling and optimization for sustainable software development.
    Measure fine-grained energy consumption, identify hotspots, and optimize code
    efficiency using hardware-level sensors and AI-powered analysis.

    [bold]Core Features:[/bold]
    - [cyan]Hardware-level energy measurement[/cyan] via Intel RAPL, NVIDIA NVML, AMD ROCm
    - [cyan]Multi-language support[/cyan] with AST-based instrumentation (Python, C++, Java, C)
    - [cyan]Function-level energy profiling[/cyan] with microsecond precision
    - [cyan]AI-powered optimization[/cyan] suggestions and energy hotspot detection
    - [cyan]Professional CLI interface[/cyan] with rich formatting and auto-completion

    [bold]Quick Start:[/bold]
    - [dim]codegreen init[/dim] - Initialize sensors and system configuration
    - [dim]codegreen measure python script.py[/dim] - Measure energy consumption
    - [dim]codegreen analyze python module.py[/dim] - Analyze code structure
    - [dim]codegreen benchmark cpu_stress[/dim] - Run energy benchmarks

    [bold]System Management:[/bold]
    - [dim]codegreen info[/dim] - Show installation and system status
    - [dim]codegreen doctor[/dim] - Diagnose installation issues
    - [dim]codegreen config --show[/dim] - View/edit configuration
    """
    if version:
        console.print(f"[bold green]CodeGreen version {codegreen.__version__}[/bold green]")
        raise typer.Exit()
    
    # If no command is provided and version is not requested, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
    
    # Set environment variables
    if debug:
        os.environ['CODEGREEN_DEBUG'] = '1'
    if config:
        os.environ['CODEGREEN_CONFIG'] = str(config)
    
    # Set log level
    os.environ['CODEGREEN_LOG_LEVEL'] = log_level.value

@app.command("measure")
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
            instrumented_code = engine.instrument_code(source_code, points, language.value)

            # Determine correct output extension
            ext_map = {'python': '.py', 'c': '.c', 'cpp': '.cpp', 'java': '.java'}
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
    return {
        "success": bool(measurement_result and measurement_result.get('success')),
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


def _should_run_actual_measurement(sensors: Optional[List[SensorType]]) -> bool:
    """Check if actual energy measurement should be performed"""
    # For now, check if binary exists for actual measurement
    binary_path = get_binary_path()
    return binary_path is not None and binary_path.exists()


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
        'timestamp': datetime.now().isoformat(),
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


@app.command("analyze")
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
            instrumented_code = engine.instrument_code(source_code, result.instrumentation_points, language.value)
            
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
            'timestamp': datetime.now().isoformat(),
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

@app.command("init")
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
        console.print("• Test with [cyan]codegreen benchmark cpu_stress --duration 5[/cyan]")
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

@app.command("info")
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
        table.add_row("Version", "[ok]", f"CodeGreen {codegreen.__version__}")
    except:
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

@app.command("doctor")
def diagnose(
    test_sensors: Annotated[bool, typer.Option("--test-sensors", help="Test sensor functionality")] = False,
    fix: Annotated[bool, typer.Option("--fix", help="Attempt to fix common issues")] = False,
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
    - [cyan]codegreen doctor --fix[/cyan] - Attempt to auto-fix common issues
    """
    console.print(Panel.fit("[bold green]CodeGreen Doctor - System Diagnosis[/bold green]"))
    
    issues = []
    warnings = []
    fixes_applied = []
    
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
        if fix:
            console.print("[blue]Attempting to install missing dependencies...[/blue]")
            # Could add auto-fix logic here
    
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
    
    # Test basic functionality if binary exists
    if binary_path and test_sensors:
        console.print("\n[bold]Testing sensor functionality...[/bold]")
        try:
            result = subprocess.run([str(binary_path), "--help"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                console.print("[green][ok][/green] Binary executes successfully")
            else:
                issues.append(f"Binary execution failed (exit code: {result.returncode})")
        except subprocess.TimeoutExpired:
            issues.append("Binary execution timed out")
        except Exception as e:
            issues.append(f"Binary execution error: {e}")
    
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
    
    if fixes_applied:
        console.print("[green]Fixes applied:[/green]")
        for fix in fixes_applied:
            console.print(f"  [green][ok][/green] {fix}")
    
    if not issues and not warnings:
        console.print("[green][ok] No issues found! CodeGreen appears to be properly installed.[/green]")
    
    if issues:
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("1. Try reinstalling CodeGreen: [cyan]pip install --force-reinstall codegreen[/cyan]")
        console.print("2. Check system requirements in the documentation")
        console.print("3. Run [cyan]codegreen init[/cyan] to initialize sensors")
        console.print("4. Report issues at: https://github.com/SMART-Dal/codegreen/issues")


@app.command("validate")
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
    if os.geteuid() != 0:
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

@app.command("config")
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

    [bold]Configuration categories:[/bold]
    - Sensor preferences and validation settings
    - Measurement accuracy and precision levels
    - Performance optimization parameters
    - Environment-specific adaptations
    - Database and logging configurations

    [bold]Examples:[/bold]
    - [cyan]codegreen config --show[/cyan] - Display current configuration
    - [cyan]codegreen config --edit[/cyan] - Edit configuration interactively
    - [cyan]codegreen config --reset[/cyan] - Reset to system defaults
    """
    config_path = get_config_path()
    
    if show:
        if config_path:
            console.print(f"[green]Configuration file:[/green] {config_path}")
            config = load_config(config_path)
            console.print(json.dumps(config, indent=2))
        else:
            console.print("[yellow]No configuration file found[/yellow]")
    
    elif edit:
        if config_path:
            console.print(f"[blue]Opening configuration file:[/blue] {config_path}")
            # Could add editor opening logic here
        else:
            console.print("[yellow]No configuration file found to edit[/yellow]")
    
    elif reset:
        console.print("[yellow]Configuration reset not implemented yet[/yellow]")
    
    else:
        console.print("[yellow]Please specify an action: --show, --edit, or --reset[/yellow]")

@app.command("init-sensors")
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
            console.print("  codegreen benchmark cpu_stress --duration 3")
            return
        except PermissionError:
            pass

    # Check if running as root
    if os.geteuid() != 0:
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
        console.print("  codegreen benchmark cpu_stress --duration 3")
        console.print("")
        console.print("[green]No sudo needed after this![/green]")

    except Exception as e:
        console.print(f"[red]Setup failed: {e}[/red]")
        raise typer.Exit(1)

@app.command("measure-workload")
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
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[red]CodeGreen binary not found[/red]")
        raise typer.Exit(1)
    
    try:
        result = subprocess.run(
            [binary_path, "--measure-workload", f"--duration={duration}", f"--workload={workload}"],
            capture_output=True,
            text=True,
            timeout=duration + 30  # Add buffer time
        )
        
        if result.returncode == 0:
            console.print("[green]Workload measurement completed successfully[/green]")
            console.print(result.stdout)
        else:
            console.print("[red]Workload measurement failed[/red]")
            console.print(result.stderr)
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("[red]Workload measurement timed out[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error during workload measurement: {e}[/red]")
        raise typer.Exit(1)

@app.command("benchmark")
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

@app.command("run")
def run_command(
    command: Annotated[List[str], typer.Argument(help="Command to measure energy for")],
    repeat: Annotated[int, typer.Option("--repeat", "-n", help="Number of repetitions")] = 10,
    warmup: Annotated[int, typer.Option("--warmup", "-w", help="Warmup runs")] = 1,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    budget: Annotated[Optional[float], typer.Option("--budget", help="Energy budget in Joules (fail if exceeded)")] = None,
):
    """Measure energy of any shell command (like hyperfine but for energy).

    Examples:
    - codegreen run python script.py
    - codegreen run --repeat 20 ./my_binary arg1 arg2
    - codegreen run --budget 10.0 python train.py
    """
    import subprocess, time, re, tempfile, math
    from benchmark.results import StatisticalAnalysis

    for i in range(warmup):
        if not json_output:
            console.print(f"[dim]Warmup {i+1}/{warmup}[/dim]")
        subprocess.run(command, capture_output=True, timeout=300)

    events = "power/energy-pkg/"
    try:
        r = subprocess.run(["perf", "list", "power"], capture_output=True, text=True, timeout=5)
        if "energy-ram" in r.stdout:
            events += ",power/energy-ram/"
    except Exception:
        pass

    energies, times = [], []
    for i in range(repeat):
        if not json_output:
            console.print(f"[dim]Run {i+1}/{repeat}[/dim]")
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            perf_file = f.name
        try:
            full = ["perf", "stat", "-e", events, "-o", perf_file, "--"] + command
            start = time.perf_counter()
            subprocess.run(full, capture_output=True, text=True, timeout=300)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            content = open(perf_file).read()
            total = 0.0
            for m in re.finditer(r'([\d.,]+)\s+Joules', content):
                total += float(m.group(1).replace(',', ''))
            if total > 0:
                energies.append(total)
        finally:
            import os
            os.unlink(perf_file)

    if not energies:
        if json_output:
            print(json.dumps({"success": False, "error": "No energy data (RAPL unavailable?)"}))
        else:
            console.print("[red]No energy data collected. Is RAPL accessible?[/red]")
        raise typer.Exit(1)

    e_stats = StatisticalAnalysis.summarize(energies)
    t_stats = StatisticalAnalysis.summarize(times)

    if json_output:
        print(json.dumps({
            "command": " ".join(command), "runs": len(energies),
            "energy_joules": {"mean": e_stats.mean, "std": e_stats.std, "min": e_stats.min, "max": e_stats.max,
                              "ci95": [e_stats.ci95_lower, e_stats.ci95_upper]},
            "time_seconds": {"mean": t_stats.mean, "std": t_stats.std, "min": t_stats.min, "max": t_stats.max},
            "budget_exceeded": budget is not None and e_stats.mean > budget
        }, indent=2))
    else:
        console.print(f"\n[bold]Energy:[/bold] {e_stats.mean:.4f} J +/- {e_stats.std:.4f} J")
        console.print(f"  Range: [{e_stats.min:.4f} .. {e_stats.max:.4f}] J, "
                       f"CI95: [{e_stats.ci95_lower:.4f}, {e_stats.ci95_upper:.4f}] J")
        console.print(f"[bold]Time:[/bold]   {t_stats.mean:.4f} s +/- {t_stats.std:.4f} s")
        console.print(f"  Runs: {len(energies)}, Outliers removed: {e_stats.outliers_removed}")
        if budget is not None:
            if e_stats.mean > budget:
                console.print(f"[red]BUDGET EXCEEDED: {e_stats.mean:.4f}J > {budget}J[/red]")
                raise typer.Exit(1)
            else:
                console.print(f"[green]Within budget: {e_stats.mean:.4f}J <= {budget}J[/green]")


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


def _find_source_roots(file_paths, proj_cfg: dict) -> set:
    """Find source root directories from file paths using config-driven markers.
    Reads source_root_markers from project_config (e.g., ["src/main/java"] for Java)."""
    markers = proj_cfg.get("source_root_markers", ["src"])
    roots = set()
    for f in file_paths:
        path_str = str(Path(f))
        for marker in markers:
            marker_parts = marker.split("/")
            parts = Path(f).parts
            # Find the marker sequence in path parts
            for i in range(len(parts) - len(marker_parts) + 1):
                if list(parts[i:i+len(marker_parts)]) == marker_parts:
                    roots.add(Path(*parts[:i+len(marker_parts)]))
                    break
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


@app.command("project")
def project_energy(
    language: Annotated[Language, typer.Argument(help="Project language")],
    project_dir: Annotated[Path, typer.Argument(help="Project root directory")],
    build_cmd: Annotated[str, typer.Option("--build-cmd", "-b", help="Build command (e.g., 'mvn package -DskipTests')")] = "",
    run_cmd: Annotated[str, typer.Option("--run-cmd", "-r", help="Run command (e.g., 'java -jar target/benchmarks.jar')")] = "",
    source_glob: Annotated[str, typer.Option("--source-glob", "-s", help="Source file glob pattern")] = "",
    granularity: Annotated[Granularity, typer.Option("--granularity", "-g", help="Instrumentation level")] = Granularity.fine,
    cores: Annotated[str, typer.Option("--cores", help="CPU cores for taskset (e.g., '0-7')")] = "",
    repeat: Annotated[int, typer.Option("--repeat", "-n", help="Measurement repetitions")] = 1,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_cleanup: Annotated[bool, typer.Option("--no-cleanup", help="Keep instrumented files")] = False,
    output_dir: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output directory for results")] = None,
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
    source_patterns = [source_glob] if source_glob else proj_cfg.get("source_patterns", [f"**/*{_lang_config['extensions'][0]}"])
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

    if output_dir:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

    # ==========================================
    # PRE-CLEANUP: Detect and remove stale instrumented files from previous runs
    # ==========================================
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

    # ==========================================
    # PHASE 1: DISCOVER
    # ==========================================
    if not json_output:
        console.print(f"\n[bold cyan]Phase 1: Discovering source files...[/bold cyan]")

    # Find source files: use Path.glob for each source pattern from config
    extensions = set(_lang_config.get("extensions", []))
    source_files_set = set()
    for pattern in source_patterns:
        # Path.rglob handles ** patterns natively
        clean = pattern.lstrip("**/") if pattern.startswith("**/") else pattern
        for f in project_dir.rglob(clean):
            if f.is_file() and f.suffix in extensions:
                source_files_set.add(f)
    # If no pattern matched, fall back to finding all files by extension
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

    if not json_output:
        console.print(f"  Instrumentable files: {len(analysis_results)}/{len(source_files)}")
        console.print(f"  Total instrumentation points: {total_points}")

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

    # Create backup of original files
    backups = {}
    runtime_files_created = []

    try:
        # Instrument each file in-place
        instrumented_count = 0
        for src_file, data in analysis_results.items():
            # Double-check: skip if file defines a checkpoint class (defense in depth)
            if _is_runtime_file(src_file):
                continue
            try:
                instrumented = engine.instrument_code(data["code"], data["points"], language.value)
                if instrumented and instrumented != data["code"]:
                    # Rewrite for standalone runtime if config specifies rewrites
                    rt_cfg = proj_cfg.get("runtime_injection", {})
                    instrumented = _rewrite_instrumented_for_standalone(instrumented, rt_cfg)
                    backups[src_file] = data["code"]
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

        all_runs = []
        for run_idx in range(repeat):
            if not json_output and repeat > 1:
                console.print(f"  Run {run_idx+1}/{repeat}")

            # Construct the run command with optional taskset
            full_cmd = run_cmd
            if cores:
                full_cmd = f"taskset -c {cores} {full_cmd}"

            # Run with perf stat for total energy + capture stderr for checkpoints
            perf_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False).name
            checkpoint_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False).name

            # Run: perf stat wrapping the command, stderr goes to checkpoint_file
            perf_cmd = f"perf stat -e power/energy-pkg/ -o {perf_file} -- bash -c '{full_cmd} 2>{checkpoint_file}'"
            start_time = time.perf_counter()
            run_result = subprocess.run(
                perf_cmd, shell=True, cwd=str(project_dir),
                capture_output=True, text=True, timeout=3600)
            wall_time = time.perf_counter() - start_time

            # Parse perf stat for total energy
            total_energy_j = 0.0
            try:
                perf_content = open(perf_file).read()
                for m in re.finditer(r'([\d.,]+)\s+Joules', perf_content):
                    total_energy_j += float(m.group(1).replace(',', ''))
            except Exception:
                pass
            finally:
                os.unlink(perf_file)

            # Parse checkpoints with per-thread call stacks for inclusive/exclusive
            func_data = {}  # name -> {inclusive_uj, exclusive_uj, time_ns, calls}
            thread_stacks = {}  # tid -> [(name, enter_ts, enter_energy, callee_energy_sum)]
            try:
                with open(checkpoint_file) as cf:
                    for line in cf:
                        if not line.startswith("CG_CP|"):
                            continue
                        parts = line.strip().split("|")
                        if len(parts) < 6:
                            continue
                        cp_type, cp_name = parts[1], parts[2]
                        cp_id_str = parts[3] if len(parts) > 3 else ""
                        cp_ts, cp_energy = int(parts[4]), int(parts[5])
                        cp_tid = int(parts[6]) if len(parts) > 6 else 0

                        # Resolve file from checkpoint_id (authoritative mapping)
                        cp_file = checkpoint_id_to_file.get(cp_id_str, "")
                        if cp_file:
                            func_file_map[cp_name] = cp_file

                        if cp_name not in func_data:
                            func_data[cp_name] = {"inclusive_uj": 0, "exclusive_uj": 0, "time_ns": 0, "calls": 0}

                        if cp_tid not in thread_stacks:
                            thread_stacks[cp_tid] = []
                        stack = thread_stacks[cp_tid]

                        if cp_type == "enter":
                            stack.append([cp_name, cp_ts, cp_energy, 0])
                        elif cp_type == "exit" and stack:
                            # Pop matching frame (handle missing exits via stack search)
                            frame = stack[-1]
                            if frame[0] == cp_name:
                                stack.pop()
                            else:
                                # Search for matching frame, unwinding abandoned frames
                                found = False
                                for si in range(len(stack) - 1, -1, -1):
                                    if stack[si][0] == cp_name:
                                        frame = stack[si]
                                        del stack[si:]
                                        found = True
                                        break
                                if not found:
                                    continue

                            dt = cp_ts - frame[1]
                            inclusive = cp_energy - frame[2]
                            callee_sum = frame[3]
                            if dt > 0 and inclusive >= 0:
                                exclusive = max(inclusive - callee_sum, 0)
                                func_data[cp_name]["inclusive_uj"] += inclusive
                                func_data[cp_name]["exclusive_uj"] += exclusive
                                func_data[cp_name]["time_ns"] += dt
                                func_data[cp_name]["calls"] += 1
                                # Propagate inclusive to parent's callee_sum
                                if stack:
                                    stack[-1][3] += inclusive
            except Exception:
                pass
            finally:
                if not no_cleanup:
                    os.unlink(checkpoint_file)
                elif output_dir:
                    shutil.copy2(checkpoint_file, str(output_dir / f"checkpoints_run{run_idx}.txt"))
                    os.unlink(checkpoint_file)

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
                if self_ratio < 0.2 and inc_pct >= 5.0:
                    verdict = "wrapper"
                elif exc_pct >= 5.0 and efficiency_ratio > 3.0:
                    verdict = "TYPE_2_INEFFICIENT"
                elif exc_pct >= 10.0:
                    verdict = "TYPE_1_DIRECT"
                elif calls > 100000 and exc_pct >= 3.0 and efficiency_ratio < 1.5:
                    verdict = "TYPE_5_FREQUENCY"
                elif exc_pct >= 3.0:
                    verdict = "TYPE_1_DIRECT"
                else:
                    verdict = "minor"
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

            all_runs.append({
                "run_idx": run_idx,
                "total_energy_j": round(total_energy_j, 4),
                "wall_time_s": round(wall_time, 3),
                "avg_power_w": round(total_energy_j / wall_time, 2) if wall_time > 0 else 0,
                "attributed_energy_j": round(total_inclusive / 1e6, 4),
                "exclusive_energy_j": round(total_exclusive / 1e6, 4),
                "attribution_pct": round(total_inclusive / 1e6 / total_energy_j * 100, 1) if total_energy_j > 0 else 0,
                "functions": func_energy,
                "total_checkpoints": sum(d["calls"] * 2 for d in func_data.values()),
            })

            if not json_output:
                console.print(f"    Energy: {total_energy_j:.2f} J, "
                              f"Attributed: {total_inclusive/1e6:.2f} J ({total_inclusive/1e6/total_energy_j*100:.0f}%), "
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
                    "runs": all_runs,
                    "hotspots": [{"rank": i+1, "function": name, **data}
                                 for i, (name, data) in enumerate(hotspots[:20])],
                }
                print(json.dumps(result, indent=2))
            else:
                console.print(f"\n[bold green]Results[/bold green]")
                console.print(f"  Total energy: {avg_energy:.2f} J (avg over {len(all_runs)} runs)")
                console.print(f"  Functions profiled: {len(last_funcs)}")
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
        # ==========================================
        # CLEANUP: Restore original files
        # ==========================================
        if not no_cleanup:
            for src_file, original_code in backups.items():
                try:
                    src_file.write_text(original_code, encoding='utf-8')
                except Exception:
                    pass
            for rf in reversed(runtime_files_created):
                try:
                    if rf.is_file():
                        rf.unlink()
                    elif rf.is_dir() and not any(rf.iterdir()):
                        rf.rmdir()
                except Exception:
                    pass
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


@app.command("validate-accuracy")
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