#!/usr/bin/env python3
"""
CodeGreen CLI - Command Line Interface

This module provides the main command-line interface for CodeGreen,
wrapping the C++ binary and providing a user-friendly Python interface.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

console = Console()

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

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version="0.1.0", prog_name="codegreen")
@click.option('--debug', is_flag=True, help='Enable debug output')
@click.option('--config', type=click.Path(exists=True), help='Path to configuration file')
@click.pass_context
def cli(ctx, debug, config):
    """
    CodeGreen - Energy-aware software development tool
    
    Measure and optimize energy consumption of your code with fine-grained analysis.
    """
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    ctx.obj['CONFIG'] = config
    
    # Set environment variables
    if debug:
        os.environ['CODEGREEN_DEBUG'] = '1'
    if config:
        os.environ['CODEGREEN_CONFIG'] = config

@cli.command()
@click.argument('language', type=click.Choice(['python', 'cpp', 'java', 'c']))
@click.argument('script', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file for results')
@click.option('--sensors', help='Comma-separated list of sensors to use (rapl,nvml,dummy)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def measure(ctx, language, script, output, sensors, verbose):
    """
    Measure energy consumption of a script.
    
    LANGUAGE: Programming language (python, cpp, java, c)
    SCRIPT: Path to the script file to measure
    """
    
    binary_path = get_binary_path()
    if not binary_path:
        console.print("[red]Error: CodeGreen binary not found![/red]")
        console.print("Please ensure CodeGreen is properly installed.")
        sys.exit(1)
    
    if not ensure_runtime_available():
        console.print("[yellow]Warning: Runtime modules may not be available[/yellow]")
    
    # Build command
    cmd = [str(binary_path), language, str(script)]
    
    if output:
        cmd.extend(['--output', output])
    
    if sensors:
        cmd.extend(['--sensors', sensors])
    
    if verbose or ctx.obj.get('DEBUG'):
        cmd.append('--verbose')
    
    if ctx.obj.get('CONFIG'):
        cmd.extend(['--config', ctx.obj['CONFIG']])
    
    try:
        console.print(f"[green]Running CodeGreen measurement...[/green]")
        console.print(f"Language: [cyan]{language}[/cyan]")
        console.print(f"Script: [cyan]{script}[/cyan]")
        
        if verbose or ctx.obj.get('DEBUG'):
            console.print(f"Command: [dim]{' '.join(cmd)}[/dim]")
        
        # Execute the binary
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode != 0:
            console.print(f"[red]Command failed with exit code {result.returncode}[/red]")
            sys.exit(result.returncode)
        
        console.print("[green]✓ Measurement completed successfully![/green]")
        
    except FileNotFoundError:
        console.print(f"[red]Error: Binary not found at {binary_path}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("[yellow]Measurement interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)

@cli.command()
@click.pass_context
def info(ctx):
    """Display CodeGreen installation information."""
    
    console.print(Panel.fit("CodeGreen Installation Information", style="bold blue"))
    
    binary_path = get_binary_path()
    config_path = get_config_path()
    runtime_available = ensure_runtime_available()
    
    # Binary information
    if binary_path:
        console.print(f"[green]✓[/green] Binary found: [cyan]{binary_path}[/cyan]")
    else:
        console.print("[red]✗[/red] Binary not found")
    
    # Configuration information
    if config_path:
        console.print(f"[green]✓[/green] Config found: [cyan]{config_path}[/cyan]")
    else:
        console.print("[yellow]⚠[/yellow] Default config not found")
    
    # Runtime information
    if runtime_available:
        console.print("[green]✓[/green] Runtime modules available")
    else:
        console.print("[yellow]⚠[/yellow] Runtime modules not found")
    
    # System information
    console.print(f"Platform: [cyan]{platform.system()} {platform.machine()}[/cyan]")
    console.print(f"Python: [cyan]{sys.version.split()[0]}[/cyan]")
    
    # Package information
    try:
        import codegreen
        console.print(f"CodeGreen version: [cyan]{codegreen.__version__}[/cyan]")
    except:
        console.print("CodeGreen version: [yellow]unknown[/yellow]")

@cli.command()
@click.option('--test-sensors', is_flag=True, help='Test sensor functionality')
@click.pass_context
def doctor(ctx, test_sensors):
    """
    Diagnose CodeGreen installation and configuration issues.
    """
    console.print(Panel.fit("CodeGreen Doctor - Diagnosing Installation", style="bold green"))
    
    issues = []
    warnings = []
    
    # Check binary
    binary_path = get_binary_path()
    if not binary_path:
        issues.append("CodeGreen binary not found")
    else:
        console.print(f"[green]✓[/green] Binary: {binary_path}")
    
    # Check dependencies
    try:
        import click, rich, psutil
        console.print("[green]✓[/green] Python dependencies available")
    except ImportError as e:
        issues.append(f"Missing Python dependency: {e}")
    
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
    
    if not issues and not warnings:
        console.print("[green]✓ No issues found! CodeGreen appears to be properly installed.[/green]")
    
    if issues:
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("1. Try reinstalling CodeGreen: [cyan]pip install --force-reinstall codegreen[/cyan]")
        console.print("2. Check system requirements in the documentation")
        console.print("3. Report issues at: https://github.com/codegreen/codegreen/issues")

def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if os.environ.get('CODEGREEN_DEBUG'):
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()