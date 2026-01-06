# CodeGreen Usage Guide

A comprehensive guide to building, installing, configuring, and using CodeGreen for energy-aware software development.

> **Note**: This document is auto-generated from the official commands reference.

## 📋 Table of Contents

1. [Installation & Setup](#1-installation--setup)
2. [Global Options](#2-global-options--flags)
3. [Measure Energy](#3-command-measure---measure-energy-consumption)
4. [Analyze Code](#4-command-analyze---analyze-code-structure)
5. [System Initialization](#5-command-init---initialize-system)
6. [System Info](#6-command-info---system-information)
7. [Diagnostics](#7-command-doctor---diagnostics)
8. [Benchmarks](#8-command-benchmark---built-in-benchmarks)
9. [Validation](#9-command-validate---validation-tests)
10. [Configuration](#10-command-config---configuration-management)

---

## 1. Installation & Setup

### Prerequisites
```bash
sudo apt-get install build-essential cmake pkg-config
sudo apt-get install libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev
```

### Install CodeGreen
```bash
git clone https://github.com/codegreen/codegreen.git
cd codegreen
./install.sh
```

### Verify Installation
```bash
codegreen --version
codegreen info
```

### Enable Energy Measurements
Requires sudo permissions for hardware sensor access:
```bash
sudo codegreen init-sensors
# OR
codegreen init --interactive
```

---

## 2. Global Options & Flags

All commands support these global options:

*   `--debug`: Enable debug output with detailed logging
*   `--config PATH`: Use custom configuration file
*   `--version, -v`: Show version and exit
*   `--log-level LEVEL`: Set logging level (DEBUG|INFO|WARNING|ERROR)
*   `--help, -h`: Show help message

**Examples:**
```bash
codegreen --debug measure python script.py
codegreen --config ./custom.json measure python app.py
```

---

## 3. Command: `measure` - Measure Energy Consumption

Instruments code, executes it, and measures energy consumption using hardware sensors (Intel RAPL, NVIDIA NVML, AMD).

**Synopsis:**
```bash
codegreen measure [OPTIONS] LANGUAGE SCRIPT [ARGS...]
```

**Supported Languages:** python, cpp, c, java

**Options:**
*   `-o, --output PATH`: Save results to file (JSON format)
*   `-s, --sensors SENSOR`: Sensors to use (rapl, nvidia, amd_gpu, amd_cpu)
*   `-p, --precision LEVEL`: low (100ms), medium (10ms), high (1ms)
*   `-t, --timeout SECONDS`: Execution timeout
*   `--verbose`: Show detailed output
*   `--json`: Output results in JSON format
*   `--no-cleanup`: Keep temporary instrumented files
*   `--instrumented`: Script is already instrumented (skip instrumentation step)

**Examples:**
```bash
# Basic measurement
codegreen measure python script.py

# High precision with specific sensors
codegreen measure python ml_train.py --precision high --sensors rapl nvidia

# Measure C++ program
codegreen measure cpp main.cpp
```

---

## 4. Command: `analyze` - Analyze Code Structure

Performs static analysis using Tree-sitter AST parsing to identify instrumentation points. No code execution - pure analysis.

**Synopsis:**
```bash
codegreen analyze [OPTIONS] LANGUAGE SCRIPT
```

**Options:**
*   `-o, --output PATH`: Save analysis to file
*   `--verbose`: Show detailed instrumentation points
*   `--suggestions`: Show optimization suggestions
*   `--save-instrumented`: Save instrumented code to current directory
*   `--output-dir PATH`: Directory for instrumented code

**Examples:**
```bash
# Basic analysis
codegreen analyze python script.py

# Save instrumented code for review
codegreen analyze python module.py --save-instrumented --output-dir ./instrumented
```

---

## 5. Command: `init` - Initialize System

Comprehensive system initialization: detects hardware, configures sensors, sets permissions, generates optimized configuration.

**Synopsis:**
```bash
codegreen init [OPTIONS]
```

**Options:**
*   `--interactive`: Interactive setup with prompts
*   `--auto-detect-only`: Auto-detect only, no prompts
*   `--sensors SENSOR`: Specify sensors to initialize
*   `--force`: Overwrite existing configuration

---

## 6. Command: `info` - System Information

Display CodeGreen installation, hardware sensors, and system information.

**Synopsis:**
```bash
codegreen info [OPTIONS]
```

**Output Includes:**
*   CodeGreen version and paths
*   Available sensors (RAPL, NVIDIA, AMD)
*   Sensor permissions status
*   Python runtime availability
*   Language support status

---

## 7. Command: `doctor` - Diagnostics

Comprehensive diagnostics to identify and fix common issues.

**Synopsis:**
```bash
codegreen doctor [OPTIONS]
```

**Options:**
*   `--verbose`: Show detailed diagnostic output
*   `--fix`: Attempt to fix issues automatically (e.g., permissions)

---

## 8. Command: `benchmark` - Built-in Benchmarks

Measure energy consumption using built-in synthetic workloads. Useful for validating sensor accuracy and system calibration.

**Synopsis:**
```bash
codegreen benchmark [OPTIONS] WORKLOAD
```

**Workloads:** cpu_stress, memory_stress, mixed, gpu_compute

**Options:**
*   `--duration SECONDS`: Duration of benchmark (default: 10)
*   `--intensity LEVEL`: Workload intensity (low|medium|high)
*   `--output PATH`: Save results to file

**Example:**
```bash
codegreen benchmark cpu_stress --duration 5
```

---

## 9. Command: `validate` - Validation Tests

Validate measurement accuracy by comparing CodeGreen measurements against native tools (perf, nvidia-smi, etc). **Requires root.**

**Synopsis:**
```bash
codegreen validate [OPTIONS]
```

**Options:**
*   `--quick`: Quick validation (30 seconds)
*   `--full`: Full validation suite (5 minutes)
*   `--tolerance PERCENT`: Acceptable error tolerance (default: 10%)

---

## 10. Command: `config` - Configuration Management

View, edit, and manage CodeGreen configuration.

**Synopsis:**
```bash
codegreen config [OPTIONS]
```

**Options:**
*   `--show`: Display current configuration
*   `--edit`: Open configuration in editor
*   `--reset`: Reset to default configuration
*   `--validate`: Validate configuration syntax

---

**Configuration File Locations:**
1. `./codegreen.json` (Local override)
2. `~/.codegreen/codegreen.json` (User config)
3. `/etc/codegreen/codegreen.json` (System config)