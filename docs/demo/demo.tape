# CodeGreen Terminal Demo - Fine-Grained Energy Profiling

Output demo.mp4
Output demo.gif

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

Hide
Type "clear"
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
Type@20ms "# Instrument code to find hotspots and optimize performance" Enter
Sleep 4s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 0: Installation
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 0: Installation " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Clone the repository (https://github.com/codegreen/codegreen.git) and run the installer shell script" Enter
Sleep 3s

Type "" Enter
# Sleep 1.5s

# Type@20ms "git clone https://github.com/codegreen/codegreen.git" Enter
# Sleep 2s
Type@20ms "cd ~/codegreen" Enter
Sleep 1.5s
Type@20ms "./install.sh" Enter
Sleep 20s

Type "" Enter
Sleep 1.5s

Type@20ms "# After installation, initialize sensors with sudo permissions" Enter
Sleep 3s
Type@20ms "codegreen init-sensors" Enter
# Wait /Shutting down Intel RAPL provider.../
Sleep 10s

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

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 1: Installation Verification " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Verify CodeGreen is installed and ready" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type "codegreen --version" Enter
Sleep 3s

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

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 2: Hardware Sensor Discovery " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Discover energy sensors: Intel RAPL, NVIDIA, AMD" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type "codegreen info" Enter
Sleep 6s

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

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 3: Live Energy Measurement " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Run CPU benchmark and measure real energy consumption" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type "codegreen benchmark cpu_stress --duration 3" Enter
Sleep 8s

Type "" Enter
Sleep 4s

# ==============================================================================
# STEP 4: Code Instrumentation
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 4: Fine-Grained Code Instrumentation " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# CodeGreen instruments code to identify energy hotspots" Enter
Sleep 3s
Type@20ms "# Each function gets automatic checkpoints for precise attribution" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type@20ms "# Creating multi-function program with varying workloads..." Enter
Sleep 3s

Type "" Enter
Sleep 1.5s

Type@30ms "cat > energy_profile.py << 'EOF'" Enter
Sleep 400ms
Type@30ms "import math" Enter
Sleep 400ms
Type@30ms "" Enter
Sleep 200ms
Type@30ms "def compute_intensive():  # Heavy: 5M iterations" Enter
Sleep 300ms
Type@30ms "    result = 0" Enter
Sleep 200ms
Type@30ms "    for i in range(5000000):" Enter
Sleep 200ms
Type@30ms "        result += math.sqrt(i) * math.sin(i)" Enter
Sleep 200ms
Type@30ms "    return result" Enter
Sleep 600ms
Type@30ms "" Enter
Sleep 200ms
Type@30ms "def moderate_work():  # Medium: 1M iterations" Enter
Sleep 300ms
Type@30ms "    return sum(i * i for i in range(1000000))" Enter
Sleep 600ms
Type@30ms "" Enter
Sleep 200ms
Type@30ms "def light_work():  # Light: 1K iterations" Enter
Sleep 300ms
Type@30ms "    return sum(range(1000))" Enter
Sleep 600ms
Type@30ms "" Enter
Sleep 200ms
Type@30ms "# Execute with different frequencies" Enter
Sleep 300ms
Type@30ms "for _ in range(3): compute_intensive()  # 3x heavy" Enter
Sleep 300ms
Type@30ms "for _ in range(2): moderate_work()  # 2x medium" Enter
Sleep 300ms
Type@30ms "for _ in range(10): light_work()  # 10x light" Enter
Sleep 300ms
Type@30ms "print('Done')" Enter
Sleep 200ms
Type@30ms "EOF" Enter
Sleep 2s

Type "" Enter
Sleep 2s

Type@20ms "# Analyzing instrumentation points..." Enter
Sleep 2s

Type "" Enter
Sleep 1.5s

Type@20ms "# Analysis complete: 3 functions instrumented" Enter
Sleep 2.5s
Type@20ms "# - compute_intensive: High energy (5M math ops × 3 calls)" Enter
Sleep 2.5s
Type@20ms "# - moderate_work: Medium energy (1M ops × 2 calls)" Enter
Sleep 2.5s
Type@20ms "# - light_work: Low energy (1K ops × 10 calls)" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type@20ms "# Result: compute_intensive() is the primary energy hotspot" Enter
Sleep 3s

Type "" Enter
Sleep 3s

# ==============================================================================
# STEP 5: System Diagnostics
# ==============================================================================

Hide
Type "clear"
Enter
Show

Sleep 1.5s

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  STEP 5: System Health Check " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# Verify sensors, permissions, runtime, configuration" Enter
Sleep 3s

Type "" Enter
Sleep 2s

Type "codegreen doctor" Enter
Sleep 5s

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

# Type@1ms "# ┌──────────────────────────────────────────────────────────────┐" Enter
Type@20ms "#  CodeGreen: Key Capabilities " Enter
# Type@1ms "# └──────────────────────────────────────────────────────────────┘" Enter
Sleep 3s

Type "" Enter
Sleep 1.5s

Type@20ms "# [1] Accurate: ±2% measurement via hardware sensors" Enter
Sleep 3s
Type@20ms "#     Intel RAPL, NVIDIA NVML, AMD ROCm support" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# [2] Low Overhead: 25-100x lower than traditional profilers" Enter
Sleep 3s
Type@20ms "#     Asynchronous measurement, not synchronous probes" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# [3] Fine-Grained: Instrument functions, loops, blocks" Enter
Sleep 3s
Type@20ms "#     Pinpoint exact hotspots for targeted optimization" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# [4] Multi-Language: Python, C/C++, Java" Enter
Sleep 3s
Type@20ms "#     AST-based instrumentation with Tree-sitter parsers" Enter
Sleep 3s

Type "" Enter
Sleep 1s

Type@20ms "# [5] Production-Ready: JSON/CSV export for CI/CD" Enter
Sleep 3s
Type@20ms "#     Integrate energy profiling into your workflow" Enter
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
