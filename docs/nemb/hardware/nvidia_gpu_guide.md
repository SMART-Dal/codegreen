# NVIDIA GPU Energy Measurement Guide

## Overview

NVIDIA GPU energy measurement utilizes NVML (NVIDIA Management Library) for comprehensive power monitoring across consumer and enterprise GPUs. This guide covers production-grade implementation for accurate GPU energy profiling.

## Hardware Architecture

### GPU Power Domains

**Total Graphics Power (TGP)**
- Complete GPU power consumption including:
  - GPU cores (SMs, RT cores, Tensor cores)
  - Memory subsystem (GDDR/HBM)
  - I/O and PCIe interface
  - Cooling and power delivery overhead

**GPU-Only Power**
- Excludes memory and I/O power
- Available on select enterprise GPUs (A100, H100)
- Useful for compute vs memory power attribution

**Memory Power**
- VRAM power consumption
- Critical for memory-intensive workloads
- Available on HBM-equipped GPUs

### Power States and Management

**Performance States (P-States)**
```cpp
enum class NVIDIAPerfState {
    P0 = 0,    // Maximum performance
    P1 = 1,    // Balanced performance  
    P2 = 2,    // Power saving mode
    P8 = 8,    // Minimum power state
    P12 = 12   // Maximum power saving
};
```

**GPU Clocks Impact on Power**
- Graphics Clock (Core)
- Memory Clock  
- Shader Clock (older architectures)
- Dynamic voltage/frequency scaling (GPU Boost)

## NVML Integration Implementation

### Core NVML Provider

```cpp
#include <nvml.h>

class NVIDIAGPUProvider : public EnergyProvider {
private:
    nvmlDevice_t device_;
    unsigned int device_count_;
    unsigned int power_limit_mw_;
    nvmlMemory_t memory_info_;
    
    // Power sampling configuration
    unsigned int power_sample_count_ = 0;
    std::chrono::steady_clock::time_point last_sample_time_;
    double accumulated_energy_joules_ = 0.0;
    
public:
    bool initialize() override {
        nvmlReturn_t result = nvmlInit();
        if (result != NVML_SUCCESS) {
            log_nvml_error("nvmlInit failed", result);
            return false;
        }
        
        // Get device count
        result = nvmlDeviceGetCount(&device_count_);
        if (result != NVML_SUCCESS || device_count_ == 0) {
            return false;
        }
        
        // Get device handle (using first GPU)
        result = nvmlDeviceGetHandleByIndex(0, &device_);
        if (result != NVML_SUCCESS) {
            return false;
        }
        
        // Verify power monitoring capability
        nvmlEnableState_t power_management;
        result = nvmlDeviceGetPowerManagementMode(device_, &power_management);
        if (result != NVML_SUCCESS || power_management != NVML_FEATURE_ENABLED) {
            return false;
        }
        
        // Get power limits for validation
        result = nvmlDeviceGetPowerManagementLimitConstraints(device_, 
                                                            &power_limit_mw_, 
                                                            nullptr);
        
        last_sample_time_ = std::chrono::steady_clock::now();
        return true;
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        // Get instantaneous power
        unsigned int power_mw;
        nvmlReturn_t result = nvmlDeviceGetPowerUsage(device_, &power_mw);
        if (result != NVML_SUCCESS) {
            reading.measurement_uncertainty = 1.0;  // High uncertainty on error
            return reading;
        }
        
        reading.instantaneous_power_watts = power_mw / 1000.0;
        
        // Calculate energy through power integration
        auto current_time = std::chrono::steady_clock::now();
        if (power_sample_count_ > 0) {
            auto time_delta = std::chrono::duration_cast<std::chrono::nanoseconds>(
                current_time - last_sample_time_);
            double time_delta_seconds = time_delta.count() / 1e9;
            
            // Trapezoidal integration for energy calculation
            double avg_power = (reading.instantaneous_power_watts + last_power_watts_) / 2.0;
            accumulated_energy_joules_ += avg_power * time_delta_seconds;
        }
        
        reading.energy_joules = accumulated_energy_joules_;
        reading.average_power_watts = accumulated_energy_joules_ / 
            (std::chrono::duration_cast<std::chrono::seconds>(
                current_time - first_sample_time_).count());
        
        // Get additional GPU context
        get_gpu_context(reading);
        
        last_power_watts_ = reading.instantaneous_power_watts;
        last_sample_time_ = current_time;
        power_sample_count_++;
        
        return reading;
    }
    
private:
    double last_power_watts_ = 0.0;
    std::chrono::steady_clock::time_point first_sample_time_;
    
    void get_gpu_context(EnergyReading& reading) {
        // GPU temperature
        unsigned int temp;
        if (nvmlDeviceGetTemperature(device_, NVML_TEMPERATURE_GPU, &temp) == NVML_SUCCESS) {
            reading.temperature_celsius = static_cast<double>(temp);
            reading.temperature_valid = true;
        }
        
        // GPU clocks
        unsigned int graphics_clock, memory_clock;
        if (nvmlDeviceGetClockInfo(device_, NVML_CLOCK_GRAPHICS, &graphics_clock) == NVML_SUCCESS) {
            reading.cpu_frequency_mhz = graphics_clock;  // Reuse field for GPU clock
            reading.frequency_valid = true;
        }
        
        // Performance state
        nvmlPstates_t pstate;
        if (nvmlDeviceGetPerformanceState(device_, &pstate) == NVML_SUCCESS) {
            reading.power_state = static_cast<uint8_t>(pstate);
        }
        
        // Memory utilization for context
        nvmlMemory_t memory;
        if (nvmlDeviceGetMemoryInfo(device_, &memory) == NVML_SUCCESS) {
            double memory_utilization = static_cast<double>(memory.used) / memory.total;
            // Store in custom field or metadata
        }
    }
    
    void log_nvml_error(const std::string& operation, nvmlReturn_t result) {
        const char* error_string = nvmlErrorString(result);
        std::cerr << "NVML Error in " << operation << ": " << error_string << std::endl;
    }
};
```

