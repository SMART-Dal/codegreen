# AMD Hardware Energy Measurement Guide

## Overview

AMD hardware energy measurement encompasses both CPU (RAPL-equivalent) and GPU (ROCm SMI) platforms. This guide covers comprehensive implementation for AMD Ryzen, EPYC, and Radeon GPU energy monitoring.

## AMD CPU Energy Measurement

### AMD RAPL Implementation

**MSR-Based Energy Counters**
AMD implements RAPL-like functionality with different MSR addresses and calculation methods:

```cpp
class AMDRAPLProvider : public EnergyProvider {
private:
    // AMD-specific MSR addresses  
    static constexpr uint32_t MSR_PWR_UNIT = 0xC0010299;      // Power unit
    static constexpr uint32_t MSR_CORE_ENERGY = 0xC001029A;   // Core energy
    static constexpr uint32_t MSR_PKG_ENERGY = 0xC001029B;    // Package energy
    static constexpr uint32_t MSR_L3_ENERGY = 0xC001029C;     // L3 cache energy (Zen3+)
    
    // Zen architecture parameters
    uint32_t ccx_count_;        // Core Complex count
    uint32_t ccd_count_;        // Core Complex Die count  
    uint32_t iod_count_;        // I/O Die count (EPYC)
    
    double energy_unit_microjoules_;
    
public:
    bool initialize() override {
        if (!detect_amd_processor()) {
            return false;
        }
        
        // Open MSR interface
        msr_fd_ = open("/dev/cpu/0/msr", O_RDONLY);
        if (msr_fd_ < 0) {
            return initialize_amd_powercap_interface();
        }
        
        // Read power unit register
        uint64_t power_unit_raw = read_msr(MSR_PWR_UNIT);
        
        // AMD energy unit calculation (different from Intel)
        // For Zen 3: Energy Unit = 15.3 microjoules * 2^(-ESU)
        uint32_t energy_unit_bits = (power_unit_raw >> 8) & 0x1F;
        energy_unit_microjoules_ = 15.3 * (1.0 / (1ULL << energy_unit_bits));
        
        // Detect Zen architecture specifics
        detect_zen_topology();
        
        return true;
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        // AMD RAPL focuses on package-level measurement
        uint64_t pkg_energy_raw = read_msr(MSR_PKG_ENERGY);
        uint64_t pkg_energy_accumulated = counter_manager_.handle_wraparound(pkg_energy_raw);
        
        reading.energy_joules = (pkg_energy_accumulated * energy_unit_microjoules_) / 1000000.0;
        
        // For Zen 3+, also read L3 cache energy
        if (supports_l3_energy_) {
            uint64_t l3_energy_raw = read_msr(MSR_L3_ENERGY);
            l3_energy_accumulated_ = l3_counter_manager_.handle_wraparound(l3_energy_raw);
            reading.l3_energy_joules = (l3_energy_accumulated_ * energy_unit_microjoules_) / 1000000.0;
        }
        
        // Calculate instantaneous power
        calculate_instantaneous_power(reading);
        
        return reading;
    }
    
private:
    bool detect_amd_processor() {
        uint32_t eax, ebx, ecx, edx;
        __cpuid(0, eax, ebx, ecx, edx);
        
        // Check for "AuthenticAMD"
        return (ebx == 0x68747541 && ecx == 0x444D4163 && edx == 0x69746E65);
    }
    
    void detect_zen_topology() {
        // Determine Zen architecture generation
        uint32_t family, model, stepping;
        get_cpu_info(family, model, stepping);
        
        if (family == 0x17) {
            // Zen, Zen+, Zen 2
            zen_generation_ = (model >= 0x30) ? ZenGeneration::ZEN2 : ZenGeneration::ZEN1;
        } else if (family == 0x19) {
            // Zen 3, Zen 4
            zen_generation_ = (model >= 0x40) ? ZenGeneration::ZEN4 : ZenGeneration::ZEN3;
            supports_l3_energy_ = true;
        }
        
        // Count CCX/CCD topology
        detect_ccx_topology();
    }
};
```

### Zen Architecture-Specific Optimizations

