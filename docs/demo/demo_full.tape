# CodeGreen Terminal Demo - Fine-Grained Energy Profiling

Output demo_full.mp4
Output demo_full.gif

Require echo

# Authentic terminal with Darkside theme
Set Shell "bash"
Set FontSize 16
Set Width 1400
Set Height 900
Set Padding 30
Set Theme "Darkside"
Set Framerate 60
Set PlaybackSpeed 1
Set TypingSpeed 20ms
Set Margin 10
Set MarginFill "#4dae50"
Set BorderRadius 10
Set WindowBar Colorful


# ==============================================================================
# OPENING: Introduction
# ==============================================================================

# Start with a clean slate and show the banner instantly
Hide
Type "clear && ./print_banner.sh"
Enter
Show
Sleep 2s

Type@1ms "# ============================================================================" Enter
Type@20ms "# CodeGreen - Fine-Grained Energy Profiling for Software" Enter
Type@1ms "# ============================================================================" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Measure energy consumption with hardware-level precision" Enter
Sleep 3s
Type@20ms "# Find hotspots and optimize performance of your software" Enter
Sleep 4s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 0: Help and Installation
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 0: Exploration & Installation " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# See all available energy profiling commands" Enter
Sleep 2s
Type "codegreen --help" Enter
Sleep 3s
# At any point...
Screenshot screenshots/01_help.png
Sleep 2s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 1s

Type@20ms "# Clone and install CodeGreen" Enter
Sleep 2s
Type@20ms "cd ~/codegreen" Enter
Sleep 1.5s
Type@20ms "./install.sh" Enter
Sleep 20s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 1.5s

Type@20ms "# Initialize hardware sensors (Intel RAPL, NVIDIA, AMD)" Enter
Sleep 2s
Type "codegreen init-sensors" Enter
Sleep 8s
# At any point...
Screenshot screenshots/02_init_sensors.png
Sleep 2s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 1: Verify Installation
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 1: Installation Verification " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type "codegreen --version" Enter
Sleep 3s
# At any point...
Screenshot screenshots/03_version.png
Sleep 2s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 2: Hardware Discovery
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 2: Hardware Sensor Discovery " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Discover available hardware energy sensors" Enter
Sleep 2s
Type "codegreen info" Enter
Sleep 6s
# At any point...
Screenshot screenshots/04_info.png
Sleep 2s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 3: Live Energy Measurement
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 3: Live Energy Measurement " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Run CPU stress benchmark and measure real-time energy" Enter
Sleep 2s
Type "codegreen benchmark cpu_stress --duration 3" Enter
Sleep 8s
# At any point...
Screenshot screenshots/05_benchmark.png
Sleep 2s

Type "" Enter
Sleep 4s

# ==============================================================================
# STEP 4: Code Instrumentation & Measurement
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 4: Fine-Grained Instrumentation " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Create a Python script with multiple workloads" Enter
Sleep 2s

Type@30ms "cat > energy_profile.py << 'EOF'" Enter
Sleep 400ms
Type@30ms "import math" Enter
Sleep 200ms
Type@30ms "def compute_intensive():" Enter
Sleep 200ms
Type@30ms "    return [math.sqrt(i) * math.sin(i) for i in range(1000000)]" Enter
Sleep 200ms
Type@30ms "def light_work():" Enter
Sleep 200ms
Type@30ms "    return sum(range(100000))" Enter
Sleep 200ms
Type@30ms "compute_intensive()" Enter
Sleep 200ms
Type@30ms "light_work()" Enter
Sleep 200ms
Type@30ms "EOF" Enter
Sleep 2s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 2s

Type@20ms "# Analyze the code structure for instrumentation" Enter
Sleep 2s
Type "codegreen analyze python energy_profile.py" Enter
Sleep 5s
# At any point...
Screenshot screenshots/06_analyze.png
Sleep 2s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 2s

Type@20ms "# Measure energy consumption with function-level precision" Enter
Sleep 2s
Type "codegreen measure python energy_profile.py" Enter
Sleep 8s
# At any point...
Screenshot screenshots/07_measure.png
Sleep 2s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 2s

Type@20ms "# Export results as JSON for CI/CD integration" Enter
Sleep 2s
Type "codegreen measure python energy_profile.py --json" Enter
Sleep 8s
# At any point...
Screenshot screenshots/07_measure_json.png
Sleep 2s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 5: System Diagnostics & Configuration
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  STEP 5: System Diagnostics & Config " Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# View current configuration" Enter
Sleep 2s
Type "codegreen config --show | less" Enter
Sleep 2s
# Top of config
Screenshot screenshots/08_config_p1.png
Sleep 2s
Type " "
Sleep 1s
# Bottom of config
Screenshot screenshots/08_config_p2.png
Type "q"
Sleep 1s

Hide
Type "clear"
Enter
Show

Type "" Enter
Sleep 2s

Type "codegreen doctor" Enter
Sleep 6s
# At any point...
Screenshot screenshots/09_doctor.png
Sleep 2s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 6: Key Capabilities
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@20ms "#  CodeGreen: Key Capabilities " Enter
Sleep 3s

Type "" Enter
Sleep 1.5s

Type@20ms "# [1] Accurate: Hardware-level measurement (±2%)" Enter
Sleep 2s
Type@20ms "# [2] Low Overhead: 25-100x faster than traditional profilers" Enter
Sleep 2s
Type@20ms "# [3] Fine-Grained: Instrument functions, loops, and blocks" Enter
Sleep 2s
Type@20ms "# [4] Multi-Language: Support for Python, C/C++, Java" Enter
Sleep 2s
Type@20ms "# [5] CI/CD Ready: Export results to JSON/CSV" Enter
Sleep 3.5s

Type "" Enter
Sleep 3s

# ==============================================================================
# CLOSING
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

Type@1ms "# ============================================================================" Enter
Type@20ms "# Start Measuring and Optimizing Your Code's Energy Today" Enter
Type@1ms "# ============================================================================" Enter
Sleep 4s

Type "" Enter
Sleep 2s

Type@20ms "# Documentation: https://smart-dal.github.io/codegreen/" Enter
Sleep 3s
Type@20ms "# GitHub: https://github.com/SMART-Dal/codegreen" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type@20ms "# Measure it. Profile it. Optimize it." Enter
Sleep 4s