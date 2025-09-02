#!/usr/bin/env python3
"""
CodeGreen Python Package Setup for PyPI
Enables easy installation via pip: pip install codegreen

This setup handles:
1. Cross-platform binary distribution
2. Automatic C++ compilation when source is available
3. Precompiled binary fallback for pip users
4. Platform-specific wheel building
"""

from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
import os
import subprocess
import sys
import platform
import shutil
from pathlib import Path

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Get version from git or use default
def get_version():
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "0.1.0"

# Custom build extension for C++ components
class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)

class CMakeBuild(build_ext):
    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        
        if not extdir.endswith(os.path.sep):
            extdir += os.path.sep

        debug = int(os.environ.get("DEBUG", 0)) if self.debug is None else self.debug
        cfg = "Debug" if debug else "Release"

        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_BUILD_TYPE={cfg}",
        ]
        build_args = []

        if "CMAKE_BUILD_PARALLEL_LEVEL" not in os.environ:
            if hasattr(self, "parallel") and self.parallel:
                build_args += [f"-j{self.parallel}"]

        build_temp = os.path.join(self.build_temp, ext.name)
        if not os.path.exists(build_temp):
            os.makedirs(build_temp)

        subprocess.check_call(
            ["cmake", ext.sourcedir] + cmake_args, cwd=build_temp
        )
        subprocess.check_call(
            ["cmake", "--build", "."] + build_args, cwd=build_temp
        )

class BinaryInstall(install):
    def run(self):
        self.copy_binaries()
        install.run(self)
        
    def copy_binaries(self):
        """Copy precompiled binaries or build from source"""
        # Check if we have precompiled binaries
        bin_dir = Path("codegreen/bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to copy from build directory if exists
        build_bin = Path("build/bin/codegreen")
        if build_bin.exists():
            shutil.copy2(build_bin, bin_dir / "codegreen")
            print(f"Copied binary from {build_bin}")
            
        # Copy runtime files
        runtime_src = Path("runtime")
        if runtime_src.exists():
            runtime_dst = bin_dir / "runtime"
            runtime_dst.mkdir(exist_ok=True)
            for file in runtime_src.glob("*.py"):
                shutil.copy2(file, runtime_dst)
                
        # Copy config files
        config_src = Path("config")
        if config_src.exists():
            config_dst = bin_dir / "config"
            config_dst.mkdir(exist_ok=True)
            for file in config_src.glob("*.json"):
                shutil.copy2(file, config_dst)

def should_build_from_source():
    """Determine if we should build from source or use precompiled binaries"""
    return (
        os.path.exists("CMakeLists.txt") and 
        shutil.which("cmake") is not None
    )

setup(
    name="codegreen",
    version=get_version(),
    author="Saurabhsingh Rajput",
    author_email="saurabh@dal.ca",
    description="Energy monitoring and optimization tool for code execution",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/saurabhrajput-dal/codegreen",
    project_urls={
        "Bug Tracker": "https://github.com/saurabhrajput-dal/codegreen/issues",
        "Documentation": "https://github.com/saurabhrajput-dal/codegreen/blob/main/DOCUMENTATION.md",
        "Source Code": "https://github.com/saurabhrajput-dal/codegreen",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "rich>=12.0.0",
        "psutil>=5.9.0",
        "packaging>=21.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
        "viz": [
            "matplotlib>=3.5.0",
            "pandas>=1.3.0",
            "plotly>=5.0",
        ],
        "all": [
            "matplotlib>=3.5.0",
            "pandas>=1.3.0",
            "plotly>=5.0",
            "pytest>=6.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "codegreen=codegreen.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "codegreen": [
            "config/*.conf",
            "scripts/*.py",
            "grafana/*.json",
        ],
    },
    # Custom build commands for C++ components
    ext_modules=[CMakeExtension("codegreen.core")] if should_build_from_source() else [],
    cmdclass={
        "build_ext": CMakeBuild,
        "install": BinaryInstall,
    },
    
    # Metadata
    keywords="energy, monitoring, optimization, performance, power, efficiency",
    platforms=["Linux", "macOS", "Windows"],
    license="MIT",
    zip_safe=False,
)