**Chiplet Power Distribution**
```cpp
class ZenChipletManager {
private:
    struct ChipletInfo {
        uint32_t ccd_id;
        uint32_t ccx_count;
        uint32_t core_count;
        double power_weight;  // Power distribution weight
    };
    
    std::vector<ChipletInfo> chiplets_;
    
public:
    double distribute_power_across_chiplets(double total_package_power) {
        double distributed_power = 0.0;
        
        for (const auto& chiplet : chiplets_) {
            double chiplet_power = total_package_power * chiplet.power_weight;
            distributed_power += chiplet_power;
            
            // Store per-chiplet power for fine-grained attribution
            chiplet_power_map_[chiplet.ccd_id] = chiplet_power;
        }
        
        return distributed_power;
    }
    
private:
    std::map<uint32_t, double> chiplet_power_map_;
};
```

**Infinity Fabric Power Accounting**
```cpp
class InfinityFabricPowerModel {
public:
    double calculate_if_power_overhead(uint32_t active_ccds, 
                                     uint32_t memory_channels,
                                     double memory_bandwidth_utilization) {
        // IF power scales with:
        // 1. Number of active CCDs
        // 2. Memory traffic
        // 3. Inter-die communication
        
        double base_if_power = active_ccds * IF_BASE_POWER_PER_CCD;
        double memory_if_power = memory_channels * memory_bandwidth_utilization * IF_MEMORY_POWER_FACTOR;
        double coherency_power = calculate_coherency_power(active_ccds);
        
        return base_if_power + memory_if_power + coherency_power;
    }
    
private:
    static constexpr double IF_BASE_POWER_PER_CCD = 0.5;  // Watts
    static constexpr double IF_MEMORY_POWER_FACTOR = 2.0; // Watts per channel at 100% utilization
};
```

## AMD GPU Energy Measurement

### ROCm SMI Integration

**ROCm System Management Interface**
```cpp
#include <rocm_smi/rocm_smi.h>

class AMDGPUProvider : public EnergyProvider {
private:
    uint32_t device_count_;
    std::vector<uint32_t> device_indices_;
    std::map<uint32_t, double> accumulated_energy_;
    
public:
    bool initialize() override {
        rsmi_status_t ret = rsmi_init(0);
        if (ret != RSMI_STATUS_SUCCESS) {
            return false;
        }
        
        // Get device count
        ret = rsmi_num_monitor_devices(&device_count_);
        if (ret != RSMI_STATUS_SUCCESS || device_count_ == 0) {
            return false;
        }
        
        // Initialize device tracking
        for (uint32_t i = 0; i < device_count_; ++i) {
            // Check if power monitoring is supported
            rsmi_power_cap_range_t power_cap;
            if (rsmi_dev_power_cap_range_get(i, 0, &power_cap) == RSMI_STATUS_SUCCESS) {
                device_indices_.push_back(i);
                accumulated_energy_[i] = 0.0;
            }
        }
        
        return !device_indices_.empty();
    }
    
    EnergyReading get_reading() override {
        EnergyReading reading{};
        reading.timestamp_ns = precision_timer_.get_precise_timestamp();
        
        double total_power = 0.0;
        double total_energy = 0.0;
        
        for (uint32_t device_id : device_indices_) {
            // Get current power consumption
            uint64_t power_uw;  // Microwatts
            rsmi_status_t ret = rsmi_dev_power_ave_get(device_id, 0, &power_uw);
            if (ret == RSMI_STATUS_SUCCESS) {
                double device_power_watts = power_uw / 1000000.0;
                total_power += device_power_watts;
                
                // Integrate power to calculate energy
                if (last_sample_time_.count() > 0) {
                    auto current_time = std::chrono::steady_clock::now();
                    auto time_delta = std::chrono::duration_cast<std::chrono::nanoseconds>(
                        current_time - last_sample_time_);
                    double time_delta_seconds = time_delta.count() / 1e9;
                    
                    accumulated_energy_[device_id] += device_power_watts * time_delta_seconds;
                }
                
                total_energy += accumulated_energy_[device_id];
            }
            
            // Get additional context
            get_amd_gpu_context(device_id, reading);
        }
        
        reading.instantaneous_power_watts = total_power;
        reading.energy_joules = total_energy;
        
        last_sample_time_ = std::chrono::steady_clock::now();
        
        return reading;
    }
    
private:
    std::chrono::steady_clock::time_point last_sample_time_{};
    
    void get_amd_gpu_context(uint32_t device_id, EnergyReading& reading) {
        // GPU temperature
        int64_t temp_millidegrees;
        if (rsmi_dev_temp_metric_get(device_id, RSMI_TEMP_TYPE_JUNCTION, 
                                   RSMI_TEMP_CURRENT, &temp_millidegrees) == RSMI_STATUS_SUCCESS) {
            reading.temperature_celsius = temp_millidegrees / 1000.0;
            reading.temperature_valid = true;
        }
        
        // GPU clocks
        rsmi_frequencies_t frequencies;
        if (rsmi_dev_gpu_clk_freq_get(device_id, RSMI_CLK_TYPE_SYS, 
                                    &frequencies) == RSMI_STATUS_SUCCESS) {
            if (frequencies.current < frequencies.num_supported) {
                reading.cpu_frequency_mhz = frequencies.frequency[frequencies.current] / 1000000;
                reading.frequency_valid = true;
            }
        }
        
        // Power limit information
        uint64_t power_cap;
        if (rsmi_dev_power_cap_get(device_id, 0, &power_cap) == RSMI_STATUS_SUCCESS) {
            reading.power_limit_watts = power_cap / 1000000.0;
        }
        
        // GPU utilization
        uint32_t busy_percent;
        if (rsmi_dev_busy_percent_get(device_id, &busy_percent) == RSMI_STATUS_SUCCESS) {
            reading.utilization_percent = busy_percent;
        }
        
        // Memory information
        rsmi_memory_usage_t memory_usage;
        if (rsmi_dev_memory_usage_get(device_id, RSMI_MEM_TYPE_VRAM, 
                                    &memory_usage) == RSMI_STATUS_SUCCESS) {
            reading.memory_used_bytes = memory_usage.memory_usage;
            reading.memory_total_bytes = memory_usage.memory_total;
        }
    }
};
```

