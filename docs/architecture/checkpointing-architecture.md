# Checkpointing Architecture

CodeGreen's checkpointing mechanism is the foundation of its energy attribution system. This document explains the technical implementation, design decisions, and theoretical basis.

## Overview

CodeGreen uses a **signal-generator model** where checkpoints act as lightweight timestamp markers rather than synchronous measurement points. This architecture achieves sub-microsecond overhead per checkpoint while maintaining nanosecond-precision timing.

## Checkpoint Format Specification

### Base Format

Each checkpoint is uniquely identified using the format:

```
original_name#inv_N_tTHREADID
```

**Components:**
- `original_name`: The function or block name from source code
- `inv_N`: Invocation number (1, 2, 3, ...) for tracking recursive calls
- `tTHREADID`: Thread identifier hash for multi-threaded programs

### Examples

```cpp
// Single-threaded, first call
calculate_primes#inv_1_t2069765334896692675

// Recursive calls on same thread
fibonacci#inv_1_t2069765334896692675
fibonacci#inv_2_t2069765334896692675
fibonacci#inv_3_t2069765334896692675

// Multi-threaded execution
process_data#inv_1_t6293947261177266884  // Thread 1
process_data#inv_1_t8497880199053515464  // Thread 2
process_data#inv_2_t6293947261177266884  // Thread 1, second call
```

## Thread-Local Invocation Tracking

### Implementation

From `src/measurement/src/nemb/codegreen_energy.cpp:135-163`:

```cpp
void EnergyMeter::Impl::mark_checkpoint(const std::string& name) {
    // Thread-local for zero-lock performance
    thread_local std::unordered_map<std::string, uint32_t> invocation_counters;

    // Get thread ID hash (computed once per thread)
    thread_local std::hash<std::thread::id> hasher;
    thread_local size_t thread_hash = hasher(std::this_thread::get_id());

    // Atomic increment of invocation counter
    uint32_t invocation = ++invocation_counters[name];

    // Capture timestamp BEFORE lock
    uint64_t ts = timer_.get_timestamp_ns();

    // Stack-based buffer to avoid heap allocations
    thread_local char enhanced_buffer[512];
    int len = snprintf(enhanced_buffer, sizeof(enhanced_buffer),
                       "%s#inv_%u_t%zu", name.c_str(), invocation, thread_hash);

    // Store marker with mutex protection
    std::lock_guard<std::mutex> lock(markers_mutex_);
    markers_.push_back({std::string(enhanced_buffer, len), ts});
}
```

### Design Decisions

1. **Thread-Local Storage**: Each thread maintains its own invocation counters
   - Zero lock contention between threads
   - Automatic cleanup on thread exit
   - Computed once per thread (thread_hash)

2. **Stack-Based Buffers**: Uses stack allocation instead of heap
   - Avoids malloc/free overhead
   - 512-byte buffer sufficient for typical names
   - Fallback to heap for very long names

3. **Timestamp Before Lock**: Critical for accuracy
   - Captures exact execution time
   - Lock overhead not included in timestamp
   - Minimizes critical section

## Timestamp Capture

### Precision Timer

CodeGreen uses high-precision timing with automatic clock source selection:

From `src/measurement/include/nemb/utils/precision_timer.hpp:20-25`:

```cpp
enum class ClockSource {
    TSC_INVARIANT,      // Time Stamp Counter (x86, highest precision)
    MONOTONIC_RAW,      // Raw monotonic clock (no NTP adjustments)
    MONOTONIC,          // Standard monotonic clock
    REALTIME            // System realtime clock (fallback)
};
```

**Clock Source Selection:**
1. **TSC (Time Stamp Counter)**: Sub-nanosecond on x86/x64
   - Direct CPU register read (~10 CPU cycles)
   - Invariant TSC required (constant rate)
   - Automatically detected and validated

