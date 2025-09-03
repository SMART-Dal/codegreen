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
    no_args_is_help=True,  # Show help when no args provided
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
    """Available PMT sensor types."""
    rapl = "rapl"
    nvml = "nvml"
    amdsmi = "amdsmi"
    powersensor3 = "powersensor3"
    powersensor2 = "powersensor2"
    likwid = "likwid"
    rocm = "rocm"
    dummy = "dummy"

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
                "preferred_sensors": ["rapl", "nvml", "dummy"]
            }
        }
    }

@app.callback()
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
    
    This command instruments your code and measures its energy consumption
    using available hardware sensors (RAPL, NVML, etc.).
    
    [bold]Examples:[/bold]
    • [cyan]codegreen measure python script.py[/cyan]
    • [cyan]codegreen measure python script.py --sensors rapl nvml[/cyan]
    • [cyan]codegreen measure python script.py --precision high --verbose[/cyan]
    """
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[red]Error: CodeGreen binary not found![/red]")
        console.print("Please ensure CodeGreen is properly installed.")
        raise typer.Exit(1)
    
    if not ensure_runtime_available():
        console.print("[yellow]Warning: Runtime modules may not be available[/yellow]")
    
    if not script.exists():
        console.print(f"[red]Error: Script file not found: {script}[/red]")
        raise typer.Exit(1)
    
    # Build command
    cmd = [str(binary_path), language.value, str(script)]
    
    if output:
        cmd.extend(['--output', str(output)])
    
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
            
            console.print(f"[green]Running CodeGreen measurement...[/green]")
            console.print(f"Language: [cyan]{language.value}[/cyan]")
            console.print(f"Script: [cyan]{script}[/cyan]")
            console.print(f"Precision: [cyan]{precision.value}[/cyan]")
            
            if sensors:
                console.print(f"Sensors: [cyan]{', '.join([s.value for s in sensors])}[/cyan]")
            
            if verbose:
                console.print(f"Command: [dim]{' '.join(cmd)}[/dim]")
            
            # Execute the binary
            result = subprocess.run(
                cmd, 
                capture_output=False, 
                text=True,
                timeout=timeout
            )
            
            progress.update(task, completed=True)
        
        if result.returncode != 0:
            console.print(f"[red]Command failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
        
        console.print("[green]✓ Measurement completed successfully![/green]")
        
    except subprocess.TimeoutExpired:
        console.print("[red]Measurement timed out[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print(f"[red]Error: Binary not found at {binary_path}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("[yellow]Measurement interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)

@app.command("init")
def init_sensors(
    force: Annotated[bool, typer.Option("--force", "-f", help="Force re-initialization even if cache exists")] = False,
    cache_path: Annotated[Optional[Path], typer.Option("--cache-path", help="Path to sensor cache file")] = None,
):
    """
    [bold]Initialize and cache sensor configuration[/bold].
    
    This command detects available sensors and caches the configuration
    to avoid sensor detection overhead during energy measurements.
    
    [bold]Benefits:[/bold]
    • Faster measurement startup
    • No sensor detection overhead during measurements
    • Consistent sensor availability
    """
    console.print(Panel.fit("[bold blue]CodeGreen Sensor Initialization[/bold blue]"))
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[red]Error: CodeGreen binary not found![/red]")
        console.print("Please ensure CodeGreen is properly installed.")
        raise typer.Exit(1)
    
    # Check if cache already exists
    if not force:
        cache_file = cache_path or Path.home() / ".codegreen" / "sensors.json"
        if cache_file.exists():
            console.print(f"[yellow]Sensor cache already exists at: {cache_file}[/yellow]")
            console.print("Use [cyan]--force[/cyan] to re-initialize")
            return
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Detecting available sensors...", total=None)
            
            # Run sensor detection and caching
            result = subprocess.run(
                [str(binary_path), "--init-sensors"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            progress.update(task, completed=True)
        
        if result.returncode == 0:
            console.print("[green]✓[/green] Sensor configuration initialized successfully!")
            
            # Parse and display sensor results
            table = Table(title="Available Sensors")
            table.add_column("Sensor", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Description")
            
            sensor_descriptions = {
                "rapl": "Intel/AMD CPU power monitoring",
                "nvml": "NVIDIA GPU power monitoring", 
                "amdsmi": "AMD GPU power monitoring",
                "powersensor3": "External USB power sensor",
                "powersensor2": "External USB power sensor",
                "likwid": "Performance monitoring",
                "rocm": "AMD ROCm",
                "dummy": "Fallback dummy sensor"
            }
            
            for line in result.stdout.split('\n'):
                if '✅' in line:
                    sensor_name = line.split(' - ')[0].replace('✅ ', '').strip()
                    table.add_row(
                        sensor_name,
                        "Available",
                        sensor_descriptions.get(sensor_name, "Unknown sensor")
                    )
                elif '❌' in line:
                    sensor_name = line.split(' - ')[0].replace('❌ ', '').strip()
                    table.add_row(
                        sensor_name,
                        "Failed",
                        sensor_descriptions.get(sensor_name, "Unknown sensor")
                    )
            
            console.print(table)
            console.print(f"\n[green]Configuration cached to:[/green] ~/.codegreen/sensors.json")
            console.print("[blue]You can now run energy measurements without sensor detection overhead.[/blue]")
            
        else:
            console.print(f"[red]Sensor initialization failed:[/red]")
            console.print(result.stderr)
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("[red]Sensor initialization timed out[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error during initialization: {e}[/red]")
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