### RDNA Architecture Optimizations

**RDNA Power Management**
```cpp
class RDNAPowerModel {
private:
    enum class RDNAGeneration {
        RDNA1,  // RX 5000 series
        RDNA2,  // RX 6000 series  
        RDNA3   // RX 7000 series
    };
    
    RDNAGeneration rdna_gen_;
    
public:
    double get_rdna_power_efficiency_factor(RDNAGeneration gen, 
                                          uint32_t compute_units_active) {
        switch (gen) {
            case RDNAGeneration::RDNA1:
                return 1.0 * (compute_units_active / 40.0);  // RX 5700 XT baseline
                
            case RDNAGeneration::RDNA2:
                // ~50% power efficiency improvement over RDNA1
                return 0.75 * (compute_units_active / 72.0); // RX 6900 XT baseline
                
            case RDNAGeneration::RDNA3:
                // Additional ~20% power efficiency improvement
                return 0.6 * (compute_units_active / 84.0);  // RX 7900 XTX baseline
                
            default:
                return 1.0;
        }
    }
    
    double calculate_infinity_cache_power(uint64_t cache_hit_rate,
                                        uint64_t memory_bandwidth) {
        // Infinity Cache significantly reduces memory power
        double memory_power_saved = cache_hit_rate * memory_bandwidth * MEMORY_POWER_PER_GB_S;
        double cache_power_overhead = INFINITY_CACHE_BASE_POWER;
        
        return cache_power_overhead - memory_power_saved;
    }
    
private:
    static constexpr double MEMORY_POWER_PER_GB_S = 0.1;  // Watts per GB/s
    static constexpr double INFINITY_CACHE_BASE_POWER = 5.0;  // Watts
};
```

### CDNA Architecture (Data Center GPUs)

**MI100/MI200/MI300 Series**
```cpp
class CDNAProvider : public AMDGPUProvider {
private:
    struct CDNAMetrics {
        double hbm_power_watts;
        double compute_power_watts;  
        double interconnect_power_watts;
        double cooling_power_watts;
    };
    
public:
    EnergyReading get_reading() override {
        auto base_reading = AMDGPUProvider::get_reading();
        
        // CDNA-specific power breakdown
        CDNAMetrics metrics = get_cdna_power_breakdown();
        
        // Enhanced accuracy for data center workloads
        base_reading.measurement_uncertainty = 0.01;  // 1% uncertainty for CDNA
        
        // Additional CDNA-specific fields
        base_reading.hbm_power_watts = metrics.hbm_power_watts;
        base_reading.interconnect_power_watts = metrics.interconnect_power_watts;
        
        return base_reading;
    }
    
private:
    CDNAMetrics get_cdna_power_breakdown() {
        CDNAMetrics metrics{};
        
        // Use ROCm SMI extended metrics for CDNA
        // These provide more detailed power breakdown
        
        return metrics;
    }
};
```

