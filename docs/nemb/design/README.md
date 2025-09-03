# CodeGreen Native Energy Measurement Backend (NEMB)
## Industry-Grade Energy Measurement System Design

### Overview

The Native Energy Measurement Backend (NEMB) is designed to be the most accurate, low-overhead, and comprehensive energy measurement system for modern computing platforms. This system replaces external dependencies with native, hardware-optimized implementations that deliver production-ready accuracy and performance.

**Design Goals:**
- **Industry-Grade Accuracy**: <2% measurement error for sustained workloads
- **Ultra-Low Overhead**: <0.1% CPU utilization impact
- **Comprehensive Coverage**: CPU, GPU, Memory, System-level measurement
- **Production Ready**: Robust error handling, validation, and self-calibration
- **Hardware Agnostic**: Support for Intel, AMD, NVIDIA, ARM platforms
- **Real-Time Capable**: Sub-millisecond measurement latency

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Hardware Abstraction Design](#hardware-abstraction-design)
3. [Measurement Accuracy Techniques](#measurement-accuracy-techniques)
4. [Noise Reduction and Filtering](#noise-reduction-and-filtering)
5. [Hardware-Specific Implementations](#hardware-specific-implementations)
6. [Performance Optimization Strategies](#performance-optimization-strategies)
7. [Validation and Calibration](#validation-and-calibration)
8. [Integration Guidelines](#integration-guidelines)
9. [Best Practices](#best-practices)
10. [Implementation Roadmap](#implementation-roadmap)

---

## System Architecture

### Core Component Hierarchy

```
NEMB Core Engine
├── Energy Measurement Coordinator
│   ├── Multi-Source Synchronization
│   ├── Temporal Alignment Engine
│   └── Counter Wraparound Handler
├── Hardware Abstraction Layer (HAL)
│   ├── CPU Energy Providers
│   ├── GPU Energy Providers
│   ├── Memory Energy Providers
│   └── System Energy Providers
├── Precision Timing Subsystem
│   ├── High-Resolution Timestamping
│   ├── Cross-Core Time Synchronization
│   └── Frequency Scaling Compensation
├── Statistical Processing Engine
│   ├── Real-Time Noise Reduction
│   ├── Outlier Detection and Filtering
│   └── Confidence Interval Calculation
└── Calibration and Validation Framework
    ├── Self-Calibration Routines
    ├── Cross-Validation with Reference Sources
    └── Systematic Error Detection
```

### Design Principles

**1. Separation of Concerns**
- Hardware abstraction isolates platform-specific code
- Core algorithms remain hardware-agnostic
- Modular design enables independent component testing

**2. Real-Time Performance**
- Lock-free data structures for high-frequency sampling
- Zero-copy measurement pipelines
- NUMA-aware memory allocation strategies

**3. Measurement Integrity**
- Multi-source cross-validation
- Statistical outlier detection
- Hardware counter consistency checks

---

## Hardware Abstraction Design

### Energy Provider Interface

```cpp
class EnergyProvider {
public:
    struct Specification {
        std::string hardware_type;      // "cpu", "gpu", "memory", "system"
        std::string vendor;             // "intel", "amd", "nvidia", "arm"
        double energy_resolution;       // Minimum measurable energy (Joules)
        double power_resolution;        // Minimum measurable power (Watts)
        std::chrono::microseconds update_interval;
        uint32_t counter_bits;          // Counter width for wraparound calculation
        bool supports_temperature;
        bool supports_frequency;
    };
    
    virtual ~EnergyProvider() = default;
    virtual bool initialize() = 0;
    virtual EnergyReading get_reading() = 0;
    virtual Specification get_specification() const = 0;
    virtual bool self_test() = 0;
};
```

### Measurement Data Structure

```cpp
struct EnergyReading {
    // Temporal Information
    uint64_t timestamp_ns;              // Nanosecond precision timestamp
    std::chrono::steady_clock::time_point system_time;
    
    // Energy and Power Data
    double energy_joules;               // Cumulative energy consumption
    double instantaneous_power_watts;   // Current power draw
    double average_power_watts;         // Average power since last reading
    
    // Hardware State Context
    uint32_t cpu_frequency_mhz;         // Current CPU frequency
    double temperature_celsius;          // Die/junction temperature
    uint8_t power_state;                // P-state, C-state information
    
    // Measurement Quality Metrics
    double measurement_uncertainty;      // Statistical uncertainty
    uint32_t sample_count;              // Samples averaged for this reading
    EnergySource source_type;           // Hardware component source
    std::string provider_id;            // Unique provider identifier
    
    // Validation Flags
    bool counter_wrapped;               // Counter overflow detected
    bool temperature_valid;             // Temperature reading valid
    bool frequency_valid;               // Frequency reading valid
};
```

---

## Measurement Accuracy Techniques

### High-Precision Timestamping

**Time Stamp Counter (TSC) Integration**
```cpp
class PrecisionTimer {
private:
    uint64_t tsc_frequency_;
    uint64_t tsc_offset_;
    bool tsc_invariant_;
    
public:
    uint64_t get_precise_timestamp() {
        if (tsc_invariant_) {
            // Use invariant TSC for maximum precision
            return (__rdtsc() - tsc_offset_) * 1000000000ULL / tsc_frequency_;
        } else {
            // Fall back to CLOCK_MONOTONIC_RAW
            struct timespec ts;
            clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
            return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
        }
    }
};
```

**Cross-Core Synchronization**
- TSC synchronization verification across all CPU cores
- Offset correction for NUMA domains
- Frequency scaling compensation algorithms

### Counter Wraparound Handling

**Intelligent Wraparound Detection**
```cpp
class CounterManager {
private:
    uint64_t counter_mask_;     // Based on hardware counter width
    uint64_t last_raw_value_;
    uint64_t accumulated_energy_;
    
public:
    uint64_t handle_wraparound(uint64_t current_raw) {
        if (current_raw < last_raw_value_) {
            // Wraparound detected
            uint64_t wrapped_increment = (counter_mask_ - last_raw_value_) + current_raw + 1;
            accumulated_energy_ += wrapped_increment;
        } else {
            accumulated_energy_ += (current_raw - last_raw_value_);
        }
        last_raw_value_ = current_raw;
        return accumulated_energy_;
    }
};
```

### Multi-Source Synchronization

**Temporal Alignment Engine**
```cpp
class MeasurementCoordinator {
    struct SynchronizedReading {
        std::vector<EnergyReading> aligned_readings;
        uint64_t common_timestamp;
        double total_system_power;
        double measurement_confidence;
    };
    
public:
    SynchronizedReading get_aligned_measurements() {
        // Collect readings from all providers
        auto readings = collect_all_provider_readings();
        
        // Time-align readings using interpolation
        auto aligned = temporal_alignment(readings);
        
        // Cross-validate for consistency
        validate_reading_consistency(aligned);
        
        return aligned;
    }
};
```

---

## Noise Reduction and Filtering

### Statistical Filtering Techniques

**Kalman Filter Implementation**
```cpp
class KalmanPowerFilter {
private:
    double process_noise_;      // Q: Process noise covariance
    double measurement_noise_;  // R: Measurement noise covariance
    double estimation_error_;   // P: Estimation error covariance
    double kalman_gain_;       // K: Kalman gain
    double filtered_power_;    // x: State estimate
    
public:
    double filter_power_reading(double raw_power, double measurement_uncertainty) {
        // Prediction step
        double predicted_power = filtered_power_;  // Assume constant power model
        double predicted_error = estimation_error_ + process_noise_;
        
        // Update step
        kalman_gain_ = predicted_error / (predicted_error + measurement_uncertainty);
        filtered_power_ = predicted_power + kalman_gain_ * (raw_power - predicted_power);
        estimation_error_ = (1 - kalman_gain_) * predicted_error;
        
        return filtered_power_;
    }
};
```

**Outlier Detection and Removal**
```cpp
class OutlierDetector {
public:
    bool is_outlier(double value, const std::vector<double>& history) {
        if (history.size() < MIN_HISTORY_SIZE) return false;
        
        double mean = calculate_mean(history);
        double stddev = calculate_stddev(history, mean);
        
        // Modified Z-score for robustness
        double modified_z_score = 0.6745 * (value - median(history)) / mad(history);
        
        return std::abs(modified_z_score) > OUTLIER_THRESHOLD;
    }
};
```

### Temperature and Frequency Compensation

**Dynamic Compensation Algorithms**
```cpp
class EnvironmentalCompensation {
private:
    std::map<double, double> temp_power_lut_;    // Temperature -> Power correction LUT
    std::map<uint32_t, double> freq_power_lut_;  // Frequency -> Power correction LUT
    
public:
    double compensate_for_environment(double raw_power, 
                                    double temperature, 
                                    uint32_t frequency) {
        double temp_correction = interpolate_temperature_correction(temperature);
        double freq_correction = interpolate_frequency_correction(frequency);
        
        return raw_power * temp_correction * freq_correction;
    }
};
```

---

## Hardware-Specific Implementations

### Intel CPU Energy Measurement

**RAPL (Running Average Power Limit) Integration**
```cpp
class IntelRAPLProvider : public EnergyProvider {
private:
    int msr_fd_;
    uint64_t energy_unit_microjoules_;  // From MSR_RAPL_POWER_UNIT
    uint64_t power_unit_milliwatts_;
    uint64_t time_unit_microseconds_;
    
    // MSR Addresses (Intel SDM Vol 4)
    static constexpr uint32_t MSR_RAPL_POWER_UNIT = 0x606;
    static constexpr uint32_t MSR_PKG_ENERGY_STATUS = 0x611;
    static constexpr uint32_t MSR_PP0_ENERGY_STATUS = 0x639;  // Core
    static constexpr uint32_t MSR_PP1_ENERGY_STATUS = 0x641;  // Uncore/GPU
    static constexpr uint32_t MSR_DRAM_ENERGY_STATUS = 0x619; // DRAM
    
public:
    bool initialize() override {
        msr_fd_ = open("/dev/cpu/0/msr", O_RDONLY);
        if (msr_fd_ < 0) {
            // Fall back to /sys/class/powercap interface
            return initialize_powercap_interface();
        }
        
        // Read energy unit from MSR_RAPL_POWER_UNIT[12:8]
        uint64_t power_unit_raw = read_msr(MSR_RAPL_POWER_UNIT);
        uint32_t energy_unit_bits = (power_unit_raw >> 8) & 0x1F;
        energy_unit_microjoules_ = 1000000 >> energy_unit_bits;  // 2^(-ESU) * 10^6
        
        return true;
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        // Read package energy (most comprehensive)
        uint64_t pkg_energy_raw = read_msr(MSR_PKG_ENERGY_STATUS) & 0xFFFFFFFF;
        uint64_t pkg_energy_accumulated = counter_manager_.handle_wraparound(pkg_energy_raw);
        
        reading.energy_joules = (pkg_energy_accumulated * energy_unit_microjoules_) / 1000000.0;
        
        // Calculate instantaneous power from energy derivative
        if (last_reading_.timestamp_ns > 0) {
            uint64_t time_delta_ns = reading.timestamp_ns - last_reading_.timestamp_ns;
            double energy_delta = reading.energy_joules - last_reading_.energy_joules;
            reading.instantaneous_power_watts = (energy_delta * 1000000000.0) / time_delta_ns;
        }
        
        last_reading_ = reading;
        return reading;
    }
};
```

### AMD CPU Energy Measurement

**AMD RAPL Implementation**
```cpp
class AMDRAPLProvider : public EnergyProvider {
private:
    // AMD-specific MSR addresses (AMD PPR)
    static constexpr uint32_t MSR_PWR_UNIT = 0xC0010299;
    static constexpr uint32_t MSR_CORE_ENERGY = 0xC001029A;
    static constexpr uint32_t MSR_PKG_ENERGY = 0xC001029B;
    
    // Zen architecture considerations
    uint32_t ccx_count_;        // Core Complex count
    uint32_t ccd_count_;        // Core Complex Die count
    
public:
    EnergyReading get_reading() override {
        // AMD RAPL differs from Intel in energy unit calculation
        // Energy = RawValue * EnergyUnit where EnergyUnit = 2^(-ESU) * 15.3μJ (Zen 3)
        uint64_t core_energy = read_msr(MSR_CORE_ENERGY);
        uint64_t pkg_energy = read_msr(MSR_PKG_ENERGY);
        
        // Account for chiplet architecture
        return calculate_zen_energy(core_energy, pkg_energy);
    }
};
```

### NVIDIA GPU Energy Measurement

**NVML Integration for Production Accuracy**
```cpp
class NVIDIAGPUProvider : public EnergyProvider {
private:
    nvmlDevice_t device_;
    unsigned int power_limit_mw_;
    nvmlPstates_t current_pstate_;
    
public:
    bool initialize() override {
        nvmlReturn_t result = nvmlInit();
        if (result != NVML_SUCCESS) return false;
        
        result = nvmlDeviceGetHandleByIndex(0, &device_);
        if (result != NVML_SUCCESS) return false;
        
        // Get power management capabilities
        nvmlEnableState_t power_management;
        nvmlDeviceGetPowerManagementMode(device_, &power_management);
        
        return power_management == NVML_FEATURE_ENABLED;
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        // Get instantaneous power draw
        unsigned int power_mw;
        nvmlReturn_t result = nvmlDeviceGetPowerUsage(device_, &power_mw);
        if (result == NVML_SUCCESS) {
            reading.instantaneous_power_watts = power_mw / 1000.0;
        }
        
        // Calculate energy from power integration
        if (last_reading_.timestamp_ns > 0) {
            uint64_t time_delta_ns = reading.timestamp_ns - last_reading_.timestamp_ns;
            double time_delta_s = time_delta_ns / 1000000000.0;
            double avg_power = (reading.instantaneous_power_watts + last_reading_.instantaneous_power_watts) / 2.0;
            reading.energy_joules = last_reading_.energy_joules + (avg_power * time_delta_s);
        }
        
        // Get additional context
        nvmlDeviceGetPerformanceState(device_, &current_pstate_);
        
        unsigned int temp;
        nvmlDeviceGetTemperature(device_, NVML_TEMPERATURE_GPU, &temp);
        reading.temperature_celsius = temp;
        
        last_reading_ = reading;
        return reading;
    }
};
```

### ARM SoC Energy Measurement

**Energy Aware Scheduling (EAS) Integration**
```cpp
class ARMEnergyProvider : public EnergyProvider {
private:
    std::vector<uint32_t> cpu_cluster_freqs_;
    std::map<uint32_t, double> energy_model_lut_;  // Frequency -> Energy/instruction LUT
    
public:
    bool initialize() override {
        // Load energy model from device tree or sysfs
        return load_energy_model_from_sysfs();
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        
        // ARM energy measurement typically relies on:
        // 1. Per-cluster frequency monitoring
        // 2. Instruction retirement counters (PMU)
        // 3. Energy model calculations
        
        double total_energy = 0.0;
        for (size_t cluster = 0; cluster < cpu_cluster_freqs_.size(); ++cluster) {
            uint32_t freq = get_cluster_frequency(cluster);
            uint64_t instructions = get_cluster_instructions(cluster);
            double energy_per_instruction = energy_model_lut_[freq];
            total_energy += instructions * energy_per_instruction;
        }
        
        reading.energy_joules = total_energy;
        return reading;
    }
};
```

---

## Performance Optimization Strategies

### Lock-Free Data Structures

**Ring Buffer Implementation**
```cpp
template<typename T, size_t N>
class LockFreeRingBuffer {
private:
    alignas(64) std::array<T, N> buffer_;
    alignas(64) std::atomic<size_t> head_{0};
    alignas(64) std::atomic<size_t> tail_{0};
    
public:
    bool push(const T& item) {
        size_t current_tail = tail_.load(std::memory_order_relaxed);
        size_t next_tail = (current_tail + 1) % N;
        
        if (next_tail == head_.load(std::memory_order_acquire)) {
            return false; // Buffer full
        }
        
        buffer_[current_tail] = item;
        tail_.store(next_tail, std::memory_order_release);
        return true;
    }
    
    bool pop(T& item) {
        size_t current_head = head_.load(std::memory_order_relaxed);
        if (current_head == tail_.load(std::memory_order_acquire)) {
            return false; // Buffer empty
        }
        
        item = buffer_[current_head];
        head_.store((current_head + 1) % N, std::memory_order_release);
        return true;
    }
};
```

### NUMA-Aware Memory Management

**CPU Affinity and Memory Allocation**
```cpp
class NUMAOptimizer {
private:
    std::vector<int> numa_nodes_;
    std::map<std::thread::id, int> thread_node_mapping_;
    
public:
    void* allocate_on_node(size_t size, int preferred_node = -1) {
        if (preferred_node == -1) {
            preferred_node = get_current_numa_node();
        }
        
        void* ptr = numa_alloc_onnode(size, preferred_node);
        if (!ptr) {
            // Fall back to system allocator
            ptr = aligned_alloc(64, size);
        }
        
        return ptr;
    }
    
    void set_thread_affinity(std::thread& thread, int numa_node) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        
        // Set affinity to CPUs in the specified NUMA node
        auto cpus_in_node = get_cpus_in_numa_node(numa_node);
        for (int cpu : cpus_in_node) {
            CPU_SET(cpu, &cpuset);
        }
        
        pthread_setaffinity_np(thread.native_handle(), sizeof(cpu_set_t), &cpuset);
    }
};
```

### Zero-Copy Measurement Pipeline

**Memory-Mapped Interface**
```cpp
class ZeroCopyMeasurementBuffer {
private:
    void* mmap_buffer_;
    size_t buffer_size_;
    std::atomic<size_t> write_offset_;
    std::atomic<size_t> read_offset_;
    
public:
    EnergyReading* get_write_slot() {
        size_t offset = write_offset_.fetch_add(sizeof(EnergyReading), 
                                              std::memory_order_relaxed);
        if (offset + sizeof(EnergyReading) > buffer_size_) {
            write_offset_.store(0, std::memory_order_release);  // Wrap around
            offset = 0;
        }
        
        return reinterpret_cast<EnergyReading*>(
            static_cast<char*>(mmap_buffer_) + offset);
    }
};
```

---

## Validation and Calibration

### Self-Calibration Framework

**Baseline Noise Characterization**
```cpp
class CalibrationEngine {
private:
    struct BaselineCharacteristics {
        double mean_idle_power;
        double stddev_idle_power;
        double max_measurement_jitter;
        std::map<double, double> temp_power_correlation;
    };
    
public:
    BaselineCharacteristics characterize_system_baseline() {
        BaselineCharacteristics baseline{};
        
        // Collect 10 seconds of idle measurements
        auto idle_measurements = collect_idle_measurements(std::chrono::seconds(10));
        
        // Calculate statistical properties
        baseline.mean_idle_power = calculate_mean_power(idle_measurements);
        baseline.stddev_idle_power = calculate_power_stddev(idle_measurements);
        baseline.max_measurement_jitter = calculate_max_jitter(idle_measurements);
        
        // Build temperature correlation model
        baseline.temp_power_correlation = build_temperature_model(idle_measurements);
        
        return baseline;
    }
    
    bool validate_measurement_chain() {
        // End-to-end validation using known power loads
        return run_power_load_validation() && 
               validate_cross_provider_consistency() &&
               check_timestamp_monotonicity();
    }
};
```

### Cross-Validation with External References

**External Power Meter Integration**
```cpp
class ExternalValidation {
public:
    struct ValidationResult {
        double mean_error_percent;
        double max_error_percent;
        double correlation_coefficient;
        bool validation_passed;
    };
    
    ValidationResult validate_against_external_meter(
        const std::vector<EnergyReading>& internal_readings,
        const std::vector<double>& external_power_readings) {
        
        ValidationResult result{};
        
        // Temporal alignment of measurements
        auto aligned_pairs = align_measurements(internal_readings, external_power_readings);
        
        // Statistical analysis
        std::vector<double> errors;
        for (const auto& pair : aligned_pairs) {
            double error_percent = ((pair.internal_power - pair.external_power) / 
                                  pair.external_power) * 100.0;
            errors.push_back(error_percent);
        }
        
        result.mean_error_percent = calculate_mean(errors);
        result.max_error_percent = *std::max_element(errors.begin(), errors.end());
        result.correlation_coefficient = calculate_correlation(aligned_pairs);
        
        // Validation criteria
        result.validation_passed = (std::abs(result.mean_error_percent) < 2.0) &&
                                 (std::abs(result.max_error_percent) < 5.0) &&
                                 (result.correlation_coefficient > 0.95);
        
        return result;
    }
};
```

---

## Integration Guidelines

### CodeGreen Integration Points

**Replacing PMT Infrastructure**
```cpp
// Replace PMTManager with NativeEnergyManager
class NativeEnergyManager {
private:
    std::vector<std::unique_ptr<EnergyProvider>> providers_;
    std::unique_ptr<MeasurementCoordinator> coordinator_;
    std::unique_ptr<StatisticalProcessor> processor_;
    
public:
    bool initialize() {
        // Auto-detect and initialize available providers
        auto intel_cpu = std::make_unique<IntelRAPLProvider>();
        if (intel_cpu->initialize()) {
            providers_.push_back(std::move(intel_cpu));
        }
        
        auto nvidia_gpu = std::make_unique<NVIDIAGPUProvider>();
        if (nvidia_gpu->initialize()) {
            providers_.push_back(std::move(nvidia_gpu));
        }
        
        coordinator_ = std::make_unique<MeasurementCoordinator>(providers_);
        processor_ = std::make_unique<StatisticalProcessor>();
        
        return !providers_.empty();
    }
    
    std::unique_ptr<Measurement> collect_measurement() {
        auto synchronized_reading = coordinator_->get_aligned_measurements();
        auto processed_reading = processor_->process(synchronized_reading);
        
        // Convert to CodeGreen Measurement format
        auto measurement = std::make_unique<Measurement>();
        measurement->joules = processed_reading.total_energy_joules;
        measurement->watts = processed_reading.total_power_watts;
        measurement->timestamp = std::chrono::system_clock::now();
        measurement->source = "NEMB";
        
        return measurement;
    }
};
```

### API Compatibility Layer

```cpp
// Maintain backward compatibility with existing CodeGreen interfaces
namespace codegreen::nemb {
    // Factory function for creating energy managers
    std::unique_ptr<EnergyManager> create_native_energy_manager(
        const NEMBConfiguration& config = NEMBConfiguration::default_config());
    
    // Configuration structure
    struct NEMBConfiguration {
        bool enable_cpu_measurement = true;
        bool enable_gpu_measurement = true;
        bool enable_memory_measurement = true;
        std::chrono::milliseconds measurement_interval{1};
        double noise_reduction_factor = 0.1;
        bool enable_self_calibration = true;
        
        static NEMBConfiguration default_config() {
            return NEMBConfiguration{};
        }
    };
}
```

---

## Best Practices

### Design Considerations

**1. Hardware Architecture Awareness**
- Understand CPU topology (cores, packages, NUMA nodes)
- Account for GPU memory hierarchy and power domains
- Consider system-on-chip (SoC) integration challenges
- Plan for heterogeneous computing environments

**2. Measurement Timing**
- Use hardware timestamps when available
- Synchronize measurements across different clock domains
- Account for measurement latency and jitter
- Handle frequency scaling impact on timing

**3. Error Handling and Recovery**
- Implement graceful degradation when hardware access fails
- Provide fallback measurement methods
- Log diagnostic information for troubleshooting
- Enable runtime recalibration capabilities

**4. Security Considerations**
- Handle privileged hardware access safely
- Validate measurement data for anomalies
- Prevent information leakage through timing channels
- Implement secure MSR access patterns

### Performance Guidelines

**1. Measurement Overhead Minimization**
- Use lock-free algorithms where possible
- Minimize system call overhead
- Batch hardware register reads
- Optimize for cache locality

**2. Memory Management**
- Pre-allocate measurement buffers
- Use memory pools for frequent allocations
- Consider huge page allocation for large buffers
- Implement proper cleanup and resource management

**3. Thread Safety**
- Design for concurrent access from multiple threads
- Use atomic operations for shared state
- Minimize critical sections
- Consider read-copy-update (RCU) patterns

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Weeks 1-2)
- [ ] Base interfaces and abstract classes
- [ ] Precision timing subsystem
- [ ] Lock-free data structures
- [ ] Basic validation framework

### Phase 2: CPU Energy Providers (Weeks 3-4)  
- [ ] Intel RAPL implementation
- [ ] AMD RAPL implementation
- [ ] ARM energy model integration
- [ ] CPU frequency/temperature correlation

### Phase 3: GPU Energy Providers (Weeks 5-6)
- [ ] NVIDIA NVML integration
- [ ] AMD ROCm SMI integration  
- [ ] Intel GPU support
- [ ] Multi-GPU synchronization

### Phase 4: Advanced Features (Weeks 7-8)
- [ ] Statistical processing engine
- [ ] Cross-validation framework
- [ ] Self-calibration routines
- [ ] Performance optimization

### Phase 5: Integration and Testing (Weeks 9-10)
- [ ] CodeGreen integration
- [ ] Comprehensive validation suite
- [ ] Performance benchmarking
- [ ] Production readiness testing

---

This design document serves as the foundation for building an industry-grade energy measurement system that will provide accurate, reliable, and high-performance energy monitoring capabilities for CodeGreen users across diverse hardware platforms.