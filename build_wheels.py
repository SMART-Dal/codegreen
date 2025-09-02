#!/usr/bin/env python3
"""
Cross-platform wheel building script for CodeGreen

This script builds wheels with precompiled binaries for different platforms.
It's designed to be run in CI/CD or by developers to create distributable wheels.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import argparse

def get_platform_tag():
    """Get platform tag for wheel naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize machine names for wheel compatibility
    machine_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64',
        'aarch64': 'aarch64', 
        'arm64': 'aarch64',
    }
    
    machine = machine_map.get(machine, machine)
    return f"{system}_{machine}"

def build_cpp_binary(build_dir: Path, install_dir: Path):
    """Build the C++ binary using CMake."""
    print(f"Building C++ binary in {build_dir}")
    
    # Create build directory
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure with CMake
    cmake_args = [
        "cmake",
        "..",
        f"-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DPMT_BUILD_TESTING=OFF",  # No tests needed for distribution
        "-DPMT_BUILD_BINARY=OFF",   # We only need the main binary
    ]
    
    subprocess.run(cmake_args, cwd=build_dir, check=True)
    
    # Build
    build_args = ["cmake", "--build", ".", "--config", "Release"]
    if shutil.which("ninja"):
        build_args.extend(["-j", str(os.cpu_count())])
    
    subprocess.run(build_args, cwd=build_dir, check=True)
    
    # Install to staging directory
    subprocess.run(["cmake", "--install", "."], cwd=build_dir, check=True)

def prepare_package_binaries(platform_tag: str):
    """Prepare binaries for packaging."""
    print(f"Preparing binaries for platform: {platform_tag}")
    
    # Create directories
    bin_dir = Path("codegreen/bin")
    platform_bin_dir = bin_dir / platform_tag
    platform_bin_dir.mkdir(parents=True, exist_ok=True)
    
    # Build binary
    build_dir = Path("build_wheel")
    install_dir = Path("install_wheel") 
    
    if not (install_dir / "bin" / "codegreen").exists():
        build_cpp_binary(build_dir, install_dir)
    
    # Copy binary to package location
    binary_name = "codegreen.exe" if platform.system() == "Windows" else "codegreen"
    source_binary = install_dir / "bin" / binary_name
    
    if source_binary.exists():
        shutil.copy2(source_binary, platform_bin_dir / binary_name)
        print(f"Copied {source_binary} to {platform_bin_dir / binary_name}")
    else:
        raise FileNotFoundError(f"Binary not found: {source_binary}")
    
    # Copy runtime files
    runtime_dir = bin_dir / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    
    runtime_source = Path("runtime")
    if runtime_source.exists():
        for py_file in runtime_source.glob("*.py"):
            shutil.copy2(py_file, runtime_dir)
            print(f"Copied runtime file: {py_file.name}")
    
    # Copy config files
    config_dir = bin_dir / "config" 
    config_dir.mkdir(exist_ok=True)
    
    config_source = Path("config")
    if config_source.exists():
        for config_file in config_source.glob("*.json"):
            shutil.copy2(config_file, config_dir)
            print(f"Copied config file: {config_file.name}")

def build_wheel(platform_tag: str):
    """Build a wheel for the specified platform."""
    print(f"Building wheel for platform: {platform_tag}")
    
    # Prepare binaries
    prepare_package_binaries(platform_tag)
    
    # Build wheel
    wheel_cmd = [
        sys.executable, "-m", "build", 
        "--wheel", 
        "--outdir", "dist"
    ]
    
    # Set environment for platform-specific wheel
    env = os.environ.copy()
    env["CODEGREEN_PLATFORM_TAG"] = platform_tag
    
    subprocess.run(wheel_cmd, env=env, check=True)
    
    print(f"✓ Wheel built successfully for {platform_tag}")

def clean_build_artifacts():
    """Clean up build artifacts."""
    artifacts = [
        "build_wheel",
        "install_wheel", 
        "codegreen/bin",
        "codegreen.egg-info",
        "build",
        "dist/*.whl"
    ]
    
    for artifact in artifacts:
        path = Path(artifact)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"Cleaned: {artifact}")

def main():
    parser = argparse.ArgumentParser(description="Build CodeGreen wheels")
    parser.add_argument("--platform", help="Platform tag (auto-detected if not specified)")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--all", action="store_true", help="Build for all supported platforms (requires cross-compilation)")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_build_artifacts()
        return
    
    # Ensure we have required tools
    required_tools = ["cmake"]
    for tool in required_tools:
        if not shutil.which(tool):
            print(f"Error: Required tool '{tool}' not found in PATH")
            sys.exit(1)
    
    if args.all:
        # This would require cross-compilation setup
        platforms = ["linux_x86_64", "macos_x86_64", "macos_aarch64", "windows_x86_64"]
        print("Cross-platform building not implemented yet.")
        print("Run this script on each target platform individually.")
        sys.exit(1)
    
    platform_tag = args.platform or get_platform_tag()
    
    try:
        build_wheel(platform_tag)
        print(f"\n✓ Wheel building completed for {platform_tag}")
        print("Check the 'dist/' directory for the generated wheel.")
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()