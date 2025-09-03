# Intel RAPL Energy Measurement Guide

## Overview

Intel RAPL (Running Average Power Limit) provides hardware-level energy measurement capabilities on Intel processors since Sandy Bridge (2011). This guide covers implementation details for production-grade RAPL integration.

## Hardware Architecture

### RAPL Domains

**Package Domain (PKG)**
- Total processor package energy consumption
- Includes cores, uncore, integrated graphics, memory controller
- Primary measurement source for most use cases
- MSR Address: `0x611 (MSR_PKG_ENERGY_STATUS)`

**Core Domain (PP0)**  
- CPU cores only (excludes uncore components)
- Useful for core vs uncore energy attribution
- MSR Address: `0x639 (MSR_PP0_ENERGY_STATUS)`

**Uncore Domain (PP1)**
- Uncore components (L3 cache, memory controller, integrated GPU)
- Not available on all platforms
- MSR Address: `0x641 (MSR_PP1_ENERGY_STATUS)`

**DRAM Domain**
- Memory subsystem energy consumption
- Available on server/workstation platforms
- MSR Address: `0x619 (MSR_DRAM_ENERGY_STATUS)`

### Energy Unit Calculation

```cpp
// Read power unit register
uint64_t power_unit_raw = read_msr(0x606);  // MSR_RAPL_POWER_UNIT

// Extract energy unit (bits 12:8)
uint32_t energy_unit_bits = (power_unit_raw >> 8) & 0x1F;
double energy_unit_joules = 1.0 / (1ULL << energy_unit_bits);

// Convert raw counter to joules
double energy_joules = raw_energy_counter * energy_unit_joules;
```

## Implementation Best Practices

### Counter Wraparound Handling

**Problem**: RAPL counters are 32-bit and wrap around frequently
**Solution**: Implement robust wraparound detection

```cpp
class RAPLCounterManager {
private:
    static constexpr uint64_t COUNTER_MASK = 0xFFFFFFFFULL;
    uint64_t last_raw_value_ = 0;
    uint64_t accumulated_energy_ = 0;
    
public:
    uint64_t accumulate_energy(uint64_t current_raw) {
        if (current_raw < last_raw_value_) {
            // Wraparound detected
            uint64_t wraparound_increment = (COUNTER_MASK - last_raw_value_) + current_raw + 1;
            accumulated_energy_ += wraparound_increment;
        } else {
            accumulated_energy_ += (current_raw - last_raw_value_);
        }
        
        last_raw_value_ = current_raw;
        return accumulated_energy_;
    }
};
```

### Access Methods

**Method 1: Direct MSR Access (Highest Accuracy)**
```cpp
class MSRAccess {
private:
    int msr_fd_;
    
public:
    bool initialize() {
        msr_fd_ = open("/dev/cpu/0/msr", O_RDONLY);
        return msr_fd_ >= 0;
    }
    
    uint64_t read_msr(uint32_t msr_index) {
        uint64_t value;
        if (pread(msr_fd_, &value, sizeof(value), msr_index) != sizeof(value)) {
            throw std::runtime_error("MSR read failed");
        }
        return value;
    }
};
```

**Method 2: PowerCap Interface (No Root Required)**
```cpp
class PowerCapAccess {
private:
    std::vector<std::string> energy_file_paths_;
    
public:
    bool initialize() {
        // Enumerate available RAPL domains
        for (const auto& entry : fs::directory_iterator("/sys/class/powercap")) {
            if (entry.path().filename().string().find("intel-rapl") == 0) {
                auto energy_file = entry.path() / "energy_uj";
                if (fs::exists(energy_file)) {
                    energy_file_paths_.push_back(energy_file.string());
                }
            }
        }
        return !energy_file_paths_.empty();
    }
    
    uint64_t read_energy_microjoules(size_t domain_index) {
        std::ifstream file(energy_file_paths_[domain_index]);
        uint64_t energy_uj;
        file >> energy_uj;
        return energy_uj;
    }
};
```

## Accuracy Considerations

### Measurement Frequency vs Overhead

| Frequency | Overhead | Use Case |
|-----------|----------|----------|
| 1000 Hz   | ~0.1%    | Function-level profiling |
| 100 Hz    | ~0.01%   | Loop-level profiling |  
| 10 Hz     | ~0.001%  | Application-level profiling |
| 1 Hz      | ~0.0001% | System-level monitoring |

### Temperature Impact Compensation

```cpp
class TemperatureCompensation {
private:
    // Thermal models for different CPU families
    std::map<std::string, ThermalModel> cpu_models_;
    
public:
    double compensate_power_for_temperature(double raw_power, 
                                          double temperature_celsius,
                                          const std::string& cpu_model) {
        auto& model = cpu_models_[cpu_model];
        
        // Linear temperature compensation (simplified)
        double temp_factor = 1.0 + model.temp_coefficient * (temperature_celsius - model.reference_temp);
        
        return raw_power / temp_factor;
    }
};
```

### Processor-Specific Optimizations

**Intel Skylake and Later**
- Use enhanced RAPL features (PSYS domain for platform energy)
- Account for dynamic voltage/frequency scaling impact
- Handle turbo boost power excursions

**Intel Atom/Silvermont**
- Limited RAPL domain availability
- Different energy unit calculations
- Package-only energy measurement

**Intel Server (Xeon)**
- Multi-socket energy aggregation
- DRAM energy measurement availability
- Uncore power attribution

## Validation and Testing

### Unit Tests
```cpp
TEST(IntelRAPLProvider, CounterWraparound) {
    IntelRAPLProvider provider;
    RAPLCounterManager manager;
    
    // Simulate wraparound scenario
    uint64_t before_wrap = 0xFFFFFFFE;
    uint64_t after_wrap = 0x00000005;
    
    uint64_t accumulated1 = manager.accumulate_energy(before_wrap);
    uint64_t accumulated2 = manager.accumulate_energy(after_wrap);
    
    EXPECT_EQ(accumulated2 - accumulated1, 7);  // 2 + 5 = 7
}
```

### Integration Tests
```cpp
TEST(IntelRAPLProvider, PowerLoadValidation) {
    IntelRAPLProvider provider;
    provider.initialize();
    
    auto start_reading = provider.get_reading();
    
    // Generate known CPU load
    generate_cpu_load_for_duration(std::chrono::seconds(5));
    
    auto end_reading = provider.get_reading();
    
    double energy_consumed = end_reading.energy_joules - start_reading.energy_joules;
    double expected_energy = 5.0 * EXPECTED_CPU_POWER_WATTS;  // 5 seconds * power
    
    EXPECT_NEAR(energy_consumed, expected_energy, expected_energy * 0.1);  // 10% tolerance
}
```

## Performance Characteristics

### Measurement Latency
- **MSR Access**: ~100-500 nanoseconds per read
- **PowerCap Access**: ~1-10 microseconds per read
- **Update Frequency**: Hardware updates every ~1ms
- **Recommended Sampling**: 10-100 Hz for most applications

### Accuracy Specifications
- **Resolution**: ~61 microjoules (typical energy unit)
- **Absolute Accuracy**: ±5% for sustained loads >1 second
- **Relative Accuracy**: ±1% for comparative measurements
- **Temporal Resolution**: ~1ms (hardware dependent)

This comprehensive guide ensures production-ready Intel RAPL integration with maximum accuracy and minimal overhead.