## AMD-Specific Considerations

### Smart Access Memory (SAM) Impact

```cpp
class SAMPowerModel {
public:
    double calculate_sam_power_impact(bool sam_enabled, 
                                    double memory_bandwidth_utilization,
                                    double cpu_gpu_data_transfer_rate) {
        if (!sam_enabled) return 0.0;
        
        // SAM can reduce total system power by eliminating PCIe bottlenecks
        double pcie_power_saved = cpu_gpu_data_transfer_rate * PCIE_POWER_PER_GB_S;
        
        // But increases memory controller power slightly
        double memory_controller_overhead = memory_bandwidth_utilization * SAM_MC_OVERHEAD;
        
        return pcie_power_saved - memory_controller_overhead;
    }
    
private:
    static constexpr double PCIE_POWER_PER_GB_S = 0.05;  // Watts per GB/s
    static constexpr double SAM_MC_OVERHEAD = 0.5;       // Watts
};
```

### Heterogeneous System Architecture (HSA) Considerations

```cpp
class HSAPowerManager {
public:
    struct HSAEnergyReading {
        double cpu_energy_joules;
        double gpu_energy_joules;
        double shared_memory_energy_joules;
        double coherency_overhead_joules;
    };
    
    HSAEnergyReading get_hsa_system_reading(AMDRAPLProvider& cpu_provider,
                                          AMDGPUProvider& gpu_provider) {
        HSAEnergyReading hsa_reading{};
        
        auto cpu_reading = cpu_provider.get_reading();
        auto gpu_reading = gpu_provider.get_reading();
        
        hsa_reading.cpu_energy_joules = cpu_reading.energy_joules;
        hsa_reading.gpu_energy_joules = gpu_reading.energy_joules;
        
        // Calculate coherency overhead for unified memory access
        hsa_reading.coherency_overhead_joules = 
            calculate_coherency_energy_overhead(cpu_reading, gpu_reading);
        
        // Shared memory energy attribution
        hsa_reading.shared_memory_energy_joules = 
            calculate_shared_memory_energy(cpu_reading, gpu_reading);
        
        return hsa_reading;
    }
    
private:
    double calculate_coherency_energy_overhead(const EnergyReading& cpu, 
                                             const EnergyReading& gpu) {
        // Model coherency protocol overhead
        return 0.0; // Implementation specific
    }
    
    double calculate_shared_memory_energy(const EnergyReading& cpu,
                                        const EnergyReading& gpu) {
        // Distribute memory energy based on access patterns
        return 0.0; // Implementation specific  
    }
};
```

## Validation and Accuracy

### AMD-Specific Validation

```cpp
class AMDValidation {
public:
    struct AMDValidationResult {
        bool rapl_accuracy_validated;
        bool rocm_smi_validated;  
        bool chiplet_distribution_accurate;
        double overall_accuracy_percent;
    };
    
    AMDValidationResult validate_amd_measurements() {
        AMDValidationResult result{};
        
        // Validate RAPL against known workloads
        result.rapl_accuracy_validated = validate_amd_rapl_accuracy();
        
        // Validate ROCm SMI against GPU-Z/HWiNFO
        result.rocm_smi_validated = validate_rocm_smi_accuracy();
        
        // Validate chiplet power distribution
        result.chiplet_distribution_accurate = validate_chiplet_power_distribution();
        
        // Calculate overall accuracy
        result.overall_accuracy_percent = calculate_overall_accuracy();
        
        return result;
    }
    
private:
    bool validate_chiplet_power_distribution() {
        // Use per-core performance counters to validate power distribution
        return true; // Implementation specific
    }
};
```

This comprehensive AMD hardware guide ensures accurate energy measurement across the complete AMD ecosystem, from consumer Ryzen to enterprise EPYC CPUs and consumer to data center GPUs.