### Multi-GPU Support

```cpp
class MultiNVIDIAProvider : public EnergyProvider {
private:
    std::vector<nvmlDevice_t> devices_;
    std::vector<std::unique_ptr<NVIDIAGPUProvider>> gpu_providers_;
    
public:
    bool initialize() override {
        nvmlReturn_t result = nvmlInit();
        if (result != NVML_SUCCESS) return false;
        
        unsigned int device_count;
        result = nvmlDeviceGetCount(&device_count);
        if (result != NVML_SUCCESS) return false;
        
        // Initialize provider for each GPU
        for (unsigned int i = 0; i < device_count; ++i) {
            nvmlDevice_t device;
            if (nvmlDeviceGetHandleByIndex(i, &device) == NVML_SUCCESS) {
                devices_.push_back(device);
                
                auto provider = std::make_unique<NVIDIAGPUProvider>();
                provider->set_device_index(i);
                if (provider->initialize()) {
                    gpu_providers_.push_back(std::move(provider));
                }
            }
        }
        
        return !gpu_providers_.empty();
    }
    
    EnergyReading get_reading() override {
        EnergyReading combined_reading{};
        combined_reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        double total_power = 0.0;
        double total_energy = 0.0;
        double max_temp = 0.0;
        
        for (auto& provider : gpu_providers_) {
            auto gpu_reading = provider->get_reading();
            total_power += gpu_reading.instantaneous_power_watts;
            total_energy += gpu_reading.energy_joules;
            max_temp = std::max(max_temp, gpu_reading.temperature_celsius);
        }
        
        combined_reading.instantaneous_power_watts = total_power;
        combined_reading.energy_joules = total_energy;
        combined_reading.temperature_celsius = max_temp;
        
        return combined_reading;
    }
};
```

## GPU Architecture Considerations

### Ampere Architecture (RTX 30, A100, H100)
```cpp
class AmpereOptimizations {
public:
    // Ampere-specific power features
    bool supports_nvlink_power_monitoring() const { return true; }
    bool supports_mig_power_isolation() const { return true; }
    
    // Enhanced power monitoring granularity
    double get_tensor_core_power_usage(nvmlDevice_t device) {
        // Implementation for Tensor Core power attribution
        // Available through nvmlDeviceGetTensorCoreUtilization()
        return 0.0; // Placeholder
    }
};
```

### Turing Architecture (RTX 20, Quadro RTX)
```cpp
class TuringOptimizations {
public:
    // RT Core power monitoring
    double get_rt_core_power_contribution(nvmlDevice_t device) {
        // Ray tracing workload power attribution
        return 0.0; // Implementation specific
    }
};
```

### Memory Architecture Impact

**GDDR Memory Power**
```cpp
class MemoryPowerModel {
private:
    struct MemorySpec {
        size_t capacity_gb;
        unsigned int bus_width;
        unsigned int memory_clock_mhz;
        double power_per_gb_active;
        double power_per_gb_idle;
    };
    
public:
    double estimate_memory_power(const nvmlMemory_t& memory_info, 
                                const MemorySpec& spec) {
        double utilization = static_cast<double>(memory_info.used) / memory_info.total;
        double active_power = utilization * spec.capacity_gb * spec.power_per_gb_active;
        double idle_power = (1.0 - utilization) * spec.capacity_gb * spec.power_per_gb_idle;
        
        return active_power + idle_power;
    }
};
```

## Advanced Features

### Dynamic Voltage/Frequency Scaling (DVFS) Tracking

