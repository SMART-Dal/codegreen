# Changelog

All notable changes to CodeGreen will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-09-02

### Added
- Initial PyPI release of CodeGreen CLI tool
- Python wrapper for C++ energy measurement engine
- Cross-platform binary distribution support
- Command-line interface with `codegreen` command
- Support for Python, C++, Java, and C language measurement
- Automatic hardware sensor detection (RAPL, NVML, AMD SMI, etc.)
- SQLite database storage for measurement results
- Configuration file support with JSON format
- Rich CLI output with colors and formatting
- Installation diagnostics with `codegreen doctor` command
- System information display with `codegreen info` command

### Features
- **Energy Measurement**: Fine-grained energy consumption analysis
- **Multi-Language Support**: Python, C++, Java, C (extensible architecture)  
- **Hardware Integration**: Support for Intel RAPL, NVIDIA NVML, AMD sensors
- **Security**: Protection against SQL injection, command injection, TOCTOU races
- **Performance**: Minimal overhead, phase-separated measurement
- **Cross-Platform**: Linux, macOS, Windows support
- **Easy Installation**: Simple `pip install codegreen` workflow

### Technical Details
- C++ core engine with Python CLI wrapper
- CMake-based build system with automatic dependency detection
- SQLite database with optimized batch operations
- Tree-sitter based code analysis for accurate instrumentation
- PMT (Power Measurement Toolkit) integration for hardware sensors
- Thread-safe operations with proper resource management

### Documentation
- Comprehensive user guide (USAGE.md)
- Complete technical documentation (DOCUMENTATION.md)
- Installation instructions for all platforms
- API reference and troubleshooting guides

[Unreleased]: https://github.com/codegreen/codegreen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/codegreen/codegreen/releases/tag/v0.1.0