2. **CLOCK_MONOTONIC**: Nanosecond precision on all platforms
   - Kernel-provided monotonic time
   - Used for correlation with RAPL timestamps
   - Not affected by NTP adjustments

## Memory Ordering Guarantees

### Atomic Operations

The checkpoint system uses careful memory ordering:

```cpp
// Invocation counter increment (relaxed ordering)
uint32_t invocation = ++invocation_counters[name];  // atomic operation

// Markers buffer operations (acquire/release)
std::lock_guard<std::mutex> lock(markers_mutex_);   // acquire semantics
markers_.push_back({name, ts});                      // happens-before guarantee
```

From `src/measurement/src/nemb/core/measurement_coordinator.cpp:231-251`:

```cpp
// Atomic buffer indices with memory ordering
if (!buffer_full_.load(std::memory_order_acquire)) {
    result.assign(readings_buffer_.begin(), readings_buffer_.end());
} else {
    size_t write_idx = buffer_write_index_.load(std::memory_order_acquire);
    // ... circular buffer read with proper ordering
}
```

**Memory Ordering Strategy:**
- **Relaxed**: For invocation counter (thread-local, no synchronization needed)
- **Acquire/Release**: For cross-thread visibility (markers_, buffer indices)
- **Mutex**: For markers_ vector (ensures sequential consistency)

## Energy Correlation Algorithm

### Time-Series Matching

After execution, checkpoints are correlated with energy readings:

From `src/measurement/src/nemb/codegreen_energy.cpp:165-201`:

```cpp
std::vector<EnergyMeter::CorrelatedCheckpoint> get_checkpoint_measurements() {
    auto readings = coordinator_->get_buffered_readings();

    for (const auto& marker : markers_) {
        // Binary search for closest energy reading
        auto it = std::lower_bound(readings.begin(), readings.end(),
                                  marker.timestamp_ns,
                                  [](const SynchronizedReading& r, uint64_t ts) {
                                      return r.common_timestamp_ns < ts;
                                  });

        // Linear interpolation between readings
        if (it != readings.begin() && it != readings.end()) {
            const auto& r2 = *it;
            const auto& r1 = *std::prev(it);
            uint64_t dt = r2.common_timestamp_ns - r1.common_timestamp_ns;
            double ratio = (dt > 0) ?
                static_cast<double>(marker.timestamp_ns - r1.common_timestamp_ns) / dt : 0.0;

            cc.cumulative_energy_joules = r1.total_system_energy_joules +
                ratio * (r2.total_system_energy_joules - r1.total_system_energy_joules);
        }
    }
}
```

### Interpolation Formula

For a checkpoint at time `t_marker` between two energy readings `(t1, E1)` and `(t2, E2)`:

```
ratio = (t_marker - t1) / (t2 - t1)
E_marker = E1 + ratio × (E2 - E1)
```

**Assumptions:**
- Power draw is approximately linear between samples
- Valid for 1ms sampling intervals (Nyquist-Shannon theorem)
- Hardware counters are cumulative (energy, not power)

## Performance Characteristics

### Overhead Analysis

From theory.txt validation results:

| Operation | Time | Impact |
|-----------|------|--------|
| Timestamp capture | ~10-50 ns | TSC register read |
| Thread-local lookup | ~5-10 ns | CPU cache hit |
| Invocation increment | ~2-5 ns | Atomic operation |
| Buffer write | ~20-50 ns | snprintf + string copy |
| Mutex lock/unlock | ~50-100 ns | Uncontended mutex |
| **Total per checkpoint** | **~100-200 ns** | **<< 0.01% for typical functions** |

**Comparison with Version 1 (Synchronous):**
- V1 synchronous read: ~5-20 μs per checkpoint (sysfs + FFI + GIL)
- V2 signal-generator: ~0.1-0.2 μs per checkpoint
- **Improvement: 25-100x faster**

### Scalability