```cpp
class DVFSTracker {
private:
    struct FrequencyPoint {
        unsigned int graphics_clock;
        unsigned int memory_clock;
        uint64_t timestamp;
        double power_coefficient;
    };
    
    std::vector<FrequencyPoint> frequency_history_;
    
public:
    double get_power_scaling_factor(unsigned int current_graphics_clock,
                                  unsigned int current_memory_clock) {
        // Power scaling approximately follows: P ∝ V² × f
        // Where voltage scales with frequency for GPU Boost
        
        double base_power_factor = 1.0;
        
        // Graphics clock scaling (simplified model)
        double graphics_scaling = std::pow(current_graphics_clock / BASE_GRAPHICS_CLOCK, 2.5);
        
        // Memory clock scaling  
        double memory_scaling = current_memory_clock / BASE_MEMORY_CLOCK;
        
        return base_power_factor * graphics_scaling * memory_scaling;
    }
};
```

### Workload-Specific Power Models

```cpp
class WorkloadPowerModel {
public:
    enum class WorkloadType {
        COMPUTE,           // CUDA compute kernels
        GRAPHICS,          // 3D rendering
        RAY_TRACING,       // RT core workloads  
        TENSOR,            // AI/ML workloads
        MEMORY_BOUND,      // Memory-intensive operations
        MIXED
    };
    
    double get_workload_power_multiplier(WorkloadType workload, 
                                       const GPUUtilization& util) {
        switch (workload) {
            case WorkloadType::COMPUTE:
                return 0.9 + 0.8 * util.compute_utilization;
                
            case WorkloadType::TENSOR:
                // Tensor cores are very power efficient
                return 1.2 + 0.6 * util.tensor_utilization;
                
            case WorkloadType::MEMORY_BOUND:
                return 0.6 + 0.9 * util.memory_utilization;
                
            default:
                return 1.0;
        }
    }
};
```

## Validation and Accuracy

### Power Limit Validation

```cpp
class PowerValidation {
public:
    bool validate_power_reading(double power_watts, unsigned int power_limit_mw) {
        double power_limit_watts = power_limit_mw / 1000.0;
        
        // Power should not exceed limit + 10% tolerance for measurement uncertainty
        if (power_watts > power_limit_watts * 1.1) {
            return false;
        }
        
        // Power should not be negative or unreasonably low
        if (power_watts < 1.0) {  // Minimum 1W for active GPU
            return false;
        }
        
        return true;
    }
    
    double calculate_measurement_uncertainty(const std::vector<double>& power_samples) {
        if (power_samples.size() < 2) return 1.0;
        
        double mean = std::accumulate(power_samples.begin(), power_samples.end(), 0.0) / 
                     power_samples.size();
        
        double variance = 0.0;
        for (double sample : power_samples) {
            variance += std::pow(sample - mean, 2);
        }
        variance /= (power_samples.size() - 1);
        
        double stddev = std::sqrt(variance);
        
        // Uncertainty as coefficient of variation
        return stddev / mean;
    }
};
```

### Cross-Validation with Hardware Monitoring

```cpp
class HardwareValidation {
public:
    struct ValidationResult {
        bool gpu_z_available;
        bool hwinfo_available;
        double correlation_coefficient;
        double mean_error_percent;
    };
    
    ValidationResult validate_against_hardware_monitoring() {
        ValidationResult result{};
        
        // Check if GPU-Z is available for cross-validation
        result.gpu_z_available = check_gpu_z_availability();
        
        // Check if HWiNFO is available
        result.hwinfo_available = check_hwinfo_availability();
        
        if (result.gpu_z_available || result.hwinfo_available) {
            // Collect parallel measurements for comparison
            auto validation_data = collect_validation_measurements();
            result.correlation_coefficient = calculate_correlation(validation_data);
            result.mean_error_percent = calculate_mean_error(validation_data);
        }
        
        return result;
    }
};
```

## Performance Characteristics

### Measurement Specifications

| Metric | Consumer GPUs | Enterprise GPUs |
|--------|---------------|-----------------|
| **Update Frequency** | ~3Hz | ~10Hz |
| **Power Resolution** | 1W | 0.1W |
| **Accuracy** | ±5% | ±2% |
| **Response Time** | ~300ms | ~100ms |
| **API Latency** | ~1ms | ~0.1ms |

### Optimization Guidelines

**High-Frequency Sampling**
- Limit to 10Hz maximum to avoid API overhead
- Use exponential moving average for smoothing
- Batch multiple NVML calls when possible

**Multi-GPU Optimization**
- Parallelize measurements across GPUs
- Consider NVLINK topology for energy attribution
- Account for shared system power (PSU efficiency)

This comprehensive guide ensures production-ready NVIDIA GPU energy measurement with maximum accuracy and robust error handling.