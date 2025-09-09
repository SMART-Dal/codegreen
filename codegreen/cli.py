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
import shutil
import json
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
    epilog="[dim]For more information, visit: https://github.com/codegreen/codegreen[/dim]"
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

def get_binary_path() -> Optional[Path]:
    """
    Get the path to the CodeGreen binary.
    
    Returns:
        Path to the binary if found, None otherwise
    """
    # Check multiple possible locations for the binary
    possible_paths = [
        # 1. In the package's bin directory
        Path(__file__).parent / "bin" / "codegreen",
        Path(__file__).parent / "bin" / "codegreen.exe",
        
        # 2. In a platform-specific subdirectory
        Path(__file__).parent / "bin" / f"{platform.system().lower()}-{platform.machine().lower()}" / "codegreen",
        Path(__file__).parent / "bin" / f"{platform.system().lower()}-{platform.machine().lower()}" / "codegreen.exe",
        
        # 3. In the build directory (development mode)
        Path(__file__).parents[1] / "build" / "bin" / "codegreen",
        Path(__file__).parents[1] / "build" / "bin" / "codegreen.exe",
        
        # 4. System-wide installation
        shutil.which("codegreen"),
    ]
    
    for path in possible_paths:
        if path and Path(path).exists() and os.access(path, os.X_OK):
            return Path(path)
    
    return None

