#!/usr/bin/env python3
"""
CodeGreen Setup Script
Energy-aware software development tool with C++ components
"""

from setuptools import setup, find_packages
from cmake_build_extension import BuildExtension, CMakeExtension
import os

# Read version from pyproject.toml
def get_version():
    import re
    with open("pyproject.toml", "r") as f:
        content = f.read()
        match = re.search(r'version = "([^"]+)"', content)
        if match:
            return match.group(1)
    return "0.1.0"

# Read long description
def get_long_description():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

# CMake configuration options
cmake_options = [
    # Enable all PMT sensors
    "-DPMT_BUILD_RAPL=ON",
    "-DPMT_BUILD_NVML=ON", 
    "-DPMT_BUILD_NVIDIA=ON",
    "-DPMT_BUILD_TEGRA=ON",
    "-DPMT_BUILD_AMD_SMI=ON",
    "-DPMT_BUILD_ROCM=ON",
    "-DPMT_BUILD_POWERSENSOR=ON",
    "-DPMT_BUILD_LIKWID=ON",
    "-DPMT_BUILD_DUMMY=ON",
    
    # Build shared libraries
    "-DBUILD_SHARED_LIBS=ON",
    
    # Enable Python bindings
    "-DBUILD_PYTHON_BINDINGS=ON",
    
    # Set install prefix for Python package
    "-DCMAKE_INSTALL_PREFIX=codegreen",
]

# Add CUDA paths if available
if os.path.exists("/usr/local/cuda"):
    cmake_options.extend([
        "-DCUDAToolkit_ROOT=/usr/local/cuda",
        "-DCMAKE_PREFIX_PATH=/usr/local/cuda"
    ])

setup(
    name="codegreen",
    version=get_version(),
    author="CodeGreen Team",
    author_email="team@codegreen.dev",
    description="Energy-aware software development tool",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/codegreen/codegreen",
    packages=find_packages(),
    py_modules=['codegreen_runtime'],
    python_requires=">=3.8",
    install_requires=[
        "typer>=0.17.0",
        "rich>=12.0.0", 
        "pydantic>=1.10.0",
        "psutil>=5.9.0",
        "packaging>=21.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "codegreen=src.cli.cli:main_cli",
        ],
    },
    # Include language configurations and runtime files
    package_data={
        "src.instrumentation": ["configs/*.json"],
    },
    # Include the CLI binary and runtime files
    data_files=[
        ('bin', ['bin/codegreen']),
        ('bin/runtime', ['src/instrumentation/language_runtimes/python/codegreen_runtime.py']),
        ('config', ['config/codegreen.json']),
    ],
    # C++ extensions for integrated builds
    ext_modules=[
        CMakeExtension(
            name="codegreen_cpp",
            install_prefix="codegreen",
            cmake_configure_options=cmake_options,
        ),
    ],
    cmdclass={
        "build_ext": BuildExtension,
    },
    zip_safe=False,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: C++",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: System :: Monitoring",
    ],
    keywords="energy monitoring, performance, sustainability, green computing",
    project_urls={
        "Bug Reports": "https://github.com/codegreen/codegreen/issues",
        "Source": "https://github.com/codegreen/codegreen",
        "Documentation": "https://codegreen.readthedocs.io/",
    },
)
