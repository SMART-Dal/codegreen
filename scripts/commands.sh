#!/bin/bash
# CodeGreen Commands Reference Script
# Run this after install.sh to see all available commands and their usage

set -e

echo "CodeGreen Commands Reference"
echo "============================"
echo ""

# Check if codegreen is available
if ! command -v codegreen >/dev/null 2>&1; then
    echo "Error: codegreen command not found. Please run install.sh first."
    exit 1
fi

echo "1. Basic Information Commands"
echo "-----------------------------"

echo "Display version and help:"
codegreen --version
echo ""

echo "Show all available commands:"
codegreen --help
echo ""

echo "Display system information:"
codegreen info
echo ""

echo "2. System Setup and Configuration"
echo "----------------------------------"

echo "Initialize CodeGreen (interactive setup):"
echo "codegreen init --interactive"
echo ""

echo "Initialize with auto-detection only:"
echo "codegreen init --auto-detect-only"
echo ""

echo "Initialize sensors for energy measurement:"
echo "codegreen init-sensors"
echo ""

echo "Run system diagnostics:"
codegreen doctor
echo ""

echo "3. Configuration Management"
echo "---------------------------"

echo "Show current configuration:"
codegreen config --show
echo ""

echo "Edit configuration (placeholder):"
echo "codegreen config --edit"
echo ""

echo "Reset configuration (placeholder):"
echo "codegreen config --reset"
echo ""

echo "4. Code Analysis Commands"
echo "-------------------------"

# Create a sample Python file for testing
cat > /tmp/sample_script.py << 'EOF'
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

if __name__ == "__main__":
    print("Factorial of 5:", factorial(5))
    print("Fibonacci of 8:", fibonacci(8))
EOF

echo "Analyze Python code without execution:"
codegreen analyze python /tmp/sample_script.py
echo ""

echo "Analyze with custom output directory:"
echo "codegreen analyze python /tmp/sample_script.py --output /tmp/analysis_output"
echo ""

echo "5. Energy Measurement Commands"
echo "------------------------------"

echo "Measure energy consumption of Python script:"
echo "codegreen measure python /tmp/sample_script.py"
echo ""

echo "Measure with custom configuration:"
echo "codegreen measure python /tmp/sample_script.py --config /path/to/config.json"
echo ""

echo "Measure with specific output file:"
echo "codegreen measure python /tmp/sample_script.py --output /tmp/energy_results.json"
echo ""

echo "6. Benchmark and Workload Testing"
echo "----------------------------------"

echo "Run CPU stress benchmark (3 seconds):"
codegreen benchmark cpu_stress --duration 3
echo ""

echo "Run memory stress benchmark:"
echo "codegreen benchmark memory_stress --duration 5"
echo ""

echo "Measure specific workload energy consumption:"
codegreen measure-workload --duration 3 --workload cpu_stress
echo ""

echo "Measure memory workload:"
echo "codegreen measure-workload --duration 5 --workload memory_stress"
echo ""

echo "7. Validation and Testing"
echo "-------------------------"

echo "Validate measurement accuracy:"
echo "codegreen validate --quick"
echo ""

echo "Full validation with detailed output:"
echo "codegreen validate --verbose --duration 10"
echo ""

echo "8. Advanced Usage Examples"
echo "---------------------------"

echo "Example 1: Complete workflow for a Python project"
echo "# Initialize system"
echo "codegreen init --auto-detect-only"
echo "# Analyze code structure"
echo "codegreen analyze python my_script.py --output ./analysis"
echo "# Measure energy consumption"
echo "codegreen measure python my_script.py --output ./energy_results.json"
echo "# Validate measurements"
echo "codegreen validate --quick"
echo ""

echo "Example 2: Benchmark and compare different algorithms"
echo "# Test baseline performance"
echo "codegreen benchmark cpu_stress --duration 10"
echo "# Measure algorithm A"
echo "codegreen measure python algorithm_a.py --output results_a.json"
echo "# Measure algorithm B"
echo "codegreen measure python algorithm_b.py --output results_b.json"
echo ""

echo "Example 3: Development workflow with diagnostics"
echo "# Check system status"
echo "codegreen doctor"
echo "# Show current configuration"
echo "codegreen config --show"
echo "# Analyze and measure code"
echo "codegreen analyze python my_app.py"
echo "codegreen measure python my_app.py"
echo ""

echo "9. Language-Specific Examples"
echo "------------------------------"

echo "Python examples:"
echo "codegreen analyze python script.py"
echo "codegreen measure python script.py arg1 arg2"
echo ""

echo "C++ examples (when supported):"
echo "codegreen analyze cpp main.cpp"
echo "codegreen measure cpp ./compiled_program"
echo ""

echo "Java examples (when supported):"
echo "codegreen analyze java Main.java"
echo "codegreen measure java Main"
echo ""

echo "10. Debug and Development Options"
echo "---------------------------------"

echo "Run with debug output:"
echo "codegreen --debug measure python script.py"
echo ""

echo "Use custom configuration file:"
echo "codegreen --config ./my_config.json measure python script.py"
echo ""

echo "Set custom log level:"
echo "codegreen --log-level DEBUG info"
echo ""

# Cleanup
rm -f /tmp/sample_script.py

echo ""
echo "Commands Reference Complete"
echo "==========================="
echo ""
echo "For detailed help on any command, use:"
echo "  codegreen COMMAND --help"
echo ""
echo "Example:"
echo "  codegreen measure --help"
echo "  codegreen benchmark --help"
echo "  codegreen analyze --help"
echo ""
echo "Configuration:"
echo "=============="
echo "Default config: ./config/codegreen.json"
echo "User config: ~/.codegreen/codegreen.json"
echo ""
echo "The config file controls:"
echo "- Energy measurement settings (RAPL, NVML, AMD sensors)"
echo "- Language-specific configurations (Python, C++, Java)"
echo "- Performance optimization parameters"
echo "- Database and logging settings"
echo "- Developer debug options"
echo ""
echo "Key configuration sections:"
echo "- measurement.nemb.providers: Enable/disable energy sensors"
echo "- measurement.timing: Measurement precision settings"
echo "- languages.python.executable: Python interpreter path"
echo "- developer.debug_mode: Enable detailed logging"
echo "- performance: Threading and optimization settings"
echo ""
echo "Documentation: https://github.com/codegreen/codegreen"