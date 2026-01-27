# NEMB C++ Backend Development Guide

This guide covers development of CodeGreen's NEMB (Native Energy Measurement Backend) - the high-performance C++ measurement engine.

## Table of Contents
1. [NEMB Architecture](#nemb-architecture)
2. [Building NEMB](#building-nemb)
3. [Core Components](#core-components)
4. [Developing Energy Providers](#developing-energy-providers)
5. [Testing](#testing)
6. [Best Practices](#best-practices)

## NEMB Architecture

NEMB uses a signal-generator model with background polling for ultra-low overhead energy measurement.

### Key Design Patterns

**Signal-Generator Model**: Checkpoints are lightweight timestamp markers, not synchronous reads
- Application thread: Generates checkpoint markers (~100-200ns overhead)
- Background thread: Polls hardware sensors at 10ms intervals (1ms in high-accuracy mode)
- Correlation engine: Binary search + linear interpolation to match checkpoints with energy readings

**Producer-Consumer**:
- Background thread produces energy readings into circular buffer
- Application thread generates checkpoint markers
- Correlation phase consumes both to produce attributed measurements

## Building NEMB

### Directory Structure
```
src/measurement/
├── CMakeLists.txt
├── main.cpp                          # Standalone binary entry point
├── include/nemb/
│   ├── codegreen_energy.hpp          # Public API (EnergyMeter)
│   ├── core/
│   │   ├── measurement_coordinator.hpp   # Multi-provider orchestration
│   │   └── energy_provider.hpp           # Abstract provider interface
│   ├── drivers/
│   │   ├── intel_rapl_provider.hpp       # Intel/AMD RAPL
│   │   ├── nvidia_nvml_provider.hpp      # NVIDIA GPU
│   │   └── amd_gpu_provider.hpp          # AMD ROCm
│   └── utils/
│       └── precision_timer.hpp           # High-resolution timing
└── src/nemb/
    ├── codegreen_energy.cpp          # Checkpoint implementation
    ├── config_loader.cpp              # JSON config parser
    ├── core/
    │   └── measurement_coordinator.cpp   # Background polling loop
    └── drivers/
        ├── intel_rapl_provider.cpp       # RAPL implementation
        ├── nvidia_nvml_provider.cpp      # NVML implementation
        └── amd_gpu_provider.cpp          # ROCm implementation
```

### Build Commands

Development build:
```bash
./install.sh
```

This runs CMake configuration and builds:
- `bin/codegreen`: Standalone NEMB binary
- `lib/libcodegreen-nemb.so`: Shared library
- `lib/libcodegreen-core.a`: Static core library

Manual build:
```bash
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

Debug build:
```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="-g -O0"
make
```

## Core Components

### 1. EnergyMeter (Public API)

Location: `src/measurement/include/nemb/codegreen_energy.hpp`

Public interface for checkpoint marking and correlation:

```cpp
class EnergyMeter {
public:
    EnergyMeter();
    ~EnergyMeter();

    void mark_checkpoint(const std::string& name);
    std::vector<CorrelatedCheckpoint> get_checkpoint_measurements() const;
    void start_measurement();
    void stop_measurement();

private:
    class Impl;
    std::unique_ptr<Impl> pImpl;  // PIMPL pattern
};
```

Implementation: `src/measurement/src/nemb/codegreen_energy.cpp:135-163`

Key features:
- Thread-local invocation counters (zero lock contention)
- Stack-based buffers to avoid heap allocation
- Timestamp captured BEFORE mutex lock for accuracy

### 2. MeasurementCoordinator

Location: `src/measurement/include/nemb/core/measurement_coordinator.hpp`

Orchestrates multiple energy providers and background polling:

```cpp
class MeasurementCoordinator {
public:
    MeasurementCoordinator();
    ~MeasurementCoordinator();

    bool start(const Config& config);
    void stop();
    std::vector<SynchronizedReading> get_buffered_readings();

private:
    void polling_loop();
    std::vector<std::unique_ptr<EnergyProvider>> providers_;
    std::thread polling_thread_;
    std::atomic<bool> running_;
};
```

Implementation: `src/measurement/src/nemb/core/measurement_coordinator.cpp`

Polling loop (lines 124-180):
```cpp
void MeasurementCoordinator::polling_loop() {
    auto interval = prefer_accuracy_over_speed_
        ? std::chrono::milliseconds(1)   // High-accuracy mode
        : std::chrono::milliseconds(10); // Default mode

    while (running_.load(std::memory_order_relaxed)) {
        uint64_t common_ts = timer_.get_timestamp_ns();

        // Poll all providers
        for (auto& provider : providers_) {
            auto reading = provider->get_reading();
            // Aggregate into SynchronizedReading
        }

        std::this_thread::sleep_for(interval);
    }
}
```

### 3. EnergyProvider (Abstract Interface)

Location: `src/measurement/include/nemb/core/energy_provider.hpp`

Base class for hardware-specific energy sensors:

```cpp
class EnergyProvider {
public:
    virtual ~EnergyProvider() = default;

    virtual bool init() = 0;
    virtual EnergyReading get_reading() = 0;
    virtual ProviderSpec get_spec() const = 0;
};
```

## Developing Energy Providers

### Example: Intel RAPL Provider

Location: `src/measurement/src/nemb/drivers/intel_rapl_provider.cpp`

```cpp
class IntelRAPLProvider : public EnergyProvider {
public:
    bool init() override {
        // Detect RAPL zones in /sys/class/powercap/intel-rapl*/
        auto rapl_dirs = glob("/sys/class/powercap/intel-rapl*");
        for (const auto& dir : rapl_dirs) {
            auto energy_file = dir + "/energy_uj";
            if (std::filesystem::exists(energy_file)) {
                zones_.push_back({energy_file, read_max_range(dir)});
            }
        }
        return !zones_.empty();
    }

    EnergyReading get_reading() override {
        uint64_t total_uj = 0;

        // Read all RAPL zones
        for (auto& zone : zones_) {
            uint64_t current_uj = read_sysfs_uint64(zone.path);

            // Handle wraparound (max_range)
            if (current_uj < zone.last_reading) {
                zone.wrapped_count++;
            }
            zone.last_reading = current_uj;

            total_uj += current_uj + (zone.wrapped_count * zone.max_range);
        }

        // Use CLOCK_MONOTONIC to match PrecisionTimer
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);

        return {
            .timestamp_ns = ts.tv_sec * 1000000000ULL + ts.tv_nsec,
            .energy_joules = total_uj / 1e6
        };
    }

    ProviderSpec get_spec() const override {
        return {"intel_rapl", "Intel RAPL CPU energy"};
    }

private:
    struct RAPLZone {
        std::string path;
        uint64_t max_range;
        uint64_t last_reading = 0;
        uint64_t wrapped_count = 0;
    };
    std::vector<RAPLZone> zones_;
};
```

### Adding a New Provider

1. Create header in `src/measurement/include/nemb/drivers/your_provider.hpp`
2. Implement `EnergyProvider` interface
3. Handle counter wraparound if applicable
4. Use `CLOCK_MONOTONIC` for timestamps
5. Register in `detect_available_providers()` in measurement_coordinator.cpp

Example registration:
```cpp
std::vector<std::unique_ptr<EnergyProvider>> detect_available_providers() {
    std::vector<std::unique_ptr<EnergyProvider>> providers;

    auto rapl = std::make_unique<IntelRAPLProvider>();
    if (rapl->init()) providers.push_back(std::move(rapl));

    auto nvml = std::make_unique<NvidiaGPUProvider>();
    if (nvml->init()) providers.push_back(std::move(nvml));

    // Add your provider here
    auto custom = std::make_unique<CustomProvider>();
    if (custom->init()) providers.push_back(std::move(custom));

    return providers;
}
```

## Testing

### Unit Tests

Location: `tests/cpp/` (create if needed)

Example test structure:
```cpp
#include <gtest/gtest.h>
#include "nemb/codegreen_energy.hpp"

TEST(EnergyMeterTest, CheckpointFormat) {
    EnergyMeter meter;
    meter.start_measurement();
    meter.mark_checkpoint("test_function");
    meter.stop_measurement();

    auto results = meter.get_checkpoint_measurements();
    ASSERT_FALSE(results.empty());

    // Verify checkpoint format: name#inv_N_tTHREADID
    EXPECT_TRUE(results[0].checkpoint_name.find("#inv_1_t") != std::string::npos);
}

TEST(IntelRAPLProvider, WrapAround) {
    IntelRAPLProvider provider;
    ASSERT_TRUE(provider.init());

    // Simulate counter wraparound
    auto r1 = provider.get_reading();
    // Force wraparound by manipulating internal state
    auto r2 = provider.get_reading();

    EXPECT_GT(r2.energy_joules, r1.energy_joules);
}
```

### Integration Tests

Test full measurement workflow:
```bash
# Build and run test program
cd tests/integration
cmake .. && make
./test_fibonacci_measurement

# Verify checkpoint generation
./test_recursive_calls

# Test multi-threading
./test_concurrent_checkpoints
```

### Benchmark Tests

Measure checkpoint overhead:
```cpp
#include <benchmark/benchmark.h>

static void BM_CheckpointOverhead(benchmark::State& state) {
    EnergyMeter meter;
    meter.start_measurement();

    for (auto _ : state) {
        meter.mark_checkpoint("bench_function");
    }

    meter.stop_measurement();
}
BENCHMARK(BM_CheckpointOverhead);
```

Expected results:
- Checkpoint marking: ~100-200 ns per call
- Background polling: <0.1% CPU utilization

## Best Practices

### Memory Management

1. Use RAII for resource management:
```cpp
class MeasurementSession {
public:
    MeasurementSession(EnergyMeter& meter) : meter_(meter) {
        meter_.start_measurement();
    }
    ~MeasurementSession() {
        meter_.stop_measurement();
    }
private:
    EnergyMeter& meter_;
};
```

2. Avoid heap allocations in hot paths:
```cpp
// Good: Stack-based buffer in mark_checkpoint()
thread_local char enhanced_buffer[512];
snprintf(enhanced_buffer, sizeof(enhanced_buffer), "%s#inv_%u_t%zu", ...);

// Bad: Heap allocation
std::string name = format("%s#inv_%u_t%zu", ...);  // malloc overhead
```

### Thread Safety

1. Use thread_local for zero-lock performance:
```cpp
void mark_checkpoint(const std::string& name) {
    thread_local std::unordered_map<std::string, uint32_t> invocation_counters;
    thread_local size_t thread_hash = compute_thread_hash();

    uint32_t inv = ++invocation_counters[name];  // No lock needed
}
```

2. Use atomic operations for cross-thread communication:
```cpp
std::atomic<bool> running_{false};
std::atomic<size_t> buffer_write_index_{0};

// Use acquire/release semantics
if (!buffer_full_.load(std::memory_order_acquire)) {
    // Safe to read buffer
}
```

3. Minimize critical sections:
```cpp
// Capture timestamp BEFORE lock
uint64_t ts = timer_.get_timestamp_ns();

// Lock only for marker storage
std::lock_guard<std::mutex> lock(markers_mutex_);
markers_.push_back({name, ts});
```

### Clock Synchronization

Always use CLOCK_MONOTONIC for consistency:
```cpp
// In PrecisionTimer
struct timespec ts;
clock_gettime(CLOCK_MONOTONIC, &ts);
return ts.tv_sec * 1000000000ULL + ts.tv_nsec;

// In energy provider (must match!)
struct timespec ts;
clock_gettime(CLOCK_MONOTONIC, &ts);  // Same clock source
```

### Error Handling

Use exceptions for initialization failures:
```cpp
bool IntelRAPLProvider::init() {
    if (zones_.empty()) {
        // Log warning but don't throw - provider just unavailable
        return false;
    }
    return true;
}
```

Use return codes for runtime failures:
```cpp
std::optional<EnergyReading> get_reading() {
    try {
        // Attempt reading
        return EnergyReading{...};
    } catch (const std::exception& e) {
        return std::nullopt;  // Provider temporarily unavailable
    }
}
```

## Debugging

Enable debug logging:
```cpp
// In config.json
{
    "measurement": {
        "log_level": "debug",
        "log_file": "/tmp/nemb_debug.log"
    }
}
```

Use gdb for checkpoint issues:
```bash
gdb --args ./bin/codegreen measure python test.py
(gdb) break EnergyMeter::Impl::mark_checkpoint
(gdb) run
(gdb) print markers_
```

Profile with perf:
```bash
perf record -g ./bin/codegreen measure python app.py
perf report
```

## References

- Implementation: `src/measurement/src/nemb/`
- Public API: `src/measurement/include/nemb/codegreen_energy.hpp`
- Architecture: `docs/design/architecture.md`
- Checkpointing: `docs/architecture/checkpointing-architecture.md`
- Theory: `theory.txt` sections 2-5