def get_config_path() -> Optional[Path]:
    """Get the path to the default configuration file."""
    possible_paths = [
        Path(__file__).parent / "bin" / "config" / "codegreen.json",
        Path(__file__).parents[1] / "config" / "codegreen.json",
        Path.home() / ".codegreen" / "codegreen.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def ensure_runtime_available() -> bool:
    """Ensure the Python runtime module is available."""
    runtime_paths = [
        Path(__file__).parent / "bin" / "runtime" / "codegreen_runtime.py",
        Path(__file__).parents[1] / "runtime" / "codegreen_runtime.py",
    ]
    
    for path in runtime_paths:
        if path.exists():
            return True
    
    return False

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
    base_config_path = Path(__file__).parent.parent / "config" / "codegreen.json"
    if base_config_path.exists():
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
        "version": "0.1.0"
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
    [bold green]CodeGreen[/bold green] - Energy-aware software development tool
    
    Measure and optimize energy consumption of your code with fine-grained analysis.
    
    [bold]Features:[/bold]
    • Real-time energy monitoring
    • Multi-language support (Python, C++, Java, C)
    • Hardware sensor integration (RAPL, NVML, AMD SMI)
    • Detailed energy reports and visualizations
    • Performance optimization suggestions
    """
    if version:
        console.print("[bold green]CodeGreen version 0.1.0[/bold green]")
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
    precision: Annotated[Precision, typer.Option("--precision", "-p", help="Measurement precision")] = Precision.high,
    timeout: Annotated[Optional[int], typer.Option("--timeout", "-t", help="Timeout in seconds")] = None,
    args: Annotated[Optional[List[str]], typer.Argument(help="Arguments to pass to the script")] = None,
):
    """
    [bold]Measure energy consumption[/bold] of a script with detailed analysis.
    
    This command analyzes your code structure, instruments it with measurement
    points, and measures energy consumption using available hardware sensors.
    
    [bold]Examples:[/bold]
    • [cyan]codegreen measure python script.py[/cyan]
    • [cyan]codegreen measure python script.py --sensors rapl nvml[/cyan]
    • [cyan]codegreen measure python script.py --precision high --verbose[/cyan]
    """
    
    # Import the new language engine
    from .core.language_engine import get_language_engine
    
    if not script.exists():
        console.print(f"[red]Error: Script file not found: {script}[/red]")
        raise typer.Exit(1)
    
    try:
        # Read source code
        with open(script, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        console.print(f"[green]Analyzing code structure...[/green]")
        console.print(f"Language: [cyan]{language.value}[/cyan]")
        console.print(f"Script: [cyan]{script}[/cyan]")
        console.print(f"Precision: [cyan]{precision.value}[/cyan]")
        
        if sensors:
            console.print(f"Sensors: [cyan]{', '.join([s.value for s in sensors])}[/cyan]")
        
        # Analyze code with language engine
        engine = get_language_engine()
        result = engine.analyze_code(source_code, language.value, str(script))
        
        if not result.success:
            console.print(f"[red]Analysis failed: {result.error}[/red]")
            raise typer.Exit(1)
        
        # Display analysis results
        console.print(f"[green]✓ Analysis completed![/green]")
        console.print(f"Analysis method: [cyan]{result.metadata.get('analysis_method', 'unknown')}[/cyan]")
        console.print(f"Instrumentation points found: [cyan]{result.checkpoint_count}[/cyan]")
        console.print(f"Analysis time: [cyan]{result.metadata.get('analysis_time_ms', 0):.2f}ms[/cyan]")
        
        if verbose:
            # Show instrumentation points
            console.print("\n[bold]Instrumentation Points:[/bold]")
            table = Table()
            table.add_column("Type", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Line", style="yellow")
            table.add_column("Context", style="dim")
            
            for point in result.instrumentation_points[:10]:  # Show first 10
                table.add_row(
                    point.type,
                    point.name,
                    str(point.line),
                    point.context[:50] + "..." if len(point.context) > 50 else point.context
                )
            
            if len(result.instrumentation_points) > 10:
                table.add_row("...", f"+{len(result.instrumentation_points) - 10} more", "", "")
            
            console.print(table)
        
        # Show optimization suggestions
        if result.optimization_suggestions:
            console.print(f"\n[bold yellow]💡 Optimization Suggestions:[/bold yellow]")
            for i, suggestion in enumerate(result.optimization_suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        
        # Instrument code
        console.print(f"\n[green]Instrumenting code for energy measurement...[/green]")
        instrumented_code = engine.instrument_code(source_code, result.instrumentation_points, language.value)
        
        # Create instrumented file
        instrumented_path = script.with_name(f'{script.stem}_instrumented{script.suffix}')
        with open(instrumented_path, 'w', encoding='utf-8') as f:
            f.write(instrumented_code)
        
        console.print(f"[green]✓ Instrumented code saved to: {instrumented_path}[/green]")
        
        # Now run the measurement
        if _should_run_actual_measurement(sensors):
            console.print(f"\n[green]Running energy measurement...[/green]")
            measurement_result = _run_energy_measurement(
                instrumented_path, language, sensors, verbose, timeout, args
            )
            
            if output:
                _save_measurement_results(output, result, measurement_result)
                console.print(f"[green]✓ Results saved to: {output}[/green]")
        else:
            console.print(f"\n[yellow]Note: No energy sensors available. Code analysis and instrumentation completed.[/yellow]")
            console.print(f"To run with actual energy measurement, ensure RAPL or other sensors are available.")
        
        console.print(f"\n[green]✓ CodeGreen measurement completed successfully![/green]")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error: File not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
        raise typer.Exit(1)


def _should_run_actual_measurement(sensors: Optional[List[SensorType]]) -> bool:
    """Check if actual energy measurement should be performed"""
    # For now, check if binary exists for actual measurement
    binary_path = get_binary_path()
    return binary_path is not None and binary_path.exists()


def _run_energy_measurement(
    instrumented_path: Path,
    language: Language,
    sensors: Optional[List[SensorType]],
    verbose: bool,
    timeout: Optional[int],
    args: Optional[List[str]]
) -> Dict[str, Any]:
    """Run actual energy measurement on instrumented code"""
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[yellow]No binary available for energy measurement[/yellow]")
        return {}
    
    # Build command for binary
    cmd = [str(binary_path), language.value, str(instrumented_path)]
    
    if sensors:
        sensor_list = ",".join([s.value for s in sensors])
        cmd.extend(['--sensors', sensor_list])
    
    if verbose:
        cmd.append('--verbose')
    
    if args:
        cmd.extend(args)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running energy measurement...", total=None)
            
            if verbose:
                console.print(f"Command: [dim]{' '.join(cmd)}[/dim]")
            
            # Execute the binary
            result = subprocess.run(
                cmd, 
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            progress.update(task, completed=True)
            
            if result.returncode == 0:
                console.print("[green]✓ Energy measurement completed![/green]")
                return {'success': True, 'output': result.stdout}
            else:
                console.print(f"[yellow]Warning: Measurement had issues (exit code {result.returncode})[/yellow]")
                if verbose and result.stderr:
                    console.print(f"[dim]Stderr: {result.stderr}[/dim]")
                return {'success': False, 'error': result.stderr}
                
    except subprocess.TimeoutExpired:
        console.print("[red]Energy measurement timed out[/red]")
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        console.print(f"[red]Energy measurement failed: {e}[/red]")
        return {'success': False, 'error': str(e)}


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
    show_suggestions: Annotated[bool, typer.Option("--suggestions", help="Show optimization suggestions")] = True,
):
    """
    [bold]Analyze code structure[/bold] without energy measurement.
    
    This command analyzes your code structure and identifies instrumentation
    points without actually running energy measurement.
    
    [bold]Examples:[/bold]
    • [cyan]codegreen analyze python script.py[/cyan]
    • [cyan]codegreen analyze python script.py --verbose --output analysis.json[/cyan]
    """
    
    from .core.language_engine import get_language_engine
    
    if not script.exists():
        console.print(f"[red]Error: Script file not found: {script}[/red]")
        raise typer.Exit(1)
    
    try:
        # Read and analyze source code
        with open(script, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        console.print(f"[green]Analyzing code structure...[/green]")
        console.print(f"Language: [cyan]{language.value}[/cyan]")
        console.print(f"Script: [cyan]{script}[/cyan]")
        
        engine = get_language_engine()
        result = engine.analyze_code(source_code, language.value, str(script))
        
        if not result.success:
            console.print(f"[red]Analysis failed: {result.error}[/red]")
            raise typer.Exit(1)
        
        # Display results
        console.print(f"[green]✓ Analysis completed![/green]")
        console.print(f"Analysis method: [cyan]{result.metadata.get('analysis_method', 'unknown')}[/cyan]")
        console.print(f"Parser available: [cyan]{result.metadata.get('parser_available', False)}[/cyan]")
        console.print(f"Instrumentation points: [cyan]{result.checkpoint_count}[/cyan]")
        console.print(f"Analysis time: [cyan]{result.metadata.get('analysis_time_ms', 0):.2f}ms[/cyan]")
        console.print(f"Source lines: [cyan]{result.metadata.get('source_lines', 0)}[/cyan]")
        
        if verbose and result.instrumentation_points:
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
        
        if show_suggestions and result.optimization_suggestions:
            console.print(f"\n[bold yellow]💡 Optimization Suggestions:[/bold yellow]")
            for i, suggestion in enumerate(result.optimization_suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        
        # Save results if requested
        if output:
            analysis_data = {
                'timestamp': datetime.now().isoformat(),
                'script': str(script),
                'language': result.language,
                'analysis_method': result.metadata.get('analysis_method'),
                'parser_available': result.metadata.get('parser_available'),
                'instrumentation_points_count': result.checkpoint_count,
                'analysis_time_ms': result.metadata.get('analysis_time_ms'),
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
            
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2)
            
            console.print(f"[green]✓ Analysis saved to: {output}[/green]")
        
        console.print(f"\n[green]✓ Code analysis completed successfully![/green]")
        
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
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
    [bold]Comprehensive CodeGreen initialization[/bold].
    
    Performs comprehensive system detection and configuration:
    • Environment type detection (personal/server/HPC/container/CI)
    • Hardware sensor discovery and caching
    • Permission validation and setup guidance
    • Performance optimization settings
    • Configuration generation with user confirmation
    
    This avoids detection overhead during measurements by caching all
    system information during initialization.
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
        install_dir = Path(__file__).parent.parent / "install"
        setup_script = install_dir / "setup_permissions.sh"
        
        if install_dir.exists() and setup_script.exists():
            console.print("[blue]Auto-running permission setup...[/blue]")
            try:
                result = subprocess.run(
                    ["sudo", str(setup_script)],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    console.print("[green]✅ Permission setup completed![/green]")
                    # Re-check permissions after setup
                    permission_info = check_energy_permissions()
                else:
                    console.print("[red]❌ Permission setup failed[/red]")
                    if result.stderr:
                        console.print(result.stderr)
            except subprocess.SubprocessError as e:
                console.print(f"[red]Setup script error: {e}[/red]")
            except subprocess.TimeoutExpired:
                console.print("[red]Setup script timeout[/red]")
        else:
            console.print("[yellow]⚠️  Permission setup requested but script not found[/yellow]")
    
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
        status = "✅ Available" if info["available"] else "❌ Unavailable"
        hw_table.add_row(sensor, status, info.get("details", ""))
    console.print(hw_table)
    
    # Permissions table
    perm_table = Table(title="Energy Access Permissions")
    perm_table.add_column("Resource", style="cyan") 
    perm_table.add_column("Status", style="green")
    perm_table.add_column("Details")
    
    for resource, info in permission_info.items():
        status = "✅ Accessible" if info["accessible"] else "❌ Denied"
        perm_table.add_row(resource, status, info.get("details", ""))
    console.print(perm_table)
    
    # Interactive confirmation (unless auto-detect-only)
    if interactive and not auto_detect_only:
        console.print("\n[bold]Configuration Confirmation[/bold]")
        
        # Environment-specific setup recommendations
        install_dir = Path(__file__).parent.parent / "install"
        
        if not permission_info.get("rapl_cpu", {}).get("accessible", False):
            console.print("[yellow]⚠️  RAPL Permission Setup Required[/yellow]")
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
            console.print("[yellow]⚠️  Container Environment Detected[/yellow]")
            if install_dir.exists():
                docker_script = install_dir / "docker-setup.sh"
                console.print(f"   See container setup: [cyan]{docker_script}[/cyan]")
            console.print("   May need --privileged or specific capabilities")
            
        elif environment_info["type"] == "hpc":
            console.print("[yellow]⚠️  HPC Environment Detected[/yellow]")
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
                            console.print("[green]✅ Permission setup completed![/green]")
                            console.print("Re-running permission check...")
                            # Re-check permissions after setup
                            permission_info = check_energy_permissions()
                        else:
                            console.print("[red]❌ Permission setup failed[/red]")
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
        console.print("[green]✅ Configuration test successful![/green]")
        
        # Save configuration
        config_dir = Path(config_file_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(config_file_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        console.print(f"\n[green]✅ Initialization completed successfully![/green]")
        console.print(f"Configuration saved to: [cyan]{config_file_path}[/cyan]")
        
        # Display next steps
        console.print("\n[bold]Next Steps:[/bold]")
        console.print("• Run [cyan]codegreen info[/cyan] to verify system status")
        console.print("• Test with [cyan]codegreen benchmark cpu_stress --duration 5[/cyan]")
        console.print("• Customize settings with [cyan]codegreen config --edit[/cyan]")
        
    else:
        console.print("[red]❌ Configuration test failed[/red]")
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
    [bold]Display CodeGreen installation information[/bold].
    
    Shows system information, installation status, and configuration details.
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
        table.add_row("Binary", "✓ Found", str(binary_path))
    else:
        table.add_row("Binary", "✗ Missing", "CodeGreen binary not found")
    
    # Configuration information
    if config_path:
        table.add_row("Config", "✓ Found", str(config_path))
    else:
        table.add_row("Config", "⚠ Default", "Using default configuration")
    
    # Runtime information
    if runtime_available:
        table.add_row("Runtime", "✓ Available", "Python runtime modules found")
    else:
        table.add_row("Runtime", "⚠ Missing", "Runtime modules not found")
    
    # System information
    table.add_row("Platform", "✓", f"{platform.system()} {platform.machine()}")
    table.add_row("Python", "✓", sys.version.split()[0])
    
    # Package information
    try:
        import codegreen
        table.add_row("Version", "✓", f"CodeGreen {codegreen.__version__}")
    except:
        table.add_row("Version", "⚠", "Unknown")
    
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
    
    Performs comprehensive system checks and provides recommendations
    for fixing common installation and configuration problems.
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
        console.print(f"[green]✓[/green] Binary: {binary_path}")
    
    # Check dependencies
    try:
        import typer, rich, psutil
        console.print("[green]✓[/green] Python dependencies available")
    except ImportError as e:
        issues.append(f"Missing Python dependency: {e}")
        if fix:
            console.print("[blue]Attempting to install missing dependencies...[/blue]")
            # Could add auto-fix logic here
    
    # Check runtime
    if not ensure_runtime_available():
        warnings.append("Runtime modules not found - some features may not work")
    else:
        console.print("[green]✓[/green] Runtime modules available")
    
    # Check configuration
    config_path = get_config_path()
    if not config_path:
        warnings.append("Default configuration file not found")
    else:
        console.print(f"[green]✓[/green] Configuration: {config_path}")
    
    # Test basic functionality if binary exists
    if binary_path and test_sensors:
        console.print("\n[bold]Testing sensor functionality...[/bold]")
        try:
            result = subprocess.run([str(binary_path), "--help"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                console.print("[green]✓[/green] Binary executes successfully")
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
            console.print(f"  [red]✗[/red] {issue}")
    
    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")
    
    if fixes_applied:
        console.print("[green]Fixes applied:[/green]")
        for fix in fixes_applied:
            console.print(f"  [green]✓[/green] {fix}")
    
    if not issues and not warnings:
        console.print("[green]✓ No issues found! CodeGreen appears to be properly installed.[/green]")
    
    if issues:
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("1. Try reinstalling CodeGreen: [cyan]pip install --force-reinstall codegreen[/cyan]")
        console.print("2. Check system requirements in the documentation")
        console.print("3. Run [cyan]codegreen init[/cyan] to initialize sensors")
        console.print("4. Report issues at: https://github.com/codegreen/codegreen/issues")

class WorkloadType(str, Enum):
    """Available workload types for energy measurement."""
    cpu_stress = "cpu_stress"
    memory_stress = "memory_stress"
    mixed = "mixed"

@app.command("benchmark")
def measure_workload(
    workload: Annotated[WorkloadType, typer.Argument(help="Type of workload to run")] = WorkloadType.cpu_stress,
    duration: Annotated[int, typer.Option("--duration", "-d", help="Duration in seconds")] = 5,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output file for results")] = None,
    validate: Annotated[bool, typer.Option("--validate", help="Run validation against native tools (requires root)")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
):
    """
    [bold]Measure energy consumption of built-in workloads[/bold].
    
    Run standardized workloads to measure energy consumption using the NEMB system.
    This is useful for benchmarking, validation, and testing energy measurement accuracy.
    
    [bold]Examples:[/bold]
    • [cyan]codegreen benchmark cpu_stress --duration 10[/cyan]
    • [cyan]codegreen benchmark memory_stress --duration 5 --validate[/cyan]
    • [cyan]codegreen benchmark mixed --output results.json --verbose[/cyan]
    """
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[red]Error: CodeGreen binary not found![/red]")
        console.print("Please ensure CodeGreen is properly installed.")
        raise typer.Exit(1)
    
    # Build command for NEMB measurement
    cmd = [str(binary_path), "benchmark", workload.value]
    cmd.extend([f"--duration={duration}"])
    
    if verbose:
        cmd.append("--verbose")
    
    console.print(Panel.fit("[bold blue]CodeGreen NEMB Workload Measurement[/bold blue]"))
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {workload.value} workload...", total=None)
            
            console.print(f"[green]Configuration:[/green]")
            console.print(f"  Workload: [cyan]{workload.value}[/cyan]")
            console.print(f"  Duration: [cyan]{duration}s[/cyan]")
            console.print(f"  Validation: [cyan]{'Yes' if validate else 'No'}[/cyan]")
            
            if verbose:
                console.print(f"  Command: [dim]{' '.join(cmd)}[/dim]")
            
            # Execute NEMB measurement
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+30)
            progress.update(task, completed=True)
        
        if result.returncode == 0:
            console.print("[green]✓ NEMB measurement completed successfully![/green]")
            console.print("\n[bold]Results:[/bold]")
            console.print(result.stdout)
            
            # Save results if output specified
            if output:
                with open(output, 'w') as f:
                    f.write(result.stdout)
                console.print(f"[green]Results saved to:[/green] {output}")
            
            # Run validation if requested
            if validate:
                console.print("\n[bold yellow]Running validation against native tools...[/bold yellow]")
                console.print("[yellow]Note: Validation requires root access for RAPL/perf[/yellow]")
                
                validation_script = Path(__file__).parents[1] / "test_nemb_validation.sh"
                if validation_script.exists():
                    console.print("Run with sudo for full validation:")
                    console.print(f"[cyan]sudo {validation_script}[/cyan]")
                else:
                    console.print("[yellow]Validation script not found[/yellow]")
            
        else:
            console.print(f"[red]NEMB measurement failed:[/red]")
            console.print(result.stderr)
            console.print(f"[red]Exit code: {result.returncode}[/red]")
            
            if "root" in result.stderr.lower() or "permission" in result.stderr.lower():
                console.print("\n[yellow]Tip: NEMB measurements may require root access for hardware sensors[/yellow]")
                console.print("Try running: [cyan]sudo codegreen benchmark[/cyan]")
            
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("[red]Measurement timed out[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)

@app.command("validate")
def validate_accuracy(
    reference: Annotated[str, typer.Option("--reference", help="Reference tool (rapl, perf, both)")] = "both",
    duration: Annotated[int, typer.Option("--duration", "-d", help="Duration in seconds")] = 5,
    tolerance: Annotated[float, typer.Option("--tolerance", "-t", help="Acceptable error percentage")] = 5.0,
):
    """
    [bold]Validate NEMB accuracy against native tools[/bold].
    
    Compare NEMB measurements with RAPL, perf, and other native energy monitoring tools
    to detect wrapper contamination and ensure measurement quality.
    
    [bold red]Requires root access[/bold red] for hardware energy interfaces.
    
    [bold]Examples:[/bold]
    • [cyan]sudo codegreen validate[/cyan]
    • [cyan]sudo codegreen validate --reference rapl --tolerance 3.0[/cyan]
    • [cyan]sudo codegreen validate --duration 10[/cyan]
    """
    
    validation_script = Path(__file__).parents[1] / "test_nemb_validation.sh"
    
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
            console.print("\n[green]✓ Validation completed successfully![/green]")
        else:
            console.print(f"\n[red]✗ Validation failed with exit code {result.returncode}[/red]")
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
    [bold]Manage CodeGreen configuration[/bold].
    
    View, edit, or reset configuration settings.
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