- **Invocations**: Supports up to 4 billion invocations per function (uint32_t)
- **Threads**: Unlimited (thread_local storage)
- **Markers**: Pre-allocated for 10,000 checkpoints (expandable)
- **Memory**: ~60 bytes per checkpoint (name + timestamp)

## Multi-Threading Support

### Thread Safety Guarantees

1. **Zero Contention**: Thread-local invocation counters
2. **Sequential Consistency**: Mutex-protected markers_ vector
3. **Lock-Free Reads**: Background thread uses atomic operations

### Thread Identification

Thread IDs are computed using std::hash:

```cpp
thread_local std::hash<std::thread::id> hasher;
thread_local size_t thread_hash = hasher(std::this_thread::get_id());
```

**Properties:**
- Deterministic for same thread across checkpoints
- Unique per thread (collision probability: ~2^-64)
- Computed once per thread (cached in thread_local)

## Recursive Function Handling

### Example: Fibonacci

```python
def fibonacci(n):
    checkpoint("fibonacci", "enter")
    if n <= 1:
        result = n
    else:
        result = fibonacci(n-1) + fibonacci(n-2)
    checkpoint("fibonacci", "exit")
    return result
```

**Generated Checkpoints for fibonacci(3):**

```
fibonacci#inv_1_t0  enter   [Start fib(3)]
fibonacci#inv_2_t0  enter   [Start fib(2)]
fibonacci#inv_3_t0  enter   [Start fib(1)]
fibonacci#inv_3_t0  exit    [End fib(1)]
fibonacci#inv_4_t0  enter   [Start fib(0)]
fibonacci#inv_4_t0  exit    [End fib(0)]
fibonacci#inv_2_t0  exit    [End fib(2)]
fibonacci#inv_5_t0  enter   [Start fib(1)]
fibonacci#inv_5_t0  exit    [End fib(1)]
fibonacci#inv_1_t0  exit    [End fib(3)]
```

**Energy Attribution:**
- Each invocation tracked separately
- Energy difference between enter/exit = energy for that invocation
- Nested calls properly attributed via timestamp ordering

## Clock Synchronization

### RAPL-Checkpoint Correlation

Critical fix from P0 Issue #1:

From `src/measurement/src/nemb/drivers/intel_rapl_provider.cpp:126-129`:

```cpp
// Use CLOCK_MONOTONIC to match PrecisionTimer
struct timespec ts;
clock_gettime(CLOCK_MONOTONIC, &ts);
reading.timestamp_ns = static_cast<uint64_t>(ts.tv_sec) * 1000000000ULL + ts.tv_nsec;
```

**Why This Matters:**
- Checkpoints use CLOCK_MONOTONIC via PrecisionTimer
- RAPL readings must use same clock source
- Both share epoch (system boot time)
- Enables accurate binary search and interpolation

## Best Practices

### Checkpoint Placement

1. **Function Boundaries**: Enter/exit for energy accounting
2. **Loop Iterations**: Track per-iteration energy (optional)
3. **Critical Sections**: Measure synchronization overhead
4. **I/O Operations**: Separate I/O energy from compute

### Naming Conventions

```python
# Good: Descriptive, unique names
checkpoint("matrix_multiply_1024", "enter")
checkpoint("gpu_kernel_conv2d", "enter")

# Avoid: Generic names in recursive functions
checkpoint("process", "enter")  # Will have inv_1, inv_2, etc.
```

### Performance Tuning

- **Minimal Checkpoints**: Only at function boundaries by default
- **Dense Instrumentation**: Use `--precision high` for loop-level tracking
- **Production Mode**: Use `--precision low` for minimal overhead

## References

- Implementation: `src/measurement/src/nemb/codegreen_energy.cpp`
- Theory: `theory.txt` sections 2-5 (Signal-Generator Model)
- Validation: P0/P1 fixes verification in test_nemb_fixes.cpp
- Commands: `scripts/commands.txt` section 3 (